"""معايير عرض الحصة على ملف PPTX الناتج (`docs/lesson_prep_plan.md`، «معايير العرض»): S7 وS8 وS12، وكلها حاجبة.

تقرأ الملف نفسه لا النموذج، فتشهد على ما سيراه المعلم: هندسة مقطع المثال ودقته، وألوان الأشكال والنص وخط العناوين وتباينها،
وسلامة الحزمة (كل جزء يُقرأ وكل علاقة تصل ولكل جزء نوع ولا عنصر نائب فارغ) وحتميتها. python-pptx خارج lockfile، فالفتح
هنا قراءة OPC بـzipfile وElementTree كما يفعل أي قارئ.
"""

from __future__ import annotations

import posixpath
import struct
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

from .domain.prep_checks import CheckResult, _result
from .pptx_export import (
    BRAND,
    CLIP_PREFIX,
    CONTENT_BOX,
    EMU_PER_INCH,
    GOLD,
    PALETTE,
    TITLE_FONT,
    WHITE,
)

MIN_CLIP_SHARE = 0.6  # ارتفاع المقطع من ارتفاع منطقة المحتوى
MIN_CLIP_DPI = 150  # بكسل لكل بوصة عند العرض بملء الشاشة
MIN_CONTRAST = 4.5

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"a": A, "p": P, "r": R}


def _xml(data: bytes) -> ET.Element:
    """الملف المفحوص من بناء `build_period_pptx` نفسه لا من مستخدم، وأجزاؤه بلا DTD ولا كيانات."""
    return ET.fromstring(data)  # noqa: S314


def _slide_names(z: zipfile.ZipFile) -> list[str]:
    names = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
    return sorted(names, key=lambda n: int(n.removeprefix("ppt/slides/slide").removesuffix(".xml")))


def _rels(z: zipfile.ZipFile, part: str) -> dict[str, str]:
    """علاقات الجزء: المعرّف ← مسار الهدف في الحزمة."""
    folder, name = posixpath.split(part)
    rels_name = posixpath.join(folder, "_rels", f"{name}.rels")
    if rels_name not in z.namelist():
        return {}
    root = _xml(z.read(rels_name))
    out = {}
    for rel in root.findall(f"{{{PKG}}}Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        out[rel.get("Id")] = posixpath.normpath(posixpath.join(folder, rel.get("Target")))
    return out


def png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("ليست PNG")
    return struct.unpack(">II", data[16:24])


def _box(element: ET.Element) -> tuple[int, int, int, int] | None:
    off = element.find(".//a:off", NS)
    ext = element.find(".//a:ext", NS)
    if off is None or ext is None:
        return None
    return int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))


def s7_clip_clarity(data: bytes) -> CheckResult:
    """وضوح المقطع: ارتفاعه المعروض 60% من منطقة المحتوى فأكثر، ودقته 150 بكسل لكل بوصة فأكثر بملء الشاشة."""
    problems = []
    content_cy = CONTENT_BOX[3]
    with zipfile.ZipFile(BytesIO(data)) as z:
        for k, name in enumerate(_slide_names(z), 1):
            rels = _rels(z, name)
            root = _xml(z.read(name))
            for pic in root.iter(f"{{{P}}}pic"):
                if not pic.find(".//p:cNvPr", NS).get("name", "").startswith(CLIP_PREFIX):
                    continue
                _, _, cx, cy = _box(pic.find("p:spPr", NS))
                if cy < MIN_CLIP_SHARE * content_cy:
                    problems.append(f"الشريحة {k}: المقطع {cy / content_cy:.0%} من ارتفاع منطقة المحتوى")
                blip = pic.find(".//a:blip", NS).get(f"{{{R}}}embed")
                width_px, height_px = png_size(z.read(rels[blip]))
                dpi = min(width_px / (cx / EMU_PER_INCH), height_px / (cy / EMU_PER_INCH))
                if dpi < MIN_CLIP_DPI:
                    problems.append(f"الشريحة {k}: دقة المقطع {dpi:.0f} بكسل لكل بوصة")
    return _result("S7", problems)


def _luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    x, y, cx, cy = inner
    ox, oy, ocx, ocy = outer
    return ox <= x and oy <= y and x + cx <= ox + ocx and y + cy <= oy + ocy


def s8_identity(data: bytes) -> CheckResult:
    """الهوية: كل لون من ألوان «أوراق»، والذهبي للتزيين لا للنص، والعناوين بخط Cairo، وتباين كل نص وخلفيته 4.5:1 فأكثر
    (الخلفية العنابي إن وقع النص داخل مستطيل عنابي، وإلا الأبيض)."""
    problems = []
    with zipfile.ZipFile(BytesIO(data)) as z:
        for k, name in enumerate(_slide_names(z), 1):
            root = _xml(z.read(name))
            foreign = sorted({c.get("val") for c in root.iter(f"{{{A}}}srgbClr")} - PALETTE)
            if foreign:
                problems.append(f"الشريحة {k}: ألوان من خارج الهوية {foreign}")
            shapes = list(root.iter(f"{{{P}}}sp"))
            brand_boxes = [
                _box(s.find("p:spPr", NS))
                for s in shapes
                if s.find("p:txBody", NS) is None
                and (fill := s.find("p:spPr/a:solidFill/a:srgbClr", NS)) is not None
                and fill.get("val") == BRAND
            ]
            for s in shapes:
                body = s.find("p:txBody", NS)
                if body is None:
                    continue
                box = _box(s.find("p:spPr", NS))
                background = BRAND if box and any(_inside(box, b) for b in brand_boxes if b) else WHITE
                is_title = s.find("p:nvSpPr/p:cNvPr", NS).get("name", "").startswith("عنوان")
                for run in body.iter(f"{{{A}}}r"):
                    color = run.find("a:rPr/a:solidFill/a:srgbClr", NS)
                    if color is None:
                        problems.append(f"الشريحة {k}: نص بلا لون صريح")
                        continue
                    value = color.get("val")
                    if value == GOLD:
                        problems.append(f"الشريحة {k}: الذهبي لون نص")
                    if contrast(value, background) < MIN_CONTRAST:
                        problems.append(f"الشريحة {k}: تباين {value} على {background} دون {MIN_CONTRAST}:1")
                    if is_title and run.find("a:rPr/a:latin", NS).get("typeface") != TITLE_FONT:
                        problems.append(f"الشريحة {k}: العنوان بغير خط {TITLE_FONT}")
    return _result("S8", sorted(set(problems), key=problems.index))


def _content_type(types: ET.Element, part: str) -> str | None:
    for o in types.findall(f"{{{CT}}}Override"):
        if o.get("PartName") == "/" + part:
            return o.get("ContentType")
    ext = part.rsplit(".", 1)[-1]
    for d in types.findall(f"{{{CT}}}Default"):
        if d.get("Extension") == ext:
            return d.get("ContentType")
    return None


def s12_package(data: bytes, rebuilt: bytes) -> CheckResult:
    """الملف يُفتح: كل جزء XML يُقرأ، ولكل جزء نوع، وكل علاقة داخلية تصل إلى جزء موجود، والشرائح المعلنة هي الموجودة، ولا
    عنصر نائب فارغ في شريحة أو صفحة ملاحظات؛ وحتمي: بناؤه ثانيةً من المدخل نفسه يعطي الملف نفسه بايتًا بايت."""
    problems = []
    if data != rebuilt:
        problems.append("الملف غير حتمي: بناؤه ثانيةً أعطى بايتات مختلفة")
    try:
        z = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        return _result("S12", [*problems, "الملف ليس حزمة ZIP"])
    with z:
        names = set(z.namelist())
        if "[Content_Types].xml" not in names:
            return _result("S12", [*problems, "لا [Content_Types].xml"])
        types = _xml(z.read("[Content_Types].xml"))
        for o in types.findall(f"{{{CT}}}Override"):
            if o.get("PartName").lstrip("/") not in names:
                problems.append(f"نوع لجزء غير موجود {o.get('PartName')}")
        for name in sorted(names - {"[Content_Types].xml"}):
            if _content_type(types, name) is None:
                problems.append(f"جزء بلا نوع {name}")
            if name.endswith((".xml", ".rels")):
                try:
                    _xml(z.read(name))
                except ET.ParseError:
                    problems.append(f"جزء لا يُقرأ {name}")
                    continue
            if name.endswith(".rels"):
                folder = posixpath.dirname(posixpath.dirname(name))
                for rel in _xml(z.read(name)).findall(f"{{{PKG}}}Relationship"):
                    if rel.get("TargetMode") == "External":
                        continue
                    target = posixpath.normpath(posixpath.join(folder, rel.get("Target")))
                    if target not in names:
                        problems.append(f"علاقة إلى جزء غير موجود {name} ← {rel.get('Target')}")
        if problems:
            return _result("S12", problems)
        presentation = _xml(z.read("ppt/presentation.xml"))
        listed = [
            _rels(z, "ppt/presentation.xml").get(s.get(f"{{{R}}}id"))
            for s in presentation.iter(f"{{{P}}}sldId")
        ]
        if listed != _slide_names(z):
            problems.append("الشرائح المعلنة في العرض لا تطابق أجزاء الشرائح")
        for name in sorted(
            n for n in names if n.startswith(("ppt/slides/slide", "ppt/notesSlides/notesSlide"))
        ):
            if not name.endswith(".xml"):
                continue
            for sp in _xml(z.read(name)).iter(f"{{{P}}}sp"):
                if sp.find("p:nvSpPr/p:nvPr/p:ph", NS) is None:
                    continue
                if not "".join(t.text or "" for t in sp.iter(f"{{{A}}}t")).strip():
                    problems.append(f"عنصر نائب فارغ في {name}")
    return _result("S12", problems)


def check_pptx(data: bytes, rebuilt: bytes) -> tuple[CheckResult, ...]:
    """معايير الملف بترتيب رموزها."""
    return (s7_clip_clarity(data), s8_identity(data), s12_package(data, rebuilt))
