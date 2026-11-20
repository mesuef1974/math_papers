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
HERE = Path(__file__).parent
FAMILIES = HERE / "families"  # ملفات عائلات التخطيط: يرثها book.yaml بـ extends: <اسم>
LEXICON = (
    HERE / "bloom_lexicon_ar.json"
)  # معجم العربية؛ لغة أخرى تضع bloom_lexicon_<لغة>.json أو تسمّي ملفها بـ bloom_lexicon
DEFAULT_ID_FORMAT = "{unit}.{lesson}"

_REQUIRED: dict[str, tuple[str, ...]] = {
    "": ("id", "title", "language", "pages", "out", "pdf", "dirs", "markers", "layout", "standards"),
    "pdf": ("dir", "pattern"),
    "dirs": ("ocr", "render"),
    "markers": ("opener", "objective_label", "objective_intro", "objective_end"),
    "layout": ("anchor", "end", "image_min"),
    "standards": ("pattern",),
}


def deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """الخرائط تُدمج مفتاحًا مفتاحًا، وما عداها (قوائم وقيم) يستبدله الابن كله. لا يغيّر مدخليه."""
    out = dict(base)
    for key, value in over.items():
        out[key] = (
            deep_merge(out[key], value)
            if isinstance(value, dict) and isinstance(out.get(key), dict)
            else value
        )
    return out


def _family_path(ref: str, here: Path) -> Path:
    if "/" in ref or "\\" in ref or ref.endswith((".yaml", ".yml")):
        path = Path(ref)
        return path if path.is_absolute() else here / path
    return FAMILIES / f"{ref}.yaml"


def resolve(path: Path, _chain: tuple[Path, ...] = ()) -> dict[str, Any]:
    """يقرأ ملف إعداد ويدمج ما يرثه (extends: اسم عائلة أو مسار نسبي لمجلد الملف) تحت قيمه هو. دورة الوراثة خطأ."""
    path = path.resolve()
    if path in _chain:
        raise ValueError("دورة في extends: " + " ← ".join(p.name for p in (*_chain, path)))
    if not path.exists():
        raise FileNotFoundError(f"ملف الإعداد غير موجود: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or "extends" not in cfg:
        return cfg
    ref = cfg["extends"]
    if not isinstance(ref, str) or not ref:
        raise ValueError("extends يجب أن يكون اسم عائلة أو مسارًا")
    parent = resolve(_family_path(ref, path.parent), (*_chain, path))
    return deep_merge(parent, {k: v for k, v in cfg.items() if k != "extends"})


def id_format_error(fmt: Any) -> str | None:
    if not isinstance(fmt, str) or "{unit}" not in fmt or "{lesson}" not in fmt:
        return "layout.id_format يلزمه {unit} و{lesson}"
    try:
        fmt.format(unit=1, lesson=1)
    except (KeyError, IndexError, ValueError):
        return "layout.id_format صيغة غير صالحة"
    return None


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
    if "id_format" in layout and (err := id_format_error(layout["id_format"])):
        errs.append(err)
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
    from . import publish, reps, student_clips, student_examples  # كسول: كلها تستورد Book من هذا الملف

    errs += reps.errors(cfg)
    errs += publish.errors(cfg)
    errs += student_clips.errors(cfg)
    errs += student_examples.errors(cfg)
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
        cfg = resolve(path)
        errs = validate(cfg)
        if errs:
            raise ValueError("book.yaml معيب: " + "؛ ".join(errs))
        book = cls(root, cfg)
        if not book.lexicon_path.is_file():
            raise ValueError(f"book.yaml معيب: معجم بلوم غير موجود: {book.lexicon_path.name}")
        return book

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

    @property
    def lexicon_path(self) -> Path:
        """معجم الأفعال: `bloom_lexicon` (اسم في مجلد الأداة أو مسار) أو bloom_lexicon_<اللغة>.json."""
        ref = self.cfg.get("bloom_lexicon") or f"bloom_lexicon_{self.cfg['language']}.json"
        path = Path(ref)
        return path if path.is_absolute() else HERE / path

    def lesson_id(self, unit: int, lesson: int) -> str:
        return self.cfg["layout"].get("id_format", DEFAULT_ID_FORMAT).format(unit=unit, lesson=lesson)

    def dir(self, key: str) -> Path:
        return self.out / self.cfg["dirs"][key]

    def has_dir(self, key: str) -> bool:
        return key in self.cfg["dirs"]

    def output(self, key: str) -> Path:
        defaults = {
            "layout": "layout.json",
            "objectives": "objectives.json",
            "examples": "examples.json",
            "tables": "tables.json",
            "fusion": "fusion.json",
            "lesson": "lessons.json",
            "load": "load.json",
            "publish": "publish.json",
            "printed_pages": "printed_pages.json",
            "exercise_links": "exercise_links.json",
            "exercise_badges": "exercise_badges.json",
            "exercise_try": "exercise_try.json",
            "student_clips": "student_clips.json",
            "student_decks": "student_decks.json",
            "student_pages": "student_pages.json",
            "student_examples": "student_examples.json",
            "student_try": "student_try.json",
        }
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
