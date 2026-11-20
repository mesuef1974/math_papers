"""أرقام الكتاب في دروس الثاني عشر: الكاتب idempotent ولا يمسّ حقلًا غير `page` و`exercise_groups` وأرقام الدليل.

المدخل مصطنع (صفحات وروابط مختلقة) على نسخة مؤقتة من ملفات الدروس المودَعة؛ لا يُقرأ مجلد الكتاب الحقيقي.
"""

import json
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.domain.book_numbers import (
    GUIDE_FIELDS,
    annotate,
    exercise_groups,
    guide_numbers,
    template_doks,
    template_max,
)
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.schemas import LessonData

COURSE = "g12-sci-s1"
LESSONS = COURSES_DIR / COURSE / "lessons"
BOOK_OUTPUTS = ("printed_pages.json", "exercise_links.json", "examples.json", "book.yaml", ".stamps.json")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip(lesson: dict) -> dict:
    rest = {k: v for k, v in lesson.items() if k != "exercise_groups"}
    rest["examples"] = [{k: v for k, v in e.items() if k != "page"} for e in lesson["examples"]]
    return rest


@pytest.fixture
def workspace(tmp_path):
    """نسخة من دروس المقرر، ومجلد كتاب مصطنع: كل مثال يبدأ في صفحة ملف مختلقة، والمطبوعة = صفحة الملف − 20."""
    courses = tmp_path / "courses"
    shutil.copytree(LESSONS, courses / COURSE / "lessons")
    book = tmp_path / "book"
    book.mkdir()
    examples, printed = {}, {}
    for i, path in enumerate(sorted(LESSONS.glob("lesson_*.json"))):
        lesson = _read(path)
        rows = [{"n": e["number"], "start": 100 + 20 * i + e["number"]} for e in lesson["examples"]]
        examples[lesson["lesson"]] = {"value": rows, "source": "derived", "status": "ok"}
        printed |= {str(row["start"]): row["start"] - 20 for row in rows}
    links = {
        "2.1": {
            "value": [
                {"example": 3, "exercises": [10, 9, 35, 50], "pages": [140]},
                {"example": 1, "exercises": [1, 2], "pages": [141]},
                {"example": 2, "exercises": [], "pages": []},
                {"example": 17, "exercises": [4], "pages": []},  # ليس من أمثلة الدرس
            ],
            "source": "teacher",
            "status": "ok",
        },
        "2.2": {"value": [{"example": 1, "exercises": [1]}], "source": "derived", "status": "review"},
    }
    for name, data in (("examples", examples), ("printed_pages", printed), ("exercise_links", links)):
        payload = data if name == "printed_pages" else {"lessons": data}
        (book / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return courses, book


def _run(courses, book, **options):
    call_command("write_book_numbers", COURSE, source=str(book), courses_dir=str(courses), **options)
    return {p.name: p.read_bytes() for p in sorted((courses / COURSE / "lessons").glob("*.json"))}


def test_template_levels_give_exercise_depths():
    templates = [
        {"label": "مراجعة سريعة 1-2", "level": "R"},  # ترقيم آخر: يُهمل
        {"label": "1-3", "level": "K"},
        {"label": "4", "level": "A"},
        {"label": "5–6 (أسئلة اختبار)", "level": "R"},
        {"label": "7", "level": ""},
    ]
    assert template_doks(templates) == {1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3}
    rows = [{"example": 2, "exercises": [7, 5, 1]}, {"example": 1, "exercises": [4, 2]}]
    assert exercise_groups(rows, template_doks(templates), {1, 2}) == [
        {"example": 1, "dok": 1, "exercises": [2]},
        {"example": 1, "dok": 2, "exercises": [4]},
        {"example": 2, "dok": 1, "exercises": [1]},
        {"example": 2, "dok": 2, "exercises": [7]},  # بلا مستوى: 2
        {"example": 2, "dok": 3, "exercises": [5]},
    ]


def test_annotate_is_pure_and_idempotent():
    lesson = _read(LESSONS / "lesson_2_1.json")
    before = json.dumps(lesson, ensure_ascii=False)
    once = annotate(lesson, {1: 61, 3: 64}, [{"example": 3, "exercises": [9]}])
    assert json.dumps(lesson, ensure_ascii=False) == before
    assert json.dumps(annotate(once, {1: 61, 3: 64}, [{"example": 3, "exercises": [9]}])) == json.dumps(once)
    given = {1: 61, 3: 64}  # ما غاب من الجدول يبقى كما كان في الملف
    assert [e.get("page") for e in once["examples"]] == [
        given.get(e["number"], e.get("page")) for e in lesson["examples"]
    ]
    assert [e["page"] for e in once["examples"] if e["number"] in given] == [61, 64]
    assert list(once["examples"][0])[:2] == ["number", "page"]
    assert annotate(once, {}, None) == once  # بلا مدخل جديد يبقى ما كُتب


def test_writer_adds_pages_and_groups_and_touches_nothing_else(workspace):
    courses, book = workspace
    original = {p.name: _read(p) for p in sorted(LESSONS.glob("lesson_*.json"))}
    written = {name: json.loads(raw) for name, raw in _run(courses, book).items()}
    assert written.keys() == original.keys()
    for i, (name, lesson) in enumerate(written.items()):
        assert _strip(lesson) == _strip(original[name]), name
        assert list(_strip(lesson)) == list(_strip(original[name])), name  # ترتيب المفاتيح أيضًا
        assert [e["page"] for e in lesson["examples"]] == [
            80 + 20 * i + e["number"] for e in lesson["examples"]
        ], name
        LessonData(**lesson)
    assert written["lesson_2_1.json"]["exercise_groups"] == [
        {"example": 1, "dok": 1, "exercises": [1, 2]},
        {"example": 3, "dok": 1, "exercises": [9]},
        {"example": 3, "dok": 2, "exercises": [10, 50]},
        {"example": 3, "dok": 3, "exercises": [35]},
    ]
    # حالته review: ينتظر اعتماد المالك، فتبقى مجموعاته كما كانت في الملف
    assert written["lesson_2_2.json"].get("exercise_groups") == original["lesson_2_2.json"].get(
        "exercise_groups"
    )


def test_writer_is_idempotent(workspace):
    courses, book = workspace
    first = _run(courses, book)
    assert first == _run(courses, book)
    assert first != {p.name: p.read_bytes() for p in sorted(LESSONS.glob("lesson_*.json"))}


def test_include_review_writes_unreviewed_links(workspace):
    courses, book = workspace
    written = _run(courses, book, include_review=True)
    groups = json.loads(written["lesson_2_2.json"])["exercise_groups"]
    assert [g["example"] for g in groups] == [1] and groups[0]["exercises"] == [1]


def test_missing_table_and_out_of_range_page_are_errors(workspace):
    courses, book = workspace
    (book / "printed_pages.json").write_text(json.dumps({"101": 1000}))
    with pytest.raises(CommandError, match="خارج المدى"):
        _run(courses, book)
    (book / "printed_pages.json").unlink()
    with pytest.raises(CommandError, match="غير موجود"):
        _run(courses, book)
    with pytest.raises(CommandError, match="لا ملفات دروس"):
        call_command("write_book_numbers", "g10-s1", source=str(book), courses_dir=str(courses))


def _field(value, status="ok"):
    return {"value": value, "source": "guide", "status": status}


def _record(total: int, **over) -> dict:
    """سجل درس مصطنع بشكل مخرج مرحلة `lesson` (نص المصطلح مختلق: لا يدخل الملف منه إلا عدده)."""
    return {
        "task_guide": _field({"basic": "1-12, 15", "advanced": "9-20"}),
        "lesson_quiz": _field({"questions": 3, "depth": [1, 2, 2]}),
        "exercises": _field(list(range(1, total + 1))),
        "vocabulary": _field(
            [{"ar": "س", "en": "x", "kind": "new"}, {"ar": "ص", "en": "y", "kind": "review"}] * 2
            + [{"ar": "ع", "en": "z", "kind": "new"}]
        ),
    } | over


def test_guide_numbers_take_only_accepted_well_formed_fields():
    assert guide_numbers(_record(20)) == {
        "task_basic": "1-12, 15",
        "task_advanced": "9-20",
        "quiz_depths": [1, 2, 2],
        "exercises_total": 20,
        "vocab_new": 3,
        "vocab_review": 2,
    }
    unread = _record(
        20,
        task_guide=_field({"basic": "انظر الدليل", "advanced": "9-20"}),  # ليس مدى أرقام
        lesson_quiz=_field({"questions": 0, "depth": []}, "missing"),
        exercises=_field(list(range(1, 21)), "review"),
        vocabulary=_field(None, "missing"),
    )
    assert guide_numbers(unread) == {}
    assert guide_numbers(unread, ("ok", "review")) == {"exercises_total": 20}
    assert guide_numbers(_record(20, lesson_quiz=_field({"depth": [1, 7]}))).get("quiz_depths") is None
    assert guide_numbers({}) == {}


def test_annotate_places_guide_numbers_deterministically():
    lesson = _read(LESSONS / "lesson_2_1.json")
    before = json.dumps(lesson, ensure_ascii=False)
    numbers = guide_numbers(_record(20))
    once = annotate(lesson, {}, None, numbers)
    assert json.dumps(lesson, ensure_ascii=False) == before
    # الترتيب لا يتبع ترتيب المدخل، والتطبيق الثاني لا يغيّر شيئًا
    assert json.dumps(annotate(once, {}, None, dict(reversed(numbers.items())))) == json.dumps(once)
    keys = list(once)
    at = keys.index("standards") + 1
    assert tuple(keys[at : at + len(GUIDE_FIELDS)]) == GUIDE_FIELDS
    rest = {k: v for k, v in once.items() if k not in GUIDE_FIELDS}
    assert rest == {k: v for k, v in lesson.items() if k not in GUIDE_FIELDS}  # ومنها page وexercise_groups
    assert annotate(once, {}, None) == once  # بلا مدخل جديد يبقى ما كُتب
    assert annotate(once, {}, None, {"exercises_total": 21})["task_basic"] == "1-12, 15"
    with pytest.raises(ValueError, match="ليست من أرقام الدليل"):
        annotate(lesson, {}, None, {"title": "نص"})


def test_writer_writes_guide_numbers_and_touches_no_text_pages_or_groups(workspace):
    courses, book = workspace
    original = {p.name: _read(p) for p in sorted(LESSONS.glob("lesson_*.json"))}
    totals = {name: template_max(lesson["templates"]) for name, lesson in original.items()}
    assert all(totals.values())
    records = book / "lessons"
    records.mkdir()
    (records / "lesson_2_1.json").write_text(json.dumps(_record(totals["lesson_2_1.json"])), "utf-8")
    # يخالف آخر رقم في قوالب الدرس: العدد لا يُكتب، وبقية الحقول تُكتب
    (records / "lesson_2_2.json").write_text(json.dumps(_record(totals["lesson_2_2.json"] + 3)), "utf-8")
    unread = _record(totals["lesson_2_3.json"])
    unread = {k: {**v, "status": "review"} for k, v in unread.items()}
    (records / "lesson_2_3.json").write_text(json.dumps(unread), "utf-8")
    first = _run(courses, book, guide_only=True)
    assert first == _run(courses, book, guide_only=True)
    written = {name: json.loads(raw) for name, raw in first.items()}
    for name, lesson in written.items():
        rest = {k: v for k, v in lesson.items() if k not in GUIDE_FIELDS}
        assert rest == {k: v for k, v in original[name].items() if k not in GUIDE_FIELDS}, name
        LessonData(**lesson)
    got = written["lesson_2_1.json"]
    assert [got[k] for k in GUIDE_FIELDS] == ["1-12, 15", "9-20", [1, 2, 2], totals["lesson_2_1.json"], 3, 2]
    assert written["lesson_2_2.json"]["quiz_depths"] == [1, 2, 2]
    assert written["lesson_2_2.json"].get("exercises_total") == original["lesson_2_2.json"].get(
        "exercises_total"
    )
    untouched = [name for name in written if name not in ("lesson_2_1.json", "lesson_2_2.json")]
    assert all(first[name] == (LESSONS / name).read_bytes() for name in untouched)  # ومنها ما حالته review
    with pytest.raises(CommandError, match="سجلات الدروس"):
        _run(courses, book, guide_only=True, records=str(book / "none"))


def test_no_book_folder_file_is_committed():
    """مخرجات مجلد الكتاب (جداول الصفحات والروابط والإعداد) تبقى خارج المستودع."""
    root = COURSES_DIR.parents[3]
    for folder in (root / "apps", root / "tools"):
        found = [p for name in BOOK_OUTPUTS for p in folder.rglob(name)]
        assert not found, found
