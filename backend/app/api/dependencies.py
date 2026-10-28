"""Construcción de las piezas compartidas. Las rutas las piden con Depends,
lo que permite sustituirlas en las pruebas."""
from functools import lru_cache
from pathlib import Path

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
