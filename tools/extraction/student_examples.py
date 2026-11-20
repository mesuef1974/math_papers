"""مقاطع الأمثلة من كتاب الطالب مباشرة، وروابط «حاول أن تحل» منه: للكتاب الذي لا مقاطع دليل له تنقلها `student_clips`.

المدخل صناديق OCR لصفحات كتاب الطالب (`student_ocr`: `dirs.student_ocr` و`student_pages.json`) لا نصه. لكل درس في `layout.json`:

1. صفحاته في كتاب الطالب: صفحات الدليل → المطبوع (`printed_pages.json`) → صفحة ملف الطالب (`student_pages.json`)، والغائبة
   بين جارتين متتابعتين تُقدَّر (`student_clips.neighbor_pages`).
2. ترتيب القراءة: أعمدة الصفحة من اليمين (`page_columns`) ثم الأسطر من الأعلى. العمودان لا يُعتمدان إلا بفاصل رأسي في وسط
   الصفحة لا يعبره أكثر من `gutter.max_cross` صندوقًا، وأسطر تغطي `gutter.min_fill` من ارتفاع الصفحة في كل جهة، وسطر «مثال»
   أو «حاول أن تحل» في كل جهة؛ `columns` (auto أو 1 أو 2) و`column_pages` (صفحة ملف → 1 أو 2) يثبّتانه.
3. الأمثلة بقاعدة `exercise_try.assign` نفسها: سطر «مثال» وحده يفتح مثالًا، وينتهي عند أعلى السطر التالي له في ترتيب
   القراءة: سطر «حاول أن تحل» المنسوب إليه (`try`) أو غير المقروء رقمه (`try_unread`) أو سطر «مثال» التالي (`label`)، وإلا
   عند علامة التمارين (`stop`: `end_patterns`، الافتراضي `markers.exercises` سطرًا وحده) أو نهاية الدرس (`lesson`). عناوين
   «مثال» الزائدة عن العدد المتوقع في آخر الدرس بلا سطر «حاول أن تحل» تُسقط (عناوين في صفحات التمارين).
   سطر «مثال» نوعان يُصحَّحان قبل العدّ، بقياس أسطر «مثال» المقروءة في الكتاب كله: كلمة «مثال N» داخل سطر من المتن صندوقها
   بارتفاع خط المتن لا الشارة، فما قصر عن `label_height` من وسيط ارتفاع أسطر «مثال» ليس عنوانًا (`inline`). والشارة التي
   لم يكشفها OCR الصفحة (لا صندوق لها) تُستردّ حيث يدل الترتيب على فواتها وحده: سطر «حاول أن تحل» لم يسبقه سطر «مثال» منذ
   سطر «حاول أن تحل» الذي قبله أو منذ أول الدرس؛ فيُبحث بينهما، في مواضع الشارة الأفقية (`label_bands`)، عن كتلة حبر
   بارتفاع الشارة (`recover.height`) لا يغطيها صندوق، وتُقرأ بالتعرّف وحده، ولا تُعتمد إلا إن قُرئت «مثال» (`recovered`).
4. العدد المتوقع لكل درس من `lessons/lesson_*.json` للمقرر `course`؛ الدرس الذي يخالفه `review` ولا تُكتب مقاطعه.
5. القصّ بعرض العمود من سطر «مثال» حتى ما قبل نهايته، وما في عمود أو صفحة تالية تتمة (`_cont`). الحواف تُضبط على الحبر من
   تصيير رمادي للصفحة (`probe_dpi`): أعلى المقطع أول صف حبر في كتلة سطر «مثال» (شارته)، وأسفله ما قبل كتلة سطر النهاية، ثم
   يُقصّ البياض حوله. المقطع يُصيَّر من PDF نفسه بـ `clip_dpi` (`student_clips.render_box`) لا من صورة التصيير.
6. تحقق الرؤية (`vision: true`): لكل مقطع سؤال واحد بمخطط JSON (`CHECK`) عن رقم المثال في أعلاه، وهل يبدأ بعنوانه، وهل
   يُقطع نص أو رسم عند حافته السفلى أو الجانبية (`verdict`). المثال الذي خالف مقطع منه `review` ولا يُكتب ما لم يُدرج اسم
   المقطع في `approved` بعد مراجعة المالك. حكم «بلا عنوان» على صورة المقطع كلها لا يكفي وحده (سطر العنوان يضيع في
   صورة المقطع الطويل): يثبت العنوان أيضًا برقم المثال المقروء مطابقًا وسطر «مثال» من صناديق OCR عند أعلى المقطع
   (`label_top` ضمن `title_top`)، وإلا يُعاد السؤال (`TITLE`) على شريط أعلى المقطع وحده (`title_strip` نقطة بـ `title_dpi`).

المخرجات خارج المستودع: المقاطع في `dirs.<target>` بأسماء `publish_assets` (`NAME`)، وما لم يُعتمد يبقى في `<target>_review`
للمراجعة، و`student_examples.json` (أرقام وحدها) و`student_try.json` بمخطط `exercise_try.json` (حالته `review` دائمًا، ولا
يكتب تصحيحًا ولا يغيّر `exercise_links`) ومقارنته بـ `exercise_try.json` الدليل (`compare`).

المسح (`scan`) نقي يأخذ الصناديق والمقاسات والقارئ محقونة؛ القصّ (`cut`) يستورد pymupdf وnumpy كسولًا (بيئة guide_extract).
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import struct
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import exercise_try, student_clips
from .config import Book
from .examples import LABEL_LINE
from .fusion import settings as fusion_settings
from .printed_pages import Boxes, pairs
from .reps import schema
from .term_plan import COURSES
from .text import norm

# اسم المقطع كما يقبله `publish_assets` (`apps.assets.services.CLIP`؛ يطابقه اختبار)
NAME = re.compile(r"^(?P<lesson>\d\.\d{1,2})_m(?P<n>\d{1,2})_p(?P<page>\d{1,3})(?P<cont>_cont)?\.png$")
DEFAULTS: dict[str, Any] = {
    "course": None,  # المقرر الذي تُعدّ أمثلة دروسه
    "courses_dir": None,  # مجلد المقررات؛ الافتراضي مجلد المستودع
    "target": "examples_student",  # مفتاح dirs للمخرجات
    "ocr_dpi": 300,
    "clip_dpi": 600,
    # جدول الصفحات المطبوعة (`student_ocr`): band كسور [x0, y0, x1, y1]؛ بلا قيمة تُجرَّب الترويسة والتذييل
    "band": None,
    "skip": [],
    "set": {},
    "fill": True,
    "body": [0.04, 0.95],  # ما بين الترويسة والتذييل من ارتفاع الصفحة
    "columns": "auto",
    "column_pages": {},
    "gutter": {"band": [0.35, 0.65], "max_cross": 2, "min_fill": 0.25},
    "end_patterns": None,  # أنماط تُطابَق على سطر بعد `text.norm`
    "label_height": 0.75,  # أدنى ارتفاع لسطر «مثال» من وسيط ارتفاع أسطره في الكتاب (0 يعطّله)
    # استرداد شارة «مثال» بلا صندوق: `ink` ما دونه حبر في صورة الصفحة، و`height` مدى ارتفاع كتلتها من الوسيط نفسه
    "recover": {"ink": 200, "height": [0.8, 1.5]},
    "probe_dpi": 144,
    "white": 245,  # ما دونه حبر
    "rise": 1.5,  # أقصى صعود (أضعاف ارتفاع السطر) إلى أول صف أبيض فوق سطر «مثال» أو سطر النهاية
    "pad": 0.35,  # ما يُزاد فوق سطر «مثال» (أضعاف ارتفاعه) حين لا صف أبيض ضمن `rise`
    "margin": 2.0,  # نقاط بياض حول الحبر
    "min_height": 6.0,  # نقاط: مقطع أقصر منه لا يُكتب
    "scan_cover": 0.85,
    "vision": True,
    "model": "small",
    "vision_dpi": 200,
    "question": None,
    "title_strip": 60.0,  # نقاط: ارتفاع شريط أعلى المقطع الأول الذي يُعاد عليه سؤال العنوان
    "title_dpi": 300,
    "title_top": 12.0,  # نقاط: أقصى بعد لأعلى سطر «مثال» (صندوق OCR) تحت أعلى المقطع ليُعدّ عنوانه
    "title_question": None,
    "approved": [],
}
COLUMNS = ("auto", 1, 2)
QUESTION = (
    "هذه صورة مقصوصة من صفحة كتاب رياضيات. number: الرقم المكتوب بجوار كلمة «مثال» في أعلى الصورة (0 إن لم يوجد). "
    "title: هل تبدأ الصورة من أعلاها بعنوان «مثال»؟ cut_bottom: هل يوجد نص أو رسم مبتور عند الحافة السفلى للصورة؟ "
    "cut_side: هل يوجد نص أو رسم مبتور عند الحافة اليمنى أو اليسرى للصورة؟"
)
CHECK = schema(
    "clip",
    {
        "number": {"type": "integer"},
        "title": {"type": "boolean"},
        "cut_bottom": {"type": "boolean"},
        "cut_side": {"type": "boolean"},
    },
)
TITLE_QUESTION = (
    "هذه صورة الشريط العلوي من مقطع مقصوص من صفحة كتاب رياضيات. title: هل يظهر فيها عنوان «مثال»؟ "
    "number: الرقم المكتوب بجوار كلمة «مثال» (0 إن لم يوجد)."
)
TITLE = schema("clip_title", {"number": {"type": "integer"}, "title": {"type": "boolean"}})
TOP = "top_"  # بادئة صورة الشريط العلوي في مجلد صور الرؤية
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

Ask = Callable[[Path, str, dict[str, Any]], dict[str, Any]]
RawEvent = tuple[str, list[int], str]  # ("label"|"try"|"stop"، صندوق، نص)


class StudentExamplesError(student_clips.StudentClipsError):
    pass


class VisionError(RuntimeError):
    """تعذّر تشغيل خادم نموذج الرؤية (رمز الخروج 4)."""


@dataclass(frozen=True)
class Column:
    """عمود في صفحة من ملف كتاب الطالب، ببكسلات صناديق OCR."""

    page: int  # صفحة الملف
    printed: int
    index: int  # 0 الأيمن
    x0: float
    x1: float
    top: float
    bottom: float
    width: int  # مقاس الصفحة
    height: int


def settings(book: Book) -> dict[str, Any]:
    cfg = book.get("student_examples", {}) or {}
    out = {**DEFAULTS, **cfg}
    out["gutter"] = {**DEFAULTS["gutter"], **(cfg.get("gutter") or {})}
    out["recover"] = {**DEFAULTS["recover"], **(cfg.get("recover") or {})}
    out["column_pages"] = {int(k): int(v) for k, v in (cfg.get("column_pages") or {}).items()}
    return out


def _is_map(value: Any) -> bool:
    return value is None or isinstance(value, dict)


def errors(cfg: dict[str, Any]) -> list[str]:
    """أخطاء قسم student_examples (قائمة فارغة = سليم أو غائب). لا يلمس القرص."""
    node = cfg.get("student_examples")
    if node is None:
        return []
    if not isinstance(node, dict):
        return ["student_examples يجب أن يكون خريطة"]
    errs: list[str] = []
    for key in ("ocr_dpi", "clip_dpi", "vision_dpi", "probe_dpi", "title_dpi"):
        value = node.get(key, DEFAULTS[key])
        if not isinstance(value, int) or isinstance(value, bool) or value < 36:
            errs.append(f"student_examples.{key} عدد صحيح 36 فأكثر")
    if node.get("columns", "auto") not in COLUMNS:
        errs.append("student_examples.columns: auto أو 1 أو 2")
    pages = node.get("column_pages") or {}
    if not isinstance(pages, dict) or any(v not in (1, 2) for v in pages.values()):
        errs.append("student_examples.column_pages: صفحة ملف → 1 أو 2")
    for key in ("band", "body"):
        value = node.get(key)
        size = 4 if key == "band" else 2
        if value is not None and not (
            isinstance(value, list) and len(value) == size and all(isinstance(v, int | float) for v in value)
        ):
            errs.append(f"student_examples.{key} قائمة من {size} كسور")
    for key in ("title_strip", "title_top"):
        value = node.get(key, DEFAULTS[key])
        if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
            errs.append(f"student_examples.{key} عدد موجب من النقاط")
    floor = node.get("label_height", DEFAULTS["label_height"])
    if not isinstance(floor, int | float) or isinstance(floor, bool) or not 0 <= floor <= 1:
        errs.append("student_examples.label_height كسر بين 0 و1")
    recover = {**DEFAULTS["recover"], **(node.get("recover") or {})} if _is_map(node.get("recover")) else None
    if recover is None or not (
        isinstance(recover["ink"], int)
        and isinstance(recover["height"], list)
        and len(recover["height"]) == 2
        and all(isinstance(v, int | float) for v in recover["height"])
    ):
        errs.append("student_examples.recover: ink عدد صحيح وheight قائمة من كسرين")
    if not isinstance(node.get("approved", []), list):
        errs.append("student_examples.approved قائمة أسماء مقاطع")
    if not isinstance(node.get("vision", True), bool):
        errs.append("student_examples.vision: true أو false")
    for pattern in node.get("end_patterns") or []:
        try:
            re.compile(pattern)
        except (re.error, TypeError) as e:
            errs.append(f"student_examples.end_patterns نمط غير صالح: {e}")
    return errs


def need_dirs(book: Book, *keys: str) -> None:
    missing = [key for key in keys if not book.has_dir(key)]
    if missing:
        raise StudentExamplesError("مفاتيح dirs ناقصة في book.yaml: " + "، ".join(missing))


# ───── المدخلات (ملفات مجلد الكتاب والمقرر) ─────
def expected_counts(book: Book) -> dict[str, int]:
    """عدد أمثلة كل درس في المقرر `student_examples.course` (كل أمثلته، والإثرائية معها)."""
    cfg = settings(book)
    if not cfg["course"]:
        raise StudentExamplesError("لا student_examples.course في book.yaml")
    root = COURSES
    if cfg["courses_dir"]:
        root = Path(cfg["courses_dir"])
        root = root if root.is_absolute() else book.root / root
    files = sorted((root / cfg["course"] / "lessons").glob("lesson_*.json"))
    if not files:
        raise StudentExamplesError(f"لا دروس للمقرر {cfg['course']}")
    counts: dict[str, int] = {}
    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        counts[str(record["lesson"])] = len(record.get("examples") or [])
    return counts


def load_pages(book: Book) -> dict[int, int]:
    """`student_pages.json`: صفحة ملف كتاب الطالب → الرقم المطبوع."""
    path = book.output("student_pages")
    if not path.exists():
        raise StudentExamplesError("لا student_pages.json: شغّل مرحلة student_ocr أولًا")
    return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def boxes_of(book: Book) -> Callable[[int], Boxes | None]:
    folder = book.dir("student_ocr")

    def get(page: int) -> Boxes | None:
        path = folder / f"{page:04d}.json"
        return pairs(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    return get


def png_size(path: Path) -> tuple[int, int]:
    """(عرض، ارتفاع) صورة PNG من ترويستها، بلا مكتبة صور."""
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != PNG_MAGIC or head[12:16] != b"IHDR":
        raise StudentExamplesError(f"ليست صورة PNG: {path.name}")
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def size_of(book: Book) -> Callable[[int], tuple[int, int]]:
    """مقاس صفحة التصيير التي قُرئت صناديقها (`dirs.student_render`)."""
    folder = book.dir("student_render")
    seen: dict[int, tuple[int, int]] = {}

    def get(page: int) -> tuple[int, int]:
        if page not in seen:
            path = folder / f"{page:04d}.png"
            if not path.exists():
                raise StudentExamplesError(f"لا تصيير للصفحة {page}: شغّل مرحلة student_ocr أولًا")
            seen[page] = png_size(path)
        return seen[page]

    return get


def end_patterns(book: Book, cfg: dict[str, Any]) -> list[re.Pattern[str]]:
    raw = cfg["end_patterns"]
    if raw is None:
        marker = book["markers"].get("exercises")
        raw = [rf"^\s*{re.escape(norm(marker))}\s*\S?\s*$"] if marker else []
    return [re.compile(pattern) for pattern in raw]


# ───── ترتيب القراءة (نقي) ─────
def page_events(boxes: Boxes, marker: str, stops: Sequence[re.Pattern[str]]) -> list[RawEvent]:
    """أسطر الصفحة المعنية من الأعلى: أسطر `exercise_try.events` ومعها علامة التمارين ("stop")."""
    found: list[RawEvent] = list(exercise_try.events(boxes, marker))
    taken = {id(box) for _, box, _ in found}
    for text, box in boxes:
        if id(box) not in taken and any(pattern.search(norm(text)) for pattern in stops):
            found.append(("stop", box, text))
    return sorted(found, key=lambda e: (e[1][1], -e[1][2]))


def coverage(boxes: Boxes) -> float:
    """مجموع ما تغطيه الصناديق من المحور الرأسي (اتحاد امتداداتها)."""
    total, reach = 0.0, -math.inf
    for top, bottom in sorted((b[1], b[3]) for _, b in boxes):
        if bottom > reach:
            total += bottom - max(top, reach)
            reach = bottom
    return total


def gutter(boxes: Boxes, size: tuple[int, int], cfg: dict[str, Any]) -> tuple[float, int]:
    """(موضع الفاصل الرأسي الأقل عبورًا في وسط الصفحة `band`، عدد الصناديق التي تعبره): منتصف أطول مدى بأقل عبور."""
    width = size[0]
    lo, hi = cfg["band"][0] * width, cfg["band"][1] * width
    step = max(width / 400, 1.0)
    xs = [lo + i * step for i in range(int((hi - lo) / step) + 1)]
    cross = [sum(1 for _, b in boxes if b[0] < x < b[2]) for x in xs]
    least = min(cross)
    best, start = (0, 0), None
    for i, count in enumerate([*cross, least + 1]):
        if count == least and start is None:
            start = i
        elif count != least and start is not None:
            best = max(best, (i - start, start))
            start = None
    return xs[best[1] + (best[0] - 1) // 2], least


def page_columns(
    boxes: Boxes, found: Sequence[RawEvent], size: tuple[int, int], cfg: dict[str, Any], forced: Any = "auto"
) -> list[tuple[float, float]]:
    """أعمدة الصفحة من اليمين: [(x0, x1)]. `forced` 1 أو 2 يثبّت العدد؛ auto لا يعتمد عمودين إلا بفاصل لا يعبره إلا
    `max_cross` صندوقًا، وأسطر تغطي `min_fill` من ارتفاع الصفحة في كل جهة، وسطر معنيّ (`found`) في كل جهة ولا سطر
    يعبر الفاصل: عمودا الخطوات وشرحها داخل مثال واحد ليسا عمودَي صفحة."""
    width, height = size
    whole = [(0.0, float(width))]
    if forced == 1 or not boxes:
        return whole
    x, cross = gutter(boxes, size, cfg["gutter"])
    two = [(x, float(width)), (0.0, x)]
    if forced == 2:
        return two
    if cross > cfg["gutter"]["max_cross"]:
        return whole
    sides = ([(t, b) for t, b in boxes if b[2] <= x], [(t, b) for t, b in boxes if b[0] >= x])
    if any(coverage(side) < cfg["gutter"]["min_fill"] * height for side in sides):
        return whole
    left = any(box[2] <= x for _, box, _ in found)
    right = any(box[0] >= x for _, box, _ in found)
    crossing = any(box[0] < x < box[2] for _, box, _ in found)
    return two if left and right and not crossing else whole


def lesson_pages(
    span: Sequence[int] | None, guide_table: dict[int, int], inverse: dict[int, int]
) -> tuple[list[tuple[int, int]] | None, list[int] | None, list[int]]:
    """صفحات الدرس في كتاب الطالب: ([(صفحة الملف، المطبوع)] أو None، [أول مطبوع، آخره] أو None، مطبوعات بلا صفحة ملف).
    `inverse`: المطبوع → صفحة ملف الطالب. الغائبة بين جارتين متتابعتين تُقدَّر في الجدولين."""
    if not span:
        return None, None, []
    guide = range(span[0], span[1] + 1)
    known = {**guide_table, **student_clips.neighbor_pages(guide_table, guide)}
    printed = sorted({known[page] for page in guide if page in known})
    if not printed:
        return None, None, []
    wanted = range(printed[0], printed[-1] + 1)
    files = {**inverse, **student_clips.neighbor_pages(inverse, wanted)}
    missing = [p for p in wanted if p not in files]
    if missing:
        return None, [printed[0], printed[-1]], missing
    return [(files[p], p) for p in wanted], [printed[0], printed[-1]], []


def lesson_columns(
    pages: Sequence[tuple[int, int]],
    boxes_of: Callable[[int], Boxes | None],
    size_of: Callable[[int], tuple[int, int]],
    cfg: dict[str, Any],
    marker: str,
    stops: Sequence[re.Pattern[str]],
) -> tuple[list[Column], list[tuple[int, int, list[RawEvent]]], tuple[int, float, str, list[int] | None]]:
    """أعمدة الدرس بترتيب القراءة، وأحداث كل عمود (مفتاحه ترتيبه)، ونهاية الدرس: (العمود، y، "stop"|"lesson"، صندوق
    علامة التمارين أو None). ما بعد علامة التمارين لا يُقرأ."""
    columns: list[Column] = []
    raw: list[tuple[int, int, list[RawEvent]]] = []
    end: tuple[int, float, str, list[int] | None] | None = None
    for page, printed in pages:
        boxes = boxes_of(page) or []
        width, height = size_of(page)
        found = page_events(boxes, marker, stops)
        forced = cfg["column_pages"].get(page, cfg["columns"])
        spans = page_columns(boxes, found, (width, height), cfg, forced)
        for index, (x0, x1) in enumerate(spans):
            mine = [e for e in found if x0 <= (e[1][0] + e[1][2]) / 2 < x1 or len(spans) == 1]
            key = len(columns)
            columns.append(
                Column(
                    page,
                    printed,
                    index,
                    x0,
                    x1,
                    cfg["body"][0] * height,
                    cfg["body"][1] * height,
                    width,
                    height,
                )
            )
            stop = next((i for i, e in enumerate(mine) if e[0] == "stop"), None)
            if stop is not None:
                end = (key, float(mine[stop][1][1]), "stop", list(mine[stop][1]))
                mine = mine[:stop]
            raw.append((key, page, mine))
            if end:
                break
        if end:
            break
    if end is None:
        end = (len(columns) - 1, columns[-1].bottom, "lesson", None)
    return columns, raw, end


RawSlot = tuple[int, int, list[RawEvent]]  # (العمود بترتيب القراءة، صفحة الملف، أحداثه من الأعلى)


def label_boxes(raw: Sequence[RawSlot]) -> list[list[int]]:
    return [box for _, _, found in raw for kind, box, _ in found if kind == "label"]


def drop_inline(raw: Sequence[RawSlot], floor: float) -> tuple[list[RawSlot], int]:
    """(الأحداث بلا أسطر «مثال» الأقصر من `floor`، عددها): كلمة «مثال N» داخل سطر من المتن لا عنوان مثال."""
    kept = [
        (key, page, [e for e in found if e[0] != "label" or e[1][3] - e[1][1] >= floor])
        for key, page, found in raw
    ]
    return kept, len(label_boxes(raw)) - len(label_boxes(kept))


def label_bands(boxes: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """مواضع شارة «مثال» الأفقية في الكتاب [(x0, x1)]: صناديق أسطر «مثال» مجموعةً بحافتها اليمنى (فرق دون ربع عرضها
    الوسيط)، فلكل جهة صفحة ولكل عمود موضعه."""
    if not boxes:
        return []
    slack = statistics.median(box[2] - box[0] for box in boxes) / 4
    bands: list[tuple[int, int]] = []
    for box in sorted(boxes, key=lambda b: b[2]):
        if bands and box[2] - bands[-1][1] <= slack:
            bands[-1] = (min(bands[-1][0], box[0]), box[2])
        else:
            bands.append((box[0], box[2]))
    return bands


def label_gaps(columns: Sequence[Column], raw: Sequence[RawSlot]) -> list[list[dict[str, Any]]]:
    """حيث فات سطر «مثال»: أجزاء (`segments`) ما بين كل سطر «حاول أن تحل» لم يسبقه سطر «مثال» وبين الحدث الذي قبله
    (سطر «حاول أن تحل» آخر، أو أول الدرس)."""
    out = []
    last: tuple[int, str, list[int]] | None = None
    for key, _, found in raw:
        for kind, box, _ in found:
            if kind == "try" and (last is None or last[1] == "try"):
                start = (0, columns[0].top) if last is None else (last[0], float(last[2][3]))
                out.append(segments(columns, start, (key, float(box[1]))))
            last = (key, kind, box)
    return out


def unboxed_labels(
    image: Any,
    boxes: Boxes,
    band: tuple[int, int],
    span: tuple[float, float],
    height: float,
    read: exercise_try.Ocr,
    cfg: dict[str, Any],
) -> list[list[int]]:
    """صناديق شارات «مثال» التي لم يكشفها OCR الصفحة، في النطاق الأفقي `band` بين الصفين `span` من صورتها (Pillow):
    كتلة حبر متصلة الصفوف بارتفاع الشارة (`cfg.height` من `height`) لا يقاطعها صندوق مقروء، وقراءتها بالتعرّف «مثال»."""
    x0, x1 = band
    top, bottom = max(int(span[0]), 0), math.ceil(span[1])
    if bottom <= top:
        return []
    ink = cfg["ink"]
    strip = image.crop((x0, top, x1, bottom)).convert("L").point(lambda v: 255 * (v < ink))
    low, high = (k * height for k in cfg["height"])
    label = re.compile(LABEL_LINE)
    out: list[list[int]] = []
    start = None
    for row, inked in enumerate([*strip.getprojection()[1], 0]):
        if inked and start is None:
            start = row
        elif not inked and start is not None:
            y0, y1, start = top + start, top + row, None
            if not low <= y1 - y0 <= high:
                continue
            if any(b[1] < y1 and b[3] > y0 and b[0] < x1 and b[2] > x0 for _, b in boxes):
                continue
            left, _, right, _ = strip.crop((0, y0 - top, x1 - x0, y1 - top)).getbbox()
            pad = max(2, (y1 - y0) // 12)
            text, _ = read(image.crop((x0 + left - pad, y0 - pad, x0 + right + pad, y1 + pad)))
            if label.match(norm(text or "")):
                out.append([x0 + left, y0, x0 + right, y1])
    return out


def recover_labels(
    columns: Sequence[Column],
    raw: Sequence[RawSlot],
    bands: Sequence[tuple[int, int]],
    height: float,
    boxes_of: Callable[[int], Boxes | None],
    image_of: Callable[[int], Any],
    read: exercise_try.Ocr,
    cfg: dict[str, Any],
) -> tuple[list[RawSlot], int]:
    """(الأحداث ومعها أسطر «مثال» المستردّة في مواضعها، عددها): لكل موضع فات فيه سطر «مثال» (`label_gaps`) شاراته التي
    لا صندوق لها (`unboxed_labels`) في كل موضع أفقي للشارة داخل العمود. بلا صورة للصفحة لا استرداد."""
    extra: dict[int, list[list[int]]] = {}
    for gap in label_gaps(columns, raw) if bands and height else []:
        for part in gap:
            column = columns[part["column"]]
            image = image_of(column.page)
            if image is None:
                continue
            boxes = boxes_of(column.page) or []
            mine = extra.setdefault(part["column"], [])
            for band in bands:
                if not (column.x0 <= band[0] and band[1] <= column.x1):
                    continue
                for box in unboxed_labels(image, boxes, band, (part["y0"], part["y1"]), height, read, cfg):
                    if not any(b[1] < box[3] and b[3] > box[1] for b in mine):  # الشارة نفسها بموضعين أفقيين
                        mine.append(box)
    out = [
        (
            key,
            page,
            sorted(
                [*found, *(("label", box, "") for box in extra.get(key, []))],
                key=lambda e: (e[1][1], -e[1][2]),
            ),
        )
        for key, page, found in raw
    ]
    return out, sum(len(found) for found in extra.values())


def segments(
    columns: Sequence[Column], start: tuple[int, float], stop: tuple[int, float]
) -> list[dict[str, Any]]:
    """أجزاء مثال من موضع بدايته إلى موضع نهايته: جزء لكل عمود يمر به (ما بعد الأول تتمة)، والفارغ يُسقط."""
    out = []
    for key in range(start[0], stop[0] + 1):
        top = start[1] if key == start[0] else columns[key].top
        bottom = stop[1] if key == stop[0] else columns[key].bottom
        if bottom > top:
            out.append({"column": key, "y0": float(top), "y1": float(bottom)})
    return out


def plan(
    columns: Sequence[Column],
    events: Sequence[exercise_try.Slot],
    end: tuple[int, float, str, list[int] | None],
) -> list[dict[str, Any]]:
    """أمثلة الدرس بترتيبها: لكل صف من `exercise_try.assign` نهايته (`end`) وأجزاؤه. المثال الذي فتحه سطر «حاول أن تحل»
    (فات سطر «مثال» قبله) بلا بداية (`label` None)."""
    flat = [(key, kind, box, reads) for key, found in events for kind, box, reads in found]
    where = {(key, tuple(box)): i for i, (key, kind, box, _) in enumerate(flat) if kind == "label"}
    out: list[dict[str, Any]] = []
    for n, row in enumerate(exercise_try.assign(events)["rows"], start=1):
        item: dict[str, Any] = {
            "example": n,
            "linked": row["line"] is not None,
            "label": None,
            "end": None,
            "stop_box": None,
            "columns": None,  # (عمود سطر «مثال»، عمود النهاية)
            "segments": [],
        }
        out.append(item)
        if row["label"] is None:
            continue
        key, box = row["label"]
        after = where[key, tuple(box)] + 1
        if after < len(flat):
            stop_key, kind, stop_box, reads = flat[after]
            stop = (stop_key, float(stop_box[1]))
            item["end"] = "label" if kind == "label" else "try" if reads else "try_unread"
            item["stop_box"] = list(stop_box)
        else:
            stop = (end[0], end[1])
            item["end"], item["stop_box"] = end[2], end[3]
        item["label"], item["columns"] = list(box), (key, stop[0])
        item["segments"] = segments(columns, (key, float(box[1])), stop)
    return out


def scan(
    book: Book,
    layout: dict[str, Any],
    guide_table: dict[int, int],
    student_table: dict[int, int],
    boxes_of: Callable[[int], Boxes | None],
    size_of: Callable[[int], tuple[int, int]],
    image_of: Callable[[int], Any],
    read: exercise_try.Ocr,
) -> dict[str, Any]:
    """يمسح دروس الكتاب: `lessons` (أعمدة كل درس وأمثلته وحالته) و`try` (مخرج `student_try.json`). `guide_table` صفحة
    الدليل → المطبوع، و`student_table` صفحة ملف الطالب → المطبوع، و`image_of` و`read` لقراءة أرقام «حاول أن تحل»
    (`exercise_try.read_try`)."""
    cfg = settings(book)
    want = expected_counts(book)
    try_cfg = exercise_try.settings(book)
    cap = fusion_settings(book)["max_exercise"]
    stops = end_patterns(book, cfg)
    inverse = {printed: page for page, printed in student_table.items()}
    lessons: dict[str, Any] = {}
    tried: dict[str, Any] = {"book": book.id, "lessons": {}}
    located = []
    for r in layout["lessons"]:
        pages, printed, missing = lesson_pages(r["pages_pdf"], guide_table, inverse)
        found = None
        if pages is not None:
            found = lesson_columns(pages, boxes_of, size_of, cfg, try_cfg["marker"], stops)
        located.append((r, pages, printed, missing, found))
    # مقياس سطر «مثال» من أسطره المقروءة في الكتاب كله: ارتفاعه الوسيط، ومواضع شارته الأفقية
    read_labels = [box for *_, found in located if found for box in label_boxes(found[1])]
    height = float(statistics.median(box[3] - box[1] for box in read_labels)) if read_labels else 0.0
    floor = cfg["label_height"] * height
    bands = label_bands([box for box in read_labels if box[3] - box[1] >= floor])
    for r, pages, printed, missing, found in located:
        lesson: dict[str, Any] = {
            "expected": want.get(r["id"]),
            "found": 0,
            "reasons": [],
            "printed": printed,
            "missing_pages": missing,
            "columns": [],
            "examples": [],
            "labels": 0,
            "opened": 0,
            "dropped": 0,
            "inline": 0,
            "recovered": 0,
        }
        lessons[r["id"]] = lesson
        events: list[exercise_try.Slot] = []
        fallback = 0
        if found is None:
            lesson["reasons"].append("pages")
        else:
            columns, raw, end = found
            raw, lesson["inline"] = drop_inline(raw, floor)
            raw, lesson["recovered"] = recover_labels(
                columns, raw, bands, height, boxes_of, image_of, read, cfg["recover"]
            )
            events, fallback = exercise_try.read_events(raw, image_of, read, cap, try_cfg)
            examples = plan(columns, events, end)
            while lesson["expected"] is not None and len(examples) > lesson["expected"]:
                if examples[-1]["linked"]:
                    break
                examples.pop()  # عنوان «مثال» بعد آخر مثال متوقع بلا سطر «حاول أن تحل»: في صفحات التمارين
                lesson["dropped"] += 1
            lesson.update(columns=columns, examples=examples, found=len(examples))
        got = exercise_try.link_slots(events)
        lesson.update(labels=got["labels"], opened=got["opened"])
        entry = exercise_try.entry(got, fallback)
        for row in entry["value"]:  # مفتاح الموضع → الصفحة المطبوعة
            row["pages"] = [lesson["columns"][key].printed for key in row["pages"]]
        tried["lessons"][r["id"]] = entry
        if lesson["expected"] is None:
            lesson["reasons"].append("expected")
        elif pages is not None and lesson["found"] != lesson["expected"]:
            lesson["reasons"].append("count")
        if any(item["label"] is None for item in lesson["examples"]):
            lesson["reasons"].append("unlabeled")
        lesson["status"] = "review" if lesson["reasons"] else "ok"
    absent = sorted(set(want) - set(lessons))
    return {"lessons": lessons, "try": tried, "absent": absent}


# ───── تحقق الرؤية والمقارنة (نقي) ─────
def top_reading(answer: dict[str, Any]) -> dict[str, Any] | None:
    """جواب سؤال الشريط العلوي (`TITLE`) رقمًا ومنطقيًا وحدهما، أو None لجواب غير صالح."""
    try:
        return {"number": int(answer["number"]), "title": bool(answer["title"])}
    except (KeyError, TypeError, ValueError):
        return None


def anchored(gap: float | None, limit: float, margin: float) -> bool:
    """هل سطر «مثال» من صناديق OCR عند أعلى المقطع؟ `gap` بُعد أعلى صندوقه تحت أعلى المقطع بالنقاط (None: المقطع لا
    يبدأ بجزء سطر «مثال»)؛ والسطر الذي فوق أعلى المقطع بأكثر من هامشه ليس فيه."""
    return gap is not None and -margin <= gap <= limit


def verdict(
    answer: dict[str, Any],
    example: int,
    first: bool,
    last: bool,
    anchored: bool = False,
    top: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """(جواب النموذج أرقامًا ومنطقيات وحدها، مخالفاته). المقطع الأول يلزمه عنوان المثال ورقمه إن قُرئ (0: لم يُقرأ)،
    والأخير ألّا يُقطع أسفله (ما قبله ينتهي بنهاية العمود قصدًا)، وكلها ألّا تُقطع جانبًا. جواب غير صالح `no_answer`.
    العنوان يثبت بجواب الصورة كلها، أو بجواب شريطها العلوي `top` (`top_reading`)، أو برقم المثال المقروء مطابقًا وسطر
    «مثال» من صناديق OCR عند أعلى المقطع (`anchored`). والرقم المقروء من الشريط، إن قُرئ، يتقدّم على رقم الصورة كلها."""
    try:
        seen = {
            "number": int(answer["number"]),
            "title": bool(answer["title"]),
            "cut_bottom": bool(answer["cut_bottom"]),
            "cut_side": bool(answer["cut_side"]),
        }
    except (KeyError, TypeError, ValueError):
        return None, ["no_answer"]
    number = top["number"] if top and top["number"] else seen["number"]
    titled = seen["title"] or bool(top and top["title"]) or (anchored and number == example)
    problems = []
    if first and not titled:
        problems.append("title")
    if first and number not in (0, example):
        problems.append("number")
    if last and seen["cut_bottom"]:
        problems.append("cut_bottom")
    if seen["cut_side"]:
        problems.append("cut_side")
    return seen, problems


def compare(student: dict[str, Any], guide: dict[str, Any] | None) -> dict[str, Any] | None:
    """مقارنة روابط «حاول أن تحل» من كتاب الطالب بروابط الدليل (`exercise_try.json`)، لكل درس: `agree` عدد الأمثلة
    المتفقة، و`differ` و`student_only` و`guide_only` بأرقامها. None بلا مخرج الدليل."""
    if guide is None:
        return None

    def linked(result: dict[str, Any], lesson: str) -> dict[int, list[int]]:
        rows = (result["lessons"].get(lesson) or {}).get("value") or []
        return {row["example"]: row["exercises"] for row in rows if row["exercises"]}

    out: dict[str, Any] = {}
    for lesson in sorted(set(student["lessons"]) | set(guide["lessons"])):
        ours, theirs = linked(student, lesson), linked(guide, lesson)
        both = sorted(set(ours) & set(theirs))
        out[lesson] = {
            "agree": sum(ours[n] == theirs[n] for n in both),
            "differ": [
                {"example": n, "student": ours[n], "guide": theirs[n]} for n in both if ours[n] != theirs[n]
            ],
            "student_only": [{"example": n, "exercises": ours[n]} for n in sorted(set(ours) - set(theirs))],
            "guide_only": [{"example": n, "exercises": theirs[n]} for n in sorted(set(theirs) - set(ours))],
        }
    return out


# ───── القصّ والتصيير (pymupdf وnumpy؛ بيئة guide_extract) ─────
def rise_above(inked: Sequence[bool], row: int, limit: int) -> int | None:
    """أول صف في كتلة الحبر التي تحوي الصف `row`: يصعد حتى أول صف أبيض ضمن `limit` صفًّا؛ None إن لم يبلغه."""
    row = min(max(row, 0), len(inked) - 1)
    for up in range(limit + 1):
        if row - up < 0:
            return 0
        if not inked[row - up]:
            return row - up + 1
    return None


class _Ink:
    """حبر صفحات كتاب الطالب من تصيير رمادي بـ `probe_dpi`، وضبط حواف الأجزاء عليه."""

    def __init__(self, doc: Any, cfg: dict[str, Any], keep: int = 4):
        self.doc, self.cfg, self.keep = doc, cfg, keep
        self.cache: dict[int, Any] = {}

    def mask(self, page: int) -> Any:
        import numpy as np
        import pymupdf

        if page not in self.cache:
            if len(self.cache) >= self.keep:
                self.cache.pop(next(iter(self.cache)))
            pix = self.doc[page - 1].get_pixmap(
                dpi=self.cfg["probe_dpi"], colorspace=pymupdf.csGRAY, alpha=False
            )
            rows = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
            self.cache[page] = rows[:, : pix.width] < self.cfg["white"]
        return self.cache[page]

    def edge(self, mask: Any, inked: Any, box: Sequence[int], k: float) -> int | None:
        """أول صف حبر في كتلة السطر ذي الصندوق `box`: بحبر العمود كله، ثم بحبر امتداد السطر وحده (خط رأسي أو تظليل
        بطول العمود يملأ صفوفه كلها)."""
        row = int(box[1] * k)
        limit = math.ceil(self.cfg["rise"] * (box[3] - box[1]) * k)
        found = rise_above(inked, row, limit)
        if found is None:
            own = mask[:, max(int(box[0] * k), 0) : math.ceil(box[2] * k)].any(axis=1)
            found = rise_above(own, row, limit)
        return found

    def refine(self, column: Column, item: dict[str, Any], part: dict[str, Any]) -> student_clips.Box | None:
        """صندوق الجزء بنقاط الصفحة مضبوطًا على الحبر، أو None لجزء بلا حبر أو أقصر من `min_height`."""
        import numpy as np

        cfg = self.cfg
        rect = self.doc[column.page - 1].rect
        dots = cfg["probe_dpi"] / 72  # بكسل التصيير الرمادي لكل نقطة
        k = rect.width / column.width * dots  # ولكل بكسل من صناديق OCR
        mask = self.mask(column.page)
        x0 = min(max(int(column.x0 * k), 0), mask.shape[1] - 1)
        x1 = min(max(math.ceil(column.x1 * k), x0 + 1), mask.shape[1])
        inked = mask[:, x0:x1].any(axis=1)
        top, bottom = int(part["y0"] * k), math.ceil(part["y1"] * k)
        first, last = item["columns"]
        if part is item["segments"][0] and part["column"] == first:
            label = item["label"]
            found = self.edge(mask, inked, label, k)
            top = found if found is not None else top - round(cfg["pad"] * (label[3] - label[1]) * k)
        if part is item["segments"][-1] and part["column"] == last and item["stop_box"] is not None:
            found = self.edge(mask, inked, item["stop_box"], k)
            bottom = found if found is not None else bottom
        top, bottom = max(top, 0), min(bottom, mask.shape[0])
        region = mask[top:bottom, x0:x1]
        rows, cols = np.flatnonzero(region.any(axis=1)), np.flatnonzero(region.any(axis=0))
        if rows.size == 0:
            return None
        pad = cfg["margin"]
        box = (
            max((x0 + cols[0]) / dots - pad, x0 / dots) + rect.x0,
            max((top + rows[0]) / dots - pad, top / dots) + rect.y0,
            min((x0 + cols[-1] + 1) / dots + pad, x1 / dots, rect.width) + rect.x0,
            min((top + rows[-1] + 1) / dots + pad, bottom / dots, rect.height) + rect.y0,
        )
        return None if box[3] - box[1] < cfg["min_height"] else tuple(float(v) for v in box)  # type: ignore[return-value]


def clip_name(lesson: str, example: int, printed: int, cont: bool) -> str:
    return f"{lesson}_m{example}_p{printed}{'_cont' if cont else ''}.png"


def _lesson_report(lesson: dict[str, Any]) -> dict[str, Any]:
    columns: list[Column] = lesson["columns"]
    return {
        "status": lesson["status"],
        "reasons": lesson["reasons"],
        "expected": lesson["expected"],
        "found": lesson["found"],
        "printed": lesson["printed"],
        "missing_pages": lesson["missing_pages"],
        "labels": lesson["labels"],
        "opened": lesson["opened"],
        "dropped": lesson["dropped"],
        "inline": lesson["inline"],
        "recovered": lesson["recovered"],
        "two_column_pages": sorted({c.page for c in columns if c.index}),
        "examples": [
            {
                "example": item["example"],
                "end": item["end"],
                "segments": [
                    {
                        "page": columns[part["column"]].page,
                        "column": columns[part["column"]].index,
                        "box": [
                            round(columns[part["column"]].x0),
                            round(part["y0"]),
                            round(columns[part["column"]].x1),
                            round(part["y1"]),
                        ],
                    }
                    for part in item["segments"]
                ],
            }
            for item in lesson["examples"]
        ],
    }


def cut(
    book: Book,
    scanned: dict[str, Any],
    asking: Callable[[], AbstractContextManager[Ask]] | None = None,
    guide_try: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """يقصّ مقاطع الدروس السليمة من ملف كتاب الطالب، ويتحقق منها بالرؤية (`asking` يفتح عميل الأسئلة؛ None يعطّله)،
    ويكتب المقبول في `dirs.<target>` ويبقي غيره في `<target>_review`، ويعيد التقرير (أرقام وحدها)."""
    import pymupdf

    cfg = settings(book)
    target = book.dir(cfg["target"])
    staging = target.with_name(f"{target.name}_review")
    probes = staging / "vision"
    for folder in (target, probes):
        folder.mkdir(parents=True, exist_ok=True)
    for old in (*staging.glob("*.png"), *probes.glob("*.png")):
        old.unlink()
    question = cfg["question"] or QUESTION
    title_question = cfg["title_question"] or TITLE_QUESTION
    render_cfg = {"scan_cover": cfg["scan_cover"], "vector_dpi": cfg["clip_dpi"]}
    clips: list[dict[str, Any]] = []
    with pymupdf.open(student_clips.student_pdf(book)) as doc:
        ink = _Ink(doc, cfg)
        for lesson_id, lesson in scanned["lessons"].items():
            if lesson["status"] != "ok":
                continue
            columns: list[Column] = lesson["columns"]
            made: list[tuple[dict[str, Any], str, Column, student_clips.Box, bool, bool]] = []
            for item in lesson["examples"]:
                kept = [
                    (part, columns[part["column"]], box)
                    for part in item["segments"]
                    if (box := ink.refine(columns[part["column"]], item, part)) is not None
                ]
                parts = [(column, box) for _, column, box in kept]
                # أول مقطع هو جزء سطر «مثال» نفسه، لا تتمة بقيت بعد سقوط جزئه بلا حبر
                labeled = (
                    bool(kept)
                    and kept[0][0] is item["segments"][0]
                    and kept[0][0]["column"] == item["columns"][0]
                )
                names = [
                    clip_name(lesson_id, item["example"], column.printed, cont=j > 0)
                    for j, (column, _) in enumerate(parts)
                ]
                if not parts:
                    lesson["reasons"].append("empty")
                if len(set(names)) != len(names):
                    lesson["reasons"].append("collision")
                if any(NAME.match(name) is None for name in names):
                    lesson["reasons"].append("name")
                made += [
                    (item, name, column, box, j == len(parts) - 1, labeled and j == 0)
                    for j, (name, (column, box)) in enumerate(zip(names, parts, strict=True))
                ]
            if lesson["reasons"]:
                lesson["reasons"] = sorted(set(lesson["reasons"]))
                lesson["status"] = "review"
                continue
            for item, name, column, box, last, labeled in made:
                rendered = student_clips.render_box(doc, column.page, box, render_cfg)
                (staging / name).write_bytes(rendered.pop("png"))
                page = doc[column.page - 1]
                label_top = None
                if labeled:  # بُعد أعلى سطر «مثال» (صندوق OCR) تحت أعلى المقطع، بالنقاط
                    scale = page.rect.width / column.width
                    label_top = round(item["label"][1] * scale + page.rect.y0 - box[1], 1)
                if asking is not None:
                    page.get_pixmap(dpi=cfg["vision_dpi"], clip=pymupdf.Rect(*box), alpha=False).save(
                        probes / name
                    )
                    if not name.endswith("_cont.png"):
                        strip = pymupdf.Rect(box[0], box[1], box[2], min(box[3], box[1] + cfg["title_strip"]))
                        page.get_pixmap(dpi=cfg["title_dpi"], clip=strip, alpha=False).save(
                            probes / f"{TOP}{name}"
                        )
                clips.append(
                    {
                        "file": name,
                        "lesson": lesson_id,
                        "example": item["example"],
                        "cont": name.endswith("_cont.png"),
                        "last": last,
                        "student_page": column.page,
                        "printed_page": column.printed,
                        "column": column.index,
                        "box": [round(v, 1) for v in box],
                        **rendered,
                        "end": item["end"],
                        "label_top": label_top,
                        "vision": None,
                        "top": None,
                        "problems": [],
                        "status": "ok",
                    }
                )
    if asking is not None and clips:
        with asking() as ask:
            for clip in clips:
                answer = ask(probes / clip["file"], question, CHECK)
                place = {
                    "first": not clip["cont"],
                    "last": clip["last"],
                    "anchored": anchored(clip["label_top"], cfg["title_top"], cfg["margin"]),
                }
                clip["vision"], clip["problems"] = verdict(answer, clip["example"], **place)
                if place["first"] and {"title", "number"} & set(clip["problems"]):
                    # حكم صورة المقطع كلها لا يكفي: يُعاد السؤال على شريطها العلوي بدقته
                    clip["top"] = top_reading(ask(probes / f"{TOP}{clip['file']}", title_question, TITLE))
                    clip["vision"], clip["problems"] = verdict(
                        answer, clip["example"], **place, top=clip["top"]
                    )
    approved = set(cfg["approved"])
    examples: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for clip in clips:
        examples.setdefault((clip["lesson"], clip["example"]), []).append(clip)
    for group in examples.values():
        accepted = all(not clip["problems"] or clip["file"] in approved for clip in group)
        for clip in group:
            if not accepted:  # مثال خالف مقطع منه لا يُكتب منه شيء
                clip["status"], clip["problems"] = "review", clip["problems"] or ["sibling"]
            elif clip["problems"]:
                clip["status"] = "approved"
    written = {clip["file"] for clip in clips if clip["status"] != "review"}
    for name in written:
        os.replace(staging / name, target / name)
    for old in probes.glob("*.png"):
        old.unlink()
    for path in target.glob(
        "*.png"
    ):  # مخرج المرحلة مقاطع هذا التشغيل وحدها: ما بقي من تشغيل سابق لدروسها يُزال
        match = NAME.match(path.name)
        if match and match["lesson"] in scanned["lessons"] and path.name not in written:
            path.unlink()
    for folder in (probes, staging):
        if not any(folder.iterdir()):
            folder.rmdir()
    return {
        "book": book.id,
        "course": cfg["course"],
        "clip_dpi": cfg["clip_dpi"],
        "vision": asking is not None,
        "absent": scanned["absent"],
        "lessons": {key: _lesson_report(lesson) for key, lesson in scanned["lessons"].items()},
        "clips": clips,
        "try": compare(scanned["try"], guide_try),
    }


def unreviewed(result: dict[str, Any]) -> list[str]:
    """ما يمنع ختم المرحلة: دروس `review` أو غائبة عن المخطط، ومقاطع `review`."""
    lessons = [key for key, lesson in result["lessons"].items() if lesson["status"] != "ok"]
    return [
        *lessons,
        *result["absent"],
        *(clip["file"] for clip in result["clips"] if clip["status"] == "review"),
    ]


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    lessons, clips, tried = result["lessons"], result["clips"], result["try"]
    out: dict[str, Any] = {
        "lessons": len(lessons),
        "expected": sum(lesson["expected"] or 0 for lesson in lessons.values()),
        "found": sum(lesson["found"] for lesson in lessons.values()),
        "clips": len(clips),
        "written": sum(clip["status"] != "review" for clip in clips),
        "approved": sum(clip["status"] == "approved" for clip in clips),
        "continuations": sum(clip["cont"] for clip in clips),
        "two_column_pages": sum(len(lesson["two_column_pages"]) for lesson in lessons.values()),
        "review": len(unreviewed(result)),
        "review_lessons": {
            key: lesson["reasons"] for key, lesson in lessons.items() if lesson["status"] != "ok"
        },
        "absent_lessons": result["absent"],
        "review_clips": {clip["file"]: clip["problems"] for clip in clips if clip["status"] == "review"},
        "try": None,
    }
    if tried is not None:
        kinds = ("differ", "student_only", "guide_only")
        out["try"] = {
            "agree": sum(row["agree"] for row in tried.values()),
            **{kind: sum(len(row[kind]) for row in tried.values()) for kind in kinds},
            # لكل درس: [متفقة، مختلفة، قرأها الطالب وحده، قرأها الدليل وحده]
            "lessons": {
                key: [row["agree"], *(len(row[kind]) for kind in kinds)] for key, row in tried.items()
            },
            "student_only_reads": {
                f"{key}/{row['example']}": row["exercises"]
                for key, rows in tried.items()
                for row in rows["student_only"]
            },
        }
    return out
