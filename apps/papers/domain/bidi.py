"""عزل المدى الرقمي في نص عربي، بلا اعتماد على صيغة ملف: يستعمله Word وعرض الحصة. نظير isolateNumberRanges في utils/bidi.ts.

«8 - 4» في «8 - 4 x» طرحٌ داخل تعبير لا مدى: عزله يفصله عن متغيره فينقلب إلى «x 8 - 4». فالمدى الذي يليه أو يسبقه
متغير أو أس أو عملية (ولو من وراء قوس) لا يُعزل، ولا يُمسّ مقطع معزول سلفًا (صيغ `plain_math`).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

NB_HYPHEN = "‑"  # الشرطة غير القاطعة
LRM = "‎"
RLM = "‏"
LRI = "⁦"  # عزل LTR لمقطع رياضي (يضعه عرض الحصة)
PDI = "⁩"
NUMBER_RANGE = re.compile(r"\d+(?:\s*[-–/]\s*\d+)+")

_ISOLATED = re.compile(f"({LRM}[^{LRM}{RLM}]*{RLM}|{LRI}[^{LRI}{PDI}]*{PDI})")
# متغير لاتيني أو يوناني، أو عملية، أو أس ودليل
_NEIGHBOUR = "A-Za-zͰ-Ͽ+=×÷·*^_/<>≤≥≠≈±∓√∞→∈−⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"
_BETWEEN = r"[\s()\[\]{}|-]*"  # ما يُتخطّى بين المدى وجاره
# «DOK» اختصار لا متغير
_MATH_AFTER = re.compile(rf"(?:[.٫]\d+)*{_BETWEEN}(?![A-Z]{{3,}}(?![A-Za-z]))[{_NEIGHBOUR}]")
_DECIMALS_BEFORE = re.compile(r"(?:\d+[.٫])+$")
_MATH_BEFORE = re.compile(rf"[{_NEIGHBOUR}]{_BETWEEN}$")
_ABBREVIATION_BEFORE = re.compile(rf"[A-Z]{{3,}}{_BETWEEN}$")
_IMPLICIT_OR_MINUS = re.compile(r"(?:\d[(\[]|(?:^|[\s(\[{|])-)$")  # «2(3 - 1)» و«-2 - 3»


def _in_expression(text: str, start: int, end: int) -> bool:
    if _MATH_AFTER.match(text, end):
        return True
    before = _DECIMALS_BEFORE.sub("", text[:start])
    if _IMPLICIT_OR_MINUS.search(before):
        return True
    return bool(_MATH_BEFORE.search(before)) and not _ABBREVIATION_BEFORE.search(before)


def range_matches(text: str) -> Iterator[re.Match[str]]:
    """المدى الرقمي المستقل في نص بلا علامات عزل: ما ليس جزءًا من تعبير رياضي."""
    return (m for m in NUMBER_RANGE.finditer(text) if not _in_expression(text, m.start(), m.end()))


def _isolate_plain(text: str) -> str:
    pieces, last = [], 0
    for match in range_matches(text):
        # والشرطة فيه غير قاطعة، فلا ينكسر العنوان الطويل بعد «2026-» ويبدأ السطر التالي بـ«2027»
        pieces += [text[last : match.start()], f"{LRM}{match.group(0).replace('-', NB_HYPHEN)}{RLM}"]
        last = match.end()
    return "".join([*pieces, text[last:]])


def isolate_number_ranges(text: str) -> str:
    """في فقرة عربية يُقلب المدى «2026-2027» إلى «2027-2026» (الأرقام بعد حرف عربي أرقام عربية والشرطة لا تصلها)؛
    علامة LRM قبله تجعله تشغيلًا من اليسار إلى اليمين، وRLM بعده تُنهيه فلا يُسحب إليه رقم يليه
    (التذييل «العاشر، 2026-2027 – 10» كان يُقرأ «العاشر، 10 – 2026-2027»)."""
    # الأجزاء الفردية من `split` مقاطع معزولة سلفًا تبقى كما هي
    return "".join(part if i % 2 else _isolate_plain(part) for i, part in enumerate(_ISOLATED.split(text)))


def strip_isolation(text: str) -> str:
    """عكس `isolate_number_ranges`: النص قبل العزل."""
    return text.replace(LRM, "").replace(RLM, "").replace(LRI, "").replace(PDI, "").replace(NB_HYPHEN, "-")
