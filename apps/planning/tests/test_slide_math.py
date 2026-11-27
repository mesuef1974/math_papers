"""معادلات شرائح الحصة: ما يُكتب معادلة، وشجرة OMML في الملف، والحارس S15، وتغطية المحوّل لأوامر البنك."""

import re
import zipfile
from io import BytesIO

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers.domain.item_bank import ItemBankError, exit_ticket
from apps.papers.word import omml
from apps.planning.domain.deck import build_period_deck
from apps.planning.domain.plain_math import MATH, convertible
from apps.planning.domain.prep_checks import FAIL, PASS
from apps.planning.domain.slide_math import segments, unicode_latex
from apps.planning.pptx_checks import s15_native_math
from apps.planning.pptx_export import build_period_pptx
from apps.planning.selectors import lesson_preps

from .test_period_pptx import clips_for


def math_of(text: str) -> list[str]:
    return [part for is_math, part in segments(text) if is_math]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("يحلل أثر قيمة a في اتجاه فتح منحنى الدالة f(x) = ax² واتساعه", ["a", "f(x) = ax^{2}"]),
        ("منحنى الدالة g(x) = (x − h)² عن الرئيسة", ["g(x) = (x - h)^{2}"]),
        ("عبارة x²+bx ونموذج مساحة", ["x^{2}+bx"]),
        ("بصيغة e^(g(x))·g′(x)", ["e^{g(x)}·g′(x)"]),
        ("فيها tan(ax) / (bx) وحد", [r"\tan (ax) / (bx)"]),
        ("حدّد الدالة $f(x)=-5x^2$ المتناقصة.", ["f(x)=-5x^2"]),
        ("حلّ تمارين الكتاب: 16-19 (DOK 2).", []),
    ],
)
def test_segments_find_the_math_inside_arabic_text(text, expected):
    assert math_of(text) == expected


def test_segments_keep_all_text_in_order():
    text = "صف الدالة (x) ثم $x=1$."
    assert "".join(part for _, part in segments(text)) == "صف الدالة (x) ثم x=1."


def test_unicode_latex_handles_roots_and_subscripts():
    assert unicode_latex("√(x+1) + a₁") == r"\sqrt{x+1} + a_{1}"


@pytest.mark.django_db
def test_every_deck_writes_native_equations_and_s15_catches_text_math(loaded_courses):
    row = next(r for r in lesson_preps(GRADE10_SLUG) if r.prep.lesson == "1.1")
    data = build_period_pptx(build_period_deck(row.prep, clips_for(row.prep)))
    assert s15_native_math(data).status == PASS
    with zipfile.ZipFile(BytesIO(data)) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    slides = [n for n in parts if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
    xml = b"".join(parts[n] for n in slides).decode()
    assert "<a14:m><m:oMath>" in xml and "<m:sSup>" in xml and "w:rPr" not in xml
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, part in parts.items():
            if name == "ppt/slides/slide1.xml":
                part = part.replace(b"</a:t>", " f(x)=x²</a:t>".encode(), 1)
            z.writestr(name, part)
    assert s15_native_math(out.getvalue()).status == FAIL


@pytest.mark.parametrize("course", [GRADE10_SLUG, "g12-sci-s1"])
def test_omml_knows_every_command_the_item_bank_writes(course):
    known = {*omml.SYMBOLS, *omml.FUNCTIONS, *omml.SPACES, *omml.SILENT}
    known |= {"frac", "dfrac", "tfrac", "sqrt", "left", "lim", "text", "mbox", "mathrm", "mathbf"}
    known |= {"operatorname", "mathbb", "overline", "begin", "end", "{", "}", "|", "%"}
    seen = 0
    lessons = [f"{u}.{n}" for u in range(1, 6) for n in range(1, 12)]
    for lesson in lessons:
        for example in range(1, 7):
            for seed in range(6):
                try:
                    item = exit_ticket(course, lesson, example, seed=seed)
                except ItemBankError:
                    break
                for text in (item.stem, *(o.text for o in item.options)):
                    if not convertible(text):
                        continue
                    for latex in MATH.findall(text):
                        seen += 1
                        assert set(re.findall(r"\\([a-zA-Z]+|.)", latex)) <= known, latex
    assert seen
