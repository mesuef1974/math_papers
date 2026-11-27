"""الربط اليدوي لتمارين الدرس بأمثلته: لكتاب لا يربطها (بلا شارات «انظر المثال»)، يختار المالك تمارين كل مثال.

المرحلة تكتب صفحة محلية `exercise_manual.html` في مجلد الكتاب (خارج المستودع): لكل درس صور صفحات تمارينه من `dirs.render`
وصف لكل مثال في `exercise_links.json` تُكتب فيه تمارينه مديات («1-8، 10»). زر الصفحة ينزّل `exercise_manual.json`:
`{"book": ..., "lessons": {"1.1": [{"example": 1, "exercises": [1, 2]}]}}`، يُحفظ في مجلد الكتاب فتقرؤه `exercise_links`
غلاف `practice` بمصدر teacher وحالة ok (`method: manual`) يغلب غلاف الشارات. الدرس الغائب من الملف يبقى كما كان.
"""

from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from string import Template
from typing import Any

from .config import Book
from .corrections import CorrectionError
from .examples import exercises_start
from .exercise_badges import after_examples
from .fields import field
from .fusion import settings as fusion_settings
from .layout import load_pages

PICKS = "exercise_manual.json"
TEMPLATE = Path(__file__).with_name("exercise_manual.html")


def picks_path(book: Book) -> Path:
    return book.out / PICKS


def _number(value: Any, cap: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= cap


def load_picks(book: Book) -> dict[str, list[dict[str, Any]]]:
    """اختيارات المالك بعد فحص شكلها: رمز الدرس → صفوف `{example, exercises}` مرتبة؛ لا ملف = لا اختيار."""
    path = picks_path(book)
    if not path.exists():
        return {}
    cap = fusion_settings(book)["max_exercise"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if raw["book"] != book.id:
            raise CorrectionError(f"{PICKS}: لكتاب آخر ({raw['book']!r} لا {book.id!r})")
        out: dict[str, list[dict[str, Any]]] = {}
        for lesson, rows in raw["lessons"].items():
            merged: dict[int, set[int]] = {}
            for row in rows:
                example, numbers = row["example"], row["exercises"]
                if not _number(example, cap) or not all(_number(x, cap) for x in numbers):
                    raise CorrectionError(f"{PICKS}: رقم خارج 1-{cap} في الدرس {lesson}")
                merged.setdefault(example, set()).update(numbers)
            out[lesson] = [{"example": e, "exercises": sorted(xs)} for e, xs in sorted(merged.items()) if xs]
    except CorrectionError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise CorrectionError(f"{PICKS}: شكل غير صالح ({type(e).__name__}: {e})") from e
    return {lesson: rows for lesson, rows in out.items() if rows}


def apply(book: Book, result: dict[str, Any]) -> None:
    """يضع اختيارات المالك غلاف `practice` معتمدًا في دروس مخرج `exercise_links`؛ درس أو مثال ليس فيه خطأ صريح."""
    for lesson, rows in load_picks(book).items():
        entry = result["lessons"].get(lesson)
        if entry is None:
            raise CorrectionError(f"{PICKS}: لا درس {lesson} في الروابط")
        unknown = {r["example"] for r in rows} - {r["example"] for r in entry["value"]}
        if unknown:
            raise CorrectionError(f"{PICKS}: أمثلة ليست في الدرس {lesson}: {sorted(unknown)}")
        entry["practice"] = field(rows, "teacher", "ok", method="manual")


def ranges_text(numbers: list[int]) -> str:
    """[1, 2, 3, 5] → «1-3، 5» (صيغة خانة الإدخال)."""
    spans: list[list[int]] = []
    for n in sorted(set(numbers)):
        if spans and spans[-1][1] == n - 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return "، ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def _src(book: Book, path: Path) -> str:
    try:
        return Path(os.path.relpath(path, book.out)).as_posix()
    except ValueError:  # قرص آخر على Windows
        return path.resolve().as_uri()


def exercise_images(
    book: Book, record: dict[str, Any], known: list[dict[str, Any]], texts: Any
) -> list[Path]:
    """صور صفحات تمارين الدرس بمنطق مرحلة الشارات؛ بلا بداية معروفة صفحات الدرس كلها."""
    if not record["pages_pdf"]:
        return []
    span = (record["pages_pdf"][0], record["pages_pdf"][1])
    start = exercises_start(book, span, texts) or after_examples(known, span) or span[0]
    pages = (book.dir("render") / f"{n:04d}.png" for n in range(start, span[1] + 1))
    return [p for p in pages if p.exists()]


def page_html(
    book: Book, layout: dict[str, Any], examples: dict[str, Any], links: dict[str, Any]
) -> tuple[str, dict[str, int]]:
    """(نص الصفحة، أعدادها). صفوف الأمثلة من `links` (بعد تصحيحاته) وتمرين «حاول» شاهد بجانب كل مثال."""
    picked = {k: {r["example"]: r["exercises"] for r in v} for k, v in load_picks(book).items()}
    texts = load_pages(book)
    sections, counts = [], {"lessons": 0, "examples": 0, "pages": 0, "picked_lessons": len(picked)}
    for record in layout["lessons"]:
        lesson = record["id"]
        rows = (links["lessons"].get(lesson) or {}).get("value") or []
        if not rows:
            continue
        known = examples["lessons"].get(lesson, {}).get("value") or []
        images = exercise_images(book, record, known, texts)
        counts["lessons"] += 1
        counts["examples"] += len(rows)
        counts["pages"] += len(images)
        figures = "".join(
            f'<a href="{escape(_src(book, p))}" target="_blank"><img loading="lazy" '
            f'src="{escape(_src(book, p))}" alt="صفحة {int(p.stem)}"></a>'
            for p in images
        )
        body = "".join(
            f"<tr><td>{r['example']}</td><td>{ranges_text(r['exercises']) or '—'}</td>"
            f'<td><input data-example="{r["example"]}" inputmode="numeric" '
            f'aria-label="تمارين المثال {r["example"]} في الدرس {escape(lesson)}" '
            f'value="{ranges_text(picked.get(lesson, {}).get(r["example"], []))}"></td></tr>'
            for r in rows
        )
        sections.append(
            f'<section data-lesson="{escape(lesson)}"><h2>الدرس {escape(lesson)}</h2>'
            f'<div class="pages">{figures}</div><table><thead><tr><th>المثال</th><th>تمرين «حاول»</th>'
            f"<th>تمارين المثال</th></tr></thead><tbody>{body}</tbody></table>"
            f'<p class="note" role="status"></p></section>'
        )
    text = Template(TEMPLATE.read_text(encoding="utf-8")).safe_substitute(
        title=escape(book["title"]),
        book=json.dumps(book.id, ensure_ascii=False).replace("<", "\\u003c"),
        cap=fusion_settings(book)["max_exercise"],
        file=PICKS,
        sections="\n".join(sections),
    )
    return text, counts
