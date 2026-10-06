# Integración n8n — Acuerdo de pago

El LLM y la lógica del agente viven en Python. n8n es solo
automatización: recibe el acuerdo confirmado, valida, actualiza
el CRM (simulado) y notifica.

## Flujo

```
Webhook → Validate Data → HTTP Request / CRM → Notification → Respond to Webhook
```

## Webhook de producción (n8n)

| Campo | Valor |
|---|---|
| Método | `POST` |
| URL (n8n) | `https://TU-N8N/webhook/payment-agreement` |
| URL local de prueba | `POST http://127.0.0.1:8000/webhook/payment-agreement` (este repo, `app/main.py`) |
| Headers | `Content-Type: application/json`, `X-Webhook-Secret: <N8N_WEBHOOK_SECRET>` |

## JSON enviado (desde `app/n8n.py`)

```json
{
  "customer_id": 123,
  "agreement_id": 987,
  "installments": 3,
  "amount_per_installment": 206.67
}
```
`agreement_id` es opcional: si se omite, el servidor lo genera.

## Respuesta esperada `200`

```json
{
  "ok": true,
  "agreement_id": 1001,
  "customer_id": 123,
  "installments": 3,
  "amount_per_installment": 206.67,
  "status": "CONFIRMED",
  "created_at": 1728000000
}
```

## Errores

| Código | Causa |
|---|---|
| `401` | `X-Webhook-Secret` ausente o inválido |
| `404` | `customer_id` inexistente |
| `422` | payload inválido (cuotas ≤0, monto ≤0, campos faltantes) |
| timeout / conexión | el agente responde "webhook no disponible", sin inventar |

## Importar el workflow

1. n8n → Workflows → Import from file → `n8n/workflow_payment_agreement.json`.
2. Activa el nodo Webhook y copia su URL a `N8N_WEBHOOK_URL` en `.env`.
3. Configura el mismo `N8N_WEBHOOK_SECRET` en n8n (header) y en `.env`.
4. El nodo `HTTP Request / CRM` apunta a `POST /agreements` del CRM real
   (en local: `http://127.0.0.1:8000/agreements`).

## Probar en local (sin n8n)

```bash
uvicorn app.main:app
curl -X POST http://127.0.0.1:8000/webhook/payment-agreement ^
  -H "Content-Type: application/json" ^
  -H "X-Webhook-Secret: local-dev-secret" ^
  -d "{\"customer_id\":123,\"installments\":3,\"amount_per_installment\":206.67}"
```
