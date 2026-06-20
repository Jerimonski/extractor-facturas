import os
import json
from typing import Annotated
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Cliente Gemini con configuración explícita de API de producción v1 para evitar 502/404s
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={'api_version': 'v1'}
)

class ErrorMessage(BaseModel):
    detail: str

@app.post(
    "/procesar-factura",
    responses={
        400: {"model": ErrorMessage, "description": "El archivo subido no es un PDF válido"},
        500: {"model": ErrorMessage, "description": "Error interno del servidor o falla en la API de Gemini"}
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

        # Prompt reforzado con las columnas reales de tu factura
        prompt = """
        Eres un extractor de datos de facturas experto. Mapea la información basándote exclusivamente en el documento.
        
        DEVUELVE SOLO UN ARREGLO JSON VÁLIDO (sin texto explicativo, sin markdown como ```json, sin introducciones).

        Mapea las columnas a estas llaves específicas:
        - "CODIGO": Déjalo vacío "" si el documento no tiene una columna explícita de códigos.
        - "PRODUCTOS": Extrae el texto de la columna 'Descripción' en MAYÚSCULAS.
        - "CANTIDAD": Extrae el número de la columna 'Cantidad' (número entero).
        - "PRECIO_UNITARIO_SOLES": Extrae el valor numérico de la columna 'Valor Unitario' (número decimal).

        FORMATO OBLIGATORIO DE RESPUESTA:
        [
          {
            "PRODUCTOS": "GASEOSA COCA COLA 12 UNID. X 600 ML.",
            "CANTIDAD": 200,
            "PRECIO_UNITARIO_SOLES": 24.60
          }
        ]
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",  
            contents=[pdf_part, prompt]
        )

        raw_output = response.text.strip()

        print("===== GEMINI RAW OUTPUT =====")
        print(raw_output)
        print("=============================")

        # Limpieza defensiva de tags Markdown
        cleaned = (
            raw_output
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        # Conversión y validación real a JSON
        try:
            data = json.loads(cleaned)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini no devolvió JSON válido: {str(e)}"
            )

        if not isinstance(data, list):
            raise HTTPException(
                status_code=500,
                detail="El JSON obtenido no es una lista de productos estructurada"
            )

        # Nota de compatibilidad: Mantenemos el retorno de 'data' serializado como string 
        # para que tu Google Apps Script actual (JSON.parse) no falle.
        return {
            "status": "success",
            "count": len(data),
            "data": json.dumps(data) 
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Esto asegura que si corres el archivo localmente con 'python main.py', lea el puerto correcto de las variables
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
