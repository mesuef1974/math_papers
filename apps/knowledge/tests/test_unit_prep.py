"""ملفات التحضير المؤلَّفة (`prep/unit-<n>.json` و`standards.json`): مخطط صارم، ومطابقة للفهرس، واعتماد المالك.

كل ملف وحدة في كل مقرر يجتاز المخطط ويطابق فهرسه: هدف لكل مثال غير إثرائي بعمق أعلى صف في تحليله، وفعل من جدول عمقه،
ووصف لكل معيار في دروسه. وصف المعيار لا يظهر قبل اعتماد وحدته.
"""

import json
import shutil

import pytest
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.unit_prep import (
    UnitPrep,
    approved_standards,
    course_standards,
    unit_files,
    unit_prep,
    unit_problems,
)
from apps.knowledge.selectors import course_index
from apps.planning.domain.prep import REJECTED_VERBS, VERBS_BY_DOK

UNIT_1 = COURSES_DIR / GRADE10_SLUG / "prep" / "unit-1.json"


def _raw() -> dict:
    return json.loads(UNIT_1.read_text(encoding="utf-8"))


@pytest.mark.django_db
def test_every_unit_file_matches_its_course_index(loaded_courses):
    courses = [p.name for p in COURSES_DIR.iterdir() if unit_files(p.name)]
    assert GRADE10_SLUG in courses
    for course in courses:
        plan_file = COURSES_DIR / course / "term_plan.json"
        plan = json.loads(plan_file.read_text(encoding="utf-8")) if plan_file.is_file() else {}
        lessons = course_index(course).lessons
        for unit in unit_files(course):
            data = unit_prep(course, unit)
            assert data is not None
            assert (
                unit_problems(
                    data,
                    lessons,
                    plan.get("enrichment_lessons", ()),
                    plan.get("enrichment_examples", {}),
                    course_standards(course),
                )
                == []
            ), (course, unit)
            for entry in data.lessons:
                for o in entry.objectives:
                    assert o.verb in VERBS_BY_DOK[o.dok], (entry.lesson, o.example)
                    assert not set(o.behavior.split()) & REJECTED_VERBS, (entry.lesson, o.example)


def test_unit_one_of_grade_ten_is_approved_with_fourteen_objectives():
    data = unit_prep(GRADE10_SLUG, 1)
    assert data.status == "approved" and data.approval.endswith("2026-11-27")
    assert [entry.lesson for entry in data.lessons] == ["1.1", "1.2", "1.3"]  # 1.4 إثرائي
    assert sum(len(entry.objectives) for entry in data.lessons) == 14


def test_schema_refuses_free_fields_missing_approval_and_verb_mismatch():
    raw = _raw()
    UnitPrep.model_validate(raw)
    with pytest.raises(ValidationError):
        UnitPrep.model_validate({**raw, "notes": "نص حر"})
    with pytest.raises(ValidationError):
        UnitPrep.model_validate({**raw, "approval": None})
    with pytest.raises(ValidationError):
        UnitPrep.model_validate({**raw, "status": "draft"})  # مسودة بسطر اعتماد
    bad = json.loads(json.dumps(raw))
    bad["lessons"][0]["objectives"][0]["verb"] = "يحسب"
    with pytest.raises(ValidationError, match="لا يبدأ بفعله"):
        UnitPrep.model_validate(bad)
    bad = json.loads(json.dumps(raw))
    bad["lessons"][0]["objectives"][0]["condition"] = ""
    with pytest.raises(ValidationError):
        UnitPrep.model_validate(bad)


@pytest.mark.django_db
def test_problems_catch_missing_example_wrong_depth_and_enrichment(loaded_courses):
    lessons = course_index(GRADE10_SLUG).lessons
    standards = course_standards(GRADE10_SLUG)
    raw = _raw()
    raw["lessons"][0]["objectives"].pop()  # 1.1 بلا هدف المثال 5
    raw["lessons"][1]["objectives"][0]["dok"] = 2
    raw["lessons"].append({"lesson": "1.4", "objectives": raw["lessons"][0]["objectives"][:1]})
    problems = unit_problems(UnitPrep.model_validate(raw), lessons, ["1.4"], {}, standards)
    assert any("الدرس 1.1" in p and "[1, 2, 3, 4]" in p for p in problems)
    assert any("1.2 مثال 1" in p for p in problems)
    assert "درس ليس في الوحدة أو إثرائي: 1.4" in problems
    assert any(
        "معيار بلا وصف" in p
        for p in unit_problems(UnitPrep.model_validate(_raw()), lessons, ["1.4"], {}, None)
    )


def test_standard_texts_appear_only_after_their_unit_is_approved(tmp_path):
    root = tmp_path / "courses"
    shutil.copytree(COURSES_DIR / GRADE10_SLUG, root / GRADE10_SLUG)
    unit_one = {"10.3.1", "10.3.2", "10.3.3"}
    every = set(course_standards(GRADE10_SLUG, root).standards)
    assert unit_one < every and set(approved_standards(GRADE10_SLUG, root)) == every
    draft = _raw() | {"status": "draft", "approval": None}
    (root / GRADE10_SLUG / "prep" / "unit-1.json").write_text(
        json.dumps(draft, ensure_ascii=False), encoding="utf-8"
    )
    unit_prep.cache_clear()
    course_standards.cache_clear()
    try:
        assert set(approved_standards(GRADE10_SLUG, root)) == every - unit_one
    finally:
        unit_prep.cache_clear()
        course_standards.cache_clear()


def test_missing_files_mean_no_unit_and_no_standards(tmp_path):
    assert unit_prep(GRADE10_SLUG, 9, tmp_path) is None
    assert course_standards(GRADE10_SLUG, tmp_path) is None
    assert unit_files(GRADE10_SLUG, tmp_path) == []
