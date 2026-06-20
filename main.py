import os
import json
from typing import Annotated
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sheets_service import test_connection

load_dotenv()

app = FastAPI()

# Cliente Gemini
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY")
)

class ErrorMessage(BaseModel):
    detail: str

@app.get("/test-sheet")
async def test_sheet():
    test_connection()

    return {
        "status": "ok"
    }

@app.post(
    "/procesar-factura",
    responses={
        400: {"model": ErrorMessage},
        500: {"model": ErrorMessage}
    }
)
async def procesar_factura(
    file: Annotated[UploadFile, File(description="Factura en PDF")]
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="El archivo debe ser PDF")

    try:
        pdf_bytes = await file.read()

        pdf_part = types.Part.from_bytes(
            data=pdf_bytes,
            mime_type="application/pdf"
        )

        # 🔥 Prompt reforzado para estructura estricta
        prompt = """
Eres un extractor de datos de facturas.

DEVUELVE SOLO JSON VÁLIDO (sin texto, sin markdown, sin explicaciones).

FORMATO OBLIGATORIO:
[
  {
    "CODIGO": "",
    "PRODUCTOS": "",
    "CANTIDAD": 0,
    "PRECIO_UNITARIO_SOLES": 0
  }
]

REGLAS:
- PRODUCTOS en MAYÚSCULAS
- CANTIDAD entero
- PRECIO_UNITARIO_SOLES decimal
- CODIGO siempre "" si no existe
- No inventes datos
- No omitas productos
"""

        response = client.models.generate_content(
            model="models/gemini-2.5-flash",  # más estable para tablas
            contents=[pdf_part, prompt]
        )

        raw_output = response.text.strip()

        print("===== GEMINI RAW OUTPUT =====")
        print(raw_output)
        print("=============================")

        # 🔥 Limpieza defensiva
        cleaned = (
            raw_output
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        # 🔥 Conversión real a JSON
        try:
            data = json.loads(cleaned)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini no devolvió JSON válido: {str(e)}"
            )

        # 🔥 Validación mínima de estructura
        if not isinstance(data, list):
            raise HTTPException(
                status_code=500,
                detail="El JSON no es una lista de productos"
            )

        return {
            "status": "success",
            "count": len(data),
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))