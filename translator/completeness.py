"""
Detects a translation that silently dropped part of its source.

Models - especially small "lite" ones - sometimes skip a sentence or a
whole paragraph and still return a fluent answer, so nothing upstream
notices. Written Cantonese is almost always at least as long as the
書面語 it comes from (嘅 / 咗 / 喺 are added, little is removed), and
the sentence boundaries survive translation. So a translation that is
clearly shorter, or has clearly fewer sentence-ending marks, than
its source has almost certainly lost something.

The thresholds are deliberately loose: a false alarm only costs one
extra API call, while a missed omission ends up in the final output.
"""
import re
from typing import Optional

# Minimum translated / source ratios before we call the result incomplete.
MIN_LENGTH_RATIO = 0.8
MIN_SENTENCE_RATIO = 0.8
# Below this many sentence marks the sentence ratio is too noisy to use
# (one short heading would swing it by 50%).
MIN_SENTENCES_FOR_CHECK = 4

_SENTENCE_END = re.compile(r"[。！？!?；;]+")


def _visible_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _sentence_count(text: str) -> int:
    return len(_SENTENCE_END.findall(text))


def completeness_score(source: str, translated: str) -> float:
    """Single number for picking the most complete of several attempts:
    the worse of the length and sentence ratios (capped at 1)."""
    src_len = _visible_len(source) or 1
    ratios = [_visible_len(translated) / src_len]
    src_sentences = _sentence_count(source)
    if src_sentences:
        ratios.append(_sentence_count(translated) / src_sentences)
    return min(1.0, *ratios)


def incompleteness_reason(source: str, translated: str) -> Optional[str]:
    """None if the translation looks complete, otherwise a short reason
    (shown to the user as the job's last chunk error)."""
    src_len = _visible_len(source)
    out_len = _visible_len(translated)
    if src_len and out_len < src_len * MIN_LENGTH_RATIO:
        return (f"Translation looks incomplete: {out_len} characters "
                f"for {src_len} in the source.")

    src_sentences = _sentence_count(source)
    out_sentences = _sentence_count(translated)
    if (src_sentences >= MIN_SENTENCES_FOR_CHECK
            and out_sentences < src_sentences * MIN_SENTENCE_RATIO):
        return (f"Translation looks incomplete: {out_sentences} sentences "
                f"for {src_sentences} in the source.")

    return None
