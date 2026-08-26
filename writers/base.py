class Writer:
    """D4: output format mirrors input (.txt->.txt, .srt->.srt,
    .docx->.txt). One Writer subclass per output format."""

    ext = ""

    def write(self, *args, **kwargs) -> bytes:
        raise NotImplementedError
