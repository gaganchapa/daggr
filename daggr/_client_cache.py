from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

_client_cache: dict[str, Any] = {}
_api_memory_cache: dict[str, dict] = {}
_validated_set: set[str] = set()

_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "daggr"


def _is_hot_reload() -> bool:
    return os.environ.get("DAGGR_HOT_RELOAD") == "1"


def _get_cache_path(src: str) -> Path:
    src_hash = hashlib.md5(src.encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{src_hash}.json"


def _get_validated_file() -> Path:
    return _CACHE_DIR / "_validated.json"


def _load_validated_set() -> None:
    global _validated_set
    if _validated_set:
        return
    if not _is_hot_reload():
        return
    validated_file = _get_validated_file()
    if validated_file.exists():
        try:
            _validated_set = set(json.loads(validated_file.read_text()))
        except (json.JSONDecodeError, OSError):
            _validated_set = set()


def _save_validated_set() -> None:
    if not _is_hot_reload():
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _get_validated_file().write_text(json.dumps(list(_validated_set)))
    except OSError:
        pass


def is_validated(cache_key: tuple) -> bool:
    if not _is_hot_reload():
        return False
    _load_validated_set()
    return str(cache_key) in _validated_set


def mark_validated(cache_key: tuple) -> None:
    if not _is_hot_reload():
        return
    _load_validated_set()
    _validated_set.add(str(cache_key))
    _save_validated_set()


def get_api_info(src: str) -> dict | None:
    if src in _api_memory_cache:
        return _api_memory_cache[src]

    if not _is_hot_reload():
        return None

    cache_path = _get_cache_path(src)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            _api_memory_cache[src] = data
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def set_api_info(src: str, info: dict) -> None:
    _api_memory_cache[src] = info
    if not _is_hot_reload():
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _get_cache_path(src)
        cache_path.write_text(json.dumps(info))
    except OSError:
        pass


def get_client(src: str):
    return _client_cache.get(src)


def set_client(src: str, client) -> None:
    _client_cache[src] = client
