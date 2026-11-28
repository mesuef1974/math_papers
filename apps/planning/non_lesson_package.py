"""باقة حصة غير الدرس (المرحلة 4 من docs/lesson_package_plan.md): أوراق الحصة المربوطة (`NonLessonPrep.papers`)
ملفاتٍ جاهزة: لكل ورقة PDF للطالب وآخر بمفتاحه للمعلم. البذرة من هوية الحصة فالطلب مرتين يعطي المحتوى نفسه."""

from __future__ import annotations

import hashlib

from apps.papers import services as papers
from apps.papers.domain.generators import LevelUnavailableError

from .domain.non_lesson import NonLessonPrep, PaperLink

WORKSHEET_COUNT = 8  # عدد مسائل صفحة التوليد الافتراضي
KEYED_SUFFIX = " (بمفتاحه)"
# ما يعني أن مولّدات المقرر لا تكفي الورقة: تُذكر في الفهرس ولا توقف الباقة
UNAVAILABLE = (
    papers.UnknownBlueprintError,
    papers.BlueprintNotReadyError,
    papers.UnknownLessonError,
    LevelUnavailableError,
)


def paper_seed(prep: NonLessonPrep, order: int) -> int:
    raw = f"{prep.course}:{prep.slug}:{prep.k}:{order}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % papers.MAX_SEED


def _content(course: str, link: PaperLink, seed: int) -> dict:
    """أوراق رابط واحد كما تقرؤها صفحة الطباعة."""
    if link.kind == "quiz":
        return {"papers": [papers.build_quiz(list(link.lessons), seed, course=course)]}
    if link.kind == "worksheet":
        level = link.level or None
        paper = papers.build_worksheet(link.lessons[0], WORKSHEET_COUNT, seed, level, course=course)
        return {"papers": [paper]}
    if link.kind == "exam":
        return {"papers": [papers.build_exam(link.blueprint, seed)]}
    plan = papers.bundle_plan(link.blueprint)
    return {
        "papers": [papers.build_bundle_item(link.blueprint, row["lesson"], seed) for row in plan],
        "bundle": {"plan": plan, "seed": seed},
    }


def print_payloads(prep: NonLessonPrep, profile: dict) -> tuple[list[tuple[str, dict]], list[str]]:
    """(اسم الملف دون امتداد، حمولة طباعته) لكل ورقة ونسخة مفتاحها، وسبب كل ورقة تعذّرت."""
    base = {"profile": profile, "date": "", "section": "", "bubble": False}
    payloads: list[tuple[str, dict]] = []
    missing: list[str] = []
    for order, link in enumerate(prep.papers, start=1):
        try:
            content = _content(prep.course, link, paper_seed(prep, order))
        except UNAVAILABLE:
            missing.append(f"تعذّر توليد «{link.label}»: مولّداتها غير مكتملة")
            continue
        name = f"{order}- {link.label.replace(':', ' -')}"
        payloads.append((name, {**base, **content, "show_key": False}))
        payloads.append((name + KEYED_SUFFIX, {**base, **content, "show_key": True}))
    return payloads, missing
