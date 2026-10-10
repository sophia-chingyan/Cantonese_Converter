"""
The user's own dictionary: source terms (書面語) and the exact 粵文 the
translation must use for them. Stored as one JSON list on disk so it
survives redeploys whenever a Railway volume is attached (see
config._default_dictionary_path).
"""
import json
import os
import threading

# gunicorn runs one process with several threads, so two requests can
# edit the file at once - serialize the read-modify-write.
_lock = threading.Lock()


def load_entries(path: str) -> list:
    """All entries, sorted by source term. A missing or unreadable file
    is treated as an empty dictionary rather than breaking translation."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    entries = [
        {"source": e["source"], "target": e["target"]}
        for e in data
        if isinstance(e, dict)
        and isinstance(e.get("source"), str) and e["source"]
        and isinstance(e.get("target"), str) and e["target"]
    ]
    entries.sort(key=lambda e: e["source"])
    return entries


def _write(path: str, entries: list) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def add_entry(path: str, source: str, target: str) -> None:
    """Adds an entry, or replaces the target of an existing one with the
    same source term - adding again is how an entry is edited."""
    source, target = source.strip(), target.strip()
    if not source or not target:
        raise ValueError("Both the source term and its translation are required.")
    with _lock:
        entries = [e for e in load_entries(path) if e["source"] != source]
        entries.append({"source": source, "target": target})
        entries.sort(key=lambda e: e["source"])
        _write(path, entries)


def delete_entry(path: str, source: str) -> None:
    with _lock:
        entries = load_entries(path)
        kept = [e for e in entries if e["source"] != source]
        if len(kept) != len(entries):
            _write(path, kept)


def entries_in_text(entries: list, text: str) -> list:
    """Only the entries whose source term appears in `text` - plain
    substring match, since Chinese has no word boundaries. Longest terms
    first, so e.g. 香港大學 is listed before 香港."""
    found = [e for e in entries if e["source"] in text]
    found.sort(key=lambda e: len(e["source"]), reverse=True)
    return found
