"""الصور المضمَّنة في صفحات الدليل بدقتها الأصلية (أساس قص الأمثلة للعروض): ملف لكل صورة وفهرس index.json.

الصور خارج المستودع (dirs.student_pages). المصدر derived: لا قراءة بصرية، فقط ما في PDF. idempotent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .config import Book


def keep(info: dict[str, Any], minimum: tuple[int, int]) -> bool:
    """صورة صفحة لا أيقونة: xref حقيقي وأبعادها لا تقل عن الحد الأدنى (عرض، ارتفاع)."""
    return bool(info.get("xref")) and info["width"] >= minimum[0] and info["height"] >= minimum[1]


def entry(
    page: int, xref: int, img: dict[str, Any], info: dict[str, Any], page_size: tuple[float, float], name: str
) -> dict[str, Any]:
    return {
        "page": page,
        "xref": xref,
        "file": name,
        "width": img["width"],
        "height": img["height"],
        "bbox": [round(v, 1) for v in info["bbox"]],
        "page_size": [round(page_size[0], 1), round(page_size[1], 1)],
        "ext": img["ext"],
        "bytes": len(img["image"]),
        "has_smask": bool(img.get("smask")),
        "sha256_12": hashlib.sha256(img["image"]).hexdigest()[:12],
    }


def extract(book: Book) -> list[dict[str, Any]]:
    import pymupdf

    out = book.dir("student_pages")
    out.mkdir(parents=True, exist_ok=True)
    minimum = tuple(book["layout"]["image_min"])
    index: list[dict[str, Any]] = []
    with pymupdf.open(book.pdf()) as doc:
        for n, page in enumerate(doc, 1):
            seen: set[int] = set()
            for info in page.get_image_info(xrefs=True):
                xref = info["xref"]
                if xref in seen or not keep(info, minimum):  # type: ignore[arg-type]
                    continue
                seen.add(xref)
                img = doc.extract_image(xref)
                if not img:
                    continue
                target = out / f"{n:04d}_xref{xref}.{img['ext']}"
                if not target.exists():
                    target.write_bytes(img["image"])
                index.append(entry(n, xref, img, info, (page.rect.width, page.rect.height), target.name))
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    return index


def by_lesson(index: list[dict[str, Any]], layout: dict[str, Any]) -> dict[str, list[str]]:
    """ملفات الصور موزعة على الدروس بحسب مدى صفحاتها؛ صورة خارج كل درس لا تدخل أي درس."""
    spans = {r["id"]: r["pages_pdf"] for r in layout["lessons"] if r["pages_pdf"]}
    return {lid: [e["file"] for e in index if span[0] <= e["page"] <= span[1]] for lid, span in spans.items()}
