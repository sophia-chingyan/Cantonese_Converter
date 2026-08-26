from .base import Writer


class TxtWriter(Writer):
    ext = "txt"

    def write(self, full_text: str) -> bytes:
        return full_text.encode("utf-8")
