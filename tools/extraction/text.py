"""توحيد النص العربي وأدوات الأرقام المشتركة بين مراحل خط الاستخراج (بلا اعتماد خارجي)."""

from __future__ import annotations

import re
from collections.abc import Iterable

DIAC = re.compile("[ً-ْٰـ]")
_FOLD = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"))
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DASHES = re.compile(r"[–—−]")


def norm(text: str) -> str:
    """يزيل التشكيل والتطويل ويوحّد الألف والياء والتاء المربوطة والأرقام الهندية ويصغّر اللاتيني."""
    text = DIAC.sub("", text)
    for a, b in _FOLD:
        text = text.replace(a, b)
    return text.translate(_DIGITS).lower()


def squash(text: str) -> str:
    """norm بلا أي فراغ: يطابق العلامات رغم تقطيع OCR للكلمات."""
    return re.sub(r"\s+", "", norm(text))


def strip_al(word: str) -> str:
    """يسقط «ال» التعريف من أول الكلمة الطويلة فقط (لا يمسّ مثل «الف»)."""
    return word[2:] if word.startswith("ال") and len(word) > 4 else word


def dashes(text: str) -> str:
    return _DASHES.sub("-", text)


def parse_numbers(spec: str, *, ceiling: int = 99) -> list[int]:
    """«1-3، 7» -> [1, 2, 3, 7]؛ المدى المقلوب أو الذي يتجاوز السقف يُهمل، وكل ما ليس رقمًا يُتجاهل."""
    out: list[int] = []
    for part in re.split(r"[,،]", dashes(norm(spec))):
        m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", part)
        if m and int(m[1]) <= int(m[2]) <= ceiling:
            out += range(int(m[1]), int(m[2]) + 1)
        elif part.strip().isdigit() and int(part) <= ceiling:
            out.append(int(part))
    return out


def chain_max(nums: Iterable[int], jump: int) -> int:
    """أكبر رقم في سلسلة متصلة من 1 لا تتجاوز فجوتها `jump`؛ 0 إن لم تبدأ السلسلة."""
    last = 0
    for x in sorted(set(nums)):
        if x - last > jump:
            break
        last = x
    return last
