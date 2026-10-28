"""Carga de prompts versionados como archivos .md."""
from functools import lru_cache
from pathlib import Path

_DIRECTORIO = Path(__file__).resolve().parent


@lru_cache
def cargar_prompt(nombre: str) -> str:
    return (_DIRECTORIO / f"{nombre}.md").read_text(encoding="utf-8").strip()