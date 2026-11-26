"""رسم المصنع: محطاته كما يعمل المشغّل فعلًا، على غرار رسم أتمتة «منصة تعليم قطر».

يقرأ لقطة اللوحة ولا يكتب شيئًا. المحطة الجارية تنبض ومسارها يسري، وما فيه عالق يحمرّ، وبوابة المالك متقطّعة.
"""

from __future__ import annotations

import html

W, H, BW, BH = 1000, 440, 168, 96
# (المفتاح، العنوان، ما يجري فيها، x، y)
NODES = (
    ("backlog", "البطاقات", "مواصفة وشرط نجاح", 816, 48),
    ("queue", "الطابور", "المشغّل كل 5 دقائق", 612, 48),
    ("build", "التنفيذ", "Sonnet في شجرة مستقلة", 408, 48),
    ("check", "الفحص المحلي", "ruff والهجرات والاختبارات", 204, 48),
    ("review", "المراجعة المستقلة", "Opus للقراءة فقط", 16, 48),
    ("approve", "اعتمادك", "البوابة البشرية", 16, 224),
    ("deploy", "الدمج والنشر", "GitHub ثم Railway", 204, 224),
    ("live", "منشورة", "خلال 48 ساعة", 408, 224),
    ("stuck", "تحتاج نظرًا", "فشل أو انقطاع", 816, 224),
)
EDGES = (
    ("backlog", "queue"),
    ("queue", "build"),
    ("build", "check"),
    ("check", "review"),
    ("review", "approve"),
    ("approve", "deploy"),
    ("deploy", "live"),
)
STATION = ("queue", "build", "check", "review", "approve", "deploy")  # بترتيب مراحل اللوحة
SAFEGUARDS = (
    "لا دمج قبل اعتمادك، والاعتماد مربوط برأس الإيداع فيسقط إن تغيّر",
    "النموذج لا يدفع ولا يفتح طلبًا؛ المشغّل وحده، وبعد فحص ناجح على الرأس نفسه",
    "ما يمسّ الحرّاس والمسارات المحظورة لا يُدفع آليًا",
    "إعادة واحدة للانقطاع أو فشل النموذج، ولا إعادة لفشل الفحص",
    "إخفاقان متتاليان يوقفان المشغّل حتى تستأنفه",
    "المراجعة الآلية رأي لا اعتماد",
)


def place(rows: dict) -> dict[str, list[dict]]:
    """لقطة اللوحة (المجموعات) ← بطاقات كل محطة."""
    at: dict[str, list[dict]] = {key: [] for key, *_ in NODES}
    at["backlog"] = list(rows["backlog"])
    for group in ("running", "approval", "queued"):
        for row in rows[group]:
            at[STATION[min(row["at_stage"], len(STATION) - 1)]].append(row)
    at["stuck"] = list(rows["stuck"])
    for row in rows["done"]:
        at["live" if row["note"] == "منشورة" else "deploy"].append(row)
    return at


def tone(key: str, cards: list[dict]) -> str:
    if any(row["group"] == "running" for row in cards):
        return "run"
    if not cards or key == "backlog":
        return "idle"
    return "bad" if key == "stuck" else "wait" if key == "approve" else "ok"


def short(text: str, limit: int = 24) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def spent(usage: dict) -> str:
    if not usage:
        return ""
    total = sum(usage.get(k) or 0 for k in ("input", "cache_write", "cache_read", "output"))
    cost = usage.get("cost_usd")
    return f"{total / 1e6:.1f}م توكن" + (f" · ${cost:.2f}" if cost else "")


def _node(key: str, title: str, sub: str, x: int, y: int, cards: list[dict]) -> str:
    e = html.escape
    state = tone(key, cards)
    latest = min(cards, key=lambda row: row["since"]) if cards else None
    note = e(short(latest["title"])) if latest else ""
    usage = ""
    if latest and key in ("check", "review", "approve", "build"):
        usage = e(spent(latest.get("review_usage" if key == "review" else "usage") or {}))
    halo = (
        f'<rect class="halo" x="-7" y="-7" width="{BW + 14}" height="{BH + 14}" rx="20"/>'
        if state == "run"
        else ""
    )
    return (
        f'<g class="node {state}{" human" if key == "approve" else ""}" transform="translate({x},{y})">{halo}'
        f'<rect width="{BW}" height="{BH}" rx="14"/>'
        f'<text x="{BW - 12}" y="24" class="title">{title}</text>'
        f'<text x="{BW - 12}" y="42" class="sub">{sub}</text>'
        f'<text x="{BW - 12}" y="64" class="note">{note}</text>'
        f'<text x="{BW - 12}" y="84" class="sub">{usage}</text>'
        f'<circle cx="22" cy="20" r="13" class="badge"/><text x="22" y="25" class="count">{len(cards)}</text></g>'
    )


def _edge(a: str, b: str, running: bool) -> str:
    spots = {key: (x, y) for key, _, _, x, y in NODES}
    (ax, ay), (bx, by) = spots[a], spots[b]
    if ay == by:
        left = bx < ax
        d = f"M{ax if left else ax + BW},{ay + BH / 2} L{bx + BW if left else bx},{by + BH / 2}"
    else:
        d = f"M{ax + BW / 2},{ay + BH} L{bx + BW / 2},{by}"
    flow = f'<path d="{d}" class="packet"/>' if running else ""
    return f'<path d="{d}" class="flow{" run" if running else ""}" marker-end="url(#arrow)"/>{flow}'


def render(groups: dict, pulse: dict, halted: bool) -> str:
    at = place(groups)
    running = {key for key, cards in at.items() if tone(key, cards) == "run"}
    edges = "".join(_edge(a, b, b in running) for a, b in EDGES)
    nodes = "".join(_node(*spec, at[spec[0]]) for spec in NODES)
    state = "bad" if halted or pulse["warn"] else "run" if running else ""
    worker = "متوقف بعد إخفاقين: runner.py --resume" if halted else pulse["text"]
    valves = "".join(f"<li>{item}</li>" for item in SAFEGUARDS)
    return (
        f'<div class="factory"><svg viewBox="0 0 {W} {H}" role="img" aria-label="رسم المصنع">'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto"><path d="M0,0 L10,5 L0,10 z" class="head"/></marker></defs>'
        '<text x="984" y="28" class="lane">① من البطاقة إلى الطلب</text>'
        '<text x="984" y="204" class="lane">② اعتمادك ثم الدمج والنشر</text>'
        f"{edges}{nodes}"
        f'<g transform="translate(16,352)" class="node {state}"><rect width="968" height="72" rx="14"/>'
        '<text x="952" y="28" class="title">المشغّل (MathPapers-Runner)</text>'
        f'<text x="952" y="54" class="sub">{html.escape(short(worker, 130))}</text></g>'
        f'</svg><section class="valves"><h3>الصمّامات</h3><ul>{valves}</ul></section></div>'
    )


STYLE = """
.factory { margin-block-start: 16px; }
.factory svg { inline-size: 100%; block-size: auto; display: block; direction: rtl; font-family: inherit; }
.factory text { text-anchor: start; fill: var(--color-ink); }
.factory .lane { font-size: 15px; font-weight: 700; fill: var(--color-ink-soft); }
.factory .title { font-size: 15px; font-weight: 700; }
.factory .sub { font-size: 11.5px; fill: var(--color-ink-soft); }
.factory .note { font-size: 12px; font-weight: 600; fill: var(--color-brand); }
.factory .count { font-size: 13px; font-weight: 700; text-anchor: middle; }
.factory .badge { fill: var(--color-surface-sunken); stroke: var(--color-line-strong); }
.factory .node rect { fill: var(--color-surface); stroke: var(--color-line-strong); stroke-width: 1.5; }
.factory .node.ok rect { stroke: var(--color-success); stroke-width: 2; }
.factory .node.run rect { stroke: var(--color-info); stroke-width: 3; fill: var(--color-info-soft); }
.factory .node.bad rect { stroke: var(--color-danger); fill: var(--color-danger-soft); }
.factory .node.human rect { stroke: var(--color-brand); stroke-dasharray: 5 4; }
.factory .node.human.wait rect { fill: var(--color-brand-soft); stroke-width: 3; }
.factory .node .halo { fill: none; stroke: var(--color-info); stroke-width: 6; animation: halo 1.6s ease-in-out infinite; }
.factory .flow { fill: none; stroke: var(--color-line-strong); stroke-width: 2.5; }
.factory .flow.run { stroke: var(--color-info); stroke-width: 3.5; stroke-dasharray: 8 7; animation: march .7s linear infinite; }
.factory .packet { fill: none; stroke: var(--color-info); stroke-width: 9; stroke-linecap: round;
  stroke-dasharray: .5 400; animation: travel 1.4s linear infinite; }
.factory .head { fill: var(--color-line-strong); }
.valves { border: 1px solid var(--color-line); border-radius: 12px; background: var(--color-surface); padding: 10px 14px; }
.valves h3 { margin-block-end: 6px; }
.valves ul { margin: 0; padding-inline-start: 18px; display: grid; gap: 4px 24px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); font-size: .9rem; }
@keyframes march { from { stroke-dashoffset: 15; } to { stroke-dashoffset: 0; } }
@keyframes halo { 0%, 100% { opacity: .12; } 50% { opacity: .5; } }
@keyframes travel { from { stroke-dashoffset: 60; } to { stroke-dashoffset: 0; } }
@media (max-width: 760px) { .factory { overflow-x: auto; } .factory svg { min-inline-size: 760px; } }
@media (prefers-reduced-motion: reduce) {
  .factory .flow.run, .factory .node .halo { animation: none; }
  .factory .packet { display: none; }
}
"""
