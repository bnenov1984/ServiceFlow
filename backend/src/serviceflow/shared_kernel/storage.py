"""Storage port (ADR-007): domain/API reference attachments only by storage key,
never by path. Local filesystem is the dev/local-edition adapter; the S3-compatible
adapter (Etap 3, ADR-017/ADR-007 amendment) implements the same Protocol."""

from functools import lru_cache
from pathlib import Path
from typing import Protocol


class StoragePort(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalFilesystemStorage:
    """Content-addressed layout (ADR-007): sharded by the key's first 4 hex chars
    so no directory ever holds more than a few thousand files."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root / key[:2] / key[2:4] / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():  # content-addressed: identical bytes, nothing to do
            path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


@lru_cache
def get_local_storage(root: str) -> LocalFilesystemStorage:
    return LocalFilesystemStorage(Path(root))
