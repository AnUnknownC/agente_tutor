"""Revisión para el investigador: lista de estudiantes y sus conversaciones."""
from fastapi import APIRouter, Depends

from app.api.dependencies import get_repositorio, requerir_admin

router = APIRouter(prefix="/admin", dependencies=[Depends(requerir_admin)])

CAMPOS_CONVERSACION = (
    "timestamp", "problem_id", "student_message", "agent_response",
    "clasificacion", "nivel_bloom", "nivel_intervencion",
)


@router.get("/students")
def listar_estudiantes(repositorio=Depends(get_repositorio)):
    return repositorio.listar_estudiantes()


@router.get("/students/{student_id}/conversation")
def conversacion(student_id: str, repositorio=Depends(get_repositorio)):
    logs = repositorio.obtener_logs_estudiante(student_id)
    return [{campo: log.get(campo) for campo in CAMPOS_CONVERSACION} for log in logs]
