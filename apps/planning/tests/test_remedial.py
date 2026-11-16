"""قرار ما بعد الحصة يولّد ورقة علاجية من مولّدات الدرس."""

import pytest

from apps.papers.services import UnknownLessonError
from apps.planning.domain.feedback import ClassOutcome, decide
from apps.planning.services import REMEDIAL_PER_PERIOD, remedial_worksheet


def _decision(correct, lesson="1.1"):
    return decide(ClassOutcome(lesson, 30, correct))


@pytest.mark.django_db
def test_mastered_class_gets_no_remedial_paper():
    assert remedial_worksheet(_decision(27)) is None


@pytest.mark.django_db
@pytest.mark.parametrize(("correct", "questions"), [(18, 1), (12, 1), (6, 2)])
def test_question_count_follows_the_decision_periods(correct, questions):
    # نامٍ (مراجعة سريعة) وتعثر عادي: خمسة أسئلة؛ تعثر شديد (حصتان): عشرة
    paper = remedial_worksheet(_decision(correct), seed=3)
    assert len(paper["questions"]) == questions * REMEDIAL_PER_PERIOD


@pytest.mark.django_db
def test_remedial_paper_is_easy_level_and_titled_remedial():
    paper = remedial_worksheet(_decision(12), seed=3)
    assert paper["kind"] == "worksheet" and paper["lesson_code"] == "1.1"
    assert paper["title"].startswith("ورقة علاجية")
    assert paper["level"] == "K"


@pytest.mark.django_db
def test_remedial_paper_is_deterministic_by_seed():
    assert remedial_worksheet(_decision(12), seed=7) == remedial_worksheet(_decision(12), seed=7)
    assert remedial_worksheet(_decision(12), seed=7) != remedial_worksheet(_decision(12), seed=8)


@pytest.mark.django_db
def test_unknown_lesson_raises():
    with pytest.raises(UnknownLessonError):
        remedial_worksheet(_decision(12, lesson="9.9"))
