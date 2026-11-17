"""سطر أوامر الخط: python -m tools.extraction <مجلد الكتاب> <مرحلة> [...]

مراحل الرؤية (خادم llama محلي يُشغَّل ويُغلق آليًا؛ مستأنَفة، وخارج `all` وأختامها): vision_pages، vision_examples، vision_vocab، reps (انظر `vision.py` و`reps.py`)؛ وتقبل `--pages A Z` و`--lessons 1.1 ...`.
المراحل: validate (فحص book.yaml)، ocr (تصيير وقراءة؛ ببيئة guide_extract)، tables (جدول تحليل التمارين)، layout، images، objectives، examples، fusion (دمج OCR والرؤية والجدول)، checks، lesson (سجل الدرس)، all
(الأربع الأخيرة بعد layout؛ وtables قبل layout حين layout.anchor=analysis). المخرجات في مجلد الكتاب خارج المستودع، ويطبع كل مرحلة ملخصها العددي.
كل مرحلة تتخطى نفسها ما لم تتغير تجزئة مدخلها (`stamps.py`)، و`--force` يعيدها؛ وتصحيحات الكتاب اليدوية (`corrections.py`)
تُطبَّق على مخرج مرحلتها بأسبابها.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from . import (
    checks,
    corrections,
    examples,
    fusion,
    images,
    layout,
    lesson,
    objectives,
    publish,
    reps,
    stamps,
    tables,
    vision,
)
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


def stage_tables(book: Book) -> None:
    from . import ocr

    result = tables.build(book, lambda p: ocr.boxes(book, p))
    tables.write(book, result)
    ocr.release()
    print(json.dumps(tables.summarize(result), ensure_ascii=False))


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


def stage_fusion(book: Book) -> None:
    result = fusion.build(book, _layout(book))
    _write(book.output("fusion"), result)
    print(json.dumps(fusion.summarize(result), ensure_ascii=False))


def stage_lesson(book: Book) -> None:
    path = book.output("objectives")
    objectives = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"lexicon_version": None, "lessons": {}}
    )
    result = lesson.run(book, _layout(book), objectives)
    _write(book.output("lesson"), result)
    print(json.dumps(lesson.summarize(result), ensure_ascii=False))


def _need(book: Book, stage: str) -> None:
    if not publish.configured(book, stage):
        raise publish.PublishError(f"لا قسم {stage} في book.yaml")


def stage_load(book: Book) -> None:
    _need(book, "load")
    result = publish.build_load(book, lesson.lessons_dir(book))
    publish.write_result(book, "load", result)
    print(json.dumps(publish.summarize(result), ensure_ascii=False))


def stage_publish(book: Book) -> None:
    _need(book, "publish")
    result = publish.build_publish(book)
    publish.write_result(book, "publish", result)
    print(json.dumps(publish.summarize(result), ensure_ascii=False))


def stage_checks(book: Book) -> None:
    result = checks.run(book, _layout(book))
    _emit(book, "checks", book.out / "checks.json", result)
    print(json.dumps(checks.summarize(result), ensure_ascii=False))


def stage_ocr(book: Book) -> None:
    from . import ocr

    print(json.dumps({"rendered": ocr.render(book), "read": ocr.run(book)}, ensure_ascii=False))


def _with_vision(book: Book, stage: str, run: Callable[[Any], dict[str, Any]]) -> None:
    from . import llama

    with llama.serve(book, vision.model_size(book, stage)) as server:
        print(json.dumps(run(llama.asker(server)), ensure_ascii=False))


def run_vision_stage(book: Book, name: str, pages: list[int] | None, lessons: list[str] | None) -> None:
    print(f"== {name}")
    if name == "vision_pages":
        first, last = pages or [1, book["pages"]]
        _with_vision(book, "pages", lambda ask: vision.run_pages(book, ask, first, last))
    elif name == "vision_examples":
        _with_vision(book, "examples", lambda ask: vision.run_examples(book, ask, lessons))
    elif name == "vision_vocab":
        _with_vision(
            book,
            "vocab",
            lambda ask: vision.run_vocab(
                book, ask, [p for p in vision.opener_pages(book) if not pages or pages[0] <= p <= pages[1]]
            ),
        )
    else:
        _with_vision(book, "reps", lambda ask: reps.run(book, ask))


VISION_STAGES = ("vision_pages", "vision_examples", "vision_vocab", "reps")

STAGES: dict[str, Callable[[Book], Any]] = {
    "ocr": stage_ocr,
    "tables": stage_tables,
    "layout": stage_layout,
    "images": stage_images,
    "objectives": stage_objectives,
    "examples": stage_examples,
    "fusion": stage_fusion,
    "checks": stage_checks,
    "lesson": stage_lesson,
    "load": stage_load,
    "publish": stage_publish,
}
TARGETED = ("load", "publish")  # مراحل لها وجهة خارج مجلد الكتاب: ختمها يشمل بصمة الوجهة


def run_stage(book: Book, name: str, force: bool = False) -> bool:
    """يشغّل مرحلة ما لم يتغير مدخلها منذ آخر تشغيل ناجح (الختم والناتج معًا)؛ يعيد هل عملت."""
    if "layout" in stamps.INPUTS[name]["after"]:
        _layout(book)  # ناتجها مدخل الختم: يُبنى قبل حسابه لا بعده، وإلا بطل الختم عند أول تشغيل
    current = stamps.digest(book, name, target=publish.target_token(name) if name in TARGETED else "")
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
    ap.add_argument("stage", choices=["validate", "all", *STAGES, *VISION_STAGES])
    ap.add_argument(
        "--pages",
        nargs=2,
        type=int,
        metavar=("من", "إلى"),
        help="نطاق صفحات لمرحلتي vision_pages وvision_vocab",
    )
    ap.add_argument("--lessons", nargs="+", help="دروس vision_examples (مثل 1.1 1.2)؛ الافتراضي كلها")
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
    if args.stage in VISION_STAGES:
        try:
            run_vision_stage(book, args.stage, args.pages, args.lessons)
        except (OSError, RuntimeError) as e:
            print(f"تعذّر تشغيل الرؤية: {e}", file=sys.stderr)
            return 4
        return 0
    todo = [args.stage]
    if args.stage == "all":
        needs_tables = book["layout"]["anchor"] == "analysis" and book.has_dir("tables")
        todo = [
            *(["tables"] if needs_tables else []),
            "layout",
            "images",
            "objectives",
            "examples",
            "fusion",
            "checks",
            "lesson",
            # الأقسام المعرَّفة في book.yaml فقط؛ load قبل publish لأن النشر يلزمه المقرر محمَّلًا
            *(s for s in TARGETED if publish.configured(book, s)),
        ]
    try:
        for name in todo:
            run_stage(book, name, args.force)
    except corrections.CorrectionError as e:
        print(f"تصحيح مرفوض: {e}", file=sys.stderr)
        return 3
    except publish.PublishError as e:
        print(f"تعذّر التحميل أو النشر: {e}", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
