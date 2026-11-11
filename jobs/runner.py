"""
Runs one translation job to completion in a background thread, so the
HTTP request that kicked it off returns immediately with a job_id and
the browser polls for progress (spec 5.1).

D5 locks chunk processing to sequential - chunks are translated one at
a time, in order, in the plain for-loop below. That's what makes D3's
context carryover possible: each chunk's prompt includes the tail of
the previous chunk's translated output.
"""
import re
import threading

from dictionary import entries_in_text, load_entries
from extractors.base import ExtractedDocument
from translator import (
    build_prompt,
    chunk_document,
    completeness_score,
    context_tail,
    get_client,
    incompleteness_reason,
    translate_with_retries,
    TranslatorError,
)
from writers import format_srt
from . import registry

# Section 7: a failed chunk is marked clearly in the output rather than
# silently dropped or misattributed to the wrong subtitle timestamp.
FAILURE_MARKER = "\u26a0\ufe0f [TRANSLATION FAILED \u2014 original text below, please fix by hand]\n"
# A translation that still looks shorter than its source after every
# retry: the best attempt is kept, followed by the original so the
# missing sentences can be found and fixed by hand.
INCOMPLETE_MARKER = (
    "\u26a0\ufe0f [TRANSLATION MAY BE INCOMPLETE \u2014 compare with the "
    "original below and fix by hand]\n"
)
ORIGINAL_LABEL = "\n\n[ORIGINAL]\n"

# Plain text: how many times a whole chunk is re-sent when the answer
# looks like it skipped sentences, before falling back to translating
# the chunk one paragraph at a time.
CHUNK_COMPLETENESS_ATTEMPTS = 2
PARAGRAPH_COMPLETENESS_ATTEMPTS = 2


def start_job(doc: ExtractedDocument, provider: str, config) -> str:
    """Creates the job record and kicks off the background thread.
    Returns the job_id immediately. `config` is Flask's dict-style
    app.config (or any dict-like object)."""
    chunks = chunk_document(doc, target_size=config["CHUNK_SIZE_CHARS"])
    job_id = registry.create_job(
        total_chunks=len(chunks),
        kind=doc.kind,
        source_ext=doc.source_ext,
        source_filename=doc.source_filename,
    )
    # Snapshot the dictionary now, so edits made while the job runs
    # don't change its wording halfway through.
    dictionary = load_entries(config)

    thread = threading.Thread(
        target=_run, args=(job_id, doc, chunks, provider, config, dictionary),
        daemon=True,
    )
    thread.start()
    return job_id


def _run(job_id, doc: ExtractedDocument, chunks, provider: str, config, dictionary) -> None:
    # Any unexpected exception in a background thread would otherwise
    # vanish and leave the browser polling a job stuck on "running".
    try:
        _translate_all(job_id, doc, chunks, provider, config, dictionary)
    except Exception as exc:  # noqa: BLE001
        registry.update_job(job_id, status="error", error=f"Translation job failed: {exc}")


def _translate_all(job_id, doc: ExtractedDocument, chunks, provider: str, config,
                   dictionary) -> None:
    client = get_client(provider, config)

    previous_context = None
    plain_pieces = []
    srt_cue_results = []  # list[(Cue, str)]
    any_failed = False

    for chunk in chunks:
        source_text = chunk.source_text()
        prompt_context = previous_context
        prompt = build_prompt(
            source_text,
            previous_context,
            kind=chunk.kind,
            cue_count=len(chunk.cues),
            glossary=entries_in_text(dictionary, source_text),
            paragraph_count=len(chunk.paragraphs),
        )

        translated = None
        chunk_ok = True
        try:
            translated = translate_with_retries(client, prompt)
            previous_context = context_tail(translated, config["CONTEXT_CARRYOVER_CHARS"])
        except TranslatorError as exc:
            chunk_ok = False
            registry.update_job(job_id, last_chunk_error=str(exc))
            previous_context = None  # don't chain a style anchor off a failure

        if chunk.kind == "srt":
            if chunk_ok:
                # Models sometimes separate blocks with extra blank lines
                # or whitespace-only lines; treat any of those as one break.
                segments = [s.strip() for s in re.split(r"\n[ \t]*\n\s*", translated.strip())]
                if len(segments) != len(chunk.cues):
                    # Can't safely map segments back to individual cues -
                    # keep every cue's original text rather than risk
                    # attaching translated text to the wrong timestamp.
                    chunk_ok = False
                    registry.update_job(
                        job_id,
                        last_chunk_error=(
                            f"Model returned {len(segments)} subtitle blocks "
                            f"for {len(chunk.cues)} cues."
                        ),
                    )
            if chunk_ok:
                for cue, seg in zip(chunk.cues, segments):
                    srt_cue_results.append((cue, seg))
            else:
                for i, cue in enumerate(chunk.cues):
                    text = cue.text
                    if i == 0:
                        text = FAILURE_MARKER + text
                    srt_cue_results.append((cue, text))
        else:
            if chunk_ok:
                translated, complete = _ensure_complete_plain(
                    job_id, client, chunk, source_text, translated,
                    prompt_context, dictionary, config,
                )
                previous_context = context_tail(translated, config["CONTEXT_CARRYOVER_CHARS"])
                if not complete:
                    chunk_ok = False
                    previous_context = None  # marked text isn't a style anchor
                plain_pieces.append(translated)
            else:
                plain_pieces.append(FAILURE_MARKER + source_text)

        if not chunk_ok:
            any_failed = True
        registry.increment_progress(job_id, failed=not chunk_ok)

    if doc.kind == "srt":
        preview_text = format_srt(srt_cue_results)
    else:
        preview_text = "\n\n".join(plain_pieces)

    registry.update_job(
        job_id,
        status="done",
        preview_text=preview_text,
        has_failures=any_failed,
    )


def _translate_checked(client, source_text, previous_context, dictionary,
                       paragraph_count, attempts, first=None):
    """Translate plain text, re-sending it while the answer looks like it
    skipped sentences. Returns (best_translation, reason_or_None).
    `first` is an answer already received for this exact prompt."""
    prompt = build_prompt(
        source_text,
        previous_context,
        glossary=entries_in_text(dictionary, source_text),
        paragraph_count=paragraph_count,
    )
    best, best_score, reason = None, -1.0, None
    for attempt in range(attempts):
        if attempt == 0 and first is not None:
            candidate = first
        else:
            candidate = translate_with_retries(client, prompt)
        reason = incompleteness_reason(source_text, candidate)
        if reason is None:
            return candidate, None
        score = completeness_score(source_text, candidate)
        if score > best_score:
            best, best_score = candidate, score
    return best, incompleteness_reason(source_text, best)


def _ensure_complete_plain(job_id, client, chunk, source_text, translated,
                           previous_context, dictionary, config):
    """Plain-text chunks have no structural check like SRT's block count,
    so a model that quietly skips a sentence would otherwise go
    unnoticed. Retry the whole chunk, then fall back to one paragraph at
    a time (short inputs are far less likely to lose sentences). Any
    paragraph that still looks short is kept but marked for review.

    Returns (text, complete)."""
    paragraphs = chunk.paragraphs
    single = len(paragraphs) <= 1
    attempts = CHUNK_COMPLETENESS_ATTEMPTS + (PARAGRAPH_COMPLETENESS_ATTEMPTS if single else 0)
    try:
        best, reason = _translate_checked(
            client, source_text, previous_context, dictionary,
            len(paragraphs), attempts, first=translated,
        )
    except TranslatorError:
        # A retry failed outright - keep the first answer and let the
        # checks below decide whether it needs marking.
        best, reason = translated, incompleteness_reason(source_text, translated)
    if reason is None:
        return best, True
    if single:
        registry.update_job(job_id, last_chunk_error=reason)
        return INCOMPLETE_MARKER + best + ORIGINAL_LABEL + source_text, False

    pieces = []
    complete = True
    context = previous_context
    for para in paragraphs:
        try:
            para_best, para_reason = _translate_checked(
                client, para, context, dictionary, 1,
                PARAGRAPH_COMPLETENESS_ATTEMPTS,
            )
        except TranslatorError as exc:
            registry.update_job(job_id, last_chunk_error=str(exc))
            pieces.append(FAILURE_MARKER + para)
            complete = False
            context = None
            continue
        if para_reason is None:
            pieces.append(para_best)
        else:
            registry.update_job(job_id, last_chunk_error=para_reason)
            pieces.append(INCOMPLETE_MARKER + para_best + ORIGINAL_LABEL + para)
            complete = False
        context = context_tail(para_best, config["CONTEXT_CARRYOVER_CHARS"])
    return "\n\n".join(pieces), complete
