"""مؤشرات خطة المبادرات: يقرأ مفاتيح kpis من docs/innovation_plan.yaml ويكتب قيمها في metrics_file.

    python manage.py plan_metrics
مفتاح لكل مؤشر، وnull لما لا جدول له بعد. أعداد ونسب فقط، وتشغيلان على قاعدة لم تتغير يعطيان الملف نفسه.
يقرؤه `python scripts/plan_status.py --write` ليملأ جدول مؤشرات الأثر في الوثيقة.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import PlanMetricsError, write_plan_metrics


class Command(BaseCommand):
    help = "يحسب مؤشرات خطة المبادرات ويكتبها JSON (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--root", type=Path, default=settings.BASE_DIR, help="جذر المستودع الذي فيه ملف الخطة"
        )

    def handle(self, *args, **options):
        root: Path = options["root"]
        try:
            target = write_plan_metrics(root)
        except PlanMetricsError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"كُتبت {target.relative_to(root.resolve()).as_posix()}")
