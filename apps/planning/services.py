"""خدمات التخطيط: الورقة العلاجية، وسجلات الحصة، والعروض، ونسخة المعلم من أهداف حصته. لا نص كتاب."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError

from apps.assets.models import Asset
from apps.assets.storage import Storage, get_storage
from apps.core.services import record_audit
from apps.curriculum import selectors as curriculum
from apps.curriculum.models import Lesson
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.unit_prep import PREP_DIR, UnitPrep, course_standards, unit_prep, unit_problems
from apps.knowledge.selectors import course_index
from apps.papers import pdf
from apps.papers import services as papers
from apps.papers.domain.book_source import number_list
from apps.papers.domain.remedial import StudentError, remedial_recipe
from apps.papers.selectors import print_profile

from . import selectors
from .domain.calendar_engine import PlanningError
from .domain.deck import DeckError, build_period_deck
from .domain.deck_checks import check_deck
from .domain.feedback import ClassOutcome, Decision
from .domain.item_results import Entry, clean_entries, mark
from .domain.lesson_run import LessonRun
from .domain.objective_text import (
    ObjectiveLockedError,
    ObjectiveNotFoundError,
    ObjectiveTextError,
    clean_note,
    clean_part,
    shared_digest,
)
from .domain.prep import Objective
from .domain.prep_checks import CheckResult, blocking_failures
from .domain.prep_override import OverrideError, dump_override, parse_override, unknown_removed
from .domain.suggestion_apply import AcceptedSuggestion, ApplyResult, apply_accepted
from .example_clips import merge_short_continuations
from .models import (
    ClassOutcomeRecord,
    DeckBuild,
    ItemResult,
    LessonRunRecord,
    ObjectiveOverride,
    ObjectiveSuggestion,
    PeriodPrepOverride,
    PrepReview,
    SectionStudent,
)
from .pptx_checks import check_pptx
from .pptx_export import build_period_pptx

MAX_PACK_STUDENTS = 40  # حد أوراق صفحة الطباعة (`MAX_BUNDLE_PAPERS` في papers/api.py)
# أسئلة ورقة الطالب في الحزمة: صفحة واحدة. قيس بـ Chromium على دروس العاشر: سؤالان صفحة، وثلاثة تفيض في أغلبها
PACK_MAX_PARTS = 2
REMEDIAL_PER_PERIOD = 5  # أسئلة لكل حصة إعادة تدريس؛ المراجعة السريعة بلا حصة تأخذ حصة واحدة في الحساب


def remedial_worksheet(decision: Decision, seed: int | None = None) -> dict | None:
    """ورقة علاجية (مستوى سهل) للدرس بحسب القرار؛ لا ورقة عند التقدّم. الدرس المجهول يرفع `UnknownLessonError`."""
    if decision.action == "advance":
        return None
    count = REMEDIAL_PER_PERIOD * max(decision.extra_periods, 1)
    return papers.build_worksheet(decision.lesson_id, count, seed, purpose="remedial")


def _section(value: str) -> str:
    section = value.strip()
    if not section or len(section) > 20:
        raise PlanningError("الشعبة مطلوبة وبحد أقصى 20 حرفًا")
    return section


def _lesson(course: str, code: str) -> Lesson:
    """درس السجل في مقرره؛ الرمز وحده لا يكفي فهو يتكرر بين الكتب."""
    try:
        lesson = curriculum.lessons(curriculum.course_by_slug(course)).filter(code=code).first()
    except curriculum.UnknownCourseError as error:
        raise PlanningError(f"المقرر غير موجود: {course}") from error
    if lesson is None:
        raise PlanningError(f"الدرس {code} غير موجود في المقرر {course}")
    return lesson


def record_outcome(
    owner: AbstractBaseUser, section: str, outcome: ClassOutcome, course: str = selectors.PLAN_COURSE
) -> tuple[ClassOutcomeRecord, bool]:
    """يحفظ آخر نتيجة لشعبة في درس من مقرر؛ idempotent: التكرار يحدّث السجل نفسه ولا يضاعفه."""
    return ClassOutcomeRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson=_lesson(course, outcome.lesson_id),
        defaults={
            "attempted": outcome.attempted,
            "correct": outcome.correct,
            "pace": outcome.pace,
            "obstacles": sorted(outcome.obstacles),
        },
    )


def save_run_report(
    owner: AbstractBaseUser,
    section: str,
    lesson_code: str,
    run: LessonRun,
    started_at: datetime,
    course: str = selectors.PLAN_COURSE,
) -> tuple[LessonRunRecord, bool]:
    """يحفظ تقرير حصة (المخطط مقابل الفعلي لكل طور)؛ المفتاح بداية الحصة فتكرار الحفظ لا يضاعف التقرير."""
    return LessonRunRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson=_lesson(course, lesson_code),
        started_at=started_at,
        defaults={
            "period_minutes": run.flow.period_minutes,
            "finished": run.finished,
            "phases": [
                {"phase": c.phase, "planned": c.planned, "actual": round(c.actual, 2), "skipped": c.skipped}
                for c in run.closed
            ],
        },
    )


# ───── تشخيص الخطأ: نتيجة الطالب لكل بند (قرار المالك 2026-11-25) ─────


@dataclass(frozen=True)
class ResultsSaved:
    """أعداد دفعة نتائج: طلابها وبنودها، وما أُنشئ منها وما تغيّر. بلا أسماء، فتصلح لسجل التدقيق كما هي."""

    students: int
    results: int
    created: int
    updated: int


def results_target(course: str, lesson: str, section: str) -> str:
    """هدف سجل التدقيق لنتائج شعبة في درس: المقرر والدرس والشعبة، بلا طالب."""
    return f"{course}/{lesson}@{section}"


@transaction.atomic
def record_item_results(
    owner: AbstractBaseUser,
    course: str,
    lesson: str,
    section: str,
    entries: Iterable[Entry],
    *,
    request_id: str = "",
) -> ResultsSaved:
    """يحفظ نتائج شعبة في بنود درس دفعة واحدة؛ idempotent: إعادة الإدخال نفسه لا تضيف صفًّا ولا تغيّر صفًّا.

    الطالب مفتاحه (المعلم، الشعبة، رقم القيد) واسمه يُحدَّث، والنتيجة مفتاحها (الطالب، الدرس، المثال، البذرة) وخيارها
    يُحدَّث. الصحة ونوع الخطأ من بنك البنود وحده (`item_results.mark`). السجل في AuditLog أعداد فقط بلا أسماء ولا أرقام قيد."""
    section = _section(section)
    record = _lesson(course, lesson)
    marked = mark(course, record.code, clean_entries(entries))
    wanted = {m.entry.enrollment_no: (m.entry.first_name, m.entry.last_name) for m in marked}
    roster = SectionStudent.objects.filter(owner=owner, section=section, enrollment_no__in=wanted)
    known = {s.enrollment_no: (s.first_name, s.last_name) for s in roster}
    SectionStudent.objects.bulk_create(
        [
            SectionStudent(owner=owner, section=section, enrollment_no=no, first_name=first, last_name=last)
            for no, (first, last) in wanted.items()
            if known.get(no) != (first, last)
        ],
        update_conflicts=True,
        unique_fields=["owner", "section", "enrollment_no"],
        update_fields=["first_name", "last_name", "updated_at"],
    )
    students = {s.enrollment_no: s for s in roster.all()}
    stored = {
        (r.student_id, r.example, r.seed): r.choice
        for r in ItemResult.objects.filter(student__in=students.values(), lesson=record)
    }
    rows, created = [], 0
    for m in marked:
        student = students[m.entry.enrollment_no]
        previous = stored.get((student.pk, m.entry.example, m.entry.seed))
        if previous == m.entry.choice:
            continue
        created += previous is None
        rows.append(
            ItemResult(
                student=student,
                lesson=record,
                example=m.entry.example,
                seed=m.entry.seed,
                choice=m.entry.choice,
                correct=m.correct,
                error_kind=m.error_kind,
            )
        )
    ItemResult.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["student", "lesson", "example", "seed"],
        update_fields=["choice", "correct", "error_kind", "updated_at"],
    )
    saved = ResultsSaved(
        students=len(wanted), results=len(marked), created=created, updated=len(rows) - created
    )
    record_audit(
        action="results.record",
        actor=owner,
        target=results_target(course, record.code, section),
        payload=asdict(saved),
        request_id=request_id,
    )
    return saved


# ───── حزمة الشعبة العلاجية (M2.2): ملف PDF واحد، صفحة لكل طالب أخطأ، ثم مفاتيحهم مجمَّعة ─────
PDF_CONTENT_TYPE = "application/pdf"
PACK_FILE, PACK_STAMP = "pack.pdf", "digest"
PACK_LOCK_SECONDS = 600


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _pack_folder(owner_id: int, course: str, lesson: str, section: str) -> str:
    """مجلد حزمة (المعلم، المقرر، الدرس، الشعبة) في التخزين: تجزئة فلا يظهر في اسم الملف أي بيان."""
    return f"remedial/{_digest([owner_id, course, lesson, section])[:32]}"


def class_pack_payload(
    owner: AbstractBaseUser, course: str, lesson: str, section: str, date: str = ""
) -> dict:
    """حمولة طباعة الحزمة: ورقة لكل طالب أخطأ في الدرس (بترتيب رقم القيد) واسمه بجوارها لا داخلها. حتمية من مدخلاتها.

    الطالب الذي لا صيغة لأي من أخطائه بلا ورقة. `PlanningError` حين لا ورقة تُبنى أو تجاوز عددها حد الملف."""
    sheets, names = [], []
    for student in selectors.class_errors(owner, course, lesson, section):
        number = student["enrollment_no"]
        seed = int(_digest([course, lesson, section, number])[:12], 16) % papers.MAX_SEED
        errors = [StudentError(**e) for e in student["errors"]]
        recipe = remedial_recipe(course, errors, seed, max_parts=PACK_MAX_PARTS)
        if recipe.empty:
            continue
        sheets.append(papers.remedial_paper(recipe, lesson))
        names.append(f"{student['first_name']} {student['last_name']} ({number})")
    if not sheets:
        raise PlanningError("لا أخطاء في هذا الدرس تُبنى منها أوراق علاجية")
    if len(sheets) > MAX_PACK_STUDENTS:
        raise PlanningError(f"الحزمة تتسع لـ {MAX_PACK_STUDENTS} طالبًا")
    return {
        "papers": sheets,
        "students": names,
        "profile": print_profile(owner),
        "date": date,
        "section": section,
        "show_key": True,  # المفاتيح كلها بعد الأوراق: مفتاح المعلم المجمَّع
        "bubble": False,
    }


def build_class_pack(
    owner: AbstractBaseUser,
    course: str,
    lesson: str,
    section: str,
    date: str = "",
    *,
    storage: Storage | None = None,
) -> str:
    """يبني ملف الحزمة ويضعه في التخزين ويعيد مفتاحه. idempotent: تجزئة الحمولة تُحفظ بجانبه، فالمدخلات نفسها لا تعيد بناءه.

    ملف واحد للشعبة في الدرس بمفتاح ثابت: تغيّر المدخلات يستبدله، وزوال ما تُبنى منه الأوراق يحذفه، ويحذفه
    `purge_ended_results` مع النتائج. قفل في الكاش المشترك يمنع بناءين معًا للملف نفسه. سجل التدقيق عدد الأوراق وحده."""
    storage = storage or get_storage()
    section = _section(section)
    scope = (owner.pk, course, lesson, section)
    folder = _pack_folder(*scope)
    lock = f"class-pack:{folder}"
    if not cache.add(lock, 1, PACK_LOCK_SECONDS):
        raise PlanningError("الحزمة قيد البناء")
    try:
        try:
            payload = class_pack_payload(owner, course, lesson, section, date)
        except PlanningError:
            _delete_class_packs([scope], storage)  # لا ملف قديمًا بأسماء وأخطاء لم تعد قائمة
            raise
        key, stamp, digest = f"{folder}/{PACK_FILE}", f"{folder}/{PACK_STAMP}", _digest(payload)
        if storage.exists(stamp) and storage.get(stamp).decode("ascii") == digest and storage.exists(key):
            return key
        data = pdf.render_payload(payload)
        # البصمة تُزال قبل الملف وتُكتب بعده: موت العامل بينهما يعيد البناء ولا يترك ملفًا لا يعرفه الحذف
        storage.delete(stamp)
        storage.put(key, data, PDF_CONTENT_TYPE)
        storage.put(stamp, digest.encode("ascii"), "text/plain")
    finally:
        cache.delete(lock)
    record_audit(
        action="remedial.pack.build",
        actor=owner,
        target=results_target(course, lesson, section),
        payload={"sheets": len(payload["papers"])},
    )
    return key


def _delete_class_packs(scopes: Iterable[tuple[int, str, str, str]], storage: Storage) -> None:
    for scope in scopes:
        folder = _pack_folder(*scope)
        storage.delete(f"{folder}/{PACK_STAMP}")
        storage.delete(f"{folder}/{PACK_FILE}")


@dataclass(frozen=True)
class ResultsPurged:
    years: tuple[str, ...]
    students: int
    results: int


@transaction.atomic
def purge_ended_results(today: date | None = None, *, write: bool = True) -> ResultsPurged:
    """يحذف نتائج البنود لمقررات انتهت سنتها الأكاديمية (آخر فصل في `AcademicCalendar` قبل اليوم) وطلابها الذين لم تبقَ
    لهم نتيجة في سنة جارية؛ idempotent، و`write=False` يعدّ بلا حذف.

    أعداد `ClassOutcomeRecord` المجمَّعة لا تُمسّ: لا بيان فرديًا فيها. سنة بلا تقويم لا تُعدّ منتهية فلا يُحذف منها شيء."""
    years = tuple(curriculum.ended_academic_years(today or timezone.localdate()))
    if not years:
        return ResultsPurged((), 0, 0)
    ended = ItemResult.objects.filter(lesson__course__academic_year__in=years)
    current = ItemResult.objects.exclude(lesson__course__academic_year__in=years)
    leaving = SectionStudent.objects.exclude(pk__in=current.values("student_id"))
    purged = ResultsPurged(years, leaving.count(), ended.count())
    if write and (purged.students or purged.results):
        # ملفات الحزم العلاجية تحمل أسماء الطلاب فتُحذف معها؛ فشل التخزين يُبقي الصفوف فيُعاد المحو كله
        scopes = ended.values_list(
            "student__owner_id", "lesson__course__slug", "lesson__code", "student__section"
        )
        _delete_class_packs(scopes.order_by().distinct(), get_storage())
        ended.delete()
        leaving.delete()
        record_audit(
            action="results.purge",
            target=",".join(years),
            payload={"students": purged.students, "results": purged.results},
        )
    return purged


# ───── عرض الحصة من تحضيرها ومقاطع الأصول المنشورة (المرحلة 4 من docs/lesson_prep_plan.md) ─────
def _error_key(key: str) -> str:
    return f"{key}.error"


def _deck_failure(results: Iterable[CheckResult]) -> str:
    return "؛ ".join(f"{r.code}: {r.details[0]}" if r.details else r.code for r in blocking_failures(results))


def _prepared(
    course: str, lesson: str, k: int, owner: AbstractBaseUser | None = None
) -> tuple[selectors.PreparedPeriod, list[Asset], str]:
    """الحصة (بتحضير المعلم إن أُعطي) وأصولها ومفتاح ملفها؛ `PrepNotFoundError` لحصة مجهولة و`DeckError` برسالة عربية لما
    يمنع البناء. لا يكتب شيئًا."""
    item = selectors.period_item(course, lesson, k, owner)
    if blocking_failures(item.checks):
        raise DeckError(f"تحضير الحصة لم يجتز معاييره الحاجبة: {_deck_failure(item.checks)}")
    numbers = [e.n for e in item.prep.examples]
    assets = selectors.deck_assets(course, lesson, numbers)
    missing = sorted(set(numbers) - {a.number for a in assets if a.kind == "example"})
    if missing:
        raise DeckError(f"لا مقاطع منشورة للأمثلة {number_list(missing)} من الدرس {lesson}")
    return item, assets, selectors.deck_key(item.prep, assets)


def prepare_deck(course: str, lesson: str, k: int, owner: AbstractBaseUser | None = None) -> str:
    """يتحقق من طلب عرض الحصة ويعيد مفتاح ملفه في التخزين."""
    return _prepared(course, lesson, k, owner)[2]


def record_deck_build(owner: AbstractBaseUser, course: str, lesson: str, k: int, key: str) -> None:
    """يسجّل مفتاح آخر عرض طلبه المعلم للحصة (idempotent): مخالفته مفتاحَ تحضيره بعدُ تعني أن العرض قديم."""
    record = Lesson.objects.get(course__slug=course, code=lesson)
    DeckBuild.objects.update_or_create(owner=owner, lesson=record, k=k, defaults={"key": key})


def deck_state(key: str, storage: Storage | None = None) -> tuple[str, str]:
    """حالة التوليد من التخزين وحده: (ready, "") أو (failed, سبب) أو (pending, ""). بلا جدول مهام فتصمد لإعادة تشغيل العامل."""
    storage = storage or get_storage()
    if storage.exists(key):
        return "ready", ""
    if storage.exists(_error_key(key)):
        return "failed", storage.get(_error_key(key)).decode("utf-8")
    return "pending", ""


def build_period_deck_file(
    course: str, lesson: str, k: int, storage: Storage | None = None, owner: AbstractBaseUser | None = None
) -> str:
    """يبني ملف PPTX للحصة ويضعه في التخزين تحت مفتاحه المشتق؛ idempotent: الملف الموجود لا يُعاد بناؤه.

    المدخل تحضير الحصة (المشترك، أو تحضير المعلم بتعديله) ومقاطع أمثلتها من طبقة الأصول، والتتمة القصيرة تُضمّ إلى ما قبلها
    (`merge_short_continuations`) فتُرسم معه في شريحة واحدة. معايير النموذج (S1 إلى S13) ثم معايير الملف (S7 وS8 وS12)
    تُفحص قبل الكتابة، والحاجب الفاشل يُسجَّل سببًا في التخزين فتقرؤه الحالة ولا يُكتب ملف."""
    storage = storage or get_storage()
    item, assets, key = _prepared(course, lesson, k, owner)
    if storage.exists(key):
        return key
    try:
        clips = selectors.clips_of(assets, storage)
        deck = build_period_deck(item.prep, clips, merge_short_continuations(clips))
        if deck.key != key:
            raise DeckError("مقطع في التخزين لا يطابق تجزئته في فهرس الأصول")
        data = build_period_pptx(deck)
        results = (
            *check_deck(deck, item.prep, clips, item.checks),
            *check_pptx(data, build_period_pptx(deck)),
        )
        if blocking_failures(results):
            raise DeckError(f"العرض لم يجتز معاييره: {_deck_failure(results)}")
    except Exception as error:
        message = str(error) if isinstance(error, PlanningError) else "تعذّر بناء العرض"
        storage.put(_error_key(key), message.encode("utf-8"), "text/plain; charset=utf-8")
        raise
    storage.put(key, data, selectors.PPTX_CONTENT_TYPE)
    if storage.exists(_error_key(key)):
        storage.delete(_error_key(key))
    return key


def build_course_decks(course: str, storage: Storage | None = None) -> tuple[int, tuple[str, ...]]:
    """يبني عرض كل حصة دروس في خطة المقرر: (عدد الناجح، أسباب الفاشل بحصته). idempotent كبناء الحصة الواحدة.

    شاهد المقاطع المنشورة على معايير العروض كلها؛ المقرر بلا خطة يرفع `PrepNotFoundError`."""
    built, failures = 0, []
    for row in selectors.prep_periods(course):
        if row["kind"] != "lesson":  # عروض حصص غير الدروس لاحقًا بقرار مستقل (`domain/non_lesson.py`)
            continue
        try:
            build_period_deck_file(course, row["lesson"], row["k"], storage)
        except PlanningError as error:
            failures.append(f"{row['lesson']} حصة {row['k']}: {error}")
        else:
            built += 1
    return built, tuple(failures)


def clear_deck_failure(key: str, storage: Storage | None = None) -> None:
    """يمحو أثر فشل سابق قبل إعادة المحاولة فلا تبقى الحالة «failed» أثناء المحاولة الجديدة."""
    storage = storage or get_storage()
    if storage.exists(_error_key(key)):
        storage.delete(_error_key(key))


# ───── تعديل المعلم لتحضير حصص درس (docs/lesson_prep_plan.md، المرحلة 6) ─────


def _lesson_items(items: Iterable[selectors.PreparedPeriod], lesson: str) -> list[selectors.PreparedPeriod]:
    return [i for i in items if i.prep.lesson == lesson]


@transaction.atomic
def save_prep_override(
    owner: AbstractBaseUser, course: str, lesson: str, data: object, *, request_id: str = ""
) -> dict:
    """يحفظ تعديل المعلم لحصص الدرس بشكله القانوني ويعيده؛ idempotent، والتعديل الذي لا يغيّر شيئًا يحذف السجل.

    يُرفض (`OverrideError` برسالة عربية) ما لا يطابق المخطط أو قواعد التوزيع والمكتبة، وحذف تمرين ليس من تمارين الحصة، وما
    يُفشل معيارًا حاجبًا لم يكن فاشلًا في التحضير المشترك: التعديل لا يتجاوز معيارًا حاجبًا."""
    record = Lesson.objects.filter(course__slug=course, code=lesson).first()
    shared = _lesson_items(selectors.lesson_preps(course), lesson)
    if record is None or not shared:
        raise selectors.PrepNotFoundError(f"لا حصص للدرس {lesson} في خطة {course}")
    mine = _lesson_items(selectors.lesson_preps(course, {lesson: data}, strict=True), lesson)
    default = shared[0].default_allocation
    parsed = parse_override(
        data, examples=[x for g in default for x in g], n=len(default), library=selectors.load_library()
    )
    for item in mine:
        edit = parsed.periods.get(item.prep.k)
        available = {x for e in item.prep.practice_examples for _, ex in e.all_rows for x in ex}
        unknown = unknown_removed(edit.removed if edit else (), available)
        if unknown:
            raise OverrideError(
                f"الحصة {item.prep.k}: التمارين {number_list(list(unknown))} ليست من تمارين أمثلتها"
            )
    before = {(i.prep.k, r.code) for i in shared for r in blocking_failures(i.checks)}
    new = [
        (i.prep.k, r) for i in mine for r in blocking_failures(i.checks) if (i.prep.k, r.code) not in before
    ]
    if new:
        reasons = "؛ ".join(f"الحصة {k}: {_deck_failure([r])}" for k, r in new)
        raise OverrideError(f"التعديل يُفشل معيارًا حاجبًا فلم يُحفظ: {reasons}")
    canonical = dump_override(parsed, default)
    existing = PeriodPrepOverride.objects.filter(owner=owner, lesson=record).first()
    previous = existing.data if existing else {}
    if canonical == previous:
        return canonical
    if canonical:
        PeriodPrepOverride.objects.update_or_create(owner=owner, lesson=record, defaults={"data": canonical})
    elif existing:
        existing.delete()
    record_audit(
        action="prep.override.save" if canonical else "prep.override.reset",
        actor=owner,
        target=_target(course, lesson),
        payload={"before": previous, "after": canonical},
        request_id=request_id,
    )
    return canonical


def save_period_override(
    owner: AbstractBaseUser,
    course: str,
    lesson: str,
    k: int,
    *,
    allocation: list[list[int]] | None = None,
    strategies: dict[str, str] | None = None,
    removed: list[int] | None = None,
    request_id: str = "",
) -> dict:
    """تعديل حصة واحدة يُدمج في المحفوظ للدرس: اختيارات الحصة `k` تحل محل المحفوظ لها، والتوزيع (إن أُعطي) محل المحفوظ،
    وباقي الحصص كما هي؛ ثم الحفظ بقواعد `save_prep_override` كلها."""
    record = PeriodPrepOverride.objects.filter(
        owner=owner, lesson__course__slug=course, lesson__code=lesson
    ).first()
    data = dict(record.data) if record else {}
    periods = dict(data.get("periods", {}))
    periods[str(k)] = {"strategies": dict(strategies or {}), "removed": list(removed or [])}
    data["periods"] = periods
    if allocation is not None:
        data["allocation"] = allocation
    return save_prep_override(owner, course, lesson, data, request_id=request_id)


def reset_prep_override(owner: AbstractBaseUser, course: str, lesson: str, *, request_id: str = "") -> None:
    """يعيد حصص الدرس إلى التحضير المشترك (idempotent)."""
    save_prep_override(owner, course, lesson, {}, request_id=request_id)


# ───── مراجعة المعلم لأهداف حصته (docs/teacher_objective_review_plan.md) ─────


class SuggestionDecidedError(PlanningError):
    """قرار الاقتراح نهائي: لا يُقرَّر مرتين."""


def _target(course: str, lesson: str, example: int | None = None, k: int | None = None) -> str:
    tail = f"/{k}" if k is not None else ""
    return f"{course}/{lesson}{tail}" + (f"#{example}" if example is not None else "")


def _editable_objective(course: str, lesson: str, k: int, example: int) -> Objective:
    """الهدف المعتمد لمثال في الحصة؛ `ObjectiveNotFoundError` إن لم يكن فيها، و`ObjectiveLockedError` قبل اعتماد وحدتها."""
    item = selectors.period_item(course, lesson, k)
    objective = next((o for o in item.prep.objectives if o.example == example), None)
    if objective is None:
        raise ObjectiveNotFoundError(f"لا هدف للمثال {example} في الحصة {k} من الدرس {lesson}")
    if item.prep.unit_status != "approved" or not all(objective.parts):
        raise ObjectiveLockedError(f"أهداف الوحدة {item.prep.unit} لم تُعتمد بعد فلا تُعدَّل")
    return objective


@transaction.atomic
def save_objective(
    owner: AbstractBaseUser,
    course: str,
    lesson: str,
    k: int,
    example: int,
    *,
    condition: str,
    criterion: str,
    suggest: bool = False,
    note: str | None = None,
    request_id: str = "",
) -> None:
    """يحفظ نسخة المعلم من شرط الهدف ومعياره (idempotent). النسخة المساوية للمعتمد تُحذف، ومع `suggest` تُرسَل
    لقطة اقتراح تحل محل اقتراحه المعلّق للمثال نفسه."""
    shared = _editable_objective(course, lesson, k, example)
    condition = clean_part(condition, "الشرط")
    criterion = clean_part(criterion, "المعيار")
    note = clean_note(note)
    record = _lesson(course, lesson)
    key = {"owner": owner, "lesson": record, "example": example}
    previous = ObjectiveOverride.objects.filter(**key).first()
    before = (previous.condition, previous.criterion) if previous else (shared.condition, shared.criterion)
    same_as_shared = (condition, criterion) == (shared.condition, shared.criterion)
    if suggest and same_as_shared:
        raise ObjectiveTextError("الاقتراح يطابق النص المعتمد")
    if same_as_shared:
        ObjectiveOverride.objects.filter(**key).delete()
    else:
        ObjectiveOverride.objects.update_or_create(
            **key,
            defaults={"condition": condition, "criterion": criterion, "base_digest": shared_digest(shared)},
        )
    target = _target(course, lesson, example)
    if before != (condition, criterion):
        record_audit(
            action="prep.objective.save",
            actor=owner,
            target=target,
            payload={"before": list(before), "after": [condition, criterion]},
            request_id=request_id,
        )
    if suggest:
        pending = ObjectiveSuggestion.objects.filter(**key, decision=ObjectiveSuggestion.PENDING).first()
        if pending and (pending.condition, pending.criterion, pending.note) == (condition, criterion, note):
            return
        if pending:
            pending.delete()
        ObjectiveSuggestion.objects.create(
            **key, condition=condition, criterion=criterion, note=note, base_digest=shared_digest(shared)
        )
        record_audit(
            action="prep.objective.suggest",
            actor=owner,
            target=target,
            payload={"condition": condition, "criterion": criterion, "note": note},
            request_id=request_id,
        )


def reset_objective(
    owner: AbstractBaseUser, course: str, lesson: str, k: int, example: int, *, request_id: str = ""
) -> None:
    """يسترجع النص المعتمد بحذف نسخة المعلم (idempotent)؛ اقتراحه المعلّق يبقى."""
    item = selectors.period_item(course, lesson, k)
    if example not in {o.example for o in item.prep.objectives}:
        raise ObjectiveNotFoundError(f"لا هدف للمثال {example} في الحصة {k} من الدرس {lesson}")
    deleted, _ = ObjectiveOverride.objects.filter(
        owner=owner, lesson=_lesson(course, lesson), example=example
    ).delete()
    if deleted:
        record_audit(
            action="prep.objective.reset",
            actor=owner,
            target=_target(course, lesson, example),
            request_id=request_id,
        )


def mark_reviewed(owner: AbstractBaseUser, course: str, lesson: str, k: int, *, request_id: str = "") -> None:
    """علامة «راجعتُ أهداف الحصة» ببصمة نصوصها كما يراها المعلم الآن (idempotent: التكرار يحدّث العلامة)."""
    sheet = selectors.teacher_sheet(course, lesson, k, owner).sheet
    PrepReview.objects.update_or_create(
        owner=owner,
        lesson=_lesson(course, lesson),
        k=k,
        defaults={"digest": selectors.sheet_digest(sheet), "reviewed_at": timezone.now()},
    )
    record_audit(
        action="prep.review", actor=owner, target=_target(course, lesson, k=k), request_id=request_id
    )


@transaction.atomic
def decide_suggestion(
    actor: AbstractBaseUser, suggestion_id: int, decision: str, note: str | None = None
) -> ObjectiveSuggestion:
    """قرار المالك في اقتراح معلم: قبول أو رفض نهائي. القبول لا يكتب ملف الوحدة؛ ذلك أمر
    `apply_objective_suggestions` ثم طلب دمج يعتمده المالك."""
    if not actor.has_perm("planning.decide_objective_suggestion"):
        raise PermissionError("قرار الاقتراحات للمالك وحده")
    if decision not in (ObjectiveSuggestion.ACCEPTED, ObjectiveSuggestion.REJECTED):
        raise PlanningError(f"قرار غير معروف: {decision}")
    row = (
        ObjectiveSuggestion.objects.select_for_update().select_related("lesson__course").get(pk=suggestion_id)
    )
    if row.decision != ObjectiveSuggestion.PENDING:
        raise SuggestionDecidedError(f"الاقتراح {row.pk} قُرِّر من قبل: {row.get_decision_display()}")
    row.decision = decision
    row.decided_by = actor
    row.decided_at = timezone.now()
    row.decision_note = clean_note(note)
    row.save(update_fields=["decision", "decided_by", "decided_at", "decision_note", "updated_at"])
    record_audit(
        action="prep.suggestion.decide",
        actor=actor,
        target=_target(row.lesson.course.slug, row.lesson.code, row.example),
        payload={"suggestion": row.pk, "decision": decision, "note": row.decision_note},
    )
    return row


def apply_objective_suggestions(
    course: str, unit: int, *, root: Path = COURSES_DIR, today: date | None = None, write: bool = True
) -> ApplyResult:
    """يكتب الاقتراحات المقبولة لوحدة في `prep/unit-<n>.json` (الشرط والمعيار وحدهما) ويحدّث سطر الاعتماد بتاريخ اليوم.
    يتحقق من الناتج بمخطط `UnitPrep` ومطابقته للفهرس (`unit_problems`) قبل الكتابة، ولا يمس الملف إن لم يتغير شيء
    (idempotent). الكتابة محلية في المستودع، ثم طلب دمج يعتمده المالك؛ `write=False` معاينة بلا كتابة."""
    path = root / course / PREP_DIR / f"unit-{unit}.json"
    if not path.is_file():
        raise PlanningError(f"لا ملف للوحدة {unit} في المقرر {course}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if UnitPrep.model_validate(raw).status != "approved":
        raise PlanningError(f"الوحدة {unit} مسودة: لا اقتراحات تُطبَّق على وحدة غير معتمدة")
    rows = (
        ObjectiveSuggestion.objects.filter(
            decision=ObjectiveSuggestion.ACCEPTED, lesson__course__slug=course, lesson__unit=unit
        )
        .select_related("lesson")
        .order_by("decided_at", "id")
    )
    accepted = [
        AcceptedSuggestion(
            suggestion=row.pk,
            lesson=row.lesson.code,
            example=row.example,
            condition=row.condition,
            criterion=row.criterion,
            base_digest=row.base_digest,
        )
        for row in rows
    ]
    result = apply_accepted(raw, accepted, today or timezone.localdate())
    if not result.changed:
        return result
    try:
        data = UnitPrep.model_validate(result.raw)
    except ValidationError as error:
        raise PlanningError(f"ملف الوحدة بعد التطبيق يخالف المخطط: {error}") from error
    plan = selectors.term_plan(course)
    problems = unit_problems(
        data,
        course_index(course).lessons,
        plan.enrichment_lessons,
        plan.enrichment_examples,
        course_standards(course, root),
    )
    if problems:
        raise PlanningError("ملف الوحدة بعد التطبيق لا يطابق الفهرس: " + "؛ ".join(problems))
    if write:
        path.write_text(json.dumps(result.raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        unit_prep.cache_clear()
        course_standards.cache_clear()
        record_audit(
            action="prep.suggestion.apply",
            target=f"{course}/unit-{unit}",
            payload={"suggestions": [item.suggestion for item in result.applied]},
        )
    return result
