import logging
import os
from typing import List
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from quiz_parser import parse_csv_quiz

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

CHANNELS = {
    "🚂 Daily Railway Quiz": "-1003996251605",
    "📘 Test Sarthi":          "@testsarthi1234",
    "📗 Channel 3":          "@channel3username",
}

# ── Send polls + channel picker ───────────────────────────────────────────────
async def send_quiz_to_user_and_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    questions: List[dict]
):
    total = len(questions)
    for i, q in enumerate(questions, start=1):
        numbered = f"Q{i}/{total}. {q['question']}"
        await update.message.reply_poll(
            question          = numbered[:300],
            options           = [opt[:100] for opt in q["options"]],
            type              = "quiz",
            correct_option_id = q["correct_option_id"],
            explanation       = q["explanation"][:200],
            is_anonymous      = True,
        )

    context.user_data['last_quiz'] = questions

    keyboard = [
        [InlineKeyboardButton(f"📢 {name}", callback_data=f"post|{chat_id}|{name}")]
        for name, chat_id in CHANNELS.items()
    ]
    keyboard.append([InlineKeyboardButton("🚀 Post to ALL channels", callback_data="post|ALL|All")])

    await update.message.reply_text(
        f"🎉 *{len(questions)} question(s)* ready!\n\n"
        "📢 *Where do you want to post?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

# ── Commands ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_list = "\n".join(f"  • {name}" for name in CHANNELS)
    await update.message.reply_text(
        "👋 *Welcome to the Multi-Channel Quiz Bot!*\n\n"
        "📋 *Two ways to send questions:*\n\n"
        "1️⃣ *Paste directly* using `|` pipe separator:\n"
        "`Question | OptA | OptB | OptC | OptD | 2`\n\n"
        "2️⃣ *Upload a file* (.txt / .csv) using tab or comma:\n"
        "`Question\\tOptA\\tOptB\\tOptC\\tOptD\\t2`\n\n"
        "*Answer column accepts:*\n"
        "• Numbers → `1`, `2`, `3`, `4`\n"
        "• Letters → `A`, `B`, `C`, `D`\n\n"
        f"📢 *Configured channels:*\n{channel_list}",
        parse_mode="Markdown",
    )

# ── Handlers ──────────────────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = parse_csv_quiz(update.message.text)
    if questions:
        await send_quiz_to_user_and_prompt(update, context, questions)
    else:
        await update.message.reply_text(
            "⚠️ Could not parse your message.\n\n"
            "*For direct paste, use `|` pipe separator:*\n"
            "`Question | OptA | OptB | OptC | OptD | 2`\n\n"
            "Each line = one question. Answer is the last column (1/2/3/4 or A/B/C/D).",
            parse_mode="Markdown",
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc       = update.message.document
    file_name = doc.file_name.lower()

    if not any(file_name.endswith(ext) for ext in ('.csv', '.tsv', '.txt')):
        await update.message.reply_text("⚠️ Please upload a `.csv`, `.tsv`, or `.txt` file.")
        return

    status = await update.message.reply_text("📥 Reading file…")
    try:
        tg_file    = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        text       = file_bytes.decode('utf-8', errors='ignore')

        questions = parse_csv_quiz(text)
        await status.delete()

        if questions:
            await send_quiz_to_user_and_prompt(update, context, questions)
        else:
            await update.message.reply_text(
                "❌ Could not parse the file.\n"
                "Each row needs: Question, options, and answer code as the last column."
            )
    except Exception as e:
        logger.error(f"File processing error: {e}", exc_info=True)
        await status.edit_text("❌ An error occurred while processing the file.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("post|"):
        return

    _, target_id, channel_name = query.data.split("|", 2)

    questions = context.user_data.get('last_quiz')
    if not questions:
        await query.edit_message_text("❌ No recent quiz found. Send your questions again.")
        return

    targets = list(CHANNELS.items()) if target_id == "ALL" else [(channel_name, target_id)]
    await query.edit_message_text(f"⏳ Posting to {channel_name}…")

    success, failed = [], []
    for name, chat_id in targets:
        try:
            total = len(questions)
            for i, q in enumerate(questions, start=1):
                numbered = f"Q{i}/{total}. {q['question']}"
                await context.bot.send_poll(
                    chat_id           = chat_id,
                    question          = numbered[:300],
                    options           = [opt[:100] for opt in q["options"]],
                    type              = "quiz",
                    correct_option_id = q["correct_option_id"],
                    explanation       = q["explanation"][:200],
                    is_anonymous      = True,
                )
            success.append(name)
        except Exception as e:
            logger.error(f"Failed to post to {name} ({chat_id}): {e}", exc_info=True)
            failed.append(f"{name} — `{e}`")

    result = ""
    if success:
        result += "✅ *Posted to:*\n" + "\n".join(f"  • {n}" for n in success)
    if failed:
        result += "\n\n❌ *Failed:*\n" + "\n".join(f"  • {n}" for n in failed)

    await query.edit_message_text(result.strip(), parse_mode="Markdown")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL,            handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot polling started.")
    app.run_polling()

if __name__ == '__main__':
    main()