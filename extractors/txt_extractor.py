from typing import Optional

from .base import Extractor, ExtractedDocument, ExtractionError, split_into_paragraphs


class TxtExtractor(Extractor):
    ext = "txt"

    def extract(self, raw_bytes: bytes, filename: Optional[str] = None) -> ExtractedDocument:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ExtractionError(
                    "Could not read this file as UTF-8 text. Please save it as UTF-8 and try again."
                ) from exc

        paragraphs = split_into_paragraphs(text)
        return ExtractedDocument(
            kind="plain",
            paragraphs=paragraphs,
            source_filename=filename,
            source_ext="txt",
        )


def extract_pasted_text(text: str) -> ExtractedDocument:
    """R1: text pasted directly into the browser, not uploaded as a file."""
    paragraphs = split_into_paragraphs(text)
    return ExtractedDocument(
        kind="plain",
        paragraphs=paragraphs,
        source_filename=None,
        source_ext="txt",
    )
