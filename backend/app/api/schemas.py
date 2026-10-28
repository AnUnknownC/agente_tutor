from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Message(BaseModel):
    role: Literal["user", "assistant"]  # se rechaza "system" y cualquier otro rol
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=100)
    problem_id: str = Field(min_length=1, max_length=100)
    messages: list[Message] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def el_ultimo_mensaje_es_del_estudiante(self):
        ultimo = self.messages[-1]
        if ultimo.role != "user" or not ultimo.content.strip():
            raise ValueError("El último mensaje debe ser del estudiante y no estar vacío")
        return self


class ChatResponse(BaseModel):
    response: str   # lo único que debe mostrar el frontend al estudiante
    metadata: dict  # datos del sistema
    profile: dict
