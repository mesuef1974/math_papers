"""يطابق فهرس الصيغ `GeneratorForm` بالشيفرة. idempotent."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.papers.services import sync_generator_forms


class Command(BaseCommand):
    help = "يزامن فهرس صيغ المولّدات من الشيفرة؛ المحذوفة تُعطَّل ولا تُحذف"

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(sync_generator_forms()))
