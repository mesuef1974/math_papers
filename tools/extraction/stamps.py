"""أختام المراحل: كل مرحلة تتخطى نفسها ما لم تتغير تجزئة مدخلها، فإعادة تشغيل الخط على كتاب لم يتغير لا تعمل شيئًا.

ختم المرحلة تجزئة SHA-256 لإعداد الكتاب المدموج وتصحيحاته ومحتوى كل ما تقرؤه (مجلدات ونواتج مراحل سابقة وملف PDF)، وتُحفظ في
`.stamps.json` بمجلد الكتاب. تُتخطى المرحلة فقط إن طابق ختمها وكان ناتجها موجودًا (حُذف الناتج = تُعاد). `--force` يتجاوز الأختام.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from . import corrections, example_text, student_clips, student_examples
from .config import Book
from .lesson import lessons_dir

FILE = ".stamps.json"
VERSION = 1  # يُرفع حين يتغير منطق مرحلة بلا تغيير في مدخلاتها، فتُعاد كل الأختام

# ما تقرؤه كل مرحلة: مجلدات الكتاب (مفاتيح dirs، الغائب منها يُهمَل)، ومراحل سابقة ناتجها مدخل، وهل يدخل ملف PDF
INPUTS: dict[str, dict[str, Any]] = {
    "ocr": {"dirs": (), "after": (), "pdf": True},
    "tables": {"dirs": ("ocr", "render"), "after": (), "pdf": False},
    "layout": {"dirs": ("ocr", "tables"), "after": (), "pdf": False},
    "images": {"dirs": (), "after": (), "pdf": True},
    "objectives": {"dirs": ("ocr", "render"), "after": ("layout",), "pdf": False},
    "examples": {"dirs": ("ocr", "vision", "badges"), "after": ("layout",), "pdf": False},
    "fusion": {"dirs": ("ocr", "vision", "tables"), "after": ("layout",), "pdf": False},
    "lesson": {
        "dirs": ("ocr", "vision", "tables", "gold", "vocab"),
        "after": ("layout", "objectives"),
        "pdf": False,
    },
    "checks": {"dirs": ("ocr",), "after": ("layout",), "pdf": False},
    "load": {
        "dirs": (),
        "after": ("lesson",),
        "pdf": False,
    },  # ومجلد سجلات الدروس ووجهة التحميل (انظر digest)
    "printed_pages": {"dirs": ("ocr", "boxes"), "after": (), "pdf": False},
    "exercise_badges": {"dirs": ("ocr", "render", "boxes"), "after": ("layout", "examples"), "pdf": False},
    "exercise_try": {"dirs": ("ocr", "render", "boxes"), "after": ("layout",), "pdf": False},
    "exercise_links": {
        "dirs": ("vision",),
        "after": ("layout", "examples", "exercise_badges", "exercise_try"),
        "pdf": False,
    },
    "publish": {"dirs": (), "after": (), "pdf": False},  # ومجلد المقاطع (publish.clips) ووجهة التخزين
    # ومجلد المقاطع الحالية (student_clips.source) وملف كتاب الطالب
    "student_clips": {"dirs": (), "after": ("printed_pages",), "pdf": True},
    "student_decks": {"dirs": (), "after": ("student_clips",), "pdf": False},  # ومجلد مقاطع كتاب الطالب
    "student_ocr": {"dirs": (), "after": (), "pdf": False},  # وملف كتاب الطالب
    # وملف كتاب الطالب ودروس المقرر (العدد المتوقع)
    "student_examples": {
        "dirs": ("student_ocr",),
        "after": ("layout", "printed_pages", "student_ocr", "exercise_try"),
        "pdf": False,
    },
    # مقاطع الأمثلة نفسها هي المدخل (تُضاف في digest)
    "example_text": {"dirs": (), "after": (), "pdf": False},
}
STUDENT_PDF = ("student_clips", "student_ocr", "student_examples")  # مراحل تقرأ ملف كتاب الطالب


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def output_path(book: Book, stage: str) -> Path:
    """الملف الذي يدل على اكتمال المرحلة."""
    if stage == "ocr":
        return book.dir("ocr") / f"{book['pages']:04d}.txt"
    if stage == "images":
        return book.dir("student_pages") / "index.json"
    if stage == "checks":
        return book.out / "checks.json"
    if stage == "student_ocr":
        return book.output("student_pages")
    return book.output(stage)


def digest(book: Book, stage: str, pdf: Callable[[Book], Path] | None = None, target: str = "") -> str:
    """`target` بصمة وجهة المرحلة (للتحميل والنشر: القاعدة والتخزين)؛ الفارغ لا يدخل التجزئة فلا تتغير أختام غيرهما."""
    spec = INPUTS[stage]
    h = hashlib.sha256()
    h.update(f"{VERSION}|{stage}".encode())
    h.update(json.dumps(book.cfg, sort_keys=True, ensure_ascii=False, default=str).encode())
    corr = corrections.path_of(book)
    if corr.exists():
        h.update(_file_digest(corr).encode())
    if stage == "objectives":
        h.update(_file_digest(book.lexicon_path).encode())
    keys = spec["dirs"]
    if stage == "lesson":  # مجلدات رؤية الأمثلة تسمّيها الإعدادات بترتيب أولويتها
        keys = (*keys, *book.get("lesson", {}).get("example_vision", ["badges"]))
    roots = {key: book.dir(key) for key in keys if book.has_dir(key)}
    if stage == "publish" and (clips := book.get("publish", {}).get("clips")) and book.has_dir(clips):
        roots[clips] = book.dir(clips)
    if stage == "load":
        roots["lessons"] = lessons_dir(book)
    if stage in ("student_clips", "student_decks"):
        key = student_clips.settings(book)["source" if stage == "student_clips" else "target"]
        if book.has_dir(key):
            roots[key] = book.dir(key)
    if stage == "example_text":
        roots["example_clips"] = example_text.clips_dir(book)
    for key, root in roots.items():
        for path in _files(root) if root.is_dir() else ():
            h.update(f"{key}/{path.relative_to(root).as_posix()}:{_file_digest(path)}".encode())
    if target:
        h.update(f"target:{target}".encode())
    for prior in spec["after"]:
        path = output_path(book, prior)
        h.update(f"{prior}:{_file_digest(path) if path.exists() else '-'}".encode())
    if spec["pdf"]:
        path = (pdf or Book.pdf)(book)
        h.update(f"pdf:{_file_digest(path)}".encode())
    if stage == "student_examples":
        h.update(json.dumps(student_examples.expected_counts(book), sort_keys=True).encode())
    if stage in STUDENT_PDF:
        h.update(f"student_pdf:{_file_digest(student_clips.student_pdf(book))}".encode())
    return h.hexdigest()


def _load(book: Book) -> dict[str, str]:
    path = book.out / FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_fresh(book: Book, stage: str, current: str) -> bool:
    return _load(book).get(stage) == current and output_path(book, stage).exists()


def record(book: Book, stage: str, current: str) -> None:
    stamps = _load(book)
    stamps[stage] = current
    (book.out / FILE).write_text(
        json.dumps(stamps, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
