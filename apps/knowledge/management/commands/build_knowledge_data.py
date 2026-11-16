"""يبني ملفات المعرفة المنسقة داخل المستودع من المستخرج الخاص خارجه.

لا يُكتب إلا ما اجتاز الحارس؛ وما سقط يُطبع للمراجعة. الإدخال خارج المستودع ولا يُنسخ إليه.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.curriculum.courses import GRADE12_SLUG
from apps.knowledge.domain.curation import Report, build_lesson, build_pedagogy, build_units
from apps.knowledge.domain.schemas import LessonData, PedagogyData, UnitData

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "courses" / GRADE12_SLUG  # مقرر الثاني عشر


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "ينسّق المستخرج الخاص إلى apps/knowledge/data/courses/g12-sci-s1 (بلا نص خام)."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="مجلد المستخرج الخاص (خارج المستودع)")

    def handle(self, *args, source, **options):
        src = Path(source)
        if not (src / "front_matter_and_units.json").exists():
            raise CommandError("مجلد المصدر لا يحوي front_matter_and_units.json")
        report = Report()
        front = _load(src / "front_matter_and_units.json")

        lessons = 0
        for unit in front["contents"]["units"]:
            for code in unit["lessons"]:
                tag = code.replace(".", "_")
                full = src / f"lesson_{tag}_full.json"
                if full.exists():
                    opener = body = _load(full)
                else:
                    opener = _load(src / f"lesson_{tag}_opener.json")
                    body = _load(src / f"lesson_{tag}_body.json")
                data = build_lesson(code, opener, body, report)
                if not data["standards"]:
                    data["standards"] = unit["lessons"][code]["standards"]
                _dump(DATA_DIR / "lessons" / f"lesson_{tag}.json", LessonData(**data).model_dump())
                lessons += 1

        reviews = {n: _load(src / f"unit_{n}_review.json") for n in (1, 2, 3)}
        units = [UnitData(**u).model_dump() for u in build_units(front, reviews, report)]
        _dump(DATA_DIR / "units.json", units)
        notes = [PedagogyData(**n).model_dump() for n in build_pedagogy(front, report)]
        _dump(DATA_DIR / "pedagogy.json", notes)

        self.stdout.write(
            f"دروس: {lessons}، وحدات: {len(units)}، مبادئ: {len(notes)}، نصوص أُسقطت: {len(report.dropped)}"
        )
        for line in report.dropped:
            self.stdout.write(f"  أُسقط {line}")
