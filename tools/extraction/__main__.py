"""سطر أوامر الخط: python -m tools.extraction <مجلد الكتاب> <مرحلة> [...]

المراحل: validate (فحص book.yaml)، ocr (تصيير وقراءة؛ ببيئة guide_extract)، layout، images، objectives، examples، checks، all
(الأربع الأخيرة بعد layout). المخرجات في مجلد الكتاب خارج المستودع، ويطبع كل مرحلة ملخصها العددي.
كل مرحلة تتخطى نفسها ما لم تتغير تجزئة مدخلها (`stamps.py`)، و`--force` يعيدها؛ وتصحيحات الكتاب اليدوية (`corrections.py`)
تُطبَّق على مخرج مرحلتها بأسبابها.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from . import checks, corrections, examples, images, layout, objectives, stamps
from .config import Book


def _write(path: Any, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _emit(book: Book, stage: str, path: Any, result: dict[str, Any]) -> None:
    """يطبّق تصحيحات المرحلة (بأسبابها) ثم يكتب مخرجها."""
    corrections.apply(book, stage, result)
    _write(path, result)


def _layout(book: Book) -> dict[str, Any]:
    path = book.output("layout")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return stage_layout(book)


def stage_layout(book: Book) -> dict[str, Any]:
    analysis = None
    if book["layout"]["anchor"] == "analysis" and book.has_dir("tables"):
        analysis = sorted(int(p.stem) for p in book.dir("tables").glob("*.json"))
    result = layout.build(book, analysis_pages=analysis)
    _emit(book, "layout", book.output("layout"), result)
    print(json.dumps(layout.summarize(result), ensure_ascii=False))
    return result


def stage_images(book: Book) -> None:
    index = images.extract(book)
    per = images.by_lesson(index, _layout(book))
    print(
        json.dumps(
            {"images": len(index), "lessons_with_images": sum(bool(v) for v in per.values())},
            ensure_ascii=False,
        )
    )


def stage_objectives(book: Book) -> None:
    from . import ocr

    cfg = objectives.settings(book)

    def marks(page: int, a: int, z: float) -> list[int]:
        return (
            objectives.checkmarks(book.dir("render") / f"{page:04d}.png", cfg, a, z)
            if cfg.get("check")
            else []
        )

    result = objectives.build(book, _layout(book), lambda p: ocr.boxes(book, p), marks)
    _emit(book, "objectives", book.output("objectives"), result)
    print(json.dumps(objectives.summarize(result), ensure_ascii=False))


def stage_examples(book: Book) -> None:
    result = examples.build(book, _layout(book), layout.load_pages(book))
    _emit(book, "examples", book.output("examples"), result)
    print(json.dumps(examples.summarize(result), ensure_ascii=False))


def stage_checks(book: Book) -> None:
    result = checks.run(book, _layout(book))
    _emit(book, "checks", book.out / "checks.json", result)
    print(json.dumps(checks.summarize(result), ensure_ascii=False))


def stage_ocr(book: Book) -> None:
    from . import ocr

    print(json.dumps({"rendered": ocr.render(book), "read": ocr.run(book)}, ensure_ascii=False))


STAGES: dict[str, Callable[[Book], Any]] = {
    "ocr": stage_ocr,
    "layout": stage_layout,
    "images": stage_images,
    "objectives": stage_objectives,
    "examples": stage_examples,
    "checks": stage_checks,
}


def run_stage(book: Book, name: str, force: bool = False) -> bool:
    """يشغّل مرحلة ما لم يتغير مدخلها منذ آخر تشغيل ناجح (الختم والناتج معًا)؛ يعيد هل عملت."""
    current = stamps.digest(book, name)
    if not force and stamps.is_fresh(book, name, current):
        print(f"== {name}: لم يتغير مدخلها، تُخطيت")
        return False
    print(f"== {name}")
    STAGES[name](book)
    stamps.record(book, name, current)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.extraction", description=__doc__)
    ap.add_argument("book", help="مجلد الكتاب (فيه book.yaml)")
    ap.add_argument("stage", choices=["validate", "all", *STAGES])
    ap.add_argument("--force", action="store_true", help="يتجاوز أختام المراحل ويعيد التشغيل")
    args = ap.parse_args(argv)
    try:
        book = Book.load(args.book)
    except (FileNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        return 2
    if args.stage == "validate":
        print("book.yaml سليم:", book.id)
        return 0
    todo = ["layout", "images", "objectives", "examples", "checks"] if args.stage == "all" else [args.stage]
    try:
        for name in todo:
            run_stage(book, name, args.force)
    except corrections.CorrectionError as e:
        print(f"تصحيح مرفوض: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
