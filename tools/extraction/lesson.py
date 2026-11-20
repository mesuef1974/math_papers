"""سجل الدرس الموحّد lesson_X_Y.json من layout وobjectives والدمج وجدول التحليل ورؤية الأمثلة والمفردات.

كل حقل غلاف {value، source، status} (`fields.py`): source من guide (مستخرج) أو derived (مشتق بقاعدة) أو library (تؤلفه المكتبة
التربوية لاحقًا) أو teacher؛ وstatus من ok وreview وmissing. حقل في الدليل ولم يُبنَ مستخرجه: guide/missing؛ وحقل لا يرد في الدليل
(الزمن، التحرير التدريجي…): library/missing. المدقّقات في `checks`؛ والذهبي (إن وُجد) للانحدار فقط ولا يدخل الحقول (`regression.py`).

الإعداد `lesson` اختياري: schema_version، example_vision (مفاتيح dirs بترتيب الأولوية: يُؤخذ أول مجلد فيه ملف الصفحة)، overrides (ملف
في dirs.gold لتصحيح تمثيلات مثال بعينه بسببه)، representation_note، library_fields، pending_fields. المخرجات في dirs.lessons.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import checks, fusion, vocabulary
from .config import Book
from .fields import field

DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "example_vision": ["badges"],
    "overrides": "reps_overrides.json",
    "representation_note": "رؤية لمقطع المثال من صورة كتاب الطالب المصغّرة (نعم/لا لكل تمثيل)؛ تُراجَع",
    "library_fields": [
        "time",
        "gradual_release",
        "exit_ticket",
        "common_errors",
        "differentiation",
        "prerequisites",
    ],
    "pending_fields": ["steps", "exercise_sections"],
}
EVIDENCE_STATUS = {"both": "ok", "ocr": "ok", "vision": "ok", "filled": "review", "badge": "ok"}


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("lesson", {})}


def lessons_dir(book: Book) -> Any:
    return book.dir("lessons") if book.has_dir("lessons") else book.out / "lessons"


def merged_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """صفوف الجدول مدموجة بالمثال والعمق (التمارين مجتمعة)."""
    acc: dict[Any, set[int]] = {}
    for r in rows:
        if r.get("exercises"):
            acc.setdefault((r["example"], r["dok"]), set()).update(r["exercises"])
    return [
        {"example": k[0], "dok": k[1], "exercises": sorted(v)}
        for k, v in sorted(acc.items(), key=lambda kv: (kv[0][0] is None, kv[0][0] or 0, kv[0][1] or 0))
    ]


def apply_override(book: Book, item: dict[str, Any], page: int) -> dict[str, Any]:
    """تصحيح مراجَع بشريًا لتمثيلات مثال بعينه (مفتاحه «صفحة_رقم») حيث يعجز سؤال النموذج؛ كل تصحيح بسببه في الملف."""
    cfg = settings(book)
    path = book.dir("gold") / cfg["overrides"] if book.has_dir("gold") else None
    rules = json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else {}
    rule = rules.get(f"{page}_{item.get('n')}")
    if not rule or item.get("representations") is None:
        return item
    reps = [r for r in item["representations"] if r not in rule.get("remove", [])]
    reps += [r for r in rule.get("add", []) if r not in reps]
    return {**item, "representations": reps, "representations_override": rule["reason"]}


def example_vision(book: Book, first: int, last: int) -> dict[int, dict[str, Any]]:
    """رقم المثال -> قراءة الرؤية (عنوان وسطر عريض وتمثيلات) وصفحة شارته: أول ظهور لشارته بين صفحات الدرس."""
    dirs = [book.dir(k) for k in settings(book)["example_vision"] if book.has_dir(k)]
    out: dict[int, dict[str, Any]] = {}
    for page in range(first, last + 1):
        path = next((d / f"{page:04d}.json" for d in dirs if (d / f"{page:04d}.json").exists()), None)
        if path is None:
            continue
        for e in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(e.get("n"), int) and e["n"] not in out:
                out[e["n"]] = {**apply_override(book, e, page), "page": page}
    return out


def _example(
    n: int,
    pages: dict[int, dict[str, Any]],
    rows: list[dict[str, Any]],
    vis: dict[int, dict[str, Any]],
    fused: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    page = next((p for p, s in pages.items() if n in s["examples"][0] or n in s["examples"][1]), None)
    ex_rows = [r for r in rows if r["example"] == n]
    v = vis.get(n)
    evidence = fused["examples"].get(n, "badge")
    ok_if_rows = "ok" if ex_rows else "review"
    # صفحة شارة المثال المقتصّة أدق من أول صفحة يرد فيها رقمه في OCR أو الرؤية الكاملة
    page_pdf = field(v["page"], "guide", "ok") if v else field(page, "guide", "ok" if page else "review")
    skill = (
        field(
            {"title": v["title"], "focus": v["focus"]},
            "guide",
            "review",
            note="عنوان المثال والسطر العريض تحته كما قرأتهما الرؤية من مقطع الشارة؛ يُراجَع الهجاء",
        )
        if v and v["title"]
        else field(None, "guide", "missing")
    )
    representation = (
        field(v["representations"], "guide", "review", note=note)
        if v and v["representations"] is not None
        else field(None, "guide", "missing")
    )
    return {
        "n": n,
        "page_pdf": page_pdf,
        "evidence": evidence,
        "status": EVIDENCE_STATUS[evidence],
        "dok": field(
            sorted({r["dok"] for r in ex_rows}, key=lambda x: (x is None, x or 0)), "guide", ok_if_rows
        ),
        "exercises": field(sorted({x for r in ex_rows for x in r["exercises"]}), "guide", ok_if_rows),
        "skill": skill,
        "representation": representation,
    }


def _objectives(objectives: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    got = objectives.get("lessons", {}).get(lesson_id)
    items = [
        {k: o[k] for k in ("text", "verb", "bloom", "confidence", "status", "split")}
        for o in (got["value"] if got else [])
    ]
    return field(
        items,
        "guide",
        got["status"] if got else "missing",
        bloom_source="derived",
        lexicon_version=objectives.get("lexicon_version"),
    )


def build(book: Book, rec: dict[str, Any], objectives: dict[str, Any]) -> dict[str, Any]:
    cfg = settings(book)
    fcfg = fusion.settings(book)
    a, z = rec["pages_pdf"]
    fused = fusion.fuse(book, a, z, fcfg)
    vis = example_vision(book, a, z)
    table = {"rows": [], "task_guide": None}
    if rec.get("table") and book.has_dir("tables"):
        path = book.dir("tables") / f"{rec['table']:04d}.json"
        if path.exists():
            table = json.loads(path.read_text(encoding="utf-8"))
    rows = merged_rows(table["rows"])
    pages = {n: fusion.page_sources(book, n, fcfg) for n in range(a, z + 1)}
    # شارات المثال المقتصّة هي المرجع لمجموعة الأمثلة متى وُجدت: الرؤية الكاملة تختلق قوائم متسلسلة وOCR يلتقط أرقامًا شاردة
    ex_nums = sorted(vis) if vis else sorted(fused["examples"])
    examples = [_example(n, pages, rows, vis, fused, cfg["representation_note"]) for n in ex_nums]
    exercises = sorted(fused["exercises"])
    tmax = max((x for r in rows for x in r["exercises"]), default=0)
    std_on_quiz = book["layout"].get("standard_on", "opener") == "quiz"
    std_page = rec.get("quiz") if std_on_quiz else rec["opener"]
    codes = checks.page_codes(book, book.page_text(std_page)) if std_page else []
    vocab = vocabulary.terms(book, rec["opener"])
    qrows = checks.quiz_rows(book, book.page_text(rec["quiz"])) if rec.get("quiz") else []
    ex_cfg = book.get("exercises", {})
    ceiling, jump = ex_cfg.get("max", 60), ex_cfg.get("jump", 5)
    ocr_nums = {x for s in pages.values() for x in s["exercises"][0]}
    gmax = checks.task_guide_max(table.get("task_guide"))
    ex_checks = {
        "exercises_contiguous_1_to_max": exercises == list(range(1, (exercises[-1] if exercises else 0) + 1)),
        "exercises_max_matches_table": bool(exercises) and exercises[-1] == tmax,
        # سلسلة OCR وحدها تفوّت آخر رقم (لا رقم بعده يسنده): يُقبل فرق واحد أو تطابق أقصى «دليل المهام» المستقل
        "exercises_max_corroborated_independently": bool(exercises)
        and bool(checks.exercise_total(exercises[-1], ocr_nums, jump, ceiling, gmax)),
        "table_exercises_within_fused": {x for r in rows for x in r["exercises"]} <= set(exercises),
        "analysis_examples_in_lesson_examples": {r["example"] for r in rows if r["example"]} <= set(ex_nums),
        # أرقام شارات الأمثلة متصلة من 1 (لا شارة فاتت ولا رقم مقروء خطأ)
        "example_badges_contiguous_from_1": bool(vis) and sorted(vis) == list(range(1, len(vis) + 1)),
        "objectives_present": bool(objectives.get("lessons", {}).get(rec["id"], {}).get("value")),
        "vocabulary_present_with_pairs": bool(vocab) and all(v["ar"] and v["en"] for v in vocab),
        "standard_found_on_quiz_page": bool(codes),
        # أرقام الأسئلة متصلة من 1، وكل عمق من 1 إلى 3، ورموز صفوفها هي رموز الصفحة نفسها
        "quiz_questions_contiguous_with_depths": bool(qrows) and bool(checks.quiz_consistent(qrows, codes)),
    }
    return {
        "schema_version": cfg["schema_version"],
        "book": book.id,
        "id": rec["id"],
        "unit": rec["unit"],
        "pages": {
            "span_pdf": field(rec["pages_pdf"], "derived", rec["status"]),
            "opener": field(rec["opener"], "derived", "ok"),
            "analysis_table": field(rec.get("table"), "derived", "ok"),
            "quiz": field(rec.get("quiz"), "derived", "ok"),
            "review_pages": field(
                sorted(fused["review_pages"]), "derived", "ok" if not fused["review_pages"] else "review"
            ),
        },
        "standards": field(
            codes,
            "guide",
            "ok" if codes else "missing",
            note="رموز المعيار من صفحة اختبار الدرس؛ ليست مربوطة بكل سؤال",
        ),
        "practices": field(sorted(fused["practices"]), "guide", "ok" if fused["practices"] else "missing"),
        "objectives": _objectives(objectives, rec["id"]),
        "examples": examples,
        # أقصى رقم بلا شاهد (جدول التحليل، أو سلسلة OCR المستقلة، أو «دليل المهام») قراءة واحدة: يُراجَع ولا يُعتمد عددًا للدرس
        "exercises": field(
            exercises,
            "guide",
            "missing"
            if not exercises
            else (
                "ok"
                if ex_checks["exercises_max_matches_table"]
                or ex_checks["exercises_max_corroborated_independently"]
                else "review"
            ),
            total=len(exercises),
        ),
        "exercise_analysis": field(
            rows,
            "guide",
            "missing" if not rows else ("review" if any(r["example"] is None for r in rows) else "ok"),
        ),
        "task_guide": field(table.get("task_guide"), "guide", "ok" if table.get("task_guide") else "missing"),
        "vocabulary": field(
            [{k: v[k] for k in ("ar", "en", "kind")} for v in vocab],
            "guide",
            "missing" if not vocab else ("ok" if all(v["status"] == "ok" for v in vocab) else "review"),
            note="رؤية لبطاقة «بناء المصطلحات» مدمجة مع OCR؛ هجاء المصطلحات المتكررة مصحَّح بالمرجع الذهبي",
            terms_review=[v["ar"] for v in vocab if v["status"] != "ok"],
        ),
        "lesson_quiz": field(
            checks.quiz_summary(qrows),
            "guide",
            "missing"
            if not qrows
            else ("ok" if ex_checks["quiz_questions_contiguous_with_depths"] else "review"),
            note="الأعماق ورموز المعايير من جدول تحليل التمارين في صفحة الاختبار؛ نص الأسئلة لا يُستخرج",
        ),
        "example_skill_representation": field(
            {
                "examples": len(examples),
                "with_skill": sum(e["skill"]["value"] is not None for e in examples),
                "with_representation": sum(e["representation"]["value"] is not None for e in examples),
                "rejected_without_badge": sorted(set(fused["examples"]) - set(ex_nums)),
            },
            "guide",
            "review" if vis else "missing",
            note="الحقلان على مستوى المثال في examples[*].skill وrepresentation؛ هذا ملخص عددهما",
        ),
        **{k: field(None, "guide", "missing") for k in cfg["pending_fields"]},
        **{k: field(None, "library", "missing") for k in cfg["library_fields"]},
        "checks": ex_checks,
    }


def tag_of(lesson_id: str) -> str:
    return re.sub(r"[^\w]+", "_", lesson_id)


def run(
    book: Book, layout: dict[str, Any], objectives: dict[str, Any], only: set[str] | None = None
) -> dict[str, Any]:
    """يبني سجل كل درس (أو المحدَّد) ويكتبه في dirs.lessons مع انحداره على الذهبي إن وُجد؛ يعيد ملخصًا."""
    from . import regression

    folder = lessons_dir(book)
    folder.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"book": book.id, "lessons": {}}
    for rec in layout["lessons"]:
        if not rec["pages_pdf"] or (only and rec["id"] not in only):
            continue
        record = build(book, rec, objectives)
        tag = tag_of(rec["id"])
        reg = regression.vs_gold(book, record, tag)
        if reg is not None:
            record["regression_vs_gold"] = reg
        soft = regression.soft(book, record, tag)
        if soft is not None:
            record["regression_soft"] = soft
        (folder / f"lesson_{tag}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        summary["lessons"][rec["id"]] = {
            "failed_checks": [k for k, v in record["checks"].items() if v is False],
            "regression": None if reg is None else [k for k, v in reg.items() if not v],
        }
    return summary


def summarize(summary: dict[str, Any]) -> dict[str, Any]:
    ls = summary["lessons"]
    return {
        "lessons": len(ls),
        "with_failed_checks": {k: v["failed_checks"] for k, v in ls.items() if v["failed_checks"]},
        "regressions": {k: v["regression"] for k, v in ls.items() if v["regression"]},
    }
