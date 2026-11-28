"""بنك الأسئلة التشخيصية: بند واحد صحيح، مشتتات موسومة ومختلفة، حتمية بالبذرة، وتوازن المواضع والاسترجاع المتناوب."""

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers.domain import item_bank
from apps.papers.domain.answer_positions import longest_run
from apps.papers.domain.generators import ERROR_KINDS, REGISTRY
from apps.papers.domain.item_bank import (
    OPTION_COUNT,
    ItemBankError,
    bank,
    exit_ticket,
    retrieval,
    usable,
)

COURSE = GRADE10_SLUG
LESSONS = ("1.1", "1.2", "1.3")


@pytest.mark.parametrize("lesson", LESSONS)
def test_every_item_has_one_correct_and_tagged_distractors(lesson):
    for item in bank(COURSE, lesson, per_variant=3, seed=1):
        assert len(item.options) == OPTION_COUNT
        assert sum(option.correct for option in item.options) == 1
        assert len({option.text for option in item.options}) == OPTION_COUNT
        for index, option in enumerate(item.options):
            if option.correct:
                assert item.diagnose(index) is None
            else:
                assert option.kind in ERROR_KINDS
                assert item.diagnose(index) == ERROR_KINDS[option.kind]


@pytest.mark.parametrize("lesson", LESSONS)
def test_bank_covers_every_objective_variant(lesson):
    names = {item.variant for item in bank(COURSE, lesson, per_variant=2, seed=0)}
    expected = {fn.__name__ for fn in REGISTRY[(COURSE, lesson)] if usable(fn)}
    assert names == expected


@pytest.mark.parametrize("lesson", LESSONS)
def test_bank_items_are_distinct_and_balanced(lesson):
    items = bank(COURSE, lesson, per_variant=3, seed=2)
    assert len({item.fingerprint for item in items}) == len(items)
    positions = [item.answer_index for item in items]
    assert longest_run(positions) <= 2
    counts = [positions.count(p) for p in range(OPTION_COUNT)]
    assert max(counts) - min(counts) <= 1


def test_bank_is_deterministic_by_seed():
    first = bank(COURSE, "1.1", seed=5)
    assert first == bank(COURSE, "1.1", seed=5)
    assert first != bank(COURSE, "1.1", seed=6)


def test_exit_ticket_measures_the_requested_example():
    item = exit_ticket(COURSE, "1.1", 2, seed=3)
    assert item.example == 2
    assert item.lesson == "1.1"
    assert sum(option.correct for option in item.options) == 1


def test_exit_ticket_unknown_example_raises():
    with pytest.raises(ItemBankError):
        exit_ticket(COURSE, "1.1", 99)


def test_retrieval_interleaves_earlier_lessons_without_consecutive_repeats():
    items = retrieval(COURSE, ["1.1", "1.2"], count=4, seed=4)
    assert [item.lesson for item in items] == ["1.1", "1.2", "1.1", "1.2"]
    assert len({item.fingerprint for item in items}) == 4
    assert all(sum(option.correct for option in item.options) == 1 for item in items)


def test_retrieval_cycles_variants_before_repeating():
    items = retrieval(COURSE, ["1.1"], count=3, seed=0)
    assert len({item.variant for item in items}) == 3


def test_retrieval_without_earlier_lessons_raises():
    with pytest.raises(ItemBankError):
        retrieval(COURSE, [], count=2)


def test_exit_ticket_variant_differs_and_default_is_unchanged():
    """التقييم البنائي (variant=1) من صيغة غير صيغة بطاقة الخروج، والافتراضي يبقى الأولى (النتائج المحفوظة)."""
    course, lesson, example = "g10-s1", "1.1", 2
    default = item_bank.exit_ticket(course, lesson, example, seed=5)
    other = item_bank.exit_ticket(course, lesson, example, seed=5, variant=1)
    assert default == item_bank.exit_ticket(course, lesson, example, seed=5, variant=0)
    assert other.variant != default.variant
    assert item_bank.exit_ticket(course, lesson, example, seed=5, variant=2) == default
