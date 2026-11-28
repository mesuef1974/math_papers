"""أرقام الصفحات مع كل مثال وتمرين (قرار المالك 2026-11-27). حارسان: لا نص يشير إلى مثال أو تمرين بعينه خارج
`book_ref` / `bookRef`، وبيانات المقررين فيها صفحة كل مثال وصفحات التمارين."""

import re
from pathlib import Path

import pytest

from apps.knowledge.domain.exercise_pages import page_map
from apps.knowledge.selectors import course_index_from_tables
from apps.papers.domain.book_source import book_ref

ROOT = Path(__file__).resolve().parents[3]
BARE = re.compile(r"(مثال|المثال|تمرين|التمرين) (\{|\$\{)")
# رسائل التشخيص للمطوّر (أخطاء ومعايير) ليست مادة يقرؤها المعلم أو الطالب في الصف
DIAGNOSTIC = ("Error(", "problems.append", 'found["B')
SHOWN = ("deck.py", "prep_sheet.py", "lesson_package.py")


def test_book_ref():
    assert book_ref("مثال", 3, 12) == "مثال 3 (ص 12)"
    assert book_ref("التمرين", 4, None) == "التمرين 4"


def test_no_reference_is_written_outside_the_shared_formatter():
    paths = [ROOT / "apps/planning/domain" / name for name in SHOWN]
    paths += [
        p
        for p in (ROOT / "frontend/src").rglob("*")
        if p.suffix in {".vue", ".ts"} and not p.name.endswith(("bookRef.ts", ".test.ts"))
    ]
    found = [
        f"{path.name}:{number}: {line.strip()}"
        for path in paths
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if BARE.search(line) and not any(mark in line for mark in DIAGNOSTIC)
    ]
    assert not found, found


# تمارين على حدّ صفحتين لم يقرأ التعرّف رقمها: لا تُخمَّن صفحتها. السقف لا يرتفع (ينخفض بتصحيحها)
MAX_UNPAGED = {"g10-s1": 9, "g12-sci-s1": 35}


@pytest.mark.django_db
@pytest.mark.parametrize("course", sorted(MAX_UNPAGED))
def test_course_data_carries_pages(loaded_courses, course):
    lessons = course_index_from_tables(course).lessons
    assert all(e.page for lesson in lessons for e in lesson.examples)
    unpaged = {}
    for lesson in lessons:
        pages = page_map(lesson.exercise_pages)
        assert pages, lesson.lesson
        gaps = sorted(set(range(1, max(pages) + 1)) - set(pages))
        if gaps:
            unpaged[lesson.lesson] = gaps
    assert sum(map(len, unpaged.values())) <= MAX_UNPAGED[course], unpaged
