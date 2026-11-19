"""معايير عرض الحصة على ملف PPTX الناتج (`docs/lesson_prep_plan.md`، «معايير العرض»): S7 وS8 وS12، بالمكتبة القياسية وحدها.

المدخل دائمًا ملف ولّده `build_period_pptx` في الخادم، لا ملف يرفعه مستخدم. تقرأ الملف كما سيفتحه المعلم لا النموذج: المقطع بمقاسه على الشريحة وأبعاد صورته الحقيقية (ترويسة PNG)، وكل لون وخط في
الشرائح، وأجزاء الحزمة وعلاقاتها. دور كل شكل من اسمه (`ROLE_*` في `pptx_export.py`). فتح الملف بـ python-pptx نفسه في
الاختبارات (`tests/test_pptx_files.py`)؛ المكتبة تبعية تطوير لا تشغيل.
"""

from __future__ import annotations

import posixpath
import re
import struct
import zipfile
from collections.abc import Iterator
from io import BytesIO
from xml.etree import ElementTree as ET

from .domain.deck import MIN_CLIP_PPI, MIN_CLIP_SHARE, MIN_CONTRAST, PeriodDeck
from .domain.prep_checks import CheckResult, _result
from .pptx_export import (
    BACKGROUND,
    CONTENT_H,
    DECORATIVE,
    EMU_PER_INCH,
    ROLE_CLIP,
    ROLE_TITLE,
    TITLE_FONT,
    TOKENS,
    build_period_pptx,
)

NSMAP = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
EMBED = f"{{{NSMAP['r']}}}embed"
SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class _Package:
    """حزمة PPTX مقروءة: أجزاؤها، وشرائحها بترتيب أرقامها، وعلاقات كل جزء."""

    def __init__(self, data: bytes):
        with zipfile.ZipFile(BytesIO(data)) as z:
            self.broken = z.testzip()
            self.names = z.namelist()
            self.parts = {n: z.read(n) for n in self.names}

    def xml(self, name: str) -> ET.Element:
        # المدخل ملف ولّده build_period_pptx في الخادم نفسه، لا ملف من مستخدم
        return ET.fromstring(self.parts[name])  # noqa: S314

    def slides(self) -> Iterator[tuple[int, str, ET.Element]]:
        numbered = sorted((int(m.group(1)), n) for n in self.parts if (m := SLIDE.match(n)))
        for k, name in numbered:
            yield k, name, self.xml(name)

    def rels(self, name: str) -> dict[str, str]:
        """معرّف العلاقة ← مسار الجزء الهدف داخل الحزمة (للعلاقات الداخلية)."""
        folder, base = posixpath.split(name)
        rels_name = posixpath.join(folder, "_rels", f"{base}.rels")
        if rels_name not in self.parts:
            return {}
        out = {}
        for rel in self.xml(rels_name).findall("rel:Relationship", NSMAP):
            if rel.get("TargetMode") == "External":
                continue
            out[_get(rel, "Id")] = posixpath.normpath(posixpath.join(folder, _get(rel, "Target")))
        return out


def _get(element: ET.Element | None, name: str) -> str:
    """قيمة الخاصية أو نص فارغ إن غاب العنصر أو الخاصية."""
    return "" if element is None else element.get(name, "")


def png_size(data: bytes) -> tuple[int, int] | None:
    """عرض الصورة وارتفاعها من ترويسة IHDR؛ None لما ليس PNG."""
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return (width, height) if width and height else None


def _role(shape: ET.Element) -> str:
    props = shape.find(".//p:cNvPr", NSMAP)
    return _get(props, "name").split(" ")[0]


def _ext(shape: ET.Element) -> tuple[int, int, int, int]:
    off = shape.find(".//a:off", NSMAP)
    ext = shape.find(".//a:ext", NSMAP)
    return (int(_get(off, "x")), int(_get(off, "y")), int(_get(ext, "cx")), int(_get(ext, "cy")))


# ---- S7 ----


def s7_clips(data: bytes) -> CheckResult:
    """ارتفاع كل مقطع معروض 60% من منطقة المحتوى فأكثر، ودقته 150 بكسل لكل بوصة من مقاسه على الشريحة فأكثر."""
    package = _Package(data)
    problems = []
    for k, name, root in package.slides():
        rels = package.rels(name)
        for pic in root.iterfind(".//p:pic", NSMAP):
            if _role(pic) != ROLE_CLIP:
                continue
            _, _, cx, cy = _ext(pic)
            blip = pic.find(".//a:blip", NSMAP)
            size = png_size(package.parts.get(rels.get(_get(blip, EMBED), ""), b""))
            if size is None:
                problems.append(f"الشريحة {k}: صورة المقطع ليست PNG مقروءة")
                continue
            share = cy / CONTENT_H
            if share < MIN_CLIP_SHARE:
                problems.append(f"الشريحة {k}: المقطع {share:.0%} من ارتفاع المحتوى")
            ppi = min(size[0] / (cx / EMU_PER_INCH), size[1] / (cy / EMU_PER_INCH))
            if ppi < MIN_CLIP_PPI:
                problems.append(f"الشريحة {k}: دقة المقطع {ppi:.0f} بكسل لكل بوصة")
    return _result("S7", problems)


# ---- S8 ----


def _luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    """نسبة التباين بتعريف WCAG 2.2."""
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _fill(shape: ET.Element) -> str | None:
    color = shape.find("p:spPr/a:solidFill/a:srgbClr", NSMAP)
    return None if color is None else _get(color, "val").upper()


def _background(shapes: list[ET.Element], index: int, box: tuple[int, int, int, int]) -> str:
    """خلفية الشكل: آخر مستطيل مملوء قبله يحوي مركزه، وإلا خلفية القالب."""
    x, y, cx, cy = box
    center = (x + cx // 2, y + cy // 2)
    for shape in reversed(shapes[:index]):
        fill = _fill(shape)
        if fill is None or shape.find("p:txBody", NSMAP) is not None:
            continue
        sx, sy, scx, scy = _ext(shape)
        if sx <= center[0] <= sx + scx and sy <= center[1] <= sy + scy:
            return fill
    return BACKGROUND


def _run_color(run: ET.Element) -> str | None:
    color = run.find("a:rPr/a:solidFill/a:srgbClr", NSMAP)
    return None if color is None else _get(color, "val").upper()


def s8_identity(data: bytes) -> CheckResult:
    """ألوان الشرائح رموز من tokens.css، والذهبي زخرفة لا نص، والعناوين بخط Cairo، وتباين كل نص وخلفيته 4.5:1 فأكثر."""
    package = _Package(data)
    problems = []
    for k, _, root in package.slides():
        colors = {_get(c, "val").upper() for c in root.iterfind(".//a:srgbClr", NSMAP)}
        problems += [f"الشريحة {k}: اللون {c} ليس من رموز الهوية" for c in sorted(colors - set(TOKENS))]
        tree = root.find("p:cSld/p:spTree", NSMAP)
        shapes = [] if tree is None else list(tree)
        for index, shape in enumerate(shapes):
            if shape.tag == f"{{{NSMAP['p']}}}sp" and shape.find("p:txBody", NSMAP) is not None:
                bg = _fill(shape) or _background(shapes, index, _ext(shape))
                runs = [(r, bg) for r in shape.iterfind(".//a:r", NSMAP)]
            elif shape.tag == f"{{{NSMAP['p']}}}graphicFrame":
                runs = []
                for cell in shape.iterfind(".//a:tc", NSMAP):
                    fill = cell.find("a:tcPr/a:solidFill/a:srgbClr", NSMAP)
                    bg = BACKGROUND if fill is None else _get(fill, "val").upper()
                    runs += [(r, bg) for r in cell.iterfind(".//a:r", NSMAP)]
            else:
                continue
            title = _role(shape) == ROLE_TITLE
            for run, bg in runs:
                fg = _run_color(run)
                text = run.findtext("a:t", "", NSMAP)
                if fg is None:
                    problems.append(f"الشريحة {k}: نص بلا لون صريح «{text[:20]}»")
                    continue
                if fg in DECORATIVE:
                    problems.append(f"الشريحة {k}: نص بلون الزخرفة {fg}")
                ratio = contrast(fg, bg)
                if ratio < MIN_CONTRAST:
                    problems.append(f"الشريحة {k}: تباين {ratio:.1f}:1 للنص «{text[:20]}»")
                if title:
                    fonts = {
                        _get(f, "typeface")
                        for tag in ("a:latin", "a:cs")
                        if (f := run.find(f"a:rPr/{tag}", NSMAP)) is not None
                    }
                    if fonts != {TITLE_FONT}:
                        problems.append(f"الشريحة {k}: العنوان بخط {sorted(fonts)} لا {TITLE_FONT}")
    return _result("S8", problems)


# ---- S12 ----


def _content_types(package: _Package) -> tuple[set[str], set[str]]:
    root = package.xml("[Content_Types].xml")
    defaults = {_get(d, "Extension").lower() for d in root.iterfind("ct:Default", NSMAP)}
    overrides = {_get(o, "PartName").lstrip("/") for o in root.iterfind("ct:Override", NSMAP)}
    return defaults, overrides


def _package_problems(package: _Package) -> list[str]:
    problems = []
    if package.broken is not None:
        return [f"جزء تالف في الأرشيف: {package.broken}"]
    if not package.names or package.names[0] != "[Content_Types].xml":
        problems.append("[Content_Types].xml ليس أول الأرشيف")
    defaults, overrides = _content_types(package)
    for name in package.names:
        if name in overrides or name.rsplit(".", 1)[-1].lower() in defaults:  # «.rels» امتداد لا اسم مخفي
            continue
        problems.append(f"جزء بلا نوع محتوى: {name}")
    problems += [f"نوع محتوى لجزء غائب: {p}" for p in sorted(overrides - set(package.names))]
    for name in package.names:
        if not name.endswith((".xml", ".rels")):
            continue
        try:
            package.xml(name)
        except ET.ParseError as error:
            problems.append(f"{name}: XML غير صالح ({error})")
            continue
        source = name.replace("_rels/", "").removesuffix(".rels") if name.endswith(".rels") else None
        if source is not None and source != "" and source not in package.parts:
            problems.append(f"علاقات لجزء غائب: {name}")
    for name in [n for n in package.names if not n.endswith(".rels")] + [""]:
        for rid, target in package.rels(name).items():
            if target not in package.parts:
                problems.append(f"{name or 'الحزمة'}: العلاقة {rid} إلى جزء غائب {target}")
    return problems


def _empty_placeholders(package: _Package) -> list[str]:
    """عنصر نائب في شريحة أو صفحة ملاحظات بلا نص: يظهر للمعلم «انقر لإضافة نص»."""
    problems = []
    for name in package.names:
        if not re.match(r"^ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml$", name):
            continue
        for shape in package.xml(name).iterfind(".//p:sp", NSMAP):
            if shape.find("p:nvSpPr/p:nvPr/p:ph", NSMAP) is None:
                continue
            text = "".join(t.text or "" for t in shape.iterfind(".//a:t", NSMAP))
            if not text.strip():
                problems.append(f"{name}: عنصر نائب فارغ")
    return problems


def s12_package(data: bytes, deck: PeriodDeck) -> CheckResult:
    """الحزمة سليمة (أنواع المحتوى والعلاقات وXML)، وبلا عنصر نائب فارغ، وحتمية: العرض نفسه يعطي الملف نفسه بايتًا بايت."""
    try:
        package = _Package(data)
    except zipfile.BadZipFile:
        return _result("S12", ["الملف ليس أرشيف ZIP"])
    problems = _package_problems(package) + _empty_placeholders(package)
    slides = sum(1 for _ in package.slides())
    if slides != len(deck.slides):
        problems.append(f"{slides} شريحة في الملف و{len(deck.slides)} في العرض")
    if build_period_pptx(deck) != data:
        problems.append("الملف لا يطابق بناءً جديدًا من العرض نفسه")
    return _result("S12", problems)


def check_pptx(data: bytes, deck: PeriodDeck) -> tuple[CheckResult, ...]:
    """معايير الملف بترتيب رموزها."""
    return (s7_clips(data), s8_identity(data), s12_package(data, deck))
