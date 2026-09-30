from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
import json
import os

from agent import get_agent_response
from logs import save_interaction, get_student_profile

app = FastAPI(title="Agente Tutor - Motor de Decisión Pedagógica")

# CORS para permitir llamadas desde Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de datos
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    student_id: str
    problem_id: str
    messages: List[Message]

class ChatResponse(BaseModel):
    response: str
    metadata: dict
    profile: dict

# Rutas de archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEMS_PATH = os.path.join(BASE_DIR, "data", "problems.json")
frontend_path = os.path.join(BASE_DIR, "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

def load_problems():
    with open(PROBLEMS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_problem_by_id(problem_id: str):
    for p in load_problems():
        if p["id"] == problem_id:
            return p
    return None

# Endpoints
@app.get("/")
async def root():
    html_path = os.path.join(BASE_DIR, "..", "frontend", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/problems")
async def get_problems():
    return load_problems()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    problem = get_problem_by_id(request.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problema no encontrado")

    problem_context = f"""
PROBLEMA ACTUAL:
ID: {problem['id']}
Título: {problem['titulo']}
Enunciado: {problem['enunciado']}
Concepto: {problem['concepto']}
Nivel Bloom objetivo: {problem['nivel_bloom']}
Fase SDLC: {problem['fase_sdlc']}
Criterio de respuesta correcta: {problem['criterio_correcto']}
"""

    messages_for_api = []

    if len(request.messages) == 1:
        messages_for_api.append({
            "role": "user",
            "content": f"{problem_context}\n\nPrimera respuesta del estudiante:\n{request.messages[-1].content}"
        })
    else:
        for msg in request.messages[:-1]:
            messages_for_api.append({
                "role": msg.role,
                "content": msg.content
            })
        messages_for_api.append({
            "role": "user",
            "content": request.messages[-1].content
        })

    result = get_agent_response(messages_for_api, request.student_id)

    save_interaction(
        student_id=request.student_id,
        problem_id=request.problem_id,
        student_message=request.messages[-1].content,
        agent_response=result["response"],
        metadata=result["metadata"]
    )

    profile = get_student_profile(request.student_id)

    return ChatResponse(
        response=result["response"],
        metadata=result["metadata"],
        profile=profile
    )

@app.get("/profile/{student_id}")
async def get_profile(student_id: str):
    return get_student_profile(student_id)

@app.get("/logs")
async def get_all_logs():
    logs_path = os.path.join(BASE_DIR, "data", "logs.json")
    if not os.path.exists(logs_path):
        return []
    with open(logs_path, "r", encoding="utf-8") as f:
        return json.load(f)