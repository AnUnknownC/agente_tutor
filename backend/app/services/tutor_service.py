"""Orquesta un turno completo del tutor.

Flujo: leer historial → calcular estado → clasificar → decidir → redactar →
guardar → devolver texto y metadata por separado.
"""
import logging
from dataclasses import dataclass, field

from app.db.logs_repository import LogsRepository
from app.domain.decision import decidir
from app.domain.state import calcular_estado
from app.llm.client import LLMError
from app.services.classifier import ClasificadorError, clasificar
from app.services.tutor_writer import RESPALDOS, redactar

logger = logging.getLogger(__name__)

MENSAJE_REINTENTO = (
    "En este momento no pude procesar tu respuesta. "
    "¿Puedes enviarla de nuevo en unos segundos?"
)


@dataclass(frozen=True)
class Turno:
    """`respuesta` es lo único que ve el estudiante; `metadata` es para el sistema."""
    respuesta: str
    metadata: dict = field(default_factory=dict)


class TutorService:
    def __init__(self, repositorio: LogsRepository, *, clasificador=clasificar, redactor=redactar):
        self._repositorio = repositorio
        self._clasificar = clasificador
        self._redactar = redactor

    def responder(self, student_id: str, problem_id: str, problema: dict, mensajes: list[dict]) -> Turno:
        """Procesa el último mensaje del estudiante.

        Los errores de lectura o escritura de logs (LogsRepositoryError) se
        propagan: sin ellos el estado pedagógico quedaría inconsistente.
        """
        logs = self._repositorio.obtener_logs(student_id, problem_id)
        estado = calcular_estado(logs)

        usos: list[dict] = []
        try:
            resultado = self._clasificar(problema, mensajes, on_uso=usos.append)
        except (LLMError, ClasificadorError):
            logger.exception("Falló la clasificación; no se registra el turno")
            return Turno(MENSAJE_REINTENTO, {"registrado": False, "motivo": "clasificador"})

        decision = decidir(resultado.clasificacion, estado)

        try:
            redaccion = self._redactar(
                problema, mensajes, resultado.clasificacion, decision, on_uso=usos.append,
            )
            texto, con_respaldo = redaccion.texto, redaccion.con_respaldo
        except LLMError:
            logger.exception("Falló el redactor; se usa el mensaje de respaldo")
            texto, con_respaldo = RESPALDOS[resultado.clasificacion], True

        if con_respaldo:
            logger.warning("Turno de %s en %s respondido con mensaje de respaldo", student_id, problem_id)

        self._repositorio.guardar_interaccion(
            student_id=student_id,
            problem_id=problem_id,
            student_message=mensajes[-1]["content"],
            agent_response=texto,
            clasificacion=resultado.clasificacion,
            nivel_bloom=resultado.nivel_bloom,
            nivel_intervencion=decision.nivel_intervencion,
        )

        return Turno(texto, {
            "registrado": True,
            "clasificacion": resultado.clasificacion.value,
            "nivel_bloom": resultado.nivel_bloom.value,
            "nivel_intervencion": decision.nivel_intervencion,
            "accion": decision.accion.value,
            "justificacion": resultado.justificacion,
            "con_respaldo": con_respaldo,
            "tokens_totales": sum(u.get("total_tokens", 0) for u in usos),
        })
