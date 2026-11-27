"""الورقة العلاجية (M2.1): وصفة من أخطاء الطالب، كل جزء فيها يعود إلى مثال أخطأ فيه، بأعداد تخالف بنده الأصلي،
حتمية بالبذرة، وبحدّ أعلى يُقدَّم فيه المثال الأكثر خطأً. والخدمة تقرأ الأخطاء من قارئ التخطيط لشعب المعلم وحدها."""

from collections import Counter
from datetime import date

import pytest
from django.core.cache import cache

from apps.assets.storage import LocalStorage
from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.papers import pdf, services
from apps.papers.access import ensure_teacher
from apps.papers.api import PdfIn, PrintPayload
from apps.papers.domain.generators import REGISTRY, SKILL_EXAMPLES
from apps.papers.domain.item_bank import exit_ticket, usable
from apps.papers.domain.remedial import (
    MAX_PARTS,
    RemedialRecipe,
    StudentError,
    allocation,
    remedial_recipe,
)
from apps.planning import services as planning
from apps.planning.models import ItemResult, SectionStudent
from apps.planning.selectors import SectionNotOwnedError, StudentNotFoundError

COURSE = GRADE10_SLUG
LESSONS = ("1.1", "1.2", "1.3")
ITEM_SEED = 3
SECTION = "10/3"
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret


def ticket_examples(lesson: str) -> list[int]:
    """أمثلة الدرس التي لها بند في البنك (صيغة موضوعية)، من سجل الأمثلة مباشرة."""
    return sorted(
        {SKILL_EXAMPLES[(COURSE, lesson, fn.__name__)] for fn in REGISTRY[(COURSE, lesson)] if usable(fn)}
    )


def sat(lesson: str, wrong_examples: set[int], seed: int = ITEM_SEED) -> list[dict]:
    """طالب أجاب بطاقة كل مثال في الدرس: خيار خاطئ في `wrong_examples` والصحيح في غيرها. النتيجة من البند نفسه."""
    answers = []
    for example in ticket_examples(lesson):
        item = exit_ticket(COURSE, lesson, example, seed=seed)
        miss = next(i for i, option in enumerate(item.options) if not option.correct)
        choice = miss if example in wrong_examples else item.answer_index
        answers.append(
            {
                "lesson": lesson,
                "example": example,
                "seed": seed,
                "choice": choice,
                "correct": item.options[choice].correct,
                "error_kind": item.options[choice].kind or "",
            }
        )
    return answers


def errors_of(answers: list[dict]) -> list[StudentError]:
    return [
        StudentError(a["lesson"], a["example"], a["error_kind"], a["seed"])
        for a in answers
        if not a["correct"]
    ]


@pytest.fixture
def answers() -> list[dict]:
    """في كل درس: أخطأ في الأمثلة ذات الموضع الزوجي من أمثلة بنكه وأصاب في الباقي."""
    out = []
    for lesson in LESSONS:
        examples = ticket_examples(lesson)
        out += sat(lesson, set(examples[::2]))
    return out


def test_parts_target_student_errors(answers):
    missed = {(a["lesson"], a["example"]) for a in answers if not a["correct"]}
    passed = {(a["lesson"], a["example"]) for a in answers if a["correct"]}
    assert missed and passed

    recipe = remedial_recipe(COURSE, errors_of(answers), seed=11, max_parts=len(missed))

    targets = [(part.lesson, part.example) for part in recipe.parts]
    assert set(targets) == missed  # جزء واحد على الأقل لكل مثال أخطأ فيه
    assert not set(targets) & passed  # ولا جزء لمثال أصاب فيه
    assert recipe.left_out == ()
    for part in recipe.parts:
        # عودة الجزء إلى مثاله تُفحص من سجل المولّدات نفسه لا من حقول الوصفة
        names = {fn.__name__ for fn in REGISTRY[(COURSE, part.lesson)]}
        assert part.variant in names
        assert SKILL_EXAMPLES[(COURSE, part.lesson, part.variant)] == part.example
        assert part.problem.lesson == part.lesson
        assert part.misses == 1
        assert part.error_kinds == tuple(
            a["error_kind"] for a in answers if (a["lesson"], a["example"]) == (part.lesson, part.example)
        )


def test_same_seed_same_recipe_and_other_seed_changes_numbers(answers):
    errors = errors_of(answers)
    first = remedial_recipe(COURSE, errors, seed=5)
    assert first == remedial_recipe(COURSE, errors, seed=5)
    assert first == remedial_recipe(COURSE, list(reversed(errors)), seed=5)  # ترتيب الإدخال لا يغيّر الوصفة

    other = remedial_recipe(COURSE, errors, seed=6)
    assert [(p.lesson, p.example) for p in other.parts] == [(p.lesson, p.example) for p in first.parts]
    assert [p.problem.stem for p in other.parts] != [p.problem.stem for p in first.parts]
    assert {p.fingerprint for p in other.parts} != {p.fingerprint for p in first.parts}


@pytest.mark.parametrize("seed", range(8))
def test_part_numbers_differ_from_the_original_item(seed):
    # بذرة الوصفة تساوي بذرة البند عمدًا: حتى عندها لا يعود البند الذي أخطأ فيه الطالب
    answers = [a for lesson in LESSONS for a in sat(lesson, set(ticket_examples(lesson)), seed=seed)]
    recipe = remedial_recipe(COURSE, errors_of(answers), seed=seed, max_parts=len(answers))
    assert len(recipe.parts) == len(answers)
    for part in recipe.parts:
        original = exit_ticket(COURSE, part.lesson, part.example, seed=seed)
        assert part.fingerprint != original.fingerprint
        assert part.problem.stem != original.stem
    assert len({part.fingerprint for part in recipe.parts}) == len(recipe.parts)


def test_student_without_errors_gets_an_empty_recipe():
    recipe = remedial_recipe(COURSE, [], seed=1)
    assert recipe == RemedialRecipe(course=COURSE, seed=1)
    assert recipe.empty
    assert recipe.parts == () and recipe.left_out == ()


def test_cap_prefers_the_most_missed_example():
    first, second, third = ticket_examples("1.1")[:3]
    errors = (
        [StudentError("1.1", first, "sign", 1)]
        + [StudentError("1.1", third, "sign", seed) for seed in (1, 2, 3)]
        + [StudentError("1.1", second, "formula", seed) for seed in (1, 2)]
    )

    tight = remedial_recipe(COURSE, errors, seed=2, max_parts=2)
    assert [p.example for p in tight.parts] == sorted([third, second])  # الأكثر خطأً يدخلان، وبترتيب المثال
    assert tight.left_out == (("1.1", first),)

    roomy = remedial_recipe(COURSE, errors, seed=2, max_parts=5)
    counts = {n: sum(p.example == n for p in roomy.parts) for n in (first, second, third)}
    assert counts == {first: 1, second: 2, third: 2}  # جزء لكل مثال أولًا، ثم الزيادة للأكثر خطأً
    assert roomy.left_out == ()
    assert len({p.fingerprint for p in roomy.parts}) == 5

    assert len(remedial_recipe(COURSE, errors, seed=2).parts) <= MAX_PARTS
    assert remedial_recipe(COURSE, errors, seed=2, max_parts=0).parts == ()


def test_allocation_never_exceeds_cap_or_misses():
    misses = {("1.1", 1): 4, ("1.1", 2): 1, ("1.2", 1): 2}
    for cap in range(9):
        counts = allocation(Counter(misses), cap)
        assert sum(counts.values()) == min(cap, sum(misses.values()))
        assert all(counts[target] <= misses[target] for target in counts)


def test_example_without_generator_is_left_out_not_an_error():
    recipe = remedial_recipe(COURSE, [StudentError("1.1", 99, "sign", 1)], seed=1)
    assert recipe.parts == ()
    assert recipe.left_out == (("1.1", 99),)


# ───── الخدمة: الأخطاء من قارئ التخطيط ─────


@pytest.fixture
def teacher(db):
    return ensure_teacher("teacher", PASSWORD)[0]


def enroll(teacher, enrollment_no: str, answers: list[dict], section: str = SECTION) -> SectionStudent:
    student = SectionStudent.objects.create(
        owner=teacher, section=section, enrollment_no=enrollment_no, first_name="سالم", last_name="المري"
    )
    lessons = {row.code: row for row in Lesson.objects.filter(course__slug=COURSE)}
    for a in answers:
        ItemResult.objects.create(
            student=student,
            lesson=lessons[a["lesson"]],
            example=a["example"],
            seed=a["seed"],
            choice=a["choice"],
            correct=a["correct"],
            error_kind=a["error_kind"],
        )
    return student


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_service_builds_the_recipe_from_recorded_errors(teacher, answers):
    enroll(teacher, "1001", answers)
    enroll(teacher, "1002", [a for a in answers if a["correct"]])
    missed = {(a["lesson"], a["example"]) for a in answers if not a["correct"]}

    recipe = services.build_remedial_recipe(teacher, COURSE, SECTION, "1001", seed=7, max_parts=len(missed))
    assert {(p.lesson, p.example) for p in recipe.parts} == missed
    assert recipe == remedial_recipe(COURSE, errors_of(answers), seed=7, max_parts=len(missed))
    assert recipe == services.build_remedial_recipe(
        teacher, COURSE, SECTION, "1001", seed=7, max_parts=len(missed)
    )

    one_lesson = services.build_remedial_recipe(teacher, COURSE, SECTION, "1001", seed=7, lesson="1.2")
    assert one_lesson.parts and {p.lesson for p in one_lesson.parts} == {"1.2"}

    clean = services.build_remedial_recipe(teacher, COURSE, SECTION, "1002", seed=7)
    assert clean.empty and clean.seed == 7  # بلا أخطاء: وصفة فارغة لا خطأ

    unseeded = services.build_remedial_recipe(teacher, COURSE, SECTION, "1001")
    assert 0 <= unseeded.seed < services.MAX_SEED


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_service_reads_only_the_teachers_own_sections(teacher, answers):
    enroll(teacher, "1001", answers)
    other = ensure_teacher("teacher2", PASSWORD)[0]
    with pytest.raises(SectionNotOwnedError):
        services.build_remedial_recipe(other, COURSE, SECTION, "1001", seed=1)
    with pytest.raises(StudentNotFoundError):
        services.build_remedial_recipe(teacher, COURSE, SECTION, "9999", seed=1)


# ───── حزمة الشعبة (M2.2) ─────


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_class_pack_is_idempotent(teacher, tmp_path, monkeypatch):
    from apps.planning.tasks import build_class_pack_task

    wrong = ticket_examples("1.1")[:3]
    for n in range(30):
        enroll(teacher, str(2000 + n), sat("1.1", set(wrong)))
    enroll(teacher, "3000", sat("1.1", set()))  # بلا خطأ: بلا ورقة

    rendered: list[dict] = []

    def render(payload):
        rendered.append(PrintPayload.model_validate(payload).model_dump())  # ما يقبله مسار صفحة الطباعة
        return b"%PDF-1.7"

    monkeypatch.setattr(pdf, "render_payload", render)
    monkeypatch.setattr(planning, "get_storage", lambda: LocalStorage(tmp_path))

    def files() -> list[str]:
        return [p.name for p in tmp_path.rglob("*.pdf")]

    key = build_class_pack_task.delay(teacher.pk, COURSE, "1.1", SECTION).get()
    assert build_class_pack_task.delay(teacher.pk, COURSE, "1.1", SECTION).get() == key
    assert len(rendered) == 1 and len(files()) == 1

    payload = rendered[0]
    # المساران العامّان لا يقبلان الأسماء ولا أكثر من نموذجين بها
    with pytest.raises(ValueError, match="أكثر من نموذجين"):
        PdfIn.model_validate(payload)
    assert len(payload["papers"]) == len(payload["students"]) == 30
    assert payload["show_key"] is True
    assert payload["students"][0] == "سالم المري (2000)"
    # ثلاثة أخطاء وسؤالان: الحد الذي تتسع له صفحة الطالب الواحدة
    assert all(len(p["questions"]) == planning.PACK_MAX_PARTS == 2 for p in payload["papers"])
    assert "المري" not in str(payload["papers"])  # الاسم بجوار الورقة لا في عنوانها (التذييل الجاري مشترك)
    assert len({p["seed"] for p in payload["papers"]}) == 30

    log = AuditLog.objects.get(action="remedial.pack.build")
    assert log.payload == {"sheets": 30}
    assert log.target == planning.results_target(COURSE, "1.1", SECTION)
    folder, name = key.rsplit("/", 1)
    assert name == "pack.pdf" and set(folder.removeprefix("remedial/")) <= set("0123456789abcdef")

    # نتيجة صُحِّحت: ملف جديد يحل محل السابق
    ItemResult.objects.filter(student__enrollment_no="2000").delete()
    assert planning.build_class_pack(teacher, COURSE, "1.1", SECTION) == key
    assert len(rendered) == 2 and len(rendered[1]["papers"]) == 29
    assert files() == ["pack.pdf"]

    # بناء جارٍ للملف نفسه: لا بناء ثانيًا معه
    lock = f"class-pack:{key.rsplit('/', 1)[0]}"
    cache.add(lock, 1)
    with pytest.raises(planning.PlanningError):
        planning.build_class_pack(teacher, COURSE, "1.1", SECTION)
    cache.delete(lock)

    # صُحِّحت نتائج الشعبة كلها: لا يبقى ملف بأسمائهم
    saved = list(ItemResult.objects.filter(correct=False))
    ItemResult.objects.filter(correct=False).delete()
    with pytest.raises(planning.PlanningError):
        planning.build_class_pack(teacher, COURSE, "1.1", SECTION)
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]
    ItemResult.objects.bulk_create(saved)
    planning.build_class_pack(teacher, COURSE, "1.1", SECTION)

    # انتهاء السنة يحذف الملف مع النتائج
    assert planning.purge_ended_results(date(2100, 1, 1)).results
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_class_pack_needs_errors_and_own_section(teacher):
    enroll(teacher, "3000", sat("1.1", set()))
    with pytest.raises(planning.PlanningError):
        planning.build_class_pack(teacher, COURSE, "1.1", SECTION)
    other = ensure_teacher("teacher2", PASSWORD)[0]
    with pytest.raises(SectionNotOwnedError):
        planning.build_class_pack(other, COURSE, "1.1", SECTION)
