"""Tests RAG + ruteo API-vs-RAG + autorización.

Ejecutar:  python -m pytest tests/test_rag.py -v
Requiere:   python -m rag.ingestion  (ya genera rag/store.json)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.retriever import search_collection_policy
from app import agent as ag
from app.session import reset_session


def _mock_apis():
    ag.api_get_customer = lambda doc: {
        "0912345678": {"success": True, "customer": {
            "id": 123, "name": "Juan Pérez",
            "document": "0912345678", "phone": "0999999999"}},
        "0923456789": {"success": True, "customer": {
            "id": 456, "name": "María González",
            "document": "0923456789", "phone": "0988888888"}},
    }.get(doc, {"success": False, "error": "CUSTOMER_NOT_FOUND"})
    ag.api_get_debt = lambda cid: {"success": True, "debt": {
        "customer_id": cid, "total_debt": 620.0 if cid == 123 else 180.0}}
    ag.api_get_payment_plans = lambda cid: {"success": True, "payment_plans": {}}


def test_1_cuotas_45_dias_usa_rag():
    r = search_collection_policy("¿Puedo acceder a 3 cuotas si tengo 45 días de mora?")
    assert r["success"], r
    assert "3 cuotas" in r["results"][0]["text"]
    assert r["results"][0]["source"] == "politica_cobranza.txt"


def test_2_cuanto_debo_usa_api_no_rag():
    _mock_apis()
    # "¿Cuánto debo?" no tiene nada en la política -> NO_INFO (no debe usar RAG)
    r = search_collection_policy("¿Cuánto debo?")
    assert not r["success"] and r["error"] == "NO_INFO"
    # ...y la deuda sí sale por API con sesión autenticada
    s = reset_session("t2")
    ag._tool_get_customer(s, "0912345678")
    ag._tool_confirm_identity(s, "Juan Pérez")
    debt = ag._tool_get_my_debt(s)
    assert debt["success"] and debt["debt"]["total_debt"] == 620.0


def test_3_descuento_maximo_usa_rag():
    r = search_collection_policy("¿Qué descuento máximo indica la política?")
    assert r["success"], r
    assert "10%" in " ".join(c["text"] for c in r["results"])


def test_4_otro_customer_id_exige_auth_y_api():
    _mock_apis()
    # El RAG jamás devuelve datos transaccionales (montos, saldos):
    # aunque recupere un chunk por la palabra "cliente", no hay deuda.
    r = search_collection_policy("¿Cuánto debe el cliente 456?")
    blob = " ".join(c["text"] for c in r.get("results", []))
    assert "620" not in blob and "180" not in blob and "saldo" not in blob.lower()
    # Juan autenticado solo ve su propia deuda (123), nunca la del 456.
    s = reset_session("t4")
    ag._tool_get_customer(s, "0912345678")
    ag._tool_confirm_identity(s, "Juan")
    debt = ag._tool_get_my_debt(s)
    assert debt["debt"]["customer_id"] == 123  # nunca 456


def test_5_pregunta_fuera_de_docs():
    r = search_collection_policy("¿Aceptan bitcoin?")
    assert not r["success"] and r["error"] == "NO_INFO"
