"""
PDF input.

A PDF has no paragraphs - it has glyphs at coordinates. pypdf hands
back one visual line at a time, so a paragraph that was wrapped across
six lines in the original arrives as six separate lines, and nothing in
the file says which of those breaks were real.

Feeding those raw lines downstream would be wrong twice over: the
chunker would treat every wrapped line as its own paragraph, and the
translator would be asked to translate half-sentences in isolation.
So this extractor reflows the lines back into paragraphs before
handing them over, using the one clue the layout leaves behind - a
wrapped line runs to the right margin, the last line of a paragraph
stops short of it (_ends_paragraph below).

Scans are the known limitation: a photographed page has no text layer
at all, so there is nothing to extract and the user is told to OCR it
first rather than being handed an empty translation.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional

from .base import Extractor, ExtractedDocument, ExtractionError

# CJK ideographs plus the CJK punctuation and full-width forms that sit
# between them. Used both for spacing decisions and for width, since
# these render roughly twice as wide as a Latin character.
_WIDE_RE = re.compile(
    r"[ᄀ-ᅟ⺀-〾ぁ-㏿㐀-䶿一-鿿"
    r"ꀀ-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]"
)

# A line that is nothing but a page number, optionally dressed up as
# "- 12 -" or "(iv)". Only stripped at the top and bottom of a page,
# where running headers and footers live.
_PAGE_FURNITURE_RE = re.compile(
    r"^[\s\-–—(\[]*(?:\d{1,4}|[ivxlcdm]{1,7})[\s\-–—)\]]*$",
    re.IGNORECASE,
)

# A Latin word broken across a line break with a hyphen.
_HYPHEN_BREAK_RE = re.compile(r"[A-Za-z]-$")

# Below this share of the page's widest line, a line is treated as the
# end of its paragraph (or as a heading standing on its own).
_SHORT_LINE_RATIO = 0.8


def _is_wide(char: str) -> bool:
    return bool(_WIDE_RE.match(char))


def _display_width(line: str) -> int:
    """Line length in character cells, counting CJK as two. Comparing
    raw len() would make a Chinese line look half as long as the Latin
    line beside it and break the margin heuristic on mixed pages."""
    return sum(2 if _is_wide(ch) else 1 for ch in line)


def _join_lines(buffered: str, line: str) -> str:
    """Append a wrapped line to the paragraph being built."""
    if not buffered:
        return line
    if _HYPHEN_BREAK_RE.search(buffered) and line[:1].islower():
        # "inter-\nnational" -> "international"
        return buffered[:-1] + line
    if _is_wide(buffered[-1]) or _is_wide(line[0]):
        # Chinese text has no inter-word spaces; inserting one here
        # would show up verbatim in the translated output.
        return buffered + line
    return buffered + " " + line


def _ends_paragraph(line: str, page_width: int) -> bool:
    """True if this line looks like the last one of its paragraph.

    Justified body text fills the measure, so any line that stops well
    short of the page's widest line is either the tail of a paragraph
    or a heading - both of which end whatever we were accumulating.
    """
    if page_width <= 0:
        return True
    return _display_width(line) < page_width * _SHORT_LINE_RATIO


def _page_lines(page_text: str) -> List[str]:
    lines = [
        ln.strip()
        for ln in page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    while lines and (not lines[0] or _PAGE_FURNITURE_RE.match(lines[0])):
        lines.pop(0)
    while lines and (not lines[-1] or _PAGE_FURNITURE_RE.match(lines[-1])):
        lines.pop()
    return lines


def reflow_pages(pages: List[str]) -> List[str]:
    """Turn per-page line dumps back into paragraphs.

    The paragraph being built carries across a page boundary, so a
    sentence split by a page break is translated as one unit.
    """
    paragraphs: List[str] = []
    buffered = ""

    for page_text in pages:
        lines = _page_lines(page_text)
        if not lines:
            continue
        page_width = max(_display_width(ln) for ln in lines)

        for line in lines:
            if not line:
                # An explicit blank line is the one unambiguous break.
                if buffered:
                    paragraphs.append(buffered)
                    buffered = ""
                continue

            buffered = _join_lines(buffered, line)
            if _ends_paragraph(line, page_width):
                paragraphs.append(buffered)
                buffered = ""

    if buffered:
        paragraphs.append(buffered)

    return [p for p in (para.strip() for para in paragraphs) if p]


class PdfExtractor(Extractor):
    ext = "pdf"

    def extract(self, raw_bytes: bytes, filename: Optional[str] = None) -> ExtractedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ExtractionError("pypdf is not installed on the server.") from exc

        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
        except Exception as exc:  # noqa: BLE001 - pypdf raises many types
            raise ExtractionError(
                "Could not read this .pdf file. It may be corrupted or not a real PDF."
            ) from exc

        if reader.is_encrypted:
            # Plenty of PDFs are encrypted only to restrict printing and
            # open with an empty user password, so try that before
            # giving up on the file.
            try:
                unlocked = reader.decrypt("")
            except Exception:  # noqa: BLE001
                unlocked = 0
            if not unlocked:
                raise ExtractionError(
                    "This PDF is password-protected. Remove the password and try again."
                )

        pages: List[str] = []
        failed_pages = 0
        try:
            page_objects = list(reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(
                "Could not read the pages of this .pdf file. It may be corrupted."
            ) from exc

        for page in page_objects:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                # One unreadable page shouldn't cost the whole document.
                failed_pages += 1
                pages.append("")

        if failed_pages and failed_pages == len(page_objects):
            raise ExtractionError(
                "Could not extract any text from this PDF - the file looks damaged."
            )

        paragraphs = reflow_pages(pages)
        if not paragraphs:
            raise ExtractionError(
                "No text found in this PDF. If it's a scan or a photo of a page, "
                "the words are an image rather than text - run it through OCR first."
            )

        return ExtractedDocument(
            kind="plain",
            paragraphs=paragraphs,
            source_filename=filename,
            # D4: .pdf input produces .txt output, same as .docx.
            source_ext="pdf",
        )
