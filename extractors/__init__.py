from .base import Cue, ExtractedDocument, ExtractionError, Extractor, split_into_paragraphs
from .txt_extractor import TxtExtractor, extract_pasted_text
from .srt_extractor import SrtExtractor
from .docx_extractor import DocxExtractor

REGISTRY = {
    "txt": TxtExtractor(),
    "srt": SrtExtractor(),
    "docx": DocxExtractor(),
}


def extract_upload(raw_bytes: bytes, filename: str) -> ExtractedDocument:
    """Dispatch an uploaded file to the extractor matching its extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extractor = REGISTRY.get(ext)
    if extractor is None:
        raise ExtractionError(
            f"Unsupported file type '.{ext}'. Supported: .txt, .srt, .docx"
        )
    return extractor.extract(raw_bytes, filename)


__all__ = [
    "Cue",
    "ExtractedDocument",
    "ExtractionError",
    "Extractor",
    "split_into_paragraphs",
    "TxtExtractor",
    "SrtExtractor",
    "DocxExtractor",
    "extract_pasted_text",
    "extract_upload",
    "REGISTRY",
    "extract_upload",
]
