from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.assets.services import AssetError, publish_assets
from apps.assets.storage import StorageError


class Command(BaseCommand):
    help = "ينشر مقاطع مجلد إلى تخزين الأصول ويفهرسها (idempotent بالتجزئة)."

    def add_arguments(self, parser):
        parser.add_argument("course", help="رمز المقرر، مثل g10-s1")
        parser.add_argument("--source", required=True, help="مجلد المقاطع (خارج المستودع)")

    def handle(self, *args, course, source, **options):
        try:
            report = publish_assets(course, Path(source))
        except (AssetError, StorageError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            f"{course}: جديد {report.created}، محدَّث {report.updated}، أُعيد رفعه {report.repaired}، "
            f"بلا تغيير {report.unchanged} (المجموع {report.total}؛ يتيم {report.orphans})"
        )
        for name in report.unmatched:
            self.stdout.write(f"  اسم لا يطابق النمط ولم يُنشر: {name}")
