"""يبني فهرس العاشر المشتق (`apps/knowledge/data/grade10_index.json`) من مخرجات الاستخراج الخارجية.

المصدر مجلد الكتاب (`lessons/lesson_*.json`) خارج المستودع ولا يُنسخ منه نص: `grade10_index.build_lesson_index` يُبقي الأرقام
والرموز والفئات المغلقة فقط. idempotent: التشغيل الثاني على المصدر نفسه يكتب الملف نفسه بايتًا ببايت.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.domain.grade10_index import build_index

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TARGET = DATA_DIR / "grade10_index.json"


class Command(BaseCommand):
    help = "يشتق فهرس العاشر (أرقام وبلوم وتمثيلات بلا نص دليل) من مجلد الاستخراج الخارجي."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="مجلد كتاب العاشر (خارج المستودع)")
        parser.add_argument("--target", default=str(TARGET), help="ملف الفهرس الناتج")

    def handle(self, *args, source, target, **options):
        files = sorted((Path(source) / "lessons").glob("lesson_*.json"))
        if not files:
            raise CommandError("لا ملفات lessons/lesson_*.json في المصدر")
        index = build_index([json.loads(f.read_text(encoding="utf-8")) for f in files])
        out = Path(target)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(index.model_dump(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.stdout.write(f"فهرس العاشر: {len(index.lessons)} درسًا → {out.name}")
