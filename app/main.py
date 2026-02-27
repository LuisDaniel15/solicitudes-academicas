from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas, models
from jose import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

app = FastAPI(title="Sistema de Solicitudes Académicas")


# ── Función para crear token JWT ──────────────────────────────
def crear_token(data: dict):
    datos = data.copy()
    expiracion = datetime.utcnow() + timedelta(hours=8)
    datos.update({"exp": expiracion})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)


# ── Función para obtener usuario del token ────────────────────
def get_usuario_actual(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = payload.get("sub")
        return crud.get_usuario_por_id(db, usuario_id)
    except:
        raise HTTPException(status_code=401, detail="Token inválido")


# ══════════════════════════════════════════════════════════════
# ENDPOINTS DE INICIO
# ══════════════════════════════════════════════════════════════

@app.get("/")
def inicio():
    return {"mensaje": "API de Solicitudes Académicas funcionando ✅"}


# ══════════════════════════════════════════════════════════════
# ENDPOINTS DE AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════

@app.post("/registro", response_model=schemas.UsuarioOut)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existe = crud.get_usuario_por_email(db, usuario.email)
    if existe:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    return crud.crear_usuario(db, usuario)


@app.post("/login", response_model=schemas.TokenOut)
def login(datos: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = crud.get_usuario_por_email(db, datos.email)
    if not usuario:
        raise HTTPException(status_code=400, detail="Email o contraseña incorrectos")
    if not crud.verificar_password(datos.password, usuario.hashed_password):
        raise HTTPException(status_code=400, detail="Email o contraseña incorrectos")
    token = crear_token({"sub": str(usuario.id)})
    return {"access_token": token, "token_type": "bearer"}


# ══════════════════════════════════════════════════════════════
# ENDPOINTS DE SOLICITUDES
# ══════════════════════════════════════════════════════════════

@app.post("/solicitudes", response_model=schemas.SolicitudOut)
def crear_solicitud(solicitud: schemas.SolicitudCreate, token: str, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(token, db)
    return crud.crear_solicitud(db, solicitud, usuario.id)


@app.get("/solicitudes", response_model=list[schemas.SolicitudOut])
def ver_todas_solicitudes(token: str, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(token, db)
    return crud.get_todas_solicitudes(db)


@app.get("/solicitudes/mis-solicitudes", response_model=list[schemas.SolicitudOut])
def mis_solicitudes(token: str, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(token, db)
    return crud.get_solicitudes_por_usuario(db, usuario.id)


@app.get("/solicitudes/buscar", response_model=list[schemas.SolicitudOut])
def buscar_solicitudes(
    token: str,
    estado_id: int = None,
    tipo_solicitud_id: int = None,
    canal_origen: str = None,
    db: Session = Depends(get_db)
):
    usuario = get_usuario_actual(token, db)
    return crud.buscar_solicitudes(db, estado_id, tipo_solicitud_id, canal_origen)


@app.get("/solicitudes/{solicitud_id}", response_model=schemas.SolicitudOut)
def ver_solicitud(solicitud_id: str, token: str, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(token, db)
    solicitud = crud.get_solicitud_por_id(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return solicitud


@app.patch("/solicitudes/{solicitud_id}/estado", response_model=schemas.SolicitudOut)
def actualizar_estado(
    solicitud_id: str,
    datos: schemas.SolicitudUpdateEstado,
    token: str,
    db: Session = Depends(get_db)
):
    usuario = get_usuario_actual(token, db)
    solicitud = crud.actualizar_estado_solicitud(
        db, solicitud_id, datos.estado_id, usuario.id, datos.comentario
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return solicitud


@app.get("/solicitudes/{solicitud_id}/historial", response_model=list[schemas.HistorialOut])
def ver_historial(solicitud_id: str, token: str, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(token, db)
    return crud.get_historial_solicitud(db, solicitud_id)


# ══════════════════════════════════════════════════════════════
# ENDPOINTS DE CATÁLOGOS
# ══════════════════════════════════════════════════════════════

@app.get("/tipos-solicitud", response_model=list[schemas.TipoSolicitudOut])
def ver_tipos_solicitud(db: Session = Depends(get_db)):
    return db.query(models.TipoSolicitud).all()


@app.get("/estados", response_model=list[schemas.EstadoOut])
def ver_estados(db: Session = Depends(get_db)):
    return db.query(models.Estado).all()

# ══════════════════════════════════════════════════════════════
# FUNCIÓN DEL ASISTENTE VIRTUAL CON MEMORIA DE SESIÓN
# ══════════════════════════════════════════════════════════════

def procesar_mensaje(mensaje: str, telefono: str, db: Session, sesion) -> str:
    """
    Recibe el mensaje y el estado actual de la sesión
    para saber en qué paso está el usuario.
    """

    # Validar mensaje vacío
    if not mensaje or not mensaje.strip():
        return "⚠️ No recibí ningún mensaje. Por favor escribe tu consulta."

    mensaje = mensaje.strip().lower()
    estado_actual = sesion.estado_sesion  # recordamos en qué paso está

    # ── PASO: INICIO — el usuario saluda ─────────────────────
    if estado_actual == "INICIO" or any(p in mensaje for p in ["hola", "buenos dias", "buenas tardes", "menu", "inicio"]):
        crud.actualizar_estado_sesion(db, str(sesion.id), "MENU_PRINCIPAL")
        return (
            "👋 ¡Hola! Bienvenido al sistema de solicitudes académicas.\n\n"
            "¿Qué deseas hacer?\n"
            "1️⃣  Crear una solicitud\n"
            "2️⃣  Consultar estado de mi solicitud\n"
            "3️⃣  Ver mis solicitudes\n"
            "4️⃣  Ayuda\n\n"
            "Responde con el número de la opción."
        )

    # ── PASO: MENU PRINCIPAL ──────────────────────────────────
    elif estado_actual == "MENU_PRINCIPAL":

        if mensaje == "1":
            crud.actualizar_estado_sesion(db, str(sesion.id), "SELECCIONAR_TIPO")
            return (
                "📋 ¿Qué tipo de solicitud necesitas?\n\n"
                "1️⃣  Certificado de Matrícula\n"
                "2️⃣  Constancia de Estudio\n"
                "3️⃣  Certificado de Notas\n"
                "4️⃣  Paz y Salvo Académico\n"
                "5️⃣  Cambio de Grupo\n"
                "6️⃣  Homologación de Materias\n"
                "7️⃣  Cancelación de Asignatura\n"
                "8️⃣  Solicitud de Grado\n"
                "9️⃣  Solicitud de Beca\n\n"
                "Responde con el número."
            )

        elif mensaje == "2":
            crud.actualizar_estado_sesion(db, str(sesion.id), "CONSULTAR_ESTADO")
            return (
                "🔍 Escribe el código de tu solicitud.\n"
                "Ejemplo: *SOL-2026-00001*"
            )

        elif mensaje == "3":
            usuario = crud.get_usuario_por_telefono(db, telefono)
            if not usuario:
                return "⚠️ Tu número no está registrado. Regístrate primero en la plataforma."
            solicitudes = crud.get_solicitudes_por_usuario(db, usuario.id)
            if not solicitudes:
                return "📭 No tienes solicitudes registradas aún."
            respuesta = "📋 *Tus solicitudes:*\n\n"
            for s in solicitudes:
                respuesta += f"• {s.codigo_referencia} — {s.tipo_solicitud.nombre} — *{s.estado.nombre}*\n"
            crud.actualizar_estado_sesion(db, str(sesion.id), "MENU_PRINCIPAL")
            return respuesta

        elif mensaje == "4":
            return (
                "ℹ️ *Ayuda:*\n\n"
                "• Escribe *hola* para ver el menú\n"
                "• Escribe *1* para crear una solicitud\n"
                "• Escribe *2* para consultar estado\n"
                "• Escribe *3* para ver tus solicitudes\n"
                "• Escribe *adios* para finalizar"
            )

        else:
            return "Por favor responde con un número del 1 al 4. Escribe *hola* para ver el menú."

    # ── PASO: SELECCIONAR TIPO DE SOLICITUD ───────────────────
    elif estado_actual == "SELECCIONAR_TIPO":
        tipos = {
            "1": "Certificado de Matrícula",
            "2": "Constancia de Estudio",
            "3": "Certificado de Notas",
            "4": "Paz y Salvo Académico",
            "5": "Cambio de Grupo / Horario",
            "6": "Homologación de Materias",
            "7": "Cancelación de Asignatura",
            "8": "Solicitud de Grado",
            "9": "Solicitud de Beca",
        }
        if mensaje in tipos:
            tipo_nombre = tipos[mensaje]
            crud.actualizar_estado_sesion(db, str(sesion.id), f"ESPERANDO_DESCRIPCION_{mensaje}")
            return (
                f"✅ Entendido: *{tipo_nombre}*\n\n"
                "Por favor descríbeme brevemente el motivo de tu solicitud."
            )
        else:
            return "Por favor responde con un número del 1 al 9."

    # ── PASO: ESPERANDO DESCRIPCIÓN ───────────────────────────
    elif estado_actual.startswith("ESPERANDO_DESCRIPCION_"):
        tipo_id = int(estado_actual.split("_")[-1])
        usuario = crud.get_usuario_por_telefono(db, telefono)

        if not usuario:
            crud.actualizar_estado_sesion(db, str(sesion.id), "MENU_PRINCIPAL")
            return "⚠️ Tu número no está registrado. Regístrate primero en la plataforma."

        # Crear la solicitud en la BD
        from app.schemas import SolicitudCreate
        nueva = SolicitudCreate(tipo_solicitud_id=tipo_id, descripcion=mensaje)
        solicitud = crud.crear_solicitud(db, nueva, str(usuario.id))

        crud.actualizar_estado_sesion(db, str(sesion.id), "MENU_PRINCIPAL")
        return (
            f"✅ *Solicitud creada exitosamente*\n\n"
            f"📄 Código: *{solicitud.codigo_referencia}*\n"
            f"Estado: Pendiente\n"
            f"Guarda este código para hacer seguimiento.\n\n"
            f"Escribe *hola* para volver al menú."
        )

    # ── PASO: CONSULTAR ESTADO ────────────────────────────────
    elif estado_actual == "CONSULTAR_ESTADO":
        if mensaje.startswith("sol-"):
            codigo = mensaje.upper()
            solicitud = crud.get_solicitud_por_codigo(db, codigo)
            crud.actualizar_estado_sesion(db, str(sesion.id), "MENU_PRINCIPAL")
            if not solicitud:
                return f"❌ No encontré la solicitud *{codigo}*. Verifica el código."
            return (
                f"📄 *{solicitud.codigo_referencia}*\n\n"
                f"Tipo: {solicitud.tipo_solicitud.nombre}\n"
                f"Estado: *{solicitud.estado.nombre}*\n"
                f"Fecha: {solicitud.creado_en.strftime('%d/%m/%Y')}\n\n"
                f"Escribe *hola* para volver al menú."
            )
        else:
            return "Por favor escribe el código en formato *SOL-2026-00001*"

    # ── DESPEDIDA ─────────────────────────────────────────────
    elif any(p in mensaje for p in ["adios", "bye", "chao", "hasta luego"]):
        crud.finalizar_sesion_whatsapp(db, str(sesion.id))
        return "👋 ¡Hasta luego! Que tengas un excelente día. 😊"

    else:
        return (
            "🤔 No entendí tu mensaje.\n"
            "Escribe *hola* para ver el menú principal."
        )


# ══════════════════════════════════════════════════════════════
# ENDPOINT WEBHOOK
# ══════════════════════════════════════════════════════════════

@app.post("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    mensaje_entrante = form.get("Body", "").strip()
    telefono         = form.get("From", "").replace("whatsapp:", "")

    # Buscar sesión activa o crear una nueva
    sesion = crud.get_sesion_activa(db, telefono)
    if not sesion:
        sesion = crud.crear_sesion_whatsapp(db, telefono)

    # Guardar mensaje entrante
    crud.guardar_mensaje_whatsapp(db, str(sesion.id), "ENTRANTE", mensaje_entrante)

    # Procesar y responder
    respuesta_texto = procesar_mensaje(mensaje_entrante, telefono, db, sesion)

    # Guardar respuesta
    crud.guardar_mensaje_whatsapp(db, str(sesion.id), "SALIENTE", respuesta_texto)

    resp = MessagingResponse()
    resp.message(respuesta_texto)
    return PlainTextResponse(str(resp), media_type="application/xml")