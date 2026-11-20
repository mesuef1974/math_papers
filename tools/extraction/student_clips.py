"""مقاطع الأمثلة من كتاب الطالب بدقته الأصلية: لكل مقطع حالي مقصوص من دليل المعلم مقطع بالاسم نفسه من كتاب الطالب.

المقاطع الحالية (`dirs.<student_clips.source>`، أسماؤها `<درس>_m<مثال>_p<صفحة الدليل>[_cont].png`) مصيَّرة من صفحة الطالب
المصغَّرة داخل الدليل، فدقتها دقة صور الدليل المضمَّنة. هنا لكل مقطع:

1. موضعه في صفحة الدليل بمطابقة قالب بمقياس واحد (المقطع مصيَّر منها بـ `clip_dpi`).
2. صفحة كتاب الطالب: `printed_pages.json` (صفحة الدليل → الرقم المطبوع؛ الغائبة تُقدَّر من جارتيها المتتابعتين `neighbor_pages`)
   ثم `page_offset` (صفحة ملف الطالب = المطبوع + الإزاحة؛ إن غابت تُقدَّر بأعلى متوسط مطابقة لعيّنة مقاطع على المدى `offsets`،
   وتثبت بقمة منفردة ولو بقيت دون العتبة).
3. نقل الصندوق من لوحة صفحة الطالب في الدليل (مستطيلات صورها المضمَّنة `get_image_rects`، `panel`) إلى صفحة الطالب (`transfer_box`).
4. تصحيح الإزاحة والمقياس بمطابقة قالب (OpenCV، `refine`): نافذة حول الموضع المنقول، ثم الصفحة كلها بمدى مقياس أوسع إن بقيت
   الدرجة دون العتبة، ثم تدقيق بدقة أعلى، ثم مقياس كل محور وحده. صفحة الجوار (`drift`) لا تُقبل إلا ببلوغ العتبة وعلوّ صفحة
   الإزاحة بهامش (`pick_shift`). تمثيل المطابقة (`modes`) يُعايَر على العيّنة
   (`pick_mode`): صورة الدليل نقطية مصغَّرة وصفحة الطالب تصيير متجهي، فالرمادي الخام قد لا يبلغ العتبة في الموضع الصحيح.
5. المقاطع التي بقيت دون العتبة تُعاد بإطار صفحة الطالب في الدليل (`FrameFit`، `refine_in_frames`): صورة اللوحة في الدليل
   ليست صفحة الطالب نفسها (تزيد عليها هامشًا عند كل حافة، وتُقصّ من أعلاها في أول صفحة من الدرس، وتُضمّ إليها صور أخرى تحتها)،
   فمقياس النقل الرأسي من ارتفاعها يخطئ، والمقطع الذي يبدأ فوق صفحة الطالب أو ينتهي تحتها فيه ما ليس فيها. المقاطع التي بلغت
   العتبة تعاير الإطار (`fit_frame`: مقياس واحد للمحورين وهامش كل حافة وانحرافها)، ثم يُقصر القالب على تقاطع صندوقه مع الإطار
   ويُنقل التقاطع وحده، بمرشّحَي التثبيت من أعلى ومن أسفل لكل صورة (`frame_candidates`). القبول ببلوغ العتبة، أو بدليل هندسي
   مستقل (`geometric`): الموضع ضمن انحراف المعايرة (عن المرشّح الذي استقر البحث قربه) والمقياس ضمن مداها ودرجة دنيا مقيسة
   (`score_floor`). وما لم يثبت وصندوقه ملاصق لحافة الصفحة يُقطع قالبه من جهتها (`trim_pinned`): هامش اللوحة في صفحته يخالف
   الوسيط المعايَر، فبقي في القالب ما هو خارج صفحة الطالب.
6. التصيير من كتاب الطالب بدقته الأصلية: صفحة ممسوحة (صورة مضمَّنة تغطي الصفحة) تُقصّ بكسلاتها نفسها بلا استيفاء، وغيرها يُصيَّر
   بـ `vector_dpi`. لا رفع دقة فوق الأصل.

المخرجات خارج المستودع: المقاطع في `dirs.<student_clips.target>` والتقرير `student_clips.json` (أرقام فقط: دقة كل مقطع ودرجة
مطابقته). المطابقة دون `threshold` لا يُكتب مقطعها ما لم يُدرج اسمها في `student_clips.approved` بعد مراجعة المالك، والمرحلة
تعيد الرمز 7 ولا تُختم ما بقي مقطع بلا مراجعة.

المنطق (النقل والبحث وتقدير الإزاحة وكشف الصفحة الممسوحة) نقي ويأخذ المطابِق مُحقَنًا؛ pymupdf وOpenCV وnumpy تُستورد كسولًا عند
التشغيل وحده (بيئة guide_extract).
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Book

NAME = re.compile(r"^(?P<lesson>\d{1,2}\.\d{1,2})_m(?P<n>\d{1,2})_p(?P<page>\d{1,4})(?P<cont>_cont)?\.png$")
DEFAULTS: dict[str, Any] = {
    "source": "examples_hires",  # مفتاح dirs للمقاطع الحالية
    "target": "examples_student",  # مفتاح dirs للمخرجات
    "clip_dpi": 400,  # دقة تصيير المقاطع الحالية من الدليل
    "vector_dpi": 600,
    "threshold": 0.8,
    "page_offset": None,
    "offsets": [-20, 60],
    "offset_margin": 0.15,  # فرق أفضل إزاحة عن تاليتها الذي يثبتها ولو بقي متوسطها دون العتبة
    "samples": 5,
    "drift": 2,  # صفحات الجوار التي تُجرَّب حين تضعف المطابقة
    "drift_margin": 0.15,  # ما تعلو به درجة صفحة جارة بلغت العتبة درجةَ صفحة الإزاحة لتُقبل
    "scan_cover": 0.85,  # حصة الصفحة التي تغطيها صورة مضمَّنة لتُعدّ ممسوحة
    "panel": {"min_width": 900, "max_x0": 100, "width": 315},
    # aspect: مدى تصحيح مقياس كل محور وحده حول المقياس الموحَّد (0 يعطّله)
    # wide_scales: مدى المقياس في بحث الصفحة كلها (لوحة أصغر من المقدَّر تُخرج المقياس الحقيقي من `scales`)
    "search": {
        "dpi": 72,
        "fine_dpi": 144,
        "margin": 0.15,
        "scales": [0.85, 1.15],
        "wide_scales": [0.6, 1.6],
        "step": 0.02,
        "pad": 6,
        "aspect": 0.06,
    },
    # إعادة المقاطع الضعيفة بإطار صفحة الطالب المعايَر: min_clips أقل عدد مقاطع ناجحة للمعايرة، scale وaspect مدى المقياس
    # حول المقياس المعايَر، min_part أقل حصة من المقطع داخل الإطار ليُطابَق
    # trim: أقصى ما يُقطع من القالب (نقاط الدليل) من جهة حافة الصفحة التي لاصقها صندوق لم يثبت (0 يعطّله)، بخطوة trim_step
    "frame": {"min_clips": 8, "scale": 0.04, "aspect": 0.02, "min_part": 0.25, "trim": 8.0, "trim_step": 0.5},
    "modes": ["gray", "blur", "binary", "edges"],  # تمثيلات المطابقة بترتيب الأمانة؛ المعايرة تختار
    "mode_margin": 0.2,  # أقل فرق بين درجة الصفحة الصحيحة وأعلى جاراتها ليُعتدّ بالتمثيل
    "approved": [],
}
MODES = ("gray", "blur", "binary", "edges")
MIN_TEMPLATE = 8  # بكسل: قالب أصغر منه لا يُطابَق
MIN_TOLERANCE = 2.0  # نقاط: أدنى انحراف موضع يُقبل به الدليل الهندسي (دقة البحث نفسها)

Box = tuple[float, float, float, float]  # x0, y0, x1, y1
Size = tuple[float, float]
# (الدقة، مقاس القالب بالنقاط، نافذة البحث بالنقاط أو None للصفحة كلها) -> (الدرجة، x، y) لركن القالب الأعلى الأيسر بالنقاط
Matcher = Callable[[int, Size, Box | None], tuple[float, float, float]]


class StudentClipsError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClipName:
    file: str
    lesson: str
    n: int
    page: int
    cont: bool


def settings(book: Book) -> dict[str, Any]:
    cfg = book.get("student_clips", {}) or {}
    out = {**DEFAULTS, **cfg}
    out["panel"] = {**DEFAULTS["panel"], **cfg.get("panel", {})}
    out["search"] = {**DEFAULTS["search"], **cfg.get("search", {})}
    out["frame"] = {**DEFAULTS["frame"], **cfg.get("frame", {})}
    return out


def errors(cfg: dict[str, Any]) -> list[str]:
    """أخطاء إعداد student_pdf وstudent_clips (قائمة فارغة = سليم أو غائب). لا يلمس القرص."""
    errs: list[str] = []
    pdf = cfg.get("student_pdf")
    if pdf is not None and not (isinstance(pdf, dict) and {"dir", "pattern"} <= set(pdf)):
        errs.append("student_pdf يلزمه dir وpattern")
    node = cfg.get("student_clips")
    if node is None:
        return errs
    if not isinstance(node, dict):
        return [*errs, "student_clips يجب أن يكون خريطة"]
    threshold = node.get("threshold", DEFAULTS["threshold"])
    if not isinstance(threshold, int | float) or not 0 < threshold <= 1:
        errs.append("student_clips.threshold بين 0 و1")
    offset = node.get("page_offset")
    if offset is not None and (not isinstance(offset, int) or isinstance(offset, bool)):
        errs.append("student_clips.page_offset عدد صحيح")
    offsets = node.get("offsets", DEFAULTS["offsets"])
    if not (isinstance(offsets, list) and len(offsets) == 2 and offsets[0] <= offsets[1]):
        errs.append("student_clips.offsets [من، إلى]")
    modes = node.get("modes", DEFAULTS["modes"])
    if not (isinstance(modes, list) and modes and set(modes) <= set(MODES)):
        errs.append(f"student_clips.modes قائمة غير فارغة من {'، '.join(MODES)}")
    if not isinstance(node.get("approved", []), list):
        errs.append("student_clips.approved قائمة أسماء مقاطع")
    return errs


def student_pdf(book: Book) -> Path:
    """ملف كتاب الطالب (`student_pdf.dir` و`pattern`)؛ الأكبر إن تعدد المطابق."""
    cfg = book.get("student_pdf")
    if not cfg:
        raise StudentClipsError("لا مفتاح student_pdf في book.yaml")
    folder = Path(cfg["dir"])
    folder = folder if folder.is_absolute() else book.root / folder
    files = list(folder.glob(cfg["pattern"]))
    if not files:
        raise StudentClipsError(f"لا ملف يطابق {cfg['pattern']} في {cfg['dir']}")
    return max(files, key=lambda p: p.stat().st_size)


def parse(name: str) -> ClipName | None:
    match = NAME.match(name)
    if match is None:
        return None
    return ClipName(name, match["lesson"], int(match["n"]), int(match["page"]), bool(match["cont"]))


# ───── هندسة الصناديق (نقية) ─────
def transfer_box(box: Box, src: Box, dst: Box) -> Box:
    """ينقل صندوقًا من مستطيل المصدر إلى مستطيل الوجهة بالتحويل الخطي الذي يطابق أحدهما على الآخر (مقياس مستقل لكل محور)."""
    sw, sh = src[2] - src[0], src[3] - src[1]
    if sw <= 0 or sh <= 0:
        raise ValueError("مستطيل المصدر فارغ")
    kx, ky = (dst[2] - dst[0]) / sw, (dst[3] - dst[1]) / sh
    return (
        dst[0] + (box[0] - src[0]) * kx,
        dst[1] + (box[1] - src[1]) * ky,
        dst[0] + (box[2] - src[0]) * kx,
        dst[1] + (box[3] - src[1]) * ky,
    )


def clamp_box(box: Box, page: Size) -> Box:
    return (max(box[0], 0.0), max(box[1], 0.0), min(box[2], page[0]), min(box[3], page[1]))


def intersect(a: Box, b: Box) -> Box | None:
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[2] > box[0] and box[3] > box[1] else None


def deviation(a: Box, b: Box) -> float:
    """أبعد حافة بين صندوقين (نقاط)."""
    return max(abs(p - q) for p, q in zip(a, b, strict=True))


def panel_images(rects: Iterable[Sequence[float]], cfg: dict[str, Any]) -> list[Sequence[float]]:
    """صور لوحة صفحة الطالب: العريضة (`min_width` بكسل فأكثر) التي تبدأ يسار `max_x0` نقطة."""
    return [r for r in rects if r[4] >= cfg["min_width"] and r[0] < cfg["max_x0"]]


def panel_rect(rects: Iterable[Sequence[float]], cfg: dict[str, Any]) -> Box | None:
    """لوحة صفحة الطالب في صفحة الدليل من مستطيلات صورها المضمَّنة: (x0, y0, x1, y1, عرض الصورة بالبكسل) لكل صورة.

    تُحسب الصور العريضة (`min_width` بكسل فأكثر) التي تبدأ يسار `max_x0` نقطة وحدها، واللوحة اتحادها؛ `width` (نقاط) يثبّت
    عرضها حين لا تغطي الصور عمود الهامش. None إن لم توجد صورة كهذه.
    """
    kept = panel_images(rects, cfg)
    if not kept:
        return None
    x0 = min(r[0] for r in kept)
    x1 = x0 + cfg["width"] if cfg.get("width") else max(r[2] for r in kept)
    return (x0, min(r[1] for r in kept), x1, max(r[3] for r in kept))


def scan_image(infos: Iterable[dict[str, Any]], page: Size, cover: float) -> dict[str, Any] | None:
    """الصورة المضمَّنة التي تجعل الصفحة ممسوحة: أكبر صورة يغطي تقاطعها مع الصفحة `cover` من مساحتها فأكثر، غير مدوَّرة."""
    best, best_area = None, 0.0
    for info in infos:
        if not info.get("xref"):
            continue
        x0, y0, x1, y1 = clamp_box(tuple(info["bbox"]), page)
        area = max(x1 - x0, 0.0) * max(y1 - y0, 0.0)
        if area >= cover * page[0] * page[1] and area > best_area and upright(info.get("transform")):
            best, best_area = info, area
    return best


def upright(transform: Sequence[float] | None) -> bool:
    """مصفوفة وضع الصورة بلا دوران ولا قلب: بكسلاتها تُقصّ مباشرة."""
    if transform is None:
        return True
    a, b, c, d = transform[:4]
    return a > 0 and d > 0 and abs(b) < 1e-6 and abs(c) < 1e-6


def pixel_box(box: Box, bbox: Box, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """صندوق بالنقاط → مستطيل بكسلات في الصورة المضمَّنة ذات المقاس `size` المرسومة في `bbox`: يتسع لأقرب بكسل ويُحصر في الصورة."""
    x0, y0, x1, y1 = transfer_box(box, bbox, (0.0, 0.0, float(size[0]), float(size[1])))
    left, top = max(math.floor(x0), 0), max(math.floor(y0), 0)
    right, bottom = min(math.ceil(x1), size[0]), min(math.ceil(y1), size[1])
    if right <= left or bottom <= top:
        raise ValueError("الصندوق خارج الصورة")
    return left, top, right, bottom


def native_dpi(bbox: Box, size: tuple[int, int]) -> float:
    """دقة الصورة المضمَّنة كما رُسمت: أقل المحورين."""
    return min(size[0] / (bbox[2] - bbox[0]), size[1] / (bbox[3] - bbox[1])) * 72


# ───── البحث (نقي؛ المطابِق مُحقَن) ─────
def steps(lo: float, hi: float, step: float) -> list[float]:
    count = int(round((hi - lo) / step))
    return [round(lo + i * step, 6) for i in range(count + 1)]


def refine(
    match: Matcher,
    predicted: Box,
    page: Size,
    search: dict[str, Any],
    threshold: float,
    trace: dict[str, Any] | None = None,
    widen: bool = True,
) -> tuple[Box, float, bool]:
    """يصحّح موضع الصندوق المنقول ومقياسه: (الصندوق في صفحة الطالب، الدرجة، هل وُسِّع البحث إلى الصفحة كلها).

    مسح خشن للمقاييس في نافذة حول الموضع المنقول (`margin` من مقاس الصفحة)؛ إن بقيت أفضل درجة دون العتبة يُعاد على الصفحة كلها
    بالمدى الأوسع `wide_scales` (النقل من لوحة أصغر أو أكبر من المقدَّر يخطئ المقياس بأكثر من `scales`، والموضع عندها لا يُعتمد
    أصلًا) ويُؤخذ الأعلى. ثم تدقيق حول أفضل مقياس بربع الخطوة وبدقة `fine_dpi` في جوار `pad` نقاط، ثم مقياس كل محور وحده في
    المدى `aspect` (اللوحة المقدَّرة في الدليل قد تخالف نسبة صفحة الطالب، والمقياس الموحَّد لا يصحّح ذلك)، ودرجته هي المعتمدة.
    `trace` (اختياري) يُملأ بأرقام التشخيص: `near_score` درجة النافذة قبل التوسيع و`scale` مقياسا المحورين المعتمدان.
    `widen=False` يبقي البحث في النافذة: استقرارها على المنقول دليل مستقل (`geometric`)، وبحث الصفحة كلها ليس كذلك.
    """
    width, height = predicted[2] - predicted[0], predicted[3] - predicted[1]
    cx, cy = (predicted[0] + predicted[2]) / 2, (predicted[1] + predicted[3]) / 2
    mx, my = search["margin"] * page[0], search["margin"] * page[1]
    Found = tuple[float, Box, Size]  # الدرجة والصندوق ومقياسا المحورين

    def sweep(
        dpi: int, pairs: Iterable[Size], window: Callable[[Size], Box | None], start: Found | None = None
    ) -> Found:
        best: Found = start or (-1.0, predicted, (1.0, 1.0))
        for sx, sy in pairs:
            if sx <= 0 or sy <= 0:
                continue
            size = (width * sx, height * sy)
            score, x, y = match(dpi, size, window(size))
            if score > best[0]:
                best = (score, (x, y, x + size[0], y + size[1]), (sx, sy))
        return best

    def near(size: Size) -> Box:
        half_w, half_h = size[0] / 2 + mx, size[1] / 2 + my
        return clamp_box((cx - half_w, cy - half_h, cx + half_w, cy + half_h), page)

    scales = [(s, s) for s in steps(*search["scales"], search["step"])]
    coarse = sweep(search["dpi"], scales, near)
    near_score = coarse[0]
    widened = widen and near_score < threshold
    if widened:
        wide = search.get("wide_scales")
        full = [(s, s) for s in steps(*wide, search["step"])] if wide else scales
        coarse = max(coarse, sweep(search["dpi"], full, lambda size: None), key=lambda found: found[0])
    _, box, (scale, _) = coarse
    pad, step = search["pad"], search["step"]

    def around(size: Size) -> Box:
        return clamp_box((box[0] - pad, box[1] - pad, box[0] + size[0] + pad, box[1] + size[1] + pad), page)

    fine_dpi = search["fine_dpi"]
    fine = sweep(fine_dpi, [(s, s) for s in steps(scale - step, scale + step, step / 4)], around)
    aspect = search.get("aspect", 0)
    if aspect and fine[0] >= 0:
        span = steps(-aspect, aspect, step / 4)
        for axis in (0, 1):  # الأفقي ثم الرأسي، وكل منهما يبدأ من أفضل ما سبقه فلا يهبط
            sx, sy = fine[2]
            pairs = [(sx + d, sy) if axis == 0 else (sx, sy + d) for d in span]
            fine = sweep(fine_dpi, pairs, around, start=fine)
    score, box, used = fine if fine[0] >= 0 else coarse
    if trace is not None:
        trace.update(near_score=round(near_score, 3), scale=[round(s, 3) for s in used])
    return clamp_box(box, page), score, widened


# ───── إطار صفحة الطالب في الدليل (نقي) ─────
@dataclass(frozen=True)
class FrameFit:
    """معايرة إطار صفحة الطالب في صفحة الدليل من المقاطع التي بلغت العتبة (نقاط الدليل، عدا `scale` و`tolerance`)."""

    scale: float  # نقاط صفحة الطالب لكل نقطة في الدليل، واحد للمحورين: الصفحة مصغَّرة بنسبتها
    left: float  # ما تزيده صورة اللوحة على صفحة الطالب عند حافتها اليسرى
    top: float
    bottom: float
    tolerance: float  # انحراف صناديق المعايرة عن المتوقع من الإطار (نقاط صفحة الطالب)
    stretch: float  # انحراف مقياسها النسبي عن 1
    clips: int


def _percentile(values: Sequence[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(math.ceil(share * len(ordered)) - 1, 0))]


def frame_candidates(rects: Iterable[Sequence[float]], panel: Box, page: Size, fit: FrameFit) -> list[Box]:
    """مستطيلات صفحة الطالب المرشّحة في صفحة الدليل: مقاسها مقاس الصفحة على المقياس المعايَر، ولكل من اللوحة وصورها مرشّحان:
    مثبَّت بحافتها العليا (صور أخرى تحت صفحة الطالب تطيل اللوحة) ومثبَّت بالسفلى (صفحة مقصوصة من أعلاها تقصّرها).
    المتطابقة (ضمن نقطة) تُحسب مرة."""
    width, height = page[0] / fit.scale, page[1] / fit.scale
    out: list[Box] = []
    for rect in [panel, *rects]:
        x = rect[0] + fit.left
        for y in (rect[1] + fit.top, rect[3] - fit.bottom - height):
            frame = (x, y, x + width, y + height)
            if all(deviation(frame, other) > 1.0 for other in out):
                out.append(frame)
    return out


def frame_target(guide_box: Box, frame: Box, page: Size, min_part: float = 0.0) -> tuple[Box, Box] | None:
    """(جزء المقطع الواقع داخل الإطار، موضعه في صفحة الطالب). ما خرج عن الإطار ليس في صفحة الطالب فلا يُطابَق ولا يُنقل.
    None إن وقع من المقطع داخل الإطار أقل من `min_part` من مساحته."""
    part = intersect(guide_box, frame)
    if part is None:
        return None
    area = (guide_box[2] - guide_box[0]) * (guide_box[3] - guide_box[1])
    if (part[2] - part[0]) * (part[3] - part[1]) < min_part * area:
        return None
    return part, clamp_box(transfer_box(part, frame, (0.0, 0.0, *page)), page)


def fit_frame(samples: Sequence[tuple[Box, Box, Box, Size]], minimum: int, slack: float) -> FrameFit | None:
    """يعاير الإطار من مقاطع بلغت العتبة: (صندوق الدليل، اللوحة، الصندوق في صفحة الطالب، مقاس صفحة الطالب) لكل مقطع.

    المقياس وسيط نسب العرض والارتفاع، والهوامش وسيط ما بين حافة اللوحة وحافة صفحة الطالب المستنتَجة من كل مقطع (الوسيط
    يسقط اللوحات الشاذة). `tolerance` و`stretch` المئين 90 لانحراف صناديق المعايرة نفسها عن المتوقع من الإطار وانحراف مقياسها،
    بحدّ أدنى `MIN_TOLERANCE` و`slack` (خطوة البحث). None دون `minimum` مقطعًا.
    """
    if len(samples) < max(minimum, 1):
        return None
    ratios: list[float] = []
    for guide, _, box, _ in samples:
        ratios += [(box[2] - box[0]) / (guide[2] - guide[0]), (box[3] - box[1]) / (guide[3] - guide[1])]
    scale = statistics.median(ratios)
    draft = FrameFit(
        scale=scale,
        left=statistics.median(g[0] - b[0] / scale - p[0] for g, p, b, _ in samples),
        top=statistics.median(g[1] - b[1] / scale - p[1] for g, p, b, _ in samples),
        bottom=statistics.median(p[3] - g[3] - (page[1] - b[3]) / scale for g, p, b, page in samples),
        tolerance=0.0,
        stretch=0.0,
        clips=len(samples),
    )
    residuals = []
    for guide, panel, box, page in samples:
        targets = [frame_target(guide, frame, page) for frame in frame_candidates([], panel, page, draft)]
        residuals.append(min((deviation(box, t[1]) for t in targets if t is not None), default=math.inf))
    return FrameFit(
        scale=scale,
        left=draft.left,
        top=draft.top,
        bottom=draft.bottom,
        tolerance=max(MIN_TOLERANCE, _percentile(residuals, 0.9)),
        stretch=max(slack, _percentile([abs(r / scale - 1) for r in ratios], 0.9)),
        clips=len(samples),
    )


def score_floor(calibration: dict[str, dict[str, float]], mode: str, margin: float) -> float | None:
    """الدرجة الدنيا المقيسة للدليل الهندسي: متوسط أعلى درجة في الصفحات الخاطئة (`miss` في معايرة التمثيل) زائد هامش الفصل
    `mode_margin`. None بلا معايرة: لا قبول هندسي."""
    row = calibration.get(mode)
    return None if row is None else row["miss"] + margin


def geometric(found: dict[str, Any], fit: FrameFit, floor: float | None) -> bool:
    """دليل هندسي مستقل عن الدرجة: بحث النافذة (لا الصفحة كلها) استقر على الموضع المتوقع من الإطار ضمن انحراف المعايرة،
    ومقياسا المحورين ضمن مداها، والدرجة فوق مستوى الصفحات الخاطئة."""
    return (
        floor is not None
        and math.isfinite(fit.tolerance)
        and not found["widened"]
        and found["score"] >= floor
        and found["deviation"] <= fit.tolerance
        and all(abs(s - 1) <= fit.stretch + 1e-9 for s in found["scale"])
    )


def frame_search(search: dict[str, Any], frame: dict[str, Any]) -> dict[str, Any]:
    """إعداد البحث بالإطار: المقياس معايَر فمداه ضيق حول 1 في النافذة وفي الصفحة كلها."""
    return {
        **search,
        "scales": [1 - frame["scale"], 1 + frame["scale"]],
        "wide_scales": None,
        "aspect": frame["aspect"],
    }


def refine_in_frames(
    matcher_for: Callable[[Box], Matcher],
    guide_box: Box,
    frames: Iterable[Box],
    page: Size,
    search: dict[str, Any],
    threshold: float,
    fit: FrameFit,
    floor: float | None,
    min_part: float = 0.0,
    trim: float = 0.0,
    trim_step: float = 0.5,
) -> dict[str, Any] | None:
    """أفضل مطابقة للمقطع على الإطارات المرشّحة، أو None إن لم يقع في أيٍّ منها.

    لكل إطار: القالب جزء المقطع داخله (`matcher_for` يعيد مطابِق ذلك الجزء من صندوق الدليل)، والمنقول موضع الجزء وحده،
    والبحث في النافذة ثم (إن لم يثبت) في الصفحة كلها. الانحراف يُقاس عن المرشّح الذي استقر البحث قربه (`settled`) لا عن
    المرشّح الذي بدأ منه: بحث يبدأ من المثبَّت من أعلى ويستقر عند المثبَّت من أسفل انحرافه عن الثاني. `evidence`: `score`
    ببلوغ العتبة، `geometry` بالدليل الهندسي (`geometric`)، None لغيرهما. يُؤخذ الأقوى دليلًا ثم الأعلى درجةً (وعند تساويها
    بحث النافذة ثم الأقل انحرافًا)، ويقف عند أول إطار يبلغ العتبة. إن لم يثبت شيء والصندوق ملاصق لحافة الصفحة يُجرَّب قطع
    القالب من جهتها (`trim` نقاط دليل على الأكثر بخطوة `trim_step`؛ `trim_pinned`). `tries` أرقام كل محاولة للتشخيص.
    """
    rank = {"score": 2, "geometry": 1, None: 0}
    frames = list(frames)

    def settled(part: Box, box: Box, score: float, widened: bool, trace: dict[str, Any]) -> dict[str, Any]:
        """نتيجة بحث قالبه `part`: الإطار المرشّح الأقرب إلى ما استقر عليه (من المرشّحات التي تحوي القالب كله) وانحرافه عنه."""
        anchors = [
            (deviation(box, target[1]), i)
            for i, frame in enumerate(frames)
            if (target := frame_target(part, frame, page)) is not None and deviation(target[0], part) < 0.05
        ]
        away, index = min(anchors)
        found = {
            "frame": frames[index],
            "template": part,
            "predicted": frame_target(part, frames[index], page)[1],  # type: ignore[index]
            "box": box,
            "score": score,
            "widened": widened,
            "deviation": away,
            "trim": {},
            **trace,
        }
        found["evidence"] = (
            "score" if score >= threshold else "geometry" if geometric(found, fit, floor) else None
        )
        return found

    def key(found: dict[str, Any]) -> tuple[int, float, bool, float]:
        return (rank[found["evidence"]], round(found["score"], 3), not found["widened"], -found["deviation"])

    best: dict[str, Any] | None = None
    tries: list[dict[str, Any]] = []
    for frame in frames:
        target = frame_target(guide_box, frame, page, min_part)
        if target is None:
            continue
        part, predicted = target
        match = matcher_for(part)
        for widen in (False, True):
            trace: dict[str, Any] = {}
            box, score, widened = refine(match, predicted, page, search, threshold, trace, widen=widen)
            found = settled(part, box, score, widened, trace)
            tries.append(
                {
                    "predicted": [round(v, 1) for v in predicted],
                    "box": [round(v, 1) for v in box],
                    "score": round(score, 3),
                    "deviation": round(found["deviation"], 1),
                    "widened": widened,
                }
            )
            if best is None or key(found) > key(best):
                best = found
            if found["evidence"]:
                break
        if best is not None and best["evidence"] == "score":
            break
    if best is None:
        return None
    if best["evidence"] is None and trim > 0:
        area = (guide_box[2] - guide_box[0]) * (guide_box[3] - guide_box[1])

        def search_part(part: Box, predicted: Box, base: dict[str, Any]) -> dict[str, Any]:
            trace: dict[str, Any] = {}
            box, score, _ = refine(matcher_for(part), predicted, page, search, threshold, trace, widen=False)
            return settled(part, box, score, base["widened"], trace)

        best = trim_pinned(
            best,
            search_part,
            page,
            fit.scale,
            steps(trim_step, trim, trim_step),
            min_part * area,
            key,
        )
    best["tries"] = tries
    return best


def trim_pinned(
    found: dict[str, Any],
    search_part: Callable[[Box, Box, dict[str, Any]], dict[str, Any]],
    page: Size,
    scale: float,
    cuts: Sequence[float],
    min_area: float,
    key: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """يقطع القالب من جهة حافة الصفحة التي لاصقها الصندوق، ويعيد أفضل النتائج (أو `found` نفسها إن لم يُفد القطع).

    الإطار المعايَر وسيط الصفحات، وهامش صورة اللوحة يختلف في بعضها (أول صفحة في الدرس)، فيبقى في القالب المقصور على الإطار
    شريط خارج صفحة الطالب: القالب لا يخرج عن الصفحة، فيلاصق حافتها مضغوطًا وتهبط درجته. لكل حافة ملاصَقة يُجرَّب قطع `cuts`
    (نقاط الدليل) من جهتها، والبحث في نافذة حول ما استقر عليه البحث (الحافة المقابلة ثابتة)، ولا يُعتدّ إلا بقطع بقي صندوقه
    عند الحافة (ضمن خطوة قطع: ما زاد عنها قطعٌ من محتوى الصفحة نفسه)؛ يُؤخذ الأعلى بـ `key` والأصغر قطعًا عند التساوي.
    `search_part(القالب، المنقول، الأصل)` يعيد نتيجة البحث. الصفحة كلها ليست دليل موضع، فالنتيجة ترث `widened` من أصلها.
    """
    limit = (cuts[1] - cuts[0] if len(cuts) > 1 else cuts[0]) * scale + 1e-6 if cuts else 0.0
    best = found
    for edge in pinned_edges(found["box"], page):
        side = ("left", "top", "right", "bottom").index(edge)
        axis, base = side % 2, best
        for cut in cuts:
            part = list(base["template"])
            part[side] += cut if side < 2 else -cut
            width, height = part[2] - part[0], part[3] - part[1]
            if width <= 0 or height <= 0 or width * height < min_area:
                break
            size = (width * scale, height * scale)
            start = [base["box"][0], base["box"][1]]
            if side < 2:  # الحافة المقابلة للملاصَقة ثابتة حيث استقر البحث
                start[axis] = base["box"][axis + 2] - size[axis]
            start = [min(max(start[i], 0.0), max(page[i] - size[i], 0.0)) for i in (0, 1)]
            predicted = (start[0], start[1], start[0] + size[0], start[1] + size[1])
            tried = search_part(tuple(part), predicted, base)  # type: ignore[arg-type]
            box = tried["box"]
            gap = box[side] if side < 2 else page[axis] - box[side]
            if gap > limit:
                continue
            tried["trim"] = {**base["trim"], edge: cut}
            if key(tried) > key(best):
                best = tried
    return best


def pick_shift(
    score_at: Callable[[int], float | None], shifts: Iterable[int], threshold: float, margin: float
) -> int | None:
    """انزياح الصفحة المعتمد عن صفحة الإزاحة (0)، أو None إن خرجت كل الصفحات عن الملف.

    صفحة الإزاحة هي الأصل: تُعتمد متى بلغت العتبة، وتبقى (للمراجعة) إن لم تبلغها ولم تثبت جارة. الجارة لا تُقبل بدرجتها
    وحدها: يلزمها بلوغ العتبة وأن تعلو درجةَ صفحة الإزاحة بـ `margin` فأكثر (أعلى درجة بين درجات كلها دون العتبة ضجيج لا
    صفحة)؛ وتُجرَّب الأقرب فالأقرب. `score_at` يعيد None لصفحة خارج الملف، وحينها تُؤخذ أعلى الجارات درجةً.
    """
    base = score_at(0)
    if base is not None and base >= threshold:
        return 0
    fallback: tuple[float, int] | None = None
    for shift in sorted((s for s in shifts if s), key=abs):
        score = score_at(shift)
        if score is None:
            continue
        if score >= threshold and (base is None or score - base >= margin):
            return shift
        if fallback is None or score > fallback[0]:
            fallback = (score, shift)
    if base is not None:
        return 0
    return None if fallback is None else fallback[1]


def pinned_edges(box: Box, page: Size, tolerance: float = 0.25) -> list[str]:
    """حواف الصفحة التي يلاصقها الصندوق: قالب يتجاوز الصفحة (مقطع فيه ما فوق صفحة الطالب أو تحتها في الدليل) يُحصر عند حافتها."""
    edges = (("left", box[0]), ("top", box[1]), ("right", page[0] - box[2]), ("bottom", page[1] - box[3]))
    return [name for name, gap in edges if gap <= tolerance]


def estimate_offset(
    score_at: Callable[[ClipName, int], float | None],
    samples: Sequence[ClipName],
    candidates: Iterable[int],
    threshold: float,
    margin: float | None = None,
) -> tuple[int, float]:
    """إزاحة ملف كتاب الطالب (صفحة الملف = المطبوع + الإزاحة): المرشّح الأعلى متوسطَ مطابقة على العيّنة؛ الأصغر عند التعادل.

    `score_at` يعيد None لصفحة خارج الملف. تثبت الإزاحة بمتوسط يبلغ العتبة، أو (مع `margin`) بقمة منفردة يعلو متوسطها تاليتها
    بـ `margin` فأكثر ولو بقي دون العتبة: الصفحة الصحيحة تُعرف بتميّزها عن غيرها لا بدرجتها المطلقة. غير ذلك خطأ صريح:
    تُكتب `page_offset` يدويًا.
    """
    means: list[tuple[float, int]] = []
    for offset in candidates:
        scores = [score_at(clip, offset) for clip in samples]
        if not scores or any(s is None for s in scores):
            continue
        means.append((sum(scores) / len(scores), offset))  # type: ignore[arg-type]
    if not means:
        raise StudentClipsError(
            "تعذّر تقدير إزاحة صفحات كتاب الطالب (لا مرشّح): اكتب student_clips.page_offset"
        )
    best = max(means, key=lambda found: (found[0], -found[1]))
    rest = [mean for mean, offset in means if offset != best[1]]
    distinct = margin is not None and bool(rest) and best[0] - max(rest) >= margin
    if best[0] < threshold and not distinct:
        raise StudentClipsError(
            f"تعذّر تقدير إزاحة صفحات كتاب الطالب (أفضل متوسط {best[0]:.2f} عند {best[1]}): "
            "اكتب student_clips.page_offset"
        )
    return best[1], best[0]


def pick_mode(
    score_at: Callable[[str, ClipName, int], float | None],
    modes: Sequence[str],
    samples: Sequence[ClipName],
    shifts: Iterable[int],
    threshold: float,
    margin: float,
) -> tuple[str, dict[str, dict[str, float]]]:
    """تمثيل المطابقة بالقياس على العيّنة: (التمثيل، جدول `hit` و`miss` لكل تمثيل).

    `hit` متوسط درجة الصفحة الصحيحة (الإزاحة 0) و`miss` متوسط أعلى درجة في جاراتها `shifts`. التمثيل السليم يفصل بينهما بـ
    `margin` فأكثر؛ يُؤخذ أول سليم (بترتيب `modes`: الأقرب إلى الأصل أولًا) يبلغ `hit` فيه العتبة، وإلا أعلى السليمة `hit`،
    وإلا (لا تمثيل سليم) أعلاها فرقًا. `score_at` يعيد None لصفحة خارج الملف.
    """
    shifts = [s for s in shifts if s]
    table: dict[str, dict[str, float]] = {}
    for mode in modes:
        hits, misses = [], []
        for clip in samples:
            hit = score_at(mode, clip, 0)
            if hit is None:
                continue
            others = [score_at(mode, clip, shift) for shift in shifts]
            hits.append(hit)
            misses.append(max((s for s in others if s is not None), default=0.0))
        if hits:
            table[mode] = {
                "hit": round(sum(hits) / len(hits), 3),
                "miss": round(sum(misses) / len(misses), 3),
            }
    if not table:
        raise StudentClipsError("تعذّرت معايرة تمثيل المطابقة: لا عيّنة في ملف كتاب الطالب")

    def gap(mode: str) -> float:
        return table[mode]["hit"] - table[mode]["miss"]

    sound = [m for m in table if gap(m) >= margin]
    if not sound:
        return max(table, key=gap), table
    for mode in sound:
        if table[mode]["hit"] >= threshold:
            return mode, table
    return max(sound, key=lambda m: table[m]["hit"]), table


def neighbor_pages(table: dict[int, int], pages: Iterable[int]) -> dict[int, int]:
    """الرقم المطبوع لصفحات دليل غابت عن الجدول، من جارتيها: أقرب صفحة معروفة قبلها وأقرب صفحة بعدها.

    لا تُقدَّر إلا حين يتتابع ما بين الجارتين صفحةً بصفحة (فرق المطبوع = فرق صفحات الدليل)؛ غير ذلك تبقى غائبة.
    """
    known = sorted(table)
    out: dict[int, int] = {}
    for page in sorted(set(pages) - set(table)):
        below = max((k for k in known if k < page), default=None)
        above = min((k for k in known if k > page), default=None)
        if below is not None and above is not None and table[above] - table[below] == above - below:
            out[page] = table[below] + page - below
    return out


def pick_samples(clips: Sequence[ClipName], count: int) -> list[ClipName]:
    """عيّنة موزعة على الكتاب من المقاطع الأصلية (أول ووسط وآخر)."""
    mains = [c for c in clips if not c.cont] or list(clips)
    if len(mains) <= count:
        return mains
    return (
        [mains[round(i * (len(mains) - 1) / (count - 1))] for i in range(count)] if count > 1 else mains[:1]
    )


def status_of(
    score: float, name: str, threshold: float, approved: Iterable[str], evidence: str | None = None
) -> str:
    """ok بدرجة العتبة فأكثر أو بدليل هندسي (`geometric`)؛ approved لمطابقة ضعيفة راجعها المالك؛ review لغيرها (لا يُكتب
    مقطعها)."""
    if score >= threshold or evidence == "geometry":
        return "ok"
    return "approved" if name in set(approved) else "review"


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    clips = result["clips"]
    scores = [c["score"] for c in clips if c.get("score") is not None]
    kinds: dict[str, int] = {}
    # لكل وحدة: كم مقطعًا مكتوبًا عند كل انزياح صفحة (ثبات الإزاحة على الكتاب)
    shifts: dict[str, dict[str, int]] = {}
    for c in clips:
        if c.get("kind"):
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        if c["status"] in ("ok", "approved") and c.get("page_shift") is not None and c.get("lesson"):
            unit = shifts.setdefault(c["lesson"].split(".")[0], {})
            unit[str(c["page_shift"])] = unit.get(str(c["page_shift"]), 0) + 1
    return {
        "clips": len(clips),
        "written": sum(1 for c in clips if c["status"] in ("ok", "approved")),
        "review": [c["file"] for c in clips if c["status"] in ("review", "missing")],
        "min_score": round(min(scores), 3) if scores else None,
        "min_dpi": min((c["dpi"] for c in clips if c.get("dpi")), default=None),
        "geometry": sum(
            1 for c in clips if c.get("evidence") == "geometry"
        ),  # المقبولة بالدليل الهندسي دون العتبة
        "kinds": kinds,
        "page_offset": result["page_offset"],
        "mode": result.get("mode"),
        "shifts": shifts,
        "unmatched_names": len(result["unmatched"]),
    }


def unreviewed(result: dict[str, Any]) -> list[str]:
    return [c["file"] for c in result["clips"] if c["status"] in ("review", "missing")]


# ───── التشغيل على الملفين (pymupdf وOpenCV؛ بيئة guide_extract) ─────
def represent(image: Any, mode: str, dpi: int) -> Any:
    """تمثيل الصورة الرمادية للمطابقة. صورة الدليل المضمَّنة نقطية مصغَّرة وصفحة الطالب تصيير متجهي، فتختلفان في التنعيم
    والتدرّج واللون لا في المحتوى: `blur` يطمس فرق التنعيم، و`binary` (عتبة Otsu) يسقط فرق التدرّج، و`edges` (مقدار التدرّج)
    يسقط فرق اللون والقطبية. الطمس بنسبة الدقة ليبقى أثره ثابتًا بالنقاط."""
    import cv2

    k = dpi / 72
    if mode == "gray":
        return image
    if mode == "blur":
        return cv2.GaussianBlur(image, (0, 0), 0.6 * k)
    if mode == "binary":
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.GaussianBlur(binary, (0, 0), 0.5 * k)
    if mode == "edges":
        smooth = cv2.GaussianBlur(image, (0, 0), 0.5 * k)
        return cv2.magnitude(cv2.Sobel(smooth, cv2.CV_32F, 1, 0), cv2.Sobel(smooth, cv2.CV_32F, 0, 1))
    raise StudentClipsError(f"تمثيل مطابقة غير معروف: {mode}")


def cv_matcher(page_image: Callable[[int], Any], clip: Any, mode: str = "gray") -> Matcher:
    """مطابِق OpenCV: معامل الارتباط المطبَّع (TM_CCOEFF_NORMED) لقالب المقطع الرمادي مصغَّرًا إلى مقاسه في صورة الصفحة،
    وكلاهما بالتمثيل `mode` (`represent`)."""
    import cv2
    import numpy as np

    def match(dpi: int, size: Size, window: Box | None) -> tuple[float, float, float]:
        image = page_image(dpi)
        k = dpi / 72
        x0 = y0 = 0
        if window is not None:
            x0, y0 = max(int(window[0] * k), 0), max(int(window[1] * k), 0)
            image = image[y0 : math.ceil(window[3] * k), x0 : math.ceil(window[2] * k)]
        w, h = round(size[0] * k), round(size[1] * k)
        if min(w, h) < MIN_TEMPLATE or image.shape[0] < h or image.shape[1] < w:
            return (-1.0, 0.0, 0.0)
        template = represent(cv2.resize(clip, (w, h), interpolation=cv2.INTER_AREA), mode, dpi)
        scores = np.nan_to_num(
            cv2.matchTemplate(represent(image, mode, dpi), template, cv2.TM_CCOEFF_NORMED),
            nan=-1.0,
            posinf=-1.0,
            neginf=-1.0,
        )
        _, score, _, where = cv2.minMaxLoc(scores)
        return (float(score), (where[0] + x0) / k, (where[1] + y0) / k)

    return match


def part_matcher(
    page_image: Callable[[int], Any], clip: Any, guide_box: Box, mode: str = "gray"
) -> Callable[[Box], Matcher]:
    """مطابِق لجزء من المقطع: `part` مستطيل داخل صندوق المقطع في صفحة الدليل، وقالبه بكسلات المقطع المقابلة له وحدها."""
    import numpy as np

    def matcher_for(part: Box) -> Matcher:
        left, top, right, bottom = pixel_box(part, guide_box, (clip.shape[1], clip.shape[0]))
        return cv_matcher(page_image, np.ascontiguousarray(clip[top:bottom, left:right]), mode)

    return matcher_for


class _Pages:
    """صفحات ملف مصيَّرة رماديةً بحسب الطلب، بمخزن صغير."""

    def __init__(self, doc: Any, keep: int = 12):
        self.doc, self.keep = doc, keep
        self.cache: dict[tuple[int, int], Any] = {}

    def gray(self, number: int, dpi: int) -> Any:
        import numpy as np
        import pymupdf

        key = (number, dpi)
        if key not in self.cache:
            if len(self.cache) >= self.keep:
                self.cache.pop(next(iter(self.cache)))
            pix = self.doc[number - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
            rows = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
            self.cache[key] = np.ascontiguousarray(rows[:, : pix.width])
        return self.cache[key]

    def size(self, number: int) -> Size:
        rect = self.doc[number - 1].rect
        return (rect.width, rect.height)


def _png(array: Any) -> bytes:
    import cv2

    done, data = cv2.imencode(".png", array)
    if not done:
        raise StudentClipsError("تعذّر ترميز PNG")
    return data.tobytes()


def _crop_scan(doc: Any, info: dict[str, Any], box: Box) -> tuple[bytes, int, int]:
    """بكسلات الصورة المضمَّنة نفسها داخل الصندوق: بلا إعادة تصيير ولا استيفاء."""
    import numpy as np
    import pymupdf

    pix = pymupdf.Pixmap(doc, info["xref"])
    if pix.colorspace is None or pix.colorspace.n not in (1, 3):
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    left, top, right, bottom = pixel_box(box, tuple(info["bbox"]), (pix.width, pix.height))
    rows = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
    pixels = rows[:, : pix.width * pix.n].reshape(pix.height, pix.width, pix.n)[top:bottom, left:right]
    pixels = pixels[:, :, 0] if pix.n == 1 else pixels[:, :, ::-1]  # OpenCV يرمّز BGR
    return _png(np.ascontiguousarray(pixels)), right - left, bottom - top


def _render(doc: Any, number: int, box: Box, cfg: dict[str, Any]) -> dict[str, Any]:
    """المقطع من صفحة كتاب الطالب بدقته الأصلية: بايتات PNG ونوع المصدر ودقته ومقاسه."""
    import pymupdf

    page = doc[number - 1]
    size = (page.rect.width, page.rect.height)
    info = scan_image(page.get_image_info(xrefs=True), size, cfg["scan_cover"])
    if info is not None:
        png, width, height = _crop_scan(doc, info, box)
        dpi = native_dpi(tuple(info["bbox"]), (info["width"], info["height"]))
        return {"png": png, "kind": "scan", "dpi": round(dpi), "width": width, "height": height}
    pix = page.get_pixmap(dpi=cfg["vector_dpi"], clip=pymupdf.Rect(*box), alpha=False)
    return {
        "png": pix.tobytes("png"),
        "kind": "vector",
        "dpi": cfg["vector_dpi"],
        "width": pix.width,
        "height": pix.height,
    }


def run(book: Book, table: dict[int, int]) -> dict[str, Any]:
    """يبني مقاطع كتاب الطالب ويكتبها، ويعيد التقرير. `table` جدول الصفحات المطبوعة (صفحة الدليل → الرقم المطبوع)."""
    import cv2
    import numpy as np
    import pymupdf

    cfg = settings(book)
    source, target = book.dir(cfg["source"]), book.dir(cfg["target"])
    if not source.is_dir():
        raise StudentClipsError(f"مجلد المقاطع الحالية غير موجود: dirs.{cfg['source']}")
    names = sorted(p.name for p in source.glob("*.png"))
    clips = [c for c in map(parse, names) if c is not None]
    unmatched = [n for n in names if parse(n) is None]
    target.mkdir(parents=True, exist_ok=True)
    search, threshold, modes = cfg["search"], cfg["threshold"], cfg["modes"]
    coarse_dpi = max(cfg["clip_dpi"] // 4, 50)
    guessed = neighbor_pages(table, [c.page for c in clips])
    table = {**table, **guessed}

    with pymupdf.open(book.pdf()) as guide_doc, pymupdf.open(student_pdf(book)) as student_doc:
        guide, student = _Pages(guide_doc), _Pages(student_doc)
        located: dict[str, tuple[Any, Box, Box | None, list[Sequence[float]]]] = {}
        guide_scores: dict[str, float] = {}  # تبقى بعد إفراغ صور المقاطع من الذاكرة
        matched: dict[tuple[str, str, int], tuple[Box, float, bool]] = {}
        traces: dict[tuple[str, str, int], dict[str, Any]] = {}  # أرقام تشخيص كل مطابقة (تُكتب في التقرير)

        def locate(clip: ClipName) -> tuple[Any, Box, Box | None, list[Sequence[float]]]:
            """صورة المقطع الرمادية وصندوقه في صفحة الدليل ولوحة صفحة الطالب فيها وصورها؛ ودرجته في `guide_scores`."""
            if clip.file not in located:
                data = np.frombuffer((source / clip.file).read_bytes(), dtype=np.uint8)
                gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
                if gray is None:
                    raise StudentClipsError(f"مقطع لا يُقرأ: {clip.file}")
                size = (gray.shape[1] * 72 / cfg["clip_dpi"], gray.shape[0] * 72 / cfg["clip_dpi"])
                match = cv_matcher(lambda dpi: guide.gray(clip.page, dpi), gray)
                score, x, y = match(coarse_dpi, size, None)
                page = guide_doc[clip.page - 1]
                rects = [
                    (r.x0, r.y0, r.x1, r.y1, image[2])
                    for image in page.get_images(full=True)
                    for r in page.get_image_rects(image[0])
                ]
                box = (x, y, x + size[0], y + size[1])
                guide_scores[clip.file] = score
                images = panel_images(rects, cfg["panel"])
                located[clip.file] = (gray, box, panel_rect(rects, cfg["panel"]), images)
            return located[clip.file]

        def on_page(clip: ClipName, number: int, mode: str) -> tuple[Box, float, bool] | None:
            """مطابقة المقطع بالتمثيل `mode` في صفحة من ملف كتاب الطالب (None خارج الملف)."""
            if not 1 <= number <= student_doc.page_count:
                return None
            if (mode, clip.file, number) not in matched:
                gray, box, panel, _ = locate(clip)
                page = student.size(number)
                whole = (0.0, 0.0, *page)
                source_rect = panel or (0.0, 0.0, *guide.size(clip.page))
                predicted = transfer_box(box, source_rect, whole)
                match = cv_matcher(lambda dpi: student.gray(number, dpi), gray, mode)
                trace: dict[str, Any] = {
                    "guide_box": [round(v, 1) for v in box],
                    "panel": None if panel is None else [round(v, 1) for v in panel],
                    "predicted": [round(v, 1) for v in predicted],
                }
                found = refine(match, predicted, page, search, threshold, trace)
                trace["pinned"] = pinned_edges(found[0], page)
                matched[mode, clip.file, number], traces[mode, clip.file, number] = found, trace
            return matched[mode, clip.file, number]

        def score_on(mode: str, clip: ClipName, number: int) -> float | None:
            found = on_page(clip, number, mode)
            return None if found is None else found[1]

        samples = pick_samples([c for c in clips if c.page in table], cfg["samples"])
        offset, offset_score = cfg["page_offset"], None
        if offset is None:
            failure: StudentClipsError | None = None
            for candidate_mode in modes:  # الإزاحة بأول تمثيل تتميّز فيه قمتها
                try:
                    offset, offset_score = estimate_offset(
                        lambda clip, candidate, m=candidate_mode: score_on(
                            m, clip, table[clip.page] + candidate
                        ),
                        samples,
                        range(cfg["offsets"][0], cfg["offsets"][1] + 1),
                        threshold,
                        cfg["offset_margin"],
                    )
                    break
                except StudentClipsError as e:
                    failure = failure or e
            if offset is None:
                raise failure or StudentClipsError("لا تمثيل مطابقة في student_clips.modes")
        drift = range(-cfg["drift"], cfg["drift"] + 1)
        mode, calibration = modes[0], {}
        if samples:
            mode, calibration = pick_mode(
                lambda m, clip, shift: score_on(m, clip, table[clip.page] + offset + shift),
                modes,
                samples,
                drift,
                threshold,
                cfg["mode_margin"],
            )
        located.clear()

        def write(entry: dict[str, Any], clip: ClipName, box: Box, score: float) -> None:
            """يحسم حالة المقطع ويكتبه من صفحة الطالب (المطابقة دون دليل بلا مراجعة لا تُكتب)."""
            entry["status"] = status_of(score, clip.file, threshold, cfg["approved"], entry.get("evidence"))
            if entry["status"] == "review":
                return
            rendered = _render(student_doc, entry["student_page"], box, cfg)
            (target / clip.file).write_bytes(rendered.pop("png"))
            entry.update(rendered)

        def in_frames(
            clip: ClipName, number: int, fit: FrameFit, floor: float | None
        ) -> dict[str, Any] | None:
            """إعادة مطابقة مقطع ضعيف بإطار صفحة الطالب المعايَر: القالب جزء المقطع داخل الإطار وحده."""
            gray, box, panel, images = locate(clip)
            if panel is None:
                return None
            page = student.size(number)
            frames = frame_candidates(images, panel, page, fit)
            found = refine_in_frames(
                part_matcher(lambda dpi: student.gray(number, dpi), gray, box, mode),
                box,
                frames,
                page,
                frame_search(search, cfg["frame"]),
                threshold,
                fit,
                floor,
                cfg["frame"]["min_part"],
                cfg["frame"]["trim"],
                cfg["frame"]["trim_step"],
            )
            if found is not None:
                found["candidates"] = len(frames)
                found["pinned"] = pinned_edges(found["box"], page)
            return found

        entries = []
        weak: list[
            tuple[ClipName, dict[str, Any], Box, float]
        ] = []  # دون العتبة: تُعاد بالإطار بعد معايرته من الناجحة
        samples_fit: list[tuple[Box, Box, Box, Size]] = []
        for clip in clips:
            entry: dict[str, Any] = {
                "file": clip.file,
                "lesson": clip.lesson,
                "example": clip.n,
                "cont": clip.cont,
                "guide_page": clip.page,
                "printed_page": table.get(clip.page),
            }
            entries.append(entry)
            if clip.page not in table:
                # لا رقم مطبوع لصفحة الدليل ولا جارتان متتابعتان تقدّرانه: تُكمَل في printed_pages
                entry["status"] = "missing"
                continue
            if clip.page in guessed:
                entry["page_source"] = "neighbors"
            base = table[clip.page] + offset
            tried: dict[int, float] = {}  # درجة كل صفحة جُرِّبت، بانزياحها

            def score_at(shift: int, clip: ClipName = clip, base: int = base) -> float | None:
                score = score_on(mode, clip, base + shift)
                if score is not None:
                    tried[shift] = score
                return score

            shift = pick_shift(score_at, drift, threshold, cfg["drift_margin"])
            located.pop(clip.file, None)  # صورة المقطع لا تبقى في الذاكرة بعد مطابقته
            guide_score = guide_scores.get(clip.file, 0.0)
            if shift is None:
                entry["status"] = "missing"
                continue
            box, score, widened = matched[mode, clip.file, base + shift]
            entry.update(
                student_page=base + shift,
                page_shift=shift,
                guide_score=round(guide_score, 3),
                score=round(score, 3),
                widened=widened,
                box=[round(v, 1) for v in box],
                pages={str(s): round(v, 3) for s, v in sorted(tried.items())},
                **traces[mode, clip.file, base + shift],
            )
            if score < threshold:
                weak.append((clip, entry, box, score))
                continue
            write(entry, clip, box, score)
            if entry["panel"] is not None and not entry["pinned"]:
                samples_fit.append(
                    (tuple(entry["guide_box"]), tuple(entry["panel"]), box, student.size(base + shift))
                )

        fit = fit_frame(samples_fit, cfg["frame"]["min_clips"], search["step"])
        floor = score_floor(calibration, mode, cfg["mode_margin"])
        for clip, entry, box, score in weak:
            found = None if fit is None else in_frames(clip, entry["student_page"], fit, floor)
            located.pop(clip.file, None)
            if found is not None:
                # أرقام تشخيص الإطار تبقى في التقرير ولو لم تُعتمد مطابقته
                entry["frame"] = {
                    "rect": [round(v, 1) for v in found["frame"]],
                    "template": [round(v, 1) for v in found["template"]],
                    "predicted": [round(v, 1) for v in found["predicted"]],
                    "box": [round(v, 1) for v in found["box"]],
                    "score": round(found["score"], 3),
                    "near_score": found["near_score"],
                    "scale": found["scale"],
                    "deviation": round(found["deviation"], 1),
                    "widened": found["widened"],
                    "candidates": found["candidates"],
                    "trim": found["trim"],
                    "tries": found["tries"],
                }
                if found["evidence"]:
                    box, score = found["box"], found["score"]
                    entry.update(
                        score=round(found["score"], 3),
                        widened=found["widened"],
                        box=[round(v, 1) for v in found["box"]],
                        predicted=entry["frame"]["predicted"],
                        near_score=found["near_score"],
                        scale=found["scale"],
                        pinned=found["pinned"],
                        evidence=found["evidence"],
                        source="frame",
                    )
            write(entry, clip, box, score)

    return {
        "page_offset": offset,
        "offset_score": None if offset_score is None else round(offset_score, 3),
        "threshold": threshold,
        "mode": mode,
        "calibration": calibration,
        # معايرة إطار صفحة الطالب في الدليل والدرجة الدنيا للدليل الهندسي (None: لم تكفِ المقاطع الناجحة أو لا معايرة تمثيل)
        "frame": None
        if fit is None
        else {k: v if k == "clips" else round(v, 3) for k, v in fit.__dict__.items()},
        "floor": None if floor is None else round(floor, 3),
        "clips": entries,
        "unmatched": unmatched,
    }


def load_table(book: Book) -> dict[int, int]:
    path = book.output("printed_pages")
    if not path.exists():
        raise StudentClipsError("لا printed_pages.json: شغّل مرحلة printed_pages أولًا")
    return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
