"""Ingestión RAG: carga .txt, trocea, genera TF-IDF y guarda store local.

Uso:
    python -m rag.ingestion
"""

import json
import re
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

BASE = Path(__file__).resolve().parent
DOCUMENTS = BASE / "documents"
STORE = BASE / "store.json"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


def norm_token(token: str) -> str:
    """Minúsculas, sin tildes, singular aproximado (descuentos->descuento)."""
    t = unicodedata.normalize("NFD", token.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    return [norm_token(t) for t in re.findall(r"\w+", text) if norm_token(t)]


def chunk_text(text: str) -> list[str]:
    """Una regla por línea + párrafos largos partidos con overlap."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks: list[str] = []
    for line in lines:
        if len(line) <= CHUNK_SIZE:
            chunks.append(line)
            continue
        start = 0
        while start < len(line):
            chunks.append(line[start:start + CHUNK_SIZE].strip())
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c]


def ingest() -> dict:
    files = sorted(DOCUMENTS.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No hay documentos en {DOCUMENTS}")
    chunks: list[dict] = []
    for path in files:
        for text in chunk_text(path.read_text(encoding="utf-8")):
            chunks.append({
                "chunk_id": len(chunks),
                "source": path.name,
                "text": text,
            })
    vectorizer = TfidfVectorizer(tokenizer=tokenize, preprocessor=None, lowercase=False)
    matrix = vectorizer.fit_transform([c["text"] for c in chunks])
    STORE.write_text(json.dumps({
        "chunks": chunks,
        "vocabulary": vectorizer.vocabulary_,
        "idf": vectorizer.idf_.tolist(),
        "vectors": matrix.toarray().tolist(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(chunks)} chunks de {len(files)} documento(s) -> {STORE.name}")
    return {"chunks": len(chunks), "documents": len(files)}


if __name__ == "__main__":
    ingest()
