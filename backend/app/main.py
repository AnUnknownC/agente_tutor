import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_chat, routes_problems, routes_profile
from app.config import get_settings
from app.db.logs_repository import LogsRepositoryError

logging.basicConfig(level=logging.INFO)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="Agente Tutor - Motor de Decisión Pedagógica")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins_list,
        allow_credentials=False,  # no se usan cookies; "*" con credenciales no es válido
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_chat.router)
    app.include_router(routes_problems.router)
    app.include_router(routes_profile.router)

    @app.exception_handler(LogsRepositoryError)
    async def logs_no_disponibles(_: Request, __: LogsRepositoryError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Servicio temporalmente no disponible. Intenta de nuevo."},
        )

    if FRONTEND_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def inicio():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
