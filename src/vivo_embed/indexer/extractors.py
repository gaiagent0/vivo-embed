"""Fajl szoveg kinyerok — PDF, DOCX, MD, TXT, kod, YAML, JSON"""
from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger("vivo_embed.extractors")

EXT_TO_COLLECTION = {
    ".pdf": "docs", ".docx": "docs", ".doc": "docs",
    ".txt": "docs", ".rtf": "docs",
    ".py": "code", ".ts": "code", ".js": "code",
    ".ps1": "code", ".bat": "code", ".sh": "code",
    ".rs": "code", ".go": "code", ".cs": "code",
    ".md": "notes", ".markdown": "notes", ".rst": "notes",
    ".yaml": "system", ".yml": "system", ".json": "system",
    ".toml": "system", ".ini": "system", ".env": "system",
    ".conf": "system",
}

def get_collection(path: Path) -> str:
    return EXT_TO_COLLECTION.get(path.suffix.lower(), "docs")

def extract_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return _pdf(path)
        elif ext in (".docx", ".doc"):
            return _docx(path)
        elif ext == ".json":
            return _json(path)
        else:
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log.warning(f"Kinyeres sikertelen: {path} - {e}")
        return None

def _pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            texts = [p.extract_text() for p in pdf.pages if p.extract_text()]
        return "\n\n".join(texts)
    except ImportError:
        try:
            import pypdf
            r = pypdf.PdfReader(str(path))
            return "\n\n".join(p.extract_text() or "" for p in r.pages)
        except Exception:
            return None

def _docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return None

def _json(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return json.dumps(data, ensure_ascii=False, indent=2)[:8000]
    except Exception:
        return path.read_text(encoding="utf-8", errors="replace")
