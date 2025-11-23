import os
import sqlite3
import requests
from flask import Flask, request

# -----------------------------
#  ТУТ ТВОЙ ТОКЕН (ти хочеш цей)
# -----------------------------
TOKEN = "8428517307:AAH7qxX-Zd19solih0DeqM8fmsKAHAT7yiM"
BASE = f"https://api.telegram.org/bot{TOKEN}"
APP_URL = "https://vibematch-bot.onrender.com/" + TOKEN

# -----------------------------
#  FLASK APP
# -----------------------------
app = Flask(__name__)

# -----------------------------
#  DATABASE
# -----------------------------
def db():
    conn = sqlite3.connect("vibematch.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            bio TEXT,
            gender TEXT,
            looking_for TEXT,
            photo_id TEXT,
            step TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            user_from INTEGER,
            user_to INTEGER
        )
    """)
    conn.commit()

init_db()

# -----------------------------
#  BOT FUNCTIONS
# -----------------------------
def send_message(chat_id, text, buttons=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if buttons:
        payload["reply_markup"] = {"keyboard": buttons, "resize_keyboard": True}
    requests.post(BASE + "/sendMessage", json=payload)

def send_photo(chat_id, file_id, caption, buttons=None):
    payload = {
        "chat_id": chat_id,
        "photo": file_id,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    if buttons:
        payload["reply_markup"] = {"keyboard": buttons, "resize_keyboard": True}
    requests.post(BASE + "/sendPhoto", json=payload)

# -----------------------------
#  ROOT CHECK
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "VibeMatch running!"

# -----------------------------
#  WEBHOOK HANDLER
# -----------------------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "OK"

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    photo = msg.get("photo")
    username = msg["chat"].get("username", "")

    conn = db()
    cur = conn.cursor()

    user = cur.execute("SELECT * FROM users WHERE user_id=?", (chat_id,)).fetchone()

    # -------------------------------------
    # НОВИЙ КОРИСТУВАЧ
    # -------------------------------------
    if user is None:
        cur.execute("INSERT INTO users (user_id, username, step) VALUES (?,?,?)",
                    (chat_id, username, "name"))
        conn.commit()
        send_message(chat_id, "👋 Привіт у *VibeMatch*! Як тебе звати?")
        return "OK"

    step = user["step"]

    # --- ІМ'Я ---
    if step == "name":
        cur.execute("UPDATE users SET name=?, step='age' WHERE user_id=?", (text, chat_id))
        conn.commit()
        send_message(chat_id, "Скільки тобі років?")
        return "OK"

    # --- ВІК ---
    if step == "age":
        if not text.isdigit():
            send_message(chat_id, "Вік має бути числом.")
            return "OK"
        cur.execute("UPDATE users SET age=?, step='city' WHERE user_id=?", (int(text), chat_id))
        conn.commit()
        send_message(chat_id, "З якого ти міста?")
        return "OK"

    # --- МІСТО ---
    if step == "city":
        cur.execute("UPDATE users SET city=?, step='gender' WHERE user_id=?", (text, chat_id))
        conn.commit()
        send_message(chat_id, "Ти хлопець чи дівчина?", [["👨 Хлопець", "👩 Дівчина"]])
        return "OK"

    # --- СТАТЬ ---
    if step == "gender":
        if text not in ["👨 Хлопець", "👩 Дівчина"]:
            send_message(chat_id, "Оберіть:", [["👨 Хлопець", "👩 Дівчина"]])
            return "OK"
        gender = "male" if "Хлопець" in text else "female"
        cur.execute("UPDATE users SET gender=?, step='looking' WHERE user_id=?", (gender, chat_id))
        conn.commit()
        send_message(chat_id, "Кого ти шукаєш?", [["👨 Хлопця", "👩 Дівчину", "🌈 Всіх"]])
        return "OK"

    # --- КОГО ШУКАЄ ---
    if step == "looking":
        if text not in ["👨 Хлопця", "👩 Дівчину", "🌈 Всіх"]:
            send_message(chat_id, "Оберіть:", [["👨 Хлопця", "👩 Дівчину", "🌈 Всіх"]])
            return "OK"
        looking = "male" if text == "👨 Хлопця" else "female" if text == "👩 Дівчину" else "all"
        cur.execute("UPDATE users SET looking_for=?, step='bio' WHERE user_id=?", (looking, chat_id))
        conn.commit()
        send_message(chat_id, "Напиши коротко про себе 📝")
        return "OK"

    # --- БІО ---
    if step == "bio":
        cur.execute("UPDATE users SET bio=?, step='photo' WHERE user_id=?", (text, chat_id))
        conn.commit()
        send_message(chat_id, "Надішли своє фото 📸")
        return "OK"

    # --- ФОТО ---
    if step == "photo":
        if not photo:
            send_message(chat_id, "Надішли саме фото.")
            return "OK"
        file_id = photo[-1]["file_id"]
        cur.execute("UPDATE users SET photo_id=?, step='done' WHERE user_id=?",
                    (file_id, chat_id))
        conn.commit()
        send_message(chat_id, "Готово! Натисни *Пошук*", [["🔍 Пошук"]])
        return "OK"

    # -------------------------------------
    #        П О Ш У К
    # -------------------------------------
    if text == "🔍 Пошук":
        usr = cur.execute("SELECT * FROM users WHERE user_id=?", (chat_id,)).fetchone()

        if usr["looking_for"] == "male":
            search = "male"
        elif usr["looking_for"] == "female":
            search = "female"
        else:
            search = None

        if search:
            other = cur.execute("""
                SELECT * FROM users WHERE user_id != ? AND gender=? ORDER BY RANDOM() LIMIT 1
            """, (chat_id, search)).fetchone()
        else:
            other = cur.execute("""
                SELECT * FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1
            """, (chat_id,)).fetchone()

        if not other:
            send_message(chat_id, "Анкети закінчились 😢")
            return "OK"

        caption = f"❤️ *{other['name']}, {other['age']}*\n📍 {other['city']}\n\n{other['bio']}"

        send_photo(chat_id, other["photo_id"], caption,
                   [["👍 Лайк", "👎 Дизлайк"], ["🔍 Пошук"]])

        cur.execute("UPDATE users SET step=? WHERE user_id=?",
                    (f"view:{other['user_id']}", chat_id))
        conn.commit()
        return "OK"

    # -------------------------------------
    #          ЛАЙК / ДИЗЛАЙК
    # -------------------------------------
    if step.startswith("view:"):
        target = int(step.split(":")[1])

        if text == "👍 Лайк":
            cur.execute("INSERT INTO likes (user_from, user_to) VALUES (?,?)",
                        (chat_id, target))
            conn.commit()

            match = cur.execute("""
                SELECT * FROM likes WHERE user_from=? AND user_to=?
            """, (target, chat_id)).fetchone()

            if match:
                # Отримуємо username обох
                my_user = cur.execute("SELECT * FROM users WHERE user_id=?", (chat_id,)).fetchone()
                other_user = cur.execute("SELECT * FROM users WHERE user_id=?", (target,)).fetchone()

                send_message(chat_id,
                             f"🎉 *Взаємна симпатія!*\nНапиши @{other_user['username']}")
                send_message(target,
                             f"🎉 *Взаємна симпатія!*\nНапиши @{my_user['username']}")

        send_message(chat_id, "Наступна анкета:", [["🔍 Пошук"]])
        cur.execute("UPDATE users SET step='done' WHERE user_id=?", (chat_id,))
        conn.commit()
        return "OK"

    return "OK"

# -----------------------------
#  SET WEBHOOK AUTO
# -----------------------------
requests.get(BASE + "/setWebhook?url=" + APP_URL)

# -----------------------------
#  RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
