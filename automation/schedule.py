#!/usr/bin/env python3
"""جدولة المشغّل على Task Scheduler في ويندوز: مهمة واحدة مخفية بلا نافذة، تتكرر كل N دقائق.

    python automation/schedule.py install [--minutes 5] [--model <id>]
    python automation/schedule.py status
    python automation/schedule.py remove

install يعيد كتابة المهمة نفسها (idempotent). المهمة تشغّل runner.py من المجلد الرئيسي للمشروع ببايثون
الذي شغّل هذا الأمر، فشغّله ببايثون `.venv`. conhost --headless يمنع ظهور نافذة طرفية (قرار المالك).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
TASK = "MathPapers-Runner"
# أطول من قفل المشغّل (3 ساعات) لا يُترك تشغيل معلَّق.
TIME_LIMIT = "PT3H"


def task_xml(python: Path, root: Path, minutes: int, start: datetime, user: str, model: str | None) -> str:
    conhost = Path(os.environ.get("SystemRoot", r"C:\WINDOWS")) / "System32" / "conhost.exe"
    arguments = f'--headless "{python}" "{root / "automation" / "runner.py"}" --once'
    if model:
        arguments += f" --model {model}"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>مشغّل بطاقات مولّد أوراق الرياضيات: يلتقط بطاقة ready واحدة في كل تشغيل.</Description>
    <URI>\\{TASK}</URI>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <Hidden>true</Hidden>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>{TIME_LIMIT}</ExecutionTimeLimit>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
  </Settings>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{start.strftime("%Y-%m-%dT%H:%M:00")}</StartBoundary>
      <Repetition>
        <Interval>PT{minutes}M</Interval>
      </Repetition>
    </TimeTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(conhost))}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(root))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def install(minutes: int, model: str | None) -> int:
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\")
    xml = task_xml(Path(sys.executable), ROOT, minutes, datetime.now(), user, model)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "task.xml"
        path.write_text(xml, encoding="utf-16")
        proc = schtasks("/create", "/tn", TASK, "/xml", str(path), "/f")
    print((proc.stdout or proc.stderr).strip())
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_install = sub.add_parser("install")
    p_install.add_argument("--minutes", type=int, default=5)
    p_install.add_argument("--model")
    sub.add_parser("status")
    sub.add_parser("remove")
    args = ap.parse_args(argv)

    if sys.platform != "win32":
        print("الجدولة هنا لويندوز وحده؛ على غيره استعمل cron مع runner.py --once")
        return 3
    if args.cmd == "install":
        return install(args.minutes, args.model)
    if args.cmd == "status":
        # «Last Result» في Task Scheduler صفر دائمًا خلف conhost؛ آخر سطر في سجل المشغّل هو الدليل.
        log = ROOT / ".worktrees" / "runner.log"
        last = log.read_text(encoding="utf-8").splitlines()[-1:] if log.exists() else []
        print("آخر تشغيل للمشغّل:", last[0] if last else "لا سجل بعد")
        proc = schtasks("/query", "/tn", TASK, "/fo", "list")
    else:
        proc = schtasks("/delete", "/tn", TASK, "/f")
    print((proc.stdout or proc.stderr).strip())
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
