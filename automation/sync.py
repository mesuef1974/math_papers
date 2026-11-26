#!/usr/bin/env python3
"""مزامنة الدفتر مع GitHub: أحداث ما بعد فتح الطلب تُكتب من حالة الطلب نفسها لا من ذاكرة الجلسة.

    python automation/sync.py [--apply] [--repo owner/name]   # بلا --apply يعرض ما سيكتبه فقط
    python automation/sync.py --worktrees                      # أشجار وفروع البطاقات المنتهية (عرض فقط)

البطاقة تُطابَق بفرعها `card/<المعرّف>`. طلب مدموج ← `merged`، وطلب مفتوح لبطاقة لم تسجّله ← `pr_opened`.
طلب أُغلق بلا دمج يُذكر ولا يُكتب له حدث: إلغاء البطاقة قرار. `deployed` لا يُعرف من GitHub (النشر على
Railway) فيبقى حدثًا يدويًا. المشغّل يستدعي `quiet()` في كل تشغيل، وبلا بطاقة معلّقة لا يُستدعى gh.
`--worktrees` لا يحذف شيئًا: الحذف بيد المالك.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402
import notify  # noqa: E402

OPEN_STATES = ("prepush_ok", "pr_opened", "ci_green", "approved")
DONE_STATES = ("merged", "deployed", "cancelled")
BRANCH_PREFIX = "card/"
PR_FIELDS = "number,state,url,headRefName,mergedAt,mergeCommit"
DEPLOY_WINDOW = timedelta(hours=24)  # بطاقة دُمجت قبلها لا يُسأل عن نشرها كل خمس دقائق
PR_LIMIT = "500"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ledger.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def fetch_prs(repo: str | None) -> list[dict]:
    cmd = ["gh", "pr", "list", "--state", "all", "--limit", PR_LIMIT, "--json", PR_FIELDS]
    proc = run(cmd + (["--repo", repo] if repo else []))
    if proc.returncode != 0:
        raise RuntimeError(f"gh فشل: {(proc.stderr or '').strip()[:160]}")
    return json.loads(proc.stdout or "[]")


def decide(state: str, prs: list[dict]) -> tuple[str | None, dict | None]:
    """حالة البطاقة وطلبات فرعها ← الحدث الذي يُكتب (أو None) والطلب الذي يشهد له."""
    merged = [pr for pr in prs if pr.get("state") == "MERGED"]
    if merged:
        return "merged", max(merged, key=lambda pr: pr.get("mergedAt") or "")
    opened = [pr for pr in prs if pr.get("state") == "OPEN"]
    if opened and state == "prepush_ok":
        return "pr_opened", opened[0]
    return None, (opened or prs or [None])[0]


def plan(prs: list[dict]) -> list[tuple[str, str | None, dict | None]]:
    """لكل بطاقة معلّقة: (المعرّف، الحدث أو None، الطلب أو None)."""
    by_branch: dict[str, list[dict]] = {}
    for pr in prs:
        by_branch.setdefault(pr.get("headRefName") or "", []).append(pr)
    rows = []
    for card in ledger.cards_in(*OPEN_STATES):
        event, pr = decide(ledger.state(card)["event"], by_branch.get(BRANCH_PREFIX + card, []))
        rows.append((card, event, pr))
    return rows


def apply(rows: list[tuple[str, str | None, dict | None]]) -> list[str]:
    written = []
    for card, event, pr in rows:
        if event:
            ledger.append(card, event, pr=pr["number"], url=pr.get("url", ""), note="sync")
            written.append(f"{card} → {event} (#{pr['number']})")
    return written


def awaiting_deploy(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    return [
        card
        for card in ledger.cards_in("merged")
        if now - datetime.fromisoformat(ledger.state(card)["at"]) <= DEPLOY_WINDOW
    ]


def deploy_states(sha: str, repo: str | None) -> set[str]:
    """حالات نشر Railway لهذا الإيداع كما يكتبها على GitHub؛ فارغة = لا نشر بعد."""
    base = f"repos/{repo or '{owner}/{repo}'}/deployments"
    found = run(["gh", "api", f"{base}?sha={sha}", "--jq", ".[].id"])
    states: set[str] = set()
    for deployment in found.stdout.split() if found.returncode == 0 else []:
        proc = run(["gh", "api", f"{base}/{deployment}/statuses", "--jq", ".[].state"])
        states |= set(proc.stdout.split()) if proc.returncode == 0 else set()
    return states


def apply_deploys(cards: list[str], prs: list[dict], repo: str | None) -> list[str]:
    """النجاح ← `deployed`، والفشل ← `blocked` مع إشعار؛ ما لم يُحسم يبقى للدورة التالية."""
    written = []
    for card in cards:
        _, pr = decide("merged", [p for p in prs if p.get("headRefName") == BRANCH_PREFIX + card])
        sha = ((pr or {}).get("mergeCommit") or {}).get("oid")
        if not sha:
            continue
        states = deploy_states(sha, repo)
        if "success" in states:
            ledger.append(card, "deployed", pr=pr["number"], url=pr.get("url", ""), note="sync")
        elif states & {"failure", "error"}:
            ledger.append(card, "blocked", reason="فشل النشر على Railway", url=pr.get("url", ""))
            notify.send("المشغّل: فشل النشر", f"{card} (#{pr['number']})")
        else:
            continue
        written.append(f"{card} → {ledger.state(card)['event']} (#{pr['number']})")
    return written


def quiet(repo: str | None = None) -> str:
    """للمشغّل: يزامن دون أن يُفشل تشغيله. يعيد ما كُتب، أو سبب التعذّر، أو نصًّا فارغًا."""
    try:
        waiting = awaiting_deploy()
        if not ledger.cards_in(*OPEN_STATES) and not waiting:
            return ""
        prs = fetch_prs(repo)
        written = apply(plan(prs))
        written += apply_deploys(awaiting_deploy(), prs, repo)
        return "، ".join(written)
    except Exception as exc:  # المزامنة خدمة جانبية: شبكة أو gh غائب لا يوقف البطاقات
        return f"تعذّرت ({type(exc).__name__})"


def card_worktrees(porcelain: str) -> list[tuple[str, str]]:
    """مخرج `git worktree list --porcelain` ← (المسار، الفرع) لأشجار فروع البطاقات."""
    out, path = [], ""
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line.startswith("branch refs/heads/" + BRANCH_PREFIX):
            out.append((path, line[len("branch refs/heads/") :]))
    return out


def finished_worktrees(porcelain: str) -> list[tuple[str, str, str]]:
    """أشجار بطاقات انتهت في الدفتر: (المسار، الفرع، الحالة)."""
    rows = []
    for path, branch in card_worktrees(porcelain):
        state = ledger.state(branch[len(BRANCH_PREFIX) :])
        if state and state["event"] in DONE_STATES:
            rows.append((path, branch, state["event"]))
    return rows


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--repo")
    ap.add_argument("--worktrees", action="store_true")
    args = ap.parse_args(argv)

    if args.worktrees:
        rows = finished_worktrees(run(["git", "worktree", "list", "--porcelain"]).stdout)
        for path, branch, state in rows:
            print(f"{state:<10} {branch}  {path}")
        print(
            f"{len(rows)} شجرة لبطاقات منتهية — الحذف بيد المالك: git worktree remove <المسار> ثم git branch -d <الفرع>"
        )
        return 0

    try:
        rows = plan(fetch_prs(args.repo))
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[خطأ] {exc}", file=sys.stderr)
        return 2
    for card, event, pr in rows:
        where = f"#{pr['number']} {pr['state']}" if pr else "لا طلب على فرعها"
        print(f"{card}  {ledger.state(card)['event']:<11} → {event or 'يبقى'}  ({where})")
    if args.apply:
        for line in apply(rows):
            print("كُتب:", line)
    elif any(event for _, event, _ in rows):
        print("عرض فقط — أعِد بـ --apply للكتابة")
    return 0


if __name__ == "__main__":
    sys.exit(main())
