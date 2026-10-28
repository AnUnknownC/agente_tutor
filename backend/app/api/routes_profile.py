from fastapi import APIRouter, Depends

from app.api.dependencies import get_repositorio
from app.services.profile_service import calcular_perfil

router = APIRouter()


@router.get("/profile/{student_id}")
def obtener_perfil(student_id: str, repositorio=Depends(get_repositorio)):
    return calcular_perfil(student_id, repositorio.obtener_logs_estudiante(student_id))
