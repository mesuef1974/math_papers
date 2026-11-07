"""تحويل المستخرج الخاص (JSON بصياغتنا خارج المستودع) إلى ملفات المعرفة المنسقة التي تدخل المستودع.

نقي بلا ORM ولا دخل/خرج: يأخذ قواميس ويعيد قواميس. كل نص يمر بحارس schemas.safe_text؛ ما يسقط يُسجَّل في
Report.dropped ليُراجع، ولا يُكتب شيء مشكوك فيه.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .schemas import BLOOMS, LEVELS, safe_text

_SPACES = re.compile(r"\s+")
_INT = re.compile(r"\d+")
_RANGE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")


@dataclass
class Report:
    dropped: list[str] = field(default_factory=list)

    def drop(self, where: str, text: str, why: str) -> None:
        self.dropped.append(f"{where}: {why}: {text[:50]}")


def clean(value: Any, report: Report, where: str) -> str:
    """نص نظيف أو سلسلة فارغة إن لم يجتز الحارس."""
    if value is None:
        return ""
    text = _SPACES.sub(" ", str(value)).strip()
    if not text:
        return ""
    try:
        return safe_text(text)
    except ValueError as error:
        report.drop(where, text, str(error))
        return ""


def as_texts(value: Any) -> list[str]:
    """نص أو قائمة نصوص أو قاموس نصوص إلى قائمة نصوص."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in as_texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in as_texts(item)]
    return [str(value)]


def normalize_level(raw: Any) -> tuple[str, str]:
    """(المستوى K/A/R، ملاحظة). نص مركب مثل «K للتمارين 9-16، A للباقي» يأخذ أول رمز ويحفظ النص ملاحظة."""
    text = str(raw or "").strip()
    if not text:
        return "", ""
    first = text[0].upper()
    if first not in LEVELS:
        return "", text
    return first, "" if len(text) == 1 else text


def normalize_bloom(raw: Any) -> tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        return "", ""
    parts = [part.strip() for part in re.split(r"[/،,]", text) if part.strip()]
    if parts and parts[0] in BLOOMS:
        return parts[0], "" if len(parts) == 1 else f"بلوم: {text}"
    return "", f"بلوم: {text}"


def numbers_in(text: str) -> set[int]:
    """أرقام التمارين في نص مثل «36-40» أو «39, 40»."""
    found: set[int] = set()
    consumed = text
    for low, high in _RANGE.findall(text):
        if int(low) <= int(high) <= int(low) + 80:
            found.update(range(int(low), int(high) + 1))
    consumed = _RANGE.sub(" ", consumed)
    found.update(int(number) for number in _INT.findall(consumed))
    return found


def exercise_count(label: str, raw: Any) -> int:
    if isinstance(raw, int) and raw >= 1:
        return raw
    match = _RANGE.search(label)
    if match and int(match.group(1)) <= int(match.group(2)):
        return int(match.group(2)) - int(match.group(1)) + 1
    return max(1, len(_INT.findall(label)))


_CATEGORY_KEYS = (
    ("جماعي", "group"),
    ("توسيع", "extension"),
    ("استكشاف", "exploration"),
    ("الكتابة", "writing"),
    ("اختبار", "standard_test"),
    ("متعدد", "standard_test"),
    ("صواب", "standard_test"),
)


def category_map(categories: dict[str, Any] | None) -> dict[int, str]:
    """رقم تمرين -> فئته، من حقل exercise_categories. «لا يوجد» لا يعطي أرقامًا."""
    mapping: dict[int, str] = {}
    for key, value in (categories or {}).items():
        text = str(value or "")
        if text.strip().startswith(("لا يوجد", "لا ")):
            continue
        category = next((name for word, name in _CATEGORY_KEYS if word in key), None)
        if category is None:
            continue
        for number in numbers_in(text):
            mapping.setdefault(number, category)
    return mapping


def section_category(label: str, section: dict[str, Any], by_number: dict[int, str]) -> str:
    for word, name in _CATEGORY_KEYS:
        if word in label:
            return name
    if section.get("exam_pattern"):
        return "standard_test"
    first = _INT.search(label)
    if first and "مراجعة" not in label:
        return by_number.get(int(first.group()), "practice")
    return "practice"


# عنوان الصندوق أو مفتاحه -> نوع البند. الترتيب مهم: الأخص أولًا.
_KIND_RULES = (
    ("ملاحظات على التمارين", "exercise_note"),
    ("يواجهون", "struggling"),
    ("struggl", "struggling"),
    ("سريعي", "fast_finisher"),
    ("fast", "fast_finisher"),
    ("تفكر", "think_question"),
    ("تفكير", "think_question"),
    ("think", "think_question"),
    ("متابعة", "follow_up"),
    ("follow", "follow_up"),
    ("مساعدة دراسية", "study_tip"),
    ("ملاحظة دراسية", "study_tip"),
    ("study", "study_tip"),
    ("تنبيه", "caution"),
    ("caution", "caution"),
    ("warning", "caution"),
    ("تذكير", "reminder"),
    ("reminder", "reminder"),
    ("إرشاد", "guidance"),
    ("guid", "guidance"),
    ("تاريخ", "history"),
    ("history", "history"),
    ("الربط", "real_world"),
    ("real_world", "real_world"),
    ("economy", "real_world"),
    ("physics", "real_world"),
    ("mechanic", "real_world"),
    ("تقنية", "technology"),
    ("technology", "technology"),
    ("video", "technology"),
)
_SKIP_BOX = ("التقييم المستمر", "motivation", "تحفيز", "objective", "vocabulary_activity_skip")


def kind_of(name: str) -> tuple[str, str] | None:
    """(النوع، العنوان الأصلي إن كان عربيًا) أو None إن كان الصندوق يُهمَل."""
    lowered = name.lower()
    if any(word.lower() in lowered for word in _SKIP_BOX):
        return None
    for word, kind in _KIND_RULES:
        if word.lower() in lowered:
            return kind, name if re.search(r"[؀-ۿ]", name) else ""
    return "note", name if re.search(r"[؀-ۿ]", name) else ""


def _items(kind: str, texts: list[str], report: Report, where: str, label: str = "") -> list[dict[str, str]]:
    items = []
    for raw in texts:
        text = clean(raw, report, where)
        if text:
            items.append({"kind": kind, "text": text, "label": clean(label, report, where)})
    return items


def build_lesson(code: str, opener: dict[str, Any], body: dict[str, Any], report: Report) -> dict[str, Any]:
    where = f"lesson {code}"
    standards = opener.get("standard") or []
    standards = [standards] if isinstance(standards, str) else standards
    items: list[dict[str, str]] = []

    items += _items("learning_goal", as_texts(opener.get("what_you_will_learn")), report, where)
    items += _items("guide_step", as_texts(opener.get("lesson_guide")), report, where)
    items += _items("prerequisite", as_texts(opener.get("prerequisites")), report, where)

    steps = [*(opener.get("concept_build") or []), *(body.get("concept_build") or [])]
    seen: set[str] = set()
    for step in steps:
        text = clean(step.get("idea") if isinstance(step, dict) else step, report, where)
        if text and text not in seen:
            seen.add(text)
            items.append({"kind": "concept_step", "text": text, "label": ""})

    for key, value in (opener.get("teacher_supports") or {}).items():
        mapped = kind_of(str(key))
        if mapped:
            items += _items(mapped[0], as_texts(value), report, where, mapped[1])
    for box in body.get("margin_boxes") or []:
        mapped = kind_of(str(box.get("type", "")))
        if mapped:
            items += _items(mapped[0], as_texts(box.get("content")), report, where, mapped[1])

    items += _items("common_error", as_texts(body.get("common_errors")), report, where)
    items += _items("technology", as_texts(body.get("technology")), report, where)
    review = body.get("quick_review")
    review_skills = review.get("skills") if isinstance(review, dict) else review
    items += _items("prerequisite", as_texts(review_skills), report, where, "مراجعة سريعة")
    items += _items("connection", as_texts(body.get("connections")), report, where)
    items += _items("solution_style", as_texts(body.get("solutions_style")), report, where)
    items += _items("pearl", as_texts(body.get("treasures")), report, where)

    terms = []
    for term in opener.get("vocabulary") or []:
        if isinstance(term, dict) and term.get("ar"):
            ar, en = clean(term["ar"], report, where), clean(term.get("en", ""), report, where)
            if ar:
                terms.append({"ar": ar, "en": en})

    examples: dict[int, dict[str, Any]] = {}
    for source in (opener.get("examples") or [], body.get("examples") or []):
        for example in source:
            number = example.get("n", example.get("number"))
            skill = clean(example.get("skill"), report, where)
            if not isinstance(number, int) or not skill:
                continue
            current = examples.setdefault(
                number, {"number": number, "skill": skill, "representation": "", "methods": []}
            )
            current["skill"] = skill
            current["representation"] = (
                clean(example.get("representation"), report, where) or current["representation"]
            )
            methods = [clean(m, report, where) for m in as_texts(example.get("methods"))]
            current["methods"] = [m for m in methods if m] or current["methods"]

    by_number = category_map(body.get("exercise_categories"))
    templates = []
    for section in body.get("exercise_sections") or []:
        label = clean(section.get("range"), report, where)
        skill = clean(section.get("skill"), report, where)
        if not label or not skill:
            continue
        level, level_note = normalize_level(section.get("inferred_level"))
        bloom, bloom_note = normalize_bloom(section.get("inferred_bloom"))
        note = " | ".join(part for part in (level_note, bloom_note) if part)
        templates.append(
            {
                "label": label,
                "directive_template": clean(section.get("directive_template"), report, where),
                "skill": skill,
                "representation": clean(section.get("representation"), report, where),
                "level": level,
                "bloom": bloom,
                "inference_note": clean(note, report, where),
                "count": exercise_count(label, section.get("count")),
                "category": section_category(label, section, by_number),
            }
        )

    assessed = body.get("self_assessment")
    if isinstance(assessed, dict):
        assessed = assessed.get("exercises")
    if not assessed:
        notes = body.get("exercise_notes")
        assessed = notes.get("self_assessment") if isinstance(notes, dict) else None
    self_assessment = sorted(numbers_in(" ".join(as_texts(assessed)))) if assessed else []
    return {
        "lesson": code,
        "title_en": clean(opener.get("english_title"), report, where),
        "standards": [str(s) for s in standards],
        "objective": clean(opener.get("objective"), report, where),
        "rationale": clean(opener.get("why"), report, where),
        "motivation": clean(" ".join(as_texts(opener.get("motivation"))), report, where),
        "self_assessment": self_assessment,
        "terms": terms,
        "items": items,
        "examples": [examples[n] for n in sorted(examples)],
        "templates": templates,
    }


_UNIT_CONTEXT_KEYS = ("history", "payoff", "caution", "related_rates", "history_hook", "applications")


def build_units(
    front: dict[str, Any], reviews: dict[int, dict[str, Any]], report: Report
) -> list[dict[str, Any]]:
    titles = {u["unit"]: u["title"] for u in front["contents"]["units"]}
    units = []
    for number, opener in sorted((int(k), v) for k, v in front["unit_openers"].items()):
        where = f"unit {number}"
        context = " ".join(
            clean(opener.get(key), report, where) for key in _UNIT_CONTEXT_KEYS if opener.get(key)
        )
        project = (reviews.get(number) or {}).get("project")
        units.append(
            {
                "unit": number,
                "title": clean(titles.get(number) or opener.get("title"), report, where),
                "big_idea": clean(opener.get("big_idea"), report, where),
                "approach": clean(opener.get("approach"), report, where),
                "context": clean(context, report, where),
                "project": None
                if not project
                else {
                    "goal": clean(project.get("goal"), report, where),
                    "context": clean(project.get("real_world_context"), report, where),
                    "data_used": clean(project.get("data_used"), report, where),
                    "tasks": [
                        t for t in (clean(x, report, where) for x in as_texts(project.get("tasks"))) if t
                    ],
                },
            }
        )
    return units


def build_pedagogy(front: dict[str, Any], report: Report) -> list[dict[str, Any]]:
    ped, book, sets = front["pedagogy"], front["book_features"], front["exercise_sets"]
    tech = ped.get("technology", {})
    raw = [
        ("rule-of-four", "قاعدة الطرائق الأربع", ped.get("rule_of_four")),
        ("problem-solving", "منهجية حل المسائل", " ثم ".join(ped.get("problem_solving_polya", []))),
        (
            "parent-functions",
            "الدوال الأساسية",
            "، ".join(ped.get("parent_functions", [])) + ". " + str(ped.get("parent_functions_note", "")),
        ),
        ("real-data", "التطبيقات والبيانات الواقعية", ped.get("real_data")),
        ("technology-policy", "سياسة التقنية والآلة الحاسبة", " ".join(as_texts(tech))),
        ("unit-intro", "مقدمة الوحدة", book.get("unit_intro")),
        ("lesson-opener", "بداية الدرس", book.get("lesson_opener")),
        (
            "color-coding",
            "الترميز اللوني في الكتاب",
            " ".join(f"{k}: {v}." for k, v in (book.get("color_coding") or {}).items()),
        ),
        ("try-after-example", "حاول أن تحل بعد كل مثال", book.get("try_after_example")),
        ("exploration", "نشاطات الاستكشاف", book.get("exploration_activities")),
        ("margin-notes", "التلميحات والملاحظات الهامشية", book.get("tips_and_margin_notes")),
        ("unit-review", "نهاية الوحدة", " ".join(as_texts(book.get("unit_review")))),
        ("exercise-start", "بداية مجموعة التمارين", sets.get("starts_with")),
        ("skill-strands", "محاور المهارات في التمارين", "، ".join(sets.get("skill_strands", []))),
        (
            "thinking-exercises",
            "تمارين التفكير",
            " ".join(f"{k}: {v}." for k, v in (sets.get("thinking_categories") or {}).items()),
        ),
        ("exercise-purpose", "غاية تنوع التمارين", sets.get("purpose")),
    ]
    notes = []
    for order, (slug, title, text) in enumerate(raw, start=1):
        cleaned = clean(text, report, f"pedagogy {slug}")
        if cleaned:
            notes.append({"slug": slug, "title": title, "text": cleaned, "order": order})
    return notes
