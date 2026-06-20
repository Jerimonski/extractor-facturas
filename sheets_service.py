import os
import json
import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials

# -------------------------
# CONFIG GOOGLE SHEETS
# -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

credentials_dict = json.loads(
    os.environ["GOOGLE_CREDENTIALS_JSON"]
)

creds = Credentials.from_service_account_info(
    credentials_dict,
    scopes=SCOPES
)

client = gspread.authorize(creds)

SHEET_ID = "1YIH_rfIlLCmWPG4-Zn_4RlsNsEvxRWdc8_6LiIOhCPc"
sheet = client.open_by_key(SHEET_ID)


# -------------------------
# HELPERS
# -------------------------
def get_year():
    return datetime.now().year


def generar_siguiente_importacion_id():
    """
    Busca última importación y genera:
    IMP-2026-001, IMP-2026-002...
    """

    ws = sheet.worksheet("Importaciones")
    data = ws.get_all_values()

    year = get_year()
    prefix = f"IMP-{year}-"

    last_number = 0

    for row in data[1:]:
        if len(row) == 0:
            continue

        imp_id = row[0]

        if imp_id.startswith(prefix):
            try:
                num = int(imp_id.split("-")[-1])
                last_number = max(last_number, num)
            except:
                pass

    next_number = last_number + 1

    return f"{prefix}{str(next_number).zfill(3)}"


# -------------------------
# IMPORTACIONES SHEET
# -------------------------
def insertar_importacion(importacion_id, nombre, cantidad_productos):
    ws = sheet.worksheet("Importaciones")

    fecha = datetime.now().strftime("%Y-%m-%d")

    ws.append_row([
        importacion_id,
        nombre,
        "",  # TipoCambio (si luego lo usas)
        "",  # GastosImportacion
        cantidad_productos,
        "",  # GastoPorUnidad
        fecha
    ])


# -------------------------
# PRODUCTOS SHEET
# -------------------------
def insertar_productos(importacion_id, productos):
    ws = sheet.worksheet("ProductosImportados")

    for p in productos:
        ws.append_row([
            importacion_id,
            p.get("CATEGORIA", ""),
            p.get("PRODUCTO", ""),
            p.get("CANTIDAD", 0),
            p.get("PRECIO_SOLES", 0),
            ""
        ])


# -------------------------
# TEST
# -------------------------
def test_connection():
    ws = sheet.worksheet("Importaciones")

    ws.append_row([
        "TEST",
        "CONEXION OK",
        "",
        "",
        "",
        "",
        datetime.now().strftime("%Y-%m-%d")
    ])