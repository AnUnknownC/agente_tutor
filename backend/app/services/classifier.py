"""Clasificador pedagógico: etiqueta el último mensaje del estudiante.

Solo clasifica. El nivel de intervención lo decide `domain.decision`.
"""
from dataclasses import dataclass

from app.domain.enums import Clasificacion, NivelBloom
from app.llm.client import completar_json
from app.prompts import cargar_prompt
from app.services.context_builder import (  # noqa: F401  (re-exportados)
    MAX_CARACTERES, MAX_MENSAJES_PREVIOS, ContextoError, construir_contexto,
)

ESQUEMA = {
    "type": "object",
    "properties": {
        "clasificacion": {"type": "string", "enum": [c.value for c in Clasificacion]},
        "nivel_bloom": {"type": "string", "enum": [n.value for n in NivelBloom]},
        "justificacion": {"type": "string"},
    },
    "required": ["clasificacion", "nivel_bloom", "justificacion"],
    "additionalProperties": False,
}


class ClasificadorError(Exception):
    """La entrada es inválida o la salida del modelo no corresponde al vocabulario."""


@dataclass(frozen=True)
class Resultado:
    clasificacion: Clasificacion
    nivel_bloom: NivelBloom
    justificacion: str


def clasificar(problema: dict, mensajes: list[dict], *, seguimiento: bool = False,
              on_uso=None, cliente=None, ajustes=None) -> Resultado:
    """`mensajes` es el historial completo; el último debe ser del estudiante.

    `seguimiento`: el turno anterior fue CORRECTA, así que el tutor planteó una
    pregunta o variación y el mensaje debe evaluarse contra ella.
    """
    entrada = construir_mensajes(problema, mensajes, seguimiento=seguimiento)
    datos = completar_json(
        entrada, ESQUEMA, nombre_esquema="clasificacion", temperature=0.0,
        on_uso=on_uso, cliente=cliente, ajustes=ajustes,
    )
    try:
        return Resultado(
            clasificacion=Clasificacion(datos["clasificacion"]),
            nivel_bloom=NivelBloom(datos["nivel_bloom"]),
            justificacion=str(datos.get("justificacion", "")).strip(),
        )
    except (KeyError, ValueError) as exc:
        raise ClasificadorError(f"Salida fuera del vocabulario: {datos}") from exc


NOTA_SEGUIMIENTO = (
    "\n\n## FASE DE SEGUIMIENTO\n"
    "El estudiante ya resolvió el problema original. El último mensaje del tutor "
    "planteó una pregunta o variación: evalúa el mensaje del estudiante contra ESA "
    "pregunta, no contra el criterio original. Si la responde bien → CORRECTA; si "
    "acierta solo una parte → PARCIAL; el resto sigue el orden de decisión."
)


def construir_mensajes(problema: dict, mensajes: list[dict], *, seguimiento: bool = False) -> list[dict]:
    try:
        contexto = construir_contexto(problema, mensajes)
    except ContextoError as exc:
        raise ClasificadorError(str(exc)) from exc
    return [
        {"role": "system", "content": cargar_prompt("classifier")},
        {"role": "user", "content": contexto + (NOTA_SEGUIMIENTO if seguimiento else "")},
    ]