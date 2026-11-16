"""سير حصة لكل درس من الـ19 بملفه الشخصي من الفهرس المشتق."""

import pytest

from apps.knowledge.domain.grade10_index import AnalysisRow, Grade10Lesson, VocabularyCount
from apps.planning.domain.strategies import PHASES, FlowError
from apps.planning.selectors import lesson_codes, lesson_flow, lesson_profile, profile_from_lesson


def _lesson(bloom, doks):
    return Grade10Lesson(
        lesson="1.1",
        unit=1,
        objectives_bloom=bloom,
        analysis=[AnalysisRow(example=i + 1, dok=d, exercises=[1]) for i, d in enumerate(doks)],
        exercises_total=1,
        vocabulary=VocabularyCount(new=0, review=0),
    )


def test_profile_drops_unclassified_and_collects_dok_from_analysis():
    profile = profile_from_lesson(_lesson(["unclassified", "تطبيق", "فهم"], [1, 3, 3]))
    assert profile.bloom == {"تطبيق", "فهم"}
    assert profile.dok == {1, 3}


def test_profile_of_a_lesson_with_nothing_read_is_empty_not_guessed():
    profile = profile_from_lesson(_lesson(["unclassified"], []))
    assert not profile.bloom and not profile.dok


def test_unknown_lesson_raises():
    with pytest.raises(KeyError):
        lesson_profile("9.9")


def test_index_has_the_nineteen_lessons():
    assert len(lesson_codes()) == 19


@pytest.mark.parametrize("code", lesson_codes())
def test_every_lesson_gets_a_flow_that_fills_the_period(code):
    flow = lesson_flow(code, 45)
    assert flow.total == 45
    assert [s.phase for s in flow.steps] == list(PHASES)


def test_double_period_without_resources_is_reported_not_trimmed():
    with pytest.raises(FlowError):
        lesson_flow("1.1", 90)


def test_lessons_with_different_profiles_get_different_flows():
    flows = {code: tuple(s.strategy.slug for s in lesson_flow(code, 60).steps) for code in lesson_codes()}
    assert len(set(flows.values())) > 1  # الملف الشخصي يؤثر فعلًا في الاختيار


def test_real_lesson_profiles_come_from_the_index():
    assert lesson_profile("2.6").dok == {1, 2}
    assert lesson_profile("3.5").dok == {2, 3, 4}
    assert lesson_profile("3.1").bloom == frozenset()  # كل أهدافه غير مصنَّفة: لا تخمين
    assert lesson_profile("1.4").bloom == {"تطبيق", "فهم"}
