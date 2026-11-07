from django.core.management.base import BaseCommand

from apps.knowledge.selectors import coverage


class Command(BaseCommand):
    help = "تقرير: تمارين الدليل مقابل صيغ المولّدات لكل درس × مستوى × رسم. الفجوة = لا مولّد."

    def handle(self, *args, **options):
        gaps = 0
        for row in coverage():
            mark = "" if row.generators else "  <-- فجوة"
            gaps += not row.generators
            graph = "رسم" if row.graph else "-"
            self.stdout.write(
                f"{row.lesson} {row.level} {graph:3} قوالب={row.templates:3} مولّدات={row.generators}{mark}"
            )
        self.stdout.write(f"فجوات: {gaps}")
