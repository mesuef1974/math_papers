"""إشعار ويندوز بلا نافذة. خدمة جانبية: أي تعذّر يُهمل ولا يُسقط المشغّل."""

from __future__ import annotations

import os
import shutil
import subprocess

# النصّان يمرّان في البيئة لا داخل الأمر: عنوان بطاقة لا يصير شيفرة PowerShell.
TOAST = r"""
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $xml.GetElementsByTagName('text')
$null = $text.Item(0).AppendChild($xml.CreateTextNode($env:RUNNER_TOAST_TITLE))
$null = $text.Item(1).AppendChild($xml.CreateTextNode($env:RUNNER_TOAST_BODY))
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def send(title: str, body: str) -> bool:
    shell = shutil.which("powershell")
    if not shell:
        return False
    env = {**os.environ, "RUNNER_TOAST_TITLE": title, "RUNNER_TOAST_BODY": body}
    try:
        proc = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-Command", TOAST],
            env=env,
            capture_output=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
