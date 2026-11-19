"""يكتب أرقام كتاب الطالب في دروس مقرر بصياغتنا (`lessons/lesson_*.json`): `page` لكل مثال و`exercise_groups`.

المصدر مجلد الكتاب خارج المستودع، ويُقرأ منه أرقام فقط: `examples.json` (صفحة بدء كل مثال في ملف الدليل) و`printed_pages.json`
(صفحة الملف → الصفحة المطبوعة) و`exercise_links.json` (اختياري: تدريبات كل مثال). الربط مستنتج فحالة دروسه `review` حتى يعتمده
المالك بتصحيح في `corrections.yaml` (فيصير `ok`)؛ الأمر يكتب المعتمد وحده، و`--include-review` يكتب ما لم يُراجَع أيضًا.
idempotent: التشغيل الثاني على المصدر نفسه لا يغيّر ملفًا، ولا يُمسّ حقل غير `page` و`exercise_groups`، والملف الذي لا يتغير لا يُكتب.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from apps.knowledge.domain.book_numbers import annotate
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.schemas import LessonData

OWNED = ("page", "exercise_groups")  # ما يكتبه الأمر؛ كل حقل سواه يبقى كما هو


def _json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CommandError(f"{what} غير صالح أو غير موجود: {path}") from error


def _printed(path: Path) -> dict[int, int]:
    raw = _json(path, "جدول الصفحات المطبوعة")
    try:
        table = {int(pdf): int(printed) for pdf, printed in raw.items()}
    except (ValueError, TypeError, AttributeError) as error:
        raise CommandError(f"جدول الصفحات المطبوعة غير صالح: {path}") from error
    if any(not (1 <= page <= 999) for page in table.values()):
        raise CommandError(f"رقم صفحة خارج المدى في {path}")
    return table


def _without_owned(lesson: dict[str, Any]) -> dict[str, Any]:
    rest = {k: v for k, v in lesson.items() if k != "exercise_groups"}
    rest["examples"] = [{k: v for k, v in e.items() if k != "page"} for e in lesson.get("examples", [])]
    return rest


class Command(BaseCommand):
    help = "يكتب صفحات أمثلة كتاب الطالب وتدريباتها (أرقام فقط) في ملفات دروس مقرر بصياغتنا."

    def add_arguments(self, parser):
        parser.add_argument("course", help="معرّف المقرر، مثل g12-sci-s1")
        parser.add_argument("--source", required=True, help="مجلد الكتاب المستخرَج (خارج المستودع)")
        parser.add_argument("--examples", help="الافتراضي examples.json تحت المصدر")
        parser.add_argument("--printed-pages", help="الافتراضي printed_pages.json تحت المصدر")
        parser.add_argument("--links", help="الافتراضي exercise_links.json تحت المصدر إن وُجد")
        parser.add_argument("--courses-dir", default=str(COURSES_DIR), help="جذر مجلدات المقررات")
        parser.add_argument(
            "--include-review",
            action="store_true",
            help="يكتب روابط الدروس التي حالتها review أيضًا (الافتراضي: المعتمدة ok وحدها)",
        )

    def handle(
        self,
        *args,
        course,
        source,
        examples=None,
        printed_pages=None,
        links=None,
        courses_dir=None,
        include_review=False,
        **options,
    ):
        source = Path(source)
        files = sorted((Path(courses_dir or COURSES_DIR) / course / "lessons").glob("lesson_*.json"))
        if not files:
            raise CommandError(f"لا ملفات دروس بصياغتنا للمقرر {course}")
        starts = _json(Path(examples) if examples else source / "examples.json", "ملف الأمثلة")["lessons"]
        printed = _printed(Path(printed_pages) if printed_pages else source / "printed_pages.json")
        links_path = Path(links) if links else source / "exercise_links.json"
        linked = _json(links_path, "ملف الروابط")["lessons"] if links or links_path.is_file() else {}
        accepted = ("ok", "review") if include_review else ("ok",)

        changed, pages, groups, held = [], 0, 0, []
        for path in files:
            lesson = _json(path, "ملف الدرس")
            code = lesson["lesson"]
            # صفحة المثال: صفحة بدئه في ملف الدليل عبر الجدول؛ ما لم يُعرف يبقى بلا صفحة
            known = {
                e["n"]: printed[e["start"]]
                for e in starts.get(code, {}).get("value") or []
                if e.get("start") in printed
            }
            entry = linked.get(code)
            if entry and entry["status"] == "review" and not include_review:
                held.append(code)
            rows = entry["value"] if entry and entry["status"] in accepted else None
            updated = annotate(lesson, known, rows)
            if _without_owned(updated) != _without_owned(lesson):  # حارس: لا حقل غير المملوكين يتغير
                raise CommandError(f"تغيّر حقل غير {OWNED} في {path.name}")
            try:
                LessonData(**updated)
            except ValidationError as error:
                raise CommandError(f"{path.name}: {error}") from error
            pages += sum(e.get("page") is not None for e in updated.get("examples", []))
            groups += len(updated.get("exercise_groups", []))
            if json.dumps(updated, ensure_ascii=False) != json.dumps(lesson, ensure_ascii=False):
                text = json.dumps(updated, ensure_ascii=False, indent=1) + "\n"
                path.write_text(text, encoding="utf-8", newline="\n")
                changed.append(code)
        self.stdout.write(
            f"{course}: {len(files)} درسًا، أمثلة بصفحة {pages}، مجموعات تدريبات {groups}، "
            f"تغيّر {len(changed)} ملفًا" + (f"، روابط تنتظر المراجعة: {', '.join(held)}" if held else "")
        )
