"""يحذف طلاب ونتائج بنود المقررات التي انتهت سنتها الأكاديمية (قرار المالك 2026-11-25: الاحتفاظ حتى نهاية العام الدراسي).

نهاية السنة آخر يوم في فصول تقويمها (`AcademicCalendar`). idempotent: التشغيل الثاني لا يجد ما يحذفه. أعداد
`ClassOutcomeRecord` المجمَّعة تبقى.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.planning import services


class Command(BaseCommand):
    help = "يحذف بيانات الطلاب الفردية (الطلاب ونتائج البنود) لمقررات السنوات الأكاديمية المنتهية."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="يعدّ ما سيُحذف بلا حذف")

    def handle(self, *args, dry_run: bool, **options):
        purged = services.purge_ended_results(write=not dry_run)
        if not purged.years:
            self.stdout.write("لا سنة أكاديمية منتهية في التقويم")
            return
        verb = "سيُحذف" if dry_run else "حُذف"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {purged.results} نتيجة و{purged.students} طالبًا من السنوات المنتهية: "
                f"{'، '.join(purged.years)}"
            )
        )
