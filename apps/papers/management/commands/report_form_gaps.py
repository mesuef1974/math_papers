"""تقرير أمثلة الوحدة التي لا صيغة لها أو لها صيغة واحدة. قراءة فقط، من الفهرس المزامَن."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.papers.selectors import generator_form_gaps


class Command(BaseCommand):
    help = "الأمثلة الأساسية بلا صيغة أو بصيغة واحدة (شغّل sync_generator_forms قبله)"

    def add_arguments(self, parser):
        parser.add_argument("course")
        parser.add_argument("--unit", type=int, default=1)

    def handle(self, *args, course, unit, **options):
        try:
            total, gaps = generator_form_gaps(course, unit)
        except KeyError as exc:
            raise CommandError(str(exc)) from exc
        if not total:
            raise CommandError(f"لا أمثلة أساسية للوحدة {unit} في {course}")
        for gap in gaps:
            names = "، ".join(gap.forms) or "لا صيغة"
            self.stdout.write(f"الدرس {gap.lesson} مثال {gap.example}: {len(gap.forms)} ({names})")
        none = sum(not gap.forms for gap in gaps)
        self.stdout.write(
            f"الأمثلة الأساسية {total}: بلا صيغة {none}، بصيغة واحدة {len(gaps) - none}، "
            f"مكتملة {total - len(gaps)}"
        )
