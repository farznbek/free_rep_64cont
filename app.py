"""
============================================================
 UnlockWord — Backend v4 (FastAPI + SQLite)
 Barcha PDF talablari kiritilgan to'liq versiya
============================================================
"""
import sqlite3
import json
import time
import threading
import difflib
import random
import io
import csv
import re
from datetime import datetime, timedelta
from typing import Optional, List

import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

BOOTSTRAP = {
    "TELEGRAM_BOT_TOKEN": "8779433775:AAFZgkrQjY2DHh9V4haS0TcIzsnRirE4Uug",
    "ADMIN_TELEGRAM_ID": 8613094318,
    "DATABASE_PATH": "unlockword.db",
}

DB_PATH = BOOTSTRAP["DATABASE_PATH"]
TG_API = f"https://api.telegram.org/bot{BOOTSTRAP['TELEGRAM_BOT_TOKEN']}"
ADMIN_ID = BOOTSTRAP["ADMIN_TELEGRAM_ID"]

app = FastAPI(title="UnlockWord API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

admin_state = {}

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

DEFAULT_SETTINGS = {
    "webapp_domain": "", "groq_api_key": "", "groq_model": "llama-3.3-70b-versatile",
    "price_per_1000": "2500", "min_credits_purchase": "100", "main_channel": "", "logo_url": "",
    "icon_home": "", "icon_search": "", "icon_practice": "", "icon_new": "", "icon_profile": "",
    "start_message_uz": "UnlockWord'ni ochish uchun tugmani bosing:",
    "start_message_ru": "Нажмите кнопку, чтобы открыть UnlockWord:",
    "start_message_en": "Tap the button to open UnlockWord:",
    "payment_card": "", "bot_message_emoji": "✨",
    "sentence_limits": json.dumps({lvl: {"min": 3, "max": 15} for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]}),
    "help_admin": "", "auto_ai_check_suggestions": "1",
    "suggestion_reward_amount": "50", "referral_bonus": "50",
    "file_parse_price": "1", "file_word_price": "1",
}

def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT NOT NULL, pronunciation TEXT,
        base_level TEXT, frequency INTEGER DEFAULT 0, status TEXT DEFAULT 'active', suggested_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS meanings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER NOT NULL,
        meaning TEXT, translation TEXT, translation_ru TEXT, cefr_level TEXT, synonym_text TEXT,
        FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT, meaning_id INTEGER NOT NULL, sentence TEXT,
        FOREIGN KEY(meaning_id) REFERENCES meanings(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS synonyms (word_id INTEGER, synonym_word_id INTEGER);
    CREATE TABLE IF NOT EXISTS antonyms (word_id INTEGER, antonym_word_id INTEGER);
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE,
        name TEXT, nickname TEXT, avatar_url TEXT, current_level TEXT DEFAULT 'A1',
        credits INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, seen_intro INTEGER DEFAULT 0,
        lang TEXT DEFAULT '', secondary_lang TEXT DEFAULT '', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_ref TEXT, kind TEXT,
        title TEXT, invite_link TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        expected_amount INTEGER, credits_to_add INTEGER,
        status TEXT DEFAULT 'awaiting_amount', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, levels TEXT,
        total_count INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
        correct_count INTEGER DEFAULT 0, next_review_at TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS batch_words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, word_id INTEGER,
        status TEXT DEFAULT 'new', FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS mistakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, word_id INTEGER,
        original TEXT, correction TEXT, explanation TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS saved_words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, word_id INTEGER, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, word_id INTEGER, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
        read INTEGER DEFAULT 0, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
        admin_reply TEXT, status TEXT DEFAULT 'open', created_at TEXT, replied_at TEXT
    );
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER UNIQUE,
        referred_ip TEXT, bonus_credits INTEGER DEFAULT 0, status TEXT DEFAULT 'granted', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS file_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT,
        word_count INTEGER DEFAULT 0, price INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
        payload TEXT, created_at TEXT
    );
    """)
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = db()
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

def seq_id(user_id: int) -> str: return f"A{user_id:03d}"
def now_iso(): return datetime.utcnow().isoformat()

def get_or_create_user(telegram_id: int, name: str = "") -> sqlite3.Row:
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    if u:
        if u["is_banned"]:
            conn.close()
            raise HTTPException(403, "Hisobingiz bloklangan.")
        conn.close()
        return u
    conn.execute("INSERT INTO users (telegram_id, name, nickname, credits, lang, created_at) VALUES (?,?,?,?,?,?)",
                 (telegram_id, name, name, 0, "", now_iso()))
    conn.commit()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return u

def call_groq_json(system_prompt: str, user_prompt: str) -> dict:
    api_key = get_setting("groq_api_key")
    if not api_key: return {}
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": get_setting("groq_model", "llama-3.3-70b-versatile"), "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.2, "response_format": {"type": "json_object"}},
            timeout=30,
        )
        if resp.ok: return json.loads(resp.json()["choices"][0]["message"]["content"])
    except: pass
    return {}

def telegram_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: return requests.post(f"{TG_API}/sendMessage", data=payload, timeout=20).json()
    except: return None

def telegram_get_file_url(file_id):
    try:
        r = requests.get(f"{TG_API}/getFile", params={"file_id": file_id}, timeout=15).json()
        return f"https://api.telegram.org/file/bot{BOOTSTRAP['TELEGRAM_BOT_TOKEN']}/{r['result']['file_path']}"
    except: return None

class LoginIn(BaseModel): telegram_id: int; name: str = ""
class SuggestWordIn(BaseModel): telegram_id: int; word: str; translation: str; translation_ru: str = ""; description: str = ""; synonym: str = ""; level: str = "A1"; example1: str = ""; example2: str = ""
class StartBatchIn(BaseModel): telegram_id: int; levels: List[str]; count: int = 20
class StartBatchFromSavedIn(BaseModel): telegram_id: int; word_ids: List[int]
class CheckSentenceIn(BaseModel): telegram_id: int; batch_id: Optional[int]=None; word_id: int; word: str; sentence: str
class ScheduleReviewIn(BaseModel): telegram_id: int; batch_id: int; delay_key: str; custom_minutes: Optional[int]=None
class ProfileUpdateIn(BaseModel): telegram_id: int; nickname: Optional[str]=None; avatar_url: Optional[str]=None; lang: Optional[str]=None; secondary_lang: Optional[str]=None
class SaveWordIn(BaseModel): telegram_id: int; word_id: int
class TicketIn(BaseModel): telegram_id: int; message: str
class ReferralIn(BaseModel): telegram_id: int; referrer_display_id: str; ip: str = ""
class FileConfirmIn(BaseModel): telegram_id: int; job_id: int

@app.get("/api/settings/public")
def public_settings():
    return {
        "logo_url": get_setting("logo_url"), "price_per_1000": int(get_setting("price_per_1000", "2500")),
        "min_credits_purchase": int(get_setting("min_credits_purchase", "100")), "payment_card": get_setting("payment_card"),
        "main_channel": get_setting("main_channel"), "help_admin": get_setting("help_admin"),
        "icon_home": get_setting("icon_home"), "icon_search": get_setting("icon_search"),
        "icon_practice": get_setting("icon_practice"), "icon_new": get_setting("icon_new"), "icon_profile": get_setting("icon_profile"),
    }

@app.post("/api/auth/login")
def login(body: LoginIn):
    u = get_or_create_user(body.telegram_id, body.name)
    return {**dict(u), "display_id": seq_id(u["id"])}

@app.get("/api/profile/{telegram_id}")
def get_profile(telegram_id: int):
    u = get_or_create_user(telegram_id)
    return {**dict(u), "display_id": seq_id(u["id"])}

@app.post("/api/profile/mark-intro-seen")
def mark_intro_seen(telegram_id: int):
    conn = db(); conn.execute("UPDATE users SET seen_intro=1 WHERE telegram_id=?", (telegram_id,)); conn.commit(); conn.close()
    return {"status": "ok"}

@app.get("/api/notifications/{telegram_id}")
def get_notifications(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); rows = conn.execute("SELECT * FROM notifications WHERE user_id=? AND read=0 ORDER BY id ASC", (u["id"],)).fetchall(); conn.close()
    return [dict(r) for r in rows]

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int):
    conn = db(); conn.execute("UPDATE notifications SET read=1 WHERE id=?", (notif_id,)); conn.commit(); conn.close()
    return {"status": "ok"}

@app.post("/api/ticket/create")
def create_ticket(body: TicketIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    conn.execute("INSERT INTO tickets (user_id, message, status, created_at) VALUES (?,?, 'open', ?)", (u["id"], body.message, now_iso()))
    ticket_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit(); conn.close()
    telegram_send_message(ADMIN_ID, f"🆘 Murojaat #{ticket_id}\nKimdan: {u['nickname']} ({seq_id(u['id'])})\n\nXabar:\n{body.message}\n\nJavob yozish uchun: /reply {ticket_id} [matn]")
    return {"status": "ok"}

@app.get("/api/ticket/list/{telegram_id}")
def list_tickets(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); rows = conn.execute("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (u["id"],)).fetchall(); conn.close()
    return [dict(r) for r in rows]

@app.post("/api/referral/claim")
def claim_referral(body: ReferralIn):
    u = get_or_create_user(body.telegram_id)
    ref_id = int(str(body.referrer_display_id).strip().lstrip("Aa").lstrip("0") or "0")
    if not ref_id or ref_id == u["id"]: return {"status": "skip"}
    conn = db()
    if conn.execute("SELECT id FROM referrals WHERE referred_id=?", (u["id"],)).fetchone(): conn.close(); return {"status": "skip"}
    bonus = int(get_setting("referral_bonus", "50"))
    conn.execute("INSERT INTO referrals (referrer_id, referred_id, bonus_credits, created_at) VALUES (?,?,?,?)", (ref_id, u["id"], bonus, now_iso()))
    conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (bonus, ref_id))
    conn.commit(); conn.close()
    telegram_send_message(conn.execute("SELECT telegram_id FROM users WHERE id=?", (ref_id,)).fetchone()["telegram_id"], f"🎁 Referral orqali yangi do'st qo'shildi! +{bonus} kredit.")
    return {"status": "ok"}

@app.get("/api/referral/info/{telegram_id}")
def referral_info(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    c = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(bonus_credits),0) s FROM referrals WHERE referrer_id=?", (u["id"],)).fetchone()
    conn.close()
    return {"display_id": seq_id(u["id"]), "invited_count": c["c"], "earned_credits": c["s"]}

def fallback_pdf_extract(raw: bytes):
    return " ".join(re.findall(rb'[a-zA-Z]{2,}', raw)).decode('ascii', errors='ignore')

@app.post("/api/file/analyze")
async def file_analyze(telegram_id: int = Form(...), file: UploadFile = File(...)):
    u = get_or_create_user(telegram_id)
    raw = await file.read()
    name = (file.filename or "").lower()
    text = ""
    if name.endswith(".txt"): text = raw.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
        except: text = fallback_pdf_extract(raw)
    elif name.endswith(".docx"):
        try:
            from docx import Document
            text = "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
        except: raise HTTPException(400, "DOCX o'qishda xatolik.")
    else: raise HTTPException(400, "Faqat PDF, DOCX yoki TXT.")
    
    words = list(set(re.findall(r"[a-zA-Z]{2,}", text.lower())))
    if not words: raise HTTPException(400, "Inglizcha so'zlar topilmadi.")
    price = int(get_setting("file_parse_price", "1")) + len(words) * int(get_setting("file_word_price", "1"))
    conn = db()
    conn.execute("INSERT INTO file_jobs (user_id, filename, word_count, price, payload, created_at) VALUES (?,?,?,?,?,?)", (u["id"], file.filename, len(words), price, json.dumps(words[:15000]), now_iso()))
    job_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit(); conn.close()
    return {"job_id": job_id, "filename": file.filename, "word_count": len(words), "price": price, "your_credits": u["credits"]}

@app.post("/api/file/confirm")
def file_confirm(body: FileConfirmIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    job = conn.execute("SELECT * FROM file_jobs WHERE id=? AND user_id=?", (body.job_id, u["id"])).fetchone()
    if not job or job["status"] != "pending": conn.close(); raise HTTPException(400, "Topilmadi yoki tasdiqlangan.")
    if u["credits"] < job["price"]: conn.close(); raise HTTPException(402, "Kredit yetarli emas.")
    words = json.loads(job["payload"])
    added = 0
    for w in words:
        ex = conn.execute("SELECT id FROM words WHERE word=?", (w,)).fetchone()
        if ex: word_id = ex["id"]
        else:
            conn.execute("INSERT INTO words (word, status) VALUES (?, 'active')", (w,))
            word_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            added += 1
        if not conn.execute("SELECT id FROM saved_words WHERE user_id=? AND word_id=?", (u["id"], word_id)).fetchone():
            conn.execute("INSERT INTO saved_words (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], word_id, now_iso()))
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (job["price"], u["id"]))
    conn.execute("UPDATE file_jobs SET status='done' WHERE id=?", (job["id"],))
    conn.commit(); conn.close()
    return {"status": "ok", "words_added_to_dictionary": added, "words_saved": len(words), "credits_spent": job["price"]}

@app.get("/api/dictionary/history/{telegram_id}")
def dictionary_history(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT w.* FROM search_history sh JOIN words w ON w.id=sh.word_id WHERE sh.user_id=? GROUP BY w.id ORDER BY MAX(sh.id) DESC LIMIT 10", (u["id"],)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        m = conn.execute("SELECT translation, translation_ru FROM meanings WHERE word_id=? LIMIT 1", (r["id"],)).fetchone()
        d["translation_preview"] = (m["translation_ru"] if (u["lang"] == "ru" and m["translation_ru"]) else m["translation"]) if m else ""
        out.append(d)
    conn.close()
    return out

@app.post("/api/dictionary/clear-history/{telegram_id}")
def clear_history(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); conn.execute("DELETE FROM search_history WHERE user_id=?", (u["id"],)); conn.commit(); conn.close()
    return {"status": "ok"}

@app.get("/api/dictionary/search")
def dictionary_search(q: str, lang: str = "uz"):
    conn = db()
    if q.strip().isdigit(): rows = conn.execute("SELECT * FROM words WHERE id=? AND status='active'", (int(q.strip()),)).fetchall()
    else: rows = conn.execute("SELECT * FROM words WHERE word LIKE ? AND status='active' ORDER BY word ASC LIMIT 20", (f"{q}%",)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        m = conn.execute("SELECT translation, translation_ru FROM meanings WHERE word_id=? LIMIT 1", (r["id"],)).fetchone()
        d["translation_preview"] = (m["translation_ru"] if (lang == "ru" and m and m["translation_ru"]) else m["translation"]) if m else ""
        out.append(d)
    conn.close()
    return out

@app.get("/api/dictionary/word/{word_id}")
def dictionary_word(word_id: int, telegram_id: Optional[int]=None, lang: str = "uz"):
    conn = db()
    w = conn.execute("SELECT * FROM words WHERE id=?", (word_id,)).fetchone()
    if not w: conn.close(); raise HTTPException(404, "So'z topilmadi.")
    if telegram_id:
        u = conn.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        if u:
            conn.execute("INSERT INTO search_history (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], word_id, now_iso()))
            conn.commit()
    meanings = conn.execute("SELECT * FROM meanings WHERE word_id=?", (word_id,)).fetchall()
    out_meanings = []
    for m in meanings:
        ex = conn.execute("SELECT sentence FROM examples WHERE meaning_id=?", (m["id"],)).fetchall()
        tr = m["translation_ru"] if (lang == "ru" and m["translation_ru"]) else m["translation"]
        out_meanings.append({**dict(m), "translation_shown": tr, "examples": [e["sentence"] for e in ex]})
    syn = conn.execute("SELECT w.id, w.word FROM synonyms s JOIN words w ON w.id=s.synonym_word_id WHERE s.word_id=?", (word_id,)).fetchall()
    ant = conn.execute("SELECT w.id, w.word FROM antonyms a JOIN words w ON w.id=a.antonym_word_id WHERE a.word_id=?", (word_id,)).fetchall()
    rank = conn.execute("SELECT COUNT(*)+1 as r FROM words WHERE frequency > (SELECT frequency FROM words WHERE id=?)", (word_id,)).fetchone()["r"]
    conn.close()
    return {**dict(w), "rank": rank, "meanings": out_meanings, "synonyms": [dict(s) for s in syn], "antonyms": [dict(a) for a in ant]}

@app.post("/api/words/suggest")
def suggest_word(body: SuggestWordIn):
    u = get_or_create_user(body.telegram_id)
    if not body.example1 or not body.example2: raise HTTPException(400, "2 ta misol kiritish majburiy.")
    
    conn = db()
    conn.execute("INSERT INTO words (word, base_level, status, suggested_by) VALUES (?,?, 'pending_admin', ?)", (body.word.strip().lower(), body.level, u["id"]))
    word_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.execute("INSERT INTO meanings (word_id, meaning, translation, translation_ru, cefr_level, synonym_text) VALUES (?,?,?,?,?,?)",
                 (word_id, body.description, body.translation, body.translation_ru, body.level, body.synonym))
    meaning_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example1))
    conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example2))
    conn.commit()
    conn.close()

    if get_setting("auto_ai_check_suggestions") == "1":
        check = call_groq_json('Review word entry. Reply JSON: {"looks_valid": bool, "note": str}', f"Word: {body.word}\nTr: {body.translation}")
        if check.get("looks_valid"):
            reward = int(get_setting("suggestion_reward_amount", "50"))
            conn = db()
            conn.execute("UPDATE words SET status='active' WHERE id=?", (word_id,))
            conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (reward, u["id"]))
            conn.commit(); conn.close()
            telegram_send_message(u["telegram_id"], f"✅ So'zingiz qabul qilindi! +{reward} kredit berildi.")
            main_ch = get_setting("main_channel")
            if main_ch:
                bot_uname = get_setting("webapp_domain").split("//")[-1] if get_setting("webapp_domain") else "UnlockWordBot"
                msg_text = f"{get_setting('bot_message_emoji', '✨')} Yangi so'z qo'shildi: <tg-spoiler>{body.word}</tg-spoiler>\nDaraja: {body.level}\nTaklif qildi: {u['nickname'] or u['name']}"
                markup = {"inline_keyboard": [
                    [{"text": "💾 So'zni saqlash", "url": f"https://t.me/{bot_uname}?startapp=save_{word_id}"},
                     {"text": "🔓 Practice qilish", "url": f"https://t.me/{bot_uname}?startapp=practice_{word_id}"}],
                    [{"text": "🆕 O'z so'zini taklif qilish", "url": f"https://t.me/{bot_uname}?startapp=new"}]
                ]}
                telegram_send_message(main_ch, msg_text, markup)
            return {"status": "ok", "message": "Avtomatik qabul qilindi!"}

    telegram_send_message(ADMIN_ID, f"🆕 Taklif: {body.word}\nTarjima: {body.translation}\n1: {body.example1}\n2: {body.example2}\nJavob: /approve {word_id} yoki /reject {word_id}")
    return {"status": "ok", "message": "Admin tekshiruvi uchun yuborildi."}

@app.get("/api/words/mysuggestions/{telegram_id}")
def my_suggestions(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); rows = conn.execute("SELECT id, word, base_level, status FROM words WHERE suggested_by=? ORDER BY id DESC", (u["id"],)).fetchall(); conn.close()
    return [dict(r) for r in rows]

@app.post("/api/words/save")
def save_word(body: SaveWordIn):
    u = get_or_create_user(body.telegram_id)
    conn = db(); conn.execute("INSERT OR IGNORE INTO saved_words (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], body.word_id, now_iso())); conn.commit(); conn.close()
    return {"status": "ok"}
@app.post("/api/words/unsave")
def unsave_word(body: SaveWordIn):
    u = get_or_create_user(body.telegram_id)
    conn = db(); conn.execute("DELETE FROM saved_words WHERE user_id=? AND word_id=?", (u["id"], body.word_id)); conn.commit(); conn.close()
    return {"status": "ok"}
@app.get("/api/words/saved/{telegram_id}")
def list_saved_words(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); rows = conn.execute("SELECT w.id, w.word, w.base_level FROM saved_words sw JOIN words w ON w.id=sw.word_id WHERE sw.user_id=? ORDER BY sw.id DESC", (u["id"],)).fetchall(); conn.close()
    return [dict(r) for r in rows]

@app.post("/api/batch/start")
def start_batch(body: StartBatchIn):
    u = get_or_create_user(body.telegram_id)
    if u["credits"] < body.count: raise HTTPException(402, "Kredit yetarli emas.")
    conn = db()
    words = conn.execute(f"SELECT id FROM words WHERE base_level IN ({','.join('?' for _ in body.levels)}) AND status='active' ORDER BY RANDOM() LIMIT ?", tuple(body.levels) + (body.count,)).fetchall()
    if not words: conn.close(); raise HTTPException(404, "So'zlar topilmadi.")
    word_ids = [w["id"] for w in words]
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (len(word_ids), u["id"]))
    conn.execute("INSERT INTO batches (user_id, levels, total_count, created_at) VALUES (?,?,?,?)", (u["id"], ",".join(body.levels), len(word_ids), now_iso()))
    batch_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    for wid in word_ids: conn.execute("INSERT INTO batch_words (batch_id, word_id, status) VALUES (?,?, 'new')", (batch_id, wid))
    conn.commit(); conn.close()
    return {"batch_id": batch_id, "levels": body.levels, "count": len(word_ids)}

@app.post("/api/batch/start-from-saved")
def start_batch_from_saved(body: StartBatchFromSavedIn):
    u = get_or_create_user(body.telegram_id)
    count = len(body.word_ids)
    if u["credits"] < count: raise HTTPException(402, "Kredit yetarli emas.")
    conn = db()
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (count, u["id"]))
    conn.execute("INSERT INTO batches (user_id, levels, total_count, created_at) VALUES (?,?,?,?)", (u["id"], "saqlangan", count, now_iso()))
    batch_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    for wid in body.word_ids: conn.execute("INSERT INTO batch_words (batch_id, word_id, status) VALUES (?,?, 'new')", (batch_id, wid))
    conn.commit(); conn.close()
    return {"batch_id": batch_id, "count": count}

@app.get("/api/batch/current/{telegram_id}")
def current_batch(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    b = conn.execute("SELECT * FROM batches WHERE user_id=? AND status IN ('active','learning_done','review_ready') ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    if not b: conn.close(); return None
    bwords = conn.execute("SELECT bw.*, w.word, w.base_level FROM batch_words bw JOIN words w ON w.id=bw.word_id WHERE bw.batch_id=?", (b["id"],)).fetchall()
    conn.close()
    return {**dict(b), "words": [dict(x) for x in bwords]}

@app.post("/api/batch/finish-learning/{batch_id}")
def finish_learning(batch_id: int):
    conn = db(); conn.execute("UPDATE batches SET status='learning_done' WHERE id=?", (batch_id,)); conn.commit(); conn.close()
    return {"status": "ok"}

@app.post("/api/batch/export-bot/{batch_id}")
def export_batch_bot(batch_id: int, telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    words = conn.execute("SELECT w.word, w.base_level FROM batch_words bw JOIN words w ON w.id=bw.word_id WHERE bw.batch_id=?", (batch_id,)).fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Word", "Level"])
    for w in words: writer.writerow([w["word"], w["base_level"]])
    
    csv_bytes = output.getvalue().encode("utf-8-sig")
    requests.post(f"{TG_API}/sendDocument", data={"chat_id": u["telegram_id"]}, files={"document": (f"words_batch_{batch_id}.csv", csv_bytes)})
    return {"status": "ok"}

@app.post("/api/sentence/check")
def check_sentence(body: CheckSentenceIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    level = conn.execute("SELECT base_level FROM words WHERE id=?", (body.word_id,)).fetchone()
    conn.close()
    limits = get_sentence_limits(level["base_level"] if level else "A1")
    wc = word_count(body.sentence)
    if wc < limits["min"]: return {"stage": "validation", "error": f"Kamida {limits['min']} ta so'z yozing."}
    if wc > limits["max"]: return {"stage": "validation", "error": f"Ko'pi bilan {limits['max']} ta so'z yozing."}
    
    result = call_groq_grammar_check(body.word, body.sentence, effective_lang(u))
    is_correct = bool(result.get("correct")) and bool(result.get("used_target_word"))
    conn = db()
    if body.batch_id: conn.execute("UPDATE batch_words SET status=? WHERE batch_id=? AND word_id=?", ("correct" if is_correct else "wrong", body.batch_id, body.word_id))
    conn.commit(); conn.close()
    return {"stage": "ai", "result": result, "is_correct": is_correct}

@app.post("/api/review/schedule")
def schedule_review(body: ScheduleReviewIn):
    mins = body.custom_minutes if body.delay_key == "custom" else REVIEW_DELAYS.get(body.delay_key, 1440)
    next_at = (datetime.utcnow() + timedelta(minutes=mins)).isoformat()
    conn = db(); conn.execute("UPDATE batches SET status='review_wait', next_review_at=? WHERE id=?", (next_at, body.batch_id)); conn.commit(); conn.close()
    return {"next_review_at": next_at}

@app.get("/api/review/status/{telegram_id}")
def review_status(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db(); b = conn.execute("SELECT * FROM batches WHERE user_id=? AND status IN ('review_wait','review_ready') ORDER BY next_review_at ASC LIMIT 1", (u["id"],)).fetchone(); conn.close()
    return dict(b) if b else None

@app.post("/api/review/submit-score")
def submit_score(batch_id: int, correct: int, total: int):
    accuracy = correct / total if total else 0
    conn = db()
    if accuracy >= 0.85: conn.execute("UPDATE batches SET status='completed', correct_count=? WHERE id=?", (correct, batch_id))
    else:
        conn.execute("UPDATE batch_words SET status='new' WHERE batch_id=?", (batch_id,))
        conn.execute("UPDATE batches SET status='active', correct_count=? WHERE id=?", (correct, batch_id))
    conn.commit(); conn.close()
    return {"accuracy": round(accuracy * 100, 1), "passed": accuracy >= 0.85}

@app.post("/api/profile/update")
def update_profile(body: ProfileUpdateIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    if body.nickname is not None: conn.execute("UPDATE users SET nickname=? WHERE id=?", (body.nickname, u["id"]))
    if body.avatar_url is not None: conn.execute("UPDATE users SET avatar_url=? WHERE id=?", (body.avatar_url, u["id"]))
    if body.lang is not None: conn.execute("UPDATE users SET lang=? WHERE id=?", (body.lang, u["id"]))
    conn.commit(); conn.close()
    return {"status": "ok"}

@app.get("/api/progress/{telegram_id}")
def progress(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    correct = conn.execute("SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status='correct'", (u["id"],)).fetchone()["c"]
    practiced = conn.execute("SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status IN ('correct','wrong')", (u["id"],)).fetchone()["c"]
    r = conn.execute("SELECT COUNT(*) c FROM (SELECT u2.id, COUNT(bw.id) score FROM users u2 JOIN batches b ON b.user_id=u2.id JOIN batch_words bw ON bw.batch_id=b.id AND bw.status='correct' GROUP BY u2.id HAVING score > ?)", (correct,)).fetchone()
    conn.close()
    return {"display_id": seq_id(u["id"]), "nickname": u["nickname"], "avatar_url": u["avatar_url"], "level": u["current_level"], "credits": u["credits"], "active_words": correct, "words_practiced": practiced, "accuracy": round((correct/practiced)*100,1) if practiced else 0, "rank_position": (r["c"] + 1) if r else 1}

@app.get("/api/ranking")
def get_ranking():
    conn = db(); rows = conn.execute("SELECT u.id as uid, u.nickname, u.avatar_url, COUNT(bw.id) as score FROM users u JOIN batches b ON b.user_id=u.id JOIN batch_words bw ON bw.batch_id=b.id WHERE bw.status='correct' GROUP BY u.id ORDER BY score DESC LIMIT 50").fetchall(); conn.close()
    return [{**dict(r), "display_id": seq_id(r["uid"])} for r in rows]

def generate_unique_amount(base: int) -> int:
    conn = db(); used = {int(r["expected_amount"]) for r in conn.execute("SELECT expected_amount FROM pending_payments WHERE status IN ('awaiting_amount','awaiting_confirm')").fetchall() if r["expected_amount"]}; conn.close()
    amt = base
    while amt in used: amt += 1
    return amt

@app.post("/api/payment/generate")
def generate_payment(telegram_id: int, credits: int = 1000):
    u = get_or_create_user(telegram_id)
    amt = generate_unique_amount(round(credits * (int(get_setting("price_per_1000", "2500")) / 1000)))
    conn = db()
    conn.execute("UPDATE pending_payments SET status='expired' WHERE user_id=? AND status IN ('awaiting_amount','awaiting_confirm')", (u["id"],))
    conn.execute("INSERT INTO pending_payments (user_id, amount, expected_amount, credits_to_add, status, created_at) VALUES (?,?,?,?,?,?)", (u["id"], amt, amt, credits, "awaiting_amount", now_iso()))
    pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit(); conn.close()
    return {"payment_id": pid, "expected_amount": amt, "credits": credits, "valid_for_mins": 5, "card": get_setting("payment_card")}

@app.get("/api/payment/status/{payment_id}")
def payment_status(payment_id: int):
    conn = db(); p = conn.execute("SELECT status, expected_amount, credits_to_add FROM pending_payments WHERE id=?", (payment_id,)).fetchone(); conn.close()
    if not p: raise HTTPException(404, "Topilmadi")
    return dict(p)

@app.post("/api/payment/mark-paid/{payment_id}")
def mark_paid(payment_id: int):
    conn = db()
    p = conn.execute("SELECT * FROM pending_payments WHERE id=?", (payment_id,)).fetchone()
    if p:
        conn.execute("UPDATE pending_payments SET status='awaiting_confirm' WHERE id=?", (payment_id,))
        conn.commit()
        telegram_send_message(ADMIN_ID, f"💳 To'lov tasdiqlash!\nSumma: {p['expected_amount']}\n/pay_approve {payment_id} yoki /pay_reject {payment_id}")
    conn.close()
    return {"status": "ok"}

# ----------------- ADMIN & TELEGRAM BOT -----------------

def get_admin_keyboard():
    return {
        "keyboard": [
            [{"text": "📢 Kanallar"}, {"text": "👥 Foyd.lar"}],
            [{"text": "💳 To'lovlar"}, {"text": "🆕 So'z taklif."}],
            [{"text": "⚙️ Sozlamalar"}, {"text": "🗑 So'z o'chirish"}]
        ],
        "resize_keyboard": True
    }

def get_settings_keyboard():
    return {
        "keyboard": [
            [{"text": "🌐 Webapp domen"}, {"text": "🤖 AI kalit"}],
            [{"text": "📚 Asosiy kanal"}, {"text": "🆘 Yordam admin"}],
            [{"text": "🖼 Rasmlar (Nav)"}, {"text": "📄 Fayl narxlari"}],
            [{"text": "⬅️ Orqaga"}]
        ],
        "resize_keyboard": True
    }

def handle_admin_text(chat_id, text):
    if text == "⬅️ Orqaga":
        admin_state.pop(chat_id, None)
        telegram_send_message(chat_id, "Asosiy menyu:", get_admin_keyboard())
        return

    if text == "⚙️ Sozlamalar":
        telegram_send_message(chat_id, "Sozlamalar bo'limi:", get_settings_keyboard())
        return

    # Kiritishlarni ushlash
    if chat_id in admin_state:
        action = admin_state[chat_id].get("action")
        if action == "set_webapp": set_setting("webapp_domain", text); telegram_send_message(chat_id, "Saqlandi.", get_settings_keyboard()); admin_state.pop(chat_id, None); return
        if action == "set_groq": set_setting("groq_api_key", text); telegram_send_message(chat_id, "Saqlandi.", get_settings_keyboard()); admin_state.pop(chat_id, None); return
        if action == "set_main_ch": set_setting("main_channel", text); telegram_send_message(chat_id, "Saqlandi.", get_settings_keyboard()); admin_state.pop(chat_id, None); return
        if action == "set_help": set_setting("help_admin", text); telegram_send_message(chat_id, "Saqlandi.", get_settings_keyboard()); admin_state.pop(chat_id, None); return
        if action == "del_word":
            conn = db()
            if text.isdigit(): conn.execute("DELETE FROM words WHERE id=?", (int(text),))
            else: conn.execute("DELETE FROM words WHERE word=?", (text.lower(),))
            conn.commit(); conn.close()
            telegram_send_message(chat_id, "So'z o'chirildi.", get_admin_keyboard()); admin_state.pop(chat_id, None); return
        if action == "reply_ticket":
            tid = admin_state[chat_id]["ticket_id"]
            conn = db(); conn.execute("UPDATE tickets SET admin_reply=?, status='answered' WHERE id=?", (text, tid)); u=conn.execute("SELECT telegram_id FROM users JOIN tickets ON tickets.user_id=users.id WHERE tickets.id=?",(tid,)).fetchone(); conn.commit(); conn.close()
            if u: telegram_send_message(u["telegram_id"], f"📩 Admin javobi:\n\n{text}")
            telegram_send_message(chat_id, "Javob yuborildi.", get_admin_keyboard()); admin_state.pop(chat_id, None); return

    if text == "🗑 So'z o'chirish": admin_state[chat_id] = {"action": "del_word"}; telegram_send_message(chat_id, "O'chirish uchun ID (#123) yoki so'zning o'zini yozing:")
    elif text == "🌐 Webapp domen": admin_state[chat_id] = {"action": "set_webapp"}; telegram_send_message(chat_id, "Webapp domenni yozing (https://...):")
    elif text == "🤖 AI kalit": admin_state[chat_id] = {"action": "set_groq"}; telegram_send_message(chat_id, "Groq API kalitni yozing:")
    elif text == "📚 Asosiy kanal": admin_state[chat_id] = {"action": "set_main_ch"}; telegram_send_message(chat_id, "Asosiy kanalni yozing (@kanal):")
    elif text == "🆘 Yordam admin": admin_state[chat_id] = {"action": "set_help"}; telegram_send_message(chat_id, "Yordamchi adminni yozing (@admin):")
    elif text == "🖼 Rasmlar (Nav)":
        admin_state[chat_id] = {"action": "wait_nav_photo"}
        telegram_send_message(chat_id, "Home tugmasi uchun rasmni yuboring:")

def auto_confirm_payment(amount: int):
    conn = db()
    p = conn.execute("SELECT * FROM pending_payments WHERE expected_amount=? AND status IN ('awaiting_amount','awaiting_confirm')", (amount,)).fetchone()
    if p:
        conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (p["credits_to_add"], p["user_id"]))
        conn.execute("UPDATE pending_payments SET status='approved' WHERE id=?", (p["id"],))
        conn.commit()
        u = conn.execute("SELECT telegram_id FROM users WHERE id=?", (p["user_id"],)).fetchone()
        if u: telegram_send_message(u["telegram_id"], f"✅ To'lovingiz tasdiqlandi! +{p['credits_to_add']} kredit.")
    conn.close()

def telegram_polling_loop():
    offset = 0
    while True:
        try:
            data = requests.get(f"{TG_API}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=35).json()
            if not data.get("ok"): time.sleep(3); continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")

                    if chat_id == ADMIN_ID:
                        if text == "/start" or text == "/admin": telegram_send_message(chat_id, "Admin Panel:", get_admin_keyboard()); continue
                        if text.startswith("/reply "):
                            parts = text.split(" ", 2)
                            if len(parts)==3: admin_state[chat_id] = {"action": "reply_ticket", "ticket_id": parts[1]}; handle_admin_text(chat_id, parts[2]); continue
                        if text.startswith("/approve "):
                            wid = text.split()[1]
                            conn = db(); conn.execute("UPDATE words SET status='active' WHERE id=?", (wid,)); conn.commit(); conn.close()
                            telegram_send_message(chat_id, f"✅ So'z #{wid} qabul qilindi."); continue
                        if text.startswith("/pay_approve "):
                            pid = text.split()[1]
                            conn = db(); p = conn.execute("SELECT * FROM pending_payments WHERE id=?",(pid,)).fetchone()
                            if p:
                                conn.execute("UPDATE users SET credits=credits+? WHERE id=?",(p["credits_to_add"], p["user_id"]))
                                conn.execute("UPDATE pending_payments SET status='approved' WHERE id=?",(pid,))
                                conn.commit()
                                u=conn.execute("SELECT telegram_id FROM users WHERE id=?",(p["user_id"],)).fetchone()
                                if u: telegram_send_message(u["telegram_id"], f"✅ To'lovingiz tasdiqlandi! +{p['credits_to_add']} kredit.")
                            conn.close()
                            telegram_send_message(chat_id, "Tasdiqlandi."); continue

                        if not admin_state.get(chat_id):
                            low = text.lower()
                            if ("uzs" in low or "+" in text) and any(ch.isdigit() for ch in text):
                                amt = int("".join(c for c in text.split(",")[0] if c.isdigit()) or 0)
                                if amt > 0: auto_confirm_payment(amt); telegram_send_message(chat_id, f"✅ {amt} so'm tasdiqlandi."); continue
                        
                        if "photo" in msg and admin_state.get(chat_id, {}).get("action") == "wait_nav_photo":
                            url = telegram_get_file_url(msg["photo"][-1]["file_id"])
                            set_setting("icon_home", url)
                            telegram_send_message(chat_id, "Rasm saqlandi.", get_settings_keyboard())
                            admin_state.pop(chat_id, None)
                            continue

                        handle_admin_text(chat_id, text)
                        continue

                    # Oddiy user start
                    if text.startswith("/start"):
                        parts = text.split()
                        app_url = get_setting("webapp_domain")
                        if len(parts) > 1 and parts[1].startswith("save_"):
                            # Deep link orqali keldi
                            word_id = int(parts[1].split("_")[1])
                            u = get_or_create_user(chat_id)
                            conn = db(); conn.execute("INSERT OR IGNORE INTO saved_words (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], word_id, now_iso())); conn.commit(); conn.close()
                            telegram_send_message(chat_id, "✅ So'z saqlandi!", {"inline_keyboard": [[{"text": "🚀 Ilovaga kirish", "web_app": {"url": app_url}}]]})
                        else:
                            telegram_send_message(chat_id, get_setting("start_message_uz"), {"inline_keyboard": [[{"text": "🚀 UnlockWord", "web_app": {"url": app_url}}]]})

        except Exception:
            time.sleep(3)

threading.Thread(target=telegram_polling_loop, daemon=True).start()

@app.get("/")
@app.get("/index.html")
def serve_webapp():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
