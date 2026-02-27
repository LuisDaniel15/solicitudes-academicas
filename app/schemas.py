from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


# ── SCHEMAS DE ROL ───────────────────────────────────────────

class RolBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class RolOut(RolBase):
    id: int

    class Config:
        from_attributes = True


# ── SCHEMAS DE USUARIO ───────────────────────────────────────

class UsuarioBase(BaseModel):
    nombres: str
    apellidos: str
    email: EmailStr
    telefono_whatsapp: Optional[str] = None
    numero_documento: str
    rol_id: int

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioOut(UsuarioBase):
    id: UUID          # ← cambiamos str por UUID
    activo: bool
    creado_en: datetime
    rol: RolOut

    class Config:
        from_attributes = True


# ── SCHEMAS DE TIPO SOLICITUD ─────────────────────────────────

class TipoSolicitudOut(BaseModel):
    id: int
    nombre: str
    dias_respuesta_habil: int

    class Config:
        from_attributes = True


# ── SCHEMAS DE ESTADO ─────────────────────────────────────────

class EstadoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    es_final: bool

    class Config:
        from_attributes = True


# ── SCHEMAS DE SOLICITUD ──────────────────────────────────────

class SolicitudCreate(BaseModel):
    tipo_solicitud_id: int
    descripcion: str

class SolicitudUpdateEstado(BaseModel):
    estado_id: int
    comentario: Optional[str] = None

class SolicitudOut(BaseModel):
    id: UUID          # ← UUID
    codigo_referencia: Optional[str]
    descripcion: str
    respuesta_final: Optional[str]
    canal_origen: str
    creado_en: datetime
    actualizado_en: Optional[datetime]
    solicitante: UsuarioOut
    tipo_solicitud: TipoSolicitudOut
    estado: EstadoOut

    class Config:
        from_attributes = True


# ── SCHEMAS DE HISTORIAL ──────────────────────────────────────

class HistorialOut(BaseModel):
    id: int
    comentario: Optional[str]
    creado_en: datetime
    estado_nuevo: EstadoOut

    class Config:
        from_attributes = True


# ── SCHEMAS DE WHATSAPP ───────────────────────────────────────

class MensajeEntranteWhatsApp(BaseModel):
    telefono: str
    mensaje: str

class RespuestaAsistente(BaseModel):
    respuesta: str
    sesion_id: Optional[str] = None


# ── SCHEMA DE LOGIN ───────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
