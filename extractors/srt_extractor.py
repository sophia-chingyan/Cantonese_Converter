import re
from typing import List, Optional

from .base import Extractor, ExtractedDocument, ExtractionError, Cue

_TIMING_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})(.*)"
)


def parse_srt(text: str) -> List[Cue]:
    """Parse SRT content into a list of Cue objects. Tolerant of the
    common real-world variations (missing/duplicate index lines, CRLF,
    a trailing BOM, extra blank lines) since subtitle files in the
    wild are rarely perfectly formed."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", text.strip())

    cues: List[Cue] = []
    auto_index = 1

    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != "" or True]
        lines = block.split("\n")
        if not lines:
            continue

        idx = 0
        # First line: cue index, if present and numeric.
        cue_index: Optional[int] = None
        first_line = lines[0].strip()
        if re.fullmatch(r"\d+", first_line):
            cue_index = int(first_line)
            idx = 1

        if idx >= len(lines):
            continue

        timing_match = _TIMING_RE.match(lines[idx].strip())
        if not timing_match:
            # Not a valid cue block (e.g. stray metadata) - skip it
            # rather than aborting the whole file.
            continue

        start, end = timing_match.group(1), timing_match.group(2)
        text_lines = lines[idx + 1:]
        cue_text = "\n".join(text_lines).strip()

        if cue_index is None:
            cue_index = auto_index

        cues.append(Cue(index=cue_index, start=start, end=end, text=cue_text))
        auto_index = cue_index + 1

    if not cues:
        raise ExtractionError(
            "No valid subtitle cues found. Check that this is a standard .srt file."
        )
    return cues


class SrtExtractor(Extractor):
    ext = "srt"

    def extract(self, raw_bytes: bytes, filename: Optional[str] = None) -> ExtractedDocument:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ExtractionError(
                "Could not read this file as UTF-8 text. Please save it as UTF-8 and try again."
            ) from exc

        cues = parse_srt(text)
        return ExtractedDocument(
            kind="srt",
            cues=cues,
            source_filename=filename,
            source_ext="srt",
        )
