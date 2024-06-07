import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from flask import Flask, request
import json

# Load environment variables
load_dotenv()

# Load Firebase service account key from environment variable
service_account_info = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not service_account_info:
    raise ValueError("The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

# Parse the service account key from JSON string
service_account_dict = json.loads(service_account_info)

# Initialize Firebase with the service account key from the environment variable
cred = credentials.Certificate(service_account_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# In-memory user data storage for current registration process
user_registration_data = {}

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return 'ok'

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Register", callback_data='register')],
        [InlineKeyboardButton("Login", callback_data='login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Please choose an option:", reply_markup=reply_markup)

# CallbackQueryHandler to handle button presses
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == 'register':
        await query.message.reply_text("Please enter your username:")
        user_registration_data[query.from_user.id] = {'step': 'username'}
    elif query.data == 'login':
        await query.message.reply_text("Login functionality not implemented yet.")

# MessageHandler to handle user responses during registration
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in user_registration_data:
        step = user_registration_data[user_id]['step']
        if step == 'username':
            username = update.message.text
            if check_username_exists(username):
                await update.message.reply_text("Username already taken. Please enter another username:")
            else:
                user_registration_data[user_id]['username'] = username
                user_registration_data[user_id]['step'] = 'password'
                await update.message.reply_text("Great! Now enter your password:")
        elif step == 'password':
            password = update.message.text
            user_registration_data[user_id]['password'] = password
            user_registration_data[user_id]['step'] = 'referral'
            await update.message.reply_text("Enter your referral code (or type 'skip' if you don't have one):")
        elif step == 'referral':
            referral_code = update.message.text
            user_registration_data[user_id]['referral'] = referral_code if referral_code.lower() != 'skip' else None
            await save_user_data(user_id)
            await update.message.reply_text("Registration complete!")
            del user_registration_data[user_id]
    else:
        await update.message.reply_text("Please start the registration process first by clicking the Register button.")

# Function to check if a username exists in Firestore
def check_username_exists(username):
    users_ref = db.collection('users')
    docs = users_ref.where('username', '==', username).stream()
    return any(doc.exists for doc in docs)

# Function to save user data to Firestore
async def save_user_data(user_id):
    user_info = user_registration_data[user_id]
    db.collection('users').document(str(user_id)).set({
        'username': user_info['username'],
        'password': user_info['password'],
        'referral': user_info['referral']
    })

def main() -> None:
    # Load bot token from environment variable
    bot_token = os.getenv("BOT_TOKEN")

    # Create the Application
    global application
    application = Application.builder().token(bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set webhook
    webhook_url = os.getenv("WEBHOOK_URL")
    application.bot.set_webhook(url=webhook_url)

if __name__ == '__main__':
    main()
    app.run(port=5000)
