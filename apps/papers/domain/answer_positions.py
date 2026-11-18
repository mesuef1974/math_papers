"""مواضع الإجابة الصحيحة في الأسئلة الموضوعية للورقة الواحدة.

خلط بدائل كل سؤال مستقلًا يكدّس الصحيح على رمز واحد في أوراق كثيرة. هنا يُختار موضع الصحيح لكل الأسئلة معًا:
الرموز متساوية التكرار (الفرق بين أي رمزين مرة واحدة على الأكثر)، ولا يتكرر رمز أكثر من مرتين متتاليتين.
منطق نقي بلا قاعدة بيانات، حتمي من مولّد الأعداد.
"""

from __future__ import annotations

import random

MAX_RUN = 2  # أطول تتابع مسموح للرمز نفسه


def longest_run(positions: list[int]) -> int:
    longest = run = 0
    previous = None
    for position in positions:
        run = run + 1 if position == previous else 1
        longest = max(longest, run)
        previous = position
    return longest


def balanced_positions(count: int, width: int, rng: random.Random) -> list[int]:
    """موضع الصحيح (0 إلى width-1) لكل سؤال من count سؤالًا بالترتيب.

    الزيادة عن القسمة تُعطى لرموز عشوائية. بديلان فأكثر يضمنان ترتيبًا بلا تتابع طويل، فإعادة الخلط تنتهي.
    """
    if count <= 0:
        return []
    if width < 2:
        return [0] * count
    base, extra = divmod(count, width)
    counts = [base] * width
    for index in rng.sample(range(width), extra):
        counts[index] += 1
    pool = [index for index, times in enumerate(counts) for _ in range(times)]
    while True:
        rng.shuffle(pool)
        if longest_run(pool) <= MAX_RUN:
            return pool
