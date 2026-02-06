import logging
import json
import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from edumate_api import fetch_attendance

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8568757589:AAFKrK_4ljcd6k1Wv7TJMUXoqY6NPqavRm0")
USERS_FILE = "users.json"

# State constants
STATE_IDLE = 0
STATE_WAITING_EMAIL = 1
STATE_WAITING_PASSWORD = 2

# In-memory value cache
user_states = {}

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user(chat_id, email):
    users = load_users()
    users[str(chat_id)] = email
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def get_user_email(chat_id):
    users = load_users()
    return users.get(str(chat_id))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    email = get_user_email(chat_id)
    
    if email:
        await update.message.reply_text(
            f"Welcome back! Your registered email is {email}.\n"
            "Use /attendance to fetch your data."
        )
        user_states[chat_id] = STATE_IDLE
    else:
        await update.message.reply_text(
            "Welcome to the Edumate Attendance Bot!\n"
            "I see you are new here. Please enter your *Edumate Email ID* to get started.",
            parse_mode="Markdown"
        )
        user_states[chat_id] = STATE_WAITING_EMAIL

async def attendance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    email = get_user_email(chat_id)
    
    if not email:
        await update.message.reply_text("You are not registered. Please use /start to register.")
        user_states[chat_id] = STATE_IDLE
        return

    await update.message.reply_text(
        "Please enter your *Edumate Password*.\n"
        "_Note: Your password is NOT stored and is only used once to fetch data._",
        parse_mode="Markdown"
    )
    user_states[chat_id] = STATE_WAITING_PASSWORD

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    state = user_states.get(chat_id, STATE_IDLE)

    if state == STATE_WAITING_EMAIL:
        # Simple email validation
        if "@" not in text:
            await update.message.reply_text("That doesn't look like a valid email. Please try again.")
            return
        
        save_user(chat_id, text)
        await update.message.reply_text(
            f"Awesome! Saved {text}.\n"
            "Now, let's fetch your attendance. Please enter your *Password*.",
            parse_mode="Markdown"
        )
        user_states[chat_id] = STATE_WAITING_PASSWORD

    elif state == STATE_WAITING_PASSWORD:
        email = get_user_email(chat_id)
        if not email:
            await update.message.reply_text("Something went wrong. Please /start again.")
            user_states[chat_id] = STATE_IDLE
            return

        # Delete the password message for security
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete password message: {e}")

        status_msg = await update.message.reply_text("Fetching data... Please wait.")
        
        try:
            data, error_msg, screenshot_path = await fetch_attendance(email, text)
            
            if data:
                result_message = (
                    f"*Student:* {data['email']}\n"
                    f"*Attendance:* {data['attendance']}\n"
                    f"*OD Percentage:* {data['od']}"
                )
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=result_message,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"Error: {error_msg}\nSee attached screenshot for details."
                )
                if screenshot_path and os.path.exists(screenshot_path):
                    await context.bot.send_photo(chat_id=chat_id, photo=open(screenshot_path, 'rb'))
                    # Clean up
                    os.remove(screenshot_path)

        except Exception as e:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"An error occurred: {str(e)}"
            )
        
        user_states[chat_id] = STATE_IDLE

    else:
        # Default behavior for random messages
        if text.lower() == "attendance":
             await attendance_command(update, context)
        else:
            await update.message.reply_text("I didn't understand that. Try /attendance or /help.")

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: TELEGRAM_BOT_TOKEN is not set properly.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attendance", attendance_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Multi-user bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
