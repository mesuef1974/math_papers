from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.domain.contract import source_slugs
from apps.knowledge.services import load_course


class Command(BaseCommand):
    help = "يحمّل معرفة مقرر (أو كل المقررات بـ --all) من مصدره بالمحمِّل الواحد (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("course", nargs="?", help=f"رمز المقرر: {', '.join(source_slugs())}")
        parser.add_argument("--all", action="store_true", help="كل المقررات ذات المصدر")

    def handle(self, *args, **options):
        if options["all"] == bool(options["course"]):
            raise CommandError("حدّد مقررًا واحدًا أو --all")
        slugs = source_slugs() if options["all"] else [options["course"]]
        for slug in slugs:
            try:
                report = load_course(slug)
            except KeyError as error:
                raise CommandError(str(error.args[0])) from error
            self.stdout.write(
                f"{slug}: تغيّر {dict(report.changed) or 'لا شيء'} (تجزئة {report.content_hash[:12]})"
            )
