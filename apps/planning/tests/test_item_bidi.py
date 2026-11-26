"""نصوص بنود الدرس 1.2 كما تُعرض (إدخال النتائج والعرض): كل صيغة تبقى كما حوّلها `plain_math` بلا عزل داخلها."""

from apps.papers.domain.item_bank import ItemBankError, exit_ticket
from apps.planning.domain.check_items import item_stem, option_label, option_text
from apps.planning.domain.plain_math import MATH, plain_math


def _items():
    for example in range(1, 10):
        for seed in range(40):
            try:
                yield exit_ticket("g12-sci-s1", "1.2", example, seed=seed)
            except ItemBankError:
                break


def test_lesson_items_have_no_isolation_inside_expressions():
    checked = 0
    for item in _items():
        shown = [(item.stem, item_stem(item))]
        for i, option in enumerate(item.options):
            shown += [(option.text, option_text(option.text)), (option.text, option_label(i, option.text))]
        for source, text in shown:
            for formula in MATH.finditer(source):
                assert plain_math(formula.group(0)) in text, text
                checked += 1
    assert checked
