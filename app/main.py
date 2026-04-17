from fastapi import FastAPI
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, models
from dotenv import load_dotenv
import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

app = FastAPI(title="Sistema de Solicitudes Académicas")


# ─────────────────────────────
# 🧠 RAG SIMPLE
# ─────────────────────────────
def responder_rag(mensaje: str):
    mensaje = mensaje.lower()

    if "homolog" in mensaje:
        return "📄 Homologación:\n• Certificado de notas\n• Contenido programático"
    if "cancel" in mensaje:
        return "📄 Cancelación:\n• Carta con motivo"
    if "certificado" in mensaje:
        return "📄 Certificados:\nNo requieren documentos"
    if "grado" in mensaje:
        return "🎓 Grado:\nDebes estar a paz y salvo"

    return None


# ─────────────────────────────
# 🎛️ MENÚ
# ─────────────────────────────
def menu_principal(usuario):
    keyboard = [
        [InlineKeyboardButton("📄 Crear solicitud", callback_data="crear")],
        [InlineKeyboardButton("🔍 Consultar estado", callback_data="consultar")],
        [InlineKeyboardButton("📋 Ver solicitudes", callback_data="ver")],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda")],
    ]

    return (
        f"👋 Hola {usuario.nombres}\n\n"
        "¿Qué deseas hacer?",
        InlineKeyboardMarkup(keyboard)
    )


def boton_volver():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Volver", callback_data="menu")]
    ])


# ─────────────────────────────
# 🤖 LÓGICA
# ─────────────────────────────
def procesar_mensaje(mensaje: str, telefono: str, db: Session, sesion):

    mensaje = mensaje.strip().lower()

    if mensaje in ["hola", "menu"]:
        crud.actualizar_estado_sesion(db, sesion.id, "INICIO")
        sesion.estado_sesion = "INICIO"

    respuesta_rag = responder_rag(mensaje)
    if respuesta_rag:
        return respuesta_rag + "\n\nEscribe 'hola' para volver"

    estado = sesion.estado_sesion

    # INICIO
    if estado == "INICIO":
        usuario = crud.get_usuario_por_telefono(db, telefono)

        if not usuario:
            crud.actualizar_estado_sesion(db, sesion.id, "PEDIR_DOCUMENTO")
            return "👋 Hola\n\nEscribe tu número de documento:"

        crud.actualizar_estado_sesion(db, sesion.id, "MENU")
        return menu_principal(usuario)

    # LOGIN
    elif estado == "PEDIR_DOCUMENTO":
        usuario = db.query(models.Usuario).filter(
            models.Usuario.numero_documento == mensaje
        ).first()

        if not usuario:
            return "❌ Documento no encontrado"

        usuario.telefono_whatsapp = telefono
        db.commit()

        crud.actualizar_estado_sesion(db, sesion.id, "MENU")

        return (
            f"✅ Bienvenido {usuario.nombres}",
            menu_principal(usuario)[1]
        )

    usuario = crud.get_usuario_por_telefono(db, telefono)

    if not usuario:
        crud.actualizar_estado_sesion(db, sesion.id, "PEDIR_DOCUMENTO")
        return "🔒 Debes identificarte"

    # CONSULTAR
    if estado == "CONSULTAR":
        if mensaje.startswith("sol-"):
            solicitud = crud.get_solicitud_por_codigo(db, mensaje.upper())

            if not solicitud:
                return "❌ No encontrada"

            crud.actualizar_estado_sesion(db, sesion.id, "MENU")

            return f"📄 {solicitud.codigo_referencia}\nEstado: {solicitud.estado.nombre}"

        return "Escribe el código correcto"

    return "🤔 No entendí. Escribe 'hola'"


# ─────────────────────────────
# 🔘 BOTONES
# ─────────────────────────────
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db = next(get_db())
    user_id = str(query.from_user.id)

    sesion = crud.get_sesion_activa(db, user_id)
    if not sesion:
        sesion = crud.crear_sesion_whatsapp(db, user_id)

    usuario = crud.get_usuario_por_telefono(db, user_id)

    if not usuario:
        await query.message.reply_text("🔒 Identifícate primero")
        return

    data = query.data

    # MENU
    if data == "menu":
        texto, teclado = menu_principal(usuario)
        await query.message.reply_text(texto, reply_markup=teclado)

    # CREAR
    elif data == "crear":
        keyboard = [
            [InlineKeyboardButton("📄 Matrícula", callback_data="tipo_1")],
            [InlineKeyboardButton("📄 Constancia", callback_data="tipo_2")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu")]
        ]

        await query.message.reply_text(
            "Selecciona tipo:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # CREAR DIRECTO
    elif data.startswith("tipo_"):
        tipo_id = int(data.split("_")[1])

        from app.schemas import SolicitudCreate

        nueva = SolicitudCreate(
            tipo_solicitud_id=tipo_id,
            descripcion="Telegram"
        )

        solicitud = crud.crear_solicitud(db, nueva, str(usuario.id))

        await query.message.reply_text(
            f"✅ Creada\nCódigo: {solicitud.codigo_referencia}"
        )

    # CONSULTAR
    elif data == "consultar":
        crud.actualizar_estado_sesion(db, sesion.id, "CONSULTAR")

        await query.message.reply_text(
            "Escribe código SOL-XXXX",
            reply_markup=boton_volver()
        )

    # VER
    elif data == "ver":
        solicitudes = crud.get_solicitudes_por_usuario(db, usuario.id)

        if not solicitudes:
            await query.message.reply_text("No tienes solicitudes")
        else:
            texto = ""
            for s in solicitudes:
                texto += f"{s.codigo_referencia} - {s.estado.nombre}\n"

            await query.message.reply_text(texto)

    # AYUDA
    elif data == "ayuda":
        await query.message.reply_text(
            "Puedes:\n1 Crear\n2 Consultar\n3 Ver",
            reply_markup=boton_volver()
        )


# ─────────────────────────────
# 💬 MENSAJES
# ─────────────────────────────
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = next(get_db())

    mensaje = update.message.text
    user_id = str(update.message.from_user.id)

    sesion = crud.get_sesion_activa(db, user_id)
    if not sesion:
        sesion = crud.crear_sesion_whatsapp(db, user_id)

    respuesta = procesar_mensaje(mensaje, user_id, db, sesion)

    if isinstance(respuesta, tuple):
        texto, teclado = respuesta
        await update.message.reply_text(texto, reply_markup=teclado)
    else:
        await update.message.reply_text(respuesta)


# ─────────────────────────────
# 🚀 BOT
# ─────────────────────────────
def iniciar_bot():
    print("🔥 Bot corriendo...")

    app_telegram = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_telegram.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje)
    )

    app_telegram.add_handler(
        CallbackQueryHandler(manejar_botones)
    )

    app_telegram.run_polling()


if __name__ == "__main__":
    iniciar_bot()