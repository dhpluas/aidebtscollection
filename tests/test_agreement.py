"""Tests del flujo de acuerdos + webhook (sin costo LLM).

Ejecutar:  python -m pytest tests/test_agreement.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import app.main as main_mod
from app import agent as ag
from app.session import reset_session


def _mock_apis(monkeypatch=None):
    ag.api_get_customer = lambda doc: {
        "0912345678": {"success": True, "customer": {
            "id": 123, "name": "Juan Pérez",
            "document": "0912345678", "phone": "0999999999"}},
    }.get(doc, {"success": False, "error": "CUSTOMER_NOT_FOUND"})
    # Juan: 52 días de mora (permite hasta 3 cuotas), plan 3x206.67 real
    ag.api_get_debt = lambda cid: {"success": True, "debt": {
        "customer_id": cid, "total_debt": 620.0,
        "days_overdue": 52, "currency": "USD", "status": "OVERDUE"}}
    ag.api_get_payment_plans = lambda cid: {"success": True, "payment_plans": {
        "customer_id": cid, "plans": [
            {"installments": 2, "amount_per_installment": 310.00},
            {"installments": 3, "amount_per_installment": 206.67},
        ]}}


def _auth_juan():
    _mock_apis()
    s = reset_session("agree1")
    ag._tool_get_customer(s, "0912345678")
    ag._tool_confirm_identity(s, "Juan Pérez")
    return s


def test_request_deja_pendiente_sin_webhook():
    s = _auth_juan()
    calls = []
    import app.n8n as n8n
    orig = n8n.send_payment_agreement
    n8n.send_payment_agreement = lambda **kw: calls.append(kw) or {"success": True}
    try:
        # Parchea también la referencia importada dentro de agent
        import app.agent as agmod
        real_fn = agmod.send_payment_agreement if hasattr(agmod, "send_payment_agreement") else None
        r = ag._tool_request_payment_agreement(s, 3)
    finally:
        n8n.send_payment_agreement = orig
    assert r["success"] and s["pending_agreement"]["installments"] == 3
    assert calls == []  # paso 1 NO dispara webhook


def test_confirm_sin_si_acepto_no_dispara():
    s = _auth_juan()
    ag._tool_request_payment_agreement(s, 3)
    r = ag._tool_confirm_payment_agreement(s, "luego te digo")
    assert not r["success"] and r["error"] == "CONFIRMATION_REQUIRED"
    assert s["pending_agreement"] is not None


def test_confirm_con_si_acepto_dispara_webhook_real_local():
    s = _auth_juan()
    ag._tool_request_payment_agreement(s, 3)
    import app.n8n as n8n
    n8n.WEBHOOK_URL = "http://127.0.0.1:8000/webhook/payment-agreement"
    # Usa TestClient en vez de red: parchea requests.post
    from fastapi.testclient import TestClient
    client = TestClient(main_mod.app)
    import requests as req_mod
    orig_post = req_mod.post

    class FakeResp:
        status_code = 200
        text = ""
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p

    def fake_post(url, json=None, headers=None, timeout=None):
        assert headers.get("X-Webhook-Secret"), "falta secret"
        r = client.post("/webhook/payment-agreement", json=json,
                        headers={"X-Webhook-Secret": headers["X-Webhook-Secret"]})
        return FakeResp(r.json())

    req_mod.post = fake_post
    try:
        r = ag._tool_confirm_payment_agreement(s, "SI ACEPTO")
    finally:
        req_mod.post = orig_post
    assert r["success"], r
    assert r["agreement"]["customer_id"] == 123  # backend impone el id
    assert s["pending_agreement"] is None


def test_webhook_exige_secret():
    client = TestClient(main_mod.app)
    r = client.post("/webhook/payment-agreement",
                    json={"customer_id": 123, "installments": 3,
                          "amount_per_installment": 206.67})
    assert r.status_code == 401
    r2 = client.post("/webhook/payment-agreement",
                     json={"customer_id": 123, "installments": 3,
                           "amount_per_installment": 206.67},
                     headers={"X-Webhook-Secret": "local-dev-secret"})
    assert r2.status_code == 200 and r2.json()["ok"] is True
