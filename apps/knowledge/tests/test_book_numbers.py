"""أرقام كتاب الطالب في دروس الثاني عشر: الكاتب idempotent ولا يمسّ حقلًا غير `page` و`exercise_groups`.

المدخل مصطنع (صفحات وروابط مختلقة) على نسخة مؤقتة من ملفات الدروس المودَعة؛ لا يُقرأ مجلد الكتاب الحقيقي.
"""

import json
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.domain.book_numbers import annotate, exercise_groups, template_doks
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
    assert "exercise_groups" not in written["lesson_2_2.json"]  # حالته review: ينتظر اعتماد المالك


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


def test_no_book_folder_file_is_committed():
    """مخرجات مجلد الكتاب (جداول الصفحات والروابط والإعداد) تبقى خارج المستودع."""
    root = COURSES_DIR.parents[3]
    for folder in (root / "apps", root / "tools"):
        found = [p for name in BOOK_OUTPUTS for p in folder.rglob(name)]
        assert not found, found
