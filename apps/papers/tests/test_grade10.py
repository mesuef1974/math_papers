"""مولّدات العاشر: نطاق الاختبار (لا سؤال من درس أو مثال إثرائي)، وكفاية الصيغ لخانات الجدول ولأوراق العمل."""

import random

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import BlueprintItem
from apps.knowledge.domain.contract import read_source
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
    plan = read_source(GRADE10_SLUG).term_plan.to_domain(1)
    assert out_of_scope(GRADE10_SLUG, plan.enrichment_lessons, plan.enrichment_examples) == []


def test_scope_guard_reports_each_kind_of_violation():
    """الحارس نفسه: مثال إثرائي، ودرس إثرائي، وصيغة بلا رقم مثال، كلٌّ يُبلَّغ باسمه."""
    plan = read_source(GRADE10_SLUG).term_plan.to_domain(1)
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


@pytest.mark.usefixtures("loaded_courses")
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


@pytest.mark.django_db
def test_full_exam_carries_the_course_grade_and_real_lesson_titles():
    """الاختبار الكامل (النموذجان) يحمل صف مقرره لا صف ملف الطباعة، وعناوين دروس الكتاب لا «الدرس <رمز>»."""
    load_all()
    for form in ("A", "B"):
        paper = services.build_exam(FINAL, 7, form)
        assert paper["grade"] == "الصف 10" and not paper["is_forecast"]
        assert len(paper["questions"]) == 18 and sum(q["marks"] for q in paper["questions"]) == 50
        titles = {part["lesson_title"] for q in paper["questions"] for part in q["parts"]}
        assert not any(title.startswith("الدرس ") for title in titles)
    assert services.build_worksheet("3.5", 2, 5, course=GRADE10_SLUG)["grade"] == "الصف 10"


@pytest.mark.django_db
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_form_b_rotates_lessons_within_each_ministry_group(seed):
    """النموذج ب يبدّل دروس كل مجموعة بين خاناتها: النوع والدرجة والمستوى ثابتة، ودروس المجموعة كلها مغطاة،
    وأغلب الفروع بدرس غير درسها في أ، وفروع السؤال الواحد بدروس مختلفة."""
    load_all()
    group_of = {
        (item.question_number, item.position): item.group
        for item in BlueprintItem.objects.filter(blueprint__slug=FINAL)
    }
    paper_a = services.build_exam(FINAL, seed)
    paper_b = services.build_exam(FINAL, seed, "B")
    assert paper_b == services.build_exam(FINAL, seed, "B")  # حتمي من البذرة
    assert paper_a["level_marks"] == paper_b["level_marks"] == {"K": 25, "A": 20, "R": 5}
    covered_a: dict[str, set[str]] = {}
    covered_b: dict[str, set[str]] = {}
    moved = 0
    for qa, qb in zip(paper_a["questions"], paper_b["questions"], strict=True):
        lessons_b = [part["lesson"] for part in qb["parts"]]
        assert len(set(lessons_b)) == len(lessons_b)
        for index, (pa, pb) in enumerate(zip(qa["parts"], qb["parts"], strict=True)):
            group = group_of[(qa["number"], index + 1)]
            assert (pa["slot"]["kind"], pa["marks"], pa["level"]) == (pb["slot"]["kind"], pb["marks"], pb["level"])
            covered_a.setdefault(group, set()).add(pa["lesson"])
            covered_b.setdefault(group, set()).add(pb["lesson"])
            moved += pa["lesson"] != pb["lesson"]
    assert covered_b == covered_a  # كل درس في مجموعته، ولا يغيب درس
    assert moved >= 17  # 3.5 وحده يملك مستوى R في مجموعته فيبقى


@pytest.mark.django_db
def test_grade12_form_b_keeps_its_lessons():
    """جدول بلا مجموعات (الثاني عشر المبذور) لا يدور: ب يكرر دروس أ بأعداد جديدة."""
    load_all()
    slug = next(b.slug for b in services.ready_blueprints() if b.course.slug != GRADE10_SLUG)
    lessons = [
        [part["lesson"] for q in services.build_exam(slug, 3, form)["questions"] for part in q["parts"]]
        for form in ("A", "B")
    ]
    assert lessons[0] == lessons[1]
