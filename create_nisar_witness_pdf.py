from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable, Flowable, ListFlowable, ListItem
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = OUT_DIR / "NISAR_WITNESS_95_Plus_Winning_Blueprint.pdf"


# Palette
NAVY = HexColor("#071A2F")
NAVY_2 = HexColor("#102A43")
BLUE = HexColor("#1D8CF8")
CYAN = HexColor("#32D6C5")
TEAL = HexColor("#0F9D8B")
GOLD = HexColor("#FFCC66")
ORANGE = HexColor("#FF8A4C")
RED = HexColor("#E45756")
GREEN = HexColor("#40C98A")
INK = HexColor("#132238")
MID = HexColor("#526579")
PALE = HexColor("#EAF2F8")
PALE_BLUE = HexColor("#E8F4FF")
PALE_GREEN = HexColor("#EAF9F3")
PALE_GOLD = HexColor("#FFF5DB")
PALE_RED = HexColor("#FDEEEE")
LINE_GREY = HexColor("#D4DEE8")
WHITE = colors.white


def register_fonts():
    candidates = [
        ("Inter", "/System/Library/Fonts/Supplemental/Arial.ttf"),
        ("Inter-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("Inter-Italic", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
        ("Mono", "/System/Library/Fonts/Supplemental/Courier New.ttf"),
    ]
    for name, path in candidates:
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont(name, path))


register_fonts()
FONT = "Inter" if "Inter" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
FONT_B = "Inter-Bold" if "Inter-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
FONT_I = "Inter-Italic" if "Inter-Italic" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Oblique"
FONT_M = "Mono" if "Mono" in pdfmetrics.getRegisteredFontNames() else "Courier"


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverKicker", fontName=FONT_B, fontSize=9, leading=12,
    textColor=CYAN, alignment=TA_CENTER, spaceAfter=10, tracking=1.4
))
styles.add(ParagraphStyle(
    name="CoverTitle", fontName=FONT_B, fontSize=34, leading=36,
    textColor=WHITE, alignment=TA_CENTER, spaceAfter=12
))
styles.add(ParagraphStyle(
    name="CoverSub", fontName=FONT, fontSize=14, leading=19,
    textColor=HexColor("#DCE9F5"), alignment=TA_CENTER, spaceAfter=18
))
styles.add(ParagraphStyle(
    name="CoverQuote", fontName=FONT_B, fontSize=15, leading=21,
    textColor=NAVY, alignment=TA_CENTER, backColor=GOLD,
    borderPadding=12, borderRadius=6, spaceBefore=8, spaceAfter=16
))
styles.add(ParagraphStyle(
    name="H1x", fontName=FONT_B, fontSize=23, leading=27,
    textColor=NAVY, spaceBefore=2, spaceAfter=12
))
styles.add(ParagraphStyle(
    name="H2x", fontName=FONT_B, fontSize=15, leading=19,
    textColor=NAVY_2, spaceBefore=12, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="H3x", fontName=FONT_B, fontSize=11.5, leading=15,
    textColor=TEAL, spaceBefore=8, spaceAfter=4
))
styles.add(ParagraphStyle(
    name="BodyX", fontName=FONT, fontSize=9.3, leading=13.5,
    textColor=INK, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="BodySmall", fontName=FONT, fontSize=8.1, leading=11.4,
    textColor=INK, spaceAfter=4
))
styles.add(ParagraphStyle(
    name="Caption", fontName=FONT, fontSize=7.5, leading=10,
    textColor=MID, spaceBefore=3, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="Callout", fontName=FONT_B, fontSize=11.5, leading=16,
    textColor=NAVY, backColor=PALE_GOLD, borderColor=GOLD,
    borderWidth=1, borderPadding=10, borderRadius=5, spaceBefore=6, spaceAfter=10
))
styles.add(ParagraphStyle(
    name="Evidence", fontName=FONT, fontSize=8.5, leading=12.5,
    textColor=INK, backColor=PALE_BLUE, borderColor=BLUE,
    borderWidth=0.7, borderPadding=8, borderRadius=4, spaceBefore=5, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="Warning", fontName=FONT, fontSize=8.5, leading=12.5,
    textColor=INK, backColor=PALE_RED, borderColor=RED,
    borderWidth=0.7, borderPadding=8, borderRadius=4, spaceBefore=5, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="TableHead", fontName=FONT_B, fontSize=7.5, leading=9,
    textColor=WHITE, alignment=TA_LEFT
))
styles.add(ParagraphStyle(
    name="TableCell", fontName=FONT, fontSize=7.1, leading=9.2,
    textColor=INK
))
styles.add(ParagraphStyle(
    name="TableCellBold", fontName=FONT_B, fontSize=7.1, leading=9.2,
    textColor=INK
))
styles.add(ParagraphStyle(
    name="Metric", fontName=FONT_B, fontSize=22, leading=24,
    textColor=BLUE, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    name="MetricLabel", fontName=FONT, fontSize=7.2, leading=9,
    textColor=MID, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    name="Source", fontName=FONT, fontSize=7.4, leading=10,
    textColor=INK, spaceAfter=4
))


def P(text, style="BodyX"):
    return Paragraph(text, styles[style])


def bullets(items, level=0, small=False):
    st = styles["BodySmall" if small else "BodyX"]
    return ListFlowable(
        [ListItem(Paragraph(x, st), leftIndent=10) for x in items],
        bulletType="bullet", start="circle", leftIndent=18 + level * 8,
        bulletFontName=FONT_B, bulletFontSize=6.5, bulletColor=TEAL,
        spaceAfter=6
    )


class SectionBand(Flowable):
    def __init__(self, number, title, subtitle=None):
        super().__init__()
        self.number = number
        self.title = title
        self.subtitle = subtitle
        self.height = 55 if subtitle else 43

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 4, self.width, self.height - 8, 7, stroke=0, fill=1)
        c.setFillColor(CYAN)
        c.circle(21, self.height / 2, 13, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont(FONT_B, 10)
        c.drawCentredString(21, self.height / 2 - 3.5, str(self.number))
        c.setFillColor(WHITE)
        c.setFont(FONT_B, 16)
        c.drawString(44, self.height / 2 + (3 if self.subtitle else -5), self.title)
        if self.subtitle:
            c.setFillColor(HexColor("#C7D8E8"))
            c.setFont(FONT, 8)
            c.drawString(44, self.height / 2 - 11, self.subtitle)


class ScoreBar(Flowable):
    def __init__(self, score, label="Conditional finished score", color=BLUE):
        super().__init__()
        self.score = score
        self.label = label
        self.color = color
        self.height = 54

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        x, y, h = 0, 15, 14
        c.setFillColor(PALE)
        c.roundRect(x, y, self.width, h, 7, stroke=0, fill=1)
        c.setFillColor(self.color)
        c.roundRect(x, y, self.width * self.score / 100, h, 7, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont(FONT_B, 24)
        c.drawRightString(self.width, 34, f"{self.score:.1f}/100")
        c.setFillColor(MID)
        c.setFont(FONT, 8)
        c.drawString(0, 36, self.label)
        for mark in [80, 90, 95, 100]:
            px = self.width * mark / 100
            c.setStrokeColor(WHITE if mark < self.score else LINE_GREY)
            c.line(px, y, px, y + h)
            c.setFillColor(MID)
            c.setFont(FONT, 6.3)
            c.drawCentredString(px, 4, str(mark))


def metric_cards(metrics):
    cells = []
    for value, label in metrics:
        cells.append([P(value, "Metric"), P(label, "MetricLabel")])
    # transpose into two rows
    data = [[c[0] for c in cells], [c[1] for c in cells]]
    t = Table(data, colWidths=[6.9 * inch / len(metrics)] * len(metrics), rowHeights=[0.34 * inch, 0.36 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, HexColor("#BBDDF8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def standard_table(headers, rows, widths, font_size=7.1, repeat=1, header_bg=NAVY_2):
    data = [[P(h, "TableHead") for h in headers]]
    for row in rows:
        data.append([
            item if isinstance(item, Flowable) else P(str(item), "TableCell")
            for item in row
        ])
    t = Table(data, colWidths=widths, repeatRows=repeat, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F6F9FC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def architecture_drawing():
    d = Drawing(500, 250)
    boxes = [
        (8, 170, 106, 55, "NASA NISAR", "Level-2 data\nand metadata", BLUE),
        (142, 170, 106, 55, "Evidence prep", "Small AOI, layers,\ncontrol region", TEAL),
        (276, 170, 106, 55, "Rule engine", "Comparability, quality,\nsensitivity", ORANGE),
        (410, 170, 82, 55, "Verdict", "Supported /\nambiguous", GREEN),
        (142, 65, 106, 55, "Evidence bundle", "Raster tiles +\nversioned JSON", CYAN),
        (276, 65, 106, 55, "Judge UI", "Map + Challenge\nthis claim", GOLD),
        (410, 65, 82, 55, "Record", "Exportable\nevidence card", BLUE),
    ]
    for x, y, w, h, title, sub, color in boxes:
        d.add(Rect(x, y, w, h, rx=7, ry=7, fillColor=HexColor("#F8FBFD"), strokeColor=color, strokeWidth=1.6))
        d.add(Rect(x, y + h - 12, w, 12, rx=7, ry=7, fillColor=color, strokeColor=color))
        d.add(String(x + 7, y + h - 9, title, fontName=FONT_B, fontSize=7.5, fillColor=WHITE))
        for i, line in enumerate(sub.split("\n")):
            d.add(String(x + 7, y + h - 27 - i * 10, line, fontName=FONT, fontSize=7, fillColor=INK))
    arrows = [
        (114, 198, 142, 198), (248, 198, 276, 198), (382, 198, 410, 198),
        (195, 170, 195, 120), (248, 93, 276, 93), (382, 93, 410, 93),
        (329, 170, 329, 120)
    ]
    for x1, y1, x2, y2 in arrows:
        d.add(Line(x1, y1, x2, y2, strokeColor=MID, strokeWidth=1.2))
        if x2 > x1:
            d.add(Polygon([x2, y2, x2 - 5, y2 + 3, x2 - 5, y2 - 3], fillColor=MID, strokeColor=MID))
        elif y2 < y1:
            d.add(Polygon([x2, y2, x2 - 3, y2 + 5, x2 + 3, y2 + 5], fillColor=MID, strokeColor=MID))
    d.add(String(8, 235, "Thin, deterministic, offline-first architecture", fontName=FONT_B, fontSize=11, fillColor=NAVY))
    d.add(String(8, 14, "AI is outside the verdict path. It may paraphrase a completed evidence record, but it cannot score the claim.", fontName=FONT_I, fontSize=7.3, fillColor=MID))
    return d


def evidence_ladder_drawing():
    d = Drawing(500, 270)
    labels = [
        ("1", "Comparable products?", "Maturity, release, mode, orbit, geometry", BLUE),
        ("2", "Valid pixels?", "Nodata, water, shadow/layover, quality masks", TEAL),
        ("3", "Signal survives?", "Threshold sensitivity and second channel", ORANGE),
        ("4", "Control stable?", "Nearby no-change region behaves as expected", GOLD),
        ("5", "Interpretation supported?", "Independent source; cause stays separate", GREEN),
        ("6", "Reproducible record", "Identifiers, rules, thresholds, limits", NAVY_2),
    ]
    y = 230
    for n, title, detail, color in labels:
        d.add(Circle(25, y + 5, 14, fillColor=color, strokeColor=color))
        d.add(String(25, y + 1, n, textAnchor="middle", fontName=FONT_B, fontSize=10, fillColor=WHITE))
        d.add(Rect(50, y - 13, 430, 36, rx=6, ry=6, fillColor=HexColor("#F7FAFC"), strokeColor=color, strokeWidth=1.1))
        d.add(String(62, y + 7, title, fontName=FONT_B, fontSize=9, fillColor=NAVY))
        d.add(String(230, y + 7, detail, fontName=FONT, fontSize=7.4, fillColor=MID))
        if n != "6":
            d.add(Line(25, y - 9, 25, y - 25, strokeColor=LINE_GREY, strokeWidth=2))
        y -= 42
    return d


def ui_wireframe():
    d = Drawing(500, 280)
    d.add(Rect(5, 5, 490, 265, rx=8, ry=8, fillColor=HexColor("#F5F8FB"), strokeColor=NAVY, strokeWidth=1.5))
    d.add(Rect(5, 238, 490, 32, rx=8, ry=8, fillColor=NAVY, strokeColor=NAVY))
    d.add(String(18, 249, "NISAR WITNESS", fontName=FONT_B, fontSize=10, fillColor=WHITE))
    d.add(String(390, 249, "Evidence record  |  Methods", fontName=FONT, fontSize=7, fillColor=HexColor("#C7D8E8")))
    # Map
    d.add(Rect(18, 50, 290, 176, rx=5, ry=5, fillColor=HexColor("#DDEAF2"), strokeColor=LINE_GREY))
    for i in range(7):
        d.add(Line(25 + i * 43, 50, 10 + i * 50, 226, strokeColor=HexColor("#C0D2DF"), strokeWidth=0.6))
    for i in range(4):
        d.add(Line(18, 75 + i * 40, 308, 67 + i * 43, strokeColor=HexColor("#C0D2DF"), strokeWidth=0.6))
    d.add(Polygon([105, 100, 155, 118, 180, 88, 220, 120, 210, 166, 142, 174, 92, 142], fillColor=HexColor("#FF9E7A"), strokeColor=RED, fillOpacity=0.65))
    d.add(Rect(30, 190, 105, 24, rx=12, ry=12, fillColor=WHITE, strokeColor=LINE_GREY))
    d.add(String(42, 198, "Before  |  After", fontName=FONT_B, fontSize=7, fillColor=NAVY))
    # Right card
    d.add(Rect(320, 50, 160, 176, rx=5, ry=5, fillColor=WHITE, strokeColor=LINE_GREY))
    d.add(String(334, 208, "CLAIM", fontName=FONT_B, fontSize=7, fillColor=MID))
    d.add(String(334, 193, "Surface response changed", fontName=FONT_B, fontSize=9, fillColor=NAVY))
    d.add(Rect(334, 154, 132, 26, rx=13, ry=13, fillColor=BLUE, strokeColor=BLUE))
    d.add(String(400, 164, "CHALLENGE THIS CLAIM", textAnchor="middle", fontName=FONT_B, fontSize=7, fillColor=WHITE))
    checks = [("Products comparable", GREEN), ("Quality mask clear", GREEN), ("Control stable", GREEN), ("Cause verified", ORANGE)]
    yy = 135
    for label, color in checks:
        d.add(Circle(339, yy + 2, 4, fillColor=color, strokeColor=color))
        d.add(String(349, yy, label, fontName=FONT, fontSize=7, fillColor=INK))
        yy -= 19
    d.add(Rect(334, 61, 132, 24, rx=5, ry=5, fillColor=PALE_GOLD, strokeColor=GOLD))
    d.add(String(400, 70, "VERDICT: AMBIGUOUS", textAnchor="middle", fontName=FONT_B, fontSize=7.5, fillColor=NAVY))
    d.add(String(18, 24, "One screen. One claim. One decisive interaction. Evidence appears next to the map, not buried in a methods page.", fontName=FONT_I, fontSize=7.5, fillColor=MID))
    return d


def timeline_drawing():
    d = Drawing(500, 175)
    blocks = [
        (0, 3, "Gate", BLUE), (3, 8, "One result", TEAL), (8, 14, "Evidence", ORANGE),
        (14, 20, "Validate", GOLD), (20, 27, "Polish", GREEN), (27, 35, "Pitch", NAVY_2), (35, 39, "Submit", RED)
    ]
    x0, y, total_w = 18, 85, 465
    d.add(String(18, 145, "39-hour execution spine", fontName=FONT_B, fontSize=12, fillColor=NAVY))
    d.add(String(18, 132, "A vertical slice is complete by hour 8. No new features after hour 31.", fontName=FONT, fontSize=7.8, fillColor=MID))
    for start, end, label, color in blocks:
        x = x0 + total_w * start / 39
        w = total_w * (end - start) / 39
        d.add(Rect(x, y, w - 2, 32, rx=4, ry=4, fillColor=color, strokeColor=color))
        d.add(String(x + (w - 2) / 2, y + 12, label, textAnchor="middle", fontName=FONT_B, fontSize=7, fillColor=WHITE if color != GOLD else NAVY))
        d.add(String(x, y - 12, f"H{start}", fontName=FONT, fontSize=6.5, fillColor=MID))
    d.add(String(x0 + total_w, y - 12, "H39", textAnchor="end", fontName=FONT, fontSize=6.5, fillColor=MID))
    d.add(Rect(18, 30, 216, 30, rx=5, ry=5, fillColor=PALE_BLUE, strokeColor=BLUE))
    d.add(String(28, 47, "Person A", fontName=FONT_B, fontSize=8, fillColor=NAVY))
    d.add(String(78, 47, "data, scientific checks, evidence rules", fontName=FONT, fontSize=7, fillColor=INK))
    d.add(Rect(267, 30, 216, 30, rx=5, ry=5, fillColor=PALE_GREEN, strokeColor=TEAL))
    d.add(String(277, 47, "Person B", fontName=FONT_B, fontSize=8, fillColor=NAVY))
    d.add(String(327, 47, "interaction, visual story, accessibility, pitch", fontName=FONT, fontSize=7, fillColor=INK))
    return d


def first_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, h, stroke=0, fill=1)
    # subtle orbital arcs
    canvas.setStrokeColor(HexColor("#123B5D"))
    canvas.setLineWidth(1)
    for r in [170, 230, 300, 380]:
        canvas.circle(w * 0.5, h * 0.65, r, stroke=1, fill=0)
    canvas.setFillColor(CYAN)
    canvas.circle(w * 0.78, h * 0.78, 7, stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.circle(w * 0.2, h * 0.6, 4, stroke=0, fill=1)
    canvas.restoreState()


def later_pages(canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 34, w, 34, stroke=0, fill=1)
    canvas.setFont(FONT_B, 7.5)
    canvas.setFillColor(WHITE)
    canvas.drawString(0.62 * inch, h - 21, "NISAR WITNESS")
    canvas.setFont(FONT, 7)
    canvas.setFillColor(HexColor("#BDD0E0"))
    canvas.drawRightString(w - 0.62 * inch, h - 21, "95+ CONDITIONAL WINNING BLUEPRINT")
    canvas.setStrokeColor(LINE_GREY)
    canvas.line(0.62 * inch, 31, w - 0.62 * inch, 31)
    canvas.setFillColor(MID)
    canvas.setFont(FONT, 7)
    canvas.drawString(0.62 * inch, 19, "Research and strategy - no pre-start implementation")
    canvas.drawRightString(w - 0.62 * inch, 19, f"{doc.page}")
    canvas.restoreState()


def add_title(story, text, subtitle=None):
    story.append(P(text, "H1x"))
    if subtitle:
        story.append(P(subtitle, "Caption"))


def add_section(story, n, title, subtitle=None):
    story.append(SectionBand(n, title, subtitle))
    story.append(Spacer(1, 7))


story = []

# Cover
story += [
    Spacer(1, 0.78 * inch),
    P("NASA SPACE APPS 2026 - GREENSBORO", "CoverKicker"),
    P("NISAR<br/>WITNESS", "CoverTitle"),
    P("A claim-testing map for trustworthy surface change", "CoverSub"),
    Spacer(1, 0.15 * inch),
    P("Most maps show where something changed.<br/>WITNESS shows whether the change claim survives scientific scrutiny.", "CoverQuote"),
    Spacer(1, 0.15 * inch),
    metric_cards([("95.7", "conditional finished score"), ("1", "primary real-world case"), ("7/7", "originality benchmark target"), ("39h", "two-person delivery window")]),
    Spacer(1, 0.28 * inch),
    P("FINAL IDEA BREAKDOWN  |  PRODUCT  |  SCIENCE  |  VALIDATION  |  EXECUTION  |  PITCH", "CoverKicker"),
    Spacer(1, 0.18 * inch),
    P("Prepared 13 November 2026. This document is a strategy blueprint. A score above 95 is conditional on the named evidence gates; it is not a promise of a judging result.", "Caption"),
    PageBreak(),
]

# Executive decision
add_section(story, 1, "Executive decision", "What the product is, why it can exceed 95, and what would invalidate that score")
story.append(P("The final product is <b>NISAR WITNESS</b>: an evidence-aware map that lets a user challenge an apparent surface-change claim made from NASA-ISRO SAR mission data. It does not stop at a before-and-after image or an AI label. It tests whether the selected observations are comparable, whether the relevant pixels are valid, whether the signal survives reasonable sensitivity checks, whether a control area remains stable, and whether any claimed cause is independently supported."))
story.append(P("<b>Primary user:</b> an emergency analyst, local responder, environmental investigator, or science communicator who must decide whether a change map is strong enough to brief, investigate, or act on."))
story.append(P("<b>Defining interaction:</b> the user sees an apparent change and presses <b>Challenge this claim</b>. WITNESS reveals an evidence ladder and returns one of three bounded outcomes: <font color='#159B72'><b>SUPPORTED</b></font>, <font color='#C37A00'><b>AMBIGUOUS</b></font>, or <font color='#C63B3B'><b>NOT COMPARABLE</b></font>."))
story.append(ScoreBar(95.7))
story.append(P("The 95.7 is a <b>conditional finished score</b>. It applies only if the real demo includes one valid NISAR case, one stable control, visible product lineage and quality evidence, a sensitivity test, an exportable record, an offline path, and a clear presentation. Without those artifacts, the current unbuilt strategy is not a 95-point submission.", "Warning"))
story.append(Spacer(1, 6))
story.append(P("<b>Why this outranks the original POLARIS:</b> POLARIS entered a mature field containing Moon Trek, NASA's Celestial Mapping System, MMGIS Sightline, STK, FreeFlyer, Cesium Moon, and several sophisticated 2026 lunar repositories. WITNESS has a fresher data moment, a broader human impact story, and a cleaner judge-facing novelty: it attempts to falsify a change claim before presenting it as knowledge."))
story.append(P("<b>Fallback:</b> if the NISAR data gate fails by hour 3, pivot to the refined lunar concept EVIDENCE FRONTIER. Do not force an invalid NISAR result merely to preserve this ranking."))

story.append(PageBreak())
add_section(story, 2, "The 95+ design", "The upgrades that move the idea from 91.3 to a defensible 95.7")
story.append(P("A higher score cannot come from adding more features. It comes from closing the weaknesses that judges can attack. The original 91.3 concept becomes a 95+ concept through six evidence upgrades:"))
upgrade_rows = [
    ("1. Decision contract", "State one user, one claim, one action, and one cost of being wrong. The app is not a general SAR viewer."),
    ("2. Dual-control validation", "Use a geographic no-change control and a software synthetic-change control. They test different failure modes."),
    ("3. Comparability certificate", "Make product maturity, processing release/CRID, dates, mode, geometry, polarization, projection, masks, and thresholds visible."),
    ("4. Counterfactual evidence", "Show what specific failed check would change the verdict. This converts uncertainty from a disclaimer into an interaction."),
    ("5. Reproducible record", "Export the exact source identifiers, rules, thresholds, result, and limitations. A screenshot becomes an auditable artifact."),
    ("6. Offline judge path", "Precompute one honest case so the defining interaction works instantly on the Surface Pro without venue internet."),
]
story.append(standard_table(["Upgrade", "Required finished evidence"], upgrade_rows, [1.55 * inch, 5.35 * inch]))
story.append(Spacer(1, 8))
story.append(P("<b>Frontier capability:</b> not automatic change detection, but <i>decision-grade claim testing</i>. Existing tools help users find and visualize data. WITNESS is judged on whether it can explain why a particular claim should or should not survive scrutiny." , "Callout"))

score_rows = [
    ("Impact", "9", "97", "A wrong change claim can misdirect response or public communication; one clear operational user."),
    ("Creativity", "8", "96", "The central interaction challenges evidence rather than displaying another difference map."),
    ("Validity", "10", "96", "Comparability, masks, controls, sensitivity, bounded verdicts, and cause separation."),
    ("Relevance", "8", "99", "Directly uses NISAR radar data to track and interpret surface change."),
    ("Presentation", "7", "97", "One location, one button, three verdicts, one exportable record."),
    ("Scientific depth", "6", "96", "SAR-specific product metadata and quality layers drive the conclusion."),
    ("NASA data", "6", "99", "NASA data and metadata are causal inputs, not decoration."),
    ("Competitive uniqueness", "8", "97", "Seven-part falsification benchmark, not a generic map or classifier."),
    ("39-hour feasibility", "8", "91", "One precomputed AOI and one case; no arbitrary upload or global processing."),
    ("Validation", "6", "97", "Control, synthetic injection, threshold sensitivity, second channel, provenance."),
    ("Data readiness", "5", "94", "Validated Level 0-2 products exist, but the archive is young and pair selection is a gate."),
    ("Reliability/offline", "4", "94", "Static evidence bundle and device mirror; no server dependency for judging."),
    ("UX", "4", "97", "Evidence is adjacent to the claim; progressive disclosure keeps it understandable."),
    ("Accessibility", "3", "93", "Keyboard flow, text verdicts, patterns plus color, captions, reduced motion."),
    ("Provenance", "3", "100", "Every verdict exports source IDs, dates, rules, thresholds, and limitations."),
    ("Long-term value", "3", "96", "The evidence contract generalizes to other NISAR locations and sensors."),
    ("Hardware fit", "2", "92", "Heavy preprocessing on M-series Mac; static demo on all three devices."),
]
story.append(PageBreak())
story.append(P("95+ weighted scorecard", "H2x"))
story.append(standard_table(["Category", "Weight", "Score", "Evidence required for score"], score_rows, [1.25 * inch, 0.48 * inch, 0.48 * inch, 4.69 * inch]))
story.append(P("Weighted result: <b>95.7/100</b>. If the data gate, validity gate, or demo gate fails, this score is void. The number is a design target tied to artifacts, not a claim about guaranteed judges.", "Evidence"))

story.append(PageBreak())
add_section(story, 3, "Problem, user, and decision", "The project is a decision tool, not a broad Earth-observation platform")
story.append(P("Radar can observe the surface through clouds and darkness, but radar intensity and interferometric products are not ordinary photographs. Apparent differences can result from acquisition geometry, polarization, processing maturity, coherence loss, masks, terrain effects, moisture, vegetation, or true physical change. A visually dramatic layer can therefore be correct, ambiguous, or scientifically incomparable."))
story.append(P("WITNESS addresses a narrow failure mode: <b>a user sees a change and jumps directly from image difference to causal story.</b> The product inserts an accountable evidence step between those two moments."))
story.append(metric_cards([("1", "claim under review"), ("2", "NASA observations"), ("1", "stable control"), ("3", "bounded verdict states")]))
story.append(P("The decision contract", "H2x"))
contract_rows = [
    ("User", "A responder or analyst preparing an initial change briefing."),
    ("Question", "Does this selected area show a defensible change signal between the chosen NISAR observations?"),
    ("Action", "Brief/investigate, hold as ambiguous, or reject the comparison."),
    ("Cost of false positive", "Resources or public attention are directed toward an artifact or unsupported interpretation."),
    ("Cost of false negative", "A meaningful change is dismissed or investigated later."),
    ("Product promise", "WITNESS does not identify every event. It exposes whether this claim survives the implemented checks."),
]
story.append(standard_table(["Element", "Definition"], contract_rows, [1.25 * inch, 5.65 * inch]))
story.append(P("Language discipline", "H2x"))
story.append(bullets([
    "Say <b>radar response changed</b> unless a physical displacement or event type is supported by the selected product and an independent source.",
    "Say <b>supported by these checks</b>, not proven true.",
    "Say <b>ambiguous</b> when evidence conflicts or quality is insufficient.",
    "Say <b>not comparable</b> when product maturity, processing lineage, mode, geometry, or coverage invalidates the comparison.",
    "Never display a probability or confidence percentage unless it was calibrated against labeled examples."
]))
story.append(P("Judge test: after a 60-second demo, a judge should be able to repeat, 'WITNESS does not tell me what changed; it tells me whether the evidence is strong enough to make the change claim.'", "Callout"))

story.append(PageBreak())
add_section(story, 4, "Product experience", "One screen, one defining action, and evidence that remains visible")
story.append(ui_wireframe())
story.append(P("Conceptual wireframe. The finished interface may differ, but the information hierarchy should not.", "Caption"))
story.append(P("The golden path", "H2x"))
golden_rows = [
    ("1. Orient", "Open directly on the chosen case. The title names location and acquisition dates."),
    ("2. Observe", "Use a before/after or swipe view plus a restrained change overlay."),
    ("3. Claim", "State exactly what the map suggests: 'Radar response changed in this boundary.'"),
    ("4. Challenge", "Press the single primary button. Checks reveal progressively, not as a dense dashboard."),
    ("5. Verdict", "Supported, ambiguous, or not comparable appears with the failed/passed evidence."),
    ("6. Counterfactual", "Show the shortest answer to 'What would change this verdict?'"),
    ("7. Export", "Download or display the evidence card with source IDs and limitations."),
]
story.append(standard_table(["Step", "Judge-visible behavior"], golden_rows, [1.25 * inch, 5.65 * inch]))
story.append(P("Accessibility acceptance criteria", "H2x"))
story.append(bullets([
    "All controls work by keyboard with visible focus.",
    "Verdicts use text, icon, and pattern; color is never the sole channel.",
    "The map has a concise text summary of location, dates, visible change, and verdict.",
    "Any animation has pause and reduced-motion behavior.",
    "The 30-second demo is captioned; the seven-slide alternative uses large type and high contrast.",
    "No essential evidence is available only on hover."
]))

story.append(PageBreak())
add_section(story, 5, "Evidence engine", "The deterministic checks behind supported, ambiguous, and not comparable")
story.append(evidence_ladder_drawing())
story.append(P("The evidence ladder is intentionally ordered. Comparability and pixel validity are gates; later checks cannot rescue incompatible inputs.", "Caption"))
rules = [
    ("Comparability", "Maturity/release, dates, product type, orbit/acquisition mode, geometry, polarization, projection, pixel spacing.", "Fail -> NOT COMPARABLE"),
    ("Pixel validity", "Nodata, water, shadow/layover, connected components, coherence or number-of-looks fields as appropriate.", "Widespread failure -> AMBIGUOUS or NOT COMPARABLE"),
    ("Signal", "A predeclared change statistic or product measurement inside a fixed area of interest.", "No signal -> UNSUPPORTED/AMBIGUOUS wording"),
    ("Sensitivity", "Conclusion repeated across at least three defensible thresholds and, where available, another polarization/layer.", "Flip -> AMBIGUOUS"),
    ("Control", "Nearby stable region processed identically; control should not produce the same apparent anomaly.", "Unstable -> AMBIGUOUS"),
    ("Interpretation", "Independent authoritative source supports any event/cause label.", "Absent -> remove cause, retain observation only"),
    ("Record", "Source IDs, acquisition times, rules, thresholds, software version, and limitations.", "Missing -> provenance gate fails"),
]
story.append(standard_table(["Check", "What is examined", "Effect"], rules, [1.05 * inch, 4.25 * inch, 1.6 * inch]))
story.append(P("Verdict policy", "H2x"))
verdict_rows = [
    (P("<font color='#159B72'><b>SUPPORTED</b></font>", "TableCellBold"), "Inputs are comparable; required pixels are valid; signal survives sensitivity checks; control is stable. Any cause label has external support."),
    (P("<font color='#C37A00'><b>AMBIGUOUS</b></font>", "TableCellBold"), "Inputs may be comparable, but quality, sensitivity, control, or interpretation does not justify a firm claim."),
    (P("<font color='#C63B3B'><b>NOT COMPARABLE</b></font>", "TableCellBold"), "A foundational mismatch or coverage failure means the selected observations cannot support the claim."),
]
story.append(standard_table(["Verdict", "Meaning"], verdict_rows, [1.4 * inch, 5.5 * inch]))
story.append(P("Do not allow an LLM to compute these states. The verdict must be reproducible from explicit rules. If Ollama is used, it may only paraphrase the already completed evidence record and must disclose the model/version.", "Warning"))

add_section(story, 6, "Data and architecture", "Use the simplest NISAR product that can support a truthful case")
story.append(P("NASA's current NISAR documentation states that fully calibrated and validated Level 0-2 L-band products were released on 6 November 2026 for acquisitions beginning 21 October 2026. The same documentation warns that differences across maturity levels can arise from processing changes rather than landscape change. This makes product lineage a first-class part of WITNESS, not a footnote. [S1][S2]"))
story.append(architecture_drawing())
story.append(P("The architecture is deliberately small. Processing happens once for one area; judging uses a compact local bundle.", "Caption"))
story.append(P("Product-selection decision", "H2x"))
product_rows = [
    ("GCOV", "Best default for a weekend MVP: geocoded, radiometrically terrain-corrected backscatter/covariance with masks and looks fields.", "Pairwise amplitude/backscatter change with careful wording."),
    ("GSLC", "Map-ready complex data; more flexibility but higher interpretation and processing burden.", "Use only if the team already understands it."),
    ("GUNW", "Geocoded unwrapped interferogram with coherence, components, ionosphere fields.", "Powerful for displacement, but only if an appropriate pair product already exists and is understood."),
    ("GOFF", "Geocoded pixel offsets with quality-related fields.", "Useful for large displacement/cryosphere cases; not the default."),
    ("Raw/RSLC", "Large, complex, and unnecessary for the product story.", "Do not build an interferometric processor during the hackathon."),
]
story.append(standard_table(["Product", "Weekend assessment", "Recommendation"], product_rows, [0.65 * inch, 3.75 * inch, 2.5 * inch]))
story.append(P("Data bundle contents", "H2x"))
story.append(bullets([
    "Two compact display rasters or one pair product for a fixed area of interest.",
    "Change/statistic layer and a nonmisleading legend.",
    "Relevant validity/quality layer such as mask, coherence, connected component, number of looks, or product uncertainty.",
    "Control-region geometry and its result.",
    "Versioned JSON evidence record containing product IDs, dates, maturity, CRID/release, geometry, polarization, projection, rules, thresholds, and limitations.",
    "Static screenshots as a last-resort pitch fallback."
]))

add_section(story, 7, "Validation that judges can see", "A 95+ score requires evidence artifacts, not the phrase 'scientifically validated'")
validation_rows = [
    ("V1 Metadata", "Parse and display the fields used to determine comparability.", "Evidence card contains both product records.", "Required"),
    ("V2 Stable control", "Process a nearby area expected to remain stable with identical rules.", "Control statistic and map remain below criterion.", "Required"),
    ("V3 Threshold sensitivity", "Repeat at three predeclared thresholds.", "Verdict remains stable or becomes honestly ambiguous.", "Required"),
    ("V4 Cross-channel", "Repeat with another polarization/layer where scientifically appropriate.", "Agreement or documented disagreement.", "High value"),
    ("V5 Synthetic injection", "Insert a known artificial patch in a copied raster.", "Pipeline detects the injected software test.", "Required software check"),
    ("V6 Mask exclusion", "Force a test geometry across invalid pixels.", "Invalid pixels cannot become supporting evidence.", "Required"),
    ("V7 Independent context", "Compare the interpretation with an authoritative event source or other sensor.", "Cause language is supported or removed.", "Required for cause"),
    ("V8 Clean replay", "Regenerate the evidence bundle from a clean run.", "Same result, rule version, and identifiers.", "Required"),
]
story.append(standard_table(["Test", "Method", "Judge-visible artifact", "Status"], validation_rows, [1.15 * inch, 2.55 * inch, 2.25 * inch, 0.95 * inch]))
story.append(P("Scientific claims table", "H2x"))
claim_rows = [
    ("The pixels differ", "Directly observed in the selected processed product(s).", "Difference layer plus product IDs."),
    ("The comparison is valid", "Supported only if metadata and coverage gates pass.", "Comparability certificate."),
    ("The surface changed", "Inference; strength depends on product, masks, control, and sensitivity.", "Bounded verdict and limitations."),
    ("A specific event caused it", "Not inferable from the radar difference alone.", "Independent authoritative source required."),
    ("The method generalizes", "Roadmap claim, not demonstrated by one case.", "Phrase as future work."),
]
story.append(standard_table(["Claim", "Epistemic status", "Required evidence"], claim_rows, [1.55 * inch, 2.65 * inch, 2.7 * inch]))
story.append(P("A passing software test does not validate a physical interpretation. A matching external report does not prove the map caused the correct conclusion. Keep software correctness, data quality, and scientific interpretation as separate evidence layers.", "Callout"))

story.append(PageBreak())
add_section(story, 8, "Originality and prior art", "What can be claimed, what cannot, and how to benchmark the finished product")
story.append(P("SAR change detection, coherence analysis, confidence measures, masks, provenance, robustness checks, and before/after visualization are established prior art. WITNESS must not claim to invent any of them. The defensible novelty is their integration into a short, judge-visible <b>claim-falsification workflow</b> for newly validated NISAR data."))
benchmark_rows = [
    ("Processing maturity/release visible", "Source collection and CRID/release appear beside the claim."),
    ("Comparability checked", "Mode, geometry, polarization, projection, date, and product type are explicitly evaluated."),
    ("Quality evidence adjacent", "Mask/coherence/looks or appropriate quality layer is one click from the verdict."),
    ("Control tested", "A stable area is processed with identical rules."),
    ("Sensitivity challenges result", "Threshold and second-channel behavior can overturn the verdict."),
    ("Observation separated from cause", "The UI distinguishes measured response, inferred change, and external interpretation."),
    ("Reproducible evidence export", "A third party receives source IDs, rules, thresholds, and limitations."),
]
story.append(standard_table(["7-part originality benchmark", "Passing condition"], benchmark_rows, [2.25 * inch, 4.65 * inch]))
story.append(P("Target: <b>7/7</b>. During the event, compare WITNESS with ASF Vertex, NASA Worldview, a standard before/after slider, and one public SAR-change notebook. Do not publish guessed competitor scores. Test the actual functions and record evidence. If an incumbent already reaches 6/7 or 7/7, narrow the distinction further.", "Evidence"))
story.append(P("Why the name is provisional", "H2x"))
story.append(P("'WITNESS' communicates evidence and observation, but a public product name should receive a proper trademark and domain review before commercialization. The hackathon may use <b>NISAR WITNESS</b> descriptively. Do not imply NASA endorsement or ownership, and follow Space Apps branding rules."))
story.append(P("Competitive moat after the event", "H2x"))
story.append(bullets([
    "A sensor-agnostic evidence schema that can represent NISAR, Sentinel-1, optical, and event records without erasing their differences.",
    "A library of versioned claim checks and counterexamples rather than a library of black-box classifications.",
    "Human-readable evidence records that can be reviewed, corrected, and reproduced.",
    "Case-specific calibration and expert review before any operational confidence claim."
]))

story.append(PageBreak())
add_section(story, 9, "Two-person execution plan", "How to preserve the 95+ qualities within the real hardware and time limit")
story.append(timeline_drawing())
schedule_rows = [
    ("H0-H1", "Read final challenge resource tab; confirm definitions; choose candidate product.", "Confirm local rules; create one-screen content map.", "Rule and challenge lock"),
    ("H1-H3", "Find compatible data; inspect metadata and quality layers; define control.", "Build visual shell using clearly marked placeholders.", "NISAR gate or lunar pivot"),
    ("H3-H8", "Generate one real result, one control, compact evidence JSON.", "Connect the golden path and offline assets.", "End-to-end vertical slice"),
    ("H8-H14", "Implement comparability, masks, sensitivity, and verdict rules.", "Build Challenge this claim and evidence ladder.", "Differentiator works"),
    ("H14-H20", "Run V1-V8 subset; freeze scientific wording.", "Accessibility and device checks.", "Validity gate"),
    ("H20-H27", "Clean replay, provenance, limitations, source list.", "Polish, responsive layout, fallback screenshots.", "Demo gate"),
    ("H27-H31", "Methods and evidence-card review.", "Slides/video, captions, submission copy.", "Story freeze"),
    ("H31-H35", "Independent result audit.", "Rehearse and private-window link checks.", "Submission candidate"),
    ("H35-H39", "Critical fixes only.", "Submit early and preserve receipt.", "No new features"),
]
story.append(standard_table(["Time", "Person A - science/data", "Person B - product/story", "Gate"], schedule_rows, [0.65 * inch, 2.45 * inch, 2.45 * inch, 1.35 * inch]))
story.append(P("Device allocation", "H2x"))
device_rows = [
    ("Apple-silicon MacBook", "Data extraction, raster preparation, scientific checks, final integration.", "Do not run a large Ollama model during heavy processing."),
    ("2017 MacBook Pro, 16 GB", "UI, source control, slides/video, browser and accessibility QA.", "Avoid full NISAR processing."),
    ("Surface Pro 8, 8 GB", "Offline demo mirror, touchscreen rehearsal, Windows compatibility, submission backup.", "Never make it the data-processing machine."),
]
story.append(standard_table(["Device", "Role", "Constraint"], device_rows, [1.55 * inch, 3.15 * inch, 2.2 * inch]))

story.append(PageBreak())
add_section(story, 10, "Hard gates and kill criteria", "A winning strategy must know when to stop")
gate_rows = [
    ("Rules", "All implementation begins after the official start; sources and AI tools are disclosed.", "Any violation or ambiguity unresolved."),
    ("Data - H3", "Comparable NISAR observations/pair product, quality evidence, control, and offline bundle path exist.", "Any required element missing by H3 -> pivot lunar."),
    ("Truth - H6", "At least one interpretable signal plus stable control.", "No signal, unstable control, or unexplained artifact -> pivot."),
    ("Performance - H8", "Defining interaction works in seconds without network.", "Precompute immediately; if still unreliable, pivot/simplify."),
    ("Validity - H20", "Metadata, mask, control, sensitivity, synthetic, and replay evidence exist.", "Stop features; repair evidence or lower claims."),
    ("Novelty - H14", "At least 6/7 benchmark functions work; 7/7 target remains achievable.", "Narrow differentiator or change concept."),
    ("Demo - H27", "A judge reaches the verdict and understands it in under 60 seconds.", "Remove screens and secondary controls."),
    ("Submission - H35", "Public links, required fields, citations, AI disclosure, demo, and final project are ready.", "Freeze and submit stable version."),
]
story.append(standard_table(["Gate", "Pass condition", "Kill action"], gate_rows, [1.0 * inch, 3.9 * inch, 2.0 * inch]))
story.append(P("Feature kill order", "H2x"))
story.append(P("Cut in this order: global coverage -> arbitrary uploads -> animated storytelling -> extra cases -> AI narration -> secondary charts -> account/cloud features. Never cut the evidence ladder, control, provenance, or offline path before cutting these features."))
story.append(P("Fallback decision", "H2x"))
story.append(P("If the NISAR gate fails, move to <b>EVIDENCE FRONTIER</b>: compare two lunar landing sites under alternate terrain evidence, find the first decision-violating interval, and identify the horizon sector whose improved measurement would resolve the choice. Do not revert to broad POLARIS features such as a general 3D globe, rover planner, link budget, or AI mission assistant." , "Callout"))

story.append(PageBreak())
add_section(story, 11, "Judge presentation", "A concise narrative that turns technical honesty into the memorable feature")
story.append(P("30-second demo script", "H2x"))
story.append(P("<b>A satellite difference map can look certain even when its products, geometry, or quality do not support the claim. NISAR WITNESS lets a responder challenge one apparent surface change. It checks comparable NASA NISAR data, quality masks, a control area, and sensitivity, then says supported, ambiguous, or not comparable. We do not ask AI to guess what happened. We show what the data proves, what it suggests, and what remains unknown.</b>", "Callout"))
story.append(P("Provisional seven-slide narrative", "H2x"))
slides = [
    ("1", "The costly mistake", "A confident-looking change map can mix physical change, processing difference, and unsupported interpretation."),
    ("2", "The user and decision", "A responder must decide whether to brief, investigate, hold, or reject a claim."),
    ("3", "The real case", "One location, two NISAR observations, one apparent change, one stable control."),
    ("4", "Challenge this claim", "Reveal comparability, validity/quality, sensitivity, and control."),
    ("5", "The bounded verdict", "Supported, ambiguous, or not comparable, plus what would change the verdict."),
    ("6", "Why trust it", "Product lineage, visible tests, independent context, and exportable evidence record."),
    ("7", "Impact and frontier", "Turn new NISAR imagery into accountable evidence; extend the contract carefully to more cases and sensors."),
]
story.append(standard_table(["Slide", "Headline", "Single job"], slides, [0.45 * inch, 1.6 * inch, 4.85 * inch]))
story.append(P("Likely judge questions", "H2x"))
qa_rows = [
    ("Is this just a before/after viewer?", "No. The map is context; the product is the comparability, quality, control, sensitivity, and provenance workflow that can overturn the initial claim."),
    ("Where is the AI?", "AI is optional narration only. Deterministic evidence rules compute the verdict so it can be reproduced."),
    ("How do you know the change is real?", "We do not claim certainty. We show the product lineage, validity layers, control, sensitivity, and any independent support, then issue a bounded verdict."),
    ("Why one location?", "One scientifically defensible case proves the interaction. Global scale without validation would reduce validity and feasibility."),
    ("What is novel?", "The judge-visible attempt to falsify a specific NISAR change claim and export the evidence record, not the individual SAR methods."),
    ("Could responders use this now?", "It is a decision-support prototype, not an operational alert system. Operational use requires more cases, calibration, expert review, and governance."),
]
story.append(standard_table(["Question", "Answer"], qa_rows, [2.05 * inch, 4.85 * inch]))

story.append(PageBreak())
add_section(story, 12, "Risk register", "The strongest concept is the one that states its failure modes before judges discover them")
risk_rows = [
    ("No compatible pair", "High", "High", "Three-hour gate; use existing pair product if valid; otherwise pivot lunar."),
    ("Files too large", "High", "Medium", "One small AOI, map-ready Level 2 data, precomputed bundle, no arbitrary upload."),
    ("Signal is moisture/vegetation, not target event", "High", "High", "Remove cause label; show radar-response change and ambiguity."),
    ("Control also changes", "Medium", "High", "Choose a better control or mark verdict ambiguous; never hide result."),
    ("Threshold chosen after seeing answer", "Medium", "High", "Declare threshold set before final comparison and show all three."),
    ("Quality field misunderstood", "Medium", "High", "Use official product guide; cut field if not explainable by H10."),
    ("Network failure", "Medium", "High", "Static local bundle on all devices; screenshots as final fallback."),
    ("AI hallucination", "Low", "High", "AI outside verdict path; constrain to structured record or remove it."),
    ("Pitch becomes technical", "Medium", "Medium", "Lead with wrong decision and one button; methods appear only after verdict."),
    ("Local schedule differs", "Medium", "Medium", "Confirm with Greensboro lead; prepare 30-second, 3-minute, and seven-slide variants."),
]
story.append(standard_table(["Risk", "Likelihood", "Impact", "Mitigation"], risk_rows, [1.85 * inch, 0.75 * inch, 0.65 * inch, 3.65 * inch]))
story.append(P("Claims explicitly excluded", "H2x"))
story.append(bullets([
    "No claim that WITNESS predicts disasters.",
    "No claim that one case validates global performance.",
    "No claim that a radar difference proves a physical cause.",
    "No claim that the project is flight-, response-, or safety-certified.",
    "No claim that the methods are mathematically novel.",
    "No claim of a guaranteed 95 score or award."
]))

story.append(PageBreak())
add_section(story, 13, "Submission checklist", "What must exist for the 95+ claim to remain honest")
check_rows = [
    ("Project title and one-sentence promise", "NISAR WITNESS: challenge a surface-change claim before acting on it."),
    ("Real NASA data", "Product IDs, dates, maturity/release, relevant metadata, and links recorded."),
    ("Demo", "One case, one control, one defining interaction, one verdict, one counterfactual."),
    ("Validation", "Visible artifacts for metadata, mask, control, sensitivity, synthetic injection, and replay."),
    ("Methods", "Statistic, thresholds, rules, assumptions, and limitations written in plain language."),
    ("Provenance", "Exportable evidence record and a complete source/reference list."),
    ("Accessibility", "Keyboard, focus, contrast, text verdict, map summary, captions, reduced motion."),
    ("Reliability", "Offline bundle tested on Surface Pro and both MacBooks."),
    ("AI disclosure", "Every AI/SI tool, model, and role listed; no hidden verdict generation."),
    ("Public links", "Opened in a private browser on a device not logged into the hosting account."),
    ("Branding", "NASA/Space Apps attribution follows official brand guidance; no endorsement implication."),
    ("Deadline", "Stable submission frozen early; receipt/screenshots preserved."),
]
story.append(standard_table(["Required artifact", "Acceptance condition"], check_rows, [2.15 * inch, 4.75 * inch]))
story.append(P("Score integrity test", "H2x"))
story.append(P("Before using '95+' in any internal assessment, point to a finished artifact for every row in the scorecard. If a row depends on a future feature, reduce the score. Judges reward what is demonstrated and explained, not the roadmap." , "Warning"))
story.append(P("Final go/no-go statement", "H2x"))
story.append(P("<b>GO:</b> comparable data, valid quality evidence, stable control, sensitivity result, deterministic verdict, exportable record, and offline demo all work. <b>NO-GO:</b> any foundational data/validity requirement is missing. Pivot to lunar EVIDENCE FRONTIER rather than presenting certainty the data cannot support.", "Callout"))

story.append(PageBreak())
add_section(story, 14, "Sources and verification notes", "Primary and official sources used for the blueprint")
sources = [
    ("S1", "ASF NISAR Data User Guide - Available NISAR Data", "Validated Level 0-2 release date, acquisition start, maturity and CRID context.", "https://nisar-docs.asf.alaska.edu/availability-overview/"),
    ("S2", "ASF NISAR Data User Guide - Product Overview", "Product levels, fields, map-ready products, and warning about mixing maturity levels.", "https://nisar-docs.asf.alaska.edu/products-overview/"),
    ("S3", "ASF NISAR Data User Guide - Known Issues", "Current validated-product issue tracking and resolved provisional timestamp issue.", "https://nisar-docs.asf.alaska.edu/nisar-known-issues/"),
    ("S4", "NASA Space Apps 2026", "Official event, registration, team, project-editing and submission window.", "https://www.spaceappschallenge.org/2026/"),
    ("S5", "NASA Space Apps Greensboro", "Venue, local contact, minor registration statement, and unresolved exact schedule.", "https://www.spaceappschallenge.org/2026/local-events/greensboro/"),
    ("S6", "NASA Space Apps GO Team - pre-start clarification", "Research, resource review, challenge selection and team formation allowed; project work begins at official start.", "https://github.com/nasa/spaceapps/discussions/1827"),
    ("S7", "NASA Space Apps GO Team - submission fields", "Required project fields, data references, AI/SI disclosure, and pre-start warning.", "https://github.com/nasa/spaceapps/discussions/1858"),
    ("S8", "NASA 2025 Global Winners", "Evidence that strong winners connect NASA data to a legible user, decision, or impact story.", "https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/"),
    ("S9", "Official 2025 winner gallery", "Project summaries and award context.", "https://www.spaceappschallenge.org/2025/awards/global-winners/"),
    ("S10", "ASF Vertex", "NISAR and SAR data discovery benchmark.", "https://search.asf.alaska.edu/"),
    ("S11", "NASA Worldview", "Earth-observation visualization benchmark.", "https://worldview.earthdata.nasa.gov/"),
]
for sid, title, use, url in sources:
    story.append(Paragraph(f"<b>{sid}. <link href='{url}' color='#1D70B8'>{title}</link></b><br/><font color='#526579'>{use}</font>", styles["Source"]))
story.append(Spacer(1, 8))
story.append(P("Verification notes", "H2x"))
story.append(bullets([
    "The official 2026 judging weights were not publicly verified when the underlying research was performed. The 17-category model is an explicit strategy model, not NASA's published weighting.",
    "The 30-second video or seven-slide format was current community guidance but was not treated as verified until an official 2026 Project Submission Guide becomes available.",
    "Greensboro's exact venue hours and local pitch format remained unpublished on the event page when checked.",
    "The score is conditional on a finished, demonstrated MVP. It is not an elapsed-time claim, probability of winning, or promise from NASA."
], small=True))

story.append(PageBreak())
add_section(story, 15, "One-page command brief", "The entire strategy reduced to the decisions that matter")
story.append(P("THE IDEA", "H3x"))
story.append(P("NISAR WITNESS is a claim-testing map. A user selects an apparent surface change and presses <b>Challenge this claim</b>. The product checks comparability, valid pixels, quality evidence, sensitivity, a control region, and independent context. It returns supported, ambiguous, or not comparable, then exports the evidence record."))
story.append(P("THE 95+ DIFFERENCE", "H3x"))
story.append(P("Do not add more scope. Earn the score with a decision contract, dual controls, a comparability certificate, counterfactual evidence, reproducible provenance, accessibility, and an offline judge path."))
story.append(P("THE THREE-HOUR GATE", "H3x"))
story.append(P("Continue only if one small area has compatible NISAR data, a usable quality layer, one interpretable signal, one stable control, and a credible offline bundle path. Otherwise pivot immediately to lunar EVIDENCE FRONTIER."))
story.append(P("THE MVP", "H3x"))
story.append(bullets([
    "One location and one bounded claim.",
    "Two observations or an appropriate pair product.",
    "One control region.",
    "One relevant quality/mask layer.",
    "Three-threshold sensitivity test.",
    "Deterministic three-state verdict.",
    "Exportable evidence card.",
    "Offline demo on the Surface Pro."
]))
story.append(P("THE PITCH", "H3x"))
story.append(Spacer(1, 7))
story.append(P("Most maps show where something changed. WITNESS shows whether the change claim survives scientific scrutiny." , "Callout"))
story.append(P("THE FINAL RULE", "H3x"))
story.append(P("Never protect the product idea at the expense of scientific honesty. A visible ambiguous result is more credible - and more distinctive - than a confident classification the data cannot support."))


doc = SimpleDocTemplate(
    str(OUTPUT), pagesize=letter,
    rightMargin=0.62 * inch, leftMargin=0.62 * inch,
    topMargin=0.58 * inch, bottomMargin=0.52 * inch,
    title="NISAR WITNESS - 95+ Winning Blueprint",
    author="OpenAI Codex for NASA Space Apps Greensboro 2026",
    subject="Detailed product, science, validation, execution, and presentation blueprint",
    creator="ReportLab"
)
doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
print(OUTPUT)
