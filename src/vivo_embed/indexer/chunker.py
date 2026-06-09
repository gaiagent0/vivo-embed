"""Magyar-tudatos szoveg chunker"""
from __future__ import annotations
import re
from typing import List

_ABBREVS = {
    "dr","mr","mrs","ms","prof","jr","sr",
    "stb","kb","ill","pl","db","szerk","ford",
    "kiad","ua","uo","i.e","i.sz","u.n","vs",
    "tel","fax","sz","nr","no","max","min",
}

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    if not text or not text.strip():
        return []
    text = _clean(text)
    if len(text) <= chunk_size:
        return [text.strip()]
    sentences = _split_sentences(text)
    chunks, current, current_len = [], [], 0
    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len > chunk_size and current:
            chunk = " ".join(current).strip()
            if chunk:
                chunks.append(chunk)
            tail = chunk[-overlap:] if len(chunk) > overlap else chunk
            current = [tail]
            current_len = len(tail)
        current.append(sent)
        current_len += sent_len + 1
    if current:
        tail = " ".join(current).strip()
        if tail:
            chunks.append(tail)
    return [c for c in chunks if len(c) > 20]

def _clean(text: str) -> str:
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def _split_sentences(text: str) -> List[str]:
    paragraphs = re.split(r'\n{2,}', text)
    sentences = []
    for para in paragraphs:
        sentences.extend(_split_para(para))
    return [s.strip() for s in sentences if s.strip()]

def _split_para(text: str) -> List[str]:
    tokens = re.split(r'(\s+)', text)
    result, current = [], []
    for i, tok in enumerate(tokens):
        current.append(tok)
        if re.search(r'[.!?]$', tok.rstrip()):
            word = tok.rstrip('.!?').lower()
            if word in _ABBREVS:
                continue
            next_real = next((t for t in tokens[i+1:] if t.strip()), "")
            if next_real and next_real[0].isupper():
                chunk = "".join(current).strip()
                if chunk:
                    result.append(chunk)
                current = []
    if current:
        tail = "".join(current).strip()
        if tail:
            result.append(tail)
    final = []
    for chunk in result if result else [text]:
        if len(chunk) > 800:
            final.extend(_split_by_length(chunk, 600))
        else:
            final.append(chunk)
    return final

def _split_by_length(text: str, max_len: int) -> List[str]:
    parts, start = [], 0
    while start < len(text):
        end = start + max_len
        if end >= len(text):
            parts.append(text[start:])
            break
        cut = text.rfind(' ', start, end)
        if cut == -1:
            cut = end
        parts.append(text[start:cut])
        start = cut + 1
    return parts
