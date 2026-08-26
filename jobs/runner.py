"""
Runs one translation job to completion in a background thread, so the
HTTP request that kicked it off returns immediately with a job_id and
the browser polls for progress (spec 5.1).

D5 locks chunk processing to sequential - chunks are translated one at
a time, in order, in the plain for-loop below. That's what makes D3's
context carryover possible: each chunk's prompt includes the tail of
the previous chunk's translated output.
"""
import threading

from extractors.base import ExtractedDocument
from translator import (
    build_prompt,
    chunk_document,
    context_tail,
    get_client,
    translate_with_retries,
    TranslatorError,
)
from writers import format_srt
from . import registry

# Section 7: a failed chunk is marked clearly in the output rather than
# silently dropped or misattributed to the wrong subtitle timestamp.
FAILURE_MARKER = "\u26a0\ufe0f [TRANSLATION FAILED \u2014 original text below, please fix by hand]\n"


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

    thread = threading.Thread(
        target=_run, args=(job_id, doc, chunks, provider, config), daemon=True
    )
    thread.start()
    return job_id


def _run(job_id, doc: ExtractedDocument, chunks, provider: str, config) -> None:
    try:
        client = get_client(provider, config)
    except Exception as exc:  # noqa: BLE001
        registry.update_job(job_id, status="error", error=str(exc))
        return

    previous_context = None
    plain_pieces = []
    srt_cue_results = []  # list[(Cue, str)]
    any_failed = False

    for chunk in chunks:
        source_text = chunk.source_text()
        prompt = build_prompt(source_text, previous_context)

        translated = None
        chunk_ok = True
        try:
            translated = translate_with_retries(client, prompt)
            previous_context = context_tail(translated, config["CONTEXT_CARRYOVER_CHARS"])
        except TranslatorError:
            chunk_ok = False
            previous_context = None  # don't chain a style anchor off a failure

        if chunk.kind == "srt":
            if chunk_ok:
                segments = [s.strip() for s in translated.split("\n\n")]
                if len(segments) != len(chunk.cues):
                    # Can't safely map segments back to individual cues -
                    # keep every cue's original text rather than risk
                    # attaching translated text to the wrong timestamp.
                    chunk_ok = False
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
