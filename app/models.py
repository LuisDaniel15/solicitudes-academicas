from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


# ── CLASE: Rol ───────────────────────────────────────────────
# Representa la tabla "roles" en la base de datos
class Rol(Base):
    __tablename__ = "roles"

    id       = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String(50), unique=True, nullable=False)
    descripcion = Column(Text)

    # Un rol tiene muchos usuarios
    usuarios = relationship("Usuario", back_populates="rol")


# ── CLASE: Usuario ───────────────────────────────────────────
# Representa la tabla "usuarios" en la base de datos
class Usuario(Base):
    __tablename__ = "usuarios"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nombres           = Column(String(100), nullable=False)
    apellidos         = Column(String(100), nullable=False)
    email             = Column(String(150), unique=True, nullable=False)
    telefono_whatsapp = Column(String(20), unique=True)
    numero_documento  = Column(String(30), unique=True, nullable=False)
    hashed_password   = Column(String(255))
    rol_id            = Column(Integer, ForeignKey("roles.id"), nullable=False)
    activo            = Column(Boolean, default=True)
    creado_en         = Column(DateTime, server_default=func.now())

    # Un usuario pertenece a un rol
    rol         = relationship("Rol", back_populates="usuarios")
    # Un usuario puede tener muchas solicitudes
    solicitudes = relationship("Solicitud", back_populates="solicitante")


# ── CLASE: TipoSolicitud ─────────────────────────────────────
# Representa la tabla "tipos_solicitud"
class TipoSolicitud(Base):
    __tablename__ = "tipos_solicitud"

    id                   = Column(Integer, primary_key=True, index=True)
    nombre               = Column(String(150), unique=True, nullable=False)
    dias_respuesta_habil = Column(Integer, default=5)
    activo               = Column(Boolean, default=True)

    # Un tipo puede tener muchas solicitudes
    solicitudes = relationship("Solicitud", back_populates="tipo_solicitud")


# ── CLASE: Estado ─────────────────────────────────────────────
# Representa la tabla "estados"
class Estado(Base):
    __tablename__ = "estados"

    id       = Column(Integer, primary_key=True, index=True)
    codigo   = Column(String(30), unique=True, nullable=False)
    nombre   = Column(String(80), nullable=False)
    es_final = Column(Boolean, default=False)

    # Un estado puede estar en muchas solicitudes
    solicitudes = relationship("Solicitud", back_populates="estado")


# ── CLASE: Solicitud ──────────────────────────────────────────
# Representa la tabla "solicitudes" — el núcleo del sistema
class Solicitud(Base):
    __tablename__ = "solicitudes"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo_referencia = Column(String(20), unique=True)
    solicitante_id    = Column(String, ForeignKey("usuarios.id"), nullable=False)
    tipo_solicitud_id = Column(Integer, ForeignKey("tipos_solicitud.id"), nullable=False)
    estado_id         = Column(Integer, ForeignKey("estados.id"), nullable=False)
    descripcion       = Column(Text, nullable=False)
    respuesta_final   = Column(Text)
    canal_origen      = Column(String(20), default="WHATSAPP")
    creado_en         = Column(DateTime, server_default=func.now())
    actualizado_en    = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones con otras tablas
    solicitante    = relationship("Usuario", back_populates="solicitudes")
    tipo_solicitud = relationship("TipoSolicitud", back_populates="solicitudes")
    estado         = relationship("Estado", back_populates="solicitudes")
    historial      = relationship("HistorialEstado", back_populates="solicitud")


# ── CLASE: HistorialEstado ────────────────────────────────────
# Guarda cada cambio de estado de una solicitud — trazabilidad
class HistorialEstado(Base):
    __tablename__ = "historial_estados"

    id                 = Column(Integer, primary_key=True, index=True)
    solicitud_id       = Column(String, ForeignKey("solicitudes.id"), nullable=False)
    estado_anterior_id = Column(Integer, ForeignKey("estados.id"))
    estado_nuevo_id    = Column(Integer, ForeignKey("estados.id"), nullable=False)
    usuario_id         = Column(String, ForeignKey("usuarios.id"), nullable=False)
    comentario         = Column(Text)
    creado_en          = Column(DateTime, server_default=func.now())

    # Relaciones
    solicitud    = relationship("Solicitud", back_populates="historial")
    estado_nuevo = relationship("Estado", foreign_keys=[estado_nuevo_id])


# ── CLASE: SesionWhatsApp ─────────────────────────────────────
# Guarda el inicio y fin de cada conversación por WhatsApp
class SesionWhatsApp(Base):
    __tablename__ = "sesiones_whatsapp"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id    = Column(String, ForeignKey("usuarios.id"))
    telefono      = Column(String(20), nullable=False)
    estado_sesion = Column(String(30), default="INICIO")
    iniciada_en   = Column(DateTime, server_default=func.now())
    finalizada_en = Column(DateTime)
    activa        = Column(Boolean, default=True)

    # Una sesión tiene muchos mensajes
    mensajes = relationship("MensajeWhatsApp", back_populates="sesion")


# ── CLASE: MensajeWhatsApp ────────────────────────────────────
# Guarda cada mensaje enviado y recibido por WhatsApp
class MensajeWhatsApp(Base):
    __tablename__ = "mensajes_whatsapp"

    id        = Column(Integer, primary_key=True, index=True)
    sesion_id = Column(String, ForeignKey("sesiones_whatsapp.id"), nullable=False)
    direccion = Column(String(10), nullable=False)  # ENTRANTE o SALIENTE
    contenido = Column(Text, nullable=False)
    creado_en = Column(DateTime, server_default=func.now())

    # Un mensaje pertenece a una sesión
    sesion = relationship("SesionWhatsApp", back_populates="mensajes")


#     {
#   "nombres": "luz",
#   "apellidos": "Perez",
#   "email": "luz@test.com",
#   "telefono_whatsapp": "+573101234568",
#   "numero_documento": "1111111111",
#   "rol_id": 1,
#   "password": "1234567"
# }
