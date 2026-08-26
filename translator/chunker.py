"""
Splits an ExtractedDocument into chunks close to D2's target size
(1,500 characters by default), without ever splitting a paragraph or
an SRT cue across two chunks (spec 5.3: a cue is atomic).

D5 locks chunk processing to sequential, not parallel - that's
enforced by the caller (jobs/runner.py) processing this list in
order, not by anything here.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from extractors.base import Cue, ExtractedDocument


@dataclass
class Chunk:
    kind: str  # "plain" or "srt"
    paragraphs: List[str] = field(default_factory=list)
    cues: List[Cue] = field(default_factory=list)

    def source_text(self) -> str:
        """The text actually sent to the translator for this chunk."""
        if self.kind == "srt":
            return "\n\n".join(cue.text for cue in self.cues)
        return "\n\n".join(self.paragraphs)


def _chunk_plain(paragraphs: List[str], target_size: int) -> List[Chunk]:
    chunks: List[Chunk] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len + 2 > target_size:
            chunks.append(Chunk(kind="plain", paragraphs=current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len + 2  # +2 for the paragraph-break join

    if current:
        chunks.append(Chunk(kind="plain", paragraphs=current))

    return chunks


def _chunk_srt(cues: List[Cue], target_size: int) -> List[Chunk]:
    chunks: List[Chunk] = []
    current: List[Cue] = []
    current_len = 0

    for cue in cues:
        cue_len = len(cue.text)
        if current and current_len + cue_len + 2 > target_size:
            chunks.append(Chunk(kind="srt", cues=current))
            current = []
            current_len = 0
        current.append(cue)
        current_len += cue_len + 2

    if current:
        chunks.append(Chunk(kind="srt", cues=current))

    return chunks


def chunk_document(doc: ExtractedDocument, target_size: Optional[int] = None) -> List[Chunk]:
    target_size = target_size or 1500
    if doc.kind == "srt":
        return _chunk_srt(doc.cues, target_size)
    return _chunk_plain(doc.paragraphs, target_size)
