from typing import Optional

# Spec 5.4 - fixed preamble, identical regardless of which provider is active.
PREAMBLE = (
    "You are a professional translator converting Standard Written Chinese "
    "(書面語) into genuine written Cantonese (粵文).\n\n"
    "Rules:\n"
    "- Use authentic Cantonese grammar and vocabulary "
    "(係 / 唔 / 嘅 / 咗 / 佢 / 喺 / 冇), not Standard Chinese with a few "
    "Cantonese words swapped in.\n"
    "- Output only in Traditional Chinese characters. Never output "
    "Simplified Chinese.\n"
    "- Preserve any English words or phrases exactly as written - do not "
    "translate them.\n"
    "- Preserve the original line breaks and paragraph structure.\n"
    "- Return ONLY the translated text. No explanations, no notes, no "
    "commentary, no markdown formatting, no restating the instructions."
)


def build_prompt(text: str, previous_context: Optional[str] = None) -> str:
    """D3: when previous_context is given (the tail of the previous
    chunk's translated output), it's included as a style anchor so
    register stays consistent across chunks - without asking the model
    to repeat it."""
    parts = [PREAMBLE]

    if previous_context:
        parts.append(
            "For style consistency, here is the end of the previously "
            "translated section (reference only - do not repeat it in "
            "your answer):\n" + previous_context
        )

    parts.append("Now translate the following text:\n" + text)
    return "\n\n".join(parts)


def context_tail(translated_text: str, max_chars: int) -> str:
    """Last N characters of a chunk's translated output, used as the
    next chunk's style anchor (D3)."""
    if not translated_text:
        return ""
    return translated_text[-max_chars:]
