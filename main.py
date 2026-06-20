import os
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field, ValidationError
from google import genai
from google.genai import types
from dotenv import load_dotenv

from sheets_service import sheets_backend

load_dotenv()

app = FastAPI(
    title="ERP Ligero - Extractor de Importaciones",
    description="Pipeline optimizado para procesar facturas individuales con opción de consolidación."
)

ALLOWED_CATEGORIES = {"BEBIDAS Y LÍQUIDOS", "GALLETAS", "HOGAR Y LIMPIEZA", "PAPEL HIGIÉNICO"}

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1"}
)

class ProductoExtraido(BaseModel):
    CATEGORIA: str
    PRODUCTO: str
    CANTIDAD: int = Field(..., gt=0)
    PRECIO_SOLES: float = Field(..., ge=0.0)

class ErrorMessage(BaseModel):
    detail: str

GEMINI_PROMPT = """
Eres un extractor de facturas comerciales. Analiza el PDF y devuelve un arreglo JSON válido.
NO incluyas bloques markdown ni texto explicativo.

FORMATO OBLIGATORIO:
[
  {
    "CATEGORIA": "GALLETAS",
    "PRODUCTO": "DESCRIPCION EN MAYUSCULAS",
    "CANTIDAD": 10,
    "PRECIO_SOLES": 15.50
  }
]

CATEGORÍAS PERMITIDAS: BEBIDAS Y LÍQUIDOS, GALLETAS, HOGAR Y LIMPIEZA, PAPEL HIGIÉNICO.
"""

@app.post(
    "/procesar-factura",
    summary="Procesar una factura en PDF",
    responses={400: {"model": ErrorMessage}, 500: {"model": ErrorMessage}}
)
async def procesar_factura(
    file: UploadFile = File(..., description="Selecciona el archivo PDF de la factura"),
    misma_importacion: bool = Form(False, description="Marca esta casilla si el PDF pertenece a la misma importación anterior")
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un formato PDF válido.")

    try:
        # 1. Decidir u obtener el ID de importación correspondiente
        if misma_importacion:
            importacion_id = sheets_backend.obtener_ultimo_importacion_id()
            es_nueva_fila_maestra = False
        else:
            importacion_id = sheets_backend.generar_siguiente_importacion_id()
            es_nueva_fila_maestra = True

        # 2. Leer archivo y consultar a Gemini
        pdf_bytes = await file.read()
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[pdf_part, GEMINI_PROMPT]
        )

        raw_output = response.text.strip()
        cleaned = raw_output.replace("```json", "").replace("```", "").strip()

        data_json = json.loads(cleaned)
        all_products_validated = []

        for item in data_json:
            if item.get("CATEGORIA") not in ALLOWED_CATEGORIES:
                item["CATEGORIA"] = "HOGAR Y LIMPIEZA"
            
            producto_validado = ProductoExtraido(**item)
            all_products_validated.append(producto_validado.model_dump())

        total_productos = len(all_products_validated)

        # 3. Guardar en Google Sheets de forma estructurada
        if es_nueva_fila_maestra:
            # Crea el registro maestro principal si es una importación nueva
            sheets_backend.insertar_importacion(
                importacion_id=importacion_id,
                nombre=f"IMPORTACION {importacion_id}",
                cantidad_productos=total_productos
            )
        else:
            # Si se consolida, actualiza el contador acumulado de la fila maestra existente
            sheets_backend.actualizar_cantidad_maestra(importacion_id, total_productos)

        # Volcado de productos asociados al ID correspondiente (Batch rápido)
        sheets_backend.insertar_productos_batch(
            importacion_id=importacion_id,
            productos=all_products_validated
        )

        return {
            "status": "success",
            "importacion_id": importacion_id,
            "consolidado": misma_importacion,
            "productos_añadidos": total_productos
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))