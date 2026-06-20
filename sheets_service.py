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
        """Lazy initialization para asegurar estabilidad en el arranque de FastAPI"""
        if self._client is None:
            try:
                credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
                creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
                self._client = gspread.authorize(creds)
            except Exception as e:
                raise RuntimeError(f"Error crítico al inicializar credenciales de Google Sheets: {str(e)}")
        return self._client

    def get_ws(self, worksheet_name: str):
        try:
            sheet = self._get_client().open_by_key(SHEET_ID)
            return sheet.worksheet(worksheet_name)
        except Exception as e:
            raise RuntimeError(f"No se pudo acceder a la pestaña '{worksheet_name}': {str(e)}")

    def generar_siguiente_importacion_id(self) -> str:
        ws = self.get_ws("Importaciones")
        data = ws.get_all_values()
        
        year = datetime.now().year
        prefix = f"IMP-{year}-"
        last_number = 0

        for row in data[1:]:
            if not row or len(row) == 0:
                continue
            imp_id = row[0]
            if imp_id.startswith(prefix):
                try:
                    num = int(imp_id.split("-")[-1])
                    last_number = max(last_number, num)
                except ValueError:
                    pass

        next_number = last_number + 1
        return f"{prefix}{str(next_number).zfill(3)}"

    def insertar_importacion(self, importacion_id: str, nombre: str, cantidad_productos: int):
        ws = self.get_ws("Importaciones")
        fecha = datetime.now().strftime("%Y-%m-%d")
        
        ws.append_row([
            importacion_id,
            nombre,
            "",  # TipoCambio
            "",  # GastosImportacion
            cantidad_productos,
            "",  # GastoPorUnidad
            fecha
        ])

    def insertar_productos_batch(self, importacion_id: str, productos: list):
        """Inserta N filas en una sola llamada de red (Batch Insert)"""
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
                ""  # PrecioVenta
            ])
            
        # Inserción masiva ultra rápida
        ws.append_rows(filas_a_insertar)

    def insertar_test(self):
        ws = self.get_ws("Importaciones")
        ws.append_row([
            "TEST", "CONEXION OK", "", "", "", "", 
            datetime.now().strftime("%Y-%m-%d")
        ])

# Instancia única reutilizable
sheets_backend = GoogleSheetsService()