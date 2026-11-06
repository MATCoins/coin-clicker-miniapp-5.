import logging
import os
import sqlite3
from pathlib import Path
from contextlib import closing

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("9212011556:AAF3s8Mh8aqbwDBhvOjLitM7Koons9njv6o", "").strip()
PRODUCT_TITLE = os.getenv("PRODUCT_TITLE", "Onlayn Qumar: Strategiya və Risk")
PRODUCT_DESCRIPTION = os.getenv(
    "PRODUCT_DESCRIPTION",
    "Ehtimallar, risklərin idarə edilməsi və emosional nəzarət haqqında PDF kitab.",
)
PRODUCT_PRICE_STARS = int(os.getenv("PRODUCT_PRICE_STARS", "900"))
PRODUCT_PDF_PATH = Path(os.getenv("PRODUCT_PDF_PATH", "book.pdf"))
DB_PATH = os.getenv("DB_PATH", "payments.sqlite3")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

PAYLOAD = "pdf_book_v1"


def init_db() -> None:
    """Create a small SQLite database for payment idempotency and delivery status."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                telegram_payment_charge_id TEXT PRIMARY KEY,
                provider_payment_charge_id TEXT,
                user_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                currency TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                delivered_at DATETIME
            )
            """
        )
        conn.commit()


def payment_record(charge_id: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM payments WHERE telegram_payment_charge_id = ?",
            (charge_id,),
        ).fetchone()


def record_payment_once(payment, user_id: int) -> bool:
    """
    Return True if this charge ID was newly recorded, False if already recorded.
    SQLite PRIMARY KEY prevents duplicate fulfillment for the same Telegram charge.
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        try:
            conn.execute(
                """
                INSERT INTO payments (
                    telegram_payment_charge_id,
                    provider_payment_charge_id,
                    user_id, payload, currency, total_amount, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    payment.telegram_payment_charge_id,
                    payment.provider_payment_charge_id,
                    user_id,
                    payment.invoice_payload,
                    payment.currency,
                    payment.total_amount,
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def mark_delivered(charge_id: str) -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            UPDATE payments
            SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP
            WHERE telegram_payment_charge_id = ?
            """,
            (charge_id,),
        )
        conn.commit()


def mark_pending(charge_id: str) -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "UPDATE payments SET status = 'pending' WHERE telegram_payment_charge_id = ?",
            (charge_id,),
        )
        conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton(f"📘 Kitabı al — {PRODUCT_PRICE_STARS} ⭐", callback_data="buy_book")],
    ]
    if SUPPORT_USERNAME:
        keyboard.append(
            [InlineKeyboardButton("💬 Dəstək", url=f"https://t.me/{SUPPORT_USERNAME}")]
        )

    message = (
        f"Salam! 👋\n\n"
        f"📘 *{PRODUCT_TITLE}*\n\n"
        f"{PRODUCT_DESCRIPTION}\n\n"
        f"Qiymət: *{PRODUCT_PRICE_STARS} Telegram Stars* ⭐\n\n"
        "Almaq üçün aşağıdakı düyməyə basın. Ödəniş təsdiqləndikdən sonra PDF kitab "
        "bu söhbətə avtomatik göndəriləcək."
    )
    await update.effective_message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def buy_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not PRODUCT_PDF_PATH.is_file():
        logger.error("PDF file not found: %s", PRODUCT_PDF_PATH)
        await query.message.reply_text(
            "Hazırda kitab faylı tapılmadı. Zəhmət olmasa, bir az sonra yenidən yoxlayın."
        )
        return

    prices = [LabeledPrice(label=PRODUCT_TITLE, amount=PRODUCT_PRICE_STARS)]
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=PRODUCT_TITLE[:32],
            description=PRODUCT_DESCRIPTION[:255],
            payload=PAYLOAD,
            provider_token="",  # Telegram Stars üçün boş saxlanılır
            currency="XTR",
            prices=prices,
        )
    except Exception:
        logger.exception("Invoice creation failed")
        await query.message.reply_text(
            "Ödəniş pəncərəsini açmaq mümkün olmadı. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
        )


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    ok = (
        query.invoice_payload == PAYLOAD
        and query.currency == "XTR"
        and query.total_amount == PRODUCT_PRICE_STARS
    )

    if not ok:
        await query.answer(
            ok=False,
            error_message="Ödəniş məlumatları düzgün deyil. Zəhmət olmasa, yenidən cəhd edin.",
        )
        return

    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    payment = message.successful_payment
    user_id = update.effective_user.id

    # Validate the final payment again before delivering the digital product.
    if (
        payment.invoice_payload != PAYLOAD
        or payment.currency != "XTR"
        or payment.total_amount != PRODUCT_PRICE_STARS
    ):
        logger.error(
            "Unexpected payment data: user=%s payload=%s currency=%s amount=%s",
            user_id,
            payment.invoice_payload,
            payment.currency,
            payment.total_amount,
        )
        await message.reply_text(
            "Ödəniş məlumatlarını avtomatik təsdiqləmək mümkün olmadı. Dəstək ilə əlaqə saxlayın."
        )
        return

    charge_id = payment.telegram_payment_charge_id
    is_new = record_payment_once(payment, user_id)

    # If this charge was already delivered, do not send the file again.
    existing = payment_record(charge_id)
    if not is_new and existing and existing["status"] == "delivered":
        await message.reply_text("Bu ödəniş artıq təsdiqlənib və kitab göndərilib. 📘")
        return

    if not PRODUCT_PDF_PATH.is_file():
        logger.error("Payment succeeded but PDF file missing: %s", PRODUCT_PDF_PATH)
        await message.reply_text(
            "Ödənişiniz təsdiqləndi, lakin kitab faylı hazırda əlçatan deyil. "
            "Zəhmət olmasa, dəstək ilə əlaqə saxlayın."
        )
        return

    try:
        with PRODUCT_PDF_PATH.open("rb") as pdf:
            await message.reply_document(
                document=pdf,
                filename=PRODUCT_PDF_PATH.name,
                caption=f"Ödəniş təsdiqləndi! 📘\n{PRODUCT_TITLE}\nXoş mütaliələr!",
            )
        mark_delivered(charge_id)
        logger.info("Delivered PDF to user=%s charge=%s", user_id, charge_id)
    except Exception:
        # Leave the payment pending so a restart/manual retry can be handled.
        mark_pending(charge_id)
        logger.exception("PDF delivery failed for charge=%s", charge_id)
        await message.reply_text(
            "Ödənişiniz təsdiqləndi, amma PDF göndərilmədi. "
            "Dəstək ilə əlaqə saxlayın və ödənişinizi təsdiqləyən mesajı saxlayın."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Kitabı almaq üçün /start yazın.\n"
        "Ödəniş və ya fayl problemi yaranarsa, botun sahibinə müraciət edin."
    )


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN .env faylında qeyd edilməyib.")
    if PRODUCT_PRICE_STARS < 1:
        raise SystemExit("PRODUCT_PRICE_STARS ən azı 1 olmalıdır.")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(buy_book, pattern="^buy_book$"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    logger.info("Bot started. Price: %s Stars", PRODUCT_PRICE_STARS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
