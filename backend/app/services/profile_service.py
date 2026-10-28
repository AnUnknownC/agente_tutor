"""Perfil agregado del estudiante a partir de sus logs."""


def calcular_perfil(student_id: str, logs: list[dict]) -> dict:
    if not logs:
        return {"student_id": student_id, "total_interacciones": 0}

    niveles = [_entero(log.get("nivel_intervencion")) for log in logs]
    clasificaciones = [log.get("clasificacion") for log in logs]

    return {
        "student_id": student_id,
        "total_interacciones": len(logs),
        "nivel_intervencion_promedio": round(sum(niveles) / len(niveles), 2),
        "errores_conceptuales": clasificaciones.count("EC"),
        "errores_procedimentales": clasificaciones.count("EP"),
        "respuestas_correctas": clasificaciones.count("CORRECTA"),
        "ultima_interaccion": logs[-1].get("timestamp"),
    }


def _entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0
