"""جدول الصفحات المطبوعة: صفحة ملف الدليل → رقم صفحة الطالب المضمَّنة فيها، من صناديق OCR وحدها (أرقام فقط).

الرقم المطبوع صندوق كله أرقام (خانة إلى ثلاث) في شريط التذييل `printed_pages.band` (كسور من مقاس الصفحة [x0, y0, x1, y1]؛
الافتراضي أسفل 12% من الصفحة). مقاس الصفحة `printed_pages.size` ([عرض، ارتفاع] بالبكسل) وإلا أقصى امتداد للصناديق في الكتاب كله.
الصفحة التي في تذييلها أكثر من رقم يُؤخذ منها ما يوافق الإزاحة الأشيع (صفحة الملف ناقص المطبوعة) بين الصفحات ذات الرقم الواحد،
وإلا تُترك. الصفحة بلا رقم بين جارتين بإزاحة واحدة تُسدّ بها (`printed_pages.fill`، الافتراضي true)، و`printed_pages.skip` صفحات
يُهمل ما قُرئ فيها (قراءة خاطئة عرفها المالك)، و`printed_pages.set` (صفحة ملف → رقم) يثبّت ما قرأه المالك بنفسه. الجدول المقبول متزايد تمامًا مع صفحات الملف وأرقامه في 1-999، وغيره يُرفض كله
ولا يُكتب: رقم واحد خاطئ يزيح صفحات أمثلة درس كامل.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from .config import Book
from .text import norm

DEFAULTS: dict[str, Any] = {"band": [0.0, 0.88, 1.0, 1.0], "fill": True, "skip": [], "set": {}, "size": None}
LOWEST, HIGHEST = 1, 999
NUMBER = re.compile(r"^\d{1,3}$")
Boxes = list[tuple[str, list[int]]]


class PrintedPagesError(ValueError):
    pass


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("printed_pages", {})}


def pairs(raw: Any) -> Boxes:
    """صناديق ملف واحد: قائمة أزواج [نص، صندوق] (صيغة `ocr.boxes`) أو مخرج PaddleOCR الخام (`rec_texts` و`rec_boxes`)."""
    if isinstance(raw, dict):
        raw = raw.get("res", raw)
        return [
            (str(t).strip(), [int(v) for v in b])
            for t, b in zip(raw.get("rec_texts", []), raw.get("rec_boxes", []), strict=False)
        ]
    return [(str(t).strip(), [int(v) for v in b]) for t, b in raw]


def stored_boxes(book: Book, page: int) -> Boxes | None:
    """صناديق الصفحة المحفوظة: `dirs.ocr/NNNN.json` ثم `dirs.boxes/NNNN.json`؛ None إن لم تُحفظ."""
    folders = [book.dir("ocr"), book.out / book["dirs"].get("boxes", "opener_boxes")]
    for folder in folders:
        path = folder / f"{page:04d}.json"
        if path.exists():
            return pairs(json.loads(path.read_text(encoding="utf-8")))
    return None


def extent(pages: Iterable[Boxes]) -> tuple[int, int]:
    """أقصى امتداد للصناديق (عرض، ارتفاع): تقدير مقاس الصفحة حين لا يُعطى."""
    width = height = 0
    for boxes in pages:
        for _, b in boxes:
            width, height = max(width, b[2]), max(height, b[3])
    return width, height


def candidates(boxes: Boxes, size: tuple[int, int], band: list[float]) -> set[int]:
    """الأرقام المطبوعة في شريط التذييل: صندوق كله أرقام ومركزه داخل الشريط."""
    width, height = size
    out: set[int] = set()
    for text, b in boxes:
        t = norm(text).strip()
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        inside = band[0] * width <= cx <= band[2] * width and band[1] * height <= cy <= band[3] * height
        if inside and NUMBER.match(t) and LOWEST <= int(t) <= HIGHEST:
            out.add(int(t))
    return out


def choose(found: dict[int, set[int]]) -> tuple[dict[int, int], list[int]]:
    """رقم واحد لكل صفحة؛ المتعدد يُحسم بالإزاحة الأشيع بين الصفحات ذات الرقم الواحد، وما لا يُحسم يُعاد في القائمة."""
    single = {page: next(iter(nums)) for page, nums in found.items() if len(nums) == 1}
    offsets = Counter(page - printed for page, printed in single.items())
    usual = offsets.most_common(1)[0][0] if offsets else None
    table, ambiguous = dict(single), []
    for page, nums in found.items():
        if len(nums) < 2:
            continue
        if usual is not None and page - usual in nums:
            table[page] = page - usual
        else:
            ambiguous.append(page)
    return table, sorted(ambiguous)


def fill(table: dict[int, int]) -> dict[int, int]:
    """يسدّ الصفحات بين جارتين بإزاحة واحدة؛ ما بين إزاحتين مختلفتين يبقى مجهولًا."""
    out = dict(table)
    pages = sorted(table)
    for a, z in zip(pages, pages[1:], strict=False):
        if a - table[a] == z - table[z]:
            for page in range(a + 1, z):
                out[page] = page - (a - table[a])
    return out


def validate(table: dict[int, int]) -> None:
    """يرفض رقمًا خارج 1-999 وجدولًا لا يتزايد تمامًا مع صفحات الملف؛ الرسالة أرقام صفحات فقط."""
    outside = sorted(page for page, printed in table.items() if not LOWEST <= printed <= HIGHEST)
    if outside:
        raise PrintedPagesError(f"رقم صفحة خارج {LOWEST}-{HIGHEST} في صفحات الملف: {outside}")
    pages = sorted(table)
    broken = [[a, z] for a, z in zip(pages, pages[1:], strict=False) if table[a] >= table[z]]
    if broken:
        raise PrintedPagesError(f"جدول غير رتيب بين صفحات الملف: {broken}")


def build(book: Book, boxes_of: Callable[[int], Boxes | None]) -> dict[str, Any]:
    """`boxes_of(صفحة)` يعيد صناديقها أو None. الناتج: `table` (غير مفحوص بعد) وأعداد ملخصه."""
    cfg = settings(book)
    skip = set(cfg["skip"])
    read: dict[int, Boxes] = {}
    for page in range(1, book["pages"] + 1):
        boxes = None if page in skip else boxes_of(page)
        if boxes:
            read[page] = boxes
    return tabulate(read, cfg)


def tabulate(read: dict[int, Boxes], cfg: dict[str, Any]) -> dict[str, Any]:
    """الجدول من صناديق الصفحات المقروءة (صفحة ملف → صناديقها) بإعداد كإعداد `settings`: منطق واحد لملف الدليل ولملف
    كتاب الطالب (`student_ocr`). الناتج: `table` (غير مفحوص بعد) وأعداد ملخصه."""
    skip = set(cfg["skip"])
    read = {page: boxes for page, boxes in read.items() if boxes and page not in skip}
    size = tuple(cfg["size"]) if cfg["size"] else extent(read.values())
    found = {page: candidates(boxes, size, cfg["band"]) for page, boxes in read.items()}
    table, ambiguous = choose({page: nums for page, nums in found.items() if nums})
    table |= {int(page): int(printed) for page, printed in cfg["set"].items()}
    filled = fill(table) if cfg["fill"] else table
    return {
        "table": {page: filled[page] for page in sorted(filled)},
        "pages_read": len(read),
        "numbered": len(table),
        "filled": len(filled) - len(table),
        "ambiguous": ambiguous,
    }


def plain(table: dict[int, int]) -> dict[str, int]:
    """صيغة الملف التي يقرؤها `build_course_index`: مفاتيح نصية مرتبة عدديًا."""
    return {str(page): table[page] for page in sorted(table)}


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    return {k: (len(v) if k == "table" else v) for k, v in result.items()}
