"""
Common interface for every input format.

Whatever comes in - pasted text, a .txt upload, an .srt upload, a .docx
upload - gets normalized into one of two shapes:

  * "plain"  - a list of paragraphs (pasted text, .txt, .docx)
  * "srt"    - a list of Cue objects, each with its own timestamp

Everything downstream (chunker, translator, writer) works off this
shape instead of caring what the original file was. Per spec 5.2, a
new input format is added by writing one Extractor subclass here and
nothing else changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Cue:
    """One SRT subtitle cue. Index and timing pass through untouched
    per spec 5.3 - only `text` is ever sent to a translator."""
    index: int
    start: str
    end: str
    text: str


@dataclass
class ExtractedDocument:
    kind: str  # "plain" or "srt"
    paragraphs: List[str] = field(default_factory=list)
    cues: List[Cue] = field(default_factory=list)
    source_filename: Optional[str] = None
    source_ext: str = "txt"  # "txt" | "srt" | "docx" -- drives D4 output mapping

    def is_empty(self) -> bool:
        if self.kind == "srt":
            return len(self.cues) == 0
        return len(self.paragraphs) == 0


class ExtractionError(Exception):
    """Raised when the input can't be parsed into a usable document."""


def split_into_paragraphs(text: str) -> List[str]:
    """Split plain text into paragraphs on blank lines. Used by pasted
    text, .txt uploads, and .docx uploads alike so chunking behaves
    the same regardless of source."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ newlines to a paragraph break, split on blank lines.
    raw_parts = re.split(r"\n\s*\n", text.strip())
    paragraphs = [p.strip() for p in raw_parts if p.strip()]
    return paragraphs


class Extractor:
    """Base class. Subclasses implement extract() for one file format."""

    #: file extension this extractor handles, e.g. "txt"
    ext = ""

    def extract(self, raw_bytes: bytes, filename: Optional[str] = None) -> ExtractedDocument:
        raise NotImplementedError
