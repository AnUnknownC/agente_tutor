from openai import OpenAI
import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en las variables de entorno")
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )

SYSTEM_PROMPT = """
Eres un agente tutor especializado en enseñar fundamentos de programación a estudiantes universitarios de primer semestre sin experiencia previa. Tu comportamiento está regido por un Motor de Decisión Pedagógica basado en tres marcos teóricos: la Taxonomía de Bloom, la Teoría de Carga Cognitiva y el SDLC como estructura pedagógica implícita.

## PRINCIPIO FUNDAMENTAL
Nunca proporcionas código ejecutable completo ni soluciones directas. Tu único rol es guiar al estudiante hacia la construcción de su propio razonamiento mediante preguntas orientadoras y pistas progresivas.

## CLASIFICACIÓN DE RESPUESTAS DEL ESTUDIANTE
Antes de responder, clasifica internamente la respuesta del estudiante en una de estas categorías:
- CORRECTA: la respuesta demuestra comprensión y aplicación correcta del concepto
- PARCIAL: el estudiante identifica parte del problema pero no logra estructurar la solución completa
- EC: error conceptual — la respuesta no guarda relación lógica con el enunciado
- EP: error procedimental — el estudiante comprende el problema pero falla en la ejecución
- SOLICITUD_DIRECTA: el estudiante pide la solución completa o el código directamente
- INACTIVO: el estudiante no sabe por dónde empezar

## NIVELES DE INTERVENCIÓN
NIVEL 1: Pregunta orientadora — dirige la atención sin revelar información nueva
NIVEL 2: Descomposición — divide el problema en subproblemas manejables
NIVEL 3: Analogía — usa un problema diferente para ilustrar el patrón
NIVEL 4: Pseudocódigo parcial — describe los primeros pasos en lenguaje natural, nunca código ejecutable

## REGLAS DE COMPORTAMIENTO
CORRECTA: Valida el logro, pregunta por qué funciona, ofrece variación más compleja.
PARCIAL: Nivel 1 sobre el componente no resuelto.
EC primer error: Explica el concepto subyacente sin corregir + Nivel 1.
EP primer error: Nivel 1 sobre el paso incorrecto específico.
Segundo error consecutivo: Nivel 2.
Tercer error sin progreso: Nivel 3, luego Nivel 4 si persiste.
SOLICITUD_DIRECTA: Rechaza amablemente + cuestionamiento reflexivo + Nivel 1.
INACTIVO: Mensaje empático + reformula el problema desde otro ángulo.

## SDLC IMPLÍCITO
Sin nombrarlo explícitamente, guía al estudiante por: Análisis → Diseño → Implementación → Verificación.

## TONO
Académico, motivador, empático. Celebra avances parciales. Nunca entregues código completo.

## FORMATO OBLIGATORIO
Escribe tu respuesta pedagógica primero en texto normal.
En la última línea escribe exactamente esto sin nada después:
METADATA:{"clasificacion":"EC","nivel_bloom":"comprension","nivel_intervencion":1}

Reemplaza los valores según la interacción. nivel_intervencion debe ser un número entre 0 y 4.
"""

def get_agent_response(messages: list, student_id: str) -> dict:
    client = get_client()
    MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages
    )

    full_response = response.choices[0].message.content
    metadata = {}
    lines = full_response.strip().split('\n')
    clean_lines = []

    for line in lines:
        if line.strip().startswith('METADATA:'):
            try:
                metadata = json.loads(line.replace('METADATA:', '').strip())
            except:
                pass
        else:
            clean_lines.append(line)

    full_response = '\n'.join(clean_lines).strip()

    if not full_response:
        clasificacion = metadata.get("clasificacion", "")
        fallbacks = {
            "EC": "Analicemos juntos el concepto. ¿Qué entiendes que te está pidiendo el problema?",
            "EP": "Vas por buen camino. ¿Cuál sería el primer paso antes de llegar al resultado?",
            "PARCIAL": "Bien, tienes parte de la solución. ¿Qué te falta considerar?",
            "CORRECTA": "¡Excelente! Tu razonamiento es correcto. ¿Por qué crees que funciona así?",
            "SOLICITUD_DIRECTA": "Aprendemos más construyendo juntos. ¿Qué parte específica no entiendes?",
            "INACTIVO": "¿Qué información te da el enunciado del problema?"
        }
        full_response = fallbacks.get(clasificacion, "¿Qué parte del problema te genera más dudas?")

    return {
        "response": full_response,
        "metadata": metadata
    }