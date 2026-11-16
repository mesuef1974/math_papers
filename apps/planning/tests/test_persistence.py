"""حفظ نتائج الصف وتقارير الحصص: idempotent، بقيود سلامة، والقرار مشتق من السجل."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.planning.domain.calendar_engine import PlanningError
from apps.planning.domain.feedback import ClassOutcome
from apps.planning.domain.lesson_run import advance, skip, start
from apps.planning.domain.strategies import PHASES, build_flow
from apps.planning.models import ClassOutcomeRecord, LessonRunRecord
from apps.planning.selectors import decision_of, outcome_of, outcome_records, run_reports
from apps.planning.services import record_outcome, save_run_report

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 11, 16, 7, 0, tzinfo=UTC)


@pytest.fixture
def teacher():
    return get_user_model().objects.create_user("t1", password="x")  # noqa: S106


@pytest.fixture
def other():
    return get_user_model().objects.create_user("t2", password="x")  # noqa: S106


def test_record_outcome_is_idempotent_per_section_and_lesson(teacher):
    _, created = record_outcome(teacher, "10/3", ClassOutcome("1.1", 30, 12))
    again, created_again = record_outcome(teacher, "10/3", ClassOutcome("1.1", 30, 12))
    assert created and not created_again
    assert ClassOutcomeRecord.objects.count() == 1 and again.correct == 12


def test_record_outcome_updates_the_latest_result_not_a_new_row(teacher):
    record_outcome(teacher, "10/3", ClassOutcome("1.1", 30, 12))
    record, _ = record_outcome(teacher, "10/3", ClassOutcome("1.1", 28, 25, pace="slow"))
    assert ClassOutcomeRecord.objects.count() == 1
    assert (record.attempted, record.correct, record.pace) == (28, 25, "slow")


def test_sections_and_lessons_are_kept_apart(teacher):
    record_outcome(teacher, "10/3", ClassOutcome("1.1", 30, 12))
    record_outcome(teacher, "10/4", ClassOutcome("1.1", 30, 27))
    record_outcome(teacher, "10/3", ClassOutcome("1.2", 30, 20))
    assert ClassOutcomeRecord.objects.count() == 3
    assert outcome_records(teacher, "10/3").count() == 2


def test_each_teacher_sees_only_their_own_records(teacher, other):
    record_outcome(teacher, "10/3", ClassOutcome("1.1", 30, 12))
    assert outcome_records(other).count() == 0 and outcome_records(teacher).count() == 1


@pytest.mark.parametrize("bad", ["", "   ", "x" * 21])
def test_section_is_required_and_bounded(teacher, bad):
    with pytest.raises(PlanningError):
        record_outcome(teacher, bad, ClassOutcome("1.1", 30, 12))


def test_database_rejects_counts_the_domain_would_have_rejected(teacher):
    with pytest.raises(IntegrityError), transaction.atomic():
        ClassOutcomeRecord.objects.create(
            owner=teacher, section="10/3", lesson_code="1.1", attempted=5, correct=6
        )


def test_decision_is_derived_from_the_record_with_current_thresholds(teacher):
    record, _ = record_outcome(
        teacher, "10/3", ClassOutcome("1.1", 30, 8, pace="slow", obstacles=frozenset({"time", "concept"}))
    )
    assert outcome_of(record) == ClassOutcome("1.1", 30, 8, "slow", frozenset({"concept", "time"}))
    decision = decision_of(record)
    assert (decision.action, decision.extra_periods) == ("reteach", 2)
    assert decision.notes == ("pace_slow", "obstacle_concept", "obstacle_time")


def test_run_report_stores_planned_versus_actual_and_is_idempotent(teacher):
    flow = build_flow(45)
    run = start(flow, 1000.0)
    run = advance(run, 1000.0 + flow.steps[0].minutes * 60)
    run = skip(run, 1000.0 + (flow.steps[0].minutes + 1) * 60)
    record, created = save_run_report(teacher, "10/3", "1.1", run, T0)
    again, created_again = save_run_report(teacher, "10/3", "1.1", run, T0)
    assert created and not created_again and LessonRunRecord.objects.count() == 1
    assert record.period_minutes == 45 and not again.finished
    assert [p["phase"] for p in again.phases] == list(PHASES[:2])
    assert again.phases[0] == {
        "phase": PHASES[0],
        "planned": flow.steps[0].minutes,
        "actual": float(flow.steps[0].minutes),
        "skipped": False,
    }
    assert again.phases[1]["skipped"] is True
    assert run_reports(teacher, "10/3").count() == 1 and run_reports(teacher, "10/9").count() == 0


def test_a_later_start_is_a_separate_report(teacher):
    run = start(build_flow(45), 1000.0)
    save_run_report(teacher, "10/3", "1.1", run, T0)
    save_run_report(teacher, "10/3", "1.1", run, T0.replace(day=17))
    assert LessonRunRecord.objects.count() == 2
