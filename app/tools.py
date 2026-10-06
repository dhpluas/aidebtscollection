import requests
import os


API_URL = os.getenv(
    "COLLECTION_API_URL",
    "http://127.0.0.1:8000"
)


def get_customer(document: str) -> dict:
    """
    Busca un cliente utilizando su número de documento.
    """

    response = requests.get(
        f"{API_URL}/customers",
        params={"document": document},
        timeout=5
    )

    if response.status_code == 404:
        return {
            "success": False,
            "error": "CUSTOMER_NOT_FOUND"
        }

    response.raise_for_status()

    return {
        "success": True,
        "customer": response.json()
    }


def get_debt(customer_id: int) -> dict:
    """
    Consulta la deuda actual de un cliente.
    """

    response = requests.get(
        f"{API_URL}/customers/{customer_id}/debt",
        timeout=5
    )

    if response.status_code == 404:
        return {
            "success": False,
            "error": "DEBT_NOT_FOUND"
        }

    response.raise_for_status()

    return {
        "success": True,
        "debt": response.json()
    }


def get_payment_plans(customer_id: int) -> dict:
    """
    Consulta los planes de pago disponibles.
    """

    response = requests.get(
        f"{API_URL}/customers/{customer_id}/payment-plans",
        timeout=5
    )

    if response.status_code == 404:
        return {
            "success": False,
            "error": "PAYMENT_PLANS_NOT_FOUND"
        }

    response.raise_for_status()

    return {
        "success": True,
        "payment_plans": response.json()
    }