"""مستخرج الخطة الفصلية: صفوف اصطناعية بصياغتنا، لا نص من وثيقة الوزارة ولا pdfplumber."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.extraction import term_plan
from tools.extraction.term_plan import PageTable, TermPlanError, logical, main, parse, week_start

REFERENCE = term_plan.COURSES / "g10-s1" / "term_plan.json"
HEAD = ["الوحدة", "الزمن", "الدروس", "عدد الحصص"]
WIDE_HEAD = ["ملاحظات", "عدد الحصص", "الدروس", "الزمن", "الوحدة"]  # صفحة لاحقة زاد فيها عمود وتبدّل الترتيب
TEXTS = {
    ("orientation", None): "تهيئة وبداية الفصل",
    ("quiz", None): "مراجعة واختبار الوحدة",
    ("review", "midterm"): "مراجعة اختبار منتصف الفصل",
    ("exam", "midterm"): "اختبار منتصف الفصل",
    ("review", "final"): "مراجعة اختبار نهاية الفصل",
    ("project", None): "مشروع تطبيقي",
    ("support", None): "دعم ومعالجة",
}


def span(start: str, style: int = 0) -> str:
    """خلية الزمن لأسبوع يبدأ في `start`، بترتيب أرقام مضطرب يختلف بحسب `style`."""
    sun = date.fromisoformat(start)
    thu = sun + timedelta(days=4)
    return (
        f"{thu.month}/{thu.day} - {sun.day}/{sun.month}/{sun.year}",
        f"{sun.year}/{sun.month}/{sun.day} الى {thu.day}/{thu.month}/{thu.year}",
        f"{thu.day}/{thu.month}/{sun.year}\n{sun.day}/{sun.month}",
    )[style % 3]


def item_text(item: dict) -> str:
    if item["kind"] == "lesson":
        return f"الدرس {item['lesson']}: عنوان من عندنا"
    return TEXTS[item["kind"], item.get("scope")]


def tables_of(plan: dict) -> list[PageTable]:
    """جداول اصطناعية تحمل خطة بصيغة العقد: الرئيسي على صفحتين بترويستين مختلفتين، ثم الإثرائي."""
    first, second = [HEAD], [WIDE_HEAD]
    for index, week in enumerate(plan["weeks"]):
        for position, item in enumerate(week["items"]):
            time = span(week["start"], index) if position == 0 else None  # خلية الزمن مدموجة رأسيًّا
            text, periods = item_text(item), str(item["periods"])
            if index < 6:
                first.append(["" if position == 0 else None, time, text, periods])
            else:
                second.append(["", periods, text, time, None])
        if week["n"] == 8:  # أسبوع إجازة بلا حصص بين الثامن والعاشر
            second.append(["", "", "إجازة منتصف الفصل", span("2026-10-25"), None])
    enrichment = [["الدروس والأمثلة الإثرائية", ""]]
    enrichment += [[f"الدرس {code}", ""] for code in plan["enrichment_lessons"]]
    enrichment += [
        [f"الدرس {code}", "مثال " + "، ".join(map(str, numbers))]
        for code, numbers in plan["enrichment_examples"].items()
    ]
    return [PageTable(1, first), PageTable(2, second), PageTable(4, enrichment)]


def week_table(*rows: list, start: str = "2026-08-30") -> PageTable:
    """أسبوع واحد: كل صف (نص، حصص) أو (نص، حصص، خلية وحدة)."""
    body = []
    for position, (text, periods, *unit) in enumerate(rows):
        body.append([unit[0] if unit else "", span(start) if position == 0 else None, text, periods])
    return PageTable(2, [HEAD, *body])


@pytest.fixture
def reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def test_logical_reverses_text_and_keeps_number_runs():
    assert logical("2.10 سردلا") == "الدرس 2.10"
    assert logical("30/8/2026 نمزلا") == "الزمن 30/8/2026"
    assert logical("5 ،4 لاثم") == "مثال 4، 5"
    # أشكال العرض تعود حروفًا، والأسطر تبقى على ترتيبها
    assert logical("ﻝﺎﺜﻣ\n12 سرد") == "مثال\nدرس 12"


def test_week_start_from_shuffled_numbers():
    assert week_start([9, 3, 30, 8, 2026]) == date(2026, 8, 30)
    assert week_start([2026, 5, 11, 1]) == date(2026, 11, 1)  # الشهر مرة واحدة
    assert week_start([31, 12, 2026, 27, 12, 2026]) == date(2026, 12, 27)
    assert week_start([8, 9, 2026]) is None  # لا خميس بين الأرقام
    assert week_start([6, 9, 10, 9], after=date(2026, 8, 30)) == date(
        2026, 9, 6
    )  # بلا سنة: من الأسبوع السابق
    assert week_start([6, 9, 10, 9]) is None


def test_week_start_without_thursday_falls_back_to_the_only_later_sunday():
    previous = date(2026, 11, 22)
    # الأحد 29/11 موجود ويوم الخميس 3/12 غائب
    assert week_start([11, 29, 2026, 12], after=previous) == date(2026, 11, 29)
    # بلا أسبوع سابق لا بديل: الأسبوع الأول يلزمه الخميس
    assert week_start([11, 29, 2026, 12]) is None
    # البديل بعد السابق تمامًا: الأسبوع نفسه لا يُعاد
    assert week_start([11, 29, 2026, 12], after=date(2026, 11, 29)) is None


def test_week_start_fallback_refuses_two_sunday_candidates():
    # 8/11 و15/11 أحدان ولا خميس لأي منهما: لا تخمين
    assert week_start([11, 8, 15, 2026], after=date(2026, 11, 1)) is None
    # 11/1/2026 و1/11/2026 أحدان معًا
    assert week_start([1, 11, 2026], after=date(2025, 12, 28)) is None


def test_week_start_prefers_the_thursday_rule_when_it_succeeds():
    # 8/11 مع خميسه 12، و15/11 أحد بلا خميس: القاعدة الأصلية تحسم
    assert week_start([11, 8, 12, 15, 2026], after=date(2026, 11, 1)) == date(2026, 11, 8)
    # الأسبوع السابق نفسه مقبول بالقاعدة الأصلية (>=) ولا يصل إلى البديل
    assert week_start([9, 3, 30, 8, 2026], after=date(2026, 8, 30)) == date(2026, 8, 30)


def test_reference_plan_round_trips_through_synthetic_rows(reference):
    extracted = parse(tables_of(reference))
    assert extracted["weeks"] == reference["weeks"]
    assert extracted["sessions_per_week"] == 5
    assert extracted["enrichment_lessons"] == reference["enrichment_lessons"]
    assert extracted["enrichment_examples"] == reference["enrichment_examples"]
    assert not set(extracted) & set(term_plan.MANUAL_FIELDS)


def test_vertical_merge_and_holiday_week_is_skipped():
    table = PageTable(
        1,
        [
            HEAD,
            ["", span("2026-10-18"), "مشروع تطبيقي", "2"],
            [None, None, "دعم ومعالجة", "2"],  # خلية الزمن المدموجة: يتبع الأسبوع نفسه
            ["", span("2026-10-25"), "إجازة منتصف الفصل", ""],
            [None, None, "اختبارات مغلقة", None],
            ["", span("2026-11-01"), "الدرس 2.7", "3"],
            [None, None, "الدرس 2.8", "2"],
        ],
    )
    weeks = parse([table])["weeks"]
    assert [(w["n"], w["start"], w["end"]) for w in weeks] == [
        (1, "2026-10-18", "2026-10-22"),
        (3, "2026-11-01", "2026-11-05"),
    ]
    assert [len(w["items"]) for w in weeks] == [2, 2]


def test_week_continues_on_next_page_with_blank_or_repeated_time():
    first = PageTable(1, [HEAD, ["", span("2026-09-06"), "الدرس 1.2", "3"]])
    blank = PageTable(2, [HEAD, ["", "", "الدرس 1.3", "2"]])
    repeated = PageTable(2, [HEAD, ["", span("2026-09-06", 1), "الدرس 1.3", "2"]])
    for second in (blank, repeated):
        (week,) = parse([first, second])["weeks"]
        assert [item["lesson"] for item in week["items"]] == ["1.2", "1.3"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("الدرس 2.10: عنوان من عندنا", {"kind": "lesson", "lesson": "2.10"}),
        ("تهيئة الطلبة", {"kind": "orientation"}),
        ("بداية الفصل", {"kind": "orientation"}),
        ("مراجعة واختبار الوحدة", {"kind": "quiz", "unit": 1}),
        ("مراجعة اختبار منتصف الفصل", {"kind": "review", "scope": "midterm"}),
        ("اختبار منتصف الفصل", {"kind": "exam", "scope": "midterm"}),
        ("مراجعة اختبار نهاية الفصل", {"kind": "review", "scope": "final"}),
        ("مشروع تطبيقي", {"kind": "project"}),
        ("دعم ومعالجة", {"kind": "support"}),
        # الخط يسقط الباء والهمزة: الكلمات ناقصة والتصنيف نفسه
        ("تهية الطلة", {"kind": "orientation"}),
        ("داية الفصل", {"kind": "orientation"}),
        ("مراجعة واختار الوحدة", {"kind": "quiz", "unit": 1}),
        ("مراجعة اختار منتصف الفصل", {"kind": "review", "scope": "midterm"}),
        ("اختار منتصف الفصل", {"kind": "exam", "scope": "midterm"}),
        ("مراجعة اختار نهاية الفصل", {"kind": "review", "scope": "final"}),
    ],
)
def test_every_item_kind(text, expected):
    (week,) = parse([week_table((text, "5"))])["weeks"]
    assert week["items"] == [{**expected, "periods": 5}]


def test_quiz_unit_from_text_then_unit_cell_then_last_lesson_then_order():
    quiz = "مراجعة واختبار الوحدة"

    def unit(*rows):
        items = parse([week_table(*rows)])["weeks"][0]["items"]
        return [item["unit"] for item in items if item["kind"] == "quiz"]

    assert unit((f"{quiz} 3", "5", "الوحدة 2")) == [3]
    assert unit(("الدرس 1.3", "4", "الوحدة 2"), (quiz, "1", None)) == [2]  # خلية الوحدة المدموجة جارية
    assert unit(("الدرس 2.10", "4"), (quiz, "1")) == [2]
    assert unit((quiz, "2"), (quiz, "3")) == [1, 2]


def test_unknown_item_is_rejected_with_page_and_row_not_text():
    table = week_table(("الدرس 1.1", "3"), ("نشاط لا نعرفه", "2"))
    with pytest.raises(TermPlanError) as error:
        parse([table])
    assert "الصفحة 2، الصف 3" in str(error.value)
    assert "نشاط" not in str(error.value)


def test_item_with_periods_and_unreadable_week_date_is_rejected():
    table = PageTable(3, [HEAD, ["", "8 - 9 / 2026", "الدرس 1.1", "5"]])
    with pytest.raises(TermPlanError, match="الصفحة 3، الصف 2"):
        parse([table])


def test_enrichment_lessons_examples_and_theorem_numbers():
    table = PageTable(
        4,
        [
            ["الدروس الاثرائية", None],  # الهمزة ساقطة من الترويسة
            ["الدرس", "المحتوى"],
            ["1.4", ""],
            ["2.7", "مثال 4، 5"],
            ["2.10", "مثال 4"],
            ["3.3", "مثال 1 و مثال 2\nاثبات النظريتين 2-1 و 3-1"],
            [None, "مثال 6"],  # خلية الدرس مدموجة: المثال للدرس الجاري
            ["3.1", "الدرس كله"],
        ],
    )
    main_table = week_table(("الدرس 1.1", "5"))
    extracted = parse([main_table, table])
    assert extracted["enrichment_lessons"] == ["1.4", "3.1"]
    assert extracted["enrichment_examples"] == {"2.7": [4, 5], "2.10": [4], "3.3": [1, 2, 6]}


def test_enrichment_row_with_unreadable_examples_is_rejected():
    table = PageTable(4, [["الدروس الإثرائية"], ["2.7 مثال"]])
    with pytest.raises(TermPlanError, match="الصفحة 4، الصف 2"):
        parse([week_table(("الدرس 1.1", "5")), table])


def test_table_without_header_is_ignored():
    stray = PageTable(1, [["الدرس 9.9", "7", "x"]])
    assert parse([stray, week_table(("الدرس 1.1", "5"))])["weeks"][0]["items"] == [
        {"kind": "lesson", "lesson": "1.1", "periods": 5}
    ]
    with pytest.raises(TermPlanError):
        parse([stray])


def test_fingerprint_of_a_cell():
    cells = [
        None,
        "",
        " \n",
        span("2026-08-30"),
        "الدرس 2.10: عنوان",
        "5",
        " 12 ",
        "٣",
        "مثال 4",
        "123",
        "6/9",
    ]
    assert "".join(map(term_plan.fingerprint, cells)) == "N--YL###ttt"


def test_headerless_continuation_with_extra_column_in_another_position():
    first = PageTable(1, [HEAD, ["", span("2026-08-30"), "الدرس 1.1", "5"]])
    continuation = PageTable(  # خمسة أعمدة بترتيب غير ترتيب الترويسة: درس، زائد، حصص، زمن، فارغ
        2,
        [
            ["الدرس 1.2", "", "3", span("2026-09-06", 1), ""],
            ["الدرس 1.3", "ملاحظة من عندنا", "2", None, ""],
            ["مشروع تطبيقي", "", "5", span("2026-09-13", 2), ""],
        ],
    )
    weeks = parse([first, continuation])["weeks"]
    assert [(w["n"], w["start"]) for w in weeks] == [(1, "2026-08-30"), (2, "2026-09-06"), (3, "2026-09-13")]
    assert weeks[1]["items"] == [
        {"kind": "lesson", "lesson": "1.2", "periods": 3},
        {"kind": "lesson", "lesson": "1.3", "periods": 2},
    ]
    assert weeks[2]["items"] == [{"kind": "project", "periods": 5}]


def test_headerless_continuation_of_original_width_after_single_column_tables():
    first = PageTable(1, [HEAD, ["", span("2026-08-30"), "الدرس 1.1", "5"]])
    notes = [PageTable(2, [["توقيع من عندنا"]]), PageTable(2, [["ملاحظة أولى"], ["ملاحظة ثانية"]])]
    continuation = PageTable(
        3,
        [
            ["", span("2026-09-06"), "الدرس 1.2", "3"],
            [None, None, "دعم ومعالجة", "2"],
        ],
    )
    weeks = parse([first, *notes, continuation])["weeks"]
    assert [w["n"] for w in weeks] == [1, 2]
    assert weeks[1]["items"] == [
        {"kind": "lesson", "lesson": "1.2", "periods": 3},
        {"kind": "support", "periods": 2},
    ]


def test_holiday_rows_with_year_in_first_column_do_not_pick_the_time_column():
    # العمود الأول يحمل سنة في ثلاثة صفوف بلا حصص، وعمود الزمن الحقيقي في خليتين فقط (المدموجة None)
    continuation = PageTable(
        2,
        [
            ["", "الدرس 2.5", "3", span("2026-10-18")],
            [None, "الدرس 2.6", "2", None],
            ["إجازة منتصف الفصل 2026", None, None, None],
            ["اختبارات مغلقة 2026", None, None, None],
            ["عطلة العام 2026/2027", None, None, None],
            ["", "الدرس 2.7", "5", span("2026-11-01", 1)],
        ],
    )
    weeks = parse([continuation])["weeks"]
    assert [(w["n"], w["start"]) for w in weeks] == [(1, "2026-10-18"), (3, "2026-11-01")]
    assert [len(w["items"]) for w in weeks] == [2, 1]


def test_enrichment_table_is_found_by_content_without_its_header_word():
    table = PageTable(
        4,
        [
            ["الدرس", "المحتوى", "ملاحظات"],  # ترويسة بلا الكلمة: تُتخطى
            ["1.4", "الدرس كله", ""],
            ["2.7", "مثال 4، 5", ""],
            ["3.3", "مثال 1 و مثال 2\nاثبات النظريتين 2-1 و 3-1", "ملاحظة من عندنا"],
        ],
    )
    extracted = parse([week_table(("الدرس 1.1", "5")), table])
    assert extracted["enrichment_lessons"] == ["1.4"]
    assert extracted["enrichment_examples"] == {"2.7": [4, 5], "3.3": [1, 2]}


def test_quiz_unit_after_continuation_is_from_last_lesson_not_a_stale_unit_cell():
    first = week_table(("الدرس 2.10", "5", "الوحدة 2"))
    continuation = PageTable(
        3,
        [
            ["", span("2026-09-06"), "الدرس 3.1", "4"],
            [None, None, "مراجعة واختبار الوحدة", "1"],
        ],
    )
    weeks = parse([first, continuation])["weeks"]
    assert weeks[1]["items"][1] == {"kind": "quiz", "unit": 3, "periods": 1}


def test_headerless_table_with_periods_but_unresolved_columns_is_rejected_with_page():
    first = week_table(("الدرس 1.1", "5"))
    no_time = PageTable(5, [["الدرس 1.2", "3", "حاشية"], ["الدرس 1.3", "2", "حاشية"]])
    with pytest.raises(TermPlanError, match="الصفحة 5") as error:
        parse([first, no_time])
    assert "حاشية" not in str(error.value)


def test_headerless_signature_table_is_ignored():
    signatures = PageTable(3, [["الاسم", "التوقيع", "التاريخ"], ["", "", ""], ["المعلم", "", "2026"]])
    assert len(parse([week_table(("الدرس 1.1", "5")), signatures])["weeks"]) == 1


def run(tables, *args):
    return main(["plan.pdf", "--course", "g10-s1", *map(str, args)], read=lambda pdf: tables)


def test_check_prints_one_line_match(reference, capsys):
    assert run(tables_of(reference), "--check", REFERENCE) == 0
    assert capsys.readouterr().out == "مطابق\n"


def test_check_prints_differing_week_keys_only(reference, capsys):
    reference["weeks"][2]["items"][0]["periods"] = 2  # الأسبوع 3: حصة تنتقل بين بندين والمجموع ثابت
    reference["weeks"][2]["items"][2]["periods"] = 2
    reference["enrichment_examples"]["2.5"] = [4]
    assert run(tables_of(reference), "--check", REFERENCE) == 1
    assert capsys.readouterr().out == "فروق: 2 (الأسبوع 3، enrichment_examples)\n"


def test_out_keeps_manual_fields_and_is_idempotent(reference, tmp_path, capsys):
    out = tmp_path / "term_plan.json"
    manual = {name: reference[name] for name in term_plan.MANUAL_FIELDS}
    out.write_text(
        json.dumps({**manual, "weeks": [], "sessions_per_week": 3}, ensure_ascii=False), encoding="utf-8"
    )
    assert run(tables_of(reference), "--out", out) == 0
    written = out.read_text(encoding="utf-8")
    assert json.loads(written) == reference
    assert list(json.loads(written)) == list(reference)  # ترتيب المفاتيح كما في ملف المقرر
    assert run(tables_of(reference), "--out", out) == 0
    assert out.read_text(encoding="utf-8") == written
    assert "الدرس" not in capsys.readouterr().out


def test_out_is_not_written_when_plan_fails_validation(reference, tmp_path, capsys):
    # بلا الأيام الفاقدة اليدوية: أسبوع الحصص الأربع لا يجتاز المحرك
    out = tmp_path / "new" / "term_plan.json"
    assert run(tables_of(reference), "--out", out) == 2
    assert not out.exists()
    assert "أسبوع 7" in capsys.readouterr().err


def test_unknown_course_is_an_error(reference, capsys):
    assert main(["plan.pdf", "--course", "no-such-course"], read=lambda pdf: tables_of(reference)) == 2
    assert "no-such-course" in capsys.readouterr().err


def test_reader_is_lazy_about_pdfplumber():
    source = Path(term_plan.__file__).read_text(encoding="utf-8")
    assert "\nimport pdfplumber" not in source and "\nfrom pdfplumber" not in source
