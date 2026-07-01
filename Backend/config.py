"""
Configuracion de la API de OPD Orders.

INSTRUCCIONES PARA DATOS REALES:
---------------------------------
1. Solicita tu WM_CONSUMER_ID al equipo de plataforma o tu Tech Coach de tienda.
   Referencia: https://confluence.walmart.com/display/PGSOMSSHIM/Order+Search+Partner+Orders+API

2. Llena los valores de REAL_API_* abajo con tus credenciales.

3. Cambia USE_MOCK_DATA = False

4. Reinicia el servidor.

Mientras USE_MOCK_DATA = True, la app usa datos de prueba generados automaticamente.
"""

# -----------------------------------------------------------------------
# Cambia esto a False cuando tengas credenciales reales
# -----------------------------------------------------------------------
USE_MOCK_DATA: bool = True

# -----------------------------------------------------------------------
# Credenciales de la API interna de Walmart (Order Service v4)
# Solicitalas a tu Tech Coach o equipo de plataforma
# -----------------------------------------------------------------------
REAL_API_BASE_URL: str = (
    "http://ultra-esb.prod-order.esb.platform.glb.prod.walmart.com"
    "/service/order-service/v4/partner-orders"
)

WM_CONSUMER_ID:   str = ""   # <-- Pon aqui tu consumer ID
WM_TENANT_ID:     str = "0"
WM_SVC_ENV:       str = "prod"
WM_SVC_NAME:      str = "order-service"
WM_SVC_VERSION:   str = "4.0.0"

# Tipos de fulfillment OPD a consultar
FULFILLMENT_TYPES: list[str] = ["PICKUP", "SCHEDULED_PICKUP", "PUT"]

# Estados de orden que se consideran "pendientes de dispensar"
PENDING_STATUSES: list[str] = ["PROCESSING", "READY_FOR_PICKUP"]

# Cuantas ordenes traer por peticion
PAGE_LIMIT: int = 50

# Intervalo de refresco en segundos
REFRESH_INTERVAL_SEC: int = 30
