"""
.pdf input.

A PDF stores glyphs at coordinates, not paragraphs, so extracted text
arrives hard-wrapped, with page furniture mixed in. Everything below
exists to turn that back into the paragraph list the rest of the app
works with (extractors/base.py): the chunker splits on paragraphs and
D3's context carryover assumes they're whole sentences, so a document
that arrives as one giant run-on paragraph, or as one paragraph per
wrapped line, chunks badly and translates worse.

Scanned PDFs have no text layer at all - there is nothing to extract
from a picture of a page - so those are rejected with a message saying
so rather than a blank translation.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional

from .base import Extractor, ExtractedDocument, ExtractionError

# Ranges covering CJK ideographs, kana, and the full-width/CJK
# punctuation that travels with them. Lines of CJK are rejoined with no
# separator, Latin lines with a space - the way each script wraps.
_CJK_CLASS = (
    "⺀-〿"   # CJK radicals, Kangxi, CJK punctuation
    "぀-ヿ"   # kana
    "㐀-䶿"   # CJK extension A
    "一-鿿"   # CJK unified ideographs
    "豈-﫿"   # compatibility ideographs
    "︰-﹏"   # CJK compatibility forms
    "＀-￯"   # full-width forms
)
_CJK_RE = re.compile("[" + _CJK_CLASS + "]")

# Layout-mode extraction pads text with spaces to reproduce horizontal
# position, which can leave gaps between CJK characters that were never
# in the text. Chinese doesn't space its characters, so a run of spaces
# between two of them is always an artifact.
_CJK_GAP_RE = re.compile(
    "(?<=[" + _CJK_CLASS + "])[ \t]+(?=[" + _CJK_CLASS + "])"
)

# Page furniture: a bare page number, "- 12 -", "Page 3", "3 of 40".
_PAGE_NUMBER_RE = re.compile(
    r"^(?:[-–—\[(]?\s*)?(?:page\s+)?\d+(?:\s*(?:/|of)\s*\d+)?"
    r"(?:\s*[-–—\])]?)?$",
    re.IGNORECASE,
)

# Sentence-ending punctuation, half- and full-width. A paragraph ending
# in none of these is treated as continuing onto the next page.
_TERMINAL_CHARS = "。．.！!？?…:：;；」』》）)\"'”’"

# A running header/footer has to show up on this share of the pages
# before it's treated as furniture rather than content.
_RUNNING_HEAD_SHARE = 0.6


def _is_cjk(char: str) -> bool:
    return bool(_CJK_RE.match(char))


def _normalize_lines(page_text: str) -> List[str]:
    text = page_text.replace("\r\n", "\n").replace("\r", "\n")
    return [_CJK_GAP_RE.sub("", line).strip() for line in text.split("\n")]


def _trim_blank_edges(lines: List[str]) -> List[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end]


def _find_running_lines(pages: List[List[str]]) -> set:
    """Headers and footers repeated on most pages - a book's running
    title, a footer with the document name. They're the same text on
    every page, so translating them once per page is noise."""
    if len(pages) < 3:
        return set()

    counts = {}
    for lines in pages:
        edges = set()
        if lines:
            edges.add(lines[0])
            edges.add(lines[-1])
        for line in edges:
            if line and not _PAGE_NUMBER_RE.match(line):
                counts[line] = counts.get(line, 0) + 1

    threshold = max(2, int(len(pages) * _RUNNING_HEAD_SHARE))
    return {line for line, count in counts.items() if count >= threshold}


def _strip_page_furniture(lines: List[str], running: set) -> List[str]:
    """Drop page numbers and running heads, but only at the top or
    bottom of a page - a bare number mid-page is content, not furniture."""
    lines = _trim_blank_edges(lines)
    while lines and (_PAGE_NUMBER_RE.match(lines[0]) or lines[0] in running):
        lines = _trim_blank_edges(lines[1:])
    while lines and (_PAGE_NUMBER_RE.match(lines[-1]) or lines[-1] in running):
        lines = _trim_blank_edges(lines[:-1])
    return lines


def _join_lines(lines: List[str]) -> str:
    """Undo the PDF's hard line wrapping inside one paragraph."""
    joined = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not joined:
            joined = line
        elif re.search(r"[A-Za-z]-$", joined):
            # Word split across a line break: "transla-" + "tion".
            joined = joined[:-1] + line
        elif _is_cjk(joined[-1]) or _is_cjk(line[0]):
            joined += line
        else:
            joined += " " + line
    return joined


def pdf_text_to_paragraphs(page_texts: List[str]) -> List[str]:
    """Turn per-page extracted text into paragraphs.

    Blank lines mark paragraph breaks within a page. Across a page
    break there's no blank line to go by, so a paragraph that didn't
    end in sentence-ending punctuation is assumed to continue onto the
    next page - the usual case for prose flowing over a boundary.
    """
    pages = [_trim_blank_edges(_normalize_lines(text)) for text in page_texts]
    running = _find_running_lines(pages)

    paragraphs: List[str] = []
    page_boundary = False

    for lines in pages:
        lines = _strip_page_furniture(lines, running)
        blocks = [b for b in re.split(r"\n\s*\n", "\n".join(lines)) if b.strip()]

        for i, block in enumerate(blocks):
            paragraph = _join_lines(block.split("\n"))
            if not paragraph:
                continue
            continues_previous = (
                i == 0
                and page_boundary
                and paragraphs
                and paragraphs[-1][-1] not in _TERMINAL_CHARS
            )
            if continues_previous:
                paragraphs[-1] = _join_lines([paragraphs[-1], paragraph])
            else:
                paragraphs.append(paragraph)

        if lines:
            page_boundary = True

    return paragraphs


def _page_text(page) -> str:
    """Layout mode keeps the vertical whitespace that tells paragraphs
    apart; the default mode throws it away and returns one line per text
    run, which would collapse a whole page into a single paragraph. It's
    the newer code path though, so fall back if it can't handle a page."""
    try:
        text = page.extract_text(extraction_mode="layout")
        if text and text.strip():
            return text
    except Exception:  # noqa: BLE001 - any layout failure falls back below
        pass
    try:
        return page.extract_text() or ""
    except Exception:  # noqa: BLE001 - one bad page shouldn't lose the file
        return ""


class PdfExtractor(Extractor):
    ext = "pdf"

    def extract(self, raw_bytes: bytes, filename: Optional[str] = None) -> ExtractedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ExtractionError("pypdf is not installed on the server.") from exc

        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
        except Exception as exc:  # noqa: BLE001 - pypdf raises several types
            raise ExtractionError(
                "Could not read this .pdf file. It may be corrupted or not a real PDF."
            ) from exc

        if reader.is_encrypted:
            # Plenty of PDFs are encrypted with an empty password and
            # open fine everywhere; those decrypt silently here.
            try:
                opened = reader.decrypt("")
            except Exception:  # noqa: BLE001
                opened = 0
            if not opened:
                raise ExtractionError(
                    "This PDF is password-protected. Remove the password and try again."
                )

        try:
            pages = list(reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(
                "Could not read the pages of this PDF. It may be corrupted."
            ) from exc

        paragraphs = pdf_text_to_paragraphs([_page_text(page) for page in pages])
        if not paragraphs:
            raise ExtractionError(
                "No text found in this PDF. If it's a scan or photos of pages, "
                "the text is an image - run it through OCR first, or paste the "
                "text in directly."
            )

        return ExtractedDocument(
            kind="plain",
            paragraphs=paragraphs,
            source_filename=filename,
            # D4: like .docx, .pdf input produces .txt output - there's
            # no PDF writer.
            source_ext="pdf",
        )
