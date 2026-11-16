"""توزيع الدرجات: مجموع البنود يساوي درجة الفرع لكل مولّد ولكل درجة، بلا بند صفري ولا خطوة ضائعة."""

import random

import pytest

from apps.papers.domain.generators import REGISTRY
from apps.papers.domain.marking import allocate, marking

ALL = [(lesson, fn) for (_, lesson), fns in REGISTRY.items() for fn in fns]
IDS = [fn.__name__ for _, fn in ALL]
SEEDS = range(40)
MARKS = range(1, 7)


def assert_sound(steps, marks):
    items = allocate(steps, marks)
    assert sum(item.halves for item in items) == marks * 2
    assert all(item.halves >= 1 for item in items)
    assert items[-1].final and not items[-1].steps
    assert all(not item.final and item.steps for item in items[:-1])
    # الخطوات كلها حاضرة بترتيبها، دُمجت أم لم تُدمج
    assert [step for item in items for step in item.steps] == list(steps)
    return items


@pytest.mark.parametrize(("lesson", "generator"), ALL, ids=IDS)
def test_step_marks_sum_to_part_marks(lesson, generator):
    for seed in SEEDS:
        problem = generator(random.Random(seed))
        for marks in MARKS:
            assert_sound(problem.steps, marks)


@pytest.mark.parametrize("count", range(0, 9))
@pytest.mark.parametrize("marks", MARKS)
def test_any_step_count_is_sound(count, marks):
    assert_sound([f"خطوة {n}" for n in range(count)], marks)


def test_final_answer_carries_its_own_mark():
    assert [item.marks for item in allocate(["أ", "ب"], 3)] == [1, 1, 1]
    # فرع الدرجة الواحدة: نصف للطريقة ونصف للجواب
    assert [item.marks for item in allocate(["أ"], 1)] == [0.5, 0.5]
    # بلا خطوات: الدرجة كلها للجواب
    assert [(item.marks, item.final) for item in allocate([], 2)] == [(2, True)]


def test_remainder_goes_to_last_steps():
    assert [item.marks for item in allocate(["أ", "ب", "ج"], 3)] == [0.5, 0.5, 1, 1]


def test_adjacent_steps_merge_when_more_than_method_halves():
    items = allocate(["أ", "ب", "ج", "د", "هـ"], 2)
    assert [item.steps for item in items] == [("أ", "ب", "ج"), ("د", "هـ"), ()]
    assert [item.marks for item in items] == [0.5, 0.5, 1]


def test_no_allocation_without_marks_or_for_mcq():
    assert allocate(["أ"], 0) == ()
    assert marking("essay", ["أ"], 0) == []
    assert marking("mcq", ["أ"], 1) == []
    assert marking("essay", ["أ"], 2) == [
        {"steps": ["أ"], "marks": 1.0, "final": False},
        {"steps": [], "marks": 1.0, "final": True},
    ]


SLUG = "g12-sci-s1-2026-27-forecast"


@pytest.mark.django_db
def test_exam_marking_reaches_the_api_for_essay_parts_only(client):
    paper = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 11}).json()
    kinds = set()
    for question in paper["questions"]:
        for part in question["parts"]:
            kinds.add(question["kind"])
            if question["kind"] == "mcq":
                assert part["marking"] == []
                continue
            assert sum(item["marks"] for item in part["marking"]) == part["marks"]
            assert part["marking"][-1]["final"]
            assert [s for item in part["marking"] for s in item["steps"]] == part["steps"]
    assert kinds == {"mcq", "essay"}


@pytest.mark.django_db
def test_worksheet_without_marks_has_no_marking(client):
    paper = client.get("/api/v1/papers/worksheet", {"lesson": "3.1", "count": 4, "seed": 5}).json()
    assert all(part["marking"] == [] for q in paper["questions"] for part in q["parts"])


@pytest.mark.django_db
def test_marking_is_derived_never_taken_from_the_client(client):
    """ورقة محفوظة قبل وجود التوزيع تناله، وتوزيع مزوَّر من العميل يُستبدل بالمحسوب."""
    from apps.papers.api import PartOut

    paper = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 11}).json()
    part = next(p for q in paper["questions"] if q["kind"] == "essay" for p in q["parts"])
    expected = part["marking"]
    old = {key: value for key, value in part.items() if key != "marking"}
    forged = {**part, "marking": [{"steps": [], "marks": 99, "final": True}]}
    for payload in (old, forged):
        assert PartOut.model_validate(payload).model_dump()["marking"] == expected
