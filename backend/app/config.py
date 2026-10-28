"""Configuración centralizada. Única fuente de variables de entorno."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> raíz del repositorio
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # LLM (Groq, API compatible con OpenAI)
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-20b"
    # Varios modelos, "modelo:peso,modelo:peso". Vacío = solo groq_model.
    groq_models: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_tokens: int = 1500
    llm_reasoning_effort: str = "low"

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Experimento: turnos máximos por estudiante (0 = sin límite)
    max_turnos_estudiante: int = 8

    # API
    cors_origins: str = "*"  # lista separada por comas

    @property
    def modelos_ponderados(self) -> list[tuple[str, int]]:
        from app.llm.rotador import interpretar

        return interpretar(self.groq_models) or [(self.groq_model, 1)]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()