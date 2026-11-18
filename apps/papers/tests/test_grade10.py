"""مولّدات العاشر: نطاق الاختبار (لا سؤال من درس أو مثال إثرائي)، وكفاية الصيغ لخانات الجدول ولأوراق العمل."""

import random

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import BlueprintItem
from apps.knowledge.selectors import course_index
from apps.knowledge.services import load_all
from apps.papers import services
from apps.papers.domain.generators import (
    REGISTRY,
    SKILL_EXAMPLES,
    available_lessons,
    generate,
    lesson_levels,
    out_of_scope,
    variants,
)
from apps.planning.domain.semester_plan import load_term_plan

FINAL = "g10-s1-2026-27-final"
UNIT_1 = {"1.1", "1.2", "1.3"}
UNIT_2A = {"2.1", "2.2", "2.3", "2.5", "2.6"}
UNIT_2B = {"2.7", "2.8", "2.9", "2.10"}
UNIT_3 = {"3.3", "3.4", "3.5"}
READY = UNIT_1 | UNIT_2A | UNIT_2B | UNIT_3
# خانات الوحدات 1 إلى 3 في جدول المواصفات بترتيب الورقة: (السؤال، الدرس، النوع، المستوى)
READY_SLOTS = [
    (1, "1.1", "mcq", "K"),
    (2, "1.2", "mcq", "A"),
    (3, "2.1", "mcq", "K"),
    (4, "2.2", "mcq", "K"),
    (5, "2.3", "mcq", "K"),
    (6, "2.5", "mcq", "A"),
    (7, "2.7", "mcq", "A"),
    (8, "2.9", "mcq", "K"),
    (9, "3.3", "mcq", "K"),
    (10, "3.4", "mcq", "K"),
    (11, "1.3", "essay", "K"),
    (11, "1.2", "essay", "K"),
    (12, "2.6", "essay", "A"),
    (13, "2.5", "essay", "A"),
    (14, "2.2", "essay", "K"),
    (15, "2.7", "essay", "K"),
    (16, "2.8", "essay", "A"),
    (17, "2.10", "essay", "A"),
    (18, "3.5", "essay", "R"),
]


def test_no_generator_is_built_on_enrichment_content():
    plan = load_term_plan()
    assert out_of_scope(GRADE10_SLUG, plan.enrichment_lessons, plan.enrichment_examples) == []


def test_scope_guard_reports_each_kind_of_violation():
    """الحارس نفسه: مثال إثرائي، ودرس إثرائي، وصيغة بلا رقم مثال، كلٌّ يُبلَّغ باسمه."""
    plan = load_term_plan()
    sample = REGISTRY[(GRADE10_SLUG, "1.1")][0]
    added = {"2.5": 5, "1.4": 1, "2.6": None}
    # الدروس المضافة قد يكون لها مولّدات حقيقية: تُستبدل صيغها مؤقتًا ثم يُعاد السجلّان كما كانا.
    registry, examples = dict(REGISTRY), dict(SKILL_EXAMPLES)
    try:
        for lesson, example in added.items():
            REGISTRY[(GRADE10_SLUG, lesson)] = [sample]
            if example is not None:
                SKILL_EXAMPLES[(GRADE10_SLUG, lesson, sample.__name__)] = example
        found = out_of_scope(GRADE10_SLUG, plan.enrichment_lessons, plan.enrichment_examples)
    finally:
        for store, saved in ((REGISTRY, registry), (SKILL_EXAMPLES, examples)):
            store.clear()
            store.update(saved)
    name = sample.__name__
    assert found == [f"1.4:{name} درس إثرائي", f"2.5:{name} مثال إثرائي 5", f"2.6:{name} بلا رقم مثال"]


def test_declared_examples_exist_in_the_book_index():
    examples = {row.lesson: {e.n for e in row.examples} for row in course_index(GRADE10_SLUG).lessons}
    declared = {key: n for key, n in SKILL_EXAMPLES.items() if key[0] == GRADE10_SLUG}
    assert declared
    for (_, lesson, name), number in declared.items():
        assert number in examples[lesson], (lesson, name, number)


def test_ready_lessons_have_generators():
    assert READY <= available_lessons(GRADE10_SLUG)


@pytest.mark.parametrize(("question", "lesson", "kind", "level"), READY_SLOTS)
def test_ready_slots_have_several_variants(question, lesson, kind, level):
    """لكل خانة صيغتان على الأقل بمستواها ونوعها، فلا يتكرر السؤال نفسه في كل نموذج."""
    assert len(variants(lesson, kind, level, course=GRADE10_SLUG)) >= 2, (question, lesson)


def test_twenty_question_worksheet_for_every_grade10_lesson_and_level():
    for lesson in sorted(available_lessons(GRADE10_SLUG)):
        levels = lesson_levels(lesson, course=GRADE10_SLUG)
        assert levels, lesson
        for level in levels:
            rng, used = random.Random(0), set()
            for _ in range(20):
                used.add(generate(lesson, rng, "essay", used, level, course=GRADE10_SLUG).key)
            assert len(used) == 20, (lesson, level)


@pytest.mark.django_db
def test_blueprint_slots_of_ready_units_are_filled_at_their_level():
    """خانات الوحدات 1 إلى 3 في الجدول المحمَّل تُملأ بنوعها ومستواها دون الرجوع إلى التوليد بلا قيد."""
    load_all()
    items = list(
        BlueprintItem.objects.filter(blueprint__slug=FINAL, lesson__code__in=READY)
        .select_related("lesson__course")
        .order_by("question_number", "position")
    )
    assert [(i.question_number, i.lesson.code, i.kind, i.level) for i in items] == READY_SLOTS
    for seed in range(40):
        rng, used = random.Random(seed), set()
        for item in items:
            assert variants(item.lesson.code, item.kind, item.level, item.needs_graph, course=GRADE10_SLUG)
            problem = services.generate_for_slot(item, rng, used)
            used.add(problem.key)
            slot = services.PartSlot(
                "", item.lesson.code, item.lesson.title, item.kind, item.marks, item.level
            )
            part = services.render_part(problem, slot, rng)
            assert part["stem"] and part["steps"] and part["level"] == item.level
            if item.kind == BlueprintItem.Kind.MCQ:
                assert (
                    len(set(part["options"])) == 4 and part["options"][part["answer_index"]] == part["answer"]
                )
            else:
                assert sum(row["marks"] for row in part["marking"]) == item.marks
        assert len(used) == len(items)


@pytest.mark.django_db
@pytest.mark.parametrize("lesson", ["1.3", "2.3", "2.5", "2.7", "2.9", "2.10", "3.3", "3.4", "3.5"])
def test_grade10_worksheet_is_built_for_a_ready_lesson(lesson):
    load_all()
    paper = services.build_worksheet(lesson, 8, 5, course=GRADE10_SLUG)
    assert len(paper["questions"]) == 8
    assert {part["lesson"] for q in paper["questions"] for part in q["parts"]} == {lesson}


def test_vertex_form_in_lesson_2_5_keeps_leading_coefficient_one():
    """المثال 5 من الدرس 2.5 (صيغة الرأس بمعامل رئيس غير الواحد) إثرائي: صيغة الرأس تبقى بمعامل واحد."""
    from apps.papers.domain.generators import x
    from apps.papers.domain.grade10_problems import vertex_form_by_completing_the_square

    for seed in range(60):
        check = vertex_form_by_completing_the_square(random.Random(seed)).check
        assert check["f"].coeff(x, 2) == 1
