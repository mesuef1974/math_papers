"""تدوير الدروس داخل المجموعة (`domain/rotation.py`): منطق نقي بلا قاعدة بيانات."""

import random

from apps.papers.domain.rotation import RotationSlot, rotate


def slot(question, index, group, lesson, kind="mcq", level="K"):
    return RotationSlot((question, index), group, lesson, kind, level, False)


def everything_fits(code, kind, level, graph):
    return True


def test_every_slot_moves_and_the_group_stays_covered():
    slots = [slot(1, 0, "g", "1.1"), slot(2, 0, "g", "1.2"), slot(3, 0, "g", "1.3")]
    for seed in range(20):
        chosen = rotate(slots, everything_fits, random.Random(seed))
        assert sorted(chosen.values()) == ["1.1", "1.2", "1.3"]
        assert all(chosen[s.key] != s.lesson for s in slots)


def test_a_slot_no_other_lesson_can_fill_keeps_its_lesson():
    """3.5 وحده يملك المستوى R: خانته تبقى عليه، والباقي يتبادل."""
    slots = [slot(9, 0, "3", "3.3"), slot(10, 0, "3", "3.4"), slot(18, 0, "3", "3.5", "essay", "R")]

    def fits(code, kind, level, graph):
        return level != "R" or code == "3.5"

    chosen = rotate(slots, fits, random.Random(1))
    assert chosen == {(9, 0): "3.4", (10, 0): "3.3", (18, 0): "3.5"}


def test_parts_of_one_question_take_different_lessons():
    slots = [slot(1, 0, "g", "1.1"), slot(11, 0, "g", "1.3", "essay"), slot(11, 1, "g", "1.2", "essay")]
    for seed in range(20):
        chosen = rotate(slots, everything_fits, random.Random(seed))
        assert chosen[(11, 0)] != chosen[(11, 1)]
        assert sorted(chosen.values()) == ["1.1", "1.2", "1.3"]


def test_groups_do_not_mix_and_ungrouped_slots_stay():
    slots = [slot(1, 0, "a", "1.1"), slot(2, 0, "a", "1.2"), slot(3, 0, "b", "2.1"), slot(4, 0, "", "3.1")]
    chosen = rotate(slots, everything_fits, random.Random(5))
    assert {chosen[(1, 0)], chosen[(2, 0)]} == {"1.1", "1.2"}
    assert chosen[(3, 0)] == "2.1" and chosen[(4, 0)] == "3.1"


def test_rotation_is_deterministic_from_the_seed():
    slots = [slot(n, 0, "g", f"1.{n}") for n in range(1, 6)]
    assert rotate(slots, everything_fits, random.Random(9)) == rotate(
        slots, everything_fits, random.Random(9)
    )
