"""Cliente único del proveedor de LLM (Groq, API compatible con OpenAI).

Expone una sola función, `completar`, que devuelve el texto generado. Aquí se
concentran los parámetros del modelo, la salida estructurada y los reintentos.
"""
import json
import logging
from functools import lru_cache

from app.config import get_settings
from app.llm.rotador import obtener_rotador

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
    detalles_prompt = getattr(uso, "prompt_tokens_details", None)
    return {
        "modelo": modelo,
        "prompt_tokens": getattr(uso, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(uso, "completion_tokens", 0) or 0,
        "total_tokens": getattr(uso, "total_tokens", 0) or 0,
        "reasoning_tokens": getattr(detalles, "reasoning_tokens", 0) or 0,
        "cached_tokens": getattr(detalles_prompt, "cached_tokens", 0) or 0,
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


SEGUNDOS_LIMITE_TASA = 60   # 429 sin Retry-After
SEGUNDOS_ERROR_SERVIDOR = 20  # 5xx o fallo de conexión
SEGUNDOS_MODELO_INVALIDO = 600  # otros 4xx: el modelo no acepta la petición


def _enfriamiento(exc: Exception) -> float | None:
    """Segundos que conviene apartar el modelo, o None si el fallo no es del modelo."""
    estado = getattr(exc, "status_code", None)
    if estado == 429:
        cabeceras = getattr(getattr(exc, "response", None), "headers", None) or {}
        try:
            return min(max(float(cabeceras.get("retry-after")), 5.0), 120.0)
        except (TypeError, ValueError):
            return SEGUNDOS_LIMITE_TASA
    if estado is None:
        nombre = type(exc).__name__
        return SEGUNDOS_ERROR_SERVIDOR if ("Connection" in nombre or "Timeout" in nombre) else None
    if estado >= 500:
        return SEGUNDOS_ERROR_SERVIDOR
    if 400 <= estado < 500:
        return SEGUNDOS_MODELO_INVALIDO
    return None


def _parametros(ajustes, modelo, mensajes, temperature, esquema, nombre_esquema) -> dict:
    parametros = {
        "model": modelo,
        "messages": mensajes,
        "temperature": temperature,
        "max_completion_tokens": ajustes.llm_max_tokens,
    }
    if "gpt-oss" in modelo:  # solo estos modelos aceptan reasoning_effort
        parametros["reasoning_effort"] = ajustes.llm_reasoning_effort
    if esquema is not None:
        parametros["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": nombre_esquema, "strict": True, "schema": esquema},
        }
    return parametros


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
    rotador=None,
) -> str:
    """Envía los mensajes a un modelo del rotador y devuelve el contenido como texto.

    Si se pasa `esquema` (JSON Schema), la salida se restringe a ese esquema
    en modo estricto. Ante límite de tasa o error del proveedor, aparta ese
    modelo y prueba con otro sin gastar reintentos (máximo uno por modelo);
    ante contenido vacío u otros fallos reintenta hasta `reintentos` veces.
    Cada llamada informa su consumo (con el modelo usado) al log y a `on_uso`.
    """
    ajustes = ajustes or get_settings()
    cliente = cliente or _cliente_por_defecto()
    rotador = rotador or obtener_rotador(
        getattr(ajustes, "modelos_ponderados", None) or [(ajustes.groq_model, 1)]
    )

    ultimo_error: Exception | None = None
    reintentos_usados = saltos = 0
    saltos_max = len(rotador.modelos)
    while reintentos_usados <= reintentos and saltos <= saltos_max:
        modelo = rotador.elegir()
        try:
            respuesta = cliente.chat.completions.create(
                **_parametros(ajustes, modelo, mensajes, temperature, esquema, nombre_esquema)
            )
            _registrar_uso(_extraer_uso(respuesta, modelo), on_uso)
            contenido = (respuesta.choices[0].message.content or "").strip()
            if not contenido:
                raise LLMError("El modelo devolvió contenido vacío")
            return contenido
        except Exception as exc:
            ultimo_error = exc
            segundos = _enfriamiento(exc)
            logger.warning("Fallo del LLM con %s: %s", modelo, exc)
            if segundos is not None:
                rotador.apartar(modelo, segundos)
                saltos += 1
            else:
                reintentos_usados += 1

    raise LLMError("No se obtuvo respuesta del modelo") from ultimo_error


def completar_json(mensajes: list[dict], esquema: dict, **kwargs) -> dict:
    """Como `completar`, pero devuelve el objeto JSON ya interpretado."""
    texto = completar(mensajes, esquema=esquema, **kwargs)
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise LLMError("La respuesta del modelo no es JSON válido") from exc