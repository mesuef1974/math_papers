"""تحضير حصص العاشر الـ48 (المرحلة 2 من docs/lesson_prep_plan.md): التوزيع والاشتقاق والمعايير T1 إلى T13.

حصص العاشر تجتاز المعايير الحاجبة كلها، وكل مثال أساسي في حصة واحدة، وكل معيار حاجب يُشغَّل على حالة فاشلة. النصوص والاعتماد والمقاطع معلَّقة لا فاشلة حتى يُعتمد ملف الوحدة.
"""

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.domain.course_index import (
    AnalysisRow,
    ExampleIndex,
    LessonIndex,
    TaskGuide,
    VocabularyCount,
)
from apps.planning.domain.prep import (
    PERIOD_MINUTES,
    STAGE_NAMES,
    Classwork,
    ExitTicket,
    PrepError,
    Recall,
    TeacherEdit,
    allocate,
    build_prep,
    derived_paths,
    lesson_examples,
    parse_ranges,
    prep_digest,
    recall_for,
)
from apps.planning.domain.prep_checks import (
    BLOCKING,
    FAIL,
    PASS,
    PENDING,
    blocking_failures,
    check_prep,
    t1_coverage,
    t2_objectives,
    t2b_chain,
    t2c_approval,
    t3_standards,
    t4_classwork,
    t5_progression,
    t6_time,
    t7_assessment,
    t8_differentiation,
    t9_homework,
    t10_recall,
    t11_load,
    t12_last_period,
    t13_closed_fields,
)
from apps.planning.domain.strategies import load_library
from apps.planning.selectors import lesson_preps

LIBRARY = {s.slug: s for s in load_library()}
APPROVED_UNITS = {1, 2, 3}  # وحدات العاشر التي اعتمد المالك نصوصها (prep/unit-<n>.json)
DRAFT_UNITS: set[int] = set()  # وحدات كُتبت نصوصها ولم تُعتمد بعد: T2c يحجبها وحده


@pytest.fixture
def preps(loaded_courses):
    return lesson_preps(GRADE10_SLUG)


def _prep(preps, lesson, k):
    return next(p.prep for p in preps if p.prep.lesson == lesson and p.prep.k == k)


# ---- الحصص الـ48 ----


def test_48_lesson_periods_pass_every_blocking_criterion(preps):
    assert len(preps) == 48
    failures = {}
    for row in preps:
        for result in blocking_failures(row.checks):
            if result.code == "T2c" and row.prep.unit in DRAFT_UNITS:
                continue  # المسودة لا يرفع حجبها إلا اعتماد المالك
            failures.setdefault((row.prep.lesson, row.prep.k), []).append(result)
    assert failures == {}


def test_every_core_example_sits_in_exactly_one_period(preps):
    placed: dict[str, list[int]] = {}
    for row in preps:
        placed.setdefault(row.prep.lesson, []).extend(e.n for e in row.prep.examples)
    for lesson, numbers in placed.items():
        assert len(numbers) == len(set(numbers)), lesson
        core = {e.n for e in _prep(preps, lesson, 1).examples} | set(numbers)
        assert sorted(numbers) == sorted(core), lesson
    assert placed["1.1"] == [1, 2, 3, 4, 5]
    assert placed["2.5"] == [1, 2, 3, 4]  # المثال 5 إثرائي
    assert placed["3.3"] == [3, 4, 5]  # المثالان 1 و2 إثرائيان


def test_every_criterion_is_reported_and_texts_are_pending_not_failing(preps):
    for row in preps:
        codes = [r.code for r in row.checks]
        assert set(codes) == BLOCKING | {"T9"} and len(codes) == len(set(codes))
        by = {r.code: r for r in row.checks}
        unit = row.prep.unit
        written = unit in APPROVED_UNITS | DRAFT_UNITS
        assert by["T2c"].status == (
            PASS if unit in APPROVED_UNITS else FAIL if unit in DRAFT_UNITS else PENDING
        )
        assert by["T2"].status == (PASS if row.prep.is_last or written else PENDING)
        if not row.prep.is_last:
            assert by["T2b"].status in (PENDING, FAIL)


def test_last_period_has_no_new_example_and_carries_the_quiz(preps):
    for row in preps:
        p = row.prep
        if p.is_last:
            assert not p.examples and not p.objectives and p.quiz and p.exit_ticket is None
        else:
            assert 1 <= len(p.objectives) <= 3 and not p.quiz and p.exit_ticket is not None


def test_stages_follow_gradual_release_and_sum_to_45(preps):
    for row in preps:
        stages = row.prep.stages
        assert tuple(s.name for s in stages) == STAGE_NAMES
        assert sum(s.minutes for s in stages) == PERIOD_MINUTES


def test_recall_links_each_period_to_what_came_before(preps):
    assert _prep(preps, "1.1", 1).recall == Recall("prior_knowledge")
    assert _prep(preps, "1.2", 1).recall == Recall("previous_lesson", "1.1")
    assert _prep(preps, "1.3", 2).recall == Recall("previous_period", k=1)
    # 1.3: حصتان في الأسبوع 2 ثم الثالثة في الأسبوع 3 بعد انقطاع
    assert _prep(preps, "1.3", 3).recall == Recall("exit_review", k=2)


def test_derivation_is_deterministic(preps):
    from apps.planning.selectors import lesson_preps as again

    assert [r.prep for r in preps] == [r.prep for r in again(GRADE10_SLUG)]


# ---- التوزيع ----


def test_allocate_keeps_order_caps_three_and_leaves_the_last_period_empty():
    groups = allocate([(1, 1), (2, 4), (3, 4), (4, 1), (5, 9)], 3)
    assert groups == ((1, 2, 3), (4, 5), ())
    assert allocate([(1, 2), (2, 2), (3, 2), (4, 2)], 4) == ((1, 2), (3,), (4,), ())


@pytest.mark.parametrize(("count", "n"), [(7, 3), (1, 3), (2, 1)])
def test_allocate_refuses_impossible_splits(count, n):
    with pytest.raises(PrepError):
        allocate([(i, 1) for i in range(1, count + 1)], n)


def test_parse_ranges_reads_task_guide_spans():
    assert parse_ranges("10-12, 15 , 20–21، 23") == {10, 11, 12, 15, 20, 21, 23}


# ---- كل معيار حاجب على حالة فاشلة ----


@pytest.fixture
def middle(preps):
    return _prep(preps, "2.3", 1)


@pytest.fixture
def last(preps):
    return _prep(preps, "2.3", 4)


def _fails(result):
    assert result.status == FAIL, result
    return result


def test_t1_fails_on_a_missing_or_doubled_example(preps):
    lesson = [r.prep for r in preps if r.prep.lesson == "2.3"]
    core = [e.n for p in lesson for e in p.examples]
    assert t1_coverage(lesson, core).status == PASS
    _fails(t1_coverage(lesson[1:], core))
    _fails(t1_coverage([lesson[0], *lesson], core))
    rich = replace(lesson[0], examples=(*lesson[0].examples, replace(lesson[0].examples[0], n=9)))
    assert "إثرائي" in _fails(t1_coverage([rich, *lesson[1:]], core, enrichment=[9])).details[0]
    flagged = replace(
        rich, examples=(*lesson[0].examples, replace(lesson[0].examples[0], n=9, extension=True))
    )
    assert t1_coverage([flagged, *lesson[1:]], core, enrichment=[9]).status == PASS


def test_t2_fails_on_bad_verb_empty_part_or_missing_objective(middle):
    o = middle.objectives[0]
    _fails(t2_objectives(replace(middle, objectives=(replace(o, verb="يفهم"), *middle.objectives[1:]))))
    _fails(t2_objectives(replace(middle, objectives=middle.objectives[1:])))
    texts = {
        "audience": "الطالب",
        "behavior": "يحسب",
        "condition": "",
        "criterion": "بلا خطأ",
        "source": "authored",
    }
    _fails(t2_objectives(replace(middle, objectives=(replace(o, **texts), *middle.objectives[1:]))))
    full = tuple(
        replace(
            x,
            audience="الطالب",
            behavior=f"{x.verb} القيمة",
            condition="من معادلة",
            criterion="صحيحًا",
            source="authored",
        )
        for x in middle.objectives
    )
    assert t2_objectives(replace(middle, objectives=full)).status == PASS


def test_t2b_fails_without_training_generator_or_clip(middle):
    e = middle.examples[0]
    no_gen = replace(middle, examples=(replace(e, has_generator=False), *middle.examples[1:]))
    _fails(t2b_chain(no_gen))
    no_work = replace(middle, classwork=tuple(c for c in middle.classwork if c.example != e.n))
    _fails(t2b_chain(no_work))
    no_clip = replace(middle, examples=tuple(replace(x, continuations=0) for x in middle.examples))
    _fails(t2b_chain(no_clip))
    clips = replace(middle, examples=tuple(replace(x, continuations=1) for x in middle.examples))
    assert t2b_chain(clips).status == PENDING  # «جرّب» وحده معلَّق
    assert t2b_chain(middle).status == PENDING


def test_t2c_fails_on_a_draft_unit(middle):
    assert t2c_approval(replace(middle, unit_status=None)).status == PENDING
    _fails(t2c_approval(replace(middle, unit_status="draft")))
    assert t2c_approval(replace(middle, unit_status="approved")).status == PASS


def test_t3_fails_when_a_standard_is_lost(preps):
    lesson = [r.prep for r in preps if r.prep.lesson == "1.3"]
    standards = lesson[0].standards
    assert t3_standards(lesson, standards).status == PASS
    _fails(t3_standards([replace(p, standards=standards[:1]) for p in lesson], standards))


def test_t4_fails_on_missing_or_foreign_classwork(middle):
    e = middle.examples[0]
    _fails(t4_classwork(replace(middle, classwork=tuple(c for c in middle.classwork if c.example != e.n))))
    _fails(t4_classwork(replace(middle, classwork=(*middle.classwork, Classwork(99, 1, (1,))))))
    _fails(t4_classwork(replace(middle, homework=(*middle.homework, 99))))


def test_t5_fails_on_falling_depth(middle):
    falling = (Classwork(1, 2, (1,)), Classwork(2, 1, (2,)))
    _fails(t5_progression(replace(middle, classwork=falling)))


def test_t6_fails_on_wrong_total_order_or_bounds(middle):
    s = middle.stages
    _fails(t6_time(replace(middle, stages=(replace(s[0], minutes=s[0].minutes + 1), *s[1:])), LIBRARY))
    _fails(t6_time(replace(middle, stages=(s[1], s[0], *s[2:])), LIBRARY))
    moved = (replace(s[0], minutes=s[0].minutes + 6), replace(s[1], minutes=s[1].minutes), *s[2:4],
             replace(s[4], minutes=s[4].minutes - 6), s[5])  # fmt: skip
    _fails(t6_time(replace(middle, stages=moved), LIBRARY))
    _fails(
        t6_time(
            replace(middle, stages=(*s[:2], replace(s[2], strategy="close-exit-ticket"), *s[3:])), LIBRARY
        )
    )


def test_t7_fails_without_formative_check_or_valid_exit(middle):
    _fails(t7_assessment(replace(middle, formative=())))
    _fails(t7_assessment(replace(middle, exit_ticket=None)))
    _fails(t7_assessment(replace(middle, exit_ticket=ExitTicket(99, 1))))
    _fails(t7_assessment(replace(middle, exit_ticket=replace(middle.exit_ticket, dok=4))))


def test_t8_fails_on_empty_or_off_guide_lists(middle):
    _fails(t8_differentiation(replace(middle, basic=())))
    _fails(t8_differentiation(replace(middle, advanced=(*middle.advanced, 99))))


def test_t9_warns_outside_three_to_eight(middle):
    result = t9_homework(replace(middle, homework=middle.homework[:2]))
    assert result.status == FAIL and not result.blocking


def test_t10_fails_on_wrong_recall(middle, preps):
    _fails(t10_recall(replace(middle, recall=Recall("prior_knowledge")), "2.2", False))
    later = _prep(preps, "2.3", 2)
    after_break = later.recall.kind == "exit_review"
    assert t10_recall(later, "2.2", after_break).status == PASS
    _fails(t10_recall(later, "2.2", not after_break))


def test_t11_fails_on_four_objectives_or_unbalanced_load(preps):
    lesson = [r.prep for r in preps if r.prep.lesson == "1.1"]
    assert t11_load(lesson).status == PASS
    crowded = replace(lesson[0], objectives=(*lesson[0].objectives, lesson[1].objectives[0]))
    _fails(t11_load([crowded, *lesson[1:]]))
    heavy = replace(lesson[0], examples=tuple(replace(e, weight=1) for e in lesson[0].examples))
    heavy2 = replace(lesson[1], examples=tuple(replace(e, weight=e.weight + 30) for e in lesson[1].examples))
    _fails(t11_load([heavy, heavy2, lesson[2]]))


def test_t12_fails_on_new_example_or_missing_quiz(last, middle):
    depths = last.quiz
    assert t12_last_period(last, depths).status == PASS
    _fails(t12_last_period(replace(last, examples=middle.examples[:1]), depths))
    _fails(t12_last_period(replace(last, quiz=()), depths))
    _fails(t12_last_period(replace(middle, quiz=depths), depths))


def test_t13_fails_on_free_text(middle):
    o = middle.objectives[0]
    guide_text = replace(o, audience="x", behavior="y", condition="z", criterion="w", source="index")
    _fails(t13_closed_fields(replace(middle, objectives=(guide_text, *middle.objectives[1:])), LIBRARY))
    _fails(t13_closed_fields(replace(middle, standards=("نص معيار من الدليل",)), LIBRARY))
    _fails(
        t13_closed_fields(
            replace(middle, stages=(replace(middle.stages[0], strategy="free"), *middle.stages[1:])), LIBRARY
        )
    )
    _fails(t13_closed_fields(replace(middle, sources={"objectives": "guide"}), LIBRARY))


# ---- درس بلا دليل مهام (الثاني عشر): الصفي من صفوف try، والتمايز والواجب من صفوف practice ----

TRY = {1: (1, [1]), 2: (2, [2]), 3: (3, [3])}  # مثال → (عمقه، تمرين «حاول أن تحل»)
PRACTICE = {1: [10, 11, 12, 13], 2: [14, 15, 16, 17, 18], 3: [20, 21, 22, 23, 24, 25, 26]}


def _unguided(practice=True, guide=None):
    rows = [AnalysisRow(example=n, dok=d, exercises=ex) for n, (d, ex) in TRY.items()]
    if practice:
        rows += [
            AnalysisRow(example=n, dok=TRY[n][0], exercises=ex, kind="practice") for n, ex in PRACTICE.items()
        ]
    lesson = LessonIndex(
        lesson="1.1",
        unit=1,
        examples=[ExampleIndex(n=n) for n in TRY],
        analysis=rows,
        exercises_total=26,
        task_guide=guide,
        quiz_depths=[1, 2],
        vocabulary=VocabularyCount(new=0, review=0),
    )
    examples = lesson_examples(lesson, "g12-like", generators=TRY)
    groups = allocate([(e.n, e.weight) for e in examples], 3)
    preps = [
        build_prep(
            course="g12-like",
            lesson=lesson,
            examples=examples,
            groups=groups,
            k=k,
            recall=recall_for(k, None, False),
            library=list(LIBRARY.values()),
        )
        for k in (1, 2, 3)
    ]
    return lesson, examples, preps


def _checks(lesson, prep):
    return check_prep(prep, LIBRARY, previous_lesson=None, after_break=False, quiz_depths=lesson.quiz_depths)


def test_unguided_lesson_trains_from_try_rows_and_differentiates_from_practice_rows():
    lesson, examples, preps = _unguided()
    # الوزن والتوزيع من صفوف try وحدها، وعمق المثال لا يتغير بصف practice
    assert [(e.weight, e.max_dok) for e in examples] == [(1, 1), (2, 2), (3, 3)]
    assert [tuple(e.n for e in p.examples) for p in preps] == [(1, 2), (3,), ()]
    tried = {x for _, ex in TRY.values() for x in ex}
    for prep in preps:
        assert {x for c in prep.classwork for x in c.exercises} <= tried
        assert bool(prep.classwork) == bool(prep.examples)
        own = {x for e in prep.practice_examples for x in PRACTICE[e.n]}
        for numbers in (prep.basic, prep.advanced, prep.homework):
            assert numbers and set(numbers) <= own, (prep.k, numbers)
        assert not set(prep.homework) & {*prep.basic, *prep.advanced}
        assert blocking_failures(_checks(lesson, prep)) == ()
    first, second, last = preps
    # الأساسي من أمثلة عمقها 1-2، والمتقدم من أعلى عمق في الدرس
    assert (last.basic, last.advanced) == ((10, 11, 12), (20, 21, 22))
    assert last.task_guide == (frozenset(range(10, 19)), frozenset(range(20, 27)))
    assert last.homework == (13, 14, 15, 16, 17, 18, 23, 24)
    # حصة بلا مثال بأعلى عمق الدرس: المتقدم من أعلى أمثلتها عمقًا
    assert (first.basic, first.advanced, first.homework) == ((10, 11, 12), (14, 15, 16), (13, 17, 18))
    # حصة كل أمثلتها فوق العمق 2: الأساسي من أدناها، والمتقدم يقدّم ما لم يأخذه الأساسي
    assert (second.basic, second.advanced, second.homework) == ((20, 21, 22), (23, 24, 25), (26,))
    assert {r.code: r.status for r in _checks(lesson, first)}["T9"] == PASS


def test_unguided_lesson_without_practice_rows_still_fails_t8():
    lesson, _, preps = _unguided(practice=False)
    for prep in preps:
        assert not prep.basic and not prep.advanced and not prep.homework
        assert "T8" in {r.code for r in blocking_failures(_checks(lesson, prep))}


def test_teacher_removed_practice_exercise_leaves_every_list():
    lesson, examples, preps = _unguided()
    groups = [tuple(e.n for e in p.examples) for p in preps]
    edited = build_prep(
        course="g12-like",
        lesson=lesson,
        examples=examples,
        groups=groups,
        k=3,
        recall=recall_for(3, None, False),
        library=list(LIBRARY.values()),
        teacher=TeacherEdit(removed=frozenset({10, 20})),
    )
    assert (edited.basic, edited.advanced) == ((11, 12, 13), (21, 22, 23))
    assert not {10, 20} & set(edited.homework)


def test_task_guide_wins_over_practice_rows():
    """مع دليل المهام المساران منه كما كانا، وصفوف practice تمارين كغيرها."""
    _, _, preps = _unguided(guide=TaskGuide(basic="1-12", advanced="13-26"))
    last = preps[-1]
    assert last.task_guide == (frozenset(range(1, 13)), frozenset(range(13, 27)))
    assert (last.basic, last.advanced) == ((1, 10, 11), (20, 21, 22))
    assert last.homework == (2, 3, 12)


def test_derived_paths_are_empty_without_practice_rows():
    _, examples, _ = _unguided(practice=False)
    assert derived_paths(examples, examples) == (frozenset(), frozenset())


def test_grade10_preps_are_untouched_by_the_practice_field(preps):
    """العاشر بدليل مهام وبلا صفوف practice ولا صفحات تمارين: الحقلان فارغان وتجزئة التحضير كما كانت قبله (لا عرض يُعلَّم قديمًا)."""
    for row in preps:
        prep = row.prep
        assert all(not e.practice for e in (*prep.examples, *prep.review))
        assert not prep.exercise_pages
        assert prep.task_guide[0] and prep.task_guide[1]
        old = asdict(prep)
        for example in (*old["examples"], *old["review"]):
            del example["practice"]
        del old["exercise_pages"]
        text = json.dumps(
            old,
            default=sorted,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        assert prep_digest(prep) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    _, _, unguided = _unguided()
    assert prep_digest(unguided[0]) != prep_digest(replace(unguided[0], examples=()))
