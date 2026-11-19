"""يكتب اقتراحات المعلمين المقبولة في ملف الوحدة `prep/unit-<n>.json` ويحدّث سطر اعتماده (idempotent).

يشغّله المالك أو الجلسة محليًا ثم طلب دمج يعتمده المالك كأي تغيير في نصوص الوحدة
(`docs/teacher_objective_review_plan.md`، جانب المالك).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.planning import services
from apps.planning.domain.calendar_engine import PlanningError


class Command(BaseCommand):
    help = "يطبّق اقتراحات الأهداف المقبولة على ملف وحدة من مقرر (الشرط والمعيار وحدهما)."

    def add_arguments(self, parser):
        parser.add_argument("course")
        parser.add_argument("--unit", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true", help="يعرض ما سيتغير بلا كتابة")

    def handle(self, *args, course: str, unit: int, dry_run: bool, **options):
        try:
            result = services.apply_objective_suggestions(course, unit, write=not dry_run)
        except (PlanningError, KeyError, ValueError) as error:
            raise CommandError(str(error)) from error
        for line in result.skipped:
            self.stdout.write(self.style.WARNING(f"تُخطّي {line}"))
        if not result.changed:
            self.stdout.write("لا تغيير: كل اقتراح مقبول مُطبَّق من قبل أو مُتخطّى")
            return
        for item in result.applied:
            self.stdout.write(
                f"الدرس {item.lesson} مثال {item.example} (الاقتراح {item.suggestion}): "
                f"{item.condition} | {item.criterion}"
            )
        verb = "سيُكتب" if dry_run else "كُتب"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {len(result.applied)} اقتراحًا في الوحدة {unit}، و{result.raw['approval']}"
            )
        )
