"""مرحلة القراءة: تصيير صفحات PDF الممسوح ثم PaddleOCR (بيئة guide_extract؛ المكتبتان تُستوردان كسولًا).

idempotent ومستأنَف: ما أُنجز لا يُعاد. النصوص والصور في مجلد الكتاب خارج المستودع.
على كرت 8 غ.ب لا يُشغَّل مع نموذج الرؤية معًا: خروج الدالة لا يحرر ذاكرة النموذج، فيلزم `gc.collect()`.
"""

from __future__ import annotations

import gc
import json
from pathlib import Path

from .config import Book

_ocr = None
_rec = None
REC_MODEL = "arabic_PP-OCRv5_mobile_rec"  # نموذج تعرّف lang="ar" في PaddleOCR


def _engine():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR

        _ocr = PaddleOCR(
            lang="ar",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _ocr


def release() -> None:
    global _ocr, _rec
    _ocr = _rec = None
    gc.collect()


def render(book: Book, pages: list[int] | None = None, dpi: int = 220) -> int:
    """يصيّر الصفحات (الكل افتراضًا) إلى PNG في dirs.render؛ يعيد عدد ما صُيِّر الآن."""
    import pymupdf

    out = book.dir("render")
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    with pymupdf.open(book.pdf()) as doc:
        for n in pages or range(1, len(doc) + 1):
            target = out / f"{n:04d}.png"
            if not target.exists():
                doc[n - 1].get_pixmap(dpi=dpi).save(target)
                done += 1
    return done


def read_page(image: Path) -> tuple[list[str], list[list[int]]]:
    for res in _engine().predict(str(image)):
        data = res.json.get("res", res.json)
        return list(data.get("rec_texts", [])), [[int(v) for v in b] for b in data.get("rec_boxes", [])]
    return [], []


def _recognizer():
    global _rec
    if _rec is None:
        from paddleocr import TextRecognition

        _rec = TextRecognition(model_name=REC_MODEL)
    return _rec


def read_scored(image) -> tuple[str, float]:
    """(نص، ثقة) مقطع صغير في الذاكرة (صورة Pillow) بالتعرّف وحده بلا كشف: الكاشف لا يجد سطرًا في مقطع رقم أو كلمة
    (قياس الثاني عشر: صفر من 37 مقطعًا بالكشف، وثقة 0.8 فأكثر بالتعرّف وحده). ما ارتفاعه دون 48 بكسلًا يُكبَّر إليها."""
    import numpy as np

    if image.height < 48:
        scale = 48 / image.height
        image = image.resize((max(1, round(image.width * scale)), 48))
    for res in _recognizer().predict(np.asarray(image.convert("RGB"))):
        data = res.json.get("res", res.json)
        return str(data.get("rec_text", "")), float(data.get("rec_score", 0.0))
    return "", 0.0


def read_crop(image) -> str:
    """نص مقطع صغير (انظر `read_scored`)."""
    return read_scored(image)[0]


def run(book: Book, pages: list[int] | None = None) -> int:
    """نص كل صفحة مصيَّرة إلى dirs.ocr/NNNN.txt؛ يعيد عدد ما قُرئ الآن."""
    out = book.dir("ocr")
    out.mkdir(parents=True, exist_ok=True)
    wanted = set(pages) if pages else None
    done = 0
    for image in sorted(book.dir("render").glob("*.png")):
        n = int(image.stem)
        target = out / f"{n:04d}.txt"
        if target.exists() or (wanted and n not in wanted):
            continue
        texts, _ = read_page(image)
        target.write_text("\n".join(texts), encoding="utf-8")
        done += 1
    release()
    return done


def boxes(book: Book, page: int) -> list[tuple[str, list[int]]]:
    """صناديق الكلمات (نص، [x0, y0, x1, y1]) لصفحة، مخزَّنة في dirs.boxes (افتراضًا opener_boxes)."""
    folder = book.out / book.cfg["dirs"].get("boxes", "opener_boxes")
    cache = folder / f"{page:04d}.json"
    if cache.exists():
        return [(t, b) for t, b in json.loads(cache.read_text(encoding="utf-8"))]
    texts, bxs = read_page(book.dir("render") / f"{page:04d}.png")
    got = [(t.strip(), b) for t, b in zip(texts, bxs, strict=True)]
    folder.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    return got
