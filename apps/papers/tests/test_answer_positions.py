"""مواضع الإجابة الصحيحة: متوازنة على الرموز وبلا تتابع طويل، حتمية، ولا تغيّر المسائل."""

import copy
import random
from collections import Counter

import pytest

from apps.papers import services
from apps.papers.domain.answer_positions import MAX_RUN, balanced_positions, longest_run

G12 = "g12-sci-s1-2026-27-forecast"
G10 = "g10-s1-2026-27-final"
LABELS = services.OPTION_LABELS


def objective(paper: dict) -> list[dict]:
    return [part for q in paper["questions"] for part in q["parts"] if part["answer_index"] >= 0]


def assert_balanced(positions: list[int], width: int = 4) -> None:
    counts = Counter(positions)
    assert max(counts.values()) - min(counts.get(i, 0) for i in range(width)) <= 1, counts
    assert longest_run(positions) <= MAX_RUN, positions


def test_longest_run():
    assert longest_run([]) == 0
    assert longest_run([1, 1, 2, 2, 2, 0]) == 3
    assert longest_run([0, 1, 0, 1]) == 1


@pytest.mark.parametrize("width", [2, 3, 4, 5])
def test_positions_are_balanced_for_every_count(width):
    for count in range(0, 41):
        for seed in range(5):
            positions = balanced_positions(count, width, random.Random(seed))
            assert len(positions) == count and all(0 <= p < width for p in positions)
            if count:
                assert_balanced(positions, width)


def test_positions_are_deterministic_and_vary_with_the_seed():
    first = balanced_positions(20, 4, random.Random("x"))
    assert first == balanced_positions(20, 4, random.Random("x"))
    assert len({tuple(balanced_positions(20, 4, random.Random(seed))) for seed in range(20)}) > 15


def test_single_option_has_one_position():
    assert balanced_positions(5, 1, random.Random(0)) == [0] * 5


@pytest.mark.django_db
@pytest.mark.parametrize("slug", [G12, G10])
@pytest.mark.parametrize("form", ["A", "B"])
@pytest.mark.usefixtures("loaded_courses")
def test_exam_answers_are_balanced(slug, form):
    for seed in range(12):
        paper = services.build_exam(slug, seed, form)
        parts = objective(paper)
        assert len(parts) >= 4
        assert_balanced([part["answer_index"] for part in parts])
        for part in parts:
            if part["option_graphs"]:
                assert part["answer"] == f"الخيار ({LABELS[part['answer_index']]})"
            else:
                assert part["options"][part["answer_index"]] == part["answer"]
        assert paper == services.build_exam(slug, seed, form)


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_forms_do_not_share_the_answer_pattern():
    """ب ليس نسخة من مفتاح أ: مولّد مواضعه غير مولّد أ."""
    different = 0
    for seed in range(10):
        a = [p["answer_index"] for p in objective(services.build_exam(G10, seed, "A"))]
        b = [p["answer_index"] for p in objective(services.build_exam(G10, seed, "B"))]
        different += a != b
    assert different >= 9


@pytest.mark.django_db
def test_quiz_answers_are_balanced():
    for code in sorted(services.available_lessons())[:6]:
        for form in ("A", "B"):
            parts = objective(services.build_quiz([code], 11, form))
            assert sorted(part["answer_index"] for part in parts) == [0, 1, 2, 3]


@pytest.mark.django_db
@pytest.mark.parametrize("slug", [G12, G10])
@pytest.mark.usefixtures("loaded_courses")
def test_balancing_moves_only_the_correct_option(slug, monkeypatch):
    """بلا التوزيع تخرج المسائل نفسها بالمشتتات نفسها وترتيبها: الفرق موضع الصحيح وحده."""
    balanced = {form: services.build_exam(slug, 5, form) for form in ("A", "B")}
    monkeypatch.setattr(services, "balance_answers", lambda questions, rng: None)
    for form, paper in balanced.items():
        raw = services.build_exam(slug, 5, form)
        moved = 0
        for after, before in zip(
            (p for q in paper["questions"] for p in q["parts"]),
            (p for q in raw["questions"] for p in q["parts"]),
            strict=True,
        ):
            after, before = copy.deepcopy(after), copy.deepcopy(before)
            moved += after["answer_index"] != before["answer_index"]
            for part in (after, before):
                if part["answer_index"] >= 0:
                    for key in ("options", "option_graphs"):
                        if part[key]:
                            part[key].pop(part["answer_index"])
                    if part["option_graphs"]:
                        part["answer"] = ""
                    part["answer_index"] = 0
            assert after == before
        assert moved > 0
        assert {k: v for k, v in paper.items() if k != "questions"} == {
            k: v for k, v in raw.items() if k != "questions"
        }


def test_parts_with_another_option_count_are_left_alone():
    part = {"answer_index": 1, "options": ["خطأ", "صح"], "option_graphs": [], "answer": "صح"}
    essay = {"answer_index": -1, "options": [], "option_graphs": [], "answer": "5"}
    questions = [{"parts": [copy.deepcopy(part), copy.deepcopy(essay)]}]
    services.balance_answers(questions, random.Random(0))
    assert questions == [{"parts": [part, essay]}]


def test_graph_options_move_with_their_label():
    graphs = [{"id": i} for i in range(4)]
    parts = [
        {"answer_index": 0, "options": [""] * 4, "option_graphs": list(graphs), "answer": "الخيار (A)"}
        for _ in range(8)
    ]
    services.balance_answers([{"parts": parts}], random.Random(3))
    assert_balanced([part["answer_index"] for part in parts])
    for part in parts:
        index = part["answer_index"]
        assert part["option_graphs"][index] == {"id": 0}
        assert [g["id"] for i, g in enumerate(part["option_graphs"]) if i != index] == [1, 2, 3]
        assert part["answer"] == f"الخيار ({LABELS[index]})"
