"""Cliente único del proveedor de LLM (Groq, API compatible con OpenAI).
 
Expone una sola función, `completar`, que devuelve el texto generado. Aquí se
concentran los parámetros del modelo, la salida estructurada y los reintentos.
"""
import json
import logging
from functools import lru_cache
 
from app.config import get_settings
 
logger = logging.getLogger(__name__)
 
 
class LLMError(Exception):
    """El modelo no devolvió una respuesta utilizable tras los reintentos."""
 
 
@lru_cache
def _cliente_por_defecto():
    from openai import OpenAI  # import diferido: no se requiere para las pruebas
 
    ajustes = get_settings()
    return OpenAI(base_url=ajustes.groq_base_url, api_key=ajustes.groq_api_key)
 
 
def _extraer_uso(respuesta, modelo: str) -> dict:
    """Tokens consumidos por la llamada, o {} si el proveedor no los informa."""
    uso = getattr(respuesta, "usage", None)
    if uso is None:
        return {}
    detalles = getattr(uso, "completion_tokens_details", None)
    return {
        "modelo": modelo,
        "prompt_tokens": getattr(uso, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(uso, "completion_tokens", 0) or 0,
        "total_tokens": getattr(uso, "total_tokens", 0) or 0,
        "reasoning_tokens": getattr(detalles, "reasoning_tokens", 0) or 0,
    }
 
 
def _registrar_uso(uso: dict, on_uso) -> None:
    if not uso:
        return
    logger.info("Uso LLM: %s", uso)
    if on_uso is not None:
        try:
            on_uso(uso)
        except Exception:
            logger.exception("Falló el callback de uso")
 
 
def completar(
    mensajes: list[dict],
    *,
    temperature: float = 0.0,
    esquema: dict | None = None,
    nombre_esquema: str = "respuesta",
    reintentos: int = 1,
    on_uso=None,
    cliente=None,
    ajustes=None,
) -> str:
    """Envía los mensajes al modelo y devuelve el contenido como texto.
 
    Si se pasa `esquema` (JSON Schema), la salida se restringe a ese esquema
    en modo estricto. Reintenta ante errores del proveedor o contenido vacío.
    Cada llamada, incluso la que devuelve contenido vacío, informa su consumo de
    tokens al log y, si se entrega, al callback `on_uso(dict)`.
    """
    ajustes = ajustes or get_settings()
    cliente = cliente or _cliente_por_defecto()
 
    parametros = {
        "model": ajustes.groq_model,
        "messages": mensajes,
        "temperature": temperature,
        "max_completion_tokens": ajustes.llm_max_tokens,
        "reasoning_effort": ajustes.llm_reasoning_effort,
    }
    if esquema is not None:
        parametros["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": nombre_esquema, "strict": True, "schema": esquema},
        }
 
    ultimo_error: Exception | None = None
    for intento in range(reintentos + 1):
        try:
            respuesta = cliente.chat.completions.create(**parametros)
            _registrar_uso(_extraer_uso(respuesta, ajustes.groq_model), on_uso)
            contenido = (respuesta.choices[0].message.content or "").strip()
            if not contenido:
                raise LLMError("El modelo devolvió contenido vacío")
            return contenido
        except Exception as exc:
            ultimo_error = exc
            logger.warning("Fallo del LLM (intento %d de %d): %s", intento + 1, reintentos + 1, exc)
 
    raise LLMError("No se obtuvo respuesta del modelo") from ultimo_error
 
 
def completar_json(mensajes: list[dict], esquema: dict, **kwargs) -> dict:
    """Como `completar`, pero devuelve el objeto JSON ya interpretado."""
    texto = completar(mensajes, esquema=esquema, **kwargs)
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise LLMError("La respuesta del modelo no es JSON válido") from exc