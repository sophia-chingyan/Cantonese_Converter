"""
The user's own dictionary: source terms (書面語) and the exact 粵文 the
translation must use for them. Stored as one JSON list, either in an
S3-compatible bucket (a Railway Bucket - see config.S3_*) or in a file
on disk. Both survive redeploys; the file only does so when it sits on a
Railway volume (see config._default_dictionary_path).
"""
import json
import os
import threading

# gunicorn runs one process with several threads, so two requests can
# edit the dictionary at once - serialize the read-modify-write.
_lock = threading.Lock()

_OBJECT_KEY = "dictionary.json"


class _FileBackend:
    def __init__(self, path: str):
        self.path = path

    def read(self):
        try:
            with open(self.path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def write(self, data: bytes) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, self.path)


class _BucketBackend:
    def __init__(self, config):
        # Imported lazily so file-only setups don't pay for boto3.
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket = config["S3_BUCKET"]
        self.client = boto3.client(
            "s3",
            endpoint_url=config["S3_ENDPOINT"],
            region_name=config["S3_REGION"] or "auto",
            aws_access_key_id=config["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=config["S3_SECRET_ACCESS_KEY"],
            config=BotoConfig(s3={"addressing_style": config["S3_URL_STYLE"]}),
        )

    def read(self):
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=_OBJECT_KEY)
        except self.client.exceptions.NoSuchKey:
            return None
        return obj["Body"].read()

    def write(self, data: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=_OBJECT_KEY, Body=data,
            ContentType="application/json; charset=utf-8",
        )


_backends = {}


def _backend(config):
    """One backend per storage location, built on first use. `config` is
    Flask's app.config (or any dict-like object with the same keys)."""
    if bucket_configured(config):
        key = ("s3", config["S3_ENDPOINT"], config["S3_BUCKET"])
        factory = lambda: _BucketBackend(config)  # noqa: E731
    else:
        key = ("file", config["DICTIONARY_PATH"])
        factory = lambda: _FileBackend(config["DICTIONARY_PATH"])  # noqa: E731
    if key not in _backends:
        _backends[key] = factory()
    return _backends[key]


def bucket_configured(config) -> bool:
    return all(config.get(name) for name in (
        "S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY",
    ))


def _parse(raw) -> list:
    if raw is None:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
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


def _read(config) -> list:
    """Raises if the storage can't be reached, so an edit never overwrites
    entries it failed to read."""
    return _parse(_backend(config).read())


def _write(config, entries: list) -> None:
    data = json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8")
    _backend(config).write(data)


def load_entries(config) -> list:
    """All entries, sorted by source term. Missing or unreadable storage
    is treated as an empty dictionary rather than breaking translation."""
    try:
        return _read(config)
    except Exception:  # noqa: BLE001 - OSError, botocore errors, ...
        return []


def add_entry(config, source: str, target: str) -> None:
    """Adds an entry, or replaces the target of an existing one with the
    same source term - adding again is how an entry is edited."""
    source, target = source.strip(), target.strip()
    if not source or not target:
        raise ValueError("Both the source term and its translation are required.")
    with _lock:
        entries = [e for e in _read(config) if e["source"] != source]
        entries.append({"source": source, "target": target})
        entries.sort(key=lambda e: e["source"])
        _write(config, entries)


def delete_entry(config, source: str) -> None:
    with _lock:
        entries = _read(config)
        kept = [e for e in entries if e["source"] != source]
        if len(kept) != len(entries):
            _write(config, kept)


def storage_is_persistent(config) -> bool:
    """False when the dictionary lives on the container filesystem, which
    Railway wipes on every redeploy."""
    if bucket_configured(config):
        return True
    if not config.get("ON_RAILWAY"):
        return True  # local runs: the file on disk is persistent enough
    volume = (config.get("RAILWAY_VOLUME_MOUNT_PATH") or "").rstrip("/")
    path = os.path.abspath(config["DICTIONARY_PATH"])
    return bool(volume) and (path == volume or path.startswith(volume + "/"))


def entries_in_text(entries: list, text: str) -> list:
    """Only the entries whose source term appears in `text` - plain
    substring match, since Chinese has no word boundaries. Longest terms
    first, so e.g. 香港大學 is listed before 香港."""
    found = [e for e in entries if e["source"] in text]
    found.sort(key=lambda e: len(e["source"]), reverse=True)
    return found
