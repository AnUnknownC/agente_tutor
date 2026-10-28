from fastapi import APIRouter, Depends

from app.api.dependencies import get_catalogo

router = APIRouter()


@router.get("/problems")
def listar_problemas(catalogo=Depends(get_catalogo)):
    """Lista pública: no incluye el criterio de respuesta correcta."""
    return catalogo.listar_publicos()
