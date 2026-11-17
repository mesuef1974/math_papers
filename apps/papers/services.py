"""تجميع الأوراق (قراءة فقط: البذرة نفسها تعطي الورقة نفسها دائمًا) وحفظ ترويسة الطباعة."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import secrets
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.cache import cache
from django.db import transaction

from apps.core.services import record_audit
from apps.curriculum import selectors
from apps.curriculum.courses import DEFAULT_COURSE
from apps.curriculum.models import BlueprintItem, Course

from .domain.generators import (
    LEVEL_NAMES,
    ExhaustedError,
    LevelUnavailableError,
    Problem,
    available_lessons,
    generate,
    generator_version,
    lesson_levels,
)
from .domain.marking import marking
from .models import PrintProfile, SavedPaper
from .selectors import PROFILE_FIELDS, print_profile, saved_paper

logger = logging.getLogger(__name__)

MAX_SEED = 2**31 - 1
PART_LABELS = "ABCDEFGH"
OPTION_LABELS = "ABCD"  # تطابق ترتيب عرض الخيارات في الواجهة
FORMS = ("A", "B")  # نموذجان متكافئان: ب بالبنية والصيغ نفسها وأعداد مختلفة
PURPOSES = {"remedial": ("K", "ورقة علاجية"), "enrichment": ("R", "ورقة إثرائية")}
# الاختبار القصير من 10: أربعة موضوعية بدرجة وسؤالان مقاليان بثلاث، بمستويات متدرجة
QUIZ_SLOTS = (
    ("mcq", "K", 1),
    ("mcq", "K", 1),
    ("mcq", "A", 1),
    ("mcq", "A", 1),
    ("essay", "A", 3),
    ("essay", "R", 3),
)
QUIZ_MAX_LESSONS = 2


class UnknownBlueprintError(LookupError):
    pass


class UnknownLessonError(LookupError):
    pass


def _course_slug(course: Course | None) -> str:
    """معرّف المقرر في سجل المولّدات؛ ما بلا مقرر هو مقرر الثاني عشر الذي نشأت عليه البيانات."""
    return course.slug if course else DEFAULT_COURSE


def _resolve_course(slug: str) -> Course:
    """مقرر بمعرّفه، والفارغ هو المقرر الحالي. المجهول يُعامَل درسًا غير متاح."""
    try:
        return selectors.course_by_slug(slug)
    except selectors.UnknownCourseError as error:
        raise UnknownLessonError(slug) from error


class SavedLimitError(ValueError):
    """بلغ المعلم الحد الأقصى من الأوراق المحفوظة."""


class SavedConflictError(ValueError):
    """التعديل يجعل الورقة نسخة من ورقة محفوظة أخرى."""


@dataclass(frozen=True)
class PartSlot:
    """خانة في الورقة: قيودها تُحفظ مع الجزء حتى يُستبدل أو يُعاد توليده بالقيود نفسها."""

    label: str
    lesson: str
    lesson_title: str
    kind: str
    marks: int
    level: str = ""  # فارغ = أي مستوى
    needs_graph: bool = False
    course: str = DEFAULT_COURSE  # معرّف المقرر: يلزم اختيار المولّد، ولا يدخل الجزء المحفوظ


def new_seed() -> int:
    return secrets.randbelow(MAX_SEED)


def render_part(problem: Problem, slot: PartSlot, rng: random.Random) -> dict:
    options: list[str] = []
    option_graphs: list[dict] = []
    answer = problem.answer
    answer_index = -1  # موضع الخيار الصحيح بعد الخلط؛ -1 للمقالي. يلزم ورقة التظليل ومفتاحها.
    if problem.option_graphs:
        # خيارات رسوم: يُخلط الترتيب، والجواب اسم الخيار الصحيح بعد الخلط.
        order = list(range(len(problem.option_graphs)))
        rng.shuffle(order)
        option_graphs = [problem.option_graphs[i] for i in order]
        options = ["" for _ in order]
        answer_index = order.index(0)
        answer = f"الخيار ({OPTION_LABELS[answer_index]})"
    elif slot.kind == BlueprintItem.Kind.MCQ:
        options = [problem.answer, *problem.wrong]
        rng.shuffle(options)
        answer_index = options.index(problem.answer)
    return {
        "label": slot.label,
        "lesson": slot.lesson,
        "lesson_title": slot.lesson_title,
        "marks": slot.marks,
        "level": problem.level,
        "stem": problem.stem,
        "options": options,
        "answer": answer,
        "answer_index": answer_index,
        "steps": list(problem.steps),
        "marking": marking(slot.kind, problem.steps, slot.marks),
        "graph": problem.graph,
        "option_graphs": option_graphs,
        "variant": problem.variant,
        "fingerprint": problem.fingerprint,
        "slot": {"kind": slot.kind, "level": slot.level, "needs_graph": slot.needs_graph},
    }


def generate_for_slot(item: BlueprintItem, rng: random.Random, used: set[str]) -> Problem:
    """مسألة بمستوى الخانة ورسمها. خانة لا صيغة لها (عُدّلت من لوحة الإدارة) تُملأ بلا قيد بدل إسقاط الاختبار."""
    course = _course_slug(item.lesson.course)
    try:
        return generate(
            item.lesson.code, rng, item.kind, used, item.level or None, item.needs_graph, course=course
        )
    except LevelUnavailableError:
        logger.warning("خانة الجدول %s بلا صيغة مطابقة؛ تُملأ بلا قيد المستوى والرسم", item.pk)
        return generate(item.lesson.code, rng, item.kind, used, course=course)


def paper_meta(kind: str, course: str = DEFAULT_COURSE, **extra: object) -> dict:
    """حقول مشتركة تهم الحفظ وإعادة التوليد."""
    return {"kind": kind, "generator_version": generator_version(course), **extra}


def build_exam(slug: str, seed: int | None = None, form: str = "A") -> dict:
    blueprint = selectors.blueprint_with_items(slug)
    if blueprint is None:
        raise UnknownBlueprintError(slug)
    seed = new_seed() if seed is None else seed
    course = _course_slug(blueprint.course)
    if form == "B":
        return build_form_b(build_exam(slug, seed), course)
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    grouped: dict[int, list[BlueprintItem]] = defaultdict(list)
    for item in blueprint.items.all():
        grouped[item.question_number].append(item)

    used: set[str] = set()
    questions = []
    level_marks: dict[str, int] = defaultdict(int)
    for number, items in sorted(grouped.items()):
        parts = []
        for position, item in enumerate(items):
            label = PART_LABELS[position] if len(items) > 1 else ""
            slot = PartSlot(
                label,
                item.lesson.code,
                item.lesson.title,
                item.kind,
                item.marks,
                item.level or "",
                item.needs_graph,
                course,
            )
            problem = generate_for_slot(item, rng, used)
            used.add(problem.key)
            level_marks[problem.level] += item.marks
            parts.append(render_part(problem, slot, rng))
        questions.append(
            {"number": number, "kind": items[0].kind, "marks": sum(i.marks for i in items), "parts": parts}
        )
    return {
        **paper_meta("exam", course, blueprint=blueprint.slug, lesson_code=""),
        "title": blueprint.title,
        "form": "A",
        "seed": seed,
        "total_marks": blueprint.total_marks,
        "is_forecast": blueprint.is_forecast,
        "level_marks": dict(level_marks),
        "questions": questions,
        "level": "",
    }


def build_worksheet(
    lesson_code: str,
    count: int,
    seed: int | None = None,
    level: str | None = None,
    form: str = "A",
    purpose: str = "",
    course: str = "",
) -> dict:
    """ورقة عمل لدرس. purpose=remedial يحصرها في السهل ويسمّيها علاجية، وenrichment في مهارات العليا إثرائية."""
    course_row = _resolve_course(course)
    lesson = selectors.lessons(course_row).filter(code=lesson_code).first()
    if lesson is None or lesson_code not in available_lessons(course_row.slug):
        raise UnknownLessonError(lesson_code)
    seed = new_seed() if seed is None else seed
    if purpose:
        level = PURPOSES[purpose][0]
    if form == "B":
        return build_form_b(
            build_worksheet(lesson_code, count, seed, level, purpose=purpose, course=course_row.slug),
            course_row.slug,
        )
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    used: set[str] = set()
    questions = []
    for number in range(1, count + 1):
        try:
            problem = generate(
                lesson.code, rng, BlueprintItem.Kind.ESSAY, used, level, course=course_row.slug
            )
        except LevelUnavailableError as error:
            raise UnknownLessonError(lesson_code) from error
        used.add(problem.key)
        slot = PartSlot(
            "", lesson.code, lesson.title, BlueprintItem.Kind.ESSAY, 0, level or "", course=course_row.slug
        )
        questions.append(
            {"number": number, "kind": slot.kind, "marks": 0, "parts": [render_part(problem, slot, rng)]}
        )
    return {
        **paper_meta("worksheet", course_row.slug, blueprint="", lesson_code=lesson.code),
        "title": f"{PURPOSES[purpose][1] if purpose else 'ورقة عمل'}: {lesson.title}"
        + (f" ({LEVEL_NAMES[level]})" if level and not purpose else ""),
        "form": "A",
        "seed": seed,
        "total_marks": 0,
        "is_forecast": False,
        "level_marks": {},
        "questions": questions,
        "level": level or "",
    }


def build_quiz(lesson_codes: list[str], seed: int | None = None, form: str = "A", course: str = "") -> dict:
    """اختبار قصير من 10 لدرس أو درسين: الخانات ثابتة وتتناوب على الدروس، ومستوى غير متاح يُملأ بلا قيد."""
    codes = list(dict.fromkeys(lesson_codes))[:QUIZ_MAX_LESSONS]
    course_row = _resolve_course(course)
    ready = available_lessons(course_row.slug)
    lessons = {row.code: row for row in selectors.lessons(course_row).filter(code__in=codes)}
    if not codes or any(code not in lessons or code not in ready for code in codes):
        raise UnknownLessonError(",".join(lesson_codes))
    seed = new_seed() if seed is None else seed
    if form == "B":
        return build_form_b(build_quiz(codes, seed, course=course_row.slug), course_row.slug)
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    used: set[str] = set()
    questions = []
    level_marks: dict[str, int] = defaultdict(int)
    for index, (kind, level, marks) in enumerate(QUIZ_SLOTS):
        lesson = lessons[codes[index % len(codes)]]
        try:
            problem = generate(lesson.code, rng, kind, used, level, course=course_row.slug)
        except LevelUnavailableError:
            problem = generate(lesson.code, rng, kind, used, course=course_row.slug)
        used.add(problem.key)
        level_marks[problem.level] += marks
        slot = PartSlot("", lesson.code, lesson.title, kind, marks, level, course=course_row.slug)
        questions.append(
            {"number": index + 1, "kind": kind, "marks": marks, "parts": [render_part(problem, slot, rng)]}
        )
    names = " و".join(f"{lessons[code].code} {lessons[code].title}" for code in codes)
    return {
        **paper_meta("quiz", course_row.slug, blueprint="", lesson_code=",".join(codes)),
        "title": f"اختبار قصير: {names}",
        "form": "A",
        "seed": seed,
        "total_marks": sum(marks for _, _, marks in QUIZ_SLOTS),
        "is_forecast": False,
        "level_marks": dict(level_marks),
        "questions": questions,
        "level": "",
    }


def build_form_b(paper_a: dict, course: str = DEFAULT_COURSE) -> dict:
    """النموذج ب من النموذج أ: الخانات نفسها والصيغ نفسها (البنية) بأعداد مختلفة، ولا مسألة مشتركة.

    حتمي من بذرة أ، فيُعاد بالرقم نفسه. صيغة لا تعطي بديلًا جديدًا تُستبدل بأي صيغة مطابقة للخانة.
    """
    rng = random.Random(f"{paper_a['seed']}:B")  # noqa: S311 — حتمية لا أمنية
    avoid = {part["fingerprint"] for q in paper_a["questions"] for part in q["parts"]}
    questions = []
    level_marks: dict[str, int] = defaultdict(int)
    for question in paper_a["questions"]:
        parts = []
        for part in question["parts"]:
            slot = PartSlot(
                part["label"],
                part["lesson"],
                part["lesson_title"],
                part["slot"]["kind"],
                part["marks"],
                part["slot"]["level"],
                part["slot"]["needs_graph"],
                course,
            )
            try:
                problem = generate(
                    slot.lesson,
                    rng,
                    slot.kind,
                    avoid,
                    part["level"],
                    slot.needs_graph,
                    part["variant"],
                    course,
                )
            except (LevelUnavailableError, ExhaustedError):
                problem = generate(
                    slot.lesson, rng, slot.kind, avoid, slot.level or None, slot.needs_graph, course=course
                )
            avoid.add(problem.key)
            avoid.add(problem.fingerprint)
            level_marks[problem.level] += slot.marks
            parts.append(render_part(problem, slot, rng))
        questions.append({**question, "parts": parts})
    return {
        **paper_a,
        "form": "B",
        "level_marks": dict(level_marks) if paper_a["kind"] != "worksheet" else {},
        "questions": questions,
    }


@transaction.atomic
def save_print_profile(user: AbstractBaseUser, data: dict[str, Any]) -> dict[str, Any]:
    """يحفظ ترويسة المعلم (idempotent: الحفظ نفسه مرتين لا يغيّر شيئًا ولا يسجّل تدقيقًا ثانيًا)."""
    row, created = PrintProfile.objects.get_or_create(user=user)
    changed = [name for name in PROFILE_FIELDS if name in data and getattr(row, name) != data[name]]
    for name in changed:
        setattr(row, name, data[name])
    if changed or created:
        row.save()
        record_audit(
            action="print_profile.save", actor=user, target=user.get_username(), payload={"fields": changed}
        )
    return print_profile(user)


def replacement_part(
    lesson_code: str, slot: PartSlot, exclude: set[str], seed: int | None = None, course: str = ""
) -> dict:
    """جزء جديد للخانة نفسها (النوع والمستوى والرسم) يخالف بصمات ما في الورقة. البذرة تعيد الجزء نفسه."""
    course_row = _resolve_course(course)
    lesson = selectors.lessons(course_row).filter(code=lesson_code).first()
    if lesson is None or lesson_code not in available_lessons(course_row.slug):
        raise UnknownLessonError(lesson_code)
    seed = new_seed() if seed is None else seed
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    try:
        problem = generate(
            lesson_code, rng, slot.kind, exclude, slot.level or None, slot.needs_graph, course=course_row.slug
        )
    except LevelUnavailableError:
        logger.warning("خانة الاستبدال %s/%s بلا صيغة مطابقة؛ تُملأ بلا قيد", lesson_code, slot.level)
        problem = generate(lesson_code, rng, slot.kind, exclude, course=course_row.slug)
    full = PartSlot(
        slot.label,
        lesson.code,
        lesson.title,
        slot.kind,
        slot.marks,
        slot.level,
        slot.needs_graph,
        course_row.slug,
    )
    return {**render_part(problem, full, rng), "seed": seed}


# الأوراق المحفوظة: لقطة كاملة (تُطبع كما كانت) ووصفة (كيف وُلّدت وما استُبدل)، والوصفة هي هوية الورقة.
MAX_SAVED_PER_USER = 200


def recipe_hash(recipe: dict) -> str:
    canonical = json.dumps(recipe, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8"), usedforsecurity=False).hexdigest()


def _recipe_course(recipe: dict) -> Course | None:
    """مقرر الوصفة (الفارغ = الحالي)؛ None إن لم يعد موجودًا فلا يمنع ذلك حفظ الورقة."""
    try:
        return selectors.course_by_slug(recipe.get("course", ""))
    except selectors.UnknownCourseError:
        return None


def _summary(snapshot: dict, recipe: dict) -> dict:
    return {
        "course": _recipe_course(recipe),
        "kind": snapshot["kind"],
        "blueprint": snapshot.get("blueprint", ""),
        "lesson_code": snapshot.get("lesson_code", ""),
        "seed": snapshot["seed"],
        "total_marks": snapshot.get("total_marks", 0),
        "question_count": len(snapshot["questions"]),
        "replacement_count": len(recipe.get("replacements", [])),
        "generator_version": snapshot.get("generator_version", ""),
    }


@transaction.atomic
def save_paper(user: AbstractBaseUser, title: str, snapshot: dict, recipe: dict) -> tuple[SavedPaper, bool]:
    """يحفظ ورقة. idempotent: الوصفة نفسها لا تُحفظ مرتين (تُعاد الموجودة وcreated=False)."""
    digest = recipe_hash(recipe)
    existing = SavedPaper.objects.filter(owner=user, recipe_hash=digest).first()
    if existing is not None:
        return existing, False
    if SavedPaper.objects.filter(owner=user).count() >= MAX_SAVED_PER_USER:
        raise SavedLimitError(str(MAX_SAVED_PER_USER))
    row = SavedPaper.objects.create(
        owner=user,
        title=(title or snapshot["title"])[:200],
        recipe_hash=digest,
        snapshot=snapshot,
        recipe=recipe,
        **_summary(snapshot, recipe),
    )
    record_audit(
        action="saved_paper.create",
        actor=user,
        target=str(row.pk),
        payload={"kind": row.kind, "seed": row.seed},
    )
    return row, True


@transaction.atomic
def update_saved_paper(
    user: AbstractBaseUser,
    pk: int,
    *,
    title: str | None = None,
    snapshot: dict | None = None,
    recipe: dict | None = None,
) -> SavedPaper | None:
    """يعيد التسمية أو يحدّث اللقطة بعد استبدال. idempotent: ما لم يتغيّر لا يُكتب ولا يُسجَّل."""
    row = saved_paper(user, pk)
    if row is None:
        return None
    changed: list[str] = []
    if title is not None and title.strip() and title.strip()[:200] != row.title:
        row.title = title.strip()[:200]
        changed.append("title")
    if snapshot is not None and recipe is not None and (snapshot != row.snapshot or recipe != row.recipe):
        digest = recipe_hash(recipe)
        if SavedPaper.objects.filter(owner=user, recipe_hash=digest).exclude(pk=row.pk).exists():
            raise SavedConflictError(digest)
        row.snapshot, row.recipe, row.recipe_hash = snapshot, recipe, digest
        for name, value in _summary(snapshot, recipe).items():
            setattr(row, name, value)
        changed.append("snapshot")
    if changed:
        row.save()
        record_audit(action="saved_paper.update", actor=user, target=str(row.pk), payload={"fields": changed})
    return row


@transaction.atomic
def delete_saved_paper(user: AbstractBaseUser, pk: int) -> bool:
    """idempotent: حذف ما ليس موجودًا (أو ليس للمعلم) لا يفعل شيئًا ولا يكشف شيئًا."""
    row = saved_paper(user, pk)
    if row is None:
        return False
    row.delete()
    record_audit(action="saved_paper.delete", actor=user, target=str(pk))
    return True


# حزمة كل أوراق العمل: عدد كل درس من وزنه في جدول المواصفات (4 + 2×الدرجات، بين 6 و12)،
# والمستويات بنسبها في الجدول مع مسألة واحدة على الأقل من كل مستوى متاح، بترتيب سهل ثم متوسط ثم عليا.
BUNDLE_MIN, BUNDLE_MAX = 6, 12


def split_levels(count: int, available: list[str], weights: dict[str, int]) -> dict[str, int]:
    """يوزّع count على المستويات المتاحة: 1 لكل مستوى ثم الباقي بنسب الأوزان (أكبر البواقي)."""
    plan = dict.fromkeys(available, 1)
    remaining = count - len(available)
    total = sum(weights.get(level, 0) for level in available)
    shares = {
        level: (weights.get(level, 0) / total if total else 1 / len(available)) * remaining
        for level in available
    }
    for level in available:
        plan[level] += int(shares[level])
    leftover = remaining - sum(int(shares[level]) for level in available)
    by_fraction = sorted(available, key=lambda lv: shares[lv] - int(shares[lv]), reverse=True)
    for level in by_fraction[:leftover]:
        plan[level] += 1
    return plan


def bundle_plan(slug: str) -> list[dict]:
    blueprint = selectors.blueprint_with_items(slug)
    if blueprint is None:
        raise UnknownBlueprintError(slug)
    marks: dict[str, int] = defaultdict(int)
    level_marks: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    titles: dict[str, str] = {}
    for item in blueprint.items.all():
        code = item.lesson.code
        titles[code] = item.lesson.title
        marks[code] += item.marks
        if item.level:
            level_marks[code][item.level] += item.marks
    course = _course_slug(blueprint.course)
    ready = available_lessons(course)
    # درس له مولّد وليس في الجدول (3.4 رسم المنحنيات) يدخل الحزمة بالحد الأدنى وبمستويات متساوية
    for row in selectors.lessons(blueprint.course).filter(code__in=ready - set(marks)):
        titles[row.code] = row.title
        marks[row.code] = 0
    plan = []
    for code in sorted(marks):
        if code not in ready:
            continue
        count = min(BUNDLE_MAX, max(BUNDLE_MIN, 4 + 2 * marks[code]))
        # تمهيد +1 لكل مستوى متاح: الجدول يرجّح لا يحتكر (درس يُختبر سهلًا فقط لا يصير 6/1/1)
        found = lesson_levels(code, course=course)
        weights = {level: level_marks[code].get(level, 0) + 1 for level in found}
        levels = split_levels(count, found, weights)
        plan.append({"lesson": code, "title": titles[code], "count": count, "levels": levels})
    return plan


def lesson_seed(bundle_seed: int, lesson_code: str, course: str = DEFAULT_COURSE) -> int:
    """بذرة الدرس مشتقة من بذرة الحزمة: الحزمة نفسها تعيد الأوراق نفسها، وكل ورقة قابلة لإعادة التوليد وحدها.

    صيغة مقرر الثاني عشر كما كانت قبل المقررات حرفيًا (أوراقه المحفوظة تُعاد بالبذرة نفسها)؛ غيره يدخل معرّفه فيها.
    """
    text = (
        f"{bundle_seed}:{lesson_code}"
        if course == DEFAULT_COURSE
        else f"{bundle_seed}:{course}:{lesson_code}"
    )
    return random.Random(text).randrange(MAX_SEED)  # noqa: S311 — حتمية لا أمنية


def build_bundle_item(slug: str, lesson_code: str, bundle_seed: int) -> dict:
    """ورقة درس واحد داخل الحزمة بخطة المستويات من الجدول، مرتبة سهل ثم متوسط ثم عليا، ومخزنة في الكاش."""
    entry = next((row for row in bundle_plan(slug) if row["lesson"] == lesson_code), None)
    if entry is None:
        raise UnknownLessonError(lesson_code)
    blueprint_course = selectors.blueprint_with_items(slug).course  # type: ignore[union-attr]  # تحقق منه bundle_plan
    course = _course_slug(blueprint_course)
    key = f"bundle:{generator_version(course)}:{slug}:{lesson_code}:{bundle_seed}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    lesson = selectors.lessons(blueprint_course).get(code=lesson_code)
    seed = lesson_seed(bundle_seed, lesson_code, course)
    rng = random.Random(seed)  # noqa: S311 — حتمية لا أمنية
    used: set[str] = set()
    questions = []
    for level in LEVEL_NAMES:
        for _ in range(entry["levels"].get(level, 0)):
            problem = generate(lesson.code, rng, BlueprintItem.Kind.ESSAY, used, level, course=course)
            used.add(problem.key)
            slot = PartSlot("", lesson.code, lesson.title, BlueprintItem.Kind.ESSAY, 0, level, course=course)
            part = render_part(problem, slot, rng)
            questions.append({"number": len(questions) + 1, "kind": slot.kind, "marks": 0, "parts": [part]})
    paper = {
        **paper_meta("worksheet", course, blueprint=slug, lesson_code=lesson.code),
        "title": f"ورقة عمل: {lesson.code} {lesson.title}",
        "form": "A",
        "seed": seed,
        "total_marks": 0,
        "is_forecast": False,
        "level_marks": {},
        "level_counts": entry["levels"],
        "questions": questions,
        "level": "",
    }
    cache.set(key, paper, 60 * 60 * 24)
    return paper
