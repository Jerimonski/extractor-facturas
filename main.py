import os
import json
from typing import List, Annotated

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from google import genai
from google.genai import types

from sheets_service import (
    insertar_importacion,
    insertar_productos,
    generar_siguiente_importacion_id
)

app = FastAPI()

ALLOWED_CATEGORIES = {
    "BEBIDAS Y LÍQUIDOS",
    "GALLETAS",
    "HOGAR Y LIMPIEZA",
    "PAPEL HIGIÉNICO"
}

# -------------------------
# GEMINI CLIENT
# -------------------------
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={'api_version': 'v1'}
)

# -------------------------
# MODELO ERROR
# -------------------------
class ErrorMessage(BaseModel):
    detail: str


# -------------------------
# TEST SHEET
# -------------------------
@app.get("/test-sheet")
async def test_sheet():
    from sheets_service import insertar_test
    insertar_test()

    return {"status": "ok"}


# -------------------------
# PROMPT GEMINI
# -------------------------
GEMINI_PROMPT = """
Eres un sistema de clasificación y extracción de facturas de importación.

Devuelve SOLO JSON válido, sin texto adicional ni markdown.

FORMATO:
[
  {
    "CATEGORIA": "",
    "PRODUCTO": "",
    "CANTIDAD": 0,
    "PRECIO_SOLES": 0
  }
]

REGLAS ESTRICTAS:
- CATEGORIA debe ser EXACTAMENTE una de estas opciones:
  - BEBIDAS Y LÍQUIDOS
  - GALLETAS
  - HOGAR Y LIMPIEZA
  - PAPEL HIGIÉNICO

- No puedes inventar ni modificar categorías
- PRODUCTO en MAYÚSCULAS
- CANTIDAD entero
- PRECIO_SOLES decimal
- No omitir productos
- No agregar explicaciones
"""
# -------------------------
# ENDPOINT PRINCIPAL
# -------------------------
@app.post("/procesar-importacion")
async def procesar_importacion(
    files: List[UploadFile] = File(...)
):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un PDF")

    try:
        # 1. generar ID IMPORTACIÓN
        importacion_id = generar_siguiente_importacion_id()

        all_products = []

        # 2. procesar todos los PDFs
        for file in files:

            if file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo inválido: {file.filename}"
                )

            pdf_bytes = await file.read()

            pdf_part = types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[pdf_part, GEMINI_PROMPT]
            )

            raw = response.text.strip()

            cleaned = raw.replace("```json", "").replace("```", "").strip()

            try:
                data = json.loads(cleaned)
                for p in data:
                    if p.get("CATEGORIA") not in ALLOWED_CATEGORIES:
                        p["CATEGORIA"] = "HOGAR Y LIMPIEZA"
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail=f"Gemini devolvió JSON inválido en {file.filename}"
                )

            if not isinstance(data, list):
                raise HTTPException(
                    status_code=500,
                    detail="Formato incorrecto desde Gemini"
                )

            all_products.extend(data)

        # 3. métricas
        total_productos = len(all_products)

        # 4. guardar en IMPORTACIONES (1 fila)
        insertar_importacion(
            importacion_id=importacion_id,
            nombre=file.filename if len(files) == 1 else f"IMPORTACION {importacion_id}",
            cantidad_productos=total_productos
        )

        # 5. guardar productos (N filas)
        insertar_productos(
            importacion_id=importacion_id,
            productos=all_products
        )

        # 6. respuesta final
        return {
            "status": "success",
            "importacion_id": importacion_id,
            "facturas_procesadas": len(files),
            "productos_totales": total_productos
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# RUN LOCAL
# -------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)