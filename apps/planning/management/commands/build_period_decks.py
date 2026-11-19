"""يبني عروض كل حصص مقرر من مقاطعه المنشورة ويطبع سطرًا واحدًا: «ناجح N فاشل M».

شاهد مقاطع الأمثلة على معايير العروض (ومنها S7: دقة المقطع وارتفاعه) قبل نشرها في الإنتاج؛ تشغّله مرحلة `student_decks`
في `tools/extraction` على قاعدة وتخزين مؤقتين. الفشل رمز خروج 1 وأسبابه في مخرج الخطأ.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.planning import selectors, services


class Command(BaseCommand):
    help = "يبني عرض كل حصة دروس في خطة المقرر ويطبع عدد الناجح والفاشل."

    def add_arguments(self, parser):
        parser.add_argument("course", help="رمز المقرر، مثل g10-s1")

    def handle(self, *args, course: str, **options):
        try:
            built, failures = services.build_course_decks(course)
        except selectors.PrepNotFoundError as error:
            raise CommandError(str(error)) from error
        line = f"ناجح {built} فاشل {len(failures)}"
        if failures:
            for failure in failures:
                self.stderr.write(failure)
            raise CommandError(line)
        self.stdout.write(line)
