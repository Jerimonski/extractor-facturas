import os
import json
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from google import genai
from google.genai import types
from dotenv import load_dotenv

from sheets_service import sheets_backend

load_dotenv()

app = FastAPI(
    title="ERP Ligero - Extractor de Importaciones",
    description="Pipeline de automatización para procesamiento de facturas en PDF usando IA"
)

ALLOWED_CATEGORIES = {"BEBIDAS Y LÍQUIDOS", "GALLETAS", "HOGAR Y LIMPIEZA", "PAPEL HIGIÉNICO"}

# Inicialización segura del cliente Gemini (API v1 estable)
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1"}
)

# -------------------------
# MODELOS DE VALIDACIÓN (PYDANTIC)
# -------------------------
class ProductoExtraido(BaseModel):
    CATEGORIA: str = Field(..., description="Categoría asignada al producto")
    PRODUCTO: str = Field(..., description="Nombre o descripción del artículo en mayúsculas")
    CANTIDAD: int = Field(..., gt=0, description="Cantidad entera mayor a cero")
    PRECIO_SOLES: float = Field(..., ge=0.0, description="Precio unitario en soles")

class ErrorMessage(BaseModel):
    detail: str

# -------------------------
# PROMPT REFORZADO
# -------------------------
GEMINI_PROMPT = """
Eres un sistema experto en extracción y clasificación de facturas comerciales.
Analiza el documento PDF adjunto y estructura su información.

Devuelve ESTRICTAMENTE un arreglo JSON válido, sin formato markdown, sin envolverlo en bloques ```json, y sin comentarios explicativos.

FORMATO DE SALIDA COMPULSORIO:
[
  {
    "CATEGORIA": "GALLETAS",
    "PRODUCTO": "NOMBRE EN MAYUSCULAS DEL PRODUCTO",
    "CANTIDAD": 10,
    "PRECIO_SOLES": 15.50
  }
]

REGLAS DE NEGOCIO:
1. Clasifica cada artículo mapeándolo única y exclusivamente a una de estas categorías permitidas:
   - BEBIDAS Y LÍQUIDOS
   - GALLETAS
   - HOGAR Y LIMPIEZA
   - PAPEL HIGIÉNICO
2. El campo 'PRODUCTO' debe estar completamente en MAYÚSCULAS.
3. 'CANTIDAD' debe extraerse como un número entero.
4. 'PRECIO_SOLES' mapea el valor monetario unitario como punto decimal.
"""

@app.get("/test-sheet", summary="Validar conexión con Sheets")
async def test_sheet():
    try:
        sheets_backend.insertar_test()
        return {"status": "ok", "message": "Fila de prueba insertada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/procesar-importacion",
    summary="Subir múltiples facturas en PDF y consolidar importación",
    responses={
        400: {"model": ErrorMessage, "description": "Formato de archivo o entrada no válida"},
        500: {"model": ErrorMessage, "description": "Error crítico en el backend o en la API de IA"}
    }
)
async def procesar_importacion(
    files: List[UploadFile] = File(..., description="Selecciona uno o varios archivos PDF de facturas")
):
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Debes cargar al menos un archivo PDF válido.")

    try:
        # 1. Generación resiliente de ID de importación
        importacion_id = sheets_backend.generar_siguiente_importacion_id()
        all_products_validated = []

        # 2. Procesamiento iterativo de los documentos
        for file in files:
            if not file.filename.lower().endswith('.pdf') and file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400, 
                    detail=f"El archivo '{file.filename}' no corresponde a un formato PDF permitido."
                )

            pdf_bytes = await file.read()
            pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

            # Invocación al modelo predictivo
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[pdf_part, GEMINI_PROMPT]
            )

            raw_output = response.text.strip()
            cleaned = raw_output.replace("```json", "").replace("```", "").strip()

            try:
                data_json = json.loads(cleaned)
                if not isinstance(data_json, list):
                    raise ValueError("La respuesta raíz de Gemini no se estructuró como una lista.")
                
                # Validación Estricta por Esquema mediante Pydantic
                for item in data_json:
                    # Corrección en caliente de categorías inválidas antes de validar
                    if item.get("CATEGORIA") not in ALLOWED_CATEGORIES:
                        item["CATEGORIA"] = "HOGAR Y LIMPIEZA"
                    
                    # Traspaso al validador nativo
                    producto_validado = ProductoExtraido(**item)
                    all_products_validated.append(producto_validado.model_dump())

            except (json.JSONDecodeError, ValidationError, ValueError) as err:
                print(f"--- LOG ERROR PROCESAMIENTO EN {file.filename} ---")
                print(f"Raw recibido: {raw_output}")
                print(f"Detalle del error: {str(err)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al analizar o estructurar los datos del archivo '{file.filename}'."
                )

        total_productos = len(all_products_validated)

        # 3. Persistencia Transaccional en Google Sheets
        # Guardamos el registro maestro (1 fila)
        sheets_backend.insertar_importacion(
            importacion_id=importacion_id,
            nombre=f"IMPORTACION {importacion_id}",
            cantidad_productos=total_productos
        )

        # Guardamos los registros detalle (N filas consolidadas de una sola vez)
        sheets_backend.insertar_productos_batch(
            importacion_id=importacion_id,
            productos=all_products_validated
        )

        return {
            "status": "success",
            "importacion_id": importacion_id,
            "facturas_procesadas": len(files),
            "productos_totales": total_productos
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla catastrófica interna del servidor: {str(e)}")