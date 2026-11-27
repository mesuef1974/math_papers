"""المعايير والأهداف بالمثال: ملف الوحدة المعتمد → `ExampleObjective` و`ExampleStandard`."""

import pytest

from apps.knowledge.domain.contract import CourseKnowledge, read_source
from apps.knowledge.models import ExampleObjective, ExampleStandard, LessonProfile
from apps.knowledge.services import load_course

COURSE = "g10-s1"


def _rows(model, *fields):
    return list(model.objects.filter(lesson__course__slug=COURSE, lesson__unit=1).values_list(*fields))


@pytest.mark.django_db
def test_every_core_example_of_unit_one_has_an_objective_and_a_standard(loaded_courses):
    objectives = set(_rows(ExampleObjective, "lesson__code", "example"))
    links = _rows(ExampleStandard, "lesson__code", "example", "standard__code")
    assert len(objectives) == 14
    assert {(code, n) for code, n, _ in links} == objectives
    assert sorted(s for code, n, s in links if (code, n) == ("1.3", 4)) == ["10.3.1", "10.3.2"]
    for code, _, standard in links:
        profile = LessonProfile.objects.get(lesson__course__slug=COURSE, lesson__code=code)
        assert profile.standards.filter(code=standard).exists()


@pytest.mark.django_db
def test_loading_twice_keeps_the_same_rows(loaded_courses):
    before = _rows(ExampleObjective, "pk"), _rows(ExampleStandard, "pk")
    report = load_course(COURSE)
    assert report.changed["example_objectives"] == report.changed["example_standards"] == 0
    assert (_rows(ExampleObjective, "pk"), _rows(ExampleStandard, "pk")) == before


def test_contract_refuses_a_target_outside_its_lesson():
    raw = read_source(COURSE).model_dump(mode="json")
    for change in ({"standards": ["10.9.9"]}, {"example": 39}):
        bad = {**raw, "targets": [{**raw["targets"][0], **change}]}
        with pytest.raises(ValueError, match="هدف المثال"):
            CourseKnowledge.model_validate(bad)
