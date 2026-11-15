"""نافذة النشر: كل دمج إلى main نشر فوري على Railway، فلا دمج وقت الدوام إلا الإصلاح العاجل.

طريقتان للفرض، والإصلاح العاجل يمرّ فيهما بوسم LABEL على الطلب:
  - `deploy_window.py status`: حالة إيداع STATUS_CONTEXT على رأس كل طلب مفتوح إلى main، حمراء وقت الدوام
    وخضراء خارجه. هي فحص مطلوب على main، فيمنع GitHub الدمج اليدوي والتلقائي داخل النافذة، ويُدمج الطلب
    المفعَّل دمجه وحده عند فتحها. يحدّثها سير عمل مجدول وأحداث الطلب (`.github/workflows/deploy-window.yml`).
    الحالة تُغلق قبل الدوام بـ GUARD_MINUTES احتياطًا لتأخر جدولة GitHub.
  - طابور الدمج (merge_group) حيث يتاح (مستودعات المنظمات)، بلا وسيط: يرفض المجموعة وقت الدوام.
الإعداد من القالب: الإزاحة 3 ساعة، الأيام weekday() = 6,0,1,2,3، الساعات 07-14.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone

# قرار المالك 2026-11-15: النشر مسموح لهذا المشروع في أي وقت. False يُخضّر الحالة دائمًا؛ True يعيد فرض نافذة الدوام.
ENFORCED = False
LOCAL_TZ = timezone(timedelta(hours=int("3")))
WORK_DAYS = {int(d) for d in "6,0,1,2,3".split(",")}
_HOURS = "07-14".split("-")
WINDOW_START_HOUR, WINDOW_END_HOUR = int(_HOURS[0]), int(_HOURS[1])
LABEL = "نشر-عاجل"
STATUS_CONTEXT = "نافذة النشر"
GUARD_MINUTES = 30
_QUEUE_PR_RE = re.compile(r"/pr-(\d+)-")


def in_work_hours(now: datetime) -> bool:
    if not ENFORCED:
        return False
    local = now.astimezone(LOCAL_TZ)
    return local.weekday() in WORK_DAYS and WINDOW_START_HOUR <= local.hour < WINDOW_END_HOUR


def queued_pr_number(head_ref: str) -> int | None:
    m = _QUEUE_PR_RE.search(head_ref)
    return int(m.group(1)) if m else None


def pr_labels(repo: str, number: int) -> list[str]:
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{number}", "--jq", "[.labels[].name]"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)


def decide(event: str, now: datetime, labels: list[str] | None) -> tuple[bool, str]:
    local = now.astimezone(LOCAL_TZ).strftime("%A %H:%M")
    end = f"{WINDOW_END_HOUR}:00"
    if not ENFORCED:
        return True, f"نافذة النشر معطّلة بقرار المالك ({local}) — النشر مسموح."
    if not in_work_hours(now):
        return True, f"خارج الدوام ({local}) — النشر مسموح."
    if event != "merge_group":
        return True, f"وقت الدوام ({local}) — لا منع هنا؛ طابور الدمج سيرفض حتى {end} ما لم يُوسم «{LABEL}»."
    if labels and LABEL in labels:
        return True, f"وقت الدوام ({local}) لكن الطلب موسوم «{LABEL}» — يمرّ إصلاحًا عاجلًا."
    return False, f"وقت الدوام ({local}): الدمج نشر فوري وممنوع الآن. أعد بعد {end} أو وسم الطلب «{LABEL}»."


def closed_for_status(now: datetime) -> bool:
    """وقت الدوام، أو ما قبله بمدة الاحتياط: الجدولة قد تتأخر دقائق، فتُغلق الحالة قبل بدء الدوام لا بعده."""
    return in_work_hours(now) or in_work_hours(now + timedelta(minutes=GUARD_MINUTES))


def status_for(now: datetime, labels: list[str]) -> tuple[str, str]:
    local = now.astimezone(LOCAL_TZ).strftime("%A %H:%M")
    if not ENFORCED:
        return "success", f"نافذة النشر معطّلة بقرار المالك ({local}) — الدمج مسموح في أي وقت."
    if not closed_for_status(now):
        return "success", f"خارج الدوام ({local}) — الدمج مسموح."
    if LABEL in labels:
        return "success", f"وقت الدوام ({local}) والطلب موسوم «{LABEL}» — يمرّ إصلاحًا عاجلًا."
    return (
        "failure",
        f"وقت الدوام ({local}): الدمج نشر فوري وممنوع حتى {WINDOW_END_HOUR}:00، أو وسم «{LABEL}».",
    )


def open_prs(repo: str, base: str) -> list[dict]:
    out = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/pulls?state=open&base={base}&per_page=100",
            "--jq",
            ".[] | {number, sha: .head.sha, labels: [.labels[].name]}",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def post_status(repo: str, sha: str, state: str, description: str) -> None:
    subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/statuses/{sha}",
            "-f",
            f"state={state}",
            "-f",
            f"context={STATUS_CONTEXT}",
            "-f",
            f"description={description[:140]}",
        ],
        check=True,
        capture_output=True,
    )


def update_statuses(repo: str, base: str, now: datetime) -> list[tuple[int, str]]:
    """يكتب الحالة على رأس كل طلب مفتوح؛ إعادة التشغيل تكتب القيمة نفسها (idempotent)."""
    written = []
    for pr in open_prs(repo, base):
        state, description = status_for(now, pr["labels"])
        post_status(repo, pr["sha"], state, description)
        written.append((pr["number"], state))
    return written


def main_status() -> int:
    written = update_statuses(os.environ["REPO"], os.environ.get("BASE", "main"), datetime.now(UTC))
    for number, state in written:
        print(f"#{number}: {STATUS_CONTEXT} = {state}")
    if not written:
        print("لا طلبات مفتوحة")
    return 0


def main() -> int:
    if sys.argv[1:] == ["status"]:
        return main_status()
    event = os.environ.get("EVENT", "")
    now = datetime.now(UTC)
    labels = None
    if event == "merge_group" and in_work_hours(now):
        number = queued_pr_number(os.environ.get("HEAD_REF", ""))
        if number is not None:
            labels = pr_labels(os.environ["REPO"], number)
    allowed, message = decide(event, now, labels)
    print(message if allowed else f"::error::{message}")
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())
