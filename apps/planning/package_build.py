"""ملف باقة الحصة المضغوط (المرحلة 3 من docs/lesson_package_plan.md): التحضير Word، والعرض، وPDF لكل ورقة، ومفتاح
واحد، وفهرس. يبنيه العامل ويضعه في تخزين الأصول، وبصمته بجانبه: تغيّر التحضير يجعله «قديمًا». لا بيانات طلاب."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.cache import cache

from apps.assets.storage import Storage, StorageError, get_storage
from apps.core.services import record_audit
from apps.papers import pdf
from apps.papers.domain.generators import generator_version
from apps.papers.selectors import print_profile

from . import non_lesson_package, selectors, services
from .domain.calendar_engine import PlanningError
from .domain.non_lesson import NonLessonPrep
from .domain.prep import prep_digest
from .prep_word import prep_docx, prep_filename

ZIP_CONTENT_TYPE = "application/zip"
ZIP_FILE, ZIP_STAMP = "package.zip", "digest"
LOCK_SECONDS = 600
STATE_SECONDS = 3600
BUSY = "الباقة قيد البناء"
FAILED = "تعذّر بناء الباقة"
INDEX_NAME = "فهرس الباقة.txt"
KEY_NAME = "مفتاح الإجابة.pdf"
ZIP_LAYOUT = 2  # يُرفع حين يتغير شكل الملف المضغوط فتصير الباقات المبنية سابقًا «قديمة»


class PackageBusyError(PlanningError):
    """بناء آخر للملف نفسه جارٍ."""


@dataclass(frozen=True)
class PackageView:
    """ما يعرضه التطبيق قبل التنزيل: الأوراق وملاحظات الفهرس، وبصمة ما تُبنى منه."""

    sheets: tuple[str, ...]
    notes: tuple[str, ...]
    signature: str
    other: NonLessonPrep | None = None  # حصة غير الدرس: أوراقها المربوطة


@dataclass(frozen=True)
class Scope:
    owner_id: int
    course: str
    lesson: str
    k: int

    @property
    def target(self) -> str:
        return f"{self.course}/{self.lesson}/{self.k}"

    @property
    def folder(self) -> str:
        raw = json.dumps([self.owner_id, self.course, self.lesson, self.k], ensure_ascii=False)
        return f"packages/{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"

    @property
    def state_key(self) -> str:
        return f"lesson-package-state:{self.folder}"


def view(owner: AbstractBaseUser, course: str, lesson: str, k: int) -> PackageView:
    """باقة الحصة دون كتابة: من تحضير المعلم، أو من أوراق حصة غير الدرس. `PrepNotFoundError` لمجهولة."""
    if selectors.non_lesson_sheet_of(course, lesson, k) is not None:
        return _non_lesson_view(owner, course, lesson, k)
    item = selectors.period_item(course, lesson, k, owner)
    siblings = [p for p in selectors.owner_preps(course, owner) if p.prep.lesson == lesson]
    try:
        deck = services.prepare_deck(course, lesson, k, owner)
    except PlanningError:
        deck = ""  # العرض لا يُبنى بعد (مقاطع غير منشورة): نشرها لاحقًا يجعل الباقة قديمة
    package = selectors.period_package(item, siblings)
    return PackageView(
        tuple(sheet.title for sheet in package.sheets),
        tuple(note.message for note in package.notes),
        _signature([prep_digest(item.prep), print_profile(owner), deck]),
    )


def _entry_name(name: str) -> str:
    """اسم ملف داخل المضغوط يقبله ويندوز: عناوين الأوراق فيها «:» فيتعذر فكها."""
    stem, _, extension = name.rpartition(".")
    return pdf.safe_filename(stem, extension)


def _signature(parts: list) -> str:
    parts = [ZIP_LAYOUT, *parts]
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _non_lesson_view(owner: AbstractBaseUser, course: str, slug: str, k: int) -> PackageView:
    items = selectors.non_lesson_preps(course)
    prep = next(p.prep for p in items if p.prep.slug == slug and p.prep.k == k)
    notes = (prep.missing_paper,) if prep.missing_paper else ()
    if not prep.papers and not notes:
        notes = ("حصة بلا ورقة مولَّدة: الباقة تحضيرها وحده",)
    return PackageView(
        tuple(link.label for link in prep.papers),
        notes,
        _signature([asdict(prep), print_profile(owner), generator_version(course)]),
        prep,
    )


def _deck_file(owner: AbstractBaseUser, scope: Scope, storage: Storage) -> tuple[bytes | None, str]:
    """ملف العرض أو سبب غيابه: الباقة تُسلَّم دونه ويذكر الفهرس السبب."""
    try:
        key = services.build_period_deck_file(scope.course, scope.lesson, scope.k, storage, owner)
        return storage.get(key), ""
    except (PlanningError, StorageError) as error:
        reason = str(error) if isinstance(error, PlanningError) else "تعذّرت قراءته من التخزين"
        return None, f"العرض غير مرفق: {reason}"


def _pdfs(payload: dict) -> list[tuple[str, bytes]]:
    """ملف PDF لكل ورقة ثم ملف المفتاح، بمحرك الطباعة القائم."""
    package = payload["package"]
    out = []
    for order, sheet in enumerate(package["sheets"], start=1):
        one = {**payload, "show_key": False, "package": {**package, "sheets": [sheet], "part": "sheets"}}
        out.append((f"{order}- {sheet['title']}.pdf", pdf.render_payload(one)))
    key = {**payload, "package": {**package, "part": "key"}}
    out.append((KEY_NAME, pdf.render_payload(key)))
    return out


def _lesson_files(
    owner: AbstractBaseUser, scope: Scope, storage: Storage
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """عرض حصة الدرس وأوراقها ومفتاحها، وسبب غياب العرض إن غاب."""
    payload = services.lesson_package_payload(owner, scope.course, scope.lesson, scope.k)
    deck, missing = _deck_file(owner, scope, storage)
    files = [] if deck is None else [(f"العرض {scope.lesson} الحصة {scope.k}.pptx", deck)]
    return files + _pdfs(payload), [missing] if missing else []


def build(scope: Scope, *, storage: Storage | None = None) -> str:
    """يبني الملف المضغوط ويضعه في التخزين ويعيد مفتاحه. idempotent: البصمة نفسها لا تعيد بناءه."""
    storage = storage or get_storage()
    lock = f"lesson-package:{scope.folder}"
    if not cache.add(lock, 1, LOCK_SECONDS):
        raise PackageBusyError(BUSY)
    try:
        owner = get_user_model().objects.get(pk=scope.owner_id)
        current = view(owner, scope.course, scope.lesson, scope.k)
        key, stamp = f"{scope.folder}/{ZIP_FILE}", f"{scope.folder}/{ZIP_STAMP}"
        if _stamp(storage, scope) == current.signature and storage.exists(key):
            return key
        sheet = selectors.teacher_sheet(scope.course, scope.lesson, scope.k, owner).sheet
        files = [
            (prep_filename(sheet), prep_docx(sheet, teacher=owner.get_full_name() or owner.get_username()))
        ]
        if current.other is None:
            more, missing = _lesson_files(owner, scope, storage)
        else:  # لا عرض لحصة غير الدرس
            payloads, missing = non_lesson_package.print_payloads(current.other, print_profile(owner))
            more = [(f"{name}.pdf", pdf.render_payload(payload)) for name, payload in payloads]
        files = [(_entry_name(name), data) for name, data in files + more]
        index = [name for name, _ in files] + list(current.notes) + missing
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in files:
                archive.writestr(name, data)
            archive.writestr(INDEX_NAME, "\r\n".join(index).encode("utf-8-sig"))
        # البصمة تُزال قبل الملف وتُكتب بعده: موت العامل بينهما يعيد البناء
        storage.delete(stamp)
        storage.put(key, buffer.getvalue(), ZIP_CONTENT_TYPE)
        storage.put(stamp, current.signature.encode("ascii"), "text/plain")
    finally:
        cache.delete(lock)
    record_audit(action="package.build", actor=owner, target=scope.target, payload={"files": len(files)})
    return key


def _stamp(storage: Storage, scope: Scope) -> str:
    key = f"{scope.folder}/{ZIP_STAMP}"
    return storage.get(key).decode("ascii") if storage.exists(key) else ""


def state(scope: Scope, signature: str, storage: Storage | None = None) -> tuple[str, str]:
    """(idle | pending | ready | stale | failed، السبب): الجاهز والقديم من التخزين، والجاري والفاشل من الكاش المشترك."""
    status, detail = cache.get(scope.state_key, ("", ""))
    if status == "pending":
        return "pending", BUSY
    if status == "failed":
        return "failed", detail
    storage = storage or get_storage()
    stamp = _stamp(storage, scope)
    if not stamp or not storage.exists(f"{scope.folder}/{ZIP_FILE}"):
        return "idle", ""
    return ("ready" if stamp == signature else "stale"), ""


def start(scope: Scope) -> bool:
    """يعلّم الباقة قيد البناء؛ False حين يكون بناؤها مطلوبًا فلا تُرسل مهمة ثانية."""
    return cache.add(scope.state_key, ("pending", ""), LOCK_SECONDS)


def clear_failure(scope: Scope) -> None:
    if cache.get(scope.state_key, ("", ""))[0] == "failed":
        cache.delete(scope.state_key)


def fail(scope: Scope, detail: str = FAILED) -> None:
    cache.set(scope.state_key, ("failed", detail), STATE_SECONDS)


def run(scope: Scope) -> str:
    """`build` وتسجيل نتيجته: رسالة `PlanningError` تصل المعلم كما هي، وغيرها رسالة عامة."""
    try:
        key = build(scope)
    except PackageBusyError:
        raise
    except PlanningError as error:
        fail(scope, str(error))
        raise
    except Exception:
        fail(scope)
        raise
    cache.delete(scope.state_key)
    return key


def file(scope: Scope, storage: Storage | None = None) -> bytes | None:
    """الملف المكتمل (بصمته بجانبه) بمفتاح يشتقه الخادم وحده؛ القديم يُقدَّم ويعلّمه التطبيق قديمًا."""
    storage = storage or get_storage()
    key = f"{scope.folder}/{ZIP_FILE}"
    if not (_stamp(storage, scope) and storage.exists(key)):
        return None
    return storage.get(key)
