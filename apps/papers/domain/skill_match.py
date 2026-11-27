"""هل تقيس الصيغة (أو الهدف) مهارة المثال الذي وُسمت به؟ مقارنة لفظية بنصوص أمثلة الدرس نفسه.

`example=N` يسري على مصدر السؤال وبطاقة الخروج وهدف الدرس، ولا يملك الفهرس العددي ما يكشف رقمًا خاطئًا. هنا نص صيغتنا
مقابل نص كل مثال (من `example_text.json` خارج المستودع): وزن الكلمة أعلى كلما قلّت أمثلة الدرس التي ترد فيها، والدرجة حصة
كلمات الصيغة (مما يرد في أي مثال) التي ترد في المثال. المشتبه ما يتقدم فيه مثال آخر على الموسوم بفارق `MARGIN`. الفحص
مؤشر يراجعه المالك لا حكم، ولا يعيد إلا أرقامًا. نقي بلا Django.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

MARGIN = 0.15
STEM = 4
_DIAC = re.compile("[ً-ْٰـ]")
_FOLD = str.maketrans("أإآٱىة", "اااايه")
_WORD = re.compile("[ء-ي]+")
_MATH = re.compile(r"\$[^$]*\$")
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_SUFFIXES = ("هما", "ها", "ين", "ون", "ات", "ان", "يه", "ه")


def stems(text: str) -> frozenset[str]:
    """جذوع الكلمات العربية: بلا معادلات ولا تشكيل ولا «ال» ولاحقة، مقصوصة إلى `STEM` أحرف."""
    out = set()
    for word in _WORD.findall(_DIAC.sub("", _MATH.sub(" ", text)).translate(_FOLD)):
        for prefix in _PREFIXES:
            if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                word = word[len(prefix) :]
                break
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                break
        if len(word) >= 3:
            out.add(word[:STEM])
    return frozenset(out)


@dataclass(frozen=True)
class Match:
    tagged: int
    best: int | None  # None: لا كلمة مشتركة مع أي مثال
    tagged_score: float
    best_score: float

    @property
    def status(self) -> str:
        if self.best is None:
            return "unknown"
        return "suspect" if self.best_score - self.tagged_score >= MARGIN else "ok"


def match(text: str, tagged: int, examples: Mapping[int, str]) -> Match:
    bags = {n: stems(t) for n, t in examples.items()}
    count = len(bags)
    weights = {
        word: math.log((count + 1) / df)
        for word in stems(text)
        if (df := sum(word in bag for bag in bags.values()))
    }
    total = sum(weights.values())
    if not total or tagged not in bags:
        return Match(tagged, None, 0.0, 0.0)
    scores = {n: sum(w for word, w in weights.items() if word in bag) / total for n, bag in bags.items()}
    best = max(scores, key=lambda n: (scores[n], n == tagged, -n))
    return Match(tagged, best, round(scores[tagged], 2), round(scores[best], 2))
