"""مكتبة الاستراتيجيات والمنتقي ومولّد سير الحصة: المكتبة صالحة، والاختيار حتمي، ومجموع الدقائق زمن الحصة تمامًا."""

import dataclasses
import json
import re

import pytest

from apps.planning.domain.calendar_engine import DATA_DIR, PlanningError
from apps.planning.domain.strategies import (
    PHASE_WEIGHTS,
    PHASES,
    FlowError,
    LessonProfile,
    Strategy,
    build_flow,
    load_library,
    select,
)

RAW_BOOK_REFS = re.compile(r"For Qatar|Savvas|ISBN|(?:ص|صفحة|الصفحة)\s*\.?\s*\d", re.IGNORECASE)


@pytest.fixture(scope="module")
def library():
    return load_library()


def test_phase_weights_cover_every_phase_and_sum_to_one():
    assert set(PHASE_WEIGHTS) == set(PHASES)
    assert sum(PHASE_WEIGHTS.values()) == pytest.approx(1.0)


def test_library_has_unique_slugs_and_a_resource_free_option_per_phase(library):
    assert len({s.slug for s in library}) == len(library)
    for phase in PHASES:
        assert any(s.phase == phase and not s.needs for s in library), phase


def test_library_text_has_no_book_references():
    raw = (DATA_DIR / "strategies.json").read_text(encoding="utf-8")
    assert not RAW_BOOK_REFS.search(raw)
    assert max(len(step) for r in json.loads(raw) for step in r["steps"]) < 200  # خطوات قصيرة بصياغتنا
    roles = [r[k] for r in json.loads(raw) for k in ("teacher_role", "student_role")]
    assert all(0 < len(role) < 120 for role in roles)  # دور كل طرف جملة قصيرة


def test_invalid_strategy_is_rejected(library):
    base = library[0]
    for change in (
        {"phase": "nope"},
        {"min": 9, "max": 3},
        {"bloom": ("x",)},
        {"dok": (7,)},
        {"needs": ("jet",)},
        {"steps": ()},
        {"teacher_role": " "},
        {"student_role": ""},
    ):
        with pytest.raises(PlanningError):
            Strategy(**{**dataclasses.asdict(base), **change})


def test_select_respects_resources_and_excludes(library):
    no_res = select(library, "explore", resources=())
    assert no_res and all(not s.needs for s in no_res)
    with_all = select(library, "explore", resources=("graph_paper", "devices"))
    assert {s.slug for s in with_all} > {s.slug for s in no_res}
    first = no_res[0].slug
    assert first not in {s.slug for s in select(library, "explore", exclude=[first])}


def test_select_prefers_matching_bloom_and_dok(library):
    higher = LessonProfile(frozenset({"تقويم", "إبداع"}), frozenset({4}))
    assert select(library, "practice", higher)[0].slug == "practice-extended-problem"
    basic = LessonProfile(frozenset({"تذكر"}), frozenset({1}))
    assert select(library, "check", basic)[0].slug in {"check-thumbs-signal", "check-mini-whiteboards"}


def test_select_ranks_by_dok_alone_and_by_bloom_alone(library):
    # الحالات مختارة بحيث يخالف الترتيب الأبجدي للمعرّفات الترتيب بالدرجة، فلا ينجح الاختبار بالتعادل وحده
    shallow = select(library, "practice", LessonProfile(dok=frozenset({1})))
    assert {s.slug for s in shallow[:2]} == {"practice-graded-independent", "practice-partner-roles"}
    assert all(1 not in s.dok for s in shallow[2:])
    applying = select(library, "check", LessonProfile(bloom=frozenset({"تطبيق"})))
    assert (
        applying[0].slug == "check-three-question-quiz"
    )  # check-thumbs-signal أسبق أبجديًا لكنه لا يخدم «تطبيق»


def test_select_is_deterministic(library):
    profile = LessonProfile(frozenset({"تطبيق"}), frozenset({2}))
    runs = [[s.slug for s in select(library, "practice", profile, ideal_minutes=11)] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


@pytest.mark.parametrize("period", range(35, 76))
def test_flow_minutes_equal_the_period_and_stay_within_each_strategys_range(period):
    flow = build_flow(period)
    assert flow.total == period
    assert [s.phase for s in flow.steps] == list(PHASES)
    for step in flow.steps:
        assert step.strategy.min <= step.minutes <= step.strategy.max
    starts = [s.start for s in flow.steps]
    assert starts[0] == 0 and starts == sorted(starts)
    assert starts[-1] + flow.steps[-1].minutes == period


def test_flow_uses_each_phases_strategy_once_and_follows_the_profile(library):
    higher = LessonProfile(frozenset({"تحليل", "تقويم"}), frozenset({3}))
    flow = build_flow(60, higher, library, resources=("graph_paper", "printed_sheets"))
    assert len({s.strategy.slug for s in flow.steps}) == len(PHASES)
    assert any(s.strategy.dok and 3 in s.strategy.dok for s in flow.steps)


def test_flow_never_uses_a_strategy_whose_resources_are_missing(library):
    flow = build_flow(50, library=library, resources=())
    assert all(not s.strategy.needs for s in flow.steps)


def test_flow_is_deterministic():
    profile = LessonProfile(frozenset({"تطبيق"}), frozenset({2}))
    a, b = build_flow(45, profile), build_flow(45, profile)
    assert a == b


def test_impossible_periods_raise_instead_of_guessing():
    with pytest.raises(FlowError):
        build_flow(15)
    with pytest.raises(FlowError):
        build_flow(120)


def test_missing_phase_strategy_raises(library):
    without_close = [s for s in library if s.phase != "close"]
    with pytest.raises(FlowError):
        build_flow(45, library=without_close)
