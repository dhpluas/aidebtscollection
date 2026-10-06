"""Bot de Telegram (polling) para el agente de cobranza.

Cada chat_id de Telegram tiene su propia sesion aislada:
  sessions[chat_id] = {history, customer_id, authenticated, ...}

Uso:
  1. Pon TELEGRAM_BOT_TOKEN en .env (habla con @BotFather).
  2. Asegura que la API mock este corriendo: uvicorn app.main:app
  3. Ejecuta: python -m app.bot
"""

import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.agent import run_agent
from app.session import get_session, reset_session


load_dotenv()

_TOKEN_PATTERN = re.compile(r"bot\d+:[\w-]{20,}")


class _TokenRedactingFilter(logging.Filter):
    """Evita que el token del bot aparezca en consola por logs de httpx/telegram."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if _TOKEN_PATTERN.search(msg):
            record.msg = _TOKEN_PATTERN.sub("bot***REDACTED***", msg)
            record.args = ()
        return True


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,  # raiz en WARNING: httpx ya no loguea la URL con el token
)
for _noisy in ("httpx", "httpcore", "telegram", "telegram.ext", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
    logging.getLogger(_noisy).addFilter(_TokenRedactingFilter())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addFilter(_TokenRedactingFilter())


WELCOME = (
    "Hola, soy tu asistente de cobranza.\n\n"
    "Para empezar indícame tu número de documento.\n"
    "Luego te pediré tu nombre o teléfono para validar tu identidad.\n\n"
    "Comandos: /empezar (cambiar de persona), /salir (cerrar sesión)."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    reset_session(chat_id)
    await update.message.reply_text(WELCOME)


async def salir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    reset_session(chat_id)
    await update.message.reply_text(
        "Sesión cerrada. Tus datos de esta conversación fueron eliminados.\n"
        "Usa /empezar si deseas atender a otra persona."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or not update.message.text:
        return
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    if not text:
        return

    # Atajos de texto para reiniciar (ademas de /empezar).
    if text.lower() in ("/empezar", "empezar", "reiniciar", "nuevo", "cambiar persona"):
        reset_session(chat_id)
        await update.message.reply_text(
            "Sesión reiniciada. ¿Cuál es tu número de documento?"
        )
        return

    session = get_session(chat_id)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        # run_agent es sincrono (requests + OpenAI): no bloquear el loop.
        reply = await asyncio.to_thread(run_agent, text, session)
    except Exception as exc:  # noqa: BLE001 - queremos responder algo util
        logger.exception("Error en run_agent chat_id=%s", chat_id)
        await update.message.reply_text(
            "Ocurrió un error al procesar tu mensaje. Intenta de nuevo "
            "o escribe /empezar para reiniciar."
        )
        return

    await update.message.reply_text(reply or "No tengo respuesta por ahora.")


def _token_suffix(token: str) -> str:
    return f"***{token[-4:]}" if len(token) >= 4 else "***"


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN en .env. "
            "Crea tu bot con @BotFather y agrega el token."
        )
    if ":" not in token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN parece incompleto (falta el ':'). "
            "Usa el token completo 123456:AAE-xxx."
        )
    try:
        app = ApplicationBuilder().token(token).build()
    except Exception:
        # No loguear la excepcion cruda: podria contener el token.
        logger.error(
            "Token de Telegram invalido (termina en %s). Revisa .env.",
            _token_suffix(token),
        )
        raise SystemExit("Token de Telegram invalido. Revisa .env.") from None
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("empezar", start))
    app.add_handler(CommandHandler("salir", salir))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot polling iniciado. Ctrl+C para detener.")
    app.run_polling()


if __name__ == "__main__":
    main()
