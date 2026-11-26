"""إرسال لقطة لوحة المشغّل إلى المنصة المنشورة (صفحة /automation).

يعمل حين يُضبط على الجهاز BOARD_PUSH_URL (https) وBOARD_PUSH_TOKEN، وإلا لا يفعل شيئًا.
خدمة جانبية: تعذّرها لا يوقف بطاقة.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import board  # noqa: E402

INTERVAL = 15
TIMEOUT = 10
PR_CACHE = {"at": 0.0, "urls": None}
FIELDS = ("id", "title", "group", "at_stage", "age", "url", "note")


def open_prs() -> set[str] | None:
    if not PR_CACHE["at"] or time.monotonic() - PR_CACHE["at"] >= board.PR_CACHE_SECONDS:
        PR_CACHE.update(at=time.monotonic(), urls=board.open_pr_urls())
    return PR_CACHE["urls"]


def payload(snap: dict) -> dict:
    groups = snap["groups"]
    done = sorted(groups["done"], key=lambda row: row["since"])
    rows = [row for key in groups if key != "done" for row in groups[key]] + done
    return {
        "stages": [label for _, label in board.STAGES],
        "cards": [{key: row[key] for key in FIELDS} | {"title": row["title"][:300]} for row in rows[:500]],
        "pulse": {"text": snap["pulse"]["text"][:500], "warn": snap["pulse"]["warn"]},
    }


def send() -> str:
    """نص فارغ عند النجاح أو غياب الإعداد، وسبب التعذّر غير ذلك (بلا المفتاح)."""
    url, token = os.environ.get("BOARD_PUSH_URL", ""), os.environ.get("BOARD_PUSH_TOKEN", "")
    if not url or not token:
        return ""
    if not url.startswith("https://"):
        return "تعذّر إرسال اللوحة (العنوان ليس https)"
    try:
        body = json.dumps(payload(board.snapshot(open_prs=open_prs())), ensure_ascii=False).encode()
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT):
            return ""
    except Exception as exc:  # شبكة أو دفتر تالف: لا يوقف المشغّل
        return f"تعذّر إرسال اللوحة ({type(exc).__name__})"


@contextlib.contextmanager
def live():
    """يرسل كل INTERVAL ثانية ما دامت البطاقة تعمل، فترى الصفحة مراحلها."""
    stop = threading.Event()

    def loop():
        send()
        while not stop.wait(INTERVAL):
            send()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(TIMEOUT + 25)
