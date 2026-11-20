"""قراءة كتاب الطالب: تصيير صفحات `student_pdf` وصناديق PaddleOCR لها، وجدول صفحاته المطبوعة (بيئة guide_extract).

الكتاب المتجهي بلا طبقة نص لا يُقرأ إلا بالتصيير: الصفحات إلى `dirs.student_render` بدقة `student_examples.ocr_dpi`، وصناديق
كل صفحة إلى `dirs.student_ocr/NNNN.json` (أزواج [نص، صندوق])، بدوالّ `ocr.py` نفسها؛ ما صُيِّر أو قُرئ لا يُعاد. ثم
`student_pages.json`: صفحة الملف → رقمها المطبوع بمنطق `printed_pages` نفسه (`tabulate`) وإعداده من `student_examples`
(`band` و`skip` و`set` و`fill`). بلا `band` يُجرَّب شريطا التذييل والترويسة ويُؤخذ ما يعطي جدولًا متزايدًا تمامًا لأكثر الصفحات.
الجدول المرفوض لا يُكتب (رمز الخروج 6). المخرجات في مجلد الكتاب خارج المستودع، والملخص أعداد.
"""

from __future__ import annotations

from typing import Any

from . import printed_pages, student_clips, student_examples
from .config import Book
from .printed_pages import Boxes

BANDS: dict[str, list[float]] = {"footer": printed_pages.DEFAULTS["band"], "header": [0.0, 0.0, 1.0, 0.12]}


def page_table(read: dict[int, Boxes], cfg: dict[str, Any], size: tuple[int, int] | None) -> dict[str, Any]:
    """جدول الصفحات المطبوعة من صناديق صفحات كتاب الطالب، و`band` اسم الشريط المعتمد. `cfg` إعداد `student_examples`."""
    base = {"skip": cfg["skip"], "set": cfg["set"], "fill": cfg["fill"], "size": list(size) if size else None}
    bands = {"config": cfg["band"]} if cfg["band"] else BANDS
    best: dict[str, Any] | None = None
    failure: printed_pages.PrintedPagesError | None = None
    for name, band in bands.items():
        got = printed_pages.tabulate(read, {**base, "band": band})
        try:
            printed_pages.validate(got["table"])
        except printed_pages.PrintedPagesError as e:
            failure = failure or e
            continue
        if best is None or len(got["table"]) > len(best["table"]):
            best = {**got, "band": name}
    if best is None or not best["table"]:
        raise failure or printed_pages.PrintedPagesError("لا رقم صفحة مقروء في كتاب الطالب")
    return best


def run(book: Book) -> dict[str, Any]:
    """يصيّر ويقرأ ما لم يُنجز، ويعيد الجدول المفحوص وأعداد التشغيل."""
    from . import ocr

    student_examples.need_dirs(book, "student_render", "student_ocr")
    cfg = student_examples.settings(book)
    render, cache = book.dir("student_render"), book.dir("student_ocr")
    rendered = ocr.render(book, dpi=cfg["ocr_dpi"], pdf=student_clips.student_pdf(book), out=render)
    images = sorted(render.glob("*.png"))
    read: dict[int, Boxes] = {}
    done = 0
    for image in images:
        target = cache / f"{image.stem}.json"
        done += not target.exists()
        read[int(image.stem)] = ocr.boxes_at(image, target)
    ocr.release()
    size = student_examples.png_size(images[0]) if images else None
    return {**page_table(read, cfg, size), "pages": len(images), "rendered": rendered, "read": done}


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    return {k: (len(v) if k == "table" else v) for k, v in result.items()}
