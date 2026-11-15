"""كتاب اصطناعي صغير لاختبارات الخط: نصوص صفحات مختلقة في مجلد مؤقت، لا نص دليل حقيقي."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.extraction.config import Book


def base_cfg(**over: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "id": "toy",
        "title": "كتاب اختباري",
        "language": "ar",
        "pages": 12,
        "out": ".",
        "pdf": {"dir": ".", "pattern": "*.pdf"},
        "dirs": {"ocr": "ocr", "render": "render", "student_pages": "imgs", "boxes": "boxes"},
        "markers": {
            "opener": "ما ستتعلمه",
            "objective_label": "معايير الدرس",
            "objective_intro": "ما ستتعلمه",
            "objective_end": ["المصطلحات"],
            "end_stop": ["مراجعة الوحدة"],
            "exercises": "تمارين",
        },
        "standards": {"pattern": r"12A\.\d+\.\d+"},
        "layout": {
            "anchor": "opener",
            "end": "next_opener",
            "image_min": [100, 50],
            "min_span": 1,
            "max_span": 10,
        },
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def make_book(root: Path, pages: dict[int, str], **over: Any) -> Book:
    cfg = base_cfg(**over)
    cfg["pages"] = max(pages, default=1)
    (root / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    (root / "ocr").mkdir(exist_ok=True)
    for n, t in pages.items():
        (root / "ocr" / f"{n:04d}.txt").write_text(t, encoding="utf-8")
    return Book.load(root)


TOY_PAGES = {
    1: "غلاف",
    2: "الوحدة 1\nعنوان الدرس\n1.1\nما ستتعلمه\nمعايير الدرس 12A.1.1",
    3: "مثال 1\nشرح",
    4: "مثال 2\nشرح",
    5: "تمارين\n1. أ\n2. ب\n3. ج",
    6: "عنوان الدرس\n1.2\nما ستتعلمه\nمعايير الدرس 12A.1.2",
    7: "مثال 1",
    8: "تمارين\n1. أ\n2. ب",
    9: "مراجعة الوحدة",
    10: "ملحق",
}


@pytest.fixture
def toy(tmp_path: Path) -> Book:
    return make_book(
        tmp_path, TOY_PAGES, layout={"id_pattern": r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"}
    )
