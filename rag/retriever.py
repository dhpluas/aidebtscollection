"""Retriever RAG: busca chunks relevantes con TF-IDF + coseno.

Solo conocimiento documental (políticas). Nunca datos
transaccionales (deuda, saldo, cliente): eso va por API.
"""

import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
STORE = BASE / "store.json"

TOP_K = 3
MIN_SCORE = 0.15


def _load_store() -> dict:
    if not STORE.exists():
        raise FileNotFoundError(
            f"No existe {STORE.name}. Ejecuta: python -m rag.ingestion"
        )
    return json.loads(STORE.read_text(encoding="utf-8"))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _vectorize_query(query: str, vocabulary: dict, idf: list[float]) -> list[float]:
    from rag.ingestion import tokenize
    vec = [0.0] * len(idf)
    for t in tokenize(query):
        idx = vocabulary.get(t)
        if idx is not None:
            vec[idx] += 1.0
    # tf * idf
    return [tf * w for tf, w in zip(vec, idf)]


def search(query: str, top_k: int = TOP_K) -> list[dict]:
    """Devuelve chunks relevantes con trazabilidad o [] si no hay nada."""
    store = _load_store()
    qvec = _vectorize_query(query, store["vocabulary"], store["idf"])
    scored = []
    for chunk, vec in zip(store["chunks"], store["vectors"]):
        score = _cosine(qvec, vec)
        if score >= MIN_SCORE:
            scored.append({**chunk, "score": round(score, 3)})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]


def search_collection_policy(query: str) -> dict:
    """Herramienta conceptual del agente: solo recupera, nunca inventa."""
    try:
        results = search(query)
    except FileNotFoundError as exc:
        return {"success": False, "error": "STORE_NOT_FOUND", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": "RETRIEVER_ERROR", "message": str(exc)}
    if not results:
        return {
            "success": False,
            "error": "NO_INFO",
            "message": "No encontré información suficiente en la política de cobranza.",
        }
    return {"success": True, "results": results}
