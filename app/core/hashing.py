"""Content hashing used to identify a book independently of its path.

A book is identified by the hash of its bytes, not by its file name, so moving
or renaming a PDF keeps its notes and bookmarks attached (see
:mod:`app.core.database`). The digest is always returned as lowercase hex so the
value stored in SQLite is canonical and comparable with ``=``.
"""

import hashlib
from pathlib import Path
from typing import Callable

# Hashers allowed by ``books.hash_algo`` in ``schema.sql``.
_HASHERS: dict[str, Callable[[], "hashlib._Hash"]] = {
    "sha256": hashlib.sha256,
    "blake2b": hashlib.blake2b,
}

# SHA-256 is the identity algorithm the phase specification asks for.
DEFAULT_ALGORITHM = "sha256"

# Read the file in blocks so hashing a large PDF does not load it into memory.
_CHUNK_SIZE = 1024 * 1024


def supported_algorithms() -> tuple[str, ...]:
    """Return the hash algorithm names the database schema accepts."""
    return tuple(_HASHERS)


def content_hash(file_path: Path, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Return the lowercase hex digest of a file's contents.

    Raises:
        ValueError: when ``algorithm`` is not one of the schema's algorithms.
        OSError: when the file cannot be read.
    """
    try:
        hasher_factory = _HASHERS[algorithm]
    except KeyError:
        raise ValueError(
            f"Unsupported hash algorithm {algorithm!r}; expected one of {supported_algorithms()}"
        ) from None

    digest = hasher_factory()
    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    # ``hexdigest`` is already lowercase; ``lower`` makes the invariant explicit.
    return digest.hexdigest().lower()
