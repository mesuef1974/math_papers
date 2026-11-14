#!/usr/bin/env python3
"""حارس بصري: يقيس انحراف تخطيط الورقة بين الشاشة والطباعة بمتصفح حقيقي، ويفشل إن انحرف.

الفكرة: الورقة على الشاشة تتبع قواعد الورق نفسها (print.css، نطاق ‎.sheet‎)، فعرض كل سؤال وجزء وارتفاعه
(أي التفاف أسطره) يجب أن يتساوى في عرض الشاشة (A4 بحجمه الحقيقي) وفي وسائط الطباعة بعرض محتوى الصفحة
(210مم ناقص هامشَي 14مم). أي قاعدة تُضاف للشاشة وحدها أو للطباعة وحدها فتغيّر ذلك تُكشف هنا قبل أن يراها معلم.

يولّد الاختبار الكامل والقصير وورقة العمل من خادم Django حقيقي (قاعدة SQLite مؤقتة) ويقيس كلًّا منها، ثم يتحقق
أن مسار الملف المضمَّن يعيد PDF صالحًا. بلا نافذة (Chromium بلا واجهة) ويغلق الخادم دائمًا في finally.

الاستعمال (يدويًا قبل تغيير في أنماط الورقة؛ ليس في pytest ولا CI لأن المتصفح والحزمة المبنية غير مضمونين فيهما):
    python scripts/visual_guard.py [--no-build] [--tolerance 1.0] [--drift-demo]
    --drift-demo يُدخل انحرافًا مقصودًا في أنماط الشاشة وحدها ليُرى الحارس يفشل ويسمّي العنصر.
الخروج: 0 لا انحراف، 1 انحراف أو ملف PDF غير صالح، 2 تعذّر التشغيل.
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8062
SELECTORS = (".question", ".part")
SCREEN_VIEWPORT = (1400, 1000)  # أوسع من A4: الورقة بحجمها الحقيقي بلا تصغير (‎--paper-zoom‎ = 1)
PRINT_VIEWPORT = (688, 1000)  # محتوى الصفحة المطبوعة: 210مم ناقص هامشَي 14مم ≈ 687.9px
MODES = (("exam", "الاختبار الكامل"), ("quiz", "الاختبار القصير"), ("worksheet", "ورقة العمل"))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

Boxes = dict[str, list[tuple[float, float]]]

MEASURE_JS = """
(selectors) => {
  const sheets = [...document.querySelectorAll('.sheet-focus .sheet')];
  const out = {};
  for (const selector of selectors) {
    out[selector] = sheets.flatMap((sheet) =>
      [...sheet.querySelectorAll(selector)].map((el) => {
        const box = el.getBoundingClientRect();
        return [box.width, box.height];
      }),
    );
  }
  out['.sheet'] = sheets.map((sheet) => { const box = sheet.getBoundingClientRect(); return [box.width, 0]; });
  return out;
}
"""


def compare_boxes(screen: Boxes, printed: Boxes, tolerance: float = 1.0) -> list[str]:
    """فروق التخطيط بين قياس الشاشة وقياس الطباعة، رسائل عربية؛ قائمة فارغة = لا انحراف.

    العناصر تُقابَل بترتيبها في الصفحة. اختلاف العدد أو العرض أو الارتفاع بأكثر من tolerance بكسل انحراف.
    عرض ‎.sheet‎ نفسه لا يُقارن (الشاشة 210مم والطباعة 182مم بالتصميم)؛ يُقاس فقط ليُعرف أن القياس جرى.
    """
    problems: list[str] = []
    for selector in sorted(set(screen) | set(printed)):
        if selector == ".sheet":
            continue
        on_screen, on_paper = screen.get(selector, []), printed.get(selector, [])
        if len(on_screen) != len(on_paper):
            problems.append(f"{selector}: العدد {len(on_screen)} على الشاشة و{len(on_paper)} في الطباعة")
            continue
        for index, ((sw, sh), (pw, ph)) in enumerate(zip(on_screen, on_paper, strict=True), start=1):
            if abs(sw - pw) > tolerance:
                problems.append(f"{selector} رقم {index}: العرض {sw:.1f} على الشاشة و{pw:.1f} في الطباعة")
            if abs(sh - ph) > tolerance:
                problems.append(f"{selector} رقم {index}: الارتفاع {sh:.1f} على الشاشة و{ph:.1f} في الطباعة")
    return problems


def _env(db: Path) -> dict[str, str]:
    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.base",
        "SECRET_KEY": secrets.token_hex(24),  # لكل تشغيل مفتاح عشوائي؛ الخادم مؤقت ولا يخرج من الجهاز
        "DATABASE_URL": f"sqlite:///{db.as_posix()}",
        "PAPERS_WARM_CACHE": "0",
        "PDF_RENDER_BASE_URL": f"http://localhost:{PORT}",
        "PYTHONUTF8": "1",
        "PORT": str(PORT),
    }


def _manage(env: dict[str, str], *args: str) -> None:
    subprocess.run(  # noqa: S603
        [sys.executable, "-X", "utf8", "manage.py", *args],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        creationflags=NO_WINDOW,
    )


def _build_frontend() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm غير موجود؛ ابنِ الواجهة يدويًا ثم مرّر --no-build")
    subprocess.run([npm, "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)  # noqa: S603


def _measure(page, selectors=SELECTORS) -> Boxes:
    page.evaluate("document.fonts.ready")
    return {k: [tuple(box) for box in v] for k, v in page.evaluate(MEASURE_JS, list(selectors)).items()}


def _generate(page, mode: str) -> None:
    """يختار النوع ويولّد، وينتظر الورقة الجديدة لا السابقة (نصها يتغيّر بين الأنواع)."""
    previous = page.evaluate("document.querySelector('.sheet-focus .sheet')?.innerText ?? ''")
    page.locator(f"input[type=radio][value={mode}]").check()
    page.locator("form.generator button[type=submit]").click()
    page.wait_for_function(
        "(previous) => { const sheet = document.querySelector('.sheet-focus .sheet');"
        " return sheet && sheet.innerText !== previous"
        " && document.querySelector('form.generator').getAttribute('aria-busy') !== 'true'; }",
        arg=previous,
        timeout=30000,
    )
    page.evaluate("document.fonts.ready")


def _check_mode(page, mode: str, label: str, tolerance: float, drift: bool) -> list[str]:
    page.set_viewport_size({"width": SCREEN_VIEWPORT[0], "height": SCREEN_VIEWPORT[1]})
    page.emulate_media(media="screen")
    _generate(page, mode)
    if drift:
        page.add_style_tag(content="@media screen { .sheet .stem { font-size: 1.25em !important; } }")
    zoom = page.evaluate(
        "getComputedStyle(document.querySelector('.sheet-focus')).getPropertyValue('--paper-zoom')"
    )
    screen = _measure(page)
    page.set_viewport_size({"width": PRINT_VIEWPORT[0], "height": PRINT_VIEWPORT[1]})
    page.emulate_media(media="print")
    printed = _measure(page)
    problems = compare_boxes(screen, printed, tolerance)
    if zoom.strip() not in ("1", ""):
        problems.append(
            f"الورقة مصغَّرة على الشاشة (‎--paper-zoom‎ = {zoom.strip()})، فالقياس غير مطابق للحجم الحقيقي"
        )
    if not screen.get(".part"):
        problems.append("لم يُقَس أي جزء: الأصناف تغيّرت أو الورقة لم تُرسم")
    counts = ", ".join(f"{len(v)} × {k}" for k, v in screen.items() if k != ".sheet")
    print(f"{'✘' if problems else '✔'} {label}: {counts}", flush=True)
    return [f"{label}: {p}" for p in problems]


def _check_pdf(page) -> list[str]:
    page.set_viewport_size({"width": SCREEN_VIEWPORT[0], "height": SCREEN_VIEWPORT[1]})
    page.emulate_media(media="screen")
    page.locator("input[type=radio][value=pdf]").check()
    page.wait_for_selector("a.open, .pdf-preview .alert-error", timeout=90000)
    if page.locator(".pdf-preview .alert-error").count():
        message = page.locator(".pdf-preview .alert-error").inner_text()
        print(f"✘ ملف PDF المضمَّن: {message}", flush=True)
        return [f"المعاينة فشلت: {message}"]
    href = page.locator("a.open").get_attribute("href") or ""
    response = page.request.get(f"http://localhost:{PORT}{href}")
    body = response.body()
    ok = response.status == 200 and body.startswith(b"%PDF") and len(body) > 10_000
    print(f"{'✔' if ok else '✘'} ملف PDF المضمَّن: {response.status}، {len(body)} بايت", flush=True)
    return [] if ok else [f"ملف PDF المضمَّن غير صالح: {response.status}، {len(body)} بايت"]


def run(tolerance: float, drift: bool) -> list[str]:
    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        env = _env(Path(tmp) / "guard.db")
        _manage(env, "migrate", "--noinput")
        _manage(env, "collectstatic", "--noinput")
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-X",
                "utf8",
                "-c",
                "import django; django.setup(); from apps.papers.access import ensure_teacher; "
                f"ensure_teacher('guard', {secrets.token_urlsafe(18)!r})",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            creationflags=NO_WINDOW,
        )
        log = open(Path(tmp) / "server.log", "w", encoding="utf-8")  # noqa: SIM115
        server = subprocess.Popen(  # noqa: S603
            [sys.executable, "-X", "utf8", "manage.py", "runserver", f"127.0.0.1:{PORT}", "--noreload"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=NO_WINDOW,
        )
        try:
            for _ in range(80):
                try:
                    urllib.request.urlopen(f"http://localhost:{PORT}/health/", timeout=2)  # noqa: S310
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError("الخادم لم يبدأ")
            code = (
                "import os, django; os.environ.update("
                + repr(
                    {k: env[k] for k in env if k in ("DJANGO_SETTINGS_MODULE", "SECRET_KEY", "DATABASE_URL")}
                )
                + "); django.setup();"
                "from django.contrib.auth import get_user_model; from django.test import Client;"
                "c = Client(); c.force_login(get_user_model().objects.get(username='guard'));"
                "print(c.cookies['sessionid'].value)"
            )
            session = subprocess.run(  # noqa: S603
                [sys.executable, "-X", "utf8", "-c", code],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                creationflags=NO_WINDOW,
            ).stdout.strip()
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(args=["--no-sandbox"])
                try:
                    context = browser.new_context(
                        viewport={"width": SCREEN_VIEWPORT[0], "height": SCREEN_VIEWPORT[1]}, locale="ar-QA"
                    )
                    context.add_cookies(
                        [{"name": "sessionid", "value": session, "url": f"http://localhost:{PORT}"}]
                    )
                    page = context.new_page()
                    page.goto(f"http://localhost:{PORT}/", wait_until="networkidle")
                    for mode, label in MODES:
                        problems += _check_mode(page, mode, label, tolerance, drift)
                    if not drift:
                        page.set_viewport_size({"width": SCREEN_VIEWPORT[0], "height": SCREEN_VIEWPORT[1]})
                        page.emulate_media(media="screen")
                        _generate(page, "exam")
                        problems += _check_pdf(page)
                finally:
                    browser.close()
        finally:
            subprocess.run(
                ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                capture_output=True,
                creationflags=NO_WINDOW,
            )  # noqa: S603, S607
            server.wait(timeout=10)
            log.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build", action="store_true", help="لا تبنِ الواجهة (بُنيت للتو)")
    parser.add_argument("--tolerance", type=float, default=1.0, help="الفرق المسموح بالبكسل")
    parser.add_argument("--drift-demo", action="store_true", help="أدخل انحرافًا مقصودًا ليُرى الفشل")
    args = parser.parse_args()
    try:
        if not args.no_build:
            _build_frontend()
        problems = run(args.tolerance, args.drift_demo)
    except Exception as exc:  # noqa: BLE001 — أي عطل في التشغيل يُبلَّغ برمز 2 لا برمز انحراف
        print(f"[خطأ] {exc}", file=sys.stderr)
        return 2
    if problems:
        print(f"\n[انحراف] {len(problems)} فرق:")
        for problem in problems[:40]:
            print(f"  - {problem}")
        return 1
    print("\n[سليم] لا انحراف بين الشاشة والطباعة")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
