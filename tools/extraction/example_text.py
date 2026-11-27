"""نص كل مثال من مقطعه المقصوص من كتاب الطالب (بيئة guide_extract)، لفحص ربط صيغنا وأهدافنا بأمثلتها.

مقطع المثال فيه مثال واحد بعينه (`<درس>_m<مثال>_p<صفحة>[_cont].png`)، فنصه أدق من نص صفحة فيها مثالان. صناديق OCR لكل
مقطع تُخزَّن في `dirs.example_ocr` (أو `example_ocr/` تحت مجلد الكتاب) ولا يُعاد المقروء، والمخرج `example_text.json`:
`{درس: {رقم المثال: نص}}`. النص محتوى الكتاب: يبقى خارج المستودع، والملخص أعداد. يقرؤه
`python manage.py check_example_skills <مقرر> --source <مجلد الكتاب>`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import student_clips
from .config import Book

Reader = Callable[[Path, Path], list[tuple[str, list[int]]]]


def clips_dir(book: Book) -> Path:
    """مقاطع الأمثلة بدقتها الأصلية: `example_text.clips`، وإلا هدف `student_clips`."""
    key = book.get("example_text", {}).get("clips") or student_clips.settings(book)["target"]
    return book.dir(key)


def cache_dir(book: Book) -> Path:
    return book.dir("example_ocr") if book.has_dir("example_ocr") else book.out / "example_ocr"


def collect(clips: Path, cache: Path, read: Reader) -> dict[str, dict[str, str]]:
    """نص الأمثلة بترتيب صفحاتها (التتمة بعد أصلها)؛ ما ليس باسم مقطع مثال يُهمل."""
    found = []
    for path in clips.glob("*.png"):
        if m := student_clips.NAME.match(path.name):
            found.append((m["lesson"], int(m["n"]), int(m["page"]), bool(m["cont"]), path))
    out: dict[str, dict[str, str]] = {}
    for lesson, n, _, _, path in sorted(found):
        text = " ".join(t for t, _ in read(path, cache / f"{path.stem}.json"))
        example = out.setdefault(lesson, {})
        example[str(n)] = f"{example.get(str(n), '')} {text}".strip()
    return out


def run(book: Book) -> dict[str, dict[str, str]]:
    from . import ocr

    got = collect(clips_dir(book), cache_dir(book), ocr.boxes_at)
    ocr.release()
    return got
