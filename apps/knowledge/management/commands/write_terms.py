"""يكتب `terms.json` لمقرر الفهرس المشتق من سجلات مرحلة `lesson` خارج المستودع: اسم كل مصطلح بالعربية والإنجليزية وحده.

idempotent: المدخل نفسه يعطي الملف نفسه. لا يطبع نص مصطلح، أعدادًا فقط.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.domain.contract import INDEX, TERMS, course_dir
from apps.knowledge.domain.schemas import TermData


def terms_of(record: dict) -> list[dict]:
    value = record.get("vocabulary") or []
    if isinstance(value, dict):
        value = value.get("value") or []
    out: dict[str, dict] = {}
    for item in value:
        ar = " ".join(str(item.get("ar") or "").split())
        if ar:
            term = TermData(ar=ar, en=" ".join(str(item.get("en") or "").split()))
            out.setdefault(ar, term.model_dump())
    return list(out.values())


class Command(BaseCommand):
    help = "يكتب أسماء مصطلحات دروس مقرر الفهرس المشتق من مجلد الكتاب خارج المستودع"

    def add_arguments(self, parser):
        parser.add_argument("course")
        parser.add_argument("--source", required=True)

    def handle(self, *args, course, source, **options):
        directory = course_dir(course)
        if not (directory / INDEX).is_file():
            raise CommandError(f"{course}: لا فهرس مشتق (مصطلحاته في ملفات دروسه)")
        codes = [lesson["lesson"] for lesson in json.loads((directory / INDEX).read_text("utf-8"))["lessons"]]
        lessons = {}
        for code in codes:
            path = Path(source) / "lessons" / f"lesson_{code.replace('.', '_')}.json"
            if path.is_file() and (terms := terms_of(json.loads(path.read_text("utf-8")))):
                lessons[code] = terms
        if not lessons:
            raise CommandError("لا مصطلحات في المصدر")
        text = json.dumps({"schema_version": 1, "lessons": lessons}, ensure_ascii=False, indent=1)
        (directory / TERMS).write_text(text + "\n", encoding="utf-8", newline="\n")
        self.stdout.write(f"{course}: {len(lessons)} درسًا، {sum(map(len, lessons.values()))} مصطلحًا")
