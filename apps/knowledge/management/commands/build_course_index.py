"""يبني الفهرس المشتق لمقرر (`apps/knowledge/data/courses/<المقرر>/index.json`) من مخرجات الاستخراج الخارجية.

المصدر مجلد الكتاب (`lessons/lesson_*.json`) خارج المستودع ولا يُنسخ منه نص: `course_index.build_lesson_index` يُبقي الأرقام
والرموز والفئات المغلقة فقط. أول تشغيل لمقرر جديد ينشئ `course.json` من بيانات المقرر المعطاة (العنوان والصف والفصل...) وقائمة
دروسه بعناوين مؤقتة «الدرس <رمز>»؛ بعدها تُضاف الدروس الجديدة فقط وتبقى العناوين التي عُدّلت يدويًا.
idempotent: التشغيل الثاني على المصدر نفسه يكتب الملفات نفسها بايتًا ببايت.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from apps.knowledge.domain.contract import (
    COURSES_DIR,
    INDEX,
    MANIFEST,
    SCHEMA_VERSION,
    CourseMeta,
    read_course_dir,
)
from apps.knowledge.domain.course_index import build_index
from apps.knowledge.domain.exercise_pages import accepted_ranges
from apps.knowledge.domain.schemas import lesson_sort_key

META_OPTIONS = ("title", "grade", "semester", "academic_year", "track", "edition", "language")
REQUIRED_FOR_NEW = ("title", "grade", "semester", "academic_year")
PRINTED_PAGES = "printed_pages.json"
EXERCISE_PAGES = "exercise_pages.json"


def _exercise_pages(path: Path, required: bool) -> dict[str, list[dict]]:
    """درس → مديات صفحات تمارينه المقبولة من مخرج المرحلة؛ غياب الملف غير المطلوب صراحةً لا شيء."""
    if not path.is_file():
        if required:
            raise CommandError(f"ملف صفحات التمارين غير موجود: {path}")
        return {}
    try:
        lessons = json.loads(path.read_text(encoding="utf-8"))["lessons"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CommandError(f"ملف صفحات التمارين غير صالح: {path}") from error
    out = {code: accepted_ranges(record) for code, record in lessons.items()}
    return {code: ranges for code, ranges in out.items() if ranges}


def _printed_pages(path: Path) -> dict[int, int]:
    """الجدول اختياري: غيابه يترك صفحات الأمثلة None. مفاتيحه وقيمه أرقام صفحات فقط."""
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        table = {int(pdf): int(printed) for pdf, printed in raw.items()}
    except (ValueError, TypeError, AttributeError) as error:
        raise CommandError(f"جدول الصفحات المطبوعة غير صالح: {path}") from error
    if any(not (1 <= page <= 999) for page in table.values()):
        raise CommandError(f"رقم صفحة خارج المدى في {path}")
    return table


def _write(path: Path, data: dict, indent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


class Command(BaseCommand):
    help = "يشتق فهرس مقرر (أرقام وبلوم وتمثيلات بلا نص دليل) من مجلد الاستخراج الخارجي إلى مجلد المقرر."

    def add_arguments(self, parser):
        parser.add_argument("course", help="معرّف المقرر، مثل g10-s1")
        parser.add_argument("--source", required=True, help="مجلد الكتاب المستخرَج (خارج المستودع)")
        parser.add_argument("--lessons-dir", help="مجلد سجلات الدروس إن لم يكن lessons تحت المصدر")
        parser.add_argument(
            "--printed-pages",
            help="جدول صفحة ملف الدليل → صفحة الطالب المطبوعة (JSON)؛ الافتراضي printed_pages.json تحت المصدر إن وُجد",
        )
        parser.add_argument(
            "--exercise-pages",
            help="صفحات التمارين المطبوعة (مخرج المرحلة)؛ الافتراضي exercise_pages.json تحت المصدر إن وُجد",
        )
        parser.add_argument("--courses-dir", default=str(COURSES_DIR), help="جذر مجلدات المقررات")
        parser.add_argument("--title", help="عنوان المقرر (لمقرر جديد)")
        parser.add_argument("--grade", type=int, help="الصف (لمقرر جديد)")
        parser.add_argument("--semester", type=int, help="الفصل (لمقرر جديد)")
        parser.add_argument("--academic-year", help="السنة الأكاديمية مثل 2026-2027 (لمقرر جديد)")
        parser.add_argument("--track", help="المسار إن وُجد")
        parser.add_argument("--edition", help="الطبعة إن وُجدت")
        parser.add_argument("--language", help="لغة الكتاب: ar أو en")

    def handle(
        self,
        *args,
        course,
        source,
        lessons_dir=None,
        courses_dir=None,
        printed_pages=None,
        exercise_pages=None,
        **options,
    ):
        folder = Path(lessons_dir) if lessons_dir else Path(source) / "lessons"
        printed = _printed_pages(Path(printed_pages) if printed_pages else Path(source) / PRINTED_PAGES)
        paged = _exercise_pages(
            Path(exercise_pages) if exercise_pages else Path(source) / EXERCISE_PAGES,
            required=bool(exercise_pages),
        )
        files = sorted(folder.glob("lesson_*.json"))
        if not files:
            raise CommandError(f"لا ملفات lesson_*.json في {folder}")
        target = Path(courses_dir or COURSES_DIR) / course
        manifest_path = target / MANIFEST
        given = {key: options[key] for key in META_OPTIONS if options.get(key) is not None}
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["course"].update(given)
        else:
            missing = [f"--{key.replace('_', '-')}" for key in REQUIRED_FOR_NEW if key not in given]
            if missing:
                raise CommandError(f"مقرر جديد يلزمه: {', '.join(missing)}")
            manifest = {"schema_version": SCHEMA_VERSION, "course": {"slug": course, **given}, "lessons": []}
        try:
            meta = CourseMeta(**manifest["course"])
            index = build_index(
                [json.loads(f.read_text(encoding="utf-8")) for f in files], meta.grade, printed, paged
            )
        except ValidationError as error:
            raise CommandError(str(error)) from error
        if meta.slug != course:
            raise CommandError(f"معرّف المقرر في {MANIFEST} ({meta.slug}) لا يطابق {course}")

        known = {ref["code"]: ref for ref in manifest["lessons"]}
        for lesson in index.lessons:
            placeholder = {
                "code": lesson.lesson,
                "title": f"الدرس {lesson.lesson}",
                "unit": lesson.unit,
                "examinable": True,
            }
            known.setdefault(lesson.lesson, placeholder)
        manifest["course"] = meta.model_dump()
        manifest["lessons"] = sorted(known.values(), key=lambda ref: lesson_sort_key(ref["code"]))
        _write(target / INDEX, index.model_dump(), 1)
        _write(manifest_path, manifest, 2)
        try:
            read_course_dir(target)  # العقد كاملًا يجب أن يصحّ قبل أن يُعدّ البناء ناجحًا
        except (ValidationError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"فهرس {course}: {len(index.lessons)} درسًا → {target.name}/{INDEX}")
