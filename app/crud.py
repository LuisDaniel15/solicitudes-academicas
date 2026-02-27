from sqlalchemy.orm import Session
from app import models, schemas
import bcrypt
import uuid


# Función para encriptar contraseña
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


# Función para verificar contraseña
def verificar_password(password_plano: str, password_encriptado: str) -> bool:
    return bcrypt.checkpw(
        password_plano.encode("utf-8"),
        password_encriptado.encode("utf-8")
    )

# ══════════════════════════════════════════════════════════════
# FUNCIONES DE USUARIO
# ══════════════════════════════════════════════════════════════

def get_usuario_por_email(db: Session, email: str):
    """Busca un usuario por su email"""
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()


def get_usuario_por_telefono(db: Session, telefono: str):
    """Busca un usuario por su número de WhatsApp"""
    return db.query(models.Usuario).filter(
        models.Usuario.telefono_whatsapp == telefono
    ).first()


def get_usuario_por_id(db: Session, usuario_id: str):
    """Busca un usuario por su ID"""
    return db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()


def get_usuarios(db: Session):
    """Devuelve todos los usuarios"""
    return db.query(models.Usuario).all()


def crear_usuario(db: Session, usuario: schemas.UsuarioCreate):
    """Crea un usuario nuevo con la contraseña encriptada"""
    hashed_password = hash_password(usuario.password)
    # hashed_password = pwd_context.hash(usuario.password)

    db_usuario = models.Usuario(
        nombres           = usuario.nombres,
        apellidos         = usuario.apellidos,
        email             = usuario.email,
        telefono_whatsapp = usuario.telefono_whatsapp,
        numero_documento  = usuario.numero_documento,
        hashed_password   = hashed_password,
        rol_id            = usuario.rol_id
    )
    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)
    return db_usuario


# def verificar_password(password_plano: str, password_encriptado: str):
#     """Verifica si una contraseña es correcta"""
#     return pwd_context.verify(password_plano, password_encriptado)


# ══════════════════════════════════════════════════════════════
# FUNCIONES DE SOLICITUD
# ══════════════════════════════════════════════════════════════

def crear_solicitud(db: Session, solicitud: schemas.SolicitudCreate, usuario_id: str):
    """Crea una nueva solicitud académica"""

    # Generamos el código de referencia — ej: SOL-2024-00001
    total = db.query(models.Solicitud).count()
    codigo = f"SOL-{__import__('datetime').datetime.now().year}-{str(total + 1).zfill(5)}"

    # Buscamos el estado inicial — siempre es PENDIENTE
    estado_pendiente = db.query(models.Estado).filter(
        models.Estado.codigo == "PENDIENTE"
    ).first()

    db_solicitud = models.Solicitud(
        codigo_referencia = codigo,
        solicitante_id    = usuario_id,
        tipo_solicitud_id = solicitud.tipo_solicitud_id,
        estado_id         = estado_pendiente.id,
        descripcion       = solicitud.descripcion,
        canal_origen      = "WHATSAPP"
    )
    db.add(db_solicitud)
    db.commit()
    db.refresh(db_solicitud)
    return db_solicitud


def get_solicitud_por_id(db: Session, solicitud_id: str):
    """Busca una solicitud por su ID"""
    return db.query(models.Solicitud).filter(
        models.Solicitud.id == solicitud_id
    ).first()


def get_solicitud_por_codigo(db: Session, codigo: str):
    """Busca una solicitud por su código de referencia — ej: SOL-2024-00001"""
    return db.query(models.Solicitud).filter(
        models.Solicitud.codigo_referencia == codigo
    ).first()


def get_solicitudes_por_usuario(db: Session, usuario_id: str):
    """Devuelve todas las solicitudes de un usuario"""
    return db.query(models.Solicitud).filter(
        models.Solicitud.solicitante_id == usuario_id
    ).all()


def get_todas_solicitudes(db: Session):
    """Devuelve todas las solicitudes — solo para admin/secretaria"""
    return db.query(models.Solicitud).all()


def actualizar_estado_solicitud(
    db: Session,
    solicitud_id: str,
    nuevo_estado_id: int,
    usuario_id: str,
    comentario: str = None
):
    """Cambia el estado de una solicitud y guarda el historial"""

    # Buscamos la solicitud
    solicitud = get_solicitud_por_id(db, solicitud_id)
    if not solicitud:
        return None

    # Guardamos el historial antes de cambiar
    historial = models.HistorialEstado(
        solicitud_id       = solicitud_id,
        estado_anterior_id = solicitud.estado_id,
        estado_nuevo_id    = nuevo_estado_id,
        usuario_id         = usuario_id,
        comentario         = comentario
    )
    db.add(historial)

    # Actualizamos el estado
    solicitud.estado_id = nuevo_estado_id
    db.commit()
    db.refresh(solicitud)
    return solicitud


def get_historial_solicitud(db: Session, solicitud_id: str):
    """Devuelve el historial completo de estados de una solicitud"""
    return db.query(models.HistorialEstado).filter(
        models.HistorialEstado.solicitud_id == solicitud_id
    ).all()


# ══════════════════════════════════════════════════════════════
# FUNCIONES DE BÚSQUEDA — el profesor pide mínimo 3 filtros
# ══════════════════════════════════════════════════════════════

def buscar_solicitudes(
    db: Session,
    estado_id: int = None,
    tipo_solicitud_id: int = None,
    canal_origen: str = None
):
    """
    Busca solicitudes por filtros:
    - estado_id: filtra por estado (PENDIENTE, APROBADA, etc)
    - tipo_solicitud_id: filtra por tipo (Certificado, Grado, etc)
    - canal_origen: filtra por canal (WHATSAPP, PRESENCIAL, etc)
    """
    query = db.query(models.Solicitud)

    if estado_id:
        query = query.filter(models.Solicitud.estado_id == estado_id)

    if tipo_solicitud_id:
        query = query.filter(models.Solicitud.tipo_solicitud_id == tipo_solicitud_id)

    if canal_origen:
        query = query.filter(models.Solicitud.canal_origen == canal_origen)

    return query.all()


# ══════════════════════════════════════════════════════════════
# FUNCIONES DE WHATSAPP
# ══════════════════════════════════════════════════════════════

def crear_sesion_whatsapp(db: Session, telefono: str, usuario_id: str = None):
    """Abre una nueva sesión de conversación por WhatsApp"""
    sesion = models.SesionWhatsApp(
        telefono   = telefono,
        usuario_id = usuario_id,
        activa     = True
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion


def finalizar_sesion_whatsapp(db: Session, sesion_id: str):
    """Marca una sesión como finalizada"""
    from datetime import datetime
    sesion = db.query(models.SesionWhatsApp).filter(
        models.SesionWhatsApp.id == sesion_id
    ).first()
    if sesion:
        sesion.activa        = False
        sesion.finalizada_en = datetime.now()
        db.commit()
    return sesion


def guardar_mensaje_whatsapp(db: Session, sesion_id: str, direccion: str, contenido: str):
    """Guarda un mensaje de WhatsApp — direccion es ENTRANTE o SALIENTE"""
    mensaje = models.MensajeWhatsApp(
        sesion_id = sesion_id,
        direccion = direccion,
        contenido = contenido
    )
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)
    return mensaje

def get_sesion_activa(db: Session, telefono: str):
    """Busca si el usuario tiene una sesión activa"""
    return db.query(models.SesionWhatsApp).filter(
        models.SesionWhatsApp.telefono == telefono,
        models.SesionWhatsApp.activa == True
    ).first()


def actualizar_estado_sesion(db: Session, sesion_id: str, nuevo_estado: str):
    """Actualiza el estado de la sesión para recordar en qué paso está el usuario"""
    sesion = db.query(models.SesionWhatsApp).filter(
        models.SesionWhatsApp.id == sesion_id
    ).first()
    if sesion:
        sesion.estado_sesion = nuevo_estado
        db.commit()
    return sesion