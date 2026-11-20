"""أرقام دليل الثاني عشر كما تبلغ الجداول: ما قُرئ بشاهد يُكتب، وما ليس في الدليل يبقى فارغًا ولا يُخمَّن.

دليل الثاني عشر (316 صفحة) ليس فيه «دليل المهام» ولا جدول «تحليل التمارين» ولا صفحة اختبار درس بأعماقها ولا بطاقة «بناء
المصطلحات» (مرحلة `lesson` على مجلد الكتاب في 2026-11-20: الحقول الأربعة `missing` في الدروس الـ19 كلها)، فدليل المهام وأعماق
الاختبار وعددا المصطلحات فارغة لكل درس، وسببها واحد: القسم غير موجود في الكتاب. عدد التمارين يُكتب حيث سندته سلسلة OCR المستقلة
وطابق آخر رقم في قوالب الدرس بصياغتنا وحده.
"""

import json

import pytest

from apps.knowledge.domain.book_numbers import template_max
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.selectors import course_index_from_tables

pytestmark = pytest.mark.django_db

COURSE = "g12-sci-s1"
ENRICHMENT = "3.6"
WITH_TOTAL = {"2.1", "3.1", "3.3", "3.4"}  # ما كتبه `write_book_numbers --guide-only` من سجلات الكتاب


def _files() -> dict[str, dict]:
    paths = sorted((COURSES_DIR / COURSE / "lessons").glob("lesson_*.json"))
    return {data["lesson"]: data for data in (json.loads(p.read_text(encoding="utf-8")) for p in paths)}


def test_exercise_totals_reach_the_tables_and_agree_with_templates(loaded_courses):
    files = _files()
    index = {lesson.lesson: lesson for lesson in course_index_from_tables(COURSE).lessons}
    assert index.keys() == files.keys() and len(index) == 19
    assert {code for code, lesson in index.items() if lesson.exercises_total} == WITH_TOTAL
    for code in WITH_TOTAL:
        assert index[code].exercises_total == files[code]["exercises_total"], code
        assert index[code].exercises_total == template_max(files[code]["templates"]), code


def test_fields_absent_from_the_guide_stay_empty(loaded_courses):
    """الدروس الـ18 القابلة للاختبار كلها بلا دليل مهام ولا أعماق اختبار: القسمان ليسا في دليل الثاني عشر، فلا يُختلقان."""
    index = {lesson.lesson: lesson for lesson in course_index_from_tables(COURSE).lessons}
    examinable = sorted(set(index) - {ENRICHMENT})
    assert len(examinable) == 18
    missing = [code for code in examinable if index[code].task_guide is None or not index[code].quiz_depths]
    assert missing == examinable
    assert all(v.vocabulary.new == v.vocabulary.review == 0 for v in index.values())
