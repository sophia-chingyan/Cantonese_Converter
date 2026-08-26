from .base import Writer
from .txt_writer import TxtWriter
from .srt_writer import SrtWriter, format_srt


def output_extension_for(source_ext: str) -> str:
    """D4: output mirrors input, except .docx -> .txt (no .docx writer)."""
    return "srt" if source_ext == "srt" else "txt"


__all__ = ["Writer", "TxtWriter", "SrtWriter", "format_srt", "output_extension_for"]
