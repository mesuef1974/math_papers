"""وسم المشتتات بنوع الخطأ: كل صيغة موسومة (العاشر 1.1-1.3، والثاني عشر 1.1-1.4 في generators.py) تعطي أنواعًا توازي مشتتاتها."""

import random

import pytest

from apps.curriculum.courses import DEFAULT_COURSE, GRADE10_SLUG
from apps.papers.domain import generators
from apps.papers.domain.generators import ERROR_KINDS, REGISTRY, Problem, tagged_wrongs

TAGGED_LESSONS = ("1.1", "1.2", "1.3")
SEEDS = range(40)
G12_TAGGED_LESSONS = ("1.1", "1.2", "1.3", "1.4")
TAGGED = [
    pytest.param(fn, id=f"{lesson}-{fn.__name__}")
    for lesson in TAGGED_LESSONS
    for fn in REGISTRY[(GRADE10_SLUG, lesson)]
] + [
    pytest.param(fn, id=f"g12-{lesson}-{fn.__name__}")
    for lesson in G12_TAGGED_LESSONS
    for fn in REGISTRY[(DEFAULT_COURSE, lesson)]
    if fn.__module__ == generators.__name__  # صيغ الرسوم والمستويات في وحداتها لم تُوسَم بعد
]


def test_every_tagged_lesson_has_variants():
    assert len(TAGGED) >= 19 + 18


@pytest.mark.parametrize("fn", TAGGED)
def test_variant_tags_every_distractor(fn):
    for seed in SEEDS:
        problem = fn(random.Random(seed))
        assert len(problem.wrong_kinds) == len(problem.wrong) == 3, (seed, problem.wrong, problem.wrong_kinds)
        assert set(problem.wrong_kinds) <= ERROR_KINDS.keys(), (seed, problem.wrong_kinds)


def test_tagged_wrongs_keeps_kind_with_its_text_after_dedup():
    texts, kinds = tagged_wrongs("A", ("sign", "A"), ("sign", "B"), ("swap", "C"), ("formula", "D"))
    assert texts == ("B", "C", "D")
    assert kinds == ("sign", "swap", "formula")


def test_tagged_wrongs_pads_numeric_answer_as_nearby():
    texts, kinds = tagged_wrongs(3, ("sign", -3))
    assert len(texts) == 3
    assert kinds[0] == "sign"
    assert set(kinds[1:]) == {"nearby"}


def test_problem_rejects_misaligned_or_unknown_kinds():
    base = ("1.1", "s", "a", ("b", "c", "d"), ("x",), "K")
    with pytest.raises(ValueError):
        Problem(*base, wrong_kinds=("sign",))
    with pytest.raises(ValueError):
        Problem(*base, wrong_kinds=("sign", "sign", "bogus"))
    assert Problem(*base, wrong_kinds=("sign", "swap", "formula")).wrong_kinds == ("sign", "swap", "formula")
