#!/usr/bin/env python3
"""لوحة محلية حية لبطاقات المشغّل: أين وصلت كل بطاقة، وما ينتظر اعتمادك، وما علق.

للقراءة فقط: تقرأ دفتر البطاقات وسجل نبض المشغّل (وقائمة الطلبات المفتوحة من gh إن توفرت) ولا تكتب شيئًا.
تعمل على 127.0.0.1 وحده، وتُغلق نفسها حين لا يطلبها متصفح، فلا يبقى خادم منسي.

    .venv\\Scripts\\pythonw.exe scripts\\board.py --open
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from automation import ledger  # noqa: E402
from scripts import factory_view  # noqa: E402

PORT = 8791
REFRESH_SECONDS = 3
FLOW_DONE_LIMIT = 5
IDLE_EXIT_SECONDS = 15 * 60  # المتصفح يبطّئ تحديث التبويب المخفي، فالمهلة أطول من التحديث بكثير
PR_CACHE_SECONDS = 60
RECENT_DONE = timedelta(hours=48)
RUNNER_SILENT = timedelta(minutes=12)

# (الحالة في الدفتر، ما يجري الآن): ترتيبها هو ترتيب شريط المراحل
STAGES = (
    ("ready", "في الطابور"),
    ("claimed", "البرمجة"),
    ("coded", "الفحص المحلي"),
    ("prepush_ok", "المراجعة المستقلة"),
    ("pr_opened", "اعتمادك"),
    ("merged", "الدمج والنشر"),
)
STAGE_OF = {state: i for i, (state, _) in enumerate(STAGES)} | {"ci_green": 4, "approved": 4, "deployed": 5}
IN_PROGRESS = ("claimed", "coded", "prepush_ok")
STOPPED_AT = {"blocked": 1, "prepush_failed": 2}  # حيث توقفت على الرسم
GROUPS = (
    ("running", "تعمل الآن"),
    ("approval", "تنتظر اعتمادك"),
    ("queued", "في الطابور"),
    ("stuck", "عالقة وتحتاج نظرًا"),
    ("done", "انتهت خلال 48 ساعة"),
    ("backlog", "لم تُجهَّز بعد"),
)


def pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes  # os.kill على ويندوز يُنهي العملية، فلا يصلح للسؤال

    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def open_pr_urls() -> set[str] | None:
    """روابط الطلبات المفتوحة؛ None حين لا يتوفر gh فلا يُحكم على بطاقة بأن طلبها أُغلق."""
    if not shutil.which("gh"):
        return None
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--limit", "100", "--json", "url"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        return {row["url"] for row in json.loads(out)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def age(delta: timedelta) -> str:
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} د"
    if minutes < 48 * 60:
        return f"{minutes // 60} س {minutes % 60} د"
    return f"{minutes // (24 * 60)} ي"


def card_row(card_id: str, now: datetime, alive, open_prs: set[str] | None) -> dict | None:
    """صف البطاقة ومجموعتها، أو None لما لا يُعرض (ملغاة، أو مدموجة قديمة)."""
    events = ledger.events(card_id)
    if not events or events[-1]["event"] == "cancelled":
        return None
    last = events[-1]
    state, since = last["event"], now - datetime.fromisoformat(last["at"])
    url = next((e["url"] for e in reversed(events) if e.get("url")), "")
    pid = next((e["pid"] for e in reversed(events) if e.get("pid")), None)
    row = {
        "id": card_id,
        "title": events[0].get("title", ""),
        "stage": STAGE_OF.get(state),
        "at_stage": STAGE_OF.get(state, last.get("stage", STOPPED_AT.get(state, 1))),
        "since": since,
        "age": age(since),
        "url": url,
        "note": "",
        "usage": next((e["usage"] for e in reversed(events) if e.get("usage")), {}),
        "review_usage": next((e["review"] for e in reversed(events) if e.get("review")), {}),
    }
    if state in ("merged", "deployed"):
        note = "" if state == "merged" else "منشورة"
        return row | {"group": "done", "note": note} if since <= RECENT_DONE else None
    if state == "created":
        return row | {"group": "backlog"}
    if state == "ready":
        return row | {"group": "queued"}
    if state in IN_PROGRESS:
        if pid and alive(pid):
            return row | {"group": "running"}
        return row | {"group": "stuck", "note": "انقطع تشغيلها: لا عملية تعمل عليها"}
    if state in ("pr_opened", "ci_green", "approved"):
        if open_prs is not None and url and url not in open_prs:
            note = "الطلب لم يعد مفتوحًا والدفتر لم يسجّل ذلك بعد"
            return row | {"group": "done", "note": note, "stage": None}
        return row | {"group": "approval"}
    notes = {"blocked": last.get("reason") or "محجوبة", "prepush_failed": "فشل الفحص المحلي"}
    return row | {"group": "stuck", "note": notes.get(state, state)}


def runner_pulse(root: Path, now: datetime) -> dict:
    log = root / ".worktrees" / "runner.log"
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    if not lines:
        return {"text": "لا سجل نبض للمشغّل", "warn": True}
    stamp, _, outcome = lines[-1].partition(" ")
    since = now - datetime.fromisoformat(stamp)
    return {"text": f"آخر نبض للمشغّل منذ {age(since)}: {outcome}", "warn": since > RUNNER_SILENT}


def snapshot(
    root: Path = ROOT, now: datetime | None = None, alive=pid_alive, open_prs: set[str] | None = None
) -> dict:
    now = now or datetime.now(UTC)
    rows = [row for card in ledger.all_cards() if (row := card_row(card, now, alive, open_prs))]
    groups = {key: [r for r in rows if r["group"] == key] for key, _ in GROUPS}
    pulse = runner_pulse(root, now)
    if groups["running"]:  # السجل يُكتب عند انتهاء البطاقة، فصمته أثناء العمل ليس تعطلًا
        pulse["warn"] = False
    try:
        health = json.loads((root / "automation" / ".health").read_text(encoding="utf-8"))
        halted = int(health["streak"]) >= 2
    except (OSError, ValueError, KeyError, TypeError):
        halted = False
    return {"groups": groups, "pulse": pulse, "halted": halted, "at": now.astimezone().strftime("%H:%M:%S")}


def render_chip(row: dict) -> str:
    e = html.escape
    # الاسم نفسه قبل التحديث وبعده، فينقل المتصفح الرقاقة من مرحلتها القديمة إلى الجديدة
    return (
        f'<div class="chip {row["group"]}" style="view-transition-name: c-{e(row["id"])}" title="{e(row["title"])}">'
        f'<code dir="ltr">'
        f"{e(row['id'][-6:])}</code> <small><bdi>{e(row['age'])}</bdi>{' ✓ منشورة' if row['note'] == 'منشورة' else ''}</small><span>{e(row['title'])}</span></div>"
    )


def render_flow(groups: dict) -> str:
    """رسم المراحل وفيه كل بطاقة حية أو عالقة في مرحلتها، وأحدث المدموجة؛ غير المجهَّزة لا تدخله."""
    live = [row for key in ("running", "approval", "queued", "stuck") for row in groups[key]]
    done = sorted(groups["done"], key=lambda row: row["since"])[:FLOW_DONE_LIMIT]
    columns = []
    for i, (_, label) in enumerate(STAGES):
        rows = done if i == len(STAGES) - 1 else [row for row in live if row["at_stage"] == i]
        total = len(groups["done"]) if i == len(STAGES) - 1 else len(rows)
        busy = " busy" if any(row["group"] == "running" for row in rows) else ""
        chips = "".join(map(render_chip, rows))
        columns.append(f'<li class="stage{busy}"><div class="node">{label} <b>{total}</b></div>{chips}</li>')
    return f'<ol class="flow" aria-label="مخطط المراحل">{"".join(columns)}</ol>'


def render_card(row: dict) -> str:
    e = html.escape
    steps = ""
    if row["stage"] is not None:
        items = "".join(
            f'<li class="{"past" if i < row["stage"] else "now" if i == row["stage"] else ""}">{label}</li>'
            for i, (_, label) in enumerate(STAGES)
        )
        steps = f'<ol class="steps">{items}</ol>'
    link = ""
    if row["url"].startswith("https://github.com/"):
        number = e(row["url"].rsplit("/", 1)[-1])
        link = f' <a href="{e(row["url"])}" target="_blank" rel="noreferrer">الطلب {number}</a>'
    note = f'<p class="note">{e(row["note"])}</p>' if row["note"] else ""
    return (
        f'<article><h3>{e(row["title"])}</h3><p class="meta"><code>{e(row["id"])}</code>'
        f" في حالتها منذ {e(row['age'])}{link}</p>{steps}{note}</article>"
    )


STYLE = """
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: var(--color-paper); color: var(--color-ink);
  font-family: var(--font-sans); line-height: 1.6; }
main { max-width: 1280px; margin-inline: auto; }
h1 { margin: 0; }
h2 { margin-block: 28px 8px; font-size: 1.15rem; }
h3 { margin: 0; font-size: 1rem; }
.pulse { color: var(--color-ink-soft); }
.pulse.warn { color: var(--color-danger); font-weight: 700; }
article { background: var(--color-surface); border: 1px solid var(--color-line); border-radius: 12px;
  padding: 12px 14px; margin-block-end: 10px; }
.stuck article { border-inline-start: 4px solid var(--color-danger); }
.running article { border-inline-start: 4px solid var(--color-info); }
.approval article { border-inline-start: 4px solid var(--color-brand); }
.meta { margin: 4px 0; color: var(--color-ink-soft); font-size: .88rem; }
.note { margin: 6px 0 0; color: var(--color-danger); font-size: .9rem; }
a { color: var(--color-brand); }
.steps { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; margin: 6px 0 0; padding: 0; }
.steps li { border: 1px solid var(--color-line); border-radius: 999px; padding: 1px 10px; font-size: .8rem;
  color: var(--color-ink-soft); }
.steps li.past { background: var(--color-success-soft); color: var(--color-success); }
.steps li.now { background: var(--color-brand); border-color: var(--color-brand); color: var(--color-on-brand); }
summary { cursor: pointer; margin-block: 28px 8px; font-weight: 700; }
.flow { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 18px; list-style: none;
  margin: 20px 0 0; padding: 0; align-items: start; }
.stage { position: relative; min-width: 0; }
.node { border: 2px solid var(--color-line-strong); border-radius: 12px; background: var(--color-surface);
  text-align: center; padding: 8px 4px; font-weight: 700; margin-block-end: 8px; }
.stage + .stage::before { content: "←"; position: absolute; inset-inline-start: -17px; inset-block-start: 8px;
  color: var(--color-ink-soft); }
.stage.busy .node { border-color: var(--color-info); background: var(--color-info-soft); color: var(--color-info);
  animation: pulse 1.6s ease-in-out infinite; }
.chip { border: 1px solid var(--color-line); border-inline-start: 4px solid var(--color-line-strong);
  border-radius: 8px; background: var(--color-surface); padding: 4px 8px; margin-block-end: 6px; font-size: .8rem; }
.chip span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.chip.running { border-color: var(--color-info); }
.chip.approval { border-color: var(--color-brand); }
.chip.stuck { border-color: var(--color-danger); }
.chip.done { border-color: var(--color-success); }
@keyframes pulse { 50% { opacity: .55; } }
::view-transition-group(*) { animation-duration: .9s; }
@media (max-width: 760px) {
  .flow { grid-template-columns: 1fr; gap: 8px; }
  .stage + .stage::before { content: none; }
}
@media (prefers-reduced-motion: reduce) {
  .stage.busy .node { animation: none; }
  ::view-transition-group(*) { animation: none; }
}
"""


# يجلب الصفحة نفسها ويبدّل محتواها بانتقال مرئي، فتُرى البطاقة وهي تنتقل؛ الأقسام المفتوحة تبقى مفتوحة
SCRIPT = """
const REFRESH = __REFRESH__ * 1000;
async function tick() {
  try {
    const res = await fetch("/", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const next = new DOMParser().parseFromString(await res.text(), "text/html").querySelector("main");
    const open = [...document.querySelectorAll("details[open]")].map((d) => d.className);
    next.querySelectorAll("details").forEach((d) => { d.open = open.includes(d.className); });
    const swap = () => document.querySelector("main").replaceWith(next);
    if (document.startViewTransition && !document.hidden) await document.startViewTransition(swap).finished;
    else swap();
  } catch {
    const pulse = document.querySelector(".pulse");
    pulse.textContent = "انقطع الاتصال باللوحة: أعد تشغيلها";
    pulse.classList.add("warn");
  }
  setTimeout(tick, REFRESH);
}
setTimeout(tick, REFRESH);
""".replace("__REFRESH__", str(REFRESH_SECONDS))


def render(data: dict, tokens: str) -> str:
    sections = []
    for key, title in GROUPS:
        rows = data["groups"][key]
        cards = "".join(map(render_card, rows)) or '<p class="meta">لا شيء</p>'
        head = f"{title} ({len(rows)})"
        if key in ("done", "backlog"):  # لا تزاحم العمل الحي
            sections.append(f'<details class="{key}"><summary>{head}</summary>{cards}</details>')
        else:
            sections.append(f'<section class="{key}"><h2>{head}</h2>{cards}</section>')
    pulse = data["pulse"]
    warn = " warn" if pulse["warn"] else ""
    return (
        '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>بطاقات المشغّل</title><style>{tokens}{STYLE}{factory_view.STYLE}</style></head><body><main>"
        f'<h1>مصنع البطاقات</h1><p class="pulse{warn}">'
        f"{html.escape(pulse['text'])} | حُدّثت {data['at']}</p>"
        f"{factory_view.render(data['groups'], pulse, data['halted'])}{render_flow(data['groups'])}"
        f"{''.join(sections)}</main><script>{SCRIPT}</script></body></html>"
    )


def local_host(header: str | None) -> bool:
    """يرفض اسم مضيف غير محلي، فلا تقرأ صفحة خارجية اللوحة بإعادة ربط DNS."""
    return (header or "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost")


class Board(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # وإلا سمح ويندوز بخادمين على المنفذ نفسه

    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), Handler)
        self.seen = time.monotonic()
        self.prs: tuple[float, set[str] | None] = (float("-inf"), None)

    def open_prs(self) -> set[str] | None:
        fetched, urls = self.prs
        if time.monotonic() - fetched > PR_CACHE_SECONDS:
            urls = open_pr_urls()
            self.prs = (time.monotonic(), urls)
        return urls


class Handler(BaseHTTPRequestHandler):
    server: Board

    def do_GET(self):
        if not local_host(self.headers.get("Host")):
            return self.send_error(403)
        if self.path != "/":
            return self.send_error(404)
        self.server.seen = time.monotonic()
        tokens = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
        body = render(snapshot(open_prs=self.server.open_prs()), tokens).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pythonw بلا stderr
        pass


def exit_when_idle(server: Board) -> None:
    while time.monotonic() - server.seen < IDLE_EXIT_SECONDS:
        time.sleep(30)
    server.shutdown()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="لوحة بطاقات المشغّل المحلية")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--open", action="store_true", help="افتح اللوحة في المتصفح")
    args = ap.parse_args(argv)
    url = f"http://127.0.0.1:{args.port}/"
    try:
        server = Board(args.port)
    except OSError:  # تعمل أصلًا على المنفذ
        if args.open:
            webbrowser.open(url)
        return 0
    threading.Thread(target=exit_when_idle, args=(server,), daemon=True).start()
    if args.open:
        webbrowser.open(url)
    server.serve_forever()
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
