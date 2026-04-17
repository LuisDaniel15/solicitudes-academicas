from fastapi import FastAPI
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, models
from dotenv import load_dotenv
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        return (
            "📄 *Homologación de materias*\n\n"
            "Necesitas:\n"
            "• Certificado de notas\n"
            "• Contenido programático\n"
            "• Plan de estudios"
        )
    if "cancel" in mensaje:
        return (
            "📄 *Cancelación de asignatura*\n\n"
            "• Carta explicando el motivo\n"
            "• Soporte (opcional)"
        )
    if "certificado" in mensaje:
        return "📄 *Certificados académicos*\n\nNo requieren documentos."
    if "grado" in mensaje:
        return "🎓 *Solicitud de grado*\n\nDebes estar a paz y salvo."
    if "beca" in mensaje:
        return "💰 *Becas*\n\nRequieren buen promedio."

    return None


# ─────────────────────────────
# 🎛️ MENÚ PRO
# ─────────────────────────────
def menu_principal(usuario):
    keyboard = [
        [InlineKeyboardButton("📄 Crear solicitud", callback_data="crear")],
        [InlineKeyboardButton("🔍 Consultar estado", callback_data="consultar")],
        [InlineKeyboardButton("📋 Ver solicitudes", callback_data="ver")],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda")],
    ]

    texto = (
        f"👋 Hola *{usuario.nombres}*, soy *Assisol* 🤖\n\n"
        "Te ayudo con tus *solicitudes académicas*.\n\n"

        "💡 También puedes preguntarme cosas como:\n"
        "• homologación\n"
        "• certificados\n"
        "• cancelación\n\n"

        "👇 Elige una opción:"
    )

    return texto, InlineKeyboardMarkup(keyboard)


def boton_volver():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="menu")]
    ])


# ─────────────────────────────
# 🤖 LÓGICA MENSAJES
# ─────────────────────────────
def procesar_mensaje(mensaje: str, telefono: str, db: Session, sesion):

    mensaje = mensaje.strip().lower()

    # RESET GLOBAL
    if mensaje in ["hola", "menu", "inicio"]:
        crud.actualizar_estado_sesion(db, sesion.id, "INICIO")
        sesion.estado_sesion = "INICIO"

    # RAG
    respuesta_rag = responder_rag(mensaje)
    if respuesta_rag:
        return respuesta_rag + "\n\n💬 Escribe *hola* para volver al menú"

    estado = sesion.estado_sesion

    # ── INICIO
    if estado == "INICIO":

        usuario = crud.get_usuario_por_telefono(db, telefono)

        if not usuario:
            crud.actualizar_estado_sesion(db, sesion.id, "PEDIR_DOCUMENTO")
            return (
                "👋 Hola, soy *Assisol* 🤖\n\n"
                "Te ayudaré con tus solicitudes.\n\n"
                "📄 Escribe tu número de documento para comenzar:"
            )

        crud.actualizar_estado_sesion(db, sesion.id, "MENU")
        return menu_principal(usuario)

    # ── LOGIN
    elif estado == "PEDIR_DOCUMENTO":

        usuario = db.query(models.Usuario).filter(
            models.Usuario.numero_documento == mensaje
        ).first()

        if not usuario:
            return "❌ Documento no encontrado. Intenta nuevamente."

        usuario.telefono_whatsapp = telefono
        db.commit()

        crud.actualizar_estado_sesion(db, sesion.id, "MENU")

        texto, teclado = menu_principal(usuario)

        return (
            f"✅ ¡Bienvenido {usuario.nombres}! 🎉\n\n" + texto,
            teclado
        )

    # VALIDACIÓN
    usuario = crud.get_usuario_por_telefono(db, telefono)
    if not usuario:
        crud.actualizar_estado_sesion(db, sesion.id, "PEDIR_DOCUMENTO")
        return "🔒 Debes identificarte primero"

    # CONSULTAR TEXTO
    if estado == "CONSULTAR":
        if mensaje.startswith("sol-"):
            solicitud = crud.get_solicitud_por_codigo(db, mensaje.upper())

            if not solicitud:
                return "❌ No encontré esa solicitud."

            crud.actualizar_estado_sesion(db, sesion.id, "MENU")

            return (
                f"📄 *{solicitud.codigo_referencia}*\n\n"
                f"Estado: *{solicitud.estado.nombre}*\n\n"
                "💬 Escribe *hola* para volver al menú"
            )

        return "❌ Escribe el código correctamente (SOL-XXXX)"

    # FALLBACK PRO
    return (
        "🤔 No entendí eso.\n\n"
        "Puedes:\n"
        "• Escribir *hola* para ver el menú\n"
        "• Usar los botones 👇\n"
        "• Preguntar algo como: 'homologación'"
    )


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
        await query.message.reply_text("🔒 Debes identificarte primero")
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
            [InlineKeyboardButton("📄 Notas", callback_data="tipo_3")],
            [InlineKeyboardButton("📄 Homologación", callback_data="tipo_6")],
            [InlineKeyboardButton("📄 Cancelación", callback_data="tipo_7")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu")]
        ]

        await query.message.reply_text(
            "📋 *Selecciona el tipo de solicitud:*",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # CREAR DIRECTO
    elif data.startswith("tipo_"):
        tipo_id = int(data.split("_")[1])

        from app.schemas import SolicitudCreate

        nueva = SolicitudCreate(
            tipo_solicitud_id=tipo_id,
            descripcion="Solicitud creada desde Telegram"
        )

        solicitud = crud.crear_solicitud(db, nueva, str(usuario.id))

        await query.message.reply_text(
            f"✅ *Solicitud creada con éxito*\n\n"
            f"📄 Código: {solicitud.codigo_referencia}\n"
            f"⏳ Estado: Pendiente\n\n"
            "🔔 Puedes consultarla cuando quieras."
        )

        texto, teclado = menu_principal(usuario)
        await query.message.reply_text(texto, reply_markup=teclado)

    # CONSULTAR
    elif data == "consultar":
        crud.actualizar_estado_sesion(db, sesion.id, "CONSULTAR")

        await query.message.reply_text(
            "🔍 Escribe el código de tu solicitud\nEjemplo: SOL-2026-00001",
            reply_markup=boton_volver()
        )

    # VER
    elif data == "ver":
        solicitudes = crud.get_solicitudes_por_usuario(db, usuario.id)

        if not solicitudes:
            await query.message.reply_text("📭 No tienes solicitudes")
        else:
            texto = "📋 *Tus solicitudes:*\n\n"
            for s in solicitudes:
                texto += f"• {s.codigo_referencia} — {s.estado.nombre}\n"

            await query.message.reply_text(texto)

        texto, teclado = menu_principal(usuario)
        await query.message.reply_text(texto, reply_markup=teclado)

    # AYUDA
    elif data == "ayuda":
        await query.message.reply_text(
            "ℹ️ *Ayuda*\n\n"
            "Puedes:\n"
            "• Crear solicitudes\n"
            "• Consultar estado\n"
            "• Ver historial\n\n"
            "💡 También puedes preguntar:\n"
            "• homologación\n"
            "• certificados\n"
            "• cancelación",
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
    print("🔥 Assisol BOT corriendo...")

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