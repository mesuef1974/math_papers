"""باقة الحصة (المرحلة 1): حصص الوحدة 1 من العاشر تجتاز B1 إلى B5، والمركِّب حتمي ويحجب الربط غير المعتمد."""

from dataclasses import replace

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.models import BookExerciseLink
from apps.planning import selectors
from apps.planning.domain.check_items import period_items
from apps.planning.domain.lesson_package import (
    BASIC,
    CLASSWORK,
    EXIT,
    BookEntry,
    GeneratedEntry,
    compose_package,
    package_problems,
)


@pytest.fixture
def unit_one(loaded_courses):
    return [p for p in selectors.lesson_preps(GRADE10_SLUG) if p.prep.unit == 1]


def _package(period, periods, blocked=None):
    lesson = [p for p in periods if p.prep.lesson == period.prep.lesson]
    if blocked is None:
        return selectors.period_package(period, lesson)
    objectives = {o.example: o.behavior for p in lesson for o in p.prep.objectives}
    return compose_package(period.prep, period_items(period.prep), objectives=objectives, blocked=blocked)


def _numbers(package):
    return {e.number for s in package.sheets for e in s.entries if isinstance(e, BookEntry)}


@pytest.mark.django_db
def test_every_period_of_unit_one_passes_the_blocking_criteria(unit_one):
    assert unit_one
    for period in unit_one:
        package = _package(period, unit_one)
        blocked = selectors.blocked_exercises(GRADE10_SLUG, period.prep.lesson)
        problems = package_problems(period.prep, period_items(period.prep), package, blocked)
        assert not any(problems.values()), (period.prep.lesson, period.prep.k, problems)


@pytest.mark.django_db
def test_package_is_deterministic_and_never_repeats_a_problem(unit_one):
    for period in unit_one:
        package = _package(period, unit_one)
        assert package == _package(period, unit_one)
        prints = [
            e.problem.fingerprint for s in package.sheets for e in s.entries if isinstance(e, GeneratedEntry)
        ]
        assert len(prints) == len(set(prints))
        if period_items(period.prep).exit:
            assert package.sheet(EXIT).per_page == 4
        elif period.prep.exit_ticket:
            assert any(n.code == "text_question" for n in package.notes)


@pytest.mark.django_db
def test_unreviewed_links_are_replaced_by_generated_problems(unit_one):
    period = unit_one[0]
    numbers = {x for c in period.prep.classwork for x in c.exercises}
    assert numbers <= _numbers(_package(period, unit_one))
    BookExerciseLink.objects.filter(
        lesson__course__slug=GRADE10_SLUG, lesson__code=period.prep.lesson, number__in=numbers
    ).update(provenance=BookExerciseLink.Provenance.AI_UNREVIEWED, reviewed_at=None)
    package = _package(period, unit_one)
    assert not numbers & _numbers(package)
    assert any(isinstance(e, GeneratedEntry) for e in package.sheet(CLASSWORK).entries)
    assert any(n.code == "blocked" for n in package.notes)


@pytest.mark.django_db
def test_the_criteria_fail_on_a_broken_package(unit_one):
    period = next(p for p in unit_one if period_items(p.prep).exit and p.prep.basic)
    items = period_items(period.prep)
    package = _package(period, unit_one)
    broken = replace(
        package,
        sheets=tuple(replace(s, objectives=()) for s in package.sheets if s.kind not in (EXIT, BASIC)),
    )
    found = package_problems(period.prep, items, broken, _numbers(package))
    assert found["B1"] and found["B3"] and found["B4"] and found["B5"]
    sheet = package.sheet(CLASSWORK)
    entry = _package(period, unit_one, blocked=_numbers(package)).sheet(CLASSWORK).entries[0]
    empty = replace(entry, problem=replace(entry.problem, answer="", wrong_kinds=()))
    broken = replace(package, sheets=(replace(sheet, entries=(empty,)),))
    assert package_problems(period.prep, items, broken)["B2"]
