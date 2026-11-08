"""مقياس التنوع: كم مسألة مختلفة تعطي كل صيغة عبر بذور متتابعة، ويعلّم الصيغ التي تكرر نفسها."""

from django.core.management.base import BaseCommand

from apps.papers.domain.generators import diversity_report


class Command(BaseCommand):
    help = "تقرير تنوع المولّدات: الصيغ التي تعطي أقل من --min مسألة مختلفة عبر --seeds بذرة تُعلَّم"

    def add_arguments(self, parser):
        parser.add_argument("--seeds", type=int, default=60)
        parser.add_argument("--min", type=int, default=20, dest="minimum")

    def handle(self, *args, **options):
        rows = diversity_report(options["seeds"])
        weak = [row for row in rows if row["distinct"] < options["minimum"]]
        self.stdout.write(f"{'الدرس':<6}{'الصيغة':<44}{'المستويات':<10}{'مختلفة/بذور'}")
        for row in rows:
            flag = "  ← ضيقة" if row["distinct"] < options["minimum"] else ""
            self.stdout.write(
                f"{row['lesson']:<6}{row['variant']:<44}{row['levels']:<10}{row['distinct']}/{row['seeds']}{flag}"
            )
        self.stdout.write(f"\n{len(rows)} صيغة، منها {len(weak)} دون الحد {options['minimum']}.")
        if weak:
            self.stdout.write(self.style.WARNING("صيغ ضيقة: " + "، ".join(r["variant"] for r in weak)))
