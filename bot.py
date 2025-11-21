import os
import requests
from flask import Flask, request
from db import init_db, get_conn

TOKEN = os.getenv("BOT_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"
app = Flask(__name__)

init_db()

def send_message(chat_id, text, buttons=None):
    payload = {"chat_id": chat_id, "text": text}

    if buttons:
        payload["reply_markup"] = {"keyboard": buttons, "resize_keyboard": True}

    requests.post(f"{BASE}/sendMessage", json=payload)

def send_photo(chat_id, photo, caption, buttons=None):
    payload = {"chat_id": chat_id, "photo": photo, "caption": caption}

    if buttons:
        payload["reply_markup"] = {"keyboard": buttons, "resize_keyboard": True}

    requests.post(f"{BASE}/sendPhoto", json=payload)

@app.route("/", methods=["GET"])
def home():
    return "VibeMatch Bot Running!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "OK"

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    photo = msg.get("photo")

    conn = get_conn()
    cur = conn.cursor()

    # Перевіряємо чи користувач існує
    user = cur.execute("SELECT * FROM users WHERE user_id=?", (chat_id,)).fetchone()

    # НОВИЙ КОРИСТУВАЧ
    if user is None:
        cur.execute("INSERT INTO users (user_id, step) VALUES (?,?)", (chat_id, "name"))
        conn.commit()
        send_message(chat_id, "👋 Вітаю у VibeMatch!\n\nЯк тебе звати?")
        return "OK"

    step = user[6]  # step field

    # --- АНКЕТА: ІМ'Я ---
    if step == "name":
        cur.execute("UPDATE users SET name=?, step=? WHERE user_id=?", (text, "age", chat_id))
        conn.commit()
        send_message(chat_id, "Скільки тобі років?")
        return "OK"

    # --- АНКЕТА: ВІК ---
    if step == "age":
        if not text.isdigit():
            send_message(chat_id, "Вік має бути числом. Спробуй ще раз:")
            return "OK"

        cur.execute("UPDATE users SET age=?, step=? WHERE user_id=?", (int(text), "city", chat_id))
        conn.commit()
        send_message(chat_id, "З якого ти міста?")
        return "OK"

    # --- АНКЕТА: МІСТО ---
    if step == "city":
        cur.execute("UPDATE users SET city=?, step=? WHERE user_id=?", (text, "bio", chat_id))
        conn.commit()
        send_message(chat_id, "Напиши коротко про себе 📝")
        return "OK"

    # --- АНКЕТА: БІО ---
    if step == "bio":
        cur.execute("UPDATE users SET bio=?, step=? WHERE user_id=?", (text, "photo", chat_id))
        conn.commit()
        send_message(chat_id, "Надішли своє фото 📸")
        return "OK"

    # --- АНКЕТА: ФОТО ---
    if step == "photo":
        if not photo:
            send_message(chat_id, "Надішли саме фото.")
            return "OK"

        file_id = photo[-1]["file_id"]
        cur.execute("UPDATE users SET photo_id=?, step=? WHERE user_id=?", (file_id, "done", chat_id))
        conn.commit()

        send_message(chat_id, "✔️ Анкету створено!\n\nНатисни *Почати пошук*", buttons=[["🔍 Пошук"]])
        return "OK"

    # --- ПОШУК ---
    if text == "🔍 Пошук":
        other = cur.execute(
            "SELECT * FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1",
            (chat_id,)
        ).fetchone()

        if not other:
            send_message(chat_id, "Немає анкет. Зачекай поки хтось додасться ❤️")
            return "OK"

        user_id, name, age, city, bio, photo_id, _ = other

        caption = f"❤️ *{name}, {age}*\n📍 {city}\n\n{bio}"

        send_photo(
            chat_id,
            photo_id,
            caption,
            buttons=[["👍 Лайк", "👎 Дизлайк"], ["🔍 Пошук"]]
        )

        cur.execute("UPDATE users SET step=? WHERE user_id=?", (f"view:{user_id}", chat_id))
        conn.commit()
        return "OK"

    # --- ЛАЙК / ДИЗЛАЙК ---
    if "view:" in step:
        target_id = int(step.split(":")[1])

        if text == "👍 Лайк":
            cur.execute("INSERT INTO likes (user_from, user_to) VALUES (?,?)", (chat_id, target_id))
            conn.commit()

            # Перевіряємо взаємний
            check = cur.execute(
                "SELECT * FROM likes WHERE user_from=? AND user_to=?",
                (target_id, chat_id)
            ).fetchone()

            if check:
                send_message(chat_id, "🎉 Взаємний лайк! Ви можете писати один одному!")
                send_message(target_id, "🎉 У вас матч! Хтось лайкнув вас!")

            send_message(chat_id, "Наступна анкета 🔍", buttons=[["🔍 Пошук"]])

        elif text == "👎 Дизлайк":
            send_message(chat_id, "Наступна анкета 🔍", buttons=[["🔍 Пошук"]])

        cur.execute("UPDATE users SET step='done' WHERE user_id=?", (chat_id,))
        conn.commit()

        return "OK"

    return "OK"
