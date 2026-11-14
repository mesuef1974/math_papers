#!/usr/bin/env python3
"""بوابة الدمج الآلي: تقرّر هل يُفعَّل `gh pr merge --auto` على طلب معيّن أم يبقى يدويًا. لا تدمج بنفسها.

الشروط (كلها لازمة):
  1. سطر اعتماد المالك في وصف الطلب مربوط برأس الطلب الحالي (scripts/approval.py).
  2. لا ملف متغيّر يطابق المسارات المحظورة (security/sensitive_paths.json → forbidden_for_auto_merge).
     ملفات CI والـ lockfiles وسكربتات البوابات نفسها محظورة دائمًا: النموذج لا يعدّل حارسه.
  3. كل فحوص CI خضراء (لا PENDING ولا FAILURE)، بآخر تشغيل لكل فحص: تشغيل قديم أُعيد بعده لا يُحسب.
     حالة «نافذة النشر» مستثناة: هي فحص مطلوب على main، فالدمج المفعَّل ينتظرها ويُنفَّذ عند فتح النافذة.

الاستعمال:  python scripts/merge_gate.py <رقم الطلب> [--repo owner/name] [--enable]
الخروج:     0 مسموح (أو فُعِّل)، 1 ممنوع يبقى يدويًا، 2 خطأ gh/شبكة.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from approval import approved_heads, same_head  # noqa: E402
from deploy_window import STATUS_CONTEXT as DEPLOY_WINDOW  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "security" / "sensitive_paths.json"

ALWAYS_FORBIDDEN = (
    ".github/*",
    ".github/**",
    "scripts/merge_gate.py",
    "scripts/approval.py",
    "scripts/pr_approval_head_check.py",
    "scripts/prepush_check.py",
    "security/*",
    ".claude/hooks/*",
    ".claude/settings.json",
    "package-lock.json",
    "frontend/package-lock.json",
    "requirements*.txt",
    "Dockerfile",
    "railway.toml",
)
FAILING = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
PENDING = {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "REQUESTED", "WAITING"}


def gh_json(args: list[str]) -> dict:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def forbidden_globs() -> tuple[str, ...]:
    extra: list[str] = []
    if RULES.exists():
        data = json.loads(RULES.read_text(encoding="utf-8"))
        extra = list(data.get("forbidden_for_auto_merge", []))
    return ALWAYS_FORBIDDEN + tuple(extra)


def path_forbidden(path: str, globs: tuple[str, ...]) -> str | None:
    for pattern in globs:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.lower(), pattern.lower()):
            return pattern
    return None


def check_name(check: dict) -> str:
    return check.get("name") or check.get("context") or "؟"


def latest_checks(checks: list[dict]) -> list[dict]:
    """آخر تشغيل لكل فحص. GitHub يُبقي التشغيل القديم في القائمة بعد إعادته (فحص الاعتماد يُعاد عند تعديل الوصف)."""
    latest: dict[tuple[str, str], dict] = {}
    for check in checks:
        key = (check.get("workflowName") or "", check_name(check))
        stamp = check.get("startedAt") or check.get("completedAt") or ""
        kept = latest.get(key)
        if kept is None or stamp >= (kept.get("startedAt") or kept.get("completedAt") or ""):
            latest[key] = check
    return list(latest.values())


def check_reasons(checks: list[dict]) -> list[str]:
    if not checks:
        return ["لا فحوص CI مسجّلة على الطلب بعد"]
    reasons = []
    for check in latest_checks(checks):
        name = check_name(check)
        if name == DEPLOY_WINDOW:
            continue
        state = (check.get("conclusion") or check.get("state") or check.get("status") or "").upper()
        if state in FAILING:
            reasons.append(f"فحص فاشل: {name}")
        elif state in PENDING or not state:
            reasons.append(f"فحص لم يكتمل: {name}")
    return reasons


def evaluate(pr: str, repo: str | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    args = ["pr", "view", pr, "--json", "body,files,statusCheckRollup,headRefOid"]
    if repo:
        args += ["--repo", repo]
    data = gh_json(args)

    head = data.get("headRefOid") or ""
    heads = approved_heads(data.get("body") or "")
    if not heads:
        reasons.append("لا سطر اعتماد («اعتُمد من المالك — YYYY-MM-DD — الرأس sha8») في وصف الطلب")
    elif not any(same_head(h, head) for h in heads):
        reasons.append(
            f"سطر الاعتماد على رأس قديم ({', '.join(h[:8] for h in heads)})، والرأس الحالي {head[:8]}"
        )

    globs = forbidden_globs()
    blocked = []
    for f in data.get("files") or []:
        path = f.get("path", "")
        pattern = path_forbidden(path, globs)
        if pattern:
            blocked.append(f"{path} ({pattern})")
    if blocked:
        reasons.append("مسارات محظورة على الدمج الآلي: " + "، ".join(blocked))

    reasons += check_reasons(data.get("statusCheckRollup") or [])
    return (not reasons), reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pr")
    ap.add_argument("--repo")
    ap.add_argument("--enable", action="store_true")
    args = ap.parse_args()
    try:
        ok, reasons = evaluate(args.pr, args.repo)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"[خطأ] {exc}", file=sys.stderr)
        return 2
    if ok:
        print(f"[مسموح] الطلب #{args.pr} يستوفي شروط الدمج الآلي")
        if args.enable:
            # squash طريقة الدمج الوحيدة في المستودع، وgh يطلبها صريحة خارج الطرفية التفاعلية.
            cmd = ["gh", "pr", "merge", args.pr, "--auto", "--squash"] + (
                ["--repo", args.repo] if args.repo else []
            )
            subprocess.run(cmd, check=True)
            print("[تفعيل] auto-merge مفعّل؛ GitHub يدمج حين تخضرّ الفحوص المطلوبة، ومنها «نافذة النشر»")
        return 0
    print(f"[ممنوع] الطلب #{args.pr} يبقى دمجًا يدويًا:")
    for r in reasons:
        print(f"  - {r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
