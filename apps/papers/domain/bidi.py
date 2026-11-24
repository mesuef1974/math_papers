"""عزل المدى الرقمي في نص عربي، بلا اعتماد على صيغة ملف: يستعمله Word وعرض الحصة. نظير isolateNumberRanges في utils/bidi.ts."""

from __future__ import annotations

import re

NB_HYPHEN = "\u2011"  # الشرطة غير القاطعة
LRM = "\u200e"
RLM = "\u200f"
LRI = "\u2066"  # عزل LTR لمقطع رياضي (يضعه عرض الحصة)
PDI = "\u2069"
NUMBER_RANGE = re.compile(r"\d+(?:\s*[-–/]\s*\d+)+")


def isolate_number_ranges(text: str) -> str:
    """في فقرة عربية يُقلب المدى «2026-2027» إلى «2027-2026» (الأرقام بعد حرف عربي أرقام عربية والشرطة لا تصلها)؛
    علامة LRM قبله تجعله تشغيلًا من اليسار إلى اليمين، وRLM بعده تُنهيه فلا يُسحب إليه رقم يليه
    (التذييل «العاشر، 2026-2027 – 10» كان يُقرأ «العاشر، 10 – 2026-2027»)."""
    # والشرطة فيه غير قاطعة، فلا ينكسر العنوان الطويل بعد «2026-» ويبدأ السطر التالي بـ«2027»
    return NUMBER_RANGE.sub(lambda match: f"{LRM}{match.group(0).replace('-', NB_HYPHEN)}{RLM}", text)


def strip_isolation(text: str) -> str:
    """عكس `isolate_number_ranges`: النص قبل العزل."""
    return text.replace(LRM, "").replace(RLM, "").replace(LRI, "").replace(PDI, "").replace(NB_HYPHEN, "-")
