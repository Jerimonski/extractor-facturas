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


def insertar_test():
    ws = get_ws("Importaciones")

    ws.append_row([
        "TEST",
        "CONEXION OK",
        "",
        "",
        "",
        "",
        datetime.now().strftime("%Y-%m-%d")
    ])

# -------------------------
# SAFE SHEET ACCESS
# -------------------------
def get_sheet():
    return client.open_by_key(SHEET_ID)


def get_ws(name: str):
    sheet = get_sheet()
    return sheet.worksheet(name)


# -------------------------
# HELPERS
# -------------------------
def get_year():
    return datetime.now().year


def generar_siguiente_importacion_id():
    ws = get_ws("Importaciones")
    data = ws.get_all_values()

    year = get_year()
    prefix = f"IMP-{year}-"

    last_number = 0

    for row in data[1:]:
        if not row:
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
# IMPORTACIONES
# -------------------------
def insertar_importacion(importacion_id, nombre, cantidad_productos):
    ws = get_ws("Importaciones")

    fecha = datetime.now().strftime("%Y-%m-%d")

    ws.append_row([
        importacion_id,
        nombre,
        "",
        "",
        cantidad_productos,
        "",
        fecha
    ])


# -------------------------
# PRODUCTOS
# -------------------------
def insertar_productos(importacion_id, productos):
    ws = get_ws("ProductosImportados")

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
    ws = get_ws("Importaciones")

    ws.append_row([
        "TEST",
        "CONEXION OK",
        "",
        "",
        "",
        "",
        datetime.now().strftime("%Y-%m-%d")
    ])