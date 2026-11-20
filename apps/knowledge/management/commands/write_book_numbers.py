"""يكتب أرقام الكتاب في دروس مقرر بصياغتنا (`lessons/lesson_*.json`): `page` لكل مثال و`exercise_groups` وأرقام الدليل.

المصدر مجلد الكتاب خارج المستودع، ويُقرأ منه أرقام فقط: `examples.json` (صفحة بدء كل مثال في ملف الدليل) و`printed_pages.json`
(صفحة الملف → الصفحة المطبوعة) و`exercise_links.json` (اختياري: تدريبات كل مثال). الربط مستنتج فحالة دروسه `review` حتى يعتمده
المالك بتصحيح في `corrections.yaml` (فيصير `ok`)؛ الأمر يكتب المعتمد وحده، و`--include-review` يكتب ما لم يُراجَع أيضًا.
غلاف `practice` بجانب صفوف الدرس (تمارين قسم «تمارين» لكل مثال، من الشارات) يُعتمد وحده بالقاعدة نفسها، ويُكتب في
`exercise_groups` صفوفًا إضافية بـ `kind: "practice"` وعمق مثالها؛ الصفوف بلا `kind` نوعها `try`.
أرقام الدليل (`book_numbers.GUIDE_FIELDS`: `task_basic` و`task_advanced` و`quiz_depths` و`exercises_total` و`vocab_new` و`vocab_review`)
من سجلات مرحلة `lesson` (`lessons/lesson_X_Y.json` تحت المصدر، اختياري): الحقل الذي حالته `ok` وحده، والمفقود أو غير المقروء يبقى
كما هو في الملف ولا يُخمَّن، وعدد التمارين الذي يخالف آخر رقم في قوالب الدرس لا يُكتب ويُذكر في الملخص. `--guide-only` يكتبها وحدها.
idempotent: التشغيل الثاني على المصدر نفسه لا يغيّر ملفًا، ولا يُمسّ حقل غير `OWNED`، والملف الذي لا يتغير لا يُكتب.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from apps.knowledge.domain.book_numbers import GUIDE_FIELDS, annotate, guide_numbers, template_max
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.schemas import LessonData

OWNED = ("page", "exercise_groups", *GUIDE_FIELDS)  # ما يكتبه الأمر؛ كل حقل سواه يبقى كما هو


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
    rest = {k: v for k, v in lesson.items() if k != "exercise_groups" and k not in GUIDE_FIELDS}
    rest["examples"] = [{k: v for k, v in e.items() if k != "page"} for e in lesson.get("examples", [])]
    return rest


class Command(BaseCommand):
    help = "يكتب صفحات أمثلة كتاب الطالب وتدريباتها وأرقام الدليل (أرقام فقط) في ملفات دروس مقرر بصياغتنا."

    def add_arguments(self, parser):
        parser.add_argument("course", help="معرّف المقرر، مثل g12-sci-s1")
        parser.add_argument("--source", required=True, help="مجلد الكتاب المستخرَج (خارج المستودع)")
        parser.add_argument("--examples", help="الافتراضي examples.json تحت المصدر")
        parser.add_argument("--printed-pages", help="الافتراضي printed_pages.json تحت المصدر")
        parser.add_argument("--links", help="الافتراضي exercise_links.json تحت المصدر إن وُجد")
        parser.add_argument("--records", help="مجلد سجلات مرحلة lesson؛ الافتراضي lessons تحت المصدر إن وُجد")
        parser.add_argument("--courses-dir", default=str(COURSES_DIR), help="جذر مجلدات المقررات")
        parser.add_argument(
            "--include-review",
            action="store_true",
            help="يكتب ما حالته review أيضًا من الروابط وأرقام الدليل (الافتراضي: ok وحدها)",
        )
        parser.add_argument(
            "--guide-only",
            action="store_true",
            help="يكتب أرقام الدليل وحدها؛ الصفحات والتدريبات تبقى كما هي في الملفات",
        )

    def handle(
        self,
        *args,
        course,
        source,
        examples=None,
        printed_pages=None,
        links=None,
        records=None,
        courses_dir=None,
        include_review=False,
        guide_only=False,
        **options,
    ):
        source = Path(source)
        files = sorted((Path(courses_dir or COURSES_DIR) / course / "lessons").glob("lesson_*.json"))
        if not files:
            raise CommandError(f"لا ملفات دروس بصياغتنا للمقرر {course}")
        starts, printed, linked = {}, {}, {}
        if not guide_only:
            starts = _json(Path(examples) if examples else source / "examples.json", "ملف الأمثلة")["lessons"]
            printed = _printed(Path(printed_pages) if printed_pages else source / "printed_pages.json")
            links_path = Path(links) if links else source / "exercise_links.json"
            linked = _json(links_path, "ملف الروابط")["lessons"] if links or links_path.is_file() else {}
        accepted = ("ok", "review") if include_review else ("ok",)
        records_dir = Path(records) if records else source / "lessons"
        if records and not records_dir.is_dir():
            raise CommandError(f"مجلد سجلات الدروس غير موجود: {records_dir}")

        changed, pages, groups, held = [], 0, 0, []
        guide_counts, contradicted = dict.fromkeys(GUIDE_FIELDS, 0), []
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
            # تمارين قسم «تمارين» غلاف مستقل بجانب الصفوف: يُعتمد وحده
            extra = entry.get("practice") if entry else None
            if extra and extra["status"] == "review" and not include_review:
                held.append(f"{code} (practice)")
            practice = extra["value"] if extra and extra["status"] in accepted else None
            record_path = records_dir / "lesson_{}.json".format(re.sub(r"[^\w]+", "_", code))
            numbers = (
                guide_numbers(_json(record_path, "سجل الدرس"), accepted) if record_path.is_file() else {}
            )
            # قوالب الدرس بصياغتنا شاهد على عدد تمارينه: عدد يخالف آخر رقم فيها قراءة لم تثبت، فلا يُكتب
            witness = template_max(lesson.get("templates", []))
            if witness and numbers.get("exercises_total", witness) != witness:
                contradicted.append(f"{code} ({numbers.pop('exercises_total')}≠{witness})")
            updated = annotate(lesson, known, rows, numbers, practice)
            if _without_owned(updated) != _without_owned(lesson):  # حارس: لا حقل غير المملوكين يتغير
                raise CommandError(f"تغيّر حقل غير {OWNED} في {path.name}")
            try:
                LessonData(**updated)
            except ValidationError as error:
                raise CommandError(f"{path.name}: {error}") from error
            pages += sum(e.get("page") is not None for e in updated.get("examples", []))
            groups += len(updated.get("exercise_groups", []))
            for key in GUIDE_FIELDS:
                guide_counts[key] += updated.get(key) not in (None, "", [])
            if json.dumps(updated, ensure_ascii=False) != json.dumps(lesson, ensure_ascii=False):
                text = json.dumps(updated, ensure_ascii=False, indent=1) + "\n"
                path.write_text(text, encoding="utf-8", newline="\n")
                changed.append(code)
        self.stdout.write(
            f"{course}: {len(files)} درسًا، أمثلة بصفحة {pages}، مجموعات تدريبات {groups}، "
            f"تغيّر {len(changed)} ملفًا" + (f"، روابط تنتظر المراجعة: {', '.join(held)}" if held else "")
        )
        self.stdout.write(
            "أرقام الدليل (دروس فيها الحقل): "
            + "، ".join(f"{key} {count}" for key, count in guide_counts.items())
            + (f"؛ عدد تمارين يخالف القوالب فلم يُكتب: {', '.join(contradicted)}" if contradicted else "")
        )
