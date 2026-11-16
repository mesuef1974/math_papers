"""تصدير `Deck` إلى PPTX من اليمين لليسار: كاتب OOXML بـzipfile بلا تبعية جديدة (python-pptx خارج lockfile).

شريحة 16:9 بهوية «أوراق»: العنابي للشريط والعناوين وترويسة الجدول، والذهبي خطًّا زخرفيًا فقط، والحبر الداكن للنص.
الاتجاه RTL على مستوى العرض (`rtl="1"`) والفقرات والجداول. الخط Arial للعربي واللاتيني (متاح على أجهزة المعلمين؛ خط الهوية
لا يُضمَّن في PPTX). المخرج حتمي: طوابع الأرشيف ثابتة فيخرج الملف نفسه من الـ`Deck` نفسه.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from .domain.deck import BulletsSlide, Deck, ExampleSlide, Slide, TableSlide, TitleSlide

WIDTH, HEIGHT = 12192000, 6858000  # 13.333in × 7.5in
BRAND, GOLD, INK, WHITE, SOFT = (
    "8E2433",
    "DB943C",
    "1F2430",
    "FFFFFF",
    "F6EEEF",
)  # BRAND = --color-brand في print.css
FONT = "Arial"
LOCKUP = Path(__file__).resolve().parents[1] / "papers" / "word" / "assets" / "lockup.png"
LOCKUP_RATIO = 2475 / 1024
COPYRIGHT_NAME = "سفيان مسيف"  # نظير COPYRIGHT_* في word/builder.py وutils/brand.ts
COPYRIGHT_PHONE = "55296286"
MARGIN = 600000
BAR_H = 1000000
FOOT_Y = 6330000
FOOT_H = 420000
IMAGE_BOX = (
    WIDTH - MARGIN - 6096000,
    1250000,
    6096000,
    4900000,
)  # نصف عرض الشريطة تقريبًا: صفحة الكتاب صغيرة الدقة

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def fit(width_px: int, height_px: int, box_cx: int, box_cy: int) -> tuple[int, int]:
    """أكبر مقاس داخل الصندوق بنسبة الصورة نفسها (يكبّر أو يصغّر ولا يشوّه)."""
    scale = min(box_cx / width_px, box_cy / height_px)
    return max(1, round(width_px * scale)), max(1, round(height_px * scale))


def _run(text: str, size: int, color: str, bold: bool = False) -> str:
    return (
        f'<a:r><a:rPr lang="ar-SA" sz="{size}" b="{int(bold)}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>'
    )


def _para(text: str, size: int, color: str, bold: bool = False, algn: str = "r", bullet: bool = False) -> str:
    if bullet:
        ppr = (
            f'<a:pPr marL="342900" indent="-342900" algn="{algn}" rtl="1"><a:spcBef><a:spcPts val="600"/></a:spcBef>'
            f'<a:buClr><a:srgbClr val="{BRAND}"/></a:buClr><a:buFont typeface="{FONT}"/><a:buChar char="•"/></a:pPr>'
        )
    else:
        ppr = f'<a:pPr algn="{algn}" rtl="1"><a:buNone/></a:pPr>'
    return f"<a:p>{ppr}{_run(text, size, color, bold)}</a:p>"


@dataclass
class _Canvas:
    """شريحة واحدة قيد البناء: أشكالها ووسائطها (الصورة: اسم الجزء ← بايتات)."""

    shapes: list[str] = field(default_factory=list)
    media: list[tuple[str, bytes]] = field(default_factory=list)
    next_id: int = 2

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def rect(self, x: int, y: int, cx: int, cy: int, fill: str) -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="شكل {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )

    def text(self, x: int, y: int, cx: int, cy: int, paragraphs: list[str], anchor: str = "t") -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="نص {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="91440" rIns="91440" rtlCol="1" anchor="{anchor}">'
            f"<a:normAutofit/></a:bodyPr><a:lstStyle/>{''.join(paragraphs)}</p:txBody></p:sp>"
        )

    def picture(self, png: bytes, x: int, y: int, cx: int, cy: int, descr: str) -> None:
        i = self._id()
        name = f"image{len(self.media) + 1}.png"
        self.media.append((name, png))
        rid = f"rId{len(self.media) + 1}"  # rId1 للتخطيط
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="صورة {i}" descr="{escape(descr, {chr(34): "&quot;"})}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill>'
            f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        )

    def table(
        self, x: int, y: int, cx: int, header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
    ) -> int:
        """جدول RTL: العمود الأول عند اليمين. يُعيد ارتفاعه ليضع المتصل به ما بعده."""
        i = self._id()
        row_h = 520000
        col_w = cx // len(header)
        grid = "".join(f'<a:gridCol w="{col_w}"/>' for _ in header)

        def cell(value: str, head: bool, shade: bool) -> str:
            color, fill = (WHITE, BRAND) if head else (INK, SOFT if shade else WHITE)
            return (
                f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{_para(value, 1800, color, bold=head)}</a:txBody>"
                f'<a:tcPr anchor="ctr"><a:lnB w="9525"><a:solidFill><a:srgbClr val="{GOLD}"/></a:solidFill></a:lnB>'
                f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>'
            )

        body = f'<a:tr h="{row_h}">{"".join(cell(h, True, False) for h in header)}</a:tr>' + "".join(
            f'<a:tr h="{row_h}">{"".join(cell(v, False, n % 2 == 1) for v in row)}</a:tr>'
            for n, row in enumerate(rows)
        )
        height = row_h * (len(rows) + 1)
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="جدول {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{height}"/></p:xfrm><a:graphic>'
            f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr rtl="1" firstRow="1"/>'
            f"<a:tblGrid>{grid}</a:tblGrid>{body}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
        )
        return height

    def xml(self) -> str:
        return (
            f'{XML}<p:sld {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f"{''.join(self.shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
        )


def _footer(c: _Canvas, lockup: bytes) -> None:
    c.rect(MARGIN, FOOT_Y - 30000, WIDTH - 2 * MARGIN, 12000, GOLD)
    lock_cy = FOOT_H - 60000
    lock_cx = round(lock_cy * LOCKUP_RATIO)
    c.picture(lockup, WIDTH - MARGIN - lock_cx, FOOT_Y + 20000, lock_cx, lock_cy, "أوراق")
    c.text(
        MARGIN,
        FOOT_Y,
        5000000,
        FOOT_H,
        [_para(f"© {COPYRIGHT_NAME}  {COPYRIGHT_PHONE}", 1100, INK, algn="l")],
        anchor="ctr",
    )


def _title_bar(c: _Canvas, title: str) -> None:
    c.rect(0, 0, WIDTH, BAR_H, BRAND)
    c.text(MARGIN, 0, WIDTH - 2 * MARGIN, BAR_H, [_para(title, 3200, WHITE, bold=True)], anchor="ctr")


def _render(slide: Slide, lockup: bytes) -> _Canvas:
    c = _Canvas()
    inner_w = WIDTH - 2 * MARGIN
    if isinstance(slide, TitleSlide):
        c.rect(0, 0, WIDTH, 4000000, BRAND)
        c.text(
            MARGIN,
            900000,
            inner_w,
            2200000,
            [_para(slide.title, 4800, WHITE, bold=True, algn="ctr")],
            anchor="ctr",
        )
        c.rect(WIDTH // 2 - 900000, 4000000, 1800000, 36000, GOLD)
        c.text(MARGIN, 4300000, inner_w, 800000, [_para(slide.subtitle, 2400, INK, algn="ctr")], anchor="ctr")
        lock_cy = 700000
        lock_cx = round(lock_cy * LOCKUP_RATIO)
        c.picture(lockup, WIDTH - MARGIN - lock_cx, HEIGHT - 400000 - lock_cy, lock_cx, lock_cy, "أوراق")
        return c
    _title_bar(c, slide.title)
    _footer(c, lockup)
    body_y = BAR_H + 350000
    if isinstance(slide, BulletsSlide):
        c.text(
            MARGIN,
            body_y,
            inner_w,
            FOOT_Y - body_y - 150000,
            [_para(b, 2600, INK, bullet=True) for b in slide.bullets],
        )
    elif isinstance(slide, TableSlide):
        height = c.table(MARGIN, body_y, inner_w, slide.header, slide.rows)
        if slide.footnote:
            c.text(MARGIN, body_y + height + 120000, inner_w, 450000, [_para(slide.footnote, 1600, INK)])
    elif isinstance(slide, ExampleSlide):
        bx, by, bw, bh = IMAGE_BOX
        cx, cy = fit(slide.clip.width_px, slide.clip.height_px, bw, bh)
        c.picture(slide.clip.png, bx + bw - cx, by + (bh - cy) // 2, cx, cy, slide.title)
        if slide.notes:
            c.text(MARGIN, by, bx - 2 * MARGIN, bh, [_para(n, 2000, INK, bullet=True) for n in slide.notes])
    return c


def _theme() -> str:
    colors = {
        "dk1": INK,
        "lt1": WHITE,
        "dk2": BRAND,
        "lt2": SOFT,
        "accent1": BRAND,
        "accent2": GOLD,
        "accent3": "5B6577",
        "accent4": "A8505D",
        "accent5": "E6B979",
        "accent6": "3F4756",
        "hlink": BRAND,
        "folHlink": "5B6577",
    }
    scheme = "".join(f'<a:{k}><a:srgbClr val="{v}"/></a:{k}>' for k, v in colors.items())
    fills = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3
    lines = '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' * 3
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    return (
        f'{XML}<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="أوراق"><a:themeElements>'
        f'<a:clrScheme name="أوراق">{scheme}</a:clrScheme><a:fontScheme name="أوراق">'
        f'<a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface="{FONT}"/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface="{FONT}"/></a:minorFont></a:fontScheme>'
        f'<a:fmtScheme name="أوراق"><a:fillStyleLst>{fills}</a:fillStyleLst><a:lnStyleLst>{lines}</a:lnStyleLst>'
        f"<a:effectStyleLst>{effects}</a:effectStyleLst><a:bgFillStyleLst>{fills}</a:bgFillStyleLst></a:fmtScheme>"
        "</a:themeElements></a:theme>"
    )


def _rels(items: list[tuple[str, str, str]]) -> str:
    body = "".join(f'<Relationship Id="{i}" Type="{t}" Target="{target}"/>' for i, t, target in items)
    return f'{XML}<Relationships xmlns="{REL_NS}">{body}</Relationships>'


EMPTY_TREE = (
    '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
    '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree>'
)
MASTER = (
    f'{XML}<p:sldMaster {NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{WHITE}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
    f'{EMPTY_TREE}</p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
)
LAYOUT = (
    f'{XML}<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="فارغ">{EMPTY_TREE}</p:cSld>'
    "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
)


def build_pptx(deck: Deck) -> bytes:
    lockup = LOCKUP.read_bytes()
    canvases = [_render(s, lockup) for s in deck.slides]
    n = len(canvases)
    media: dict[str, bytes] = {}
    for k, c in enumerate(canvases, start=1):
        for name, data in c.media:
            media[f"slide{k}_{name}"] = data

    overrides = [
        ("/ppt/presentation.xml", "presentation.main"),
        ("/ppt/slideMasters/slideMaster1.xml", "slideMaster"),
        ("/ppt/slideLayouts/slideLayout1.xml", "slideLayout"),
        ("/ppt/theme/theme1.xml", "theme"),
        *((f"/ppt/slides/slide{k}.xml", "slide") for k in range(1, n + 1)),
    ]
    ct_main = "application/vnd.openxmlformats-officedocument.presentationml."
    kinds = {
        "presentation.main": ct_main + "presentation.main+xml",
        "slideMaster": ct_main + "slideMaster+xml",
        "slideLayout": ct_main + "slideLayout+xml",
        "slide": ct_main + "slide+xml",
        "theme": "application/vnd.openxmlformats-officedocument.theme+xml",
    }
    content_types = (
        f'{XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
        + "".join(f'<Override PartName="{p}" ContentType="{kinds[k]}"/>' for p, k in overrides)
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )
    title = next((s.title for s in deck.slides if isinstance(s, TitleSlide)), deck.lesson)
    core = (
        f'{XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>أوراق</dc:creator>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created></cp:coreProperties>'
    )
    presentation = (
        f'{XML}<p:presentation {NS} rtl="1" saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        "</p:sldMasterIdLst><p:sldIdLst>"
        + "".join(f'<p:sldId id="{255 + k}" r:id="rId{k + 2}"/>' for k in range(1, n + 1))
        + f'</p:sldIdLst><p:sldSz cx="{WIDTH}" cy="{HEIGHT}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    )
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": _rels(
            [
                ("rId1", f"{REL}/officeDocument", "ppt/presentation.xml"),
                (
                    "rId2",
                    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
                    "docProps/core.xml",
                ),
            ]
        ),
        "docProps/core.xml": core,
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": _rels(
            [("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml")]
            + [(f"rId{k + 2}", f"{REL}/slide", f"slides/slide{k}.xml") for k in range(1, n + 1)]
        ),
        "ppt/slideMasters/slideMaster1.xml": MASTER,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _rels(
            [
                ("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", f"{REL}/theme", "../theme/theme1.xml"),
            ]
        ),
        "ppt/slideLayouts/slideLayout1.xml": LAYOUT,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _rels(
            [("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml")]
        ),
        "ppt/theme/theme1.xml": _theme(),
    }
    for k, c in enumerate(canvases, start=1):
        parts[f"ppt/slides/slide{k}.xml"] = c.xml()
        parts[f"ppt/slides/_rels/slide{k}.xml.rels"] = _rels(
            [("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml")]
            + [
                (f"rId{j + 2}", f"{REL}/image", f"../media/slide{k}_{name}")
                for j, (name, _) in enumerate(c.media)
            ]
        )
    for name, data in media.items():
        parts[f"ppt/media/{name}"] = data

    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():  # [Content_Types].xml أولًا كما تشترط OPC عادةً
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data.encode("utf-8") if isinstance(data, str) else data)
    return out.getvalue()
