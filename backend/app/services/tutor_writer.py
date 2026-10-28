"""Redactor: convierte la decisión pedagógica en el mensaje para el estudiante.

No decide nada. Después de generar, revisa que el texto no contenga código y,
si lo contiene, regenera una vez; si persiste, usa un mensaje de respaldo.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass

from app.domain.decision import Decision
from app.domain.enums import Accion, Clasificacion
from app.llm.client import completar
from app.prompts import cargar_prompt
from app.services.context_builder import construir_contexto

logger = logging.getLogger(__name__)

TEMPERATURA = 0.2

# Ayuda autorizada (material del profesor en problems.json) según el nivel.
AYUDAS_POR_NIVEL = {1: "pista_nivel1", 2: "pista_nivel2", 3: "analogia", 4: "pseudocodigo_parcial"}

REFUERZO = (
    "Tu respuesta anterior incluía código o sintaxis de programación, lo cual está "
    "prohibido. Reescríbela solo en lenguaje natural, sin ninguna expresión de código."
)

RESPALDOS = {
    Clasificacion.EC: "Analicemos juntos el concepto. ¿Qué entiendes que te está pidiendo el problema?",
    Clasificacion.EP: "Vas por buen camino. ¿Cuál sería el primer paso antes de llegar al resultado?",
    Clasificacion.PARCIAL: "Bien, tienes parte de la solución. ¿Qué te falta considerar?",
    Clasificacion.CORRECTA: "¡Excelente! Tu razonamiento es correcto. ¿Por qué crees que funciona así?",
    Clasificacion.SOLICITUD_DIRECTA: "Aprendemos más construyendo juntos. ¿Qué parte específica no entiendes?",
    Clasificacion.INACTIVO: "¿Qué información te da el enunciado del problema?",
}

_PATRONES_CODIGO = [
    re.compile(r"```"),
    re.compile(r"^\s*(def|class|import|from|for|while|if|elif|else|return|print|try|except|"
               r"switch|case|public|private|static|void|let|const|var)\b[^\n]*[:;{})]\s*$",
               re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*[A-Za-z_]\w*\s*[-+*/]?=\s*[^=\s][^\n]*$", re.MULTILINE),
    re.compile(r"\b(print|printf|scanf|range|len|input|append|System\.out\.println)\s*\("),
    # asignaciones o comparaciones dentro de una frase, p. ej. “precio = 1500”
    re.compile(r"[A-Za-z_]\w*\s*(?:==|!=|<=|>=|[-+*/]?=)\s*\S"),
]


@dataclass(frozen=True)
class Redaccion:
    texto: str
    con_respaldo: bool = False


def contiene_codigo(texto: str) -> bool:
    return any(patron.search(texto) for patron in _PATRONES_CODIGO)


def construir_mensajes(problema: dict, mensajes: list[dict], clasificacion: Clasificacion,
                       decision: Decision) -> list[dict]:
    fase = "Análisis" if decision.accion == Accion.RETROCEDER else problema.get("fase_sdlc", "")
    instruccion = (
        "\n\n## INSTRUCCIÓN PEDAGÓGICA\n"
        f"Clasificación: {clasificacion.value}\n"
        f"Nivel de intervención: {decision.nivel_intervencion} (0 = sin intervención)\n"
        f"Acción: {decision.accion.value}\n"
        f"Fase de trabajo: {fase}"
    )
    ayuda = _ayuda_autorizada(problema, decision)
    if ayuda:
        instruccion += f"\nAyuda autorizada para este nivel (material del profesor):\n<ayuda>\n{ayuda}\n</ayuda>"
    return [
        {"role": "system", "content": cargar_prompt("writer")},
        {"role": "user", "content": construir_contexto(problema, mensajes, incluir_criterio=False) + instruccion},
    ]


def _ayuda_autorizada(problema: dict, decision: Decision) -> str | None:
    if decision.accion == Accion.RETROCEDER:  # el retroceso replantea el reto; no se da ayuda
        return None
    clave = AYUDAS_POR_NIVEL.get(decision.nivel_intervencion)
    ayuda = problema.get(clave) if clave else None
    return ayuda.strip() if isinstance(ayuda, str) and ayuda.strip() else None


def _es_raro(c: str) -> bool:
    """Espacio Unicode distinto del normal, o carácter invisible/de control (salvo saltos de línea y tabulador)."""
    if c in "\n\t ":
        return False
    return unicodedata.category(c) in {"Zs", "Zl", "Zp", "Cf", "Cc"} or c in "\u034f\u2800\u3164"


def normalizar_texto(texto: str) -> str:
    """Convierte espacios Unicode y caracteres invisibles en espacios normales.

    Registra en el log los códigos encontrados para poder diagnosticar el origen.
    """
    raros = {c for c in texto if _es_raro(c)}
    if raros:
        logger.warning("Caracteres raros en la respuesta del modelo: %s",
                       ", ".join(f"U+{ord(c):04X}" for c in sorted(raros)))
        texto = "".join(" " if c in raros else c for c in texto)
    return re.sub(r"[ \t]{2,}", " ", texto).strip()


def redactar(problema: dict, mensajes: list[dict], clasificacion: Clasificacion, decision: Decision,
             *, on_uso=None, cliente=None, ajustes=None) -> Redaccion:
    entrada = construir_mensajes(problema, mensajes, clasificacion, decision)

    texto = _generar(entrada, on_uso, cliente, ajustes)
    if not contiene_codigo(texto):
        return Redaccion(texto)

    corregido = _generar(entrada + [{"role": "user", "content": REFUERZO}], on_uso, cliente, ajustes)
    if not contiene_codigo(corregido):
        return Redaccion(corregido)

    return Redaccion(RESPALDOS[clasificacion], con_respaldo=True)


def _generar(entrada, on_uso, cliente, ajustes) -> str:
    return normalizar_texto(
        completar(entrada, temperature=TEMPERATURA, on_uso=on_uso, cliente=cliente, ajustes=ajustes)
    )