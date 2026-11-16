from django.core.management.base import BaseCommand

from apps.knowledge.services import load_knowledge


class Command(BaseCommand):
    help = "اسم قديم لـ load_course: يحمّل معرفة الثاني عشر (idempotent)."

    def handle(self, *args, **options):
        report = load_knowledge()
        self.stdout.write(f"تغيّر: {dict(report.changed) or 'لا شيء'}")
