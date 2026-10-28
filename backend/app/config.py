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
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_tokens: int = 1500
    llm_reasoning_effort: str = "low"
 
    # Supabase
    supabase_url: str
    supabase_service_key: str
 
    # API
    cors_origins: str = "*"  # lista separada por comas
 
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()