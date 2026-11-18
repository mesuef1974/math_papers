"""مستخرج الخطة الفصلية للوزارة من PDF إلى `term_plan.json` لمقرر: أعداد وتواريخ وفئات فقط، بلا نص من الوثيقة.

    python -m tools.extraction.term_plan <ملف PDF> --course <المقرر> [--out <مسار>] [--check <term_plan.json مرجعي>]

طبقتان: قارئ PDF (`read_tables`، pdfplumber باستيراد كسول) يعيد جداول الصفحات خلايا نصية بترتيب منطقي، ومحلّل نقي (`parse`)
يحوّلها إلى قاموس بصيغة `TermPlanData` (`apps/knowledge/domain/sources.py`). الأعمدة تُحدَّد من كلمات الترويسة لا من موضعها، والكلمات
تُطابَق بمفتاح يُسقط الباء والهمزة لأن خط الوثيقة يسقطهما. الجدول بلا ترويسة (تتمة صفحة، أو الإثرائي حين يسقط الخط كلمته) يُصنَّف
ببصمات خلاياه (`fingerprint`) لا بعرضه ولا بما قبله. ما لا يُصنَّف خطأ صريح بالصفحة والصف، ولا يُخمَّن، والخطأ لا يحمل نص الخلية.
`lost_days` و`class_during_exams` و`notes` يدوية: تُحفظ من الملف الموجود ولا تُستخرج.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .text import norm, squash

COURSES = Path(__file__).resolve().parents[2] / "apps" / "knowledge" / "data" / "courses"
MANUAL_FIELDS = ("class_during_exams", "lost_days", "notes")
COMPARED_FIELDS = ("sessions_per_week", "enrichment_lessons", "enrichment_examples")
FIELD_ORDER = (
    "source",
    "sessions_per_week",
    "class_during_exams",
    "lost_days",
    "enrichment_lessons",
    "enrichment_examples",
    "notes",
    "weeks",
)
SUNDAY = 6

Row = list[str | None]

# تتابع الأرقام بفواصله (2.10 و30/8) وحدة واحدة يسارًا إلى يمين في خوارزمية الاتجاه
_RUN = re.compile(r"\d+(?:[.,:/\-]\d+)*")
_LESSON = re.compile(r"(?<!\d)\d{1,2}\.\d{1,2}(?!\d)")
_YEAR = re.compile(r"(?<!\d)\d{4}(?!\d)")
_COUNT = re.compile(r"\d{1,2}")
_THEOREM = re.compile(r"\d+\s*-\s*\d+")
_EXAMPLE_WORD = re.compile("مثال|مثله")
_EXAMPLES = re.compile(r"(?:مثال|مثله)\s*:?\s*(\d+(?:\s*[،,و]?\s*\d+)*)")
_DROPPED = re.compile("[بءئؤأإآٱٓ-ٕ]")


class TermPlanError(ValueError):
    """الوثيقة لا تطابق البنية المعروفة: يُذكر الموضع (صفحة وصف) لا النص."""


@dataclass(frozen=True)
class PageTable:
    page: int
    rows: list[Row]


def logical(text: str) -> str:
    """نص خلية بترتيب بصري إلى ترتيب منطقي: يعكس كل سطر ثم يعيد عكس تتابعات الأرقام (مخزنة يسارًا إلى يمين)."""
    lines = unicodedata.normalize("NFKC", text).split("\n")
    return "\n".join(_RUN.sub(lambda m: m[0][::-1], line[::-1]) for line in lines)


def read_tables(pdf: Path) -> Iterator[PageTable]:
    """جداول الملف صفحةً صفحة: المدموجة رأسيًّا `None` في صفوفها التالية، والفارغة ""."""
    import pdfplumber  # ليس في بيئة المشروع: المستخرج يُشغَّل ببايثون فيه pdfplumber

    with pdfplumber.open(pdf) as document:
        for number, page in enumerate(document.pages, start=1):
            for table in page.find_tables():
                rows = [[None if cell is None else logical(cell) for cell in row] for row in table.extract()]
                yield PageTable(number, rows)


def _key(text: str) -> str:
    """مفتاح مطابقة الكلمات: بلا فراغ ولا باء ولا همزة، فيطابق النص الذي أسقط الخط حروفه."""
    return squash(_DROPPED.sub("", text))


def _has(key: str, *words: str) -> bool:
    return all(_key(word) in key for word in words)


def _numbers(text: str | None) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", norm(text or ""))]


def _lesson_order(code: str) -> tuple[int, ...]:
    return tuple(int(part) for part in code.split("."))


_HEADER = {"periods": "الحصص", "lesson": "الدروس", "time": "الزمن", "unit": "الوحدة"}
_ENRICHMENT = "ثرا"  # جذع «الإثرائية» بين همزتيها


def _columns(row: Row) -> dict[str, int] | None:
    """أعمدة الجدول الرئيسي من كلمات ترويسته، أو None إن لم يكن الصف ترويسته (عمود الوحدة اختياري)."""
    found: dict[str, int] = {}
    for index, cell in enumerate(row):
        key = _key(cell or "")
        for name, word in _HEADER.items():
            if _has(key, word):
                found.setdefault(name, index)
    return found if {"periods", "lesson", "time"} <= found.keys() else None


def fingerprint(cell: str | None) -> str:
    """بصمة الخلية حرفًا: N مدموجة، - فارغة، Y فيها عدد بأربع خانات، L فيها رمز درس، # عدد بخانة أو خانتين وحده، t غير ذلك."""
    if cell is None:
        return "N"
    text = norm(cell).strip()
    if not text:
        return "-"
    if _YEAR.search(text):
        return "Y"
    if _LESSON.search(text):
        return "L"
    return "#" if _COUNT.fullmatch(text) else "t"


def _marks(rows: list[Row]) -> list[str]:
    """بصمات الجدول صفًّا صفًّا بعرض واحد (الصف القصير يُكمَل N)."""
    width = max((len(row) for row in rows), default=0)
    return ["".join(map(fingerprint, row)).ljust(width, "N") for row in rows]


def _is_enrichment(marks: list[str]) -> bool:
    """جدول الإثرائي بمحتواه: لا عدد حصص ولا سنة في أي خلية، والعمود الأول رمز درس في نصف الصفوف فأكثر."""
    if any(mark in "#Y" for row in marks for mark in row):
        return False
    return 2 * sum(row[0] == "L" for row in marks) >= len(marks)


def _continuation(marks: list[str], page: int) -> dict[str, int] | None:
    """أعمدة تتمة الجدول الرئيسي بلا ترويسة من بصمات خلاياها، أو None إن لم يكن الجدول تتمة (توقيعات وملاحظات)."""

    def best(rows: list[str], wanted: str, skip: tuple[int, ...]) -> tuple[int, int]:
        counts = [
            (sum(row[index] in wanted for row in rows), sum(row[index] == wanted[0] for row in rows), -index)
            for index in range(len(marks[0]))
            if index not in skip
        ]
        count, _, index = max(counts, default=(0, 0, 0))
        return -index, count

    periods, count = best(marks, "#", ())
    if count == 0 or count < 0.4 * len(marks):
        return None
    counted = [
        row for row in marks if row[periods] == "#"
    ]  # صفوف الإجازة قد تحمل سنة خارج عمود الزمن: لا تُحسب
    lesson, lessons = best(counted, "Lt", (periods,))
    time, times = best(counted, "Y", (periods, lesson))
    if not lessons or not times:
        raise TermPlanError(f"جدول بلا ترويسة فيه عمود حصص ولم تتعيّن أعمدته (الصفحة {page})")
    return {"periods": periods, "lesson": lesson, "time": time}


def week_start(numbers: list[int], after: date | None = None) -> date | None:
    """بداية الأسبوع من أرقام خلية الزمن وحدها مهما اضطرب ترتيبها.

    السنة العدد ذو الأربع خانات (وبدونه سنة الأسبوع السابق أو التي تليها)، والبداية زوج (شهر، يوم) يكون أحدًا ويومُ الخميس
    بعده بين الأرقام الباقية. None إن لم يتعيّن تاريخ واحد.
    """
    years = sorted({n for n in numbers if 1000 <= n <= 9999})
    rest = [n for n in numbers if n < 1000]
    if not years and after:
        years = [after.year, after.year + 1]
    found: set[date] = set()
    for year in years:
        for i, month in enumerate(rest):
            for j, day in enumerate(rest):
                if i == j:
                    continue
                try:
                    start = date(year, month, day)
                except ValueError:
                    continue
                others = [n for k, n in enumerate(rest) if k not in (i, j)]
                if start.weekday() == SUNDAY and (start + timedelta(days=4)).day in others:
                    found.add(start)
    if after:
        found = {start for start in found if start >= after}
    return found.pop() if len(found) == 1 else None


@dataclass
class _Builder:
    weeks: dict[date, list[dict[str, Any]]] = field(default_factory=dict)
    lessons: set[str] = field(default_factory=set)
    examples: dict[str, set[int]] = field(default_factory=dict)
    start: date | None = None  # بداية الأسبوع الجاري
    latest: date | None = None  # آخر بداية تعيّنت: الأسابيع لا تعود إلى الوراء
    unit_cell: int | None = None
    last_unit: int | None = None  # وحدة آخر درس مرّ
    quizzes: int = 0
    enriched: str | None = None  # رمز الدرس الإثرائي الجاري (لصفوف أمثلته المدموجة)

    def main_row(self, row: Row, columns: dict[str, int], where: str) -> None:
        cells = {name: row[index] if index < len(row) else None for name, index in columns.items()}
        time = cells["time"]
        if time is not None and time.strip():
            self.start = week_start(_numbers(time), self.latest)
            self.latest = self.start or self.latest
        unit = cells.get("unit")
        if unit is not None and unit.strip():
            numbers = _numbers(unit)
            self.unit_cell = numbers[0] if len(numbers) == 1 else None
        periods = _numbers(cells["periods"])
        if not periods or periods == [0]:
            return  # إجازة أو اختبار مغلق: بلا حصص
        if len(periods) > 1:
            raise TermPlanError(f"خلية الحصص فيها أكثر من عدد ({where})")
        if self.start is None:
            raise TermPlanError(f"بند بحصص لم يتعيّن تاريخ أسبوعه من خلية الزمن ({where})")
        item = self._item(cells["lesson"] or "", where)
        self.weeks.setdefault(self.start, []).append({**item, "periods": periods[0]})

    def _item(self, text: str, where: str) -> dict[str, Any]:
        code = _LESSON.search(norm(text))
        if code:
            self.last_unit = int(code[0].split(".")[0])
            return {"kind": "lesson", "lesson": code[0]}
        key = _key(text)
        if _has(key, "اختبار", "الوحدة"):
            self.quizzes += 1
            numbers = _numbers(text)
            unit = numbers[0] if len(numbers) == 1 else self.unit_cell or self.last_unit or self.quizzes
            return {"kind": "quiz", "unit": unit}
        if _has(key, "منتصف", "مراجعة"):
            return {"kind": "review", "scope": "midterm"}
        if _has(key, "منتصف", "اختبار"):
            return {"kind": "exam", "scope": "midterm"}
        if _has(key, "نهاية", "مراجعة", "اختبار"):
            return {"kind": "review", "scope": "final"}
        if _has(key, "تهيئة") or "تهيي" in key or _has(key, "بداية الفصل"):
            return {"kind": "orientation"}
        if _has(key, "مشروع"):
            return {"kind": "project"}
        if _has(key, "دعم"):
            return {"kind": "support"}
        raise TermPlanError(f"بند لا يُصنَّف ({where})")

    def enrichment_row(self, row: Row, where: str) -> None:
        text = norm(" ".join(cell for cell in row if cell))
        codes = _LESSON.findall(text)
        rest = _THEOREM.sub(" ", _LESSON.sub(" ", text))  # رمز الدرس وأرقام النظريات (2-1) ليست أمثلة
        if not _EXAMPLE_WORD.search(rest):
            self.lessons.update(codes)
            self.enriched = codes[-1] if codes else self.enriched
            return
        numbers = [int(n) for found in _EXAMPLES.findall(rest) for n in re.findall(r"\d+", found)]
        if len(codes) > 1 or not numbers:
            raise TermPlanError(f"صف إثرائي لا تتعيّن أمثلته ({where})")
        code = codes[0] if codes else self.enriched
        if code is None:
            raise TermPlanError(f"أمثلة إثرائية بلا رمز درس ({where})")
        self.enriched = code
        self.examples.setdefault(code, set()).update(numbers)

    def result(self) -> dict[str, Any]:
        if not self.weeks:
            raise TermPlanError("لا أسبوع بحصص في الوثيقة: ترويسة الجدول الرئيسي لم توجد")
        starts = sorted(self.weeks)
        totals = Counter(sum(item["periods"] for item in self.weeks[start]) for start in starts)
        best = max(totals.values())
        return {
            "sessions_per_week": max(total for total, count in totals.items() if count == best),
            "enrichment_lessons": sorted(self.lessons, key=_lesson_order),
            "enrichment_examples": {
                code: sorted(self.examples[code]) for code in sorted(self.examples, key=_lesson_order)
            },
            "weeks": [
                {
                    "n": (start - starts[0]).days // 7 + 1,
                    "start": start.isoformat(),
                    "end": (start + timedelta(days=4)).isoformat(),
                    "items": self.weeks[start],
                }
                for start in starts
            ],
        }


def parse(tables: Iterable[PageTable]) -> dict[str, Any]:
    """المحلّل النقي: جداول بخلايا منطقية النص إلى الحقول المستخرجة (الأسابيع وحصصها الأسبوعية والإثرائي)."""
    builder = _Builder()
    for table in tables:
        mode: str | None = None
        columns: dict[str, int] = {}
        marks = _marks(table.rows)
        for number, row in enumerate(table.rows, start=1):
            header = _columns(row)
            if header:
                mode, columns = "main", header
            elif mode is None and number <= 2 and any(_ENRICHMENT in _key(cell or "") for cell in row):
                mode = "enrichment"
            elif mode == "main":
                builder.main_row(row, columns, f"الصفحة {table.page}، الصف {number}")
            elif mode == "enrichment":
                builder.enrichment_row(row, f"الصفحة {table.page}، الصف {number}")
        if mode is not None or len(marks) < 2 or len(marks[0]) < 3:
            continue
        # بلا ترويسة: يُصنَّف بمحتواه، لا بعرضه ولا بما قبله
        if _is_enrichment(marks):
            for number, (row, mark) in enumerate(zip(table.rows, marks, strict=True), start=1):
                if "L" in mark:  # صف الترويسة بلا رمز درس: يُتخطى
                    builder.enrichment_row(row, f"الصفحة {table.page}، الصف {number}")
            continue
        columns = _continuation(marks, table.page)
        if columns:
            builder.unit_cell = None  # لا عمود وحدة في التتمة: وحدة الاختبار من آخر درس مرّ
            for number, row in enumerate(table.rows, start=1):
                builder.main_row(row, columns, f"الصفحة {table.page}، الصف {number}")
    return builder.result()


def assemble(extracted: dict[str, Any], source: str | None, manual: dict[str, Any]) -> dict[str, Any]:
    """الملف كما يُكتب: المستخرَج ومعرّف المصدر والحقول اليدوية كما هي، بترتيب مفاتيح ثابت."""
    merged = {**extracted, **{name: manual[name] for name in MANUAL_FIELDS if name in manual}}
    if source:
        merged["source"] = source
    return {name: merged[name] for name in FIELD_ORDER if name in merged}


def validate(result: dict[str, Any], semester: int) -> dict[str, Any]:
    """تحقق العقد ثم محرك التخطيط (أسبوع من الأحد إلى الخميس ومجموع حصصه)؛ يعيد الصيغة الموحَّدة للمقارنة."""
    from apps.knowledge.domain.sources import TermPlanData
    from apps.planning.domain.calendar_engine import PlanningError

    try:
        data = TermPlanData(**result)
        data.to_domain(semester)
    except (ValueError, PlanningError) as error:
        raise TermPlanError(f"الخطة لا تجتاز التحقق: {error}") from error
    return data.model_dump(mode="json")


def differences(result: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    """مفاتيح ما اختلف بين خطتين موحَّدتين: أسابيع بأرقامها ثم الحقول المستخرجة؛ اليدوية والمصدر لا تُقارن."""
    ours = {week["n"]: week for week in result["weeks"]}
    theirs = {week["n"]: week for week in reference["weeks"]}
    keys = [f"الأسبوع {n}" for n in sorted(ours.keys() | theirs.keys()) if ours.get(n) != theirs.get(n)]
    for name in COMPARED_FIELDS:
        a, b = result[name], reference[name]
        if name == "enrichment_lessons":
            a, b = sorted(a), sorted(b)
        if a != b:
            keys.append(name)
    return keys


def _manual(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    existing = json.loads(path.read_text(encoding="utf-8"))
    return {name: existing[name] for name in MANUAL_FIELDS if name in existing}


def _course(slug: str) -> tuple[int, str | None]:
    """فصل المقرر ومعرّف مصدر خطته الفصلية من `sources.json` (None إن لم يُسجَّل)."""
    folder = COURSES / slug
    if not (folder / "course.json").exists():
        raise TermPlanError(f"مقرر غير معروف: {slug}")
    semester = int(json.loads((folder / "course.json").read_text(encoding="utf-8"))["course"]["semester"])
    sources = folder / "sources.json"
    listed = json.loads(sources.read_text(encoding="utf-8")) if sources.exists() else []
    slugs = [entry["slug"] for entry in listed if entry.get("kind") == "term_plan"]
    if len(slugs) > 1:
        raise TermPlanError(f"أكثر من مصدر خطة فصلية للمقرر {slug}: {slugs}")
    return semester, slugs[0] if slugs else None


def main(argv: list[str] | None = None, read: Callable[[Path], Iterable[PageTable]] = read_tables) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.extraction.term_plan", description=__doc__)
    parser.add_argument("pdf", type=Path, help="ملف الخطة الفصلية (خارج المستودع)")
    parser.add_argument("--course", required=True, help="معرّف المقرر، مثل g10-s1")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--out", type=Path, help="يكتب term_plan.json ويحفظ حقوله اليدوية الموجودة")
    target.add_argument("--check", type=Path, help="يقارن بملف مرجعي ويطبع سطرًا واحدًا")
    args = parser.parse_args(argv)
    try:
        semester, source = _course(args.course)
        result = assemble(parse(read(args.pdf)), source, _manual(args.check or args.out))
        unified = validate(result, semester)
        if args.check:
            reference = validate(json.loads(args.check.read_text(encoding="utf-8")), semester)
            keys = differences(unified, reference)
            print(f"فروق: {len(keys)} ({'، '.join(keys)})" if keys else "مطابق")
            return 1 if keys else 0
    except (TermPlanError, OSError, json.JSONDecodeError) as error:
        print(f"تعذّر الاستخراج: {error}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(json.dumps({"weeks": len(result["weeks"]), "out": str(args.out)}, ensure_ascii=False))
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
