"""Arma el contexto común (problema, turnos recientes, último mensaje) que
consumen el clasificador y el redactor."""

MAX_MENSAJES_PREVIOS = 8   # equivale a 4 turnos (estudiante + tutor)
MAX_CARACTERES = 800       # por mensaje, para acotar el consumo de tokens
ETIQUETA_INICIO = "<mensaje_estudiante>"
ETIQUETA_FIN = "</mensaje_estudiante>"

_ROLES = {"user": "Estudiante", "assistant": "Tutor"}


class ContextoError(ValueError):
    """El historial recibido no se puede usar."""


def validar_mensajes(mensajes: list[dict]) -> None:
    if not mensajes or mensajes[-1].get("role") != "user" or not mensajes[-1].get("content", "").strip():
        raise ContextoError("El último mensaje debe ser del estudiante y no estar vacío")


def construir_contexto(problema: dict, mensajes: list[dict]) -> str:
    validar_mensajes(mensajes)
    return (
        "## PROBLEMA\n"
        f"Título: {problema['titulo']}\n"
        f"Enunciado: {problema['enunciado']}\n"
        f"Concepto: {problema['concepto']}\n"
        f"Nivel Bloom objetivo: {problema['nivel_bloom']}\n"
        f"Criterio de respuesta correcta: {problema['criterio_correcto']}\n\n"
        "## TURNOS RECIENTES\n"
        f"{_turnos_previos(mensajes)}\n\n"
        "## ÚLTIMO MENSAJE DEL ESTUDIANTE\n"
        f"{ETIQUETA_INICIO}\n{_ultimo(mensajes)}\n{ETIQUETA_FIN}"
    )


def _turnos_previos(mensajes: list[dict]) -> str:
    previos = [m for m in mensajes[:-1] if m.get("role") in _ROLES][-MAX_MENSAJES_PREVIOS:]
    lineas = [f"{_ROLES[m['role']]}: {_recortar(m['content'])}" for m in previos]
    return "\n".join(lineas) or "(sin turnos previos)"


def _ultimo(mensajes: list[dict]) -> str:
    return _recortar(mensajes[-1]["content"]).replace(ETIQUETA_FIN, "")


def _recortar(texto: str) -> str:
    texto = texto.strip()
    return texto if len(texto) <= MAX_CARACTERES else texto[:MAX_CARACTERES] + "…"
