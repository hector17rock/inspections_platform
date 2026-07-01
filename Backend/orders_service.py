"""
orders_service.py — Capa de datos de ordenes OPD.

Cuando USE_MOCK_DATA=True : genera datos de prueba por tienda.
Cuando USE_MOCK_DATA=False : consulta la API interna de Walmart (Order Service v4).
"""

import logging
import random
import uuid
from datetime import datetime, timedelta

import httpx

import config

log = logging.getLogger("opd.orders")

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_CUSTOMERS = [
    "Maria Lopez", "Juan Garcia", "Ana Martinez", "Carlos Hernandez",
    "Laura Perez", "Miguel Sanchez", "Sofia Ramirez", "Diego Torres",
    "Isabella Flores", "Andres Morales", "Valentina Cruz", "Luis Castillo",
    "Rosa Gutierrez", "Pedro Jimenez", "Carmen Vargas", "Jose Mendoza",
]

_MOCK_PRODUCTS = [
    ["Leche 1L x2", "Pan Bimbo", "Huevos x12"],
    ["Detergente Ariel", "Suavitel 1L", "Jabon Palmolive x3"],
    ["Coca-Cola 2L x3", "Papas Sabritas", "Galletas Oreo"],
    ["Pollo entero", "Carne molida 1kg", "Chorizo"],
    ["Shampoo H&S", "Acondicionador", "Gel Gillette"],
    ["Panales Pampers T3 x40", "Toallitas humedas", "Crema Neutrogena"],
    ["Arroz 2kg", "Frijoles 1kg", "Aceite 1L", "Sal 1kg"],
    ["Yogurt Activia x4", "Queso Oaxaca", "Crema Lala"],
    ["Agua Ciel 5L", "Jugo Del Valle 1L x2"],
    ["Manzanas x6", "Platanos x5", "Uvas 500g", "Naranjas x4"],
    ["Jabon Dove x3", "Papel higienico x12", "Servilletas x2"],
    ["Cereal Zucaritas", "Leche Lala 1L x3", "Jugo Jumex"],
]

# Store-keyed mock orders: store_num -> {order_id -> order_dict}
_mock_store: dict[str, dict[str, dict]] = {}


def _new_mock_order() -> dict:
    return {
        "id":         str(uuid.uuid4())[:8].upper(),
        "customer":   random.choice(_MOCK_CUSTOMERS),
        "products":   random.choice(_MOCK_PRODUCTS),
        "status":     "Pendiente",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


def _seed_mock_store(store_num: str) -> dict[str, dict]:
    orders: dict[str, dict] = {}
    rng = random.Random(int(store_num) if store_num.isdigit() else hash(store_num))
    for i in range(rng.randint(4, 7)):
        order = _new_mock_order()
        order["created_at"] = datetime.now() - timedelta(minutes=rng.randint(1, 28))
        if i % 3 == 0:
            order["status"] = "En proceso"
        orders[order["id"]] = order
    return orders


def _simulate_tick(orders: dict[str, dict]) -> None:
    to_remove = []
    for oid, order in orders.items():
        wait = (datetime.now() - order["created_at"]).total_seconds() / 60
        if order["status"] == "Pendiente" and wait > 2 and random.random() < 0.3:
            order["status"] = "En proceso"
            order["updated_at"] = datetime.now()
        elif order["status"] == "En proceso" and random.random() < 0.2:
            order["status"] = "Listo"
            order["updated_at"] = datetime.now()
        elif order["status"] == "Listo":
            if (datetime.now() - order["updated_at"]).total_seconds() / 60 > 3:
                to_remove.append(oid)
    for oid in to_remove:
        del orders[oid]
    if random.random() < 0.30:
        o = _new_mock_order()
        orders[o["id"]] = o


def _get_mock_orders(store_num: str) -> list[dict]:
    if store_num not in _mock_store:
        _mock_store[store_num] = _seed_mock_store(store_num)
    _simulate_tick(_mock_store[store_num])
    return list(_mock_store[store_num].values())


# ---------------------------------------------------------------------------
# Real API integration — Order Service v4
# ---------------------------------------------------------------------------

def _map_real_status(api_status: str) -> str:
    """Convierte el status de la API de Walmart al status de la app."""
    mapping = {
        "PROCESSING":       "Pendiente",
        "READY_FOR_PICKUP": "Listo",
        "PICKED_UP":        "Listo",
    }
    return mapping.get(api_status.upper(), "Pendiente")


def _parse_real_orders(payload: list[dict]) -> list[dict]:
    """Transforma la respuesta de Order Service v4 al formato de la app."""
    orders = []
    for po in payload:
        order_lines = po.get("orderLines", {}).get("orderLine", [])
        products = []
        status_raw = "PROCESSING"

        for line in order_lines:
            name = line.get("item", {}).get("productName", "Producto")
            qty  = line.get("orderLineQuantity", {}).get("amount", 1)
            products.append(f"{name} x{qty}")

            statuses = line.get("orderLineStatuses", {}).get("orderLineStatus", [])
            if statuses:
                status_raw = statuses[0].get("status", "PROCESSING")

        customer_name = (
            po.get("shippingInfo", {})
              .get("postalAddress", {})
              .get("name", "Cliente")
        )
        order_date_str = po.get("orderDate", "")
        try:
            created_at = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.now()

        orders.append({
            "id":         po.get("customerOrderId", str(uuid.uuid4())[:8])[-8:].upper(),
            "customer":   customer_name,
            "products":   products or ["Sin detalle"],
            "status":     _map_real_status(status_raw),
            "created_at": created_at.replace(tzinfo=None),
            "updated_at": datetime.now(),
        })
    return orders


async def _fetch_real_orders(store_num: str) -> list[dict]:
    """Llama a la API interna de Walmart y retorna las ordenes OPD."""
    import uuid as _uuid

    headers = {
        "WM_SVC.VERSION":        config.WM_SVC_VERSION,
        "WM_SVC.ENV":            config.WM_SVC_ENV,
        "WM_SVC.NAME":           config.WM_SVC_NAME,
        "WM_CONSUMER.ID":        config.WM_CONSUMER_ID,
        "WM_QOS.CORRELATION_ID": str(_uuid.uuid4()),
        "WM_CONSUMER.TENANT_ID": config.WM_TENANT_ID,
        "Accept":                "application/json",
    }

    today = datetime.now()
    params = {
        "storeId":          store_num,
        "fulfillmentType":  ",".join(config.FULFILLMENT_TYPES),
        "lineStatus":       ",".join(config.PENDING_STATUSES),
        "fromOrderDate":    (today - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "toOrderDate":      today.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit":            config.PAGE_LIMIT,
        "offset":           0,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(config.REAL_API_BASE_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    payload = data.get("payload", [])
    return _parse_real_orders(payload)


# ---------------------------------------------------------------------------
# Public interface — usado por main.py
# ---------------------------------------------------------------------------

async def get_orders(store_num: str) -> list[dict]:
    """
    Punto de entrada principal.
    Retorna lista de ordenes para la tienda indicada.
    """
    if config.USE_MOCK_DATA:
        return _get_mock_orders(store_num)

    try:
        return await _fetch_real_orders(store_num)
    except Exception as exc:
        log.error("Error consultando API real para tienda %s: %s", store_num, exc)
        log.warning("Cayendo a datos mock como fallback temporal.")
        return _get_mock_orders(store_num)


def seed_demo_stores() -> None:
    """Pre-siembra tiendas de demo para mock mode."""
    if config.USE_MOCK_DATA:
        for demo in ["1234", "5678", "9999"]:
            _mock_store[demo] = _seed_mock_store(demo)
