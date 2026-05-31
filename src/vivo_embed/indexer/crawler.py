"""Minden particio fajl crawler — diff-alapu, inkrementalis"""
from __future__ import annotations
import logging
import json
from pathlib import Path
from typing import Iterator, Tuple
from .. config import get
from . extractors import extract_text, get_collection, EXT_TO_COLLECTION
from . chunker import chunk_text

log = logging.getLogger("vivo_embed.crawler")
STATE_FILE = Path(r"C:\AI\data\vivo-embed\crawl_state.json")

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def _file_hash(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{stat.st_size}_{stat.st_mtime_ns}"
    except Exception:
        return ""

def get_drives() -> list[str]:
    cfg = get()["crawler"]
    if cfg.get("scan_drives") == "auto":
        import string
        return [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    return cfg.get("scan_drives", ["C:\\"])

def _should_skip(path: Path, exclude_dirs: list[str]) -> bool:
    path_str = str(path).lower()
    for excl in exclude_dirs:
        if excl.lower() in path_str:
            return True
    return False

def iter_files(incremental: bool = True) -> Iterator[Tuple[Path, str, list[str]]]:
    cfg     = get()["crawler"]
    exts    = set()
    for ext_list in cfg["extensions"].values():
        exts.update(ext_list)
    excl    = cfg.get("exclude_dirs", [])
    max_mb  = cfg.get("max_file_size_mb", 50) * 1024 * 1024
    min_b   = cfg.get("min_file_size_bytes", 100)
    state   = _load_state() if incremental else {}
    new_state = dict(state)
    priority  = [Path(p) for p in cfg.get("priority_paths", []) if Path(p).exists()]
    drives    = [Path(d) for d in get_drives()]
    all_roots = priority + [d for d in drives if d not in priority]
    processed = 0
    for root in all_roots:
        try:
            for fpath in root.rglob("*"):
                if not fpath.is_file():
                    continue
                if _should_skip(fpath, excl):
                    continue
                if fpath.suffix.lower() not in exts:
                    continue
                try:
                    size = fpath.stat().st_size
                except Exception:
                    continue
                if size > max_mb or size < min_b:
                    continue
                fhash = _file_hash(fpath)
                key   = str(fpath)
                if incremental and state.get(key) == fhash:
                    continue
                text = extract_text(fpath)
                if not text or len(text.strip()) < 50:
                    continue
                chunks = chunk_text(text)
                if not chunks:
                    continue
                col = get_collection(fpath)
                new_state[key] = fhash
                processed += 1
                if processed % 100 == 0:
                    log.info(f"Feldolgozva: {processed} fajl...")
                    _save_state(new_state)
                yield fpath, col, chunks
        except PermissionError:
            log.debug(f"Nincs jogosultsag: {root}")
        except Exception as e:
            log.warning(f"Crawler hiba ({root}): {e}")
    _save_state(new_state)
    log.info(f"Crawler kesz. Feldolgozott fajlok: {processed}")
