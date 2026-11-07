from django.core.management.base import BaseCommand

from apps.knowledge.services import load_knowledge


class Command(BaseCommand):
    help = "يحمّل معرفة المنهج من apps/knowledge/data (idempotent)."

    def handle(self, *args, **options):
        report = load_knowledge()
        self.stdout.write(f"تغيّر: {dict(report.changed) or 'لا شيء'}")
        if report.skipped:
            self.stdout.write(f"دروس خارج منهج المنصة (لم تُحمَّل): {', '.join(report.skipped)}")
