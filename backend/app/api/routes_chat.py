import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_catalogo, get_repositorio, get_tutor_service
from app.api.schemas import ChatRequest, ChatResponse
from app.db.logs_repository import LogsRepositoryError
from app.services.profile_service import calcular_perfil

logger = logging.getLogger(__name__)
router = APIRouter()


# `def` (no `async def`): los clientes de Groq y Supabase son síncronos y así
# FastAPI los ejecuta en un hilo sin bloquear el servidor.
@router.post("/chat", response_model=ChatResponse)
def chat(
    solicitud: ChatRequest,
    servicio=Depends(get_tutor_service),
    repositorio=Depends(get_repositorio),
    catalogo=Depends(get_catalogo),
):
    problema = catalogo.obtener(solicitud.problem_id)
    if problema is None:
        raise HTTPException(status_code=404, detail="Problema no encontrado")

    mensajes = [m.model_dump() for m in solicitud.messages]
    turno = servicio.responder(solicitud.student_id, solicitud.problem_id, problema, mensajes)

    try:
        perfil = calcular_perfil(solicitud.student_id, repositorio.obtener_logs_estudiante(solicitud.student_id))
    except LogsRepositoryError:
        # El turno ya está guardado: no se pierde la respuesta por un fallo del perfil.
        logger.exception("No se pudo calcular el perfil")
        perfil = {}

    return ChatResponse(response=turno.respuesta, metadata=turno.metadata, profile=perfil)
