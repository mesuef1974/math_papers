"""نموذج عرض الدرس: شرائح حتمية من الفهرس المشتق وسير الحصة، بلا Django ولا نص دليل في المستودع.

نصوص الأهداف والمصطلحات وصور الأمثلة المقصوصة من الكتاب محتوى محميّ يبقى خارج المستودع (قاعدة نطاق المحتوى)؛ فهي مدخلات
`LessonContent` يمرّرها المعلم محليًا. ما يُشتق هنا فقط: ترتيب الشرائح، وتمثيلات كل مثال وعمق تمارينه من الفهرس، وسير الحصة
بدقائقه، وملخص اختبار الدرس. الناقص لا يُخمَّن: مدخل فارغ لا تُرسم له شريحة، ومثال مقصوص رقمه خارج الفهرس خطأ لا تجاهل.
التصدير في `pptx_export.py` وهو وحده يعرف شكل الملف.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from apps.knowledge.domain.grade10_index import Grade10Lesson

from .calendar_engine import PlanningError
from .strategies import Flow

PHASE_LABELS = {
    "opening": "التهيئة",
    "explore": "الاستكشاف",
    "explain": "الشرح",
    "practice": "التدريب",
    "check": "الفحص",
    "close": "الإغلاق",
}
REPRESENTATION_LABELS = {
    "بياني": "بياني",
    "جبري": "جبري",
    "سياق": "سياق حياتي",
    "جدولي": "جدولي",
    "لفظي": "لفظي",
}


class DeckError(PlanningError):
    """مدخل لا يصلح لبناء عرض."""


@dataclass(frozen=True)
class ExampleClip:
    """مثال مقصوص من صفحة الكتاب: صورة PNG بأبعادها ورقم المثال في الدرس."""

    n: int
    png: bytes
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise DeckError(f"أبعاد صورة المثال {self.n} غير صالحة")
        if not self.png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DeckError(f"صورة المثال {self.n} ليست PNG")


@dataclass(frozen=True)
class LessonContent:
    """ما يضعه المعلم من نصوصه المحلية: عنوان الدرس وأهدافه ومصطلحاته (عربي، إنجليزي) والأمثلة المقصوصة."""

    title: str
    objectives: tuple[str, ...] = ()
    vocabulary: tuple[tuple[str, str], ...] = ()
    examples: tuple[ExampleClip, ...] = ()


@dataclass(frozen=True)
class TitleSlide:
    title: str
    subtitle: str


@dataclass(frozen=True)
class BulletsSlide:
    title: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class TableSlide:
    title: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    footnote: str = ""


@dataclass(frozen=True)
class ExampleSlide:
    title: str
    clip: ExampleClip
    notes: tuple[str, ...]


Slide = TitleSlide | BulletsSlide | TableSlide | ExampleSlide


@dataclass(frozen=True)
class Deck:
    lesson: str
    slides: tuple[Slide, ...]


def _example_notes(lesson: Grade10Lesson, n: int) -> tuple[str, ...]:
    indexed = next((e for e in lesson.examples if e.n == n), None)
    if indexed is None:
        raise DeckError(f"المثال {n} غير موجود في الدرس {lesson.lesson} بالفهرس")
    notes: list[str] = []
    if indexed.representations:
        notes.append(
            "التمثيلات: " + "، ".join(REPRESENTATION_LABELS.get(r, r) for r in indexed.representations)
        )
    doks = sorted({row.dok for row in lesson.analysis if row.example == n})
    if doks:
        notes.append("عمق التمارين المرتبطة: " + "، ".join(f"DOK {d}" for d in doks))
    return tuple(notes)


def _flow_slide(flow: Flow) -> TableSlide:
    rows = tuple((PHASE_LABELS[s.phase], s.strategy.title, f"{s.minutes}", f"{s.start}") for s in flow.steps)
    return TableSlide(
        title="سير الحصة",
        header=("الطور", "الاستراتيجية", "الدقائق", "يبدأ عند الدقيقة"),
        rows=rows,
        footnote=f"زمن الحصة {flow.period_minutes} دقيقة",
    )


def _assessment_slide(lesson: Grade10Lesson) -> TableSlide | None:
    if not lesson.quiz_depths:
        return None
    counts = Counter(lesson.quiz_depths)
    rows = tuple((f"DOK {d}", f"{counts[d]}") for d in sorted(counts))
    return TableSlide(
        title="التقويم",
        header=("العمق المعرفي", "عدد أسئلة اختبار الدرس"),
        rows=rows,
        footnote=f"عدد التمارين في الدرس {lesson.exercises_total}",
    )


def build_deck(lesson: Grade10Lesson, content: LessonContent, flow: Flow) -> Deck:
    """ترتيب الشرائح: العنوان، الأهداف، المصطلحات، مثال لكل مقصوص بترتيب رقمه، سير الحصة، التقويم."""
    if not content.title.strip():
        raise DeckError("عنوان الدرس فارغ")
    numbers = [c.n for c in content.examples]
    if len(set(numbers)) != len(numbers):
        raise DeckError("رقم مثال مكرر في المقصوصات")

    subtitle = f"الدرس {lesson.lesson}"
    if lesson.standards:
        subtitle += " · " + "، ".join(lesson.standards)
    slides: list[Slide] = [TitleSlide(content.title, subtitle)]
    if content.objectives:
        slides.append(BulletsSlide("أهداف الدرس", content.objectives))
    if content.vocabulary:
        slides.append(
            TableSlide("المصطلحات", ("المصطلح", "Term"), tuple((ar, en) for ar, en in content.vocabulary))
        )
    for clip in sorted(content.examples, key=lambda c: c.n):
        slides.append(ExampleSlide(f"مثال {clip.n}", clip, _example_notes(lesson, clip.n)))
    slides.append(_flow_slide(flow))
    assessment = _assessment_slide(lesson)
    if assessment is not None:
        slides.append(assessment)
    return Deck(lesson.lesson, tuple(slides))
