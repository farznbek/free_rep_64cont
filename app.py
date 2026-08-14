"""
UnlockWord — Backend & Telegram Bot (Admin Panel bilan)
"""
import sqlite3
import json
import time
import random
import requests
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

CONFIG = {
    "TELEGRAM_BOT_TOKEN": "8779433775:AAFZgkrQjY2DHh9V4haS0TcIzsnRirE4Uug",
    "ADMIN_TELEGRAM_ID": 8613094318, # O'zingizning ID raqamingizni yozing
    "WEBAPP_DOMAIN": "t.me/UnlockWordbot/apps",
    "GROQ_API_KEY": "GROQ_KEY_SHU_YERGA",
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "DB_PATH": "unlockword.db",
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def db():
    conn = sqlite3.connect(CONFIG["DB_PATH"], check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    INSERT OR IGNORE INTO settings VALUES ('start_text', 'Salom! UnlockWordga xush kelibsiz.');
    INSERT OR IGNORE INTO settings VALUES ('start_photo', '');
    INSERT OR IGNORE INTO settings VALUES ('price', '2500');
    INSERT OR IGNORE INTO settings VALUES ('channels', '[]');
    
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        name TEXT, credits INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, expected_amount INTEGER, status TEXT DEFAULT 'pending'
    );
    """)
    conn.commit()
    conn.close()

init_db()

# --- FASTAPI WEBAPP ENDPOINTLAR ---
class LoginIn(BaseModel):
    telegram_id: int
    name: str

@app.post("/api/auth/login")
def login(body: LoginIn):
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (body.telegram_id,)).fetchone()
    if not u:
        conn.execute("INSERT INTO users (telegram_id, name) VALUES (?,?)", (body.telegram_id, body.name))
        conn.commit()
        u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (body.telegram_id,)).fetchone()
    conn.close()
    if u['is_banned']: raise HTTPException(403, "Bloklangansiz.")
    return dict(u)

@app.post("/api/payment/generate")
def gen_payment(telegram_id: int):
    conn = db()
    price = int(conn.execute("SELECT value FROM settings WHERE key='price'").fetchone()['value'])
    amount = price + random.randint(1, 99)
    conn.execute("INSERT INTO payments (user_id, expected_amount) VALUES (?,?)", (telegram_id, amount))
    conn.commit()
    conn.close()
    return {"amount": amount}

# --- TELEGRAM BOT & ADMIN PANEL ---
def send_msg(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

def send_photo(chat_id, photo, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

admin_states = {}

@app.post("/webhook")
async def tg_webhook(req: Request):
    update = await req.json()
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        
        # Oddiy user start
        if text == "/start":
            conn = db()
            start_txt = conn.execute("SELECT value FROM settings WHERE key='start_text'").fetchone()['value']
            start_pic = conn.execute("SELECT value FROM settings WHERE key='start_photo'").fetchone()['value']
            conn.close()
            markup = {"inline_keyboard": [[{"text": "🔓 Ilovaga kirish", "web_app": {"url": CONFIG["WEBAPP_DOMAIN"]}}]]}
            if start_pic: send_photo(chat_id, start_pic, start_txt, markup)
            else: send_msg(chat_id, start_txt, markup)
            return {"ok": True}

        # Admin panel qismi
        if chat_id == CONFIG["ADMIN_TELEGRAM_ID"]:
            if text == "/admin":
                markup = {"keyboard": [
                    ["📣 Xabar tarqatish", "⚙️ Start xabarni sozlash"],
                    ["📢 Kanallarni sozlash", "🚫 Userni bloklash"],
                    ["💳 Narxni o'zgartirish", "🔙 Chiqish"]
                ], "resize_keyboard": True}
                send_msg(chat_id, "👑 <b>Admin Panelga xush kelibsiz!</b>", markup)
                admin_states[chat_id] = None
                return {"ok": True}
            
            state = admin_states.get(chat_id)
            if text == "🔙 Chiqish":
                admin_states[chat_id] = None
                send_msg(chat_id, "Bosh menyudasiz.", {"remove_keyboard": True})
            elif text == "📣 Xabar tarqatish":
                admin_states[chat_id] = "broadcast"
                send_msg(chat_id, "Tarqatmoqchi bo'lgan xabaringizni yuboring (Forward qilsangiz ham bo'ladi):")
            elif state == "broadcast":
                conn = db()
                users = conn.execute("SELECT telegram_id FROM users").fetchall()
                conn.close()
                send_msg(chat_id, f"Xabar {len(users)} ta userga yuborilmoqda...")
                admin_states[chat_id] = None
            elif text == "⚙️ Start xabarni sozlash":
                admin_states[chat_id] = "set_start_txt"
                send_msg(chat_id, "Yangi start matnini yuboring:")
            elif state == "set_start_txt":
                conn = db()
                conn.execute("UPDATE settings SET value=? WHERE key='start_text'", (text,))
                conn.commit()
                conn.close()
                send_msg(chat_id, "✅ Start matni yangilandi!")
                admin_states[chat_id] = None
                
            # To'lov avtotasdiqlash (Humo/Uzcard forward qilinsa)
            if "forward_from" in msg or "forward_from_chat" in msg:
                if "tushdi" in text.lower() or "summa" in text.lower():
                    # Xabar ichidan summani qidiramiz
                    conn = db()
                    pendings = conn.execute("SELECT * FROM payments WHERE status='pending'").fetchall()
                    for p in pendings:
                        if str(p['expected_amount']) in text:
                            conn.execute("UPDATE payments SET status='paid' WHERE id=?", (p['id'],))
                            conn.execute("UPDATE users SET credits=credits+1000 WHERE telegram_id=?", (p['user_id'],))
                            conn.commit()
                            send_msg(chat_id, f"✅ To'lov tasdiqlandi! User ({p['user_id']}) ga 1000 ta so'z berildi.")
                            send_msg(p['user_id'], "🎉 To'lovingiz tasdiqlandi! Hisobingizga 1000 ta so'z qo'shildi.")
                            break
                    conn.close()

    return {"ok": True}

@app.get("/")
def serve_html():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)

