"""إعداد كتاب واحد (book.yaml): كل مراحل الخط تقرؤه ولا تثبّت مسارًا ولا علامة ولا عتبة.

book.yaml يقع في مجلد الكتاب خارج المستودع (فيه نص الدليل وصوره)، والمستودع يحمل المخطط والمدقّق فقط.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ANCHORS = ("opener", "analysis")  # كيف يُعرف الدرس: بصفحة افتتاحه، أو بصفحة جدول تحليل التمارين
ENDS = ("quiz", "next_opener")  # كيف تنتهي صفحاته: بصفحة اختبار الدرس، أو بما قبل افتتاحية التالي
LEXICON = Path(__file__).with_name("bloom_lexicon_ar.json")

_REQUIRED: dict[str, tuple[str, ...]] = {
    "": ("id", "title", "language", "pages", "out", "pdf", "dirs", "markers", "layout", "standards"),
    "pdf": ("dir", "pattern"),
    "dirs": ("ocr", "render"),
    "markers": ("opener", "objective_label", "objective_intro", "objective_end"),
    "layout": ("anchor", "end", "image_min"),
    "standards": ("pattern",),
}


def validate(cfg: dict[str, Any]) -> list[str]:
    """أخطاء الإعداد (قائمة فارغة = سليم). لا يلمس القرص."""
    errs: list[str] = []
    if not isinstance(cfg, dict):
        return ["الإعداد ليس خريطة"]
    for section, keys in _REQUIRED.items():
        node = cfg if not section else cfg.get(section)
        if section and not isinstance(node, dict):
            errs.append(f"القسم {section} مفقود")
            continue
        errs += [f"{section + '.' if section else ''}{k} مفقود" for k in keys if k not in node]
    if errs:
        return errs
    if not isinstance(cfg["pages"], int) or cfg["pages"] < 1:
        errs.append("pages يجب أن يكون عددًا موجبًا")
    layout = cfg["layout"]
    if layout["anchor"] not in ANCHORS:
        errs.append(f"layout.anchor خارج {ANCHORS}")
    if layout["end"] not in ENDS:
        errs.append(f"layout.end خارج {ENDS}")
    if layout["anchor"] == "analysis" and "analysis" not in cfg["markers"]:
        errs.append("anchor=analysis يلزمه markers.analysis")
    if layout["end"] == "quiz" and "quiz" not in cfg["markers"]:
        errs.append("end=quiz يلزمه markers.quiz")
    w = layout["image_min"]
    if not (isinstance(w, list) and len(w) == 2 and all(isinstance(x, int) and x > 0 for x in w)):
        errs.append("layout.image_min يجب أن يكون [عرض، ارتفاع]")
    if not isinstance(cfg["markers"]["objective_end"], list) or not cfg["markers"]["objective_end"]:
        errs.append("markers.objective_end قائمة غير فارغة")
    try:
        re.compile(cfg["standards"]["pattern"])
    except re.error as e:
        errs.append(f"standards.pattern نمط غير صالح: {e}")
    for key in ("pattern",):
        try:
            re.compile(cfg.get("examples", {}).get(key, "x"))
        except re.error as e:
            errs.append(f"examples.{key} نمط غير صالح: {e}")
    return errs


class Book:
    """كتاب مُحمَّل: `Book.load(مجلد)` يقرأ book.yaml ويرفض الإعداد المعيب برسالة بالعربية."""

    def __init__(self, root: Path, cfg: dict[str, Any]):
        self.root = Path(root)
        self.cfg = cfg

    @classmethod
    def load(cls, root: str | Path) -> Book:
        root = Path(root)
        path = root / "book.yaml"
        if not path.exists():
            raise FileNotFoundError(f"لا book.yaml في {root}")
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        errs = validate(cfg)
        if errs:
            raise ValueError("book.yaml معيب: " + "؛ ".join(errs))
        return cls(root, cfg)

    def __getitem__(self, key: str) -> Any:
        return self.cfg[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.cfg.get(key, default)

    @property
    def id(self) -> str:
        return self.cfg["id"]

    @property
    def out(self) -> Path:
        out = Path(self.cfg["out"])
        return out if out.is_absolute() else self.root / out

    def dir(self, key: str) -> Path:
        return self.out / self.cfg["dirs"][key]

    def has_dir(self, key: str) -> bool:
        return key in self.cfg["dirs"]

    def output(self, key: str) -> Path:
        defaults = {"layout": "layout.json", "objectives": "objectives.json", "examples": "examples.json"}
        outputs = self.cfg.get("outputs", {})
        # generic_<اسم> يتقدم على <اسم> حين يشترك الكتاب مع أدوات قديمة في الملف نفسه بصيغة مختلفة
        return self.out / outputs.get(f"generic_{key}", outputs.get(key, defaults[key]))

    def pdf(self) -> Path:
        c = self.cfg["pdf"]
        folder = Path(c["dir"])
        folder = folder if folder.is_absolute() else self.root / folder
        files = list(folder.glob(c["pattern"]))
        if not files:
            raise FileNotFoundError(f"لا ملف يطابق {c['pattern']} في {c['dir']}")
        suffix = c.get("prefer_suffix", "")
        return max(files, key=lambda x: (x.name.endswith(suffix) if suffix else False, x.stat().st_size))

    def page_text(self, n: int) -> str:
        return (self.dir("ocr") / f"{n:04d}.txt").read_text(encoding="utf-8")
