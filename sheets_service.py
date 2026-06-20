import os
import json
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = "1YIH_rfIlLCmWPG4-Zn_4RlsNsEvxRWdc8_6LiIOhCPc"

class GoogleSheetsService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
            creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
            self._client = gspread.authorize(creds)
        return self._client

    def get_ws(self, worksheet_name: str):
        sheet = self._get_client().open_by_key(SHEET_ID)
        return sheet.worksheet(worksheet_name)

    def obtener_ultimo_importacion_id(self) -> str:
        """Obtiene el ID más reciente directamente de la última fila de la tabla"""
        ws = self.get_ws("Importaciones")
        data = ws.get_all_values()
        if len(data) <= 1:
            # Fallback si la hoja está completamente vacía, genera el primero
            return self.generar_siguiente_importacion_id()
        return data[-1][0]  # Toma el ID de la última fila

    def generar_siguiente_importacion_id(self) -> str:
        ws = self.get_ws("Importaciones")
        data = ws.get_all_values()
        year = datetime.now().year
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
                except ValueError:
                    pass

        return f"{prefix}{str(last_number + 1).zfill(3)}"

    def insertar_importacion(self, importacion_id: str, nombre: str, cantidad_productos: int):
        ws = self.get_ws("Importaciones")
        fecha = datetime.now().strftime("%Y-%m-%d")
        ws.append_row([importacion_id, nombre, "", "", cantidad_productos, "", fecha])

    def actualizar_cantidad_maestra(self, importacion_id: str, cantidad_adicional: int):
        """Busca la fila correspondiente en 'Importaciones' y suma la nueva cantidad extraída"""
        ws = self.get_ws("Importaciones")
        data = ws.get_all_values()
        
        for i, row in enumerate(data):
            if row and row[0] == importacion_id:
                # La columna CantidadProductos está en la posición índice 4 (quinta columna)
                try:
                    cantidad_actual = int(row[4]) if row[4] else 0
                except ValueError:
                    cantidad_actual = 0
                
                nueva_cantidad = cantidad_actual + cantidad_adicional
                # gspread usa índices base 1, por ende la fila es i+1 y la columna es 5
                ws.update_cell(i + 1, 5, nueva_cantidad)
                break

    def insertar_productos_batch(self, importacion_id: str, productos: list):
        if not productos:
            return
        ws = self.get_ws("ProductosImportados")
        filas_a_insertar = []
        for p in productos:
            filas_a_insertar.append([
                importacion_id,
                p.get("CATEGORIA", "HOGAR Y LIMPIEZA"),
                p.get("PRODUCTO", ""),
                p.get("CANTIDAD", 0),
                p.get("PRECIO_SOLES", 0),
                ""
            ])
        ws.append_rows(filas_a_insertar)

sheets_backend = GoogleSheetsService()