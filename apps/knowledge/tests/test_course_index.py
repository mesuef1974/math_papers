"""الفهرس المشتق للمقرر (والعاشر أول مقرر به): المخطط صارم، والباني يُبقي الأرقام والفئات المغلقة فقط، والملف المودَع سليم ولا نص دليل فيه."""

import json
import re

import pytest
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.knowledge.domain.contract import COURSES_DIR, INDEX, read_course_dir
from apps.knowledge.domain.course_index import (
    BLOOM_VALUES,
    CourseIndex,
    LessonIndex,
    build_index,
    build_lesson_index,
)
from apps.knowledge.domain.schemas import ExampleData, representations_in
from apps.knowledge.selectors import course_index, lesson_index

GRADE10_INDEX = COURSES_DIR / GRADE10_SLUG / INDEX


def field(value):
    return {"value": value, "source": "guide", "status": "ok"}


def lesson_output(**over):
    base = {
        "id": "2.1",
        "unit": "2",
        "standards": field(["10.2.2", "غير معيار"]),
        "practices": field([]),
        "objectives": field(
            [
                {"text": "نص هدف طويل من الدليل", "verb": "استعمال", "bloom": "تطبيق"},
                {"text": "نص آخر", "verb": "x", "bloom": None},
            ]
        ),
        "examples": [
            {
                "n": 2,
                "representation": field(["جدول", "جبري"]),
                "skill": field({"title": "عنوان", "focus": "س"}),
            },
            {"n": 1, "representation": field(["سياق حياتي", "بياني"])},
        ],
        "exercise_analysis": field(
            [
                {"example": 1, "dok": 1, "exercises": [3, 1, 2, 2]},
                {"example": 1, "dok": None, "exercises": [9]},
                {"example": 2, "dok": 2, "exercises": [4]},
            ]
        ),
        "exercises": field([1, 2, 3, 4, 9]),
        "task_guide": field({"basic": "1-4, 9", "advanced": "2-9"}),
        "lesson_quiz": field({"questions": 3, "depth": [1, 2, 2]}),
        "vocabulary": field(
            [
                {"ar": "حل", "en": "solution", "kind": "review"},
                {"ar": "معادلة", "en": "equation", "kind": "new"},
                {"ar": "صفر", "en": "zero", "kind": "new"},
            ]
        ),
    }
    return base | over


def test_builder_keeps_only_numbers_and_closed_categories():
    rec = build_lesson_index(lesson_output(), 10)
    assert rec["standards"] == ["10.2.2"]
    assert rec["objectives_bloom"] == ["تطبيق", "unclassified"]
    assert [e["n"] for e in rec["examples"]] == [1, 2]
    assert rec["examples"][0]["representations"] == ["بياني", "سياق"]  # «سياق حياتي» يُوحَّد
    assert rec["examples"][1]["representations"] == ["جدول", "جبري"]
    assert rec["analysis"] == [
        {"example": 1, "dok": 1, "exercises": [1, 2, 3]},
        {"example": 2, "dok": 2, "exercises": [4]},
    ]  # الصف بلا عمق لا يدخل
    assert rec["exercises_total"] == 9
    assert rec["task_guide"] == {"basic": "1-4, 9", "advanced": "2-9"}
    assert rec["quiz_depths"] == [1, 2, 2]
    assert rec["vocabulary"] == {"new": 2, "review": 1}
    assert LessonIndex(**rec)


def test_no_source_text_survives_the_builder():
    dumped = json.dumps(build_lesson_index(lesson_output(), 10), ensure_ascii=False)
    for leaked in ("نص هدف", "عنوان", "معادلة", "solution", "استعمال"):
        assert leaked not in dumped


def test_task_guide_that_is_not_a_numeric_range_is_dropped():
    bad = lesson_output(task_guide=field({"basic": "انظر الدليل", "advanced": "2-9"}))
    assert build_lesson_index(bad, 10)["task_guide"] is None


def test_schema_rejects_free_text_and_unknown_fields():
    rec = build_lesson_index(lesson_output(), 10)
    with pytest.raises(ValidationError):
        LessonIndex(**rec | {"title": "عنوان الدرس"})
    with pytest.raises(ValidationError):
        LessonIndex(**rec | {"objectives_bloom": ["نص حر"]})
    with pytest.raises(ValidationError):
        LessonIndex(**rec | {"task_guide": {"basic": "نص", "advanced": "1-2"}})
    with pytest.raises(ValidationError):
        LessonIndex(**rec | {"examples": [{"n": 1, "representations": ["غير معروف"]}]})


def test_index_orders_lessons_numerically():
    lessons = [lesson_output(id="2.10"), lesson_output(id="2.2"), lesson_output(id="1.4")]
    assert [x.lesson for x in build_index(lessons, 10).lessons] == ["1.4", "2.2", "2.10"]


# --- الملف المودَع ---

EXPECTED = ["1.1", "1.2", "1.3", "1.4"] + [f"2.{n}" for n in range(1, 11)] + [f"3.{n}" for n in range(1, 6)]


@pytest.mark.usefixtures("loaded_courses")
def test_committed_index_is_valid_and_complete():
    index = course_index(GRADE10_SLUG)
    assert [x.lesson for x in index.lessons] == EXPECTED
    for lesson in index.lessons:
        assert lesson.unit == int(lesson.lesson[0])
        assert lesson.examples, lesson.lesson
        assert lesson.practices, lesson.lesson
        assert lesson.analysis, lesson.lesson
        assert set(lesson.objectives_bloom) <= set(BLOOM_VALUES)
        example_numbers = {e.n for e in lesson.examples}
        assert {row.example for row in lesson.analysis} <= example_numbers, lesson.lesson
        flat = [n for row in lesson.analysis for n in row.exercises]
        assert max(flat) <= lesson.exercises_total, lesson.lesson


def test_committed_index_roundtrips_byte_for_byte():
    raw = GRADE10_INDEX.read_text(encoding="utf-8")
    again = json.dumps(CourseIndex(**json.loads(raw)).model_dump(), ensure_ascii=False, indent=1) + "\n"
    assert raw == again


def test_committed_index_holds_no_arabic_prose():
    """الحروف العربية الوحيدة المسموحة قيم القوائم المغلقة (بلوم وتمثيلات)؛ أي جملة تعني تسرّب نص."""
    allowed = {*BLOOM_VALUES, "جدول", "بياني", "جبري", "سياق"}
    strings = re.findall(r'"([^"]*[؀-ۿ][^"]*)"', GRADE10_INDEX.read_text(encoding="utf-8"))
    assert set(strings) <= allowed


@pytest.mark.usefixtures("loaded_courses")
def test_selector_finds_a_lesson_in_its_own_course():
    assert lesson_index(GRADE10_SLUG, "3.5").unit == 3
    assert lesson_index(GRADE10_SLUG, "9.9") is None
    # الرمز نفسه في مقرر آخر درسه هو (الثاني عشر من دروسه بصياغتنا)، وفي مقرر بلا مصدر لا درس
    assert lesson_index(GRADE12_SLUG, "3.5").examples != lesson_index(GRADE10_SLUG, "3.5").examples
    assert lesson_index("g7-s1", "3.5") is None
    with pytest.raises(KeyError, match="لا فهرس محمَّل"):
        course_index("g7-s1")


def test_builder_keeps_only_the_standards_of_the_course_grade():
    record = lesson_output(standards=field(["10.2.2", "9.1.4", "12A.3.4", "نص"]))
    assert build_lesson_index(record, 10)["standards"] == ["10.2.2"]
    assert build_lesson_index(record, 12)["standards"] == ["12A.3.4"]
    assert build_lesson_index(record, 9)["standards"] == ["9.1.4"]


def test_index_accepts_two_digit_units_and_rejects_duplicates():
    late = build_lesson_index(lesson_output(id="12.3", unit=12), 10)
    assert LessonIndex(**late).unit == 12
    with pytest.raises(ValidationError, match="مكرر"):
        CourseIndex(lessons=[late, late])


def test_index_command_reads_lessons_dir_override(tmp_path):
    from django.core.management import call_command

    folder = tmp_path / "records"
    folder.mkdir()
    (folder / "lesson_2_1.json").write_text(json.dumps(lesson_output()), encoding="utf-8")
    courses = tmp_path / "courses"
    new_course = {
        "title": "الرياضيات: السابع، الفصل الثاني",
        "grade": 10,
        "semester": 2,
        "academic_year": "2026-2027",
    }
    common = {"source": str(tmp_path), "courses_dir": str(courses)}
    with pytest.raises(Exception, match="--title"):
        call_command(
            "build_course_index", "g7-s2", lessons_dir=str(folder), **common
        )  # مقرر جديد بلا بياناته
    call_command("build_course_index", "g7-s2", lessons_dir=str(folder), **common, **new_course)
    target = courses / "g7-s2"
    assert [x["lesson"] for x in json.loads((target / INDEX).read_text(encoding="utf-8"))["lessons"]] == [
        "2.1"
    ]
    knowledge = read_course_dir(target)
    assert knowledge.course.slug == "g7-s2" and knowledge.course.language == "ar"
    assert [(ref.code, ref.title, ref.unit) for ref in knowledge.lessons] == [("2.1", "الدرس 2.1", 2)]
    assert [p.source for p in knowledge.profiles] == ["extracted"]

    # إعادة البناء: درس جديد يُضاف، والعنوان المعدَّل يدويًا يبقى، والملفات تُكتب بايتًا ببايت
    manifest = json.loads((target / "course.json").read_text(encoding="utf-8"))
    manifest["lessons"][0]["title"] = "عنوان مراجَع"
    (target / "course.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (folder / "lesson_2_10.json").write_text(json.dumps(lesson_output(id="2.10")), encoding="utf-8")
    (folder / "lesson_2_2.json").write_text(json.dumps(lesson_output(id="2.2")), encoding="utf-8")
    call_command("build_course_index", "g7-s2", lessons_dir=str(folder), **common)
    first = {f.name: f.read_bytes() for f in target.iterdir()}
    refs = read_course_dir(target).lessons
    assert [(ref.code, ref.title) for ref in refs] == [
        ("2.1", "عنوان مراجَع"),
        ("2.2", "الدرس 2.2"),
        ("2.10", "الدرس 2.10"),
    ]
    call_command("build_course_index", "g7-s2", lessons_dir=str(folder), **common)
    assert {f.name: f.read_bytes() for f in target.iterdir()} == first

    with pytest.raises(Exception, match="lesson_"):
        call_command("build_course_index", "g7-s2", **common)  # لا lessons تحت المصدر


def test_builder_maps_the_guide_page_of_an_example_to_its_printed_page():
    """صفحة المثال المطبوعة من صفحة ملف الدليل عبر جدول الصفحات؛ الغائب من الجدول أو بلا صفحة يبقى None ولا يُخمَّن."""
    record = lesson_output(
        examples=[
            {"n": 1, "page_pdf": field(28)},
            {"n": 2, "page_pdf": field(99)},
            {"n": 3},
        ]
    )
    pages = [e["page"] for e in build_lesson_index(record, 10, {28: 5})["examples"]]
    assert pages == [5, None, None]
    assert [e["page"] for e in build_lesson_index(record, 10)["examples"]] == [None, None, None]
    with pytest.raises(ValidationError):
        LessonIndex(**(build_lesson_index(record, 10) | {"examples": [{"n": 1, "page": 0}]}))


def test_committed_index_knows_the_printed_page_of_every_example():
    """كل أمثلة العاشر بصفحاتها المطبوعة في كتاب الطالب، متزايدة داخل الدرس، وصفحتان قُرئتا من الكتاب نفسه."""
    lessons = {
        row.lesson: row
        for row in CourseIndex(**json.loads(GRADE10_INDEX.read_text(encoding="utf-8"))).lessons
    }
    for code, lesson in lessons.items():
        pages = [e.page for e in lesson.examples]
        assert all(pages), code
        assert pages == sorted(pages), code
    assert lessons["1.1"].examples[0].page == 5
    assert lessons["3.5"].examples[3].page == 161


def test_index_command_reads_the_printed_pages_table(tmp_path):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    folder = tmp_path / "lessons"
    folder.mkdir()
    record = lesson_output(examples=[{"n": 1, "page_pdf": field(28)}, {"n": 2, "page_pdf": field(29)}])
    (folder / "lesson_2_1.json").write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "printed_pages.json").write_text(json.dumps({"28": 5, "29": 6}), encoding="utf-8")
    courses = tmp_path / "courses"
    meta = {"title": "مقرر تجريبي", "grade": 10, "semester": 2, "academic_year": "2026-2027"}
    call_command("build_course_index", "g7-s2", source=str(tmp_path), courses_dir=str(courses), **meta)
    written = json.loads((courses / "g7-s2" / INDEX).read_text(encoding="utf-8"))
    assert [e["page"] for e in written["lessons"][0]["examples"]] == [5, 6]
    (tmp_path / "printed_pages.json").write_text(json.dumps({"28": "ص"}), encoding="utf-8")
    with pytest.raises(CommandError, match="غير صالح"):
        call_command("build_course_index", "g7-s2", source=str(tmp_path), courses_dir=str(courses))


def test_our_lessons_count_their_representations_from_the_description():
    assert representations_in("جبري وجدولي وبياني (الشكلان 3.2.10 و3.2.11)") == ["جدول", "بياني", "جبري"]
    assert representations_in("تطبيقي/هندسي") == ["سياق"]
    assert representations_in("جبري مع خط أعداد ورسم (الشكل 3.1.3)") == ["بياني", "جبري"]
    assert representations_in("عددي") == []
    kept = ExampleData(number=1, representation="جبري", representations=["جدول"])
    assert kept.representations == ["جدول"]  # المعدود صراحة يُقدَّم على الوصف


@pytest.mark.usefixtures("loaded_courses")
def test_grade12_index_comes_from_our_lessons():
    lessons = course_index(GRADE12_SLUG).lessons
    examples = [e for lesson in lessons for e in lesson.examples]
    assert len(lessons) == 19 and len(examples) == 93
    assert all(e.page for e in examples)
    assert sum(1 for e in examples if e.representations) == 65  # 28 مثالًا بلا وصف تمثيل في صياغتنا
