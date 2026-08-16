"""
============================================================
 UnlockWord — Backend v4 (FastAPI + SQLite)
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
from fastapi.responses import FileResponse, StreamingResponse
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
    "help_admin": "", "auto_ai_check_suggestions": "0", "enable_suggestion_reward": "1",
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

def seq_id(user_id: int) -> str:
    return f"A{user_id:03d}"

def now_iso():
    return datetime.utcnow().isoformat()

def get_or_create_user(telegram_id: int, name: str = "") -> sqlite3.Row:
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    if u:
        if u["is_banned"]:
            conn.close()
            raise HTTPException(403, "Sizning hisobingiz bloklangan.")
        conn.close()
        return u
    conn.execute("INSERT INTO users (telegram_id, name, nickname, credits, lang, created_at) VALUES (?,?,?,?,?,?)",
                 (telegram_id, name, name, 0, "", now_iso()))
    conn.commit()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return u

def require_admin(telegram_id: int):
    if telegram_id != ADMIN_ID:
        raise HTTPException(403, "Faqat admin uchun.")

def call_groq_json(system_prompt: str, user_prompt: str) -> dict:
    api_key = get_setting("groq_api_key")
    if not api_key: return {}
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": get_setting("groq_model", "llama-3.3-70b-versatile"), "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.2, "response_format": {"type": "json_object"}},
        timeout=30,
    )
    if resp.ok: return json.loads(resp.json()["choices"][0]["message"]["content"])
    return {}

def telegram_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{TG_API}/sendMessage", data=payload, timeout=20)
    except: pass

def telegram_get_file_url(file_id):
    try:
        r = requests.get(f"{TG_API}/getFile", params={"file_id": file_id}, timeout=15).json()
        path = r["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOOTSTRAP['TELEGRAM_BOT_TOKEN']}/{path}"
    except: return None

class LoginIn(BaseModel): telegram_id: int; name: str = ""
class SuggestWordIn(BaseModel):
    telegram_id: int; word: str; translation: str; translation_ru: str = ""; description: str = ""; synonym: str = ""; level: str = "A1"
    example1: str = ""; example2: str = ""
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
    d = dict(u)
    d["display_id"] = seq_id(u["id"])
    return d

@app.get("/api/profile/{telegram_id}")
def get_profile(telegram_id: int):
    u = get_or_create_user(telegram_id)
    d = dict(u)
    d["display_id"] = seq_id(u["id"])
    return d

@app.post("/api/profile/update")
def update_profile(body: ProfileUpdateIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    if body.nickname is not None: conn.execute("UPDATE users SET nickname=? WHERE id=?", (body.nickname, u["id"]))
    if body.avatar_url is not None: conn.execute("UPDATE users SET avatar_url=? WHERE id=?", (body.avatar_url, u["id"]))
    if body.lang is not None: conn.execute("UPDATE users SET lang=? WHERE id=?", (body.lang, u["id"]))
    if body.secondary_lang is not None: conn.execute("UPDATE users SET secondary_lang=? WHERE id=?", (body.secondary_lang, u["id"]))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/progress/{telegram_id}")
def progress(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    correct = conn.execute("SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status='correct'", (u["id"],)).fetchone()["c"]
    practiced = conn.execute("SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status IN ('correct','wrong')", (u["id"],)).fetchone()["c"]
    saved_count = conn.execute("SELECT COUNT(*) c FROM saved_words WHERE user_id=?", (u["id"],)).fetchone()["c"]
    suggested_count = conn.execute("SELECT COUNT(*) c FROM words WHERE suggested_by=?", (u["id"],)).fetchone()["c"]
    rank_row = conn.execute("SELECT COUNT(*) c FROM (SELECT u2.id, COUNT(bw.id) score FROM users u2 JOIN batches b ON b.user_id=u2.id JOIN batch_words bw ON bw.batch_id=b.id AND bw.status='correct' GROUP BY u2.id HAVING score > ?)", (correct,)).fetchone()
    rank_position = (rank_row["c"] + 1) if rank_row else 1
    conn.close()
    accuracy = round((correct / practiced) * 100, 1) if practiced else 0
    return {
        "display_id": seq_id(u["id"]), "nickname": u["nickname"], "avatar_url": u["avatar_url"], "level": u["current_level"],
        "credits": u["credits"], "active_words": correct, "words_practiced": practiced, "accuracy": accuracy,
        "saved_count": saved_count, "suggested_count": suggested_count, "rank_position": rank_position,
    }

@app.get("/api/ranking")
def get_ranking():
    conn = db()
    rows = conn.execute("SELECT u.id as uid, u.nickname, u.avatar_url, COUNT(bw.id) as score FROM users u JOIN batches b ON b.user_id=u.id JOIN batch_words bw ON bw.batch_id=b.id WHERE bw.status='correct' GROUP BY u.id ORDER BY score DESC LIMIT 50").fetchall()
    conn.close()
    return [{**dict(r), "display_id": seq_id(r["uid"])} for r in rows]

@app.get("/api/dictionary/history/{telegram_id}")
def dictionary_history(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT w.*, m.translation, m.translation_ru, m.cefr_level FROM search_history sh JOIN words w ON w.id=sh.word_id LEFT JOIN meanings m ON m.word_id=w.id WHERE sh.user_id=? GROUP BY w.id ORDER BY sh.id DESC LIMIT 10", (u["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
        translation = m["translation_ru"] if (lang == "ru" and m["translation_ru"]) else m["translation"]
        out_meanings.append({**dict(m), "translation_shown": translation, "examples": [e["sentence"] for e in ex]})
    syn = conn.execute("SELECT w.id, w.word FROM synonyms s JOIN words w ON w.id=s.synonym_word_id WHERE s.word_id=?", (word_id,)).fetchall()
    ant = conn.execute("SELECT w.id, w.word FROM antonyms a JOIN words w ON w.id=a.antonym_word_id WHERE a.word_id=?", (word_id,)).fetchall()
    rank = conn.execute("SELECT COUNT(*)+1 as r FROM words WHERE frequency > (SELECT frequency FROM words WHERE id=?)", (word_id,)).fetchone()["r"]
    conn.close()
    return {**dict(w), "rank": rank, "meanings": out_meanings, "synonyms": [dict(s) for s in syn], "antonyms": [dict(a) for a in ant]}

@app.post("/api/words/suggest")
def suggest_word(body: SuggestWordIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    conn.execute("INSERT INTO words (word, base_level, status, suggested_by) VALUES (?,?, 'pending_admin', ?)", (body.word.strip().lower(), body.level, u["id"]))
    word_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.execute("INSERT INTO meanings (word_id, meaning, translation, translation_ru, cefr_level, synonym_text) VALUES (?,?,?,?,?,?)",
                 (word_id, body.description, body.translation, body.translation_ru, body.level, body.synonym))
    meaning_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    if body.example1: conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example1))
    if body.example2: conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example2))
    conn.commit()
    conn.close()

    ai_note = ""
    is_auto_accepted = False
    if get_setting("auto_ai_check_suggestions") == "1":
        try:
            check = call_groq_json("Review vocabulary entry. Reply JSON: {"looks_valid": bool, "note": str}", f"Word: {body.word}\nTr: {body.translation}\nDesc: {body.description}")
            if check.get("looks_valid"):
                is_auto_accepted = True
            ai_note = f"\n\n🤖 AI: {check.get('note', '')}"
        except: pass

    reward_amount = int(get_setting("suggestion_reward_amount", "50"))
    give_reward = get_setting("enable_suggestion_reward", "1") == "1"

    if is_auto_accepted:
        conn = db()
        conn.execute("UPDATE words SET status='active' WHERE id=?", (word_id,))
        if give_reward: conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (reward_amount, u["id"]))
        conn.commit()
        conn.close()
        
        msg = f"✅ Sizning "{body.word}" so'zingiz qabul qilindi!"
        if give_reward: msg += f" Rahmat sifatida {reward_amount} kredit taqdim etildi."
        telegram_send_message(u["telegram_id"], msg)
        
        main_ch = get_setting("main_channel")
        if main_ch:
            emoji = get_setting("bot_message_emoji", "✨")
            ch_msg = f"{emoji} Yangi so'z qo'shildi!\n\nSo'z: <tg-spoiler>{body.word}</tg-spoiler>\nDaraja: {body.level}\n\nTaklif qildi: {u['nickname'] or u['name']}"
            telegram_send_message(main_ch, ch_msg)
        return {"status": "ok", "message": "So'zingiz avtomatik qabul qilindi va lug'atga qo'shildi!"}
    
    telegram_send_message(ADMIN_ID, f"🆕 Yangi so'z taklifi (#{word_id}):\n\nSo'z: {body.word}\nTarjima: {body.translation}\nLevel: {body.level}\nKimdan: {u['nickname']} ({seq_id(u['id'])}){ai_note}")
    return {"status": "ok", "message": "So'zingiz admin ko'rib chiqishi uchun yuborildi."}

@app.get("/api/words/mysuggestions/{telegram_id}")
def my_suggestions(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT id, word, base_level, status FROM words WHERE suggested_by=? ORDER BY id DESC", (u["id"],)).fetchall()
    conn.close()
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
    conn = db()
    rows = conn.execute("SELECT w.id, w.word, w.base_level FROM saved_words sw JOIN words w ON w.id=sw.word_id WHERE sw.user_id=? ORDER BY sw.id DESC", (u["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
    else: raise HTTPException(400, "Faqat PDF, DOCX yoki TXT fayllar qabul qilinadi.")
    words = list(set(re.findall(r"[a-zA-Z]{2,}", text.lower())))
    if not words: raise HTTPException(400, "Faylda inglizcha so'zlar topilmadi.")
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
    if not job or job["status"] != "pending": conn.close(); raise HTTPException(400, "Topilmadi yoki allaqachon qayta ishlangan.")
    if u["credits"] < job["price"]: conn.close(); raise HTTPException(402, "Kredit yetarli emas.")
    words = json.loads(job["payload"] or "[]")
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
    return {"status": "ok", "words_added": added, "words_saved": len(words), "credits_spent": job["price"]}

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

@app.get("/api/batch/current/{telegram_id}")
def current_batch(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    b = conn.execute("SELECT * FROM batches WHERE user_id=? AND status IN ('active','learning_done','review_ready') ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    if not b: conn.close(); return None
    bwords = conn.execute("SELECT bw.*, w.word, w.base_level FROM batch_words bw JOIN words w ON w.id=bw.word_id WHERE bw.batch_id=?", (b["id"],)).fetchall()
    conn.close()
    return {**dict(b), "words": [dict(x) for x in bwords]}

@app.post("/api/sentence/check")
def check_sentence(body: CheckSentenceIn):
    u = get_or_create_user(body.telegram_id)
    lang = "uz" if u["lang"]=="uz" else ("ru" if u["lang"]=="ru" else u["secondary_lang"] or "uz")
    resp = call_groq_json(f"You check English sentences for a vocabulary app. Target word: '{body.word}'. Student sentence: '{body.sentence}'. Write explanation in {'Uzbek' if lang=='uz' else 'Russian'}. Respond JSON: {{"correct":bool, "used_target_word":bool, "mistakes":[{{"original":str,"correction":str,"explanation":str}}], "corrected_sentence":str}}", "")
    is_correct = bool(resp.get("correct") and resp.get("used_target_word"))
    conn = db()
    if body.batch_id: conn.execute("UPDATE batch_words SET status=? WHERE batch_id=? AND word_id=?", ("correct" if is_correct else "wrong", body.batch_id, body.word_id))
    conn.commit(); conn.close()
    return {"stage": "ai", "result": resp, "is_correct": is_correct}

@app.post("/api/review/schedule")
def schedule_review(body: ScheduleReviewIn):
    mins = body.custom_minutes if body.delay_key == "custom" else {"30m": 30, "1h": 60, "4h": 240, "12h": 720, "24h": 1440, "48h": 2880, "3d": 4320, "7d": 10080}.get(body.delay_key)
    next_at = (datetime.utcnow() + timedelta(minutes=mins)).isoformat()
    conn = db(); conn.execute("UPDATE batches SET status='review_wait', next_review_at=? WHERE id=?", (next_at, body.batch_id)); conn.commit(); conn.close()
    return {"next_review_at": next_at}

@app.get("/api/review/status/{telegram_id}")
def review_status(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    b = conn.execute("SELECT * FROM batches WHERE user_id=? AND status IN ('review_wait','review_ready') ORDER BY next_review_at ASC LIMIT 1", (u["id"],)).fetchone()
    conn.close()
    return dict(b) if b else None

@app.post("/api/payment/generate")
def generate_payment(telegram_id: int, credits: int = 1000):
    u = get_or_create_user(telegram_id)
    price = round(credits * (int(get_setting("price_per_1000", "2500")) / 1000))
    amount = price
    conn = db()
    while conn.execute("SELECT id FROM pending_payments WHERE expected_amount=? AND status='awaiting_amount'", (amount,)).fetchone(): amount += 1
    conn.execute("INSERT INTO pending_payments (user_id, amount, expected_amount, credits_to_add, status, created_at) VALUES (?,?,?,?,?,?)", (u["id"], price, amount, credits, "awaiting_amount", now_iso()))
    pid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit(); conn.close()
    return {"payment_id": pid, "expected_amount": amount, "credits": credits, "valid_for_mins": 5, "card": get_setting("payment_card")}

@app.get("/api/payment/status/{payment_id}")
def payment_status(payment_id: int):
    conn = db(); p = conn.execute("SELECT status, expected_amount, credits_to_add FROM pending_payments WHERE id=?", (payment_id,)).fetchone(); conn.close()
    if not p: raise HTTPException(404, "Not found")
    return dict(p)

@app.post("/api/payment/mark-paid/{payment_id}")
def mark_paid(payment_id: int):
    conn = db(); conn.execute("UPDATE pending_payments SET status='awaiting_confirm' WHERE id=?", (payment_id,)); conn.commit(); conn.close()
    telegram_send_message(ADMIN_ID, f"💳 To'lov: #{payment_id} tasdiqlang")
    return {"status": "ok"}

@app.get("/api/payment/history/{telegram_id}")
def payment_history(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT * FROM pending_payments WHERE user_id=? ORDER BY id DESC LIMIT 20", (u["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def telegram_polling_loop():
    offset = 0
    while True:
        try:
            data = requests.get(f"{TG_API}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=35).json()
            if not data.get("ok"): time.sleep(3); continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    if text == "/start": telegram_send_message(chat_id, "Salom! Bot ishlayabdi.")
        except: time.sleep(3)

threading.Thread(target=telegram_polling_loop, daemon=True).start()

@app.get("/")
@app.get("/index.html")
def serve_webapp():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
