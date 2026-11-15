import json

from tools.extraction import checks, examples, layout

from .conftest import TOY_PAGES, make_book


def test_numbers_in_ignores_running_text_and_big_numbers():
    text = "مثال 1\nمثال٢\nومثالاً 5\nمثال 40\nمثال 3.5"
    assert examples.numbers_in(text) == {1, 2}


def src(table):
    return lambda n: table.get(n, set())


def test_lesson_boundaries_chain_and_ends():
    per = {2: {1}, 3: {1, 2}, 4: {3}, 5: set(), 6: {8}}
    got = examples.lesson_boundaries((2, 6), {"ocr": src(per)}, None, 2)
    ex = {e["n"]: (e["start"], e["end"]) for e in got["examples"]}
    assert ex == {1: (2, 2), 2: (3, 3), 3: (4, 6)}  # 8 قفزة فوق السلسلة فترفض
    assert got["rejected"] == [8] and got["contiguous"] and got["monotone"]
    assert got["examples"][-1]["end_estimated"] is True
    assert all(e["status"] == "review" for e in got["examples"])  # مصدر واحد لا يكفي لـ ok


def test_last_example_stops_at_exercises_page():
    per = {1: {1}, 2: {2}}
    got = examples.lesson_boundaries((1, 4), {"ocr": src(per)}, 3, 2)
    assert got["examples"][-1]["end"] == 2


def test_two_independent_sources_make_ok_and_single_vision_stays_review():
    o = {1: {1}}
    v = {1: {1}, 2: {2}}
    got = examples.lesson_boundaries((1, 2), {"ocr": src(o), "vision": src(v)}, None, 2)
    assert [e["evidence"] for e in got["examples"]] == [["ocr", "vision"], ["vision"]]
    assert [e["status"] for e in got["examples"]] == ["ok", "review"]


def test_badges_are_authoritative_and_reject_others():
    ocr = {1: {1, 2, 3, 4, 5}, 2: {1, 2}, 3: {3}}  # OCR يلتقط إحالات لأمثلة أخرى
    badge = {2: {1}, 3: {2}}
    got = examples.lesson_boundaries((1, 3), {"ocr": src(ocr), "badge": src(badge)}, None, 2)
    assert got["authoritative"] == "badge"
    assert [(e["n"], e["start"]) for e in got["examples"]] == [
        (1, 2),
        (2, 3),
    ]  # الصفحة من الشارة لا من أول ظهور في OCR
    assert got["rejected"] == [3, 4, 5]
    assert all(e["status"] == "ok" for e in got["examples"])


def test_label_sequence_numbers_standalone_labels_across_pages():
    texts = {1: "مثال \nنص", 2: "على سبيل المثال في جملة\nمثال ٥\n", 3: "لا شيء", 4: "مثال"}
    assert examples.label_sequence(texts) == {1: {1}, 2: {2}, 4: {3}}


def test_sequence_numbering_source_in_build(toy):
    toy.cfg["examples"] = {"numbering": "sequence"}
    lay = layout.build(toy)
    pages = layout.load_pages(toy)
    # صفحات الدرس الأول (3 و4) فيها «مثال 1» و«مثال 2» برقم مقروء فلا سطر «مثال» وحده؛ الترقيم التسلسلي لا يضيف شيئًا
    got = examples.build(toy, lay, pages)["lessons"]["1.1"]
    assert [e["n"] for e in got["value"]] == [1, 2]


def test_build_over_toy_book_marks_single_source_review(toy):
    result = examples.build(toy, layout.build(toy), layout.load_pages(toy))
    first = result["lessons"]["1.1"]
    assert first["source"] == "derived"
    assert [(e["n"], e["start"], e["end"]) for e in first["value"]] == [(1, 3, 3), (2, 4, 4)]
    assert first["status"] == "review"  # OCR وحده
    assert examples.summarize(result)["examples"] == 3


def test_build_with_badges_dir_is_ok(toy):
    toy.cfg["dirs"]["badges"] = "badges"
    folder = toy.out / "badges"
    folder.mkdir()
    (folder / "0003.json").write_text(json.dumps([{"n": 1, "title": "x"}]), encoding="utf-8")
    (folder / "0004.json").write_text(json.dumps([{"n": 2}, {"n": "x"}]), encoding="utf-8")
    result = examples.build(toy, layout.build(toy), layout.load_pages(toy))
    assert result["lessons"]["1.1"]["status"] == "ok"
    assert result["lessons"]["1.1"]["authoritative"] == "badge"
    assert examples.badge_numbers(toy, 4) == {2}
    assert examples.badge_numbers(toy, 9) == set()


def test_vision_numbers_directory(toy):
    assert examples.vision_numbers(toy, 4) == set()  # لا dirs.vision في الإعداد
    toy.cfg["dirs"]["vision"] = "vision"
    (toy.out / "vision").mkdir()
    (toy.out / "vision" / "0004.json").write_text(json.dumps({"examples": [2, "x", 40]}), encoding="utf-8")
    assert examples.vision_numbers(toy, 4) == {2}
    assert examples.vision_numbers(toy, 3) == set()


def test_exercises_start_marker(toy):
    pages = layout.load_pages(toy)
    assert examples.exercises_start(toy, (2, 5), pages) == 5


# ---- المدقّقات


def test_exercise_numbers_from_line_starts():
    assert checks.exercise_numbers("1. أ\n٢) ب\nنص 7. ليس بداية\n 12 . ج") == {1, 2, 12}


def test_exercise_total_rules():
    assert checks.exercise_total(0, {1}, 5, 60) is None
    assert checks.exercise_total(10, set(range(1, 11)), 5, 60) is True
    assert checks.exercise_total(10, set(range(1, 10)), 5, 60) is True  # فرق واحد مقبول
    assert checks.exercise_total(10, set(range(1, 8)), 5, 60) is False
    assert checks.exercise_total(19, set(range(1, 15)), 5, 60, guide_max=19) is True  # شاهد دليل المهام


def test_task_guide_max():
    assert checks.task_guide_max({"basic": "1-5, 9", "advanced": "10–14"}) == 14
    assert checks.task_guide_max(None) == 0


QUIZ = """12A.1.1
نص سؤال
1 1
12A.1.1, 12A.1.2
2 2
12A.1.2
3 3
"""


def test_quiz_rows_and_consistency(toy):
    rows = checks.quiz_rows(toy, QUIZ)
    assert [(r["q"], r["depth"]) for r in rows] == [(1, 1), (2, 2), (3, 3)]
    assert rows[1]["standards"] == ["12A.1.1", "12A.1.2"]
    codes = checks.page_codes(toy, QUIZ)
    assert codes == ["12A.1.1", "12A.1.2"]
    assert checks.quiz_consistent(rows, codes) is True
    assert checks.quiz_consistent(rows, ["12A.9.9"]) is False
    assert checks.quiz_consistent([], codes) is None
    assert checks.quiz_summary(rows)["depth"] == [1, 2, 3]


def test_quiz_rejects_gap_in_numbers_and_duplicates(toy):
    text = "12A.1.1\n1 1\n12A.1.1\n2 1\n12A.1.1\n1 3\n"  # عمق ثم رقم السؤال: 1 ثم 1 مكرر ثم 3
    rows = checks.quiz_rows(toy, text)
    assert [r["q"] for r in rows] == [1, 3]  # المكرر يبقى أول صف
    assert checks.quiz_consistent(rows, ["12A.1.1"]) is False  # الأرقام غير متصلة


def test_run_over_toy_book(toy):
    lay = layout.build(toy)
    result = checks.run(toy, lay, {"1.1": 3, "1.2": 9})
    assert result["lessons"]["1.1"]["exercise_total_matches_independent_ocr"] is True
    assert result["lessons"]["1.2"]["exercise_total_matches_independent_ocr"] is False
    assert result["lessons"]["1.1"]["standard_found"] is True
    s = checks.summarize(result)
    assert s["failed"] == ["1.2"] and s["exercise_total_checked"] == 2


def test_run_without_claims_leaves_none(toy):
    result = checks.run(toy, layout.build(toy))
    assert all(v["exercise_total_matches_independent_ocr"] is None for v in result["lessons"].values())
    assert checks.summarize(result)["failed"] == []


def test_run_quiz_page_checked(tmp_path):
    pages = dict(TOY_PAGES)
    pages[8] = QUIZ
    book = make_book(
        tmp_path,
        pages,
        markers={"quiz": "12A"},
        layout={"end": "quiz", "anchor": "opener"},
    )
    lay = layout.build(book)
    lay["lessons"][1]["quiz"] = 8
    quiz = checks.run(book, lay)["lessons"]["1.2"]["quiz"]
    assert quiz["consistent"] is True and quiz["summary"]["questions"] == 3
