import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta

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
ADMIN_ID = os.environ.get("ADMIN_ID")  # faqat shu ID ishlata oladi
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

TYPE_LABELS_SHORT = {
    TYPE_INTAKE: "Olingan",
    TYPE_RETURN: "Vazvrat",
    TYPE_FINISHED: "Tayyor",
}

# Faqat shu turlarda mahsulot soni (dona hisobi) so'raladi
ITEM_COUNT_TYPES = (TYPE_INTAKE, TYPE_FINISHED)

# Conversation holatlari
TYPING_AMOUNT, TYPING_ITEMS, TYPING_NOTE = range(3)

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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions (id)
        )
        """
    )
    conn.commit()
    conn.close()


def add_transaction(t_type: str, amount: float, note) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO transactions (type, amount, note, created_at) VALUES (?, ?, ?, ?)",
        (t_type, amount, note, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    tx_id = cur.lastrowid
    conn.close()
    return tx_id


def add_items(transaction_id: int, items: list):
    if not items:
        return
    conn = get_conn()
    conn.executemany(
        "INSERT INTO items (transaction_id, product_name, count) VALUES (?, ?, ?)",
        [(transaction_id, name, count) for count, name in items],
    )
    conn.commit()
    conn.close()


def get_totals(since=None):
    conn = get_conn()
    if since:
        rows = conn.execute(
            "SELECT type, COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE created_at>=? GROUP BY type",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT type, COALESCE(SUM(amount), 0) as total FROM transactions GROUP BY type"
        ).fetchall()
    conn.close()
    totals = {TYPE_INTAKE: 0.0, TYPE_RETURN: 0.0, TYPE_FINISHED: 0.0}
    for row in rows:
        totals[row["type"]] = row["total"]
    return totals


def get_item_totals(t_type: str, since=None):
    """Berilgan tur (intake/finished) bo'yicha mahsulot nomlari va jami soni."""
    conn = get_conn()
    if since:
        rows = conn.execute(
            """
            SELECT items.product_name as name, COALESCE(SUM(items.count), 0) as total
            FROM items
            JOIN transactions ON items.transaction_id = transactions.id
            WHERE transactions.type=? AND transactions.created_at>=?
            GROUP BY items.product_name
            """,
            (t_type, since),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT items.product_name as name, COALESCE(SUM(items.count), 0) as total
            FROM items
            JOIN transactions ON items.transaction_id = transactions.id
            WHERE transactions.type=?
            GROUP BY items.product_name
            """,
            (t_type,),
        ).fetchall()
    conn.close()
    return {row["name"]: row["total"] for row in rows}


def get_item_count_for_tx(transaction_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(count), 0) as total FROM items WHERE transaction_id=?",
        (transaction_id,),
    ).fetchone()
    conn.close()
    return row["total"] if row else 0


def get_history(limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def delete_last():
    conn = get_conn()
    row = conn.execute("SELECT id FROM transactions ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        conn.execute("DELETE FROM items WHERE transaction_id=?", (row["id"],))
        conn.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    return row is not None


# ------------------------------------------------------------------
# RUXSAT TEKSHIRUVI
# ------------------------------------------------------------------
def is_authorized(update: Update) -> bool:
    if not ADMIN_ID:
        return True
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
        [InlineKeyboardButton("🧮 Mahsulot hisoboti", callback_data="items_report")],
        [InlineKeyboardButton("📅 Haftalik hisobot", callback_data="weekly")],
        [InlineKeyboardButton("🗓 Oylik hisobot", callback_data="monthly")],
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
# JADVAL KO'RINISHIDAGI HISOBOTLAR
# ------------------------------------------------------------------
def format_report_table(title: str, since=None) -> str:
    totals = get_totals(since)
    intake = totals[TYPE_INTAKE]
    ret = totals[TYPE_RETURN]
    finished = totals[TYPE_FINISHED]
    balance = intake - ret - finished

    header = f"{'Turi':<12}{'Miqdor (g)':>12}"
    sep = "-" * len(header)
    lines = [header, sep]
    lines.append(f"{'Olingan':<12}{intake:>12.2f}")
    lines.append(f"{'Vazvrat':<12}{ret:>12.2f}")
    lines.append(f"{'Tayyor':<12}{finished:>12.2f}")
    lines.append(sep)
    lines.append(f"{'Qoldiq':<12}{balance:>12.2f}")
    table = "\n".join(lines)

    return f"📊 <b>{title}</b>\n<pre>{table}</pre>"


def format_balance() -> str:
    return format_report_table("Umumiy hisobot")


def format_items_report(since=None, title="Mahsulot hisoboti") -> str:
    intake_items = get_item_totals(TYPE_INTAKE, since)
    finished_items = get_item_totals(TYPE_FINISHED, since)

    names = sorted(set(intake_items.keys()) | set(finished_items.keys()))
    if not names:
        return f"🧮 <b>{title}</b>\n\nHozircha mahsulot bo'yicha ma'lumot yo'q."

    header = f"{'Nomi':<11}{'Olingan':>8}{'Tayyor':>8}{'Farq':>7}"
    sep = "-" * len(header)
    lines = [header, sep]
    total_intake = total_finished = 0
    for name in names:
        i_count = intake_items.get(name, 0)
        f_count = finished_items.get(name, 0)
        diff = i_count - f_count
        total_intake += i_count
        total_finished += f_count
        display_name = name if len(name) <= 10 else name[:10]
        lines.append(f"{display_name:<11}{i_count:>8}{f_count:>8}{diff:>7}")
    lines.append(sep)
    lines.append(f"{'Jami':<11}{total_intake:>8}{total_finished:>8}{total_intake - total_finished:>7}")
    table = "\n".join(lines)
    return f"🧮 <b>{title}</b>\n<pre>{table}</pre>\n<i>Farq = hali tugallanmagan (jarayonda qolgan) dona</i>"


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        format_balance(),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def show_items_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        format_items_report(),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def show_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
    text = format_report_table("Haftalik hisobot (so'nggi 7 kun)", since)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def show_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    since = datetime.now().strftime("%Y-%m-01 00:00")
    text = format_report_table("Oylik hisobot (joriy oy)", since)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = get_history(10)
    if not rows:
        text = "Hozircha yozuvlar yo'q."
    else:
        header = f"{'Sana':<11}{'Turi':<9}{'Miqdor':>7}{'Dona':>6}"
        sep = "-" * len(header)
        table_lines = [header, sep]
        for r in rows:
            date = r["created_at"][:10]
            label = TYPE_LABELS_SHORT.get(r["type"], r["type"])
            amount = f"{r['amount']:.2f}"
            item_count = get_item_count_for_tx(r["id"])
            dona = str(item_count) if item_count else "-"
            table_lines.append(f"{date:<11}{label:<9}{amount:>7}{dona:>6}")
        table_text = "\n".join(table_lines)
        text = f"📜 <b>Oxirgi {len(rows)} ta yozuv:</b>\n<pre>{table_text}</pre>"
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


# ------------------------------------------------------------------
# MAHSULOT SATRLARINI TAHLIL QILISH
# ------------------------------------------------------------------
def parse_items_text(text: str):
    """
    '50 uzuk' kabi qatorlarni ro'yxatga aylantiradi: [(50, 'uzuk'), ...]
    Noto'g'ri qatorlar e'tiborsiz qoldiriladi.
    """
    items = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\s+(.+)$", line)
        if match:
            count = int(match.group(1))
            name = match.group(2).strip().lower()
            if count > 0 and name:
                items.append((count, name))
    return items


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
    t_type = context.user_data["pending_type"]

    if t_type in ITEM_COUNT_TYPES:
        await update.message.reply_text(
            "Mahsulot turlari va sonini kiriting.\n"
            "Har birini yangi qatorda yozing, masalan:\n\n"
            "50 uzuk\n30 komplekt\n5 tros\n5 bilak\n\n"
            "Agar kerak bo'lmasa, /skip yuboring."
        )
        return TYPING_ITEMS
    else:
        await update.message.reply_text(
            "Izoh qo'shmoqchimisiz? (ixtiyoriy)\n"
            "Yozing yoki o'tkazib yuborish uchun /skip buyrug'ini yuboring."
        )
        return TYPING_NOTE


async def receive_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = parse_items_text(update.message.text)
    context.user_data["pending_items"] = items
    if items:
        summary = ", ".join(f"{c} {n}" for c, n in items)
        await update.message.reply_text(f"Qabul qilindi: {summary}")
    else:
        await update.message.reply_text(
            "Hech qanday mahsulot aniqlanmadi, davom etamiz."
        )
    await update.message.reply_text(
        "Izoh qo'shmoqchimisiz? (ixtiyoriy)\n"
        "Yozing yoki o'tkazib yuborish uchun /skip buyrug'ini yuboring."
    )
    return TYPING_NOTE


async def skip_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_items"] = []
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
    items = context.user_data.pop("pending_items", [])

    tx_id = add_transaction(t_type, amount, note)
    if items:
        add_items(tx_id, items)

    label = TYPE_LABELS[t_type]
    msg = f"✅ Saqlandi: {label} — {amount:.2f} g" + (f" ({note})" if note else "")
    if items:
        item_lines = "\n".join(f"  • {c} {n}" for c, n in items)
        msg += f"\n\nMahsulotlar:\n{item_lines}"
    await update.message.reply_text(msg)
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
            TYPING_ITEMS: [
                CommandHandler("skip", skip_items),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_items),
            ],
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
    app.add_handler(CallbackQueryHandler(show_items_report, pattern="^items_report$"))
    app.add_handler(CallbackQueryHandler(show_weekly, pattern="^weekly$"))
    app.add_handler(CallbackQueryHandler(show_monthly, pattern="^monthly$"))
    app.add_handler(CallbackQueryHandler(show_history, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^menu$"))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
