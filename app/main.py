from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field
import logging
import os
import time

app = FastAPI(
    title="Collection API",
    description="API simulada para pruebas de agente de cobranza",
    version="1.0.0"
)


customers = {
    "0912345678": {
        "id": 123,
        "name": "Juan Pérez",
        "document": "0912345678",
        "phone": "0999999999"
    },
    "0923456789": {
        "id": 456,
        "name": "María González",
        "document": "0923456789",
        "phone": "0988888888"
    }
}


debts = {
    123: {
        "customer_id": 123,
        "total_debt": 620.00,
        "days_overdue": 52,
        "currency": "USD",
        "status": "OVERDUE"
    },
    456: {
        "customer_id": 456,
        "total_debt": 180.00,
        "days_overdue": 20,
        "currency": "USD",
        "status": "OVERDUE"
    }
}


payment_plans = {
    123: [
        {
            "installments": 2,
            "amount_per_installment": 310.00
        },
        {
            "installments": 3,
            "amount_per_installment": 206.67
        }
    ],
    456: [
        {
            "installments": 2,
            "amount_per_installment": 90.00
        }
    ]
}


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/customers")
def get_customer(document: str):
    customer = customers.get(document)

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    return customer


@app.get("/customers/{customer_id}/debt")
def get_debt(customer_id: int):
    debt = debts.get(customer_id)

    if not debt:
        raise HTTPException(
            status_code=404,
            detail="Debt information not found"
        )

    return debt


@app.get("/customers/{customer_id}/payment-plans")
def get_payment_plans(customer_id: int):
    plans = payment_plans.get(customer_id)

    if plans is None:
        raise HTTPException(
            status_code=404,
            detail="Payment plans not found"
        )

    return {
        "customer_id": customer_id,
        "plans": plans
    }


logger = logging.getLogger(__name__)

# CRM simulado en memoria (prueba técnica, no persistente).
agreements: dict[int, dict] = {}
_next_agreement_id = 1000


class AgreementIn(BaseModel):
    customer_id: int
    installments: int = Field(ge=1, le=12)
    amount_per_installment: float = Field(gt=0)


class WebhookAgreementIn(BaseModel):
    customer_id: int
    installments: int = Field(ge=1, le=12)
    amount_per_installment: float = Field(gt=0)
    agreement_id: int | None = None


def _check_secret(provided: str | None) -> None:
    expected = os.getenv("N8N_WEBHOOK_SECRET", "local-dev-secret")
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@app.post("/agreements")
def create_agreement(body: AgreementIn):
    """CRM simulado: registra un acuerdo de pago."""
    global _next_agreement_id
    if body.customer_id not in debts:
        raise HTTPException(status_code=404, detail="Customer not found")
    _next_agreement_id += 1
    record = {
        "agreement_id": _next_agreement_id,
        "customer_id": body.customer_id,
        "installments": body.installments,
        "amount_per_installment": body.amount_per_installment,
        "status": "CONFIRMED",
        "created_at": int(time.time()),
    }
    agreements[_next_agreement_id] = record
    logger.info("CRM: acuerdo %s para cliente %s", _next_agreement_id, body.customer_id)
    return record


@app.post("/webhook/payment-agreement")
async def webhook_payment_agreement(
    body: WebhookAgreementIn,
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
):
    """Receptor de prueba local. En producción esta URL es la del webhook de n8n.

    Valida secret + payload, simula actualización de CRM y notificación,
    y responde para que el agente confirme al usuario.
    """
    _check_secret(x_webhook_secret)
    if body.customer_id not in debts:
        raise HTTPException(status_code=404, detail="Customer not found")
    # Simula CRM: reutiliza la misma lógica de registro.
    global _next_agreement_id
    _next_agreement_id += 1
    agreement_id = body.agreement_id or _next_agreement_id
    record = {
        "agreement_id": agreement_id,
        "customer_id": body.customer_id,
        "installments": body.installments,
        "amount_per_installment": body.amount_per_installment,
        "status": "CONFIRMED",
        "created_at": int(time.time()),
    }
    agreements[agreement_id] = record
    # Simula notificación (en n8n real: nodo Telegram/Slack/Email).
    logger.info(
        "Notify: acuerdo %s confirmado: cliente %s, %sx %.2f",
        agreement_id, body.customer_id,
        body.installments, body.amount_per_installment,
    )
    return {"ok": True, **record}