"""توليد PDF في الخادم: Chromium (عبر Playwright) يفتح صفحة الطباعة نفسها من واجهة Vue ويطبعها A4.

لا عارض ثانٍ للورقة: ما يراه المعلم على الشاشة هو ما يُطبع، وترقيم الصفحات من قواعد @page نفسها لكن بمحرك
واحد معروف بدل متصفح كل معلم. المهمة خلفية داخل عملية الويب (خيط واحد وطابور قصير) لأن التوليد ثوانٍ، وحالتها
وملفها في الكاش بمهلة قصيرة فيجيب أي عامل gunicorn الاستطلاع. صفحة الطباعة تقرأ حمولتها برمز موقّع قصير العمر
بلا جلسة، فلا تصل كوكي المعلم إلى المتصفح الخادمي.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import cache as memoize
from typing import Any

from django.conf import settings
from django.core import signing
from django.core.cache import cache

log = logging.getLogger(__name__)

TTL = 600  # ثوانٍ يبقى فيها الملف والحالة في الكاش
TOKEN_MAX_AGE = 300  # عمر رمز صفحة الطباعة
TOKEN_SALT = "papers.pdf.print"
RENDER_TIMEOUT_MS = 30_000
STALE_AFTER = 90  # مهمة لم تنتهِ بعد هذه الثواني فشل عاملها، فتُبلَّغ خطأً بدل انتظار بلا نهاية
MAX_QUEUE = 4  # أقصى مهام بانتظار الخيط الواحد؛ فوقها يُطلب من المعلم المحاولة لاحقًا
BUSY = "الخادم مشغول بتوليد ملفات أخرى. حاول بعد قليل."
UNAVAILABLE = "توليد PDF في الخادم غير مفعّل هنا. استعمل «طباعة أو حفظ PDF» من المتصفح."
FAILED = "تعذر توليد الملف. حاول مرة أخرى، أو اطبع من المتصفح."


class BusyError(RuntimeError):
    pass


class UnavailableError(RuntimeError):
    pass


def base_url() -> str:
    """عنوان الخادم نفسه كما يراه Chromium في الحاوية (الصحة تفحص localhost أيضًا، فهو في ALLOWED_HOSTS)."""
    configured = getattr(settings, "PDF_RENDER_BASE_URL", "") or os.environ.get("PDF_RENDER_BASE_URL", "")
    return configured.rstrip("/") or f"http://localhost:{os.environ.get('PORT', '8000')}"


@memoize
def available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def render_pdf(url: str) -> bytes:
    """يفتح صفحة الطباعة في Chromium وينتظر إشارة جاهزيتها (الخطوط والرياضيات) ثم يطبع A4 بخلفياتها."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        # لا رمل (sandbox) لأن الحاوية بلا user namespaces، والصفحة صفحتنا وحدها.
        browser = playwright.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            # خلف وكيل Railway يُعاد توجيه http إلى https؛ الطلب الداخلي يحمل الترويسة نفسها التي يحملها الوكيل.
            context = browser.new_context(extra_http_headers={"X-Forwarded-Proto": "https"}, locale="ar-QA")
            page = context.new_page()
            page.emulate_media(media="print")
            page.goto(url, wait_until="networkidle", timeout=RENDER_TIMEOUT_MS)
            page.wait_for_function(
                "['1', 'error'].includes(document.documentElement.dataset.printReady ?? '')",
                timeout=RENDER_TIMEOUT_MS,
            )
            if page.evaluate("document.documentElement.dataset.printReady") == "error":
                raise RuntimeError("print page reported an error")
            return page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


_PAGE_OBJECT = re.compile(rb"/Type\s*/Page(?![A-Za-z])")


def count_pages(data: bytes) -> int:
    """عدد صفحات ملف PDF من Chromium: كائنات الصفحات (‎/Type /Page‎) لا عقدة الشجرة (‎/Pages‎).
    تقدير للتقليب في المعاينة فقط؛ الصفر يعني «غير معروف» فيُعرض العارض بلا أزرار."""
    return len(_PAGE_OBJECT.findall(data))


def safe_filename(title: str, extension: str = "pdf") -> str:
    cleaned = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", title)).strip() or "ورقة"
    return f"{cleaned[:120]}.{extension}"


def _key(job_id: str, part: str = "") -> str:
    return f"papers:pdf:{job_id}:{part}" if part else f"papers:pdf:{job_id}"


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="papers-pdf")
_lock = threading.Lock()
_queued = 0


def _submit(job_id: str) -> None:
    global _queued
    with _lock:
        if _queued >= MAX_QUEUE:
            raise BusyError(BUSY)
        _queued += 1
    _executor.submit(_run, job_id)


def _run(job_id: str) -> None:
    global _queued
    try:
        _render_job(job_id)
    finally:
        with _lock:
            _queued -= 1


def _render_job(job_id: str) -> None:
    meta = cache.get(_key(job_id))
    if not meta:
        return
    cache.set(_key(job_id), {**meta, "status": "running", "started": time.time()}, TTL)
    token = signing.dumps({"job": job_id}, salt=TOKEN_SALT)
    try:
        if meta.get("format") == "docx":
            from .word.builder import build_docx

            data = build_docx(cache.get(_key(job_id, "payload")))
        else:
            data = render_pdf(f"{base_url()}/print/{token}")
    except Exception:  # noqa: BLE001 — أي عطل في المتصفح يُبلَّغ للمعلم كرسالة واحدة ويُسجَّل كاملًا
        log.exception("pdf render failed for job %s", job_id)
        cache.set(_key(job_id), {**meta, "status": "error", "error": FAILED}, TTL)
        return
    pages = count_pages(data) if meta.get("format") != "docx" else 0
    cache.set(_key(job_id, "file"), data, TTL)
    cache.set(_key(job_id), {**meta, "status": "done", "size": len(data), "pages": pages}, TTL)


def create_job(owner_id: int, payload: dict[str, Any], title: str, fmt: str = "pdf") -> dict[str, Any]:
    """يسجّل الحمولة والحالة ثم يسلّم المهمة للخيط الخلفي. يرفع UnavailableError أو BusyError.
    fmt: pdf (Chromium) أو docx (python-docx، لا يحتاج المتصفح)."""
    if fmt == "pdf" and not available():
        raise UnavailableError(UNAVAILABLE)
    job_id = uuid.uuid4().hex
    meta = {
        "id": job_id,
        "owner": owner_id,
        "status": "queued",
        "error": "",
        "format": fmt,
        "filename": safe_filename(title, fmt),
        "created": time.time(),
    }
    cache.set(_key(job_id, "payload"), payload, TTL)
    cache.set(_key(job_id), meta, TTL)
    try:
        _submit(job_id)
    except BusyError:
        cache.delete_many([_key(job_id), _key(job_id, "payload")])
        raise
    return cache.get(_key(job_id)) or meta  # قد يكون الخيط أنهى المهمة قبل الرد


def job_status(owner_id: int, job_id: str) -> dict[str, Any] | None:
    """حالة مهمة المالك نفسه؛ غيره لا يرى حتى وجودها."""
    meta = cache.get(_key(job_id))
    if not meta or meta["owner"] != owner_id:
        return None
    if (
        meta["status"] in ("queued", "running")
        and time.time() - meta.get("started", meta["created"]) > STALE_AFTER
    ):
        meta = {**meta, "status": "error", "error": FAILED}
        cache.set(_key(job_id), meta, TTL)
    return meta


def job_file(owner_id: int, job_id: str) -> tuple[bytes, str] | None:
    meta = job_status(owner_id, job_id)
    if not meta or meta["status"] != "done":
        return None
    data = cache.get(_key(job_id, "file"))
    return (data, meta["filename"]) if data else None


def payload_for_token(token: str) -> dict[str, Any] | None:
    """حمولة صفحة الطباعة برمزها الموقّع: صالح لدقائق ولمهمة قائمة فقط."""
    try:
        job_id = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)["job"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
    return cache.get(_key(job_id, "payload"))
