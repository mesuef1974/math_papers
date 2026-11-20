"""ملء نصوص غلاف قالب المدرسة: النص في القالب مقسوم على أشواط، ومكرر في بديل VML (mc:Fallback)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

P, T = qn("w:p"), qn("w:t")


def leaf_paragraphs(elements: Iterable) -> list:
    """الفقرات التي لا تحوي فقرات (نصوص مربعات النص تُحسب وحدها)، في الأصل والبديل معًا."""
    found = []
    for element in elements:
        candidates = [element] if element.tag == P else []
        candidates += list(element.iter(P))
        found += [p for p in candidates if p.find(f".//{P}") is None]
    return list(dict.fromkeys(found))


def fill(elements: Iterable, mapping: Mapping[str, str]) -> int:
    """يستبدل كل مفتاح بقيمته في نص الفقرة المجمّع، فيبقى تنسيق أول شوط، وفاصل السطر في القيمة
    فاصل سطر في الشوط. يعيد عدد الفقرات المعدّلة."""
    changed = 0
    for paragraph in leaf_paragraphs(elements):
        texts = list(paragraph.iter(T))
        if not texts:
            continue
        whole = "".join(t.text or "" for t in texts)
        new = whole
        for key, value in mapping.items():
            new = new.replace(key, value)
        if new == whole:
            continue
        first, *rest = new.split("\n")
        texts[0].text = first
        texts[0].set(qn("xml:space"), "preserve")
        for t in texts[1:]:
            t.text = ""
        anchor = texts[0]
        for line in rest:  # سطر جديد في القيمة فاصل سطر في الشوط نفسه فيبقى تنسيقه
            br = OxmlElement("w:br")
            t = OxmlElement("w:t")
            t.text = line
            t.set(qn("xml:space"), "preserve")
            anchor.addnext(br)
            br.addnext(t)
            anchor = t
        changed += 1
    return changed
