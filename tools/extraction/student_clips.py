"""مقاطع الأمثلة من كتاب الطالب بدقته الأصلية: لكل مقطع حالي مقصوص من دليل المعلم مقطع بالاسم نفسه من كتاب الطالب.

المقاطع الحالية (`dirs.<student_clips.source>`، أسماؤها `<درس>_m<مثال>_p<صفحة الدليل>[_cont].png`) مصيَّرة من صفحة الطالب
المصغَّرة داخل الدليل، فدقتها دقة صور الدليل المضمَّنة. هنا لكل مقطع:

1. موضعه في صفحة الدليل بمطابقة قالب بمقياس واحد (المقطع مصيَّر منها بـ `clip_dpi`).
2. صفحة كتاب الطالب: `printed_pages.json` (صفحة الدليل → الرقم المطبوع) ثم `page_offset` (صفحة ملف الطالب = المطبوع + الإزاحة؛
   إن غابت تُقدَّر بأعلى متوسط مطابقة لعيّنة مقاطع على المدى `offsets`).
3. نقل الصندوق من لوحة صفحة الطالب في الدليل (مستطيلات صورها المضمَّنة `get_image_rects`، `panel`) إلى صفحة الطالب (`transfer_box`).
4. تصحيح الإزاحة والمقياس بمطابقة قالب (OpenCV، `refine`): نافذة حول الموضع المنقول، ثم الصفحة كلها إن بقيت الدرجة دون العتبة،
   ثم صفحات الجوار (`drift`)، ثم تدقيق بدقة أعلى.
5. التصيير من كتاب الطالب بدقته الأصلية: صفحة ممسوحة (صورة مضمَّنة تغطي الصفحة) تُقصّ بكسلاتها نفسها بلا استيفاء، وغيرها يُصيَّر
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
    "offsets": [0, 40],
    "samples": 3,
    "drift": 2,  # صفحات الجوار التي تُجرَّب حين تضعف المطابقة
    "scan_cover": 0.85,  # حصة الصفحة التي تغطيها صورة مضمَّنة لتُعدّ ممسوحة
    "panel": {"min_width": 900, "max_x0": 100, "width": 315},
    "search": {"dpi": 72, "fine_dpi": 144, "margin": 0.15, "scales": [0.85, 1.15], "step": 0.02, "pad": 6},
    "approved": [],
}
MIN_TEMPLATE = 8  # بكسل: قالب أصغر منه لا يُطابَق

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


def panel_rect(rects: Iterable[Sequence[float]], cfg: dict[str, Any]) -> Box | None:
    """لوحة صفحة الطالب في صفحة الدليل من مستطيلات صورها المضمَّنة: (x0, y0, x1, y1, عرض الصورة بالبكسل) لكل صورة.

    تُحسب الصور العريضة (`min_width` بكسل فأكثر) التي تبدأ يسار `max_x0` نقطة وحدها، واللوحة اتحادها؛ `width` (نقاط) يثبّت
    عرضها حين لا تغطي الصور عمود الهامش. None إن لم توجد صورة كهذه.
    """
    kept = [r for r in rects if r[4] >= cfg["min_width"] and r[0] < cfg["max_x0"]]
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
    match: Matcher, predicted: Box, page: Size, search: dict[str, Any], threshold: float
) -> tuple[Box, float, bool]:
    """يصحّح موضع الصندوق المنقول ومقياسه: (الصندوق في صفحة الطالب، الدرجة، هل وُسِّع البحث إلى الصفحة كلها).

    مسح خشن للمقاييس في نافذة حول الموضع المنقول (`margin` من مقاس الصفحة)؛ إن بقيت أفضل درجة دون العتبة يُعاد على الصفحة كلها
    ويُؤخذ الأعلى. ثم تدقيق حول أفضل مقياس بربع الخطوة وبدقة `fine_dpi` في جوار `pad` نقاط، ودرجته هي المعتمدة.
    """
    width, height = predicted[2] - predicted[0], predicted[3] - predicted[1]
    cx, cy = (predicted[0] + predicted[2]) / 2, (predicted[1] + predicted[3]) / 2
    mx, my = search["margin"] * page[0], search["margin"] * page[1]

    def sweep(
        dpi: int, scales: Iterable[float], window: Callable[[Size], Box | None]
    ) -> tuple[float, Box, float]:
        best: tuple[float, Box, float] = (-1.0, predicted, 1.0)
        for s in scales:
            if s <= 0:
                continue
            size = (width * s, height * s)
            score, x, y = match(dpi, size, window(size))
            if score > best[0]:
                best = (score, (x, y, x + size[0], y + size[1]), s)
        return best

    def near(size: Size) -> Box:
        half_w, half_h = size[0] / 2 + mx, size[1] / 2 + my
        return clamp_box((cx - half_w, cy - half_h, cx + half_w, cy + half_h), page)

    scales = steps(*search["scales"], search["step"])
    coarse = sweep(search["dpi"], scales, near)
    widened = coarse[0] < threshold
    if widened:
        coarse = max(coarse, sweep(search["dpi"], scales, lambda size: None), key=lambda found: found[0])
    _, box, scale = coarse
    pad, step = search["pad"], search["step"]

    def around(size: Size) -> Box:
        return clamp_box((box[0] - pad, box[1] - pad, box[0] + size[0] + pad, box[1] + size[1] + pad), page)

    fine = sweep(search["fine_dpi"], steps(scale - step, scale + step, step / 4), around)
    score, box, _ = fine if fine[0] >= 0 else coarse
    return clamp_box(box, page), score, widened


def estimate_offset(
    score_at: Callable[[ClipName, int], float | None],
    samples: Sequence[ClipName],
    candidates: Iterable[int],
    threshold: float,
) -> tuple[int, float]:
    """إزاحة ملف كتاب الطالب (صفحة الملف = المطبوع + الإزاحة): المرشّح الأعلى متوسطَ مطابقة على العيّنة؛ الأصغر عند التعادل.

    `score_at` يعيد None لصفحة خارج الملف. أفضل متوسط دون العتبة خطأ صريح: تُكتب `page_offset` يدويًا.
    """
    best: tuple[float, int] | None = None
    for offset in candidates:
        scores = [score_at(clip, offset) for clip in samples]
        if not scores or any(s is None for s in scores):
            continue
        mean = sum(scores) / len(scores)  # type: ignore[arg-type]
        if best is None or mean > best[0]:
            best = (mean, offset)
    if best is None or best[0] < threshold:
        found = "لا مرشّح" if best is None else f"أفضل متوسط {best[0]:.2f} عند {best[1]}"
        raise StudentClipsError(
            f"تعذّر تقدير إزاحة صفحات كتاب الطالب ({found}): اكتب student_clips.page_offset"
        )
    return best[1], best[0]


def pick_samples(clips: Sequence[ClipName], count: int) -> list[ClipName]:
    """عيّنة موزعة على الكتاب من المقاطع الأصلية (أول ووسط وآخر)."""
    mains = [c for c in clips if not c.cont] or list(clips)
    if len(mains) <= count:
        return mains
    return (
        [mains[round(i * (len(mains) - 1) / (count - 1))] for i in range(count)] if count > 1 else mains[:1]
    )


def status_of(score: float, name: str, threshold: float, approved: Iterable[str]) -> str:
    """ok بدرجة العتبة فأكثر؛ approved لمطابقة ضعيفة راجعها المالك؛ review لغيرها (لا يُكتب مقطعها)."""
    if score >= threshold:
        return "ok"
    return "approved" if name in set(approved) else "review"


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    clips = result["clips"]
    scores = [c["score"] for c in clips if c.get("score") is not None]
    kinds: dict[str, int] = {}
    for c in clips:
        if c.get("kind"):
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    return {
        "clips": len(clips),
        "written": sum(1 for c in clips if c["status"] in ("ok", "approved")),
        "review": [c["file"] for c in clips if c["status"] in ("review", "missing")],
        "min_score": round(min(scores), 3) if scores else None,
        "min_dpi": min((c["dpi"] for c in clips if c.get("dpi")), default=None),
        "kinds": kinds,
        "page_offset": result["page_offset"],
        "unmatched_names": len(result["unmatched"]),
    }


def unreviewed(result: dict[str, Any]) -> list[str]:
    return [c["file"] for c in result["clips"] if c["status"] in ("review", "missing")]


# ───── التشغيل على الملفين (pymupdf وOpenCV؛ بيئة guide_extract) ─────
def cv_matcher(page_image: Callable[[int], Any], clip: Any) -> Matcher:
    """مطابِق OpenCV: معامل الارتباط المطبَّع (TM_CCOEFF_NORMED) لقالب المقطع الرمادي مصغَّرًا إلى مقاسه في صورة الصفحة."""
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
        template = cv2.resize(clip, (w, h), interpolation=cv2.INTER_AREA)
        scores = np.nan_to_num(
            cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED), nan=-1.0, posinf=-1.0, neginf=-1.0
        )
        _, score, _, where = cv2.minMaxLoc(scores)
        return (float(score), (where[0] + x0) / k, (where[1] + y0) / k)

    return match


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
    search, threshold = cfg["search"], cfg["threshold"]
    coarse_dpi = max(cfg["clip_dpi"] // 4, 50)

    with pymupdf.open(book.pdf()) as guide_doc, pymupdf.open(student_pdf(book)) as student_doc:
        guide, student = _Pages(guide_doc), _Pages(student_doc)
        located: dict[str, tuple[Any, Box, float, Box | None]] = {}
        matched: dict[tuple[str, int], tuple[Box, float, bool]] = {}

        def locate(clip: ClipName) -> tuple[Any, Box, float, Box | None]:
            """صورة المقطع الرمادية وصندوقه في صفحة الدليل ودرجته ولوحة صفحة الطالب فيها."""
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
                located[clip.file] = (gray, box, score, panel_rect(rects, cfg["panel"]))
            return located[clip.file]

        def on_page(clip: ClipName, number: int) -> tuple[Box, float, bool] | None:
            """مطابقة المقطع في صفحة من ملف كتاب الطالب (None خارج الملف)."""
            if not 1 <= number <= student_doc.page_count:
                return None
            if (clip.file, number) not in matched:
                gray, box, _, panel = locate(clip)
                page = student.size(number)
                whole = (0.0, 0.0, *page)
                source_rect = panel or (0.0, 0.0, *guide.size(clip.page))
                predicted = transfer_box(box, source_rect, whole)
                match = cv_matcher(lambda dpi: student.gray(number, dpi), gray)
                matched[clip.file, number] = refine(match, predicted, page, search, threshold)
            return matched[clip.file, number]

        offset, offset_score = cfg["page_offset"], None
        if offset is None:
            known = [c for c in clips if c.page in table]

            def score_at(clip: ClipName, candidate: int) -> float | None:
                found = on_page(clip, table[clip.page] + candidate)
                return None if found is None else found[1]

            offset, offset_score = estimate_offset(
                score_at,
                pick_samples(known, cfg["samples"]),
                range(cfg["offsets"][0], cfg["offsets"][1] + 1),
                threshold,
            )
            located.clear()

        entries = []
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
                entry["status"] = "missing"  # لا رقم مطبوع لصفحة الدليل: تُكمَل في printed_pages
                continue
            base = table[clip.page] + offset
            best: tuple[int, tuple[Box, float, bool]] | None = None
            for shift in sorted(range(-cfg["drift"], cfg["drift"] + 1), key=abs):
                found = on_page(clip, base + shift)
                if found is not None and (best is None or found[1] > best[1][1]):
                    best = (shift, found)
                if best is not None and best[1][1] >= threshold:
                    break
            _, _, guide_score, _ = located.pop(
                clip.file, (None, None, 0.0, None)
            )  # صورة المقطع لا تبقى في الذاكرة بعد مطابقته
            if best is None:
                entry["status"] = "missing"
                continue
            shift, (box, score, widened) = best
            entry.update(
                student_page=base + shift,
                page_shift=shift,
                guide_score=round(guide_score, 3),
                score=round(score, 3),
                widened=widened,
                box=[round(v, 1) for v in box],
                status=status_of(score, clip.file, threshold, cfg["approved"]),
            )
            if entry["status"] == "review":
                continue
            rendered = _render(student_doc, base + shift, box, cfg)
            (target / clip.file).write_bytes(rendered.pop("png"))
            entry.update(rendered)

    return {
        "page_offset": offset,
        "offset_score": None if offset_score is None else round(offset_score, 3),
        "threshold": threshold,
        "clips": entries,
        "unmatched": unmatched,
    }


def load_table(book: Book) -> dict[int, int]:
    path = book.output("printed_pages")
    if not path.exists():
        raise StudentClipsError("لا printed_pages.json: شغّل مرحلة printed_pages أولًا")
    return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
