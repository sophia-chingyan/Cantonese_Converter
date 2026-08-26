from typing import List, Tuple

from extractors.base import Cue
from .base import Writer


def format_srt(cues_with_text: List[Tuple[Cue, str]]) -> str:
    blocks = []
    for cue, text in cues_with_text:
        blocks.append(f"{cue.index}\n{cue.start} --> {cue.end}\n{text}")
    return "\n\n".join(blocks) + "\n"


class SrtWriter(Writer):
    ext = "srt"

    def write(self, cues_with_text: List[Tuple[Cue, str]]) -> bytes:
        return format_srt(cues_with_text).encode("utf-8")
