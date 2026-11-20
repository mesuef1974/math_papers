"""ربط تدريبات صفحات التمارين بأمثلتها من الشارات الملونة («انظر المثال n») في صورة الصفحة، لا من تجاور الأرقام.

نص OCR لا يحمل الإحالة: رقم الشارة الملونة لا يُقرأ مع الصفحة كلها، فالإشارة في الصورة. الشارة مكوّن متصل من بكسلات مشبعة
اللون (أو لون `exercise_badges.color` بتفاوت `tolerance`) بحجم بين `min_size` و`max_size` من عرض الصفحة وفي داخله مكوّن فاتح
محاط به (الرقم). تُقصّ وتُعكس إلى رقم داكن على فاتح وتُكبَّر ثم تُقرأ بدالة OCR محقونة. ترتيب القراءة من اليمين: أعمدة أرقام
التدريبات (العمود الأيمن أولًا) ثم من الأعلى إلى الأسفل، وكل تدريب يأخذ أمثلة آخر شارة قبله، والشارة تمتد إلى العمود والصفحة
التاليين حتى شارة جديدة. ما قبل أول شارة وما بعد شارة غير مقروءة `unlinked`. المخرج بمخطط `exercise_links.json` (أرقام وحدها)
وحالته `review` دائمًا: الربط مقروء من صورة لا من جدول، ولا يصير `ok` إلا بتصحيح المالك في مرحلة `exercise_links`.
معالجة الصورة بـ Pillow وحدها.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .config import Book
from .examples import exercises_start
from .examples import settings as example_settings
from .fields import field
from .fusion import settings as fusion_settings
from .layout import load_pages
from .printed_pages import Boxes
from .text import chain_max, norm

DEFAULTS: dict[str, Any] = {
    "color": None,  # [r, g, b] لون الشارة؛ بلا لون تكفي عتبتا التشبع والقيمة
    "tolerance": 40,
    "saturation": 0.45,
    "value": 0.35,
    "min_size": 0.012,  # كسور من عرض الصفحة، لعرض الشارة وارتفاعها معًا
    "max_size": 0.06,
}
FILL = 0.35  # أقل نصيب للبكسلات الملونة من صندوق الشارة: يُسقط الإطارات والخطوط
INNER = 0.01  # أقل نصيب للرقم الفاتح من صندوق الشارة
LIGHT = (0.25, 0.7)  # الفاتح: تشبع لا يتجاوز الأول وقيمة لا تقل عن الثاني
SCALE = 4
COLUMN_GAP = 0.15  # فجوة بين حواف أرقام التدريبات (كسر من عرض الصفحة) تبدأ عمودًا جديدًا
ANCHOR = re.compile(r"^(\d{1,2})[.)]?$")
Ocr = Callable[[Any], str]


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **(book.get("exercise_badges") or {})}


def _threshold(band: Any, keep: Callable[[int], bool]) -> Any:
    return band.point(lambda x: 255 if keep(x) else 0)


def _masks(image: Any, cfg: dict[str, Any]) -> tuple[Any, Any]:
    """(قناع البكسلات الملونة، قناع الفاتحة) صورتين 0/255 بمقاس الصورة."""
    from PIL import ImageChops

    rgb = image.convert("RGB")
    _, s, v = rgb.convert("HSV").split()
    if cfg["color"]:
        hits = [
            _threshold(band, lambda x, want=want: abs(x - want) <= cfg["tolerance"])
            for band, want in zip(rgb.split(), cfg["color"], strict=True)
        ]
        colored = ImageChops.darker(ImageChops.darker(hits[0], hits[1]), hits[2])
    else:
        colored = ImageChops.darker(
            _threshold(s, lambda x: x >= cfg["saturation"] * 255),
            _threshold(v, lambda x: x >= cfg["value"] * 255),
        )
    light = ImageChops.darker(
        _threshold(s, lambda x: x <= LIGHT[0] * 255), _threshold(v, lambda x: x >= LIGHT[1] * 255)
    )
    return colored, light


def _components(mask: Any) -> list[tuple[int, int, int, int, int]]:
    """المكوّنات المتصلة (8 جيران) في قناع 0/255: (x0, y0, x1, y1, مساحة)، بمقاطع الصفوف واتحادها."""
    width, height = mask.size
    data = mask.tobytes()
    runs: list[tuple[int, int, int]] = []
    for y in range(height):
        row = data[y * width : (y + 1) * width]
        x = row.find(b"\xff")
        while x != -1:
            end = row.find(b"\x00", x)
            end = width if end == -1 else end
            runs.append((y, x, end))
            x = row.find(b"\xff", end)
    parent = list(range(len(runs)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    above, i = (0, 0, -2), 0
    while i < len(runs):
        y, j = runs[i][0], i
        while j < len(runs) and runs[j][0] == y:
            j += 1
        if above[2] == y - 1:
            p = above[0]
            for k in range(i, j):
                while p < above[1] and runs[p][2] < runs[k][1]:
                    p += 1
                q = p
                while q < above[1] and runs[q][1] <= runs[k][2]:
                    parent[root(q)] = root(k)
                    q += 1
        above, i = (i, j, y), j
    found: dict[int, list[int]] = {}
    for i, (y, x, end) in enumerate(runs):
        box = found.setdefault(root(i), [x, y, end, y + 1, 0])
        box[0], box[2], box[3] = min(box[0], x), max(box[2], end), y + 1
        box[4] += end - x
    return [(b[0], b[1], b[2], b[3], b[4]) for b in found.values()]


def _digit(colored: Any, light: Any) -> bytes:
    """قناع الرقم في مقطع شارة: الفاتح الذي لا يصل إلى حافة المقطع إلا عبر لون الشارة (فزوايا الصفحة البيضاء خارجه)."""
    width, height = colored.size
    col, lit = colored.tobytes(), light.tobytes()
    size = width * height
    edge = {*range(width), *range(size - width, size), *range(0, size, width), *range(width - 1, size, width)}
    stack = [i for i in edge if not col[i]]
    outside = bytearray(size)
    for i in stack:
        outside[i] = 1
    while stack:
        i = stack.pop()
        x = i % width
        for j in (i - width, i + width, i - 1 if x else -1, i + 1 if x < width - 1 else -1):
            if 0 <= j < size and not col[j] and not outside[j]:
                outside[j] = 1
                stack.append(j)
    return bytes(255 if lit[i] and not col[i] and not outside[i] else 0 for i in range(size))


def find_badges(image: Any, cfg: dict[str, Any] | None = None) -> list[list[int]]:
    """صناديق الشارات [x0, y0, x1, y1] في صورة الصفحة (Pillow)، من الأعلى إلى الأسفل."""
    cfg = {**DEFAULTS, **(cfg or {})}
    colored, light = _masks(image, cfg)
    low, high = cfg["min_size"] * image.width, cfg["max_size"] * image.width
    out = []
    for x0, y0, x1, y1, area in _components(colored):
        w, h = x1 - x0, y1 - y0
        if not (low <= w <= high and low <= h <= high) or area < FILL * w * h:
            continue
        box = (x0, y0, x1, y1)
        inner = _digit(colored.crop(box), light.crop(box)).count(b"\xff")
        if inner >= max(4, INNER * w * h):
            out.append(list(box))
    return sorted(out, key=lambda b: (b[1], b[0]))


def example_numbers(text: str, ceiling: int) -> list[int]:
    """أرقام الأمثلة 1..ceiling في نص شارة؛ العدد فوق السقف خاناته أمثلة متجاورة («12» بسقف 9 هو 1 و2)."""
    out: set[int] = set()
    for token in re.findall(r"\d+", norm(text)):
        parts = [token] if 1 <= int(token) <= ceiling else list(token)
        out |= {int(p) for p in parts if 1 <= int(p) <= ceiling}
    return sorted(out)


def read_badge(
    image: Any, box: list[int], ocr: Ocr, ceiling: int = 9, cfg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """يقصّ الشارة ويعكسها إلى رقم داكن على فاتح مكبَّرًا ×4 ثم يقرؤها بـ `ocr(صورة) -> نص`. بلا رقم: `unreadable`."""
    from PIL import Image

    cfg = {**DEFAULTS, **(cfg or {})}
    colored, light = _masks(image.crop(tuple(box)), cfg)
    w, h = colored.size
    digit = Image.frombytes("L", (w, h), _digit(colored, light)).point(lambda x: 255 - x)
    pad = max(2, h // 4)
    canvas = Image.new("L", (w + 2 * pad, h + 2 * pad), 255)
    canvas.paste(digit, (pad, pad))
    crop = canvas.resize((canvas.width * SCALE, canvas.height * SCALE), Image.BICUBIC).convert("RGB")
    numbers = example_numbers(ocr(crop) or "", ceiling)
    return {"box": [int(v) for v in box], "examples": numbers, "unreadable": not numbers}


def exercise_anchors(boxes: Boxes, cap: int) -> list[dict[str, Any]]:
    """صناديق الكلمات التي نصها رقم تدريب وحده (1..cap، مع نقطة أو قوس اختياري)."""
    out = []
    for text, box in boxes:
        m = ANCHOR.match(norm(text).strip())
        if m and 1 <= int(m.group(1)) <= cap:
            out.append({"n": int(m.group(1)), "box": [int(v) for v in box]})
    return out


def _columns(anchors: list[dict[str, Any]], width: float, gap: float) -> list[int]:
    """الحد الأيمن لكل عمود تدريبات في صفحة، من اليمين إلى اليسار: تجميع الحواف اليمنى لأرقامها. العمود رقمان فأكثر؛
    الرقم المنفرد بعيدًا عن الأعمدة (رقم في نص تدريب، أو على حافة عمود) لا يصنع عمودًا ويلحق بأقرب عمود، إلا في صفحة
    لا عمود فيها برقمين فتبقى المجموعات المنفردة أعمدتها."""
    groups: list[list[int]] = []
    for x in sorted((a["box"][2] for a in anchors), reverse=True):
        if not groups or groups[-1][-1] - x > gap * width:
            groups.append([x])
        else:
            groups[-1].append(x)
    full = [g[0] for g in groups if len(g) >= 2]
    return full or [g[0] for g in groups]


def _column(x: float, bounds: list[int], slack: float) -> int:
    """العمود الذي يقع فيه x: أقصى عمود يسارًا حدّه الأيمن عند x أو يمينه."""
    return max((i for i, bound in enumerate(bounds) if x <= bound + slack), default=0)


def _inside(
    box: list[int], anchors: list[dict[str, Any]], bounds: list[int], reach: float, slack: float
) -> bool:
    """هل الشارة في منطقة التدريبات: لا يمين الحد الأيمن لأول عمود (الهامش)، ورأسيًا بين أعلى رقم تدريب بمسافة
    `reach` فوقه (عنوان المجموعة) وأسفل رقم؛ فدوائر أرقام الصفحات وزخارف الترويسة والتذييل لا تُعدّ إحالات. صفحة بلا
    أرقام تدريبات لا شارة لها."""
    if not anchors:
        return False
    x0, y0, x1, y1 = box
    top = min(a["box"][1] for a in anchors) - reach
    bottom = max(a["box"][3] for a in anchors)
    return (x0 + x1) / 2 <= bounds[0] + slack and top <= (y0 + y1) / 2 <= bottom


def assign(
    badges: list[dict[str, Any]], anchors: list[dict[str, Any]], width: float, gap: float = COLUMN_GAP
) -> dict[str, Any]:
    """يوزّع التدريبات على أمثلة الشارات بترتيب القراءة. العنصر `box` ومعه `page` اختياريًا (الصفحات بترتيبها)،
    والشارة `examples` والتدريب `n`. الناتج `links` (مثال → `exercises` و`pages`) و`unlinked`."""
    order = []
    for page in sorted({item.get("page", 0) for item in (*badges, *anchors)}):
        here = [a for a in anchors if a.get("page", 0) == page]
        bounds = _columns(here, width, gap)
        slack = gap * width / 3
        for badge in (b for b in badges if b.get("page", 0) == page):
            if not _inside(badge["box"], here, bounds, gap * width, slack):
                continue
            x0, y0, x1, y1 = badge["box"]
            # الشارة في سطر تدريبها الأول تسبقه: موضعها أعلى حافتها لا مركزها
            order.append((page, _column((x0 + x1) / 2, bounds, slack), y0 - (y1 - y0) / 2, 0, badge))
        for anchor in here:
            _, y0, x1, y1 = anchor["box"]
            order.append((page, _column(x1, bounds, 0), (y0 + y1) / 2, 1, anchor))
    links: dict[int, dict[str, set[int]]] = {}
    unlinked: set[int] = set()
    current: list[int] = []
    for page, _, _, kind, item in sorted(order, key=lambda entry: entry[:4]):
        if kind == 0:
            current = item["examples"]
        elif not current:
            unlinked.add(item["n"])
        else:
            for example in current:
                row = links.setdefault(example, {"exercises": set(), "pages": set()})
                row["exercises"].add(item["n"])
                row["pages"].add(page)
    return {
        "links": {x: {k: sorted(v) for k, v in row.items()} for x, row in sorted(links.items())},
        "unlinked": sorted(unlinked),
    }


def scan(
    image: Any, boxes: Boxes, ocr: Ocr, cfg: dict[str, Any], max_example: int, max_exercise: int
) -> dict[str, Any]:
    """شارات صفحة مقروءةً وأرقام تدريباتها وعرضها."""
    return {
        "width": image.width,
        "badges": [read_badge(image, box, ocr, max_example, cfg) for box in find_badges(image, cfg)],
        "anchors": exercise_anchors(boxes, max_exercise),
    }


def link(scans: dict[int, dict[str, Any]], accepted: set[int], jump: int) -> dict[str, Any]:
    """ربط درس واحد من صفحات تمارينه الممسوحة (`scan`). أرقام التدريبات سلسلة من 1 بقفزة `jump` كالدمج، ومثال
    الشارة غير المقبول في `examples.json` يُرفض وتدريباته `unlinked`."""
    cap = chain_max((a["n"] for s in scans.values() for a in s["anchors"]), jump)
    badges = [{**b, "page": page} for page, s in scans.items() for b in s["badges"]]
    anchors = [{**a, "page": page} for page, s in scans.items() for a in s["anchors"] if a["n"] <= cap]
    got = assign(badges, anchors, max((s["width"] for s in scans.values()), default=1))
    rows = [{"example": x, **got["links"].get(x, {"exercises": [], "pages": []})} for x in sorted(accepted)]
    linked = {n for row in rows for n in row["exercises"]}
    stray = {n for x, row in got["links"].items() if x not in accepted for n in row["exercises"]}
    return {
        "links": rows,
        "unlinked": sorted((set(got["unlinked"]) | stray) - linked),
        "rejected": sorted(set(got["links"]) - accepted),
        "pages": [
            {
                "page": page,
                "badges": len(s["badges"]),
                "unreadable": sum(b["unreadable"] for b in s["badges"]),
                "exercises": sum(a["n"] <= cap for a in s["anchors"]),
            }
            for page, s in sorted(scans.items())
        ],
    }


def after_examples(known: list[dict[str, Any]], span: tuple[int, int]) -> int | None:
    """بداية التمارين بلا علامة `markers.exercises`: الصفحة التي بعد بداية آخر مثال، ما دامت في الدرس."""
    page = max((e["start"] for e in known), default=span[0] - 1) + 1
    return page if span[0] <= page <= span[1] else None


def build(
    book: Book,
    layout: dict[str, Any],
    examples: dict[str, Any],
    image_of: Callable[[int], Any],
    boxes_of: Callable[[int], Boxes | None],
    ocr: Ocr,
) -> dict[str, Any]:
    """`image_of(صفحة)` صورتها (Pillow) أو None، و`boxes_of(صفحة)` صناديق كلماتها أو None، و`ocr(صورة) -> نص`."""
    cfg, fusion = settings(book), fusion_settings(book)
    ceiling = example_settings(book)["max"]
    texts = load_pages(book)
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        known = examples["lessons"].get(r["id"], {}).get("value") or []
        accepted = {e["n"] for e in known}
        span = (r["pages_pdf"][0], r["pages_pdf"][1]) if r["pages_pdf"] else None
        start = (
            (exercises_start(book, span, texts) or after_examples(known, span)) if span and accepted else None
        )
        scans = {}
        for page in range(start, span[1] + 1) if start else ():
            image = image_of(page)
            if image is not None:
                scans[page] = scan(image, boxes_of(page) or [], ocr, cfg, ceiling, fusion["max_exercise"])
        got = link(scans, accepted, fusion["jump"]["exercises"])
        result["lessons"][r["id"]] = field(
            got["links"] if scans else [],
            "derived",
            "review" if any(row["exercises"] for row in got["links"]) else "missing",
            unlinked=got["unlinked"],
            rejected=got["rejected"],
            pages=got["pages"],
            badges=sum(p["badges"] for p in got["pages"]),
            unreadable=sum(p["unreadable"] for p in got["pages"]),
        )
    return result


def readable(entry: dict[str, Any] | None) -> bool:
    """هل في الدرس شارة مقروءة واحدة فأكثر (فيُؤخذ ربطه من الشارات لا من التجاور)."""
    return bool(entry) and entry.get("badges", 0) - entry.get("unreadable", 0) >= 1


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    return {
        "lessons": len(ls),
        "linked_examples": sum(bool(row["exercises"]) for v in ls.values() for row in v["value"]),
        "badges": sum(v["badges"] for v in ls.values()),
        "unreadable": sum(v["unreadable"] for v in ls.values()),
        "review": [k for k, v in ls.items() if v["status"] == "review"],
        "missing": [k for k, v in ls.items() if v["status"] == "missing"],
    }
