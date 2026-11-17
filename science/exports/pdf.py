"""Minimal deterministic text-only PDF 1.4 writer (no third-party PDF library is installed).

Base-14 fonts (Helvetica, Helvetica-Bold, Courier), WinAnsiEncoding, uncompressed content streams so the export test
can read every string back (`extract_text`). Characters outside cp1252 are transliterated (>= <= - ->), and the same
transliteration is applied by the test to the expected strings.
"""
from __future__ import annotations

import re

PAGE_W, PAGE_H = 612.0, 792.0          # US Letter, points
MARGIN = 48.0
FONTS = {'F1': 'Helvetica', 'F2': 'Helvetica-Bold', 'F3': 'Courier'}
_TRANSLIT = {'≥': '>=', '≤': '<=', '−': '-', '→': '->', '←': '<-', '±': '+/-', 'σ': 'sigma', '✓': 'ok', '✗': 'x',
             ' ': ' ', ' ': ' ', ' ': ' ', '⁻': '-', '¹': '1', '²': '2', '³': '3'}


def translit(s: str) -> str:
    s = ''.join(_TRANSLIT.get(ch, ch) for ch in str(s))
    return s.encode('cp1252', errors='replace').decode('cp1252')


def _esc(s: str) -> bytes:
    b = translit(s).encode('cp1252', errors='replace')
    return b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def wrap(text: str, size: float, width: float, mono=False) -> list:
    """Greedy wrap on an average glyph width (0.6 em Courier, 0.52 em Helvetica). Long tokens are split."""
    per = max(8, int(width / (size * (0.6 if mono else 0.52))))
    out = []
    for para in str(text).split('\n'):
        line = ''
        for word in para.split(' '):
            while len(word) > per:
                if line:
                    out.append(line); line = ''
                out.append(word[:per]); word = word[per:]
            cand = word if not line else f'{line} {word}'
            if len(cand) <= per:
                line = cand
            else:
                out.append(line); line = word
        out.append(line)
    return out


class Doc:
    """Flow layout: add(text, size, font) appends wrapped lines and breaks pages."""

    def __init__(self, footer=''):
        self.pages = [[]]; self.y = PAGE_H - MARGIN; self.footer = footer

    def _line(self, text, size, font, x):
        if self.y - size < MARGIN + 14:
            self.pages.append([]); self.y = PAGE_H - MARGIN
        self.y -= size * 1.25
        self.pages[-1].append((x, self.y, size, font, text))

    def add(self, text, size=9.0, font='F1', indent=0.0, gap=0.0):
        x = MARGIN + indent
        for ln in wrap(text, size, PAGE_W - MARGIN - x, mono=font == 'F3'):
            self._line(ln, size, font, x)
        self.y -= gap

    def space(self, h=6.0):
        self.y -= h

    def render(self, title='', subject='') -> bytes:
        objs = []                                   # (num, bytes)
        font_ids = {}
        n = 3
        for key, name in FONTS.items():
            font_ids[key] = n
            objs.append((n, f'<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>'.encode()))
            n += 1
        page_ids = []
        total = len(self.pages)
        for pi, items in enumerate(self.pages, start=1):
            parts = []
            for x, y, size, font, text in items:
                parts.append(b'BT /%s %.2f Tf %.2f %.2f Td (%s) Tj ET' % (font.encode(), size, x, y, _esc(text)))
            foot = f'{self.footer}   page {pi} of {total}'
            parts.append(b'BT /F1 7.00 Tf %.2f %.2f Td (%s) Tj ET' % (MARGIN, MARGIN - 14, _esc(foot)))
            stream = b'\n'.join(parts)
            cid = n; n += 1
            objs.append((cid, b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream'))
            pid = n; n += 1
            fonts = ' '.join(f'/{k} {v} 0 R' for k, v in font_ids.items())
            objs.append((pid, (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:g} {PAGE_H:g}] '
                               f'/Resources << /Font << {fonts} >> >> /Contents {cid} 0 R >>').encode()))
            page_ids.append(pid)
        info = n
        objs.append((info, b'<< /Title (%s) /Subject (%s) /Producer (POLARIS X science.exports.pdf) >>'
                     % (_esc(title), _esc(subject))))
        objs = [(1, b'<< /Type /Catalog /Pages 2 0 R >>'),
                (2, ('<< /Type /Pages /Kids [%s] /Count %d >>' % (' '.join(f'{p} 0 R' for p in page_ids), len(page_ids))).encode())] + objs
        objs.sort()
        out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = {}
        for num, body in objs:
            offsets[num] = len(out)
            out += b'%d 0 obj\n' % num + body + b'\nendobj\n'
        xref = len(out)
        size = max(offsets) + 1
        out += b'xref\n0 %d\n0000000000 65535 f \n' % size
        for i in range(1, size):
            out += b'%010d 00000 n \n' % offsets[i]
        out += b'trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, info, xref)
        return bytes(out)


_TJ = re.compile(rb'\(((?:\\.|[^\\)])*)\) Tj')


def extract_text(pdf: bytes) -> list:
    """Every string drawn with Tj, in order (the writer's own output only)."""
    out = []
    for m in _TJ.finditer(pdf):
        s = re.sub(rb'\\(.)', rb'\1', m.group(1))
        out.append(s.decode('cp1252'))
    return out
