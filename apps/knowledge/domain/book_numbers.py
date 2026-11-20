"""أرقام كتاب الطالب لدرس بصياغتنا: صفحة كل مثال وتدريبات الكتاب عليه، تُضاف إلى ملف الدرس بلا مسّ أي نص.

المدخل مخرجات خط الاستخراج (أرقام فقط): صفحة بدء كل مثال في ملف الدليل (`examples.json`)، وجدول صفحة الملف → الصفحة المطبوعة
(`printed_pages.json`)، وربط التدريبات بالأمثلة (`exercise_links.json`). عمق مجموعة التمارين من مستوى قالب التمرين في الدرس نفسه
(K=1، A=2، R=3)، يُعرف القالب من مدى الأرقام في أول عنوانه («10-13»، «35 …»)، والتمرين بلا قالب أو بلا مستوى عمقه 2.
الدالة نقية وidempotent: لا تغيّر مدخلها، وتطبيقها مرتين كتطبيقها مرة.

أرقام الدليل للدرس (`GUIDE_FIELDS`: دليل المهام وأعماق اختبار الدرس وعدد التمارين وعدد المصطلحات) من سجل الدرس في مخرج مرحلة
`lesson` (`lessons/lesson_X_Y.json`، كل حقل غلاف `{value, source, status}`): `guide_numbers` يأخذ الحقل الذي حالته مقبولة وقيمته
بالشكل المنتظر وحده، وما سواه (مفقود، أو يُراجَع، أو قراءة لا تطابق الشكل) لا يُعاد فيبقى الحقل في الملف كما كان: لا تخمين.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .schemas import RANGE

DOK = {"K": 1, "A": 2, "R": 3}
DEFAULT_DOK = 2
MAX_EXAMPLE = 20  # حد `ExerciseGroupData.example`
_LABEL_RANGE = re.compile(r"^\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?(?!\d)")
# بترتيب كتابتها في الملف
GUIDE_FIELDS = ("task_basic", "task_advanced", "quiz_depths", "exercises_total", "vocab_new", "vocab_review")
MAX_EXERCISES = 99  # حد `LessonData.exercises_total`
MAX_DEPTH = 4


def _template_ranges(templates: Iterable[Mapping[str, Any]]) -> Iterable[tuple[int, int, str]]:
    """(أول، آخر، مستوى) لكل قالب يبدأ عنوانه برقم؛ ما سواه (مراجعة سريعة...) ترقيمه غير ترقيم التمارين فيُهمل."""
    for template in templates:
        match = _LABEL_RANGE.match(template.get("label", ""))
        if match:
            first = int(match[1])
            yield first, int(match[2]) if match[2] else first, template.get("level", "")


def template_doks(templates: Iterable[Mapping[str, Any]]) -> dict[int, int]:
    """رقم التمرين → عمقه من قوالب الدرس (القالب بلا مستوى يُهمل)."""
    out: dict[int, int] = {}
    for first, last, level in _template_ranges(templates):
        if level in DOK:
            for number in range(first, last + 1):
                out.setdefault(number, DOK[level])
    return out


def template_max(templates: Iterable[Mapping[str, Any]]) -> int:
    """أكبر رقم تمرين تذكره قوالب الدرس (0 بلا قوالب مرقّمة): شاهد من صياغتنا على عدد تمارين الدرس."""
    return max((last for _, last, _ in _template_ranges(templates)), default=0)


def _accepted(record: Mapping[str, Any], key: str, accepted: Iterable[str]) -> Any:
    field = record.get(key)
    return field.get("value") if isinstance(field, Mapping) and field.get("status") in accepted else None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def guide_numbers(record: Mapping[str, Any], accepted: Iterable[str] = ("ok",)) -> dict[str, Any]:
    """حقول `GUIDE_FIELDS` المقروءة في سجل درس من مرحلة `lesson`؛ الحقل غير المقبول أو غير المطابق للشكل يغيب.

    دليل المهام مساران معًا بشكل المدى `schemas.RANGE` («1-12, 15»)، وأعماق الاختبار كلها 1..4، وعدد التمارين أقصى رقم،
    وعددا المصطلحات من `kind` كل مصطلح (لا يدخل نص المصطلح).
    """
    accepted = tuple(accepted)
    out: dict[str, Any] = {}
    guide = _accepted(record, "task_guide", accepted)
    if isinstance(guide, Mapping):
        basic, advanced = (str(guide.get(k) or "").strip() for k in ("basic", "advanced"))
        if basic and advanced and RANGE.match(basic) and RANGE.match(advanced):
            out |= {"task_basic": basic, "task_advanced": advanced}
    quiz = _accepted(record, "lesson_quiz", accepted)
    depths = quiz.get("depth") if isinstance(quiz, Mapping) else None
    if depths and all(_is_int(d) and 1 <= d <= MAX_DEPTH for d in depths):
        out["quiz_depths"] = list(depths)
    exercises = _accepted(record, "exercises", accepted)
    if exercises and all(_is_int(x) for x in exercises) and 1 <= max(exercises) <= MAX_EXERCISES:
        out["exercises_total"] = max(exercises)
    vocab = _accepted(record, "vocabulary", accepted)
    if vocab and all(isinstance(v, Mapping) and v.get("kind") in ("new", "review") for v in vocab):
        out["vocab_new"] = sum(v["kind"] == "new" for v in vocab)
        out["vocab_review"] = sum(v["kind"] == "review" for v in vocab)
    return out


def exercise_groups(
    links: Iterable[Mapping[str, Any]], doks: Mapping[int, int], examples: set[int]
) -> list[dict[str, Any]]:
    """صفوف `exercise_groups` مرتبة بالمثال ثم العمق؛ رابط إلى مثال ليس في الدرس أو بلا تدريبات يُهمل."""
    merged: dict[int, set[int]] = {}
    for row in links:
        if row["example"] in examples and row["example"] <= MAX_EXAMPLE:
            merged.setdefault(row["example"], set()).update(int(x) for x in row["exercises"])
    groups: list[dict[str, Any]] = []
    for example in sorted(merged):
        by_dok: dict[int, list[int]] = {}
        for number in sorted(merged[example]):
            by_dok.setdefault(doks.get(number, DEFAULT_DOK), []).append(number)
        groups += [{"example": example, "dok": dok, "exercises": by_dok[dok]} for dok in sorted(by_dok)]
    return groups


def _with_page(example: dict[str, Any], page: int | None) -> dict[str, Any]:
    if page is None:
        return dict(example)
    out: dict[str, Any] = {}
    for key, value in example.items():
        if key != "page":
            out[key] = value
        if key == "number":
            out["page"] = page  # موضعه بعد الرقم دائمًا، فالتشغيل الثاني لا يحرّك مفتاحًا
    return out


def annotate(
    lesson: Mapping[str, Any],
    pages: Mapping[int, int],
    links: Iterable[Mapping[str, Any]] | None,
    numbers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """نسخة من ملف الدرس بـ `page` لكل مثال عُرفت صفحته وبـ `exercise_groups` من الروابط وبأرقام الدليل `numbers`.

    `pages`: رقم المثال → صفحته المطبوعة (ما غاب يبقى كما كان). `links`: صفوف `{example, exercises}`، وNone أو ما لا ينتج
    مجموعة يترك `exercise_groups` كما كانت. المفتاح الجديد `exercise_groups` يوضع قبل `examples`. `numbers`: من `GUIDE_FIELDS`
    (ما غاب يبقى كما كان)، ومكانها بعد `standards` (أو `lesson`) بترتيب `GUIDE_FIELDS` دائمًا. لا يُمسّ حقل غير هذه.
    """
    unknown = set(numbers or {}) - set(GUIDE_FIELDS)
    if unknown:
        raise ValueError(f"حقول ليست من أرقام الدليل: {sorted(unknown)}")
    given = {**{k: lesson[k] for k in GUIDE_FIELDS if k in lesson}, **(numbers or {})}
    guide = {k: given[k] for k in GUIDE_FIELDS if k in given}
    anchor = "standards" if "standards" in lesson else "lesson"
    examples = [_with_page(e, pages.get(e["number"])) for e in lesson.get("examples", [])]
    groups = (
        exercise_groups(links, template_doks(lesson.get("templates", [])), {e["number"] for e in examples})
        if links is not None
        else []
    )
    out: dict[str, Any] = {}
    for key, value in lesson.items():
        if key in GUIDE_FIELDS:
            continue
        if key == "examples":
            if groups:
                out["exercise_groups"] = groups
            out[key] = examples
        elif key != "exercise_groups" or not groups:
            out[key] = value
        if key == anchor:
            out |= guide
    return out
