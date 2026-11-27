"""فحص ربط الصيغ والأهداف بمثال الكتاب (`domain/skill_match.py`) بنصوص من تأليفنا."""

from apps.papers.domain.skill_match import match, stems

EXAMPLES = {
    1: "وصف اتجاه فتحة المنحنى واتساعه",
    2: "كتابة قاعدة الدالة من جدول القيم",
    3: "تحديد فترات تزايد الدالة وتناقصها",
}


def test_stems_drop_math_article_and_diacritics():
    assert stems("الدالَّةُ $f(x)=x^2$ دالة") == stems("دالة")


def test_wrong_tag_is_suspect():
    found = match("حدد الفترة التي تكون فيها الدالة متزايدة أو متناقصة", 1, EXAMPLES)
    assert (found.best, found.status) == (3, "suspect")


def test_right_tag_is_ok():
    assert match("أوجد قاعدة الدالة من الجدول", 2, EXAMPLES).status == "ok"


def test_no_common_word_is_unknown_not_guessed():
    assert match("احسب المساحة", 1, EXAMPLES).status == "unknown"
    assert match("جدول", 9, EXAMPLES).status == "unknown"
