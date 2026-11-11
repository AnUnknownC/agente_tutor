"""Acceso a la tabla `logs`. Solo lee y escribe datos; no aplica reglas."""
import logging

from app.domain.enums import Clasificacion, NivelBloom

TABLA = "logs"
NIVEL_MIN, NIVEL_MAX = 0, 4

logger = logging.getLogger(__name__)


class LogsRepositoryError(Exception):
    """Fallo al leer o escribir logs. No se oculta: el estado depende de ellos."""


class LogsRepository:
    def __init__(self, client=None):
        if client is None:
            from app.db.client import get_supabase
            client = get_supabase()
        self._client = client

    def guardar_interaccion(
        self,
        *,
        student_id: str,
        problem_id: str,
        student_message: str,
        agent_response: str,
        clasificacion: Clasificacion,
        nivel_bloom: NivelBloom,
        nivel_intervencion: int,
    ) -> None:
        if not NIVEL_MIN <= nivel_intervencion <= NIVEL_MAX:
            raise ValueError(f"nivel_intervencion fuera de rango: {nivel_intervencion}")

        fila = {
            "student_id": student_id,
            "problem_id": problem_id,
            "student_message": student_message,
            "agent_response": agent_response,
            "clasificacion": clasificacion.value,
            "nivel_bloom": nivel_bloom.value,
            "nivel_intervencion": nivel_intervencion,
        }
        try:
            self._client.table(TABLA).insert(fila).execute()
        except Exception as exc:
            logger.exception("Error guardando log")
            raise LogsRepositoryError("No se pudo guardar la interacción") from exc

    def obtener_logs(self, student_id: str, problem_id: str) -> list[dict]:
        """Logs del estudiante en un problema, en orden cronológico."""
        return self._consultar(student_id, problem_id)

    def obtener_logs_estudiante(self, student_id: str) -> list[dict]:
        """Logs del estudiante en todos los problemas, en orden cronológico."""
        return self._consultar(student_id, None)

    def _consultar(self, student_id: str, problem_id: str | None) -> list[dict]:
        try:
            consulta = self._client.table(TABLA).select("*").eq("student_id", student_id)
            if problem_id is not None:
                consulta = consulta.eq("problem_id", problem_id)
            respuesta = consulta.order("timestamp").execute()
        except Exception as exc:
            logger.exception("Error obteniendo logs")
            raise LogsRepositoryError("No se pudieron obtener los logs") from exc
        return respuesta.data or []

    def listar_estudiantes(self) -> list[dict]:
        """Estudiantes con logs: id, número de turnos y última interacción (más reciente primero)."""
        filas, pagina, desde = [], 1000, 0
        try:
            while True:
                respuesta = (
                    self._client.table(TABLA).select("student_id,timestamp").order("timestamp")
                    .range(desde, desde + pagina - 1).execute()
                )
                datos = respuesta.data or []
                filas.extend(datos)
                if len(datos) < pagina:
                    break
                desde += pagina
        except Exception as exc:
            logger.exception("Error listando estudiantes")
            raise LogsRepositoryError("No se pudo listar los estudiantes") from exc

        agregado: dict[str, dict] = {}
        for fila in filas:
            e = agregado.setdefault(fila["student_id"], {"student_id": fila["student_id"], "turnos": 0, "ultima_interaccion": None})
            e["turnos"] += 1
            e["ultima_interaccion"] = fila.get("timestamp") or e["ultima_interaccion"]
        return sorted(agregado.values(), key=lambda e: e["ultima_interaccion"] or "", reverse=True)
