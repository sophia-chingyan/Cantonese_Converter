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
    "- Translate the content faithfully - do not add, omit, expand, "
    "summarise or explain anything. Every idea in the source must appear "
    "in the translation, and nothing that is not in the source may be "
    "added.\n"
    "- Return ONLY the translated text. No explanations, no notes, no "
    "commentary, no markdown formatting, no restating the instructions."
)

# Extra rules for SRT chunks only. The translated subtitles are read aloud
# to build a new audio track that has to line up with the original audio,
# so each block has to stay close to its original in length. Stating the
# block count also makes the cue-mapping contract explicit - jobs/runner.py
# discards a whole chunk's translation when the block count doesn't match.
SRT_RULES = (
    "This text comes from a subtitle (SRT) file. Each blank-line-separated "
    "block below is one subtitle cue. The translation will be read aloud to "
    "produce a new audio track that must match the length of the original "
    "audio, so length matters as much as meaning.\n"
    "- Return exactly {cue_count} blocks, in the same order, separated by a "
    "single blank line. Never merge, split, reorder, add or drop a block.\n"
    "- Keep each block's translation as close as possible in length "
    "(character count) to its own original block, so it takes about the "
    "same time to say aloud.\n"
    "- Do not pad a short block with filler words and do not cut anything "
    "out of a long one - just avoid making a block noticeably longer or "
    "shorter than its original."
)


def build_prompt(
    text: str,
    previous_context: Optional[str] = None,
    kind: str = "plain",
    cue_count: Optional[int] = None,
) -> str:
    """D3: when previous_context is given (the tail of the previous
    chunk's translated output), it's included as a style anchor so
    register stays consistent across chunks - without asking the model
    to repeat it.

    For SRT chunks (kind="srt" with a cue_count), the subtitle rules are
    added on top of the shared preamble: one block per cue, and each block
    kept close to its original in length so the synthesised audio matches
    the original timing."""
    parts = [PREAMBLE]

    if kind == "srt" and cue_count:
        parts.append(SRT_RULES.format(cue_count=cue_count))

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
