"""Catálogo de problemas cargado desde `data/problems.json`."""
import json
from pathlib import Path

CLAVES_REQUERIDAS = ("id", "titulo", "enunciado", "concepto", "nivel_bloom", "criterio_correcto")
# Lista blanca: solo estos campos se envían al estudiante. Todo lo demás
# (criterio, pistas, analogía, pseudocódigo) es material del tutor.
CLAVES_PUBLICAS = ("id", "titulo", "enunciado", "concepto", "nivel_bloom", "fase_sdlc")


class CatalogoProblemas:
    def __init__(self, ruta: Path):
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if not isinstance(datos, list):
            raise ValueError("problems.json debe contener una lista de problemas")

        ids = set()
        for problema in datos:
            faltantes = [c for c in CLAVES_REQUERIDAS if c not in problema]
            if faltantes:
                raise ValueError(f"Problema {problema.get('id', '?')}: faltan {faltantes}")
            if problema["id"] in ids:
                raise ValueError(f"Id de problema repetido: {problema['id']}")
            ids.add(problema["id"])

        self._problemas = datos
        self._por_id = {p["id"]: p for p in datos}

    def obtener(self, problem_id: str) -> dict | None:
        return self._por_id.get(problem_id)

    def listar_publicos(self) -> list[dict]:
        return [{k: p[k] for k in CLAVES_PUBLICAS if k in p} for p in self._problemas]