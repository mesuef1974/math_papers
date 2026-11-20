"""سجل الدرس والمفردات والانحدار: كتاب اصطناعي وملفات مختلقة، لا بيانات دليل حقيقية."""

import json

from tools.extraction import lesson, regression, vocabulary
from tools.extraction.__main__ import main

from .conftest import TOY_PAGES, make_book

ID_PATTERN = {"id_pattern": r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"}


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def toy_book(tmp_path, pages=None, **over):
    dirs = {"vision": "vision", "tables": "tables", "gold": "gold", "vocab": "vocab"}
    dirs.update(over.pop("dirs", {}))
    return make_book(tmp_path, pages or TOY_PAGES, dirs=dirs, layout=ID_PATTERN, **over)


def test_stage_writes_lesson_records_and_skips_when_unchanged(tmp_path, capsys):
    book = toy_book(tmp_path)
    assert main([str(book.root), "lesson"]) == 0
    rec = json.loads((book.out / "lessons" / "lesson_1_1.json").read_text(encoding="utf-8"))
    assert rec["id"] == "1.1"
    assert rec["standards"]["value"] == ["12A.1.1"]
    assert rec["exercises"]["value"] == [1, 2, 3]
    assert [e["n"] for e in rec["examples"]] == [1, 2]
    assert rec["time"] == {"value": None, "source": "library", "status": "missing"}
    assert rec["steps"]["source"] == "guide"
    assert rec["objectives"]["status"] == "missing"
    assert set(json.loads((book.out / "lessons.json").read_text(encoding="utf-8"))["lessons"]) == {
        "1.1",
        "1.2",
    }
    capsys.readouterr()
    assert main([str(book.root), "lesson"]) == 0
    assert "تُخطيت" in capsys.readouterr().out


def test_exercise_total_without_independent_witness_is_review(tmp_path):
    """كتاب بلا جدول تحليل: أقصى تمرين قرأته الرؤية وحدها فوق سلسلة OCR يُراجَع، والذي تسنده السلسلة ok."""
    rec = {"id": "1.1", "unit": 1, "status": "ok", "pages_pdf": [2, 5], "opener": 2, "quiz": None}
    book = toy_book(tmp_path)
    got = lesson.build(book, rec, {})
    assert got["exercises"]["value"] == [1, 2, 3] and got["exercises"]["status"] == "ok"
    write(tmp_path, "vision/0005.json", {"examples": [], "exercises": [4, 5], "practices": []})
    got = lesson.build(book, rec, {})
    assert got["exercises"]["value"] == [1, 2, 3, 4, 5]
    assert got["checks"]["exercises_max_corroborated_independently"] is False
    assert got["exercises"]["status"] == "review"
    # لا «دليل مهام» ولا جدول اختبار في الكتاب: الحقلان مفقودان ولا يُختلقان
    assert got["task_guide"]["status"] == got["lesson_quiz"]["status"] == "missing"


def test_objectives_wrapper_is_trimmed_and_status_kept():
    objectives = {
        "lexicon_version": "v1",
        "lessons": {
            "1.1": {
                "value": [
                    {"text": "ت", "verb": "ف", "bloom": "فهم", "confidence": 0.9, "status": "ok",
                     "split": "check", "source": {"text": "guide"}}
                ],
                "status": "review",
            }
        },
    }  # fmt: skip
    got = lesson._objectives(objectives, "1.1")
    assert got["status"] == "review" and "source" not in got["value"][0]
    assert got["lexicon_version"] == "v1"
    assert lesson._objectives(objectives, "9.9")["status"] == "missing"


def test_example_vision_priority_and_override(tmp_path):
    book = toy_book(
        tmp_path,
        dirs={"reps_a": "ra", "reps_b": "rb"},
        lesson={"example_vision": ["reps_a", "reps_b"]},
    )
    item = {"n": 1, "title": "أ", "focus": "ف", "representations": ["جدول"]}
    write(tmp_path, "ra/0003.json", [item])
    write(tmp_path, "rb/0003.json", [{**item, "title": "ب"}])
    write(tmp_path, "rb/0004.json", [{**item, "n": 2, "title": "ج", "representations": None}])
    write(
        tmp_path,
        "gold/reps_overrides.json",
        {"3_1": {"add": ["بياني"], "remove": ["جدول"], "reason": "مراجعة"}},
    )
    vis = lesson.example_vision(book, 2, 5)
    assert vis[1]["title"] == "أ" and vis[1]["page"] == 3  # الأعلى أولوية يغلب
    assert vis[1]["representations"] == ["بياني"] and vis[1]["representations_override"] == "مراجعة"
    assert vis[2]["representations"] is None and vis[2]["page"] == 4  # التصحيح لا يمسّ قيمة غائبة


def test_badges_are_the_example_reference_when_present(tmp_path):
    book = toy_book(tmp_path, dirs={"badges": "badges"})
    write(
        tmp_path,
        "badges/0003.json",
        [{"n": 1, "title": "عنوان", "focus": "تركيز", "representations": ["جدول"]}],
    )
    rec = lesson.build(
        book, {"id": "1.1", "unit": 1, "status": "ok", "pages_pdf": [2, 5], "opener": 2, "quiz": None}, {}
    )
    assert [e["n"] for e in rec["examples"]] == [1]
    assert rec["examples"][0]["page_pdf"]["value"] == 3
    assert rec["examples"][0]["skill"]["value"] == {"title": "عنوان", "focus": "تركيز"}
    assert rec["checks"]["example_badges_contiguous_from_1"] is True
    assert rec["example_skill_representation"]["value"]["rejected_without_badge"] == [2]


def test_vocabulary_merges_vision_with_ocr_and_snaps_to_gold(tmp_path):
    page = "مراجعة المصطلحات\nدالة\nfunction\nالمصطلحات الجديدة\nمشتقة\nderivative"
    book = toy_book(tmp_path, {1: "غلاف", 2: page})
    write(
        tmp_path,
        "vocab/0002.json",
        {
            "review": [{"ar": "دالة", "en": "function"}, {"ar": "المصطلحات", "en": "x"}],
            "new": [{"ar": "مشتقه", "en": "derivative"}],
        },
    )
    write(tmp_path, "gold/lesson_9_9.json", {"vocabulary": [{"ar": "مشتقة", "en": "derivative"}]})
    rows = vocabulary.terms(book, 2)
    assert [(r["ar"], r["kind"], r["status"]) for r in rows] == [
        ("دالة", "review", "ok"),
        ("مشتقة", "new", "ok"),
    ]
    assert vocabulary.terms(book, 2, fix_spelling=False)[1]["ar"] == "مشتقه"  # بلا تصحيح بالذهبي
    assert vocabulary.terms(book, 1) == []  # لا قراءة رؤية لهذه الصفحة


def test_vocabulary_flags_review_when_ocr_disagrees(tmp_path):
    book = toy_book(tmp_path, {1: "غلاف", 2: "مراجعة المصطلحات\nشيء آخر تماما"})
    write(tmp_path, "vocab/0002.json", {"review": [{"ar": "دالة", "en": "function"}], "new": []})
    assert vocabulary.terms(book, 2)[0]["status"] == "review"


def test_soft_regression_counts_representations(tmp_path):
    book = toy_book(tmp_path)
    write(tmp_path, "gold/lesson_1_1.json", {"examples": [{"n": 1, "representation": "تمثيل جدول وبياني"}]})
    mine = {"examples": [{"n": 1, "representation": {"value": ["بياني", "سياق حياتي"]}}]}
    got = regression.soft(book, mine, "1_1")
    assert got == {"representation_exact": 0, "of": 1, "precision": 0.5, "recall": 0.5}
    assert regression.soft(book, mine, "7_7") is None


def test_visual_regression_when_no_full_gold(tmp_path):
    book = toy_book(tmp_path)
    write(
        tmp_path, "gold/quiz_visual.json", {"1.1": {"questions": 2, "depth": [1, 2], "standard": "12A.1.1"}}
    )
    rec = {
        "id": "1.1",
        "lesson_quiz": {
            "value": {
                "questions": 2,
                "depth": [1, 2],
                "standards_by_question": {"1": ["12A.1.1"], "2": ["12A.1.1"]},
            },
            "status": "ok",
        },
    }
    assert regression.vs_gold(book, rec, "1_1") == {
        "quiz_questions": True,
        "quiz_depths": True,
        "quiz_standards_union": True,
        "quiz_status_ok": True,
    }
    assert regression.vs_gold(book, {**rec, "id": "2.2"}, "2_2") is None
