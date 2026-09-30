import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def save_interaction(student_id: str, problem_id: str, student_message: str, agent_response: str, metadata: dict):
    try:
        supabase.table("logs").insert({
            "student_id": student_id,
            "problem_id": problem_id,
            "student_message": student_message,
            "agent_response": agent_response,
            "clasificacion": metadata.get("clasificacion", "DESCONOCIDA"),
            "nivel_bloom": metadata.get("nivel_bloom", "desconocido"),
            "nivel_intervencion": metadata.get("nivel_intervencion", 0)
        }).execute()
    except Exception as e:
        print(f"Error guardando log: {e}")

def get_student_logs(student_id: str) -> list:
    try:
        response = supabase.table("logs").select("*").eq("student_id", student_id).order("timestamp").execute()
        return response.data
    except Exception as e:
        print(f"Error obteniendo logs: {e}")
        return []

def get_student_profile(student_id: str) -> dict:
    logs = get_student_logs(student_id)

    if not logs:
        return {"student_id": student_id, "total_interacciones": 0}

    niveles = [log.get("nivel_intervencion", 0) for log in logs]
    clasificaciones = [log.get("clasificacion", "") for log in logs]

    return {
        "student_id": student_id,
        "total_interacciones": len(logs),
        "nivel_intervencion_promedio": round(sum(niveles) / len(niveles), 2),
        "errores_conceptuales": clasificaciones.count("EC"),
        "errores_procedimentales": clasificaciones.count("EP"),
        "respuestas_correctas": clasificaciones.count("CORRECTA"),
        "ultima_interaccion": logs[-1].get("timestamp")
    }