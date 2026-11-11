"""Construcción de las piezas compartidas. Las rutas las piden con Depends,
lo que permite sustituirlas en las pruebas."""
import secrets
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.db.logs_repository import LogsRepository
from app.services.problems import CatalogoProblemas
from app.services.tutor_service import TutorService

RUTA_PROBLEMAS = Path(__file__).resolve().parents[1] / "data" / "problems.json"


@lru_cache
def get_repositorio() -> LogsRepository:
    return LogsRepository()


@lru_cache
def get_catalogo() -> CatalogoProblemas:
    return CatalogoProblemas(RUTA_PROBLEMAS)


@lru_cache
def get_tutor_service() -> TutorService:
    return TutorService(get_repositorio())


def get_max_turnos() -> int:
    return get_settings().max_turnos_estudiante


def get_admin_token() -> str:
    return get_settings().admin_token


def requerir_admin(x_admin_token: str | None = Header(default=None), token: str = Depends(get_admin_token)):
    """Protege las rutas de revisión. Sin ADMIN_TOKEN configurado, no existen."""
    if not token:
        raise HTTPException(status_code=404, detail="No encontrado")
    if not x_admin_token or not secrets.compare_digest(x_admin_token.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="Token inválido")
