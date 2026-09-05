import os
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ------------------------------------------------------------------
# SOZLAMALAR
# ------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # ixtiyoriy: faqat shu ID ishlata oladi
DB_PATH = os.environ.get("DB_PATH", "zargarlik.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Turlar
TYPE_INTAKE = "intake"     # Jarayonga olingan (berilgan tilla)
TYPE_RETURN = "return"     # Vazvrat (qaytgan)
TYPE_FINISHED = "finished"  # Tayyor mahsulot

TYPE_LABELS = {
    TYPE_INTAKE: "➕ Jarayonga olingan",
    TYPE_RETURN: "↩️ Vazvrat",
    TYPE_FINISHED: "✅ Tayyor mahsulot",
}

# Conversation holatlari
TYPING_AMOUNT, TYPING_NOTE = range(2)

# ------------------------------------------------------------------
# MA'LUMOTLAR BAZASI
# ------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_transaction(t_type: str, amount: float, note: str | None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions (type, amount, note, created_at) VALUES (?, ?, ?, ?)",
        (t_type, amount, note, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def get_totals():
    conn = get_conn()
    rows = conn.execute(
        "SELECT type, COALESCE(SUM(amount), 0) as total FROM transactions GROUP BY type"
    ).fetchall()
    conn.close()
    totals = {TYPE_INTAKE: 0.0, TYPE_RETURN: 0.0, TYPE_FINISHED: 0.0}
    for row in rows:
        totals[row["type"]] = row["total"]
    return totals


def get_history(limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def delete_last(t_type: str | None = None):
    conn = get_conn()
    if t_type:
        row = conn.execute(
            "SELECT id FROM transactions WHERE type=? ORDER BY id DESC LIMIT 1", (t_type,)
        ).fetchone()
    else:
        row = conn.execute("SELECT id FROM transactions ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        conn.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    return row is not None


# ------------------------------------------------------------------
# RUXSAT TEKSHIRUVI
# ------------------------------------------------------------------
def is_authorized(update: Update) -> bool:
    if not ADMIN_ID:
        return True  # agar ADMIN_ID sozlanmagan bo'lsa, hammaga ochiq (tavsiya etilmaydi)
    return str(update.effective_user.id) == str(ADMIN_ID)


# ------------------------------------------------------------------
# MENYU
# ------------------------------------------------------------------
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(TYPE_LABELS[TYPE_INTAKE], callback_data=TYPE_INTAKE)],
        [InlineKeyboardButton(TYPE_LABELS[TYPE_RETURN], callback_data=TYPE_RETURN)],
        [InlineKeyboardButton(TYPE_LABELS[TYPE_FINISHED], callback_data=TYPE_FINISHED)],
        [InlineKeyboardButton("📊 Qoldiqni ko'rish", callback_data="balance")],
        [InlineKeyboardButton("📜 Oxirgi yozuvlar", callback_data="history")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("Kechirasiz, sizda bu botdan foydalanish huquqi yo'q.")
        return
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Zargarlik hisob-kitob boti. Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu_keyboard(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Bo'limni tanlang:", reply_markup=main_menu_keyboard()
    )


# ------------------------------------------------------------------
# QOLDIQ VA TARIX
# ------------------------------------------------------------------
def format_balance() -> str:
    totals = get_totals()
    intake = totals[TYPE_INTAKE]
    ret = totals[TYPE_RETURN]
    finished = totals[TYPE_FINISHED]
    balance = intake - ret - finished

    text = (
        "📊 <b>Hisobot</b>\n\n"
        f"➕ Jarayonga olingan (jami): <b>{intake:.2f} g</b>\n"
        f"↩️ Vazvrat (jami): <b>{ret:.2f} g</b>\n"
        f"✅ Tayyor mahsulot (jami): <b>{finished:.2f} g</b>\n"
        "————————————————\n"
        f"💰 <b>Qoldiq: {balance:.2f} g</b>\n"
    )
    return text


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        format_balance(),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = get_history(10)
    if not rows:
        text = "Hozircha yozuvlar yo'q."
    else:
        lines = ["📜 <b>Oxirgi 10 ta yozuv:</b>\n"]
        for r in rows:
            label = TYPE_LABELS.get(r["type"], r["type"])
            note = f" ({r['note']})" if r["note"] else ""
            lines.append(f"{r['created_at']} — {label}: {r['amount']:.2f} g{note}")
        text = "\n".join(lines)
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


# ------------------------------------------------------------------
# YOZUV QO'SHISH (CONVERSATION)
# ------------------------------------------------------------------
async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    t_type = query.data
    context.user_data["pending_type"] = t_type
    label = TYPE_LABELS[t_type]
    await query.edit_message_text(
        f"{label}\n\nMiqdorni gramm hisobida kiriting (masalan: 12.5):"
    )
    return TYPING_AMOUNT


async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Iltimos, to'g'ri musbat son kiriting (masalan: 12.5):"
        )
        return TYPING_AMOUNT

    context.user_data["pending_amount"] = amount
    await update.message.reply_text(
        "Izoh qo'shmoqchimisiz? (ixtiyoriy)\n"
        "Yozing yoki o'tkazib yuborish uchun /skip buyrug'ini yuboring."
    )
    return TYPING_NOTE


async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    await _save_entry(update, context, note)
    return ConversationHandler.END


async def skip_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _save_entry(update, context, None)
    return ConversationHandler.END


async def _save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, note):
    t_type = context.user_data.pop("pending_type")
    amount = context.user_data.pop("pending_amount")
    add_transaction(t_type, amount, note)
    label = TYPE_LABELS[t_type]
    await update.message.reply_text(
        f"✅ Saqlandi: {label} — {amount:.2f} g" + (f" ({note})" if note else ""),
    )
    await update.message.reply_text(
        format_balance(), parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bekor qilindi.", reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text("Menyu:", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ------------------------------------------------------------------
# QOSHIMCHA BUYRUQLAR
# ------------------------------------------------------------------
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        format_balance(), parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    ok = delete_last()
    if ok:
        await update.message.reply_text(
            "So'nggi yozuv o'chirildi.\n\n" + format_balance(),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text("O'chiriladigan yozuv topilmadi.")


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment o'zgaruvchisi topilmadi!")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                ask_amount, pattern=f"^({TYPE_INTAKE}|{TYPE_RETURN}|{TYPE_FINISHED})$"
            )
        ],
        states={
            TYPING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            TYPING_NOTE: [
                CommandHandler("skip", skip_note),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_note),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("undo", undo_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(show_history, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^menu$"))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
