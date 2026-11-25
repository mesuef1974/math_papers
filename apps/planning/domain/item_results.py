"""نتيجة الطالب لكل بند: تنظيف الإدخال وتصحيحه من بنك البنود. نقي بلا Django ولا قاعدة.

هوية الطالب رقم قيد واسم مختصر (الأول والعائلة) بقرار المالك 2026-11-25: الاسم الرباعي يُرفض بحد الكلمات. والصحة ونوع الخطأ
يُشتقان من البند نفسه (`item_bank.exit_ticket` بالمقرر والدرس والمثال والبذرة) ومن رقم الخيار، ولا يُقبلان من العميل.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from apps.papers.domain.item_bank import OPTION_COUNT, Item, ItemBankError, exit_ticket

from .calendar_engine import PlanningError

ENROLLMENT_LENGTH = 20
NAME_LENGTH = 30
NAME_WORDS = 2  # «عبد الله» و«آل ثاني» كلمتان؛ ما زاد اسم مركّب من أكثر من اسم
MAX_EXAMPLE = 999
MAX_SEED = 2_147_483_647
MAX_ENTRIES = 600
ENROLLMENT = re.compile(rf"[0-9A-Za-z-]{{1,{ENROLLMENT_LENGTH}}}")


class ResultsError(PlanningError):
    """إدخال نتائج لا يُحفظ: رسالته عربية وبلا اسم طالب (قد تصل السجلات)."""


@dataclass(frozen=True)
class Entry:
    """اختيار طالب في بند كما أدخله المعلم."""

    enrollment_no: str
    first_name: str
    last_name: str
    example: int
    seed: int
    choice: int


@dataclass(frozen=True)
class Marked:
    """الإدخال بعد تصحيحه من البنك: `error_kind` مفتاح من ERROR_KINDS للخاطئ وفارغ للصحيح."""

    entry: Entry
    correct: bool
    error_kind: str


def _name(value: str, label: str, enrollment_no: str) -> str:
    name = " ".join(value.split())
    if not name or len(name) > NAME_LENGTH or len(name.split(" ")) > NAME_WORDS:
        raise ResultsError(
            f"{label} للطالب {enrollment_no} مطلوب، بحد أقصى {NAME_LENGTH} حرفًا وكلمتين (لا اسم رباعي)"
        )
    return name


def _clean(entry: Entry) -> Entry:
    enrollment_no = entry.enrollment_no.strip()
    if not ENROLLMENT.fullmatch(enrollment_no):
        raise ResultsError(f"رقم القيد أرقام وحروف لاتينية بحد أقصى {ENROLLMENT_LENGTH} خانة")
    if not 1 <= entry.example <= MAX_EXAMPLE:
        raise ResultsError(f"رقم المثال للطالب {enrollment_no} خارج المدى")
    if not 0 <= entry.seed <= MAX_SEED:
        raise ResultsError(f"بذرة البند للطالب {enrollment_no} خارج المدى")
    if not 0 <= entry.choice < OPTION_COUNT:
        raise ResultsError(f"الخيار المختار للطالب {enrollment_no} من 0 إلى {OPTION_COUNT - 1}")
    return Entry(
        enrollment_no,
        _name(entry.first_name, "الاسم الأول", enrollment_no),
        _name(entry.last_name, "اسم العائلة", enrollment_no),
        entry.example,
        entry.seed,
        entry.choice,
    )


def clean_entries(raw: Iterable[Entry]) -> list[Entry]:
    """الإدخالات منظَّفة وبلا تكرار؛ يُرفض طالب باسمين في الدفعة، وبند واحد له خياران."""
    entries = [_clean(entry) for entry in raw]
    if not entries:
        raise ResultsError("لا نتائج في الإدخال")
    if len(entries) > MAX_ENTRIES:
        raise ResultsError(f"الدفعة الواحدة بحد أقصى {MAX_ENTRIES} نتيجة")
    names: dict[str, tuple[str, str]] = {}
    unique: dict[tuple[str, int, int], Entry] = {}
    for entry in entries:
        name = names.setdefault(entry.enrollment_no, (entry.first_name, entry.last_name))
        if name != (entry.first_name, entry.last_name):
            raise ResultsError(f"رقم القيد {entry.enrollment_no} ورد باسمين مختلفين في الدفعة")
        key = (entry.enrollment_no, entry.example, entry.seed)
        if unique.setdefault(key, entry).choice != entry.choice:
            raise ResultsError(f"الطالب {entry.enrollment_no} له خياران في بند المثال {entry.example} نفسه")
    return list(unique.values())


def mark(course: str, lesson: str, entries: Iterable[Entry]) -> list[Marked]:
    """يصحّح كل إدخال من بنده في البنك؛ `ResultsError` لمثال بلا بند موضوعي في الدرس."""
    items: dict[tuple[int, int], Item] = {}
    marked = []
    for entry in entries:
        key = (entry.example, entry.seed)
        if key not in items:
            try:
                items[key] = exit_ticket(course, lesson, entry.example, seed=entry.seed)
            except ItemBankError as error:
                raise ResultsError(f"لا بند في بنك الدرس {lesson} للمثال {entry.example}") from error
        option = items[key].options[entry.choice]
        marked.append(Marked(entry, option.correct, option.kind or ""))
    return marked
