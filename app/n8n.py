"""Cliente del webhook de automatización (n8n).

El LLM nunca llama al webhook directo: solo los wrappers de
app/agent.py, que validan autenticación + confirmación explícita
y fijan el customer_id desde la sesión (backend).
"""

import os

import requests

WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://127.0.0.1:8000/webhook/payment-agreement",
)
WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "local-dev-secret")
TIMEOUT = 8


def send_payment_agreement(
    customer_id: int,
    installments: int,
    amount_per_installment: float,
    agreement_id: int | None = None,
) -> dict:
    """POST al webhook. Nunca inventa: propaga errores tal cual."""
    payload = {
        "customer_id": customer_id,
        "installments": installments,
        "amount_per_installment": amount_per_installment,
    }
    if agreement_id is not None:
        payload["agreement_id"] = agreement_id
    try:
        resp = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": WEBHOOK_SECRET,
            },
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        return {"success": False, "error": "TIMEOUT",
                "message": "El webhook no respondió a tiempo."}
    except requests.ConnectionError:
        return {"success": False, "error": "WEBHOOK_UNAVAILABLE",
                "message": "Webhook no disponible. Intenta más tarde."}
    if resp.status_code == 401:
        return {"success": False, "error": "INVALID_SECRET",
                "message": "Secreto del webhook inválido."}
    if 400 <= resp.status_code < 500:
        return {"success": False, "error": f"HTTP_{resp.status_code}",
                "message": f"Payload rechazado: {resp.text[:200]}"}
    if resp.status_code >= 500:
        return {"success": False, "error": f"HTTP_{resp.status_code}",
                "message": "Error del servidor de automatización."}
    try:
        data = resp.json()
    except Exception:
        return {"success": False, "error": "INVALID_RESPONSE",
                "message": "Respuesta inválida del webhook."}
    return {"success": True, "webhook": data}
