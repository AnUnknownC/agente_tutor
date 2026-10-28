import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_catalogo, get_max_turnos, get_repositorio, get_tutor_service
from app.api.schemas import ChatRequest, ChatResponse
from app.db.logs_repository import LogsRepositoryError
from app.services.profile_service import calcular_perfil

logger = logging.getLogger(__name__)
router = APIRouter()

MENSAJE_LIMITE = (
    "¡Gracias por tu participación! Alcanzaste el máximo de turnos de esta sesión. "
    "Ya no necesitas enviar más mensajes."
)


# `def` (no `async def`): los clientes de Groq y Supabase son síncronos y así
# FastAPI los ejecuta en un hilo sin bloquear el servidor.
@router.post("/chat", response_model=ChatResponse)
def chat(
    solicitud: ChatRequest,
    servicio=Depends(get_tutor_service),
    repositorio=Depends(get_repositorio),
    catalogo=Depends(get_catalogo),
    max_turnos: int = Depends(get_max_turnos),
):
    problema = catalogo.obtener(solicitud.problem_id)
    if problema is None:
        raise HTTPException(status_code=404, detail="Problema no encontrado")

    # Límite por estudiante (todos los problemas), antes de gastar cupo del LLM.
    previos = []
    if max_turnos > 0:
        try:
            previos = repositorio.obtener_logs_estudiante(solicitud.student_id)
        except LogsRepositoryError:
            # Sin lectura no se puede verificar el tope; si la BD cayó de verdad,
            # el servicio falla al leer/guardar y responde 503.
            logger.exception("No se pudo verificar el límite de turnos")
        if len(previos) >= max_turnos:
            return ChatResponse(
                response=MENSAJE_LIMITE,
                metadata={"registrado": False, "motivo": "limite_turnos", "turnos": len(previos)},
                profile=calcular_perfil(solicitud.student_id, previos),
            )

    mensajes = [m.model_dump() for m in solicitud.messages]
    turno = servicio.responder(solicitud.student_id, solicitud.problem_id, problema, mensajes)

    try:
        perfil = calcular_perfil(solicitud.student_id, repositorio.obtener_logs_estudiante(solicitud.student_id))
    except LogsRepositoryError:
        # El turno ya está guardado: no se pierde la respuesta por un fallo del perfil.
        logger.exception("No se pudo calcular el perfil")
        perfil = {}

    return ChatResponse(response=turno.respuesta, metadata=turno.metadata, profile=perfil)