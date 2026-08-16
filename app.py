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
    "webapp_domain": "", "backend_domain": "",
    "groq_api_key": "", "groq_model": "llama-3.3-70b-versatile",
    "price_per_1000": "2500", "min_credits_purchase": "100", "main_channel": "", "logo_url": "",
    "icon_home": "", "icon_search": "", "icon_practice": "", "icon_new": "", "icon_profile": "",
    "start_message_uz": "UnlockWord'ni ochish uchun tugmani bosing:",
    "start_message_ru": "Нажмите кнопку, чтобы открыть UnlockWord:",
    "start_message_en": "Tap the button to open UnlockWord:",
    "payment_card": "", "bot_message_emoji": "✨",
    "sentence_limits": json.dumps({lvl: {"min": 3, "max": 15} for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]}),
    "bg_color": "", "help_admin": "",
    "auto_ai_check_suggestions": "0",
    "enable_suggestion_reward": "1",
    "suggestion_reward_amount": "50",
    "referral_bonus": "50",
    "file_parse_price": "1", "file_word_price": "1",
}

def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL, pronunciation TEXT, base_level TEXT, frequency INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active', suggested_by INTEGER
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
    try:
        c.execute("ALTER TABLE users ADD COLUMN seen_intro INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
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
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

def get_sentence_limits(level):
    try:
        data = json.loads(get_setting("sentence_limits"))
        return data.get(level, {"min": 3, "max": 15})
    except Exception:
        return {"min": 3, "max": 15}

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
    conn.execute(
        "INSERT INTO users (telegram_id, name, nickname, credits, lang, created_at) VALUES (?,?,?,?,?,?)",
        (telegram_id, name, name, 0, "", now_iso()),
    )
    conn.commit()
    u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return u

def require_admin(telegram_id: int):
    if telegram_id != ADMIN_ID:
        raise HTTPException(403, "Faqat admin uchun.")

def word_count(sentence: str) -> int:
    return len([w for w in sentence.strip().split() if w])

def call_groq_json(system_prompt: str, user_prompt: str) -> dict:
    api_key = get_setting("groq_api_key")
    if not api_key:
        raise HTTPException(500, "AI kaliti sozlanmagan.")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": get_setting("groq_model", "llama-3.3-70b-versatile"),
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": 0.2, "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])

LANG_NAMES = {"uz": "Uzbek", "ru": "Russian", "en": "English"}

def effective_lang(u) -> str:
    lang = u["lang"] if u["lang"] else "uz"
    if lang == "en":
        return u["secondary_lang"] or "uz"
    return lang

def call_groq_grammar_check(target_word: str, sentence: str, explain_lang: str = "uz") -> dict:
    lang_name = LANG_NAMES.get(explain_lang, "Uzbek")
    system_prompt = (
        "You are a strict English grammar checker for a vocabulary app. "
        "You ONLY check grammar correctness, correct usage of the TARGET WORD, "
        "and naturalness of the sentence. Never translate, never write essays. "
        "IMPORTANT: the student may use any grammatical FORM of the target word "
        "(e.g. plural, past tense, gerund). Only set used_target_word=false "
        "if no form of the target word appears at all. "
        f"Write the 'explanation' fields in {lang_name}. "
        "Respond with ONLY valid JSON: "
        '{"correct": bool, "used_target_word": bool, "word_usage_correct": bool, '
        '"mistakes": [{"original": str, "correction": str, "explanation": str}], '
        '"corrected_sentence": str}'
    )
    try:
        data = call_groq_json(system_prompt, f'Target word: "{target_word}"\nStudent sentence: "{sentence}"')
    except Exception as e:
        raise HTTPException(502, f"AI xizmatida xatolik: {e}")
    return data

REVIEW_DELAYS = {"30m": 30, "1h": 60, "4h": 240, "12h": 720, "24h": 1440, "48h": 2880, "3d": 4320, "7d": 10080}

def telegram_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        return requests.post(f"{TG_API}/sendMessage", data=payload, timeout=20).json()
    except Exception:
        return None

def telegram_edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{TG_API}/editMessageText", data=payload, timeout=20)
    except Exception:
        pass

def telegram_answer_callback(callback_id, text=""):
    try:
        requests.post(f"{TG_API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text}, timeout=10)
    except Exception:
        pass

def telegram_get_file_url(file_id):
    try:
        r = requests.get(f"{TG_API}/getFile", params={"file_id": file_id}, timeout=15).json()
        path = r["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOOTSTRAP['TELEGRAM_BOT_TOKEN']}/{path}"
    except Exception:
        return None

def add_notification(user_id, message):
    conn = db()
    conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)", (user_id, message, now_iso()))
    conn.commit()
    conn.close()

def check_user_subscription(telegram_id: int):
    conn = db()
    channels = conn.execute("SELECT * FROM channels WHERE kind IN ('public','private_request')").fetchall()
    conn.close()
    missing = []
    for ch in channels:
        try:
            r = requests.get(f"{TG_API}/getChatMember",
                              params={"chat_id": ch["chat_ref"], "user_id": telegram_id}, timeout=10).json()
            status = r.get("result", {}).get("status")
            if status not in ("member", "administrator", "creator"):
                missing.append(dict(ch))
        except Exception:
            missing.append(dict(ch))
    return len(missing) == 0, missing

def subscription_keyboard(missing_channels, lang="uz"):
    rows = []
    for ch in missing_channels:
        url = ch["invite_link"] or (f"https://t.me/{ch['chat_ref'].lstrip('@')}" if str(ch["chat_ref"]).startswith("@") else "")
        rows.append([{"text": f"📢 {ch['title'] or ch['chat_ref']}", "url": url}])
    check_labels = {"uz": "✅ Tekshirish", "ru": "✅ Проверить", "en": "✅ Check"}
    rows.append([{"text": check_labels.get(lang, check_labels["uz"]), "callback_data": "check_sub"}])
    return {"inline_keyboard": rows}

# MODELS
class LoginIn(BaseModel):
    telegram_id: int
    name: str = ""

class StartBatchIn(BaseModel):
    telegram_id: int
    levels: List[str]
    count: int = 20

class StartBatchFromSavedIn(BaseModel):
    telegram_id: int
    word_ids: List[int]

class CheckSentenceIn(BaseModel):
    telegram_id: int
    batch_id: Optional[int] = None
    word_id: int
    word: str
    sentence: str

class ScheduleReviewIn(BaseModel):
    telegram_id: int
    batch_id: int
    delay_key: str
    custom_minutes: Optional[int] = None

class SuggestWordIn(BaseModel):
    telegram_id: int
    word: str
    translation: str
    translation_ru: str = ""
    description: str = ""
    synonym: str = ""
    level: str = "A1"
    example1: str = ""
    example2: str = ""

class ProfileUpdateIn(BaseModel):
    telegram_id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    lang: Optional[str] = None
    secondary_lang: Optional[str] = None

class SaveWordIn(BaseModel):
    telegram_id: int
    word_id: int

class TicketIn(BaseModel):
    telegram_id: int
    message: str

class ReferralIn(BaseModel):
    telegram_id: int
    referrer_display_id: str
    ip: str = ""

class FileConfirmIn(BaseModel):
    telegram_id: int
    job_id: int


@app.get("/api/settings/public")
def public_settings():
    conn = db()
    channels = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    return {
        "logo_url": get_setting("logo_url"),
        "price_per_1000": int(get_setting("price_per_1000", "2500")),
        "min_credits_purchase": int(get_setting("min_credits_purchase", "100")),
        "payment_card": get_setting("payment_card"),
        "bg_color": get_setting("bg_color"),
        "main_channel": get_setting("main_channel"),
        "help_admin": get_setting("help_admin"),
        "channels": [dict(c) for c in channels],
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

@app.post("/api/profile/mark-intro-seen")
def mark_intro_seen(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    conn.execute("UPDATE users SET seen_intro=1 WHERE id=?", (u["id"],))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/subscription/status/{telegram_id}")
def subscription_status(telegram_id: int):
    ok, missing = check_user_subscription(telegram_id)
    return {"ok": ok, "missing": missing}

@app.get("/api/notifications/{telegram_id}")
def get_notifications(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT * FROM notifications WHERE user_id=? AND read=0 ORDER BY id ASC", (u["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int):
    conn = db()
    conn.execute("UPDATE notifications SET read=1 WHERE id=?", (notif_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/ticket/create")
def create_ticket(body: TicketIn):
    u = get_or_create_user(body.telegram_id)
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Xabar bo'sh bo'lishi mumkin emas.")
    conn = db()
    conn.execute("INSERT INTO tickets (user_id, message, status, created_at) VALUES (?,?, 'open', ?)",
                 (u["id"], msg, now_iso()))
    ticket_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit()
    conn.close()
    telegram_send_message(
        ADMIN_ID,
        f"🆘 Yangi murojaat (#{ticket_id})\n\nKimdan: {u['nickname'] or u['name']} ({seq_id(u['id'])})\n"
        f"Telegram ID: {u['telegram_id']}\n\nXabar:\n{msg}\n\n"
        f"Javob berish uchun shu xabarga REPLY qiling.",
    )
    admin_state[ADMIN_ID] = {"action": "await_ticket_reply", "ticket_id": ticket_id}
    return {"status": "ok", "ticket_id": ticket_id, "message": "Murojaatingiz adminga yuborildi."}

@app.get("/api/ticket/list/{telegram_id}")
def list_tickets(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute("SELECT id, message, admin_reply, status, created_at, replied_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 20", (u["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _user_id_from_display(display_id: str):
    try:
        return int(str(display_id).strip().lstrip("Aa").lstrip("0") or "0")
    except Exception:
        return None

@app.post("/api/referral/claim")
def claim_referral(body: ReferralIn):
    u = get_or_create_user(body.telegram_id)
    referrer_uid = _user_id_from_display(body.referrer_display_id)
    if not referrer_uid or referrer_uid == u["id"]:
        raise HTTPException(400, "Noto'g'ri referral havolasi.")
    conn = db()
    referrer = conn.execute("SELECT * FROM users WHERE id=?", (referrer_uid,)).fetchone()
    if not referrer:
        conn.close()
        raise HTTPException(404, "Taklif qiluvchi topilmadi.")
    already = conn.execute("SELECT id FROM referrals WHERE referred_id=?", (u["id"],)).fetchone()
    if already:
        conn.close()
        return {"status": "skip", "message": "Siz allaqachon referral orqali ro'yxatdan o'tgansiz."}
    if body.ip:
        same_ip = conn.execute("SELECT id FROM referrals WHERE referrer_id=? AND referred_ip=?", (referrer_uid, body.ip)).fetchone()
        if same_ip:
            conn.execute("INSERT INTO referrals (referrer_id, referred_id, referred_ip, bonus_credits, status, created_at) VALUES (?,?,?,?, 'fraud_blocked', ?)",
                         (referrer_uid, u["id"], body.ip, 0, now_iso()))
            conn.commit()
            conn.close()
            return {"status": "blocked", "message": "Bir xil tarmoqdan takroriy referral bloklandi."}
    bonus = int(get_setting("referral_bonus", "50"))
    conn.execute("INSERT INTO referrals (referrer_id, referred_id, referred_ip, bonus_credits, status, created_at) VALUES (?,?,?,?, 'granted', ?)",
                 (referrer_uid, u["id"], body.ip, bonus, now_iso()))
    conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (bonus, referrer_uid))
    conn.commit()
    conn.close()
    msg = f"🎁 Sizning referral havolangiz orqali yangi foydalanuvchi qo'shildi! +{bonus} kredit."
    telegram_send_message(referrer["telegram_id"], msg)
    add_notification(referrer_uid, msg)
    return {"status": "ok", "bonus": bonus}

@app.get("/api/referral/info/{telegram_id}")
def referral_info(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    count = conn.execute("SELECT COUNT(*) c FROM referrals WHERE referrer_id=? AND status='granted'", (u["id"],)).fetchone()["c"]
    earned = conn.execute("SELECT COALESCE(SUM(bonus_credits),0) s FROM referrals WHERE referrer_id=? AND status='granted'", (u["id"],)).fetchone()["s"]
    conn.close()
    return {"display_id": seq_id(u["id"]), "invited_count": count, "earned_credits": earned,
            "bonus_per_invite": int(get_setting("referral_bonus", "50"))}

def fallback_pdf_extract(raw: bytes):
    return " ".join(re.findall(rb'[a-zA-Z]{2,}', raw)).decode('ascii', errors='ignore')

def _extract_text_from_file(filename: str, raw: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return raw.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            text_fallback = fallback_pdf_extract(raw)
            if text_fallback: return text_fallback
            raise HTTPException(400, "PDF o'qishda xatolik yuz berdi.")
    if name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            raise HTTPException(400, "DOCX o'qishda xatolik.")
    raise HTTPException(400, "Faqat PDF, DOCX yoki TXT fayllar qabul qilinadi.")

def _extract_english_words(text: str) -> list:
    tokens = re.findall(r"[a-zA-Z]{2,}", text.lower())
    seen, out = set(), []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out

@app.post("/api/file/analyze")
async def file_analyze(telegram_id: int = Form(...), file: UploadFile = File(...)):
    u = get_or_create_user(telegram_id)
    raw = await file.read()
    text = _extract_text_from_file(file.filename, raw)
    words = _extract_english_words(text)
    if not words:
        raise HTTPException(400, "Faylda inglizcha so'zlar topilmadi.")
    parse_price = int(get_setting("file_parse_price", "1"))
    word_price = int(get_setting("file_word_price", "1"))
    price = parse_price + len(words) * word_price
    conn = db()
    conn.execute("INSERT INTO file_jobs (user_id, filename, word_count, price, status, payload, created_at) VALUES (?,?,?,?, 'pending', ?, ?)",
                 (u["id"], file.filename, len(words), price, json.dumps(words[:15000]), now_iso()))
    job_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit()
    conn.close()
    return {"job_id": job_id, "filename": file.filename, "word_count": len(words),
            "price": price, "your_credits": u["credits"]}

@app.post("/api/file/confirm")
def file_confirm(body: FileConfirmIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    job = conn.execute("SELECT * FROM file_jobs WHERE id=? AND user_id=?", (body.job_id, u["id"])).fetchone()
    if not job or job["status"] != "pending":
        conn.close()
        raise HTTPException(400, "Bu fayl topshirig'i topilmadi yoki allaqachon qayta ishlangan.")
    if u["credits"] < job["price"]:
        conn.close()
        raise HTTPException(402, f"Kredit yetarli emas. Kerak: {job['price']}, sizda: {u['credits']}.")
    words = json.loads(job["payload"] or "[]")
    added = 0
    for w in words:
        exists = conn.execute("SELECT id FROM words WHERE word=?", (w,)).fetchone()
        if exists:
            word_id = exists["id"]
        else:
            conn.execute("INSERT INTO words (word, base_level, frequency, status) VALUES (?,?,?, 'active')", (w, "", 0))
            word_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            added += 1
        already = conn.execute("SELECT id FROM saved_words WHERE user_id=? AND word_id=?", (u["id"], word_id)).fetchone()
        if not already:
            conn.execute("INSERT INTO saved_words (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], word_id, now_iso()))
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (job["price"], u["id"]))
    conn.execute("UPDATE file_jobs SET status='done' WHERE id=?", (job["id"],))
    conn.commit()
    conn.close()
    return {"status": "ok", "words_added_to_dictionary": added, "words_saved": len(words),
            "credits_spent": job["price"]}

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
    conn = db()
    conn.execute("DELETE FROM search_history WHERE user_id=?", (u["id"],))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/dictionary/search")
def dictionary_search(q: str, lang: str = "uz"):
    conn = db()
    if q.strip().isdigit():
        rows = conn.execute("SELECT * FROM words WHERE id=? AND status='active'", (int(q.strip()),)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM words WHERE word LIKE ? AND status='active' ORDER BY word ASC LIMIT 20",
            (f"{q}%",),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        m = conn.execute("SELECT translation, translation_ru FROM meanings WHERE word_id=? LIMIT 1", (r["id"],)).fetchone()
        if m:
            d["translation_preview"] = (m["translation_ru"] if (lang == "ru" and m["translation_ru"]) else m["translation"]) or ""
        else:
            d["translation_preview"] = ""
        out.append(d)
    conn.close()
    return out

@app.get("/api/dictionary/word/{word_id}")
def dictionary_word(word_id: int, telegram_id: Optional[int]=None, lang: str = "uz"):
    conn = db()
    w = conn.execute("SELECT * FROM words WHERE id=?", (word_id,)).fetchone()
    if not w:
        conn.close()
        raise HTTPException(404, "So'z topilmadi.")
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
    if not body.example1 or not body.example2:
        raise HTTPException(400, "Kamida 2 ta misol kiritish majburiy.")
    
    conn = db()
    conn.execute(
        "INSERT INTO words (word, base_level, frequency, status, suggested_by) VALUES (?,?,?, 'pending_admin', ?)",
        (body.word.strip().lower(), body.level, 0, u["id"]),
    )
    word_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.execute(
        "INSERT INTO meanings (word_id, meaning, translation, translation_ru, cefr_level, synonym_text) VALUES (?,?,?,?,?,?)",
        (word_id, body.description, body.translation, body.translation_ru, body.level, body.synonym),
    )
    meaning_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example1))
    conn.execute("INSERT INTO examples (meaning_id, sentence) VALUES (?,?)", (meaning_id, body.example2))
    conn.commit()
    conn.close()

    ai_note = ""
    is_auto_accepted = False
    if get_setting("auto_ai_check_suggestions") == "1":
        try:
            check = call_groq_json(
                'Review vocabulary entry. Reply JSON: {"looks_valid": bool, "note": str}',
                f"Word: {body.word}\nTranslation: {body.translation}\nDescription: {body.description}"
            )
            if check.get("looks_valid"):
                is_auto_accepted = True
            valid_label = "mos ko'rinadi" if check.get("looks_valid") else "shubhali"
            ai_note = f"\n\n🤖 AI tekshiruvi: {valid_label} — {check.get('note', '')}"
        except Exception:
            pass
            
    reward_amount = int(get_setting("suggestion_reward_amount", "50"))

    if is_auto_accepted:
        conn = db()
        conn.execute("UPDATE words SET status='active' WHERE id=?", (word_id,))
        conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (reward_amount, u["id"]))
        conn.commit()
        conn.close()
        
        msg = f"✅ Sizning \"{body.word}\" so'zingiz qabul qilindi! Rahmat sifatida {reward_amount} kredit taqdim etildi."
        telegram_send_message(u["telegram_id"], msg)
        
        main_ch = get_setting("main_channel")
        if main_ch:
            emoji = get_setting("bot_message_emoji", "✨")
            ch_msg = f"{emoji} Yangi so'z qo'shildi!\n\nSo'z: <tg-spoiler>{body.word}</tg-spoiler>\nDaraja: {body.level}\n\nTaklif qildi: {u['nickname'] or u['name']}"
            telegram_send_message(main_ch, ch_msg)
            
        return {"status": "ok", "message": "So'zingiz avtomatik qabul qilindi va lug'atga qo'shildi!"}

    telegram_send_message(
        ADMIN_ID,
        f"🆕 Yangi so'z taklifi (#{word_id}):\n\nSo'z: {body.word}\nTarjima (UZ): {body.translation}\n"
        f"Tavsif: {body.description}\nLevel: {body.level}\nKimdan: {u['nickname'] or u['name']} ({seq_id(u['id'])}){ai_note}",
        {"inline_keyboard": [[
            {"text": "✅ Qabul qilish", "callback_data": f"word_approve_{word_id}"},
            {"text": "❌ Rad etish", "callback_data": f"word_reject_{word_id}"},
        ]]},
    )
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
    conn = db()
    exists = conn.execute("SELECT id FROM saved_words WHERE user_id=? AND word_id=?", (u["id"], body.word_id)).fetchone()
    if not exists:
        conn.execute("INSERT INTO saved_words (user_id, word_id, created_at) VALUES (?,?,?)", (u["id"], body.word_id, now_iso()))
        conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/api/words/unsave")
def unsave_word(body: SaveWordIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    conn.execute("DELETE FROM saved_words WHERE user_id=? AND word_id=?", (u["id"], body.word_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/words/saved/{telegram_id}")
def list_saved_words(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    rows = conn.execute(
        "SELECT w.id, w.word, w.base_level FROM saved_words sw JOIN words w ON w.id=sw.word_id WHERE sw.user_id=? ORDER BY sw.id DESC",
        (u["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _create_batch(u, levels_label, word_ids):
    conn = db()
    conn.execute(
        "INSERT INTO batches (user_id, levels, total_count, created_at) VALUES (?,?,?,?)",
        (u["id"], levels_label, len(word_ids), now_iso()),
    )
    batch_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    for wid in word_ids:
        conn.execute("INSERT INTO batch_words (batch_id, word_id, status) VALUES (?,?, 'new')", (batch_id, wid))
    conn.commit()
    conn.close()
    return batch_id

@app.post("/api/batch/start")
def start_batch(body: StartBatchIn):
    u = get_or_create_user(body.telegram_id)
    if u["credits"] < body.count:
        raise HTTPException(402, f"Bu paket uchun {body.count} ta so'z limiti kerak. Sizda {u['credits']} ta bor.")
    conn = db()
    placeholders = ",".join("?" for _ in body.levels)
    words = conn.execute(
        f"SELECT id FROM words WHERE base_level IN ({placeholders}) AND status='active' ORDER BY RANDOM() LIMIT ?",
        tuple(body.levels) + (body.count,),
    ).fetchall()
    if not words:
        conn.close()
        raise HTTPException(404, "Tanlangan darajalarda so'zlar topilmadi.")
    word_ids = [w["id"] for w in words]
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (len(word_ids), u["id"]))
    conn.commit()
    conn.close()
    batch_id = _create_batch(u, ",".join(body.levels), word_ids)
    return {"batch_id": batch_id, "levels": body.levels, "count": len(word_ids)}

@app.post("/api/batch/start-from-saved")
def start_batch_from_saved(body: StartBatchFromSavedIn):
    u = get_or_create_user(body.telegram_id)
    count = len(body.word_ids)
    if count == 0:
        raise HTTPException(400, "So'z tanlanmagan.")
    if u["credits"] < count:
        raise HTTPException(402, f"Bu paket uchun {count} ta so'z limiti kerak. Sizda {u['credits']} ta bor.")
    conn = db()
    conn.execute("UPDATE users SET credits = credits - ? WHERE id=?", (count, u["id"]))
    conn.commit()
    conn.close()
    batch_id = _create_batch(u, "saqlangan", body.word_ids)
    return {"batch_id": batch_id, "count": count}

@app.get("/api/batch/current/{telegram_id}")
def current_batch(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    b = conn.execute(
        "SELECT * FROM batches WHERE user_id=? AND status IN ('active','learning_done','review_ready') ORDER BY id DESC LIMIT 1",
        (u["id"],),
    ).fetchone()
    if not b:
        conn.close()
        return None
    bwords = conn.execute(
        "SELECT bw.*, w.word, w.base_level FROM batch_words bw JOIN words w ON w.id=bw.word_id WHERE bw.batch_id=?",
        (b["id"],),
    ).fetchall()
    conn.close()
    return {**dict(b), "words": [dict(x) for x in bwords]}

@app.post("/api/batch/finish-learning/{batch_id}")
def finish_learning(batch_id: int):
    conn = db()
    conn.execute("UPDATE batches SET status='learning_done' WHERE id=?", (batch_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/batch/export/{batch_id}")
def export_batch(batch_id: int, fmt: str = "csv"):
    conn = db()
    words = conn.execute(
        "SELECT w.id, w.word, w.base_level FROM batch_words bw JOIN words w ON w.id=bw.word_id WHERE bw.batch_id=?",
        (batch_id,),
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Word", "Translation", "Level", "Synonym", "Example1", "Example2"])
    for w in words:
        m = conn.execute("SELECT * FROM meanings WHERE word_id=? LIMIT 1", (w["id"],)).fetchone()
        translation = m["translation"] if m else ""
        synonym = m["synonym_text"] if m else ""
        examples = []
        if m:
            examples = [e["sentence"] for e in conn.execute("SELECT sentence FROM examples WHERE meaning_id=?", (m["id"],)).fetchall()]
        writer.writerow([w["word"], translation, w["base_level"], synonym or "",
                          examples[0] if len(examples) > 0 else "", examples[1] if len(examples) > 1 else ""])
    conn.close()
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=unlockword_batch_{batch_id}.csv"},
    )

@app.post("/api/sentence/check")
def check_sentence(body: CheckSentenceIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    word_row = conn.execute("SELECT base_level FROM words WHERE id=?", (body.word_id,)).fetchone()
    conn.close()
    level = word_row["base_level"] if word_row else "A1"
    limits = get_sentence_limits(level)
    wc = word_count(body.sentence)
    if wc < limits["min"]:
        return {"stage": "validation", "error": f"Kamida {limits['min']} ta so'z yozing."}
    if wc > limits["max"]:
        return {"stage": "validation", "error": f"Ko'pi bilan {limits['max']} ta so'z yozishingiz mumkin."}
    result = call_groq_grammar_check(body.word, body.sentence, effective_lang(u))
    conn = db()
    is_correct = bool(result.get("correct")) and bool(result.get("used_target_word")) and bool(result.get("word_usage_correct"))
    if not result.get("used_target_word") and not result.get("mistakes"):
        lang = effective_lang(u)
        no_word_msgs = {"uz": f"\"{body.word}\" so'zi ishlatilmagan.", "ru": "Слово не использовано."}
        result["mistakes"] = [{"original": body.sentence, "correction": "", "explanation": no_word_msgs.get(lang, no_word_msgs["uz"])}]
    if body.batch_id:
        conn.execute("UPDATE batch_words SET status=? WHERE batch_id=? AND word_id=?",
                     ("correct" if is_correct else "wrong", body.batch_id, body.word_id))
    conn.commit()
    conn.close()
    return {"stage": "ai", "result": result, "is_correct": is_correct}

@app.post("/api/review/schedule")
def schedule_review(body: ScheduleReviewIn):
    minutes = body.custom_minutes if body.delay_key == "custom" else REVIEW_DELAYS.get(body.delay_key)
    if not minutes:
        raise HTTPException(400, "Noto'g'ri review vaqti.")
    next_at = (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()
    conn = db()
    conn.execute("UPDATE batches SET status='review_wait', next_review_at=? WHERE id=?", (next_at, body.batch_id))
    conn.commit()
    conn.close()
    return {"next_review_at": next_at}

@app.get("/api/review/status/{telegram_id}")
def review_status(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    b = conn.execute("SELECT * FROM batches WHERE user_id=? AND status IN ('review_wait','review_ready') ORDER BY next_review_at ASC LIMIT 1", (u["id"],)).fetchone()
    conn.close()
    return dict(b) if b else None

@app.post("/api/review/submit-score")
def submit_score(batch_id: int, correct: int, total: int):
    accuracy = correct / total if total else 0
    conn = db()
    if accuracy >= 0.85:
        conn.execute("UPDATE batches SET status='completed', correct_count=? WHERE id=?", (correct, batch_id))
    else:
        conn.execute("UPDATE batch_words SET status='new' WHERE batch_id=?", (batch_id,))
        conn.execute("UPDATE batches SET status='active', correct_count=? WHERE id=?", (correct, batch_id))
    conn.commit()
    conn.close()
    return {"accuracy": round(accuracy * 100, 1), "passed": accuracy >= 0.85}

@app.post("/api/profile/update")
def update_profile(body: ProfileUpdateIn):
    u = get_or_create_user(body.telegram_id)
    conn = db()
    if body.nickname is not None:
        conn.execute("UPDATE users SET nickname=? WHERE id=?", (body.nickname, u["id"]))
    if body.avatar_url is not None:
        conn.execute("UPDATE users SET avatar_url=? WHERE id=?", (body.avatar_url, u["id"]))
    if body.lang is not None:
        conn.execute("UPDATE users SET lang=? WHERE id=?", (body.lang, u["id"]))
    if body.secondary_lang is not None:
        conn.execute("UPDATE users SET secondary_lang=? WHERE id=?", (body.secondary_lang, u["id"]))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/progress/{telegram_id}")
def progress(telegram_id: int):
    u = get_or_create_user(telegram_id)
    conn = db()
    correct = conn.execute(
        "SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status='correct'", (u["id"],)
    ).fetchone()["c"]
    practiced = conn.execute(
        "SELECT COUNT(*) c FROM batch_words bw JOIN batches b ON b.id=bw.batch_id WHERE b.user_id=? AND bw.status IN ('correct','wrong')", (u["id"],)
    ).fetchone()["c"]
    saved_count = conn.execute("SELECT COUNT(*) c FROM saved_words WHERE user_id=?", (u["id"],)).fetchone()["c"]
    suggested_count = conn.execute("SELECT COUNT(*) c FROM words WHERE suggested_by=?", (u["id"],)).fetchone()["c"]
    rank_row = conn.execute(
        "SELECT COUNT(*) c FROM (SELECT u2.id, COUNT(bw.id) score FROM users u2 "
        "JOIN batches b ON b.user_id=u2.id JOIN batch_words bw ON bw.batch_id=b.id AND bw.status='correct' "
        "GROUP BY u2.id HAVING score > ?)",
        (correct,),
    ).fetchone()
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
    rows = conn.execute(
        "SELECT u.id as uid, u.nickname, u.avatar_url, COUNT(bw.id) as score FROM users u "
        "JOIN batches b ON b.user_id=u.id JOIN batch_words bw ON bw.batch_id=b.id "
        "WHERE bw.status='correct' GROUP BY u.id ORDER BY score DESC LIMIT 50"
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["display_id"] = seq_id(r["uid"])
        out.append(d)
    return out

def generate_unique_amount(base: int) -> int:
    conn = db()
    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    rows = conn.execute(
        "SELECT expected_amount FROM pending_payments "
        "WHERE status IN ('awaiting_amount','awaiting_confirm') AND created_at >= ?",
        (cutoff,),
    ).fetchall()
    conn.close()
    used = {int(r["expected_amount"]) for r in rows if r["expected_amount"] is not None}
    amount = base
    while amount in used:
        amount += 1
    return amount

def parse_uzs_amount_to_int(raw: str) -> int:
    int_part = raw.split(",")[0]
    digits = "".join(ch for ch in int_part if ch.isdigit())
    return int(digits) if digits else 0

def _approve_payment_row(p, source="auto"):
    conn = db()
    fresh = conn.execute("SELECT * FROM pending_payments WHERE id=?", (p["id"],)).fetchone()
    if not fresh or fresh["status"] not in ("awaiting_amount", "awaiting_confirm"):
        conn.close()
        return False
    conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (fresh["credits_to_add"], fresh["user_id"]))
    conn.execute("UPDATE pending_payments SET status='approved' WHERE id=?", (fresh["id"],))
    conn.commit()
    urow = conn.execute("SELECT telegram_id FROM users WHERE id=?", (fresh["user_id"],)).fetchone()
    conn.close()
    if urow:
        prefix = "🤖 To'lovingiz avtomatik tasdiqlandi!" if source == "auto" else "✅ To'lovingiz tasdiqlandi!"
        msg = f"{prefix} {fresh['credits_to_add']} so'z limiti qo'shildi."
        telegram_send_message(urow["telegram_id"], msg)
        add_notification(fresh["user_id"], msg)
    return True

def auto_confirm_payment_by_amount(amount: int, source="auto"):
    conn = db()
    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    p = conn.execute(
        "SELECT * FROM pending_payments WHERE expected_amount=? "
        "AND status IN ('awaiting_amount','awaiting_confirm') AND created_at >= ? "
        "ORDER BY created_at ASC LIMIT 1",
        (amount, cutoff),
    ).fetchone()
    conn.close()
    if not p:
        return None
    ok = _approve_payment_row(p, source=source)
    if not ok:
        return None
    return {"payment_id": p["id"], "user_id": p["user_id"], "credits": p["credits_to_add"],
            "display_id": seq_id(p["user_id"])}

class BankNotifyIn(BaseModel):
    amount: Optional[int] = None
    raw_text: Optional[str] = None

@app.post("/api/payment/bank-notify")
def bank_notify(body: BankNotifyIn):
    amount = body.amount
    if amount is None and body.raw_text:
        amount = parse_uzs_amount_to_int(body.raw_text)
    if not amount or amount <= 0:
        raise HTTPException(400, "Summani aniqlab bo'lmadi.")
    res = auto_confirm_payment_by_amount(amount, source="auto")
    if not res:
        return {"status": "no_match", "amount": amount,
                "message": f"{amount} so'mga mos kutilayotgan to'lov topilmadi (yoki muddati o'tgan)."}
    telegram_send_message(
        ADMIN_ID,
        f"✅ To'lov avtomatik aniqlandi va tasdiqlandi!\n\nFoydalanuvchi: {res['display_id']}\n"
        f"Summa: {amount} so'm · Kredit: {res['credits']}",
    )
    return {"status": "approved", "amount": amount, "credits": res["credits"], "user": res["display_id"]}


@app.post("/api/payment/generate")
def generate_payment(telegram_id: int, credits: int = 1000):
    u = get_or_create_user(telegram_id)
    min_credits = int(get_setting("min_credits_purchase", "100"))
    if credits < min_credits:
        raise HTTPException(400, f"Minimal {min_credits} ta kredit sotib olishingiz mumkin.")
    price_per_credit = int(get_setting("price_per_1000", "2500")) / 1000
    base_price = round(credits * price_per_credit)
    unique_amount = generate_unique_amount(base_price)

    conn = db()
    conn.execute("UPDATE pending_payments SET status='expired' WHERE user_id=? AND status IN ('awaiting_amount','awaiting_confirm')", (u["id"],))
    conn.execute(
        "INSERT INTO pending_payments (user_id, amount, expected_amount, credits_to_add, status, created_at) VALUES (?,?,?,?,?,?)",
        (u["id"], base_price, unique_amount, credits, "awaiting_amount", now_iso()),
    )
    payment_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit()
    conn.close()
    return {"payment_id": payment_id, "expected_amount": unique_amount, "credits": credits,
            "valid_for_mins": 5, "card": get_setting("payment_card"), "min_credits": min_credits}

@app.get("/api/payment/status/{payment_id}")
def payment_status(payment_id: int):
    conn = db()
    p = conn.execute("SELECT status, expected_amount, credits_to_add FROM pending_payments WHERE id=?", (payment_id,)).fetchone()
    conn.close()
    if not p:
        raise HTTPException(404, "To'lov topilmadi.")
    return {"status": p["status"], "expected_amount": p["expected_amount"], "credits": p["credits_to_add"]}

@app.post("/api/payment/mark-paid/{payment_id}")
def mark_paid(payment_id: int):
    conn = db()
    p = conn.execute("SELECT * FROM pending_payments WHERE id=?", (payment_id,)).fetchone()
    if not p or p["status"] != "awaiting_amount":
        conn.close()
        raise HTTPException(400, "Bu to'lov muddati o'tgan yoki topilmadi. Qaytadan urinib ko'ring.")
    u = conn.execute("SELECT * FROM users WHERE id=?", (p["user_id"],)).fetchone()
    conn.execute("UPDATE pending_payments SET status='awaiting_confirm' WHERE id=?", (payment_id,))
    conn.commit()
    conn.close()
    telegram_send_message(
        ADMIN_ID,
        f"💳 To'lov tasdiqlash so'rovi\n\nFoydalanuvchi: {u['nickname'] or u['name']} ({seq_id(u['id'])})\n"
        f"Summa: {p['expected_amount']} so'm\nKredit: {p['credits_to_add']}\n\n"
        f"O'z bank ilovangizda shu summa tushganini tekshirib, tasdiqlang:",
        {"inline_keyboard": [[
            {"text": "✅ Tasdiqlash", "callback_data": f"pay_approve_{payment_id}"},
            {"text": "❌ Bekor qilish", "callback_data": f"pay_reject_{payment_id}"},
        ]]},
    )
    return {"status": "sent_to_admin"}

def expire_old_payments_loop():
    while True:
        try:
            conn = db()
            cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
            conn.execute(
                "UPDATE pending_payments SET status='expired' WHERE status IN ('awaiting_amount','awaiting_confirm') AND created_at < ?",
                (cutoff,),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(60)

# ----------------- TELEGRAM BOT LOGIC (100% RESTORED) -----------------

def webapp_url_for_bot():
    domain = get_setting("webapp_domain").strip()
    return domain or None

def send_start_message(chat_id, lang="uz"):
    url = webapp_url_for_bot()
    if not url:
        telegram_send_message(chat_id, "⚠️ Bot hali to'liq sozlanmagan. Admin tez orada tugatadi.")
        return
    ok, missing = check_user_subscription(chat_id)
    if not ok:
        texts = {"uz": "Davom etish uchun quyidagi kanallarga obuna bo'ling:",
                 "ru": "Чтобы продолжить, подпишитесь на каналы ниже:",
                 "en": "Please subscribe to the channels below to continue:"}
        telegram_send_message(chat_id, texts.get(lang, texts["uz"]), subscription_keyboard(missing, lang))
        return
    msg = get_setting(f"start_message_{lang}", get_setting("start_message_uz"))
    telegram_send_message(chat_id, msg, {"inline_keyboard": [[{"text": "🚀 UnlockWord", "web_app": {"url": url}}]]})

def send_lang_menu(chat_id, first_time=False):
    prefix = "firstlang_" if first_time else "setlang_"
    telegram_send_message(chat_id, "Tilni tanlang / Выберите язык / Choose language:", {"inline_keyboard": [
        [{"text": "🇺🇿 O'zbek", "callback_data": f"{prefix}uz"}],
        [{"text": "🇷🇺 Русский", "callback_data": f"{prefix}ru"}],
        [{"text": "🇬🇧 English", "callback_data": f"{prefix}en"}],
    ]})

def send_lang2_menu(chat_id):
    telegram_send_message(chat_id, "So'zlar tarjimasini qaysi tilda ko'rmoqchisiz?", {"inline_keyboard": [
        [{"text": "🇺🇿 O'zbek", "callback_data": "setlang2_uz"}],
        [{"text": "🇷🇺 Русский", "callback_data": "setlang2_ru"}],
    ]})

def admin_main_menu():
    return {"inline_keyboard": [
        [{"text": "📢 Kanallar", "callback_data": "adm_channels"}, {"text": "👥 Foydalanuvchilar", "callback_data": "adm_users"}],
        [{"text": "💳 To'lovlar", "callback_data": "adm_payments"}, {"text": "🆕 So'z takliflari", "callback_data": "adm_pendingwords"}],
        [{"text": "✏️ Gap chegarasi", "callback_data": "adm_sentlimits"}, {"text": "💬 Start xabari", "callback_data": "adm_startmsg"}],
        [{"text": "🗑 So'z o'chirish", "callback_data": "adm_delword"}],
        [{"text": "⚙️ Sozlamalar", "callback_data": "adm_settings"}],
    ]}

def clear_admin_state(chat_id):
    if chat_id in admin_state:
        del admin_state[chat_id]

def handle_admin_command(chat_id, text):
    if text in ("/admin", "/start"):
        clear_admin_state(chat_id)
        if text == "/admin":
            telegram_send_message(chat_id, "🔧 Admin panel", admin_main_menu())
            return True
        return False

    state = admin_state.get(chat_id)
    if not state:
        return False
    action = state.get("action")

    if action == "await_ticket_reply":
        reply = text.strip()
        ticket_id = state.get("ticket_id")
        conn = db()
        ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket:
            conn.close()
            clear_admin_state(chat_id)
            telegram_send_message(chat_id, "❌ Murojaat topilmadi.", admin_main_menu())
            return True
        conn.execute("UPDATE tickets SET admin_reply=?, status='answered', replied_at=? WHERE id=?",
                     (reply, now_iso(), ticket_id))
        conn.commit()
        target = conn.execute("SELECT telegram_id FROM users WHERE id=?", (ticket["user_id"],)).fetchone()
        conn.close()
        clear_admin_state(chat_id)
        if target:
            msg = f"📩 Admin javobi (murojaat #{ticket_id}):\n\n{reply}"
            telegram_send_message(target["telegram_id"], msg)
            add_notification(ticket["user_id"], msg)
        telegram_send_message(chat_id, "✅ Javob foydalanuvchiga yuborildi.", admin_main_menu())
        return True

    if action == "await_referral_bonus":
        try:
            int(text.strip())
        except ValueError:
            telegram_send_message(chat_id, "Faqat raqam yuboring.")
            return True
        set_setting("referral_bonus", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Referral bonusi yangilandi.", admin_main_menu())
        return True

    if action == "await_file_parse_price":
        set_setting("file_parse_price", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Fayl tahlili narxi yangilandi.", admin_main_menu())
        return True

    if action == "await_file_word_price":
        set_setting("file_word_price", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Har bir so'z narxi yangilandi.", admin_main_menu())
        return True

    simple_setters = {
        "await_channel_remove": ("DELETE FROM channels WHERE id=?", lambda t: (t.strip(),)),
        "await_ban": ("UPDATE users SET is_banned=1 WHERE telegram_id=?", lambda t: (int(t.strip()),)),
        "await_unban": ("UPDATE users SET is_banned=0 WHERE telegram_id=?", lambda t: (int(t.strip()),)),
    }
    if action in simple_setters:
        sql, args_fn = simple_setters[action]
        try:
            conn = db()
            conn.execute(sql, args_fn(text))
            conn.commit()
            conn.close()
            clear_admin_state(chat_id)
            telegram_send_message(chat_id, "✅ Bajarildi.", admin_main_menu())
        except Exception:
            telegram_send_message(chat_id, "❌ Noto'g'ri format, qaytadan urining.")
        return True

    if action == "await_public_ref":
        ref = text.strip()
        if not ref.startswith("@"):
            telegram_send_message(chat_id, "Kanal username @ bilan boshlanishi kerak. Masalan: @mychannel")
            return True
        conn = db()
        conn.execute("INSERT INTO channels (chat_ref, kind, title, invite_link, created_at) VALUES (?,?,?,?,?)",
                     (ref, "public", ref, "", now_iso()))
        conn.commit()
        conn.close()
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, f"✅ Ommaviy kanal qo'shildi: {ref}", admin_main_menu())
        return True

    if action == "await_private_id":
        ref = text.strip()
        if not (ref.startswith("-100") and ref[1:].lstrip("-").isdigit()):
            telegram_send_message(chat_id, "Kanal ID -100 bilan boshlanadigan raqam bo'lishi kerak. Masalan: -1001234567890")
            return True
        admin_state[chat_id] = {"action": "await_private_link", "chat_ref": ref}
        telegram_send_message(chat_id, "Endi shu kanalning taklif havolasini yuboring (masalan https://t.me/+AbCdEfGh):")
        return True

    if action == "await_private_link":
        link = text.strip()
        ref = state.get("chat_ref")
        conn = db()
        conn.execute("INSERT INTO channels (chat_ref, kind, title, invite_link, created_at) VALUES (?,?,?,?,?)",
                     (ref, "private_request", ref, link, now_iso()))
        conn.commit()
        conn.close()
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, f"✅ Maxfiy (so'rov) kanal qo'shildi: {ref}", admin_main_menu())
        return True

    if action == "await_optional_ref":
        ref = text.strip()
        link = ref if ref.startswith("http") else ""
        conn = db()
        conn.execute("INSERT INTO channels (chat_ref, kind, title, invite_link, created_at) VALUES (?,?,?,?,?)",
                     (ref, "optional", ref, link, now_iso()))
        conn.commit()
        conn.close()
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, f"✅ Ixtiyoriy kanal/havola qo'shildi: {ref}", admin_main_menu())
        return True

    if action == "await_price":
        set_setting("price_per_1000", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Narx yangilandi.", admin_main_menu())
        return True

    if action == "await_min_credits":
        try:
            int(text.strip())
        except ValueError:
            telegram_send_message(chat_id, "Faqat raqam yuboring.")
            return True
        set_setting("min_credits_purchase", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Minimal kredit yangilandi.", admin_main_menu())
        return True

    if action == "await_mainchannel":
        set_setting("main_channel", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Asosiy kanal saqlandi.", admin_main_menu())
        return True

    if action in ("await_webapp_domain", "await_backend_domain", "await_groq_key", "await_logo_url",
                  "await_card_number", "await_bg_color", "await_help_admin",
                  "await_bot_emoji"):
        key_map = {
            "await_webapp_domain": "webapp_domain", "await_backend_domain": "backend_domain",
            "await_groq_key": "groq_api_key", "await_logo_url": "logo_url",
            "await_card_number": "payment_card", "await_bg_color": "bg_color",
            "await_help_admin": "help_admin",
            "await_bot_emoji": "bot_message_emoji",
        }
        set_setting(key_map[action], text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Saqlandi.", admin_main_menu())
        return True

    if action == "await_delete_word":
        query = text.strip()
        conn = db()
        if query.isdigit():
            w = conn.execute("SELECT * FROM words WHERE id=?", (int(query),)).fetchone()
        else:
            w = conn.execute("SELECT * FROM words WHERE word=?", (query.lower(),)).fetchone()
        if not w:
            conn.close()
            telegram_send_message(chat_id, "❌ Bunday so'z topilmadi. ID yoki so'zning o'zini aniq yuboring.")
            return True
        conn.execute("DELETE FROM words WHERE id=?", (w["id"],))
        conn.execute("DELETE FROM meanings WHERE word_id=?", (w["id"],))
        conn.commit()
        conn.close()
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, f"✅ \"{w['word']}\" (#{w['id']}) o'chirildi.", admin_main_menu())
        return True

    if action == "await_logo_photo":
        telegram_send_message(chat_id, "Iltimos, rasm (photo) sifatida yuboring, matn emas.")
        return True

    if action.startswith("await_startmsg_"):
        lang = action.split("_")[-1]
        set_setting(f"start_message_{lang}", text.strip())
        clear_admin_state(chat_id)
        telegram_send_message(chat_id, "✅ Start xabari saqlandi.", admin_main_menu())
        return True

    if action == "await_sentlimit":
        parts = text.strip().split()
        if len(parts) != 3 or parts[0] not in ("A1", "A2", "B1", "B2", "C1", "C2"):
            telegram_send_message(chat_id, "Format: A1 3 15  (daraja, min, max)")
            return True
        try:
            level, mn, mx = parts[0], int(parts[1]), int(parts[2])
            data = json.loads(get_setting("sentence_limits"))
            data[level] = {"min": mn, "max": mx}
            set_setting("sentence_limits", json.dumps(data))
            clear_admin_state(chat_id)
            telegram_send_message(chat_id, f"✅ {level}: {mn}-{mx} so'z saqlandi.", admin_main_menu())
        except Exception:
            telegram_send_message(chat_id, "❌ Xato format. Masalan: A1 3 15")
        return True

    return False

def handle_admin_callback(chat_id, message_id, data, callback_id):
    clear_admin_state(chat_id)

    if data == "adm_channels":
        conn = db()
        rows = conn.execute("SELECT * FROM channels").fetchall()
        conn.close()
        text = "📢 Kanallar:\n\n" + "\n".join([f"#{r['id']} {r['chat_ref']} ({r['kind']})" for r in rows]) if rows else "📢 Kanallar yo'q."
        telegram_edit_message(chat_id, message_id, text, {"inline_keyboard": [
            [{"text": "➕ Qo'shish", "callback_data": "adm_channel_add"}, {"text": "➖ O'chirish", "callback_data": "adm_channel_remove"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_back"}],
        ]})
    elif data == "adm_channel_add":
        telegram_edit_message(chat_id, message_id, "Qanday turdagi kanal qo'shmoqchisiz?", {"inline_keyboard": [
            [{"text": "📣 Ommaviy kanal", "callback_data": "adm_channel_add_public"}],
            [{"text": "🔒 Maxfiy (so'rov bilan) kanal", "callback_data": "adm_channel_add_private"}],
            [{"text": "🔗 Ixtiyoriy kanal/havola", "callback_data": "adm_channel_add_optional"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_channels"}],
        ]})
    elif data == "adm_channel_add_public":
        admin_state[chat_id] = {"action": "await_public_ref"}
        telegram_send_message(chat_id, "📣 Ommaviy kanal username'ini yuboring (@mychannel).\n\n⚠️ Botni shu kanalga ADMIN qilib qo'shing.")
    elif data == "adm_channel_add_private":
        admin_state[chat_id] = {"action": "await_private_id"}
        telegram_send_message(chat_id, "🔒 Kanal ID raqamini yuboring (-1001234567890).\n\n⚠️ Botni shu kanalga ADMIN qilib qo'shing.")
    elif data == "adm_channel_add_optional":
        admin_state[chat_id] = {"action": "await_optional_ref"}
        telegram_send_message(chat_id, "🔗 Ixtiyoriy kanal username'ini (@kanal) yoki havolasini yuboring.")
    elif data == "adm_channel_remove":
        admin_state[chat_id] = {"action": "await_channel_remove"}
        telegram_send_message(chat_id, "O'chirish uchun kanal ID raqamini yuboring (#raqam).")
    elif data == "adm_users":
        telegram_edit_message(chat_id, message_id, "👥 Foydalanuvchilar boshqaruvi:", {"inline_keyboard": [
            [{"text": "🚫 Bloklash", "callback_data": "adm_ban"}, {"text": "✅ Blokdan chiqarish", "callback_data": "adm_unban"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_back"}],
        ]})
    elif data == "adm_ban":
        admin_state[chat_id] = {"action": "await_ban"}
        telegram_send_message(chat_id, "Bloklash uchun Telegram ID yuboring:")
    elif data == "adm_unban":
        admin_state[chat_id] = {"action": "await_unban"}
        telegram_send_message(chat_id, "Blokdan chiqarish uchun Telegram ID yuboring:")
    elif data == "adm_payments":
        price = get_setting("price_per_1000", "2500")
        card = get_setting("payment_card") or "kiritilmagan"
        min_cr = get_setting("min_credits_purchase", "100")
        telegram_edit_message(chat_id, message_id, f"💳 Narx: {price} so'm / 1000 kredit\n💳 Karta: {card}\n📉 Minimal xarid: {min_cr} kredit", {"inline_keyboard": [
            [{"text": "✏️ Narxni o'zgartirish", "callback_data": "adm_price"}],
            [{"text": "💳 Karta raqami", "callback_data": "adm_card"}],
            [{"text": "📉 Minimal kredit", "callback_data": "adm_mincredits"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_back"}],
        ]})
    elif data == "adm_price":
        admin_state[chat_id] = {"action": "await_price"}
        telegram_send_message(chat_id, "Yangi narxni kiriting (so'm, 1000 kredit uchun, masalan 2500):")
    elif data == "adm_mincredits":
        admin_state[chat_id] = {"action": "await_min_credits"}
        telegram_send_message(chat_id, "Minimal xarid qilinadigan kredit sonini yuboring (masalan 100):")
    elif data == "adm_card":
        admin_state[chat_id] = {"action": "await_card_number"}
        telegram_send_message(chat_id, "Karta raqami va egasini yuboring (masalan: 8600 1234 5678 9012 - F.I.Sh):")
    elif data == "adm_pendingwords":
        conn = db()
        rows = conn.execute("SELECT * FROM words WHERE status='pending_admin' LIMIT 10").fetchall()
        conn.close()
        if not rows:
            telegram_edit_message(chat_id, message_id, "🆕 Yangi so'z takliflari yo'q.", {"inline_keyboard": [[{"text": "⬅️ Orqaga", "callback_data": "adm_back"}]]})
        else:
            text = "🆕 Kutilayotgan takliflar:\n\n" + "\n".join([f"#{r['id']} {r['word']} ({r['base_level']})" for r in rows])
            telegram_edit_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": "⬅️ Orqaga", "callback_data": "adm_back"}]]})
    elif data == "adm_delword":
        admin_state[chat_id] = {"action": "await_delete_word"}
        telegram_send_message(chat_id, "O'chirmoqchi bo'lgan so'zning ID raqamini (#123) yoki so'zning o'zini (aniq, masalan: chicken) yuboring:")
    elif data == "adm_sentlimits":
        limits = json.loads(get_setting("sentence_limits"))
        text = "✏️ Gap chegaralari (daraja: min-max so'z):\n\n" + "\n".join([f"{lvl}: {v['min']}-{v['max']}" for lvl, v in limits.items()])
        admin_state[chat_id] = {"action": "await_sentlimit"}
        telegram_edit_message(chat_id, message_id, text + "\n\nO'zgartirish uchun yuboring: A1 3 15", {"inline_keyboard": [[{"text": "⬅️ Orqaga", "callback_data": "adm_back"}]]})
    elif data == "adm_startmsg":
        telegram_edit_message(chat_id, message_id, "💬 Qaysi til uchun start xabarini o'zgartirasiz?", {"inline_keyboard": [
            [{"text": "🇺🇿 UZ", "callback_data": "adm_startmsg_uz"}, {"text": "🇷🇺 RU", "callback_data": "adm_startmsg_ru"}, {"text": "🇬🇧 EN", "callback_data": "adm_startmsg_en"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_back"}],
        ]})
    elif data.startswith("adm_startmsg_"):
        lang = data.split("_")[-1]
        admin_state[chat_id] = {"action": f"await_startmsg_{lang}"}
        telegram_send_message(chat_id, f"Yangi start xabarini ({lang}) yuboring:")
    elif data == "adm_settings":
        telegram_edit_message(chat_id, message_id, "⚙️ Sozlamalar:", {"inline_keyboard": [
            [{"text": "🌐 Webapp domen", "callback_data": "adm_set_webapp"}],
            [{"text": "🖥 Backend domen", "callback_data": "adm_set_backend"}],
            [{"text": "🤖 AI (Groq) kalit", "callback_data": "adm_set_groq"}],
            [{"text": "🖼 Logo (rasm yuborish)", "callback_data": "adm_set_logo"}],
            [{"text": "🎨 Fon rangi (hex)", "callback_data": "adm_set_bg"}],
            [{"text": "📚 Asosiy kanal (yangi so'z + yangiliklar)", "callback_data": "adm_set_mainchannel"}],
            [{"text": "🆘 Yordam admin (@)", "callback_data": "adm_set_help"}],
            [{"text": "✨ Bot xabar emoji", "callback_data": "adm_set_botemoji"}],
            [{"text": "🎁 Referral bonus (kredit)", "callback_data": "adm_set_refbonus"}],
            [{"text": "📄 Fayl tahlili narxi", "callback_data": "adm_set_fileparse"}, {"text": "🔤 Har so'z narxi", "callback_data": "adm_set_fileword"}],
            [{"text": "🤖 So'z takliflarida AI tekshiruv: yoqish/o'chirish", "callback_data": "adm_toggle_autoai"}],
            [{"text": "⬅️ Orqaga", "callback_data": "adm_back"}],
        ]})
    elif data == "adm_set_webapp":
        admin_state[chat_id] = {"action": "await_webapp_domain"}
        telegram_send_message(chat_id, "Webapp (index.html) joylashgan https manzilni yuboring:")
    elif data == "adm_set_backend":
        admin_state[chat_id] = {"action": "await_backend_domain"}
        telegram_send_message(chat_id, "Backend (app.py) joylashgan https manzilni yuboring:")
    elif data == "adm_set_groq":
        admin_state[chat_id] = {"action": "await_groq_key"}
        telegram_send_message(chat_id, "GROQ_API_KEY ni yuboring:")
    elif data == "adm_set_logo":
        admin_state[chat_id] = {"action": "await_logo_photo"}
        telegram_send_message(chat_id, "Endi logo rasmini shu chatga rasm (photo) sifatida yuboring:")
    elif data == "adm_set_bg":
        admin_state[chat_id] = {"action": "await_bg_color"}
        telegram_send_message(chat_id, "Fon rangini hex formatda yuboring (masalan #F8F9FC):")
    elif data == "adm_set_mainchannel":
        admin_state[chat_id] = {"action": "await_mainchannel"}
        telegram_send_message(chat_id, "Asosiy kanal username'ini yuboring — yangi so'zlar va yangiliklar shu yerga e'lon qilinadi (masalan @unlockword):")
    elif data == "adm_set_help":
        admin_state[chat_id] = {"action": "await_help_admin"}
        telegram_send_message(chat_id, "Yordam uchun admin username'ini yuboring (@...):")
    elif data == "adm_set_botemoji":
        admin_state[chat_id] = {"action": "await_bot_emoji"}
        telegram_send_message(chat_id, "Bot avtomatik xabarlarida ishlatiladigan emojini yuboring (masalan ✨ yoki 🔥):")
    elif data == "adm_set_refbonus":
        admin_state[chat_id] = {"action": "await_referral_bonus"}
        telegram_send_message(chat_id, f"Referral uchun beriladigan bonus kreditni yuboring (hozir: {get_setting('referral_bonus','50')}):")
    elif data == "adm_set_fileparse":
        admin_state[chat_id] = {"action": "await_file_parse_price"}
        telegram_send_message(chat_id, f"Fayl tahlili uchun bir martalik narxni (kredit) yuboring (hozir: {get_setting('file_parse_price','1')}):")
    elif data == "adm_set_fileword":
        admin_state[chat_id] = {"action": "await_file_word_price"}
        telegram_send_message(chat_id, f"Fayldagi har bir so'z uchun narxni (kredit) yuboring (hozir: {get_setting('file_word_price','1')}):")
    elif data == "adm_toggle_autoai":
        cur = get_setting("auto_ai_check_suggestions", "0")
        new = "0" if cur == "1" else "1"
        set_setting("auto_ai_check_suggestions", new)
        telegram_answer_callback(callback_id, "Yoqildi" if new == "1" else "O'chirildi")
    elif data == "adm_back":
        telegram_edit_message(chat_id, message_id, "🔧 Admin panel", admin_main_menu())
    elif data.startswith("word_approve_"):
        wid = int(data.split("_")[-1])
        conn = db()
        conn.execute("UPDATE words SET status='active' WHERE id=?", (wid,))
        w = conn.execute("SELECT * FROM words WHERE id=?", (wid,)).fetchone()
        conn.commit()
        if w and w["suggested_by"]:
            submitter = conn.execute("SELECT telegram_id FROM users WHERE id=?", (w["suggested_by"],)).fetchone()
            if submitter:
                msg = f"✅ Sizning \"{w['word']}\" so'zingiz qabul qilindi va lug'atga qo'shildi!"
                telegram_send_message(submitter["telegram_id"], msg)
                add_notification(w["suggested_by"], msg)
        main_ch = get_setting("main_channel")
        if main_ch and w:
            emoji = get_setting("bot_message_emoji", "✨")
            telegram_send_message(main_ch, f"{emoji} Yangi so'z qo'shildi: {w['word']} ({w['base_level']})")
        conn.close()
        telegram_answer_callback(callback_id, "Qabul qilindi")
        telegram_edit_message(chat_id, message_id, "✅ So'z qabul qilindi va lug'atga qo'shildi.")
    elif data.startswith("word_reject_"):
        wid = int(data.split("_")[-1])
        conn = db()
        w = conn.execute("SELECT * FROM words WHERE id=?", (wid,)).fetchone()
        if w and w["suggested_by"]:
            submitter = conn.execute("SELECT telegram_id FROM users WHERE id=?", (w["suggested_by"],)).fetchone()
            if submitter:
                msg = f"❌ Sizning \"{w['word']}\" so'z taklifingiz rad etildi."
                telegram_send_message(submitter["telegram_id"], msg)
                add_notification(w["suggested_by"], msg)
        conn.execute("DELETE FROM words WHERE id=?", (wid,))
        conn.commit()
        conn.close()
        telegram_answer_callback(callback_id, "Rad etildi")
        telegram_edit_message(chat_id, message_id, "❌ So'z rad etildi.")
    elif data.startswith("pay_approve_"):
        pid = int(data.split("_")[-1])
        conn = db()
        p = conn.execute("SELECT * FROM pending_payments WHERE id=?", (pid,)).fetchone()
        if p and p["status"] == "awaiting_confirm":
            conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (p["credits_to_add"], p["user_id"]))
            conn.execute("UPDATE pending_payments SET status='approved' WHERE id=?", (pid,))
            conn.commit()
            u = conn.execute("SELECT telegram_id FROM users WHERE id=?", (p["user_id"],)).fetchone()
            telegram_send_message(u["telegram_id"], f"✅ To'lovingiz tasdiqlandi! {p['credits_to_add']} so'z limiti qo'shildi.")
        conn.close()
        telegram_answer_callback(callback_id, "Tasdiqlandi")
        telegram_edit_message(chat_id, message_id, "✅ To'lov tasdiqlandi.")
    elif data.startswith("pay_reject_"):
        pid = int(data.split("_")[-1])
        conn = db()
        p = conn.execute("SELECT * FROM pending_payments WHERE id=?", (pid,)).fetchone()
        if p:
            conn.execute("UPDATE pending_payments SET status='rejected' WHERE id=?", (pid,))
            conn.commit()
            u = conn.execute("SELECT telegram_id FROM users WHERE id=?", (p["user_id"],)).fetchone()
            telegram_send_message(u["telegram_id"], "❌ To'lovingiz tasdiqlanmadi.")
        conn.close()
        telegram_answer_callback(callback_id, "Bekor qilindi")
        telegram_edit_message(chat_id, message_id, "❌ To'lov bekor qilindi.")
    elif data.startswith("firstlang_"):
        lang = data.split("_")[-1]
        conn = db()
        u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
        if not u:
            conn.execute("INSERT INTO users (telegram_id, name, nickname, credits, lang, created_at) VALUES (?,?,?,?,?,?)",
                         (chat_id, "", "", 0, lang, now_iso()))
        else:
            conn.execute("UPDATE users SET lang=? WHERE telegram_id=?", (lang, chat_id))
        conn.commit()
        conn.close()
        telegram_answer_callback(callback_id, "OK")
        if lang == "en":
            telegram_edit_message(chat_id, message_id, "✅ Language set to English.")
            send_lang2_menu(chat_id)
        else:
            telegram_edit_message(chat_id, message_id, "✅ Til saqlandi." if lang == "uz" else "✅ Язык сохранён.")
            send_start_message(chat_id, lang)
    elif data.startswith("setlang2_"):
        lang2 = data.split("_")[-1]
        conn = db(); conn.execute("UPDATE users SET secondary_lang=? WHERE telegram_id=?", (lang2, chat_id)); conn.commit(); conn.close()
        telegram_answer_callback(callback_id, "OK")
        telegram_edit_message(chat_id, message_id, "✅ Saqlandi.")
        send_start_message(chat_id, "en")
    elif data.startswith("setlang_"):
        lang = data.split("_")[-1]
        conn = db(); conn.execute("UPDATE users SET lang=? WHERE telegram_id=?", (lang, chat_id)); conn.commit(); conn.close()
        telegram_answer_callback(callback_id, "OK")
        confirms = {"uz": "✅ Til o'zbekchaga o'zgartirildi.", "ru": "✅ Язык изменён на русский.", "en": "✅ Language changed to English."}
        telegram_edit_message(chat_id, message_id, confirms.get(lang, confirms["uz"]))
        if lang == "en":
            send_lang2_menu(chat_id)

def telegram_polling_loop():
    offset = 0
    while True:
        try:
            data = requests.get(f"{TG_API}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=35).json()
            if not data.get("ok"):
                time.sleep(3)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    cb_data = cq.get("data", "")
                    if cb_data == "check_sub":
                        ok, missing = check_user_subscription(chat_id)
                        if ok:
                            telegram_answer_callback(cq["id"], "✅ Obuna tasdiqlandi!")
                            send_start_message(chat_id)
                        else:
                            telegram_answer_callback(cq["id"], "❌ Hali obuna bo'lmagansiz.")
                        continue
                    if cb_data.startswith("setlang_") or cb_data.startswith("firstlang_") or cb_data.startswith("setlang2_"):
                        handle_admin_callback(chat_id, message_id, cb_data, cq["id"])
                        continue
                    if chat_id == ADMIN_ID:
                        handle_admin_callback(chat_id, message_id, cb_data, cq["id"])
                    continue

                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                if not chat_id:
                    continue

                if "photo" in message:
                    file_id = message["photo"][-1]["file_id"]
                    is_admin_logo = chat_id == ADMIN_ID and admin_state.get(chat_id, {}).get("action") == "await_logo_photo"
                    url = telegram_get_file_url(file_id)
                    if url:
                        if is_admin_logo:
                            set_setting("logo_url", url)
                            clear_admin_state(chat_id)
                            telegram_send_message(chat_id, "✅ Logo saqlandi.", admin_main_menu())
                        else:
                            conn = db()
                            u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
                            if u:
                                conn.execute("UPDATE users SET avatar_url=? WHERE telegram_id=?", (url, chat_id))
                                conn.commit()
                                telegram_send_message(chat_id, "✅ Rasm profilingizga saqlandi.")
                            conn.close()
                    continue

                text = message.get("text", "")
                if not text:
                    continue

                if text == "/lang":
                    clear_admin_state(chat_id) if chat_id == ADMIN_ID else None
                    send_lang_menu(chat_id)
                    continue

                if text == "/lang2":
                    conn = db()
                    u = conn.execute("SELECT lang FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
                    conn.close()
                    if u and u["lang"] == "en":
                        send_lang2_menu(chat_id)
                    continue

                if chat_id == ADMIN_ID and handle_admin_command(chat_id, text):
                    continue

                if chat_id == ADMIN_ID and not admin_state.get(chat_id):
                    low = text.lower()
                    if ("uzs" in low or "so'm" in low or "som" in low or "+" in text) and any(ch.isdigit() for ch in text):
                        amount = parse_uzs_amount_to_int(text)
                        if amount > 0:
                            res = auto_confirm_payment_by_amount(amount, source="auto")
                            if res:
                                telegram_send_message(
                                    chat_id,
                                    f"✅ {amount} so'mlik to'lov {res['display_id']} ID egasiga mos keldi — "
                                    f"{res['credits']} kredit avtomatik qo'shildi.",
                                )
                            else:
                                telegram_send_message(
                                    chat_id,
                                    f"ℹ️ {amount} so'mga mos kutilayotgan to'lov topilmadi (yoki muddati o'tgan).",
                                )
                            continue

                if text == "/start":
                    conn = db()
                    urow = conn.execute("SELECT lang FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
                    conn.close()
                    if not urow or not urow["lang"]:
                        send_lang_menu(chat_id, first_time=True)
                    else:
                        send_start_message(chat_id, urow["lang"])

        except Exception:
            time.sleep(3)

def review_notifier_loop():
    while True:
        try:
            conn = db()
            due = conn.execute(
                "SELECT b.id, u.telegram_id, u.lang, b.levels FROM batches b "
                "JOIN users u ON u.id=b.user_id "
                "WHERE b.status='review_wait' AND b.next_review_at <= ?",
                (now_iso(),),
            ).fetchall()
            for row in due:
                texts = {
                    "uz": "🔔 Review tayyor! So'zlaringizni takrorlash vaqti keldi.",
                    "ru": "🔔 Повторение готово! Пора повторить слова.",
                    "en": "🔔 Review ready! Time to review your words.",
                }
                lang = row["lang"] or "uz"
                url = webapp_url_for_bot()
                markup = {"inline_keyboard": [[{"text": "🚀 UnlockWord", "web_app": {"url": url}}]]} if url else None
                telegram_send_message(row["telegram_id"], texts.get(lang, texts["uz"]), markup)
                conn.execute("UPDATE batches SET status='review_ready' WHERE id=?", (row["id"],))
            conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(30)

def start_telegram_bot():
    if not BOOTSTRAP["TELEGRAM_BOT_TOKEN"]:
        return
    try:
        requests.get(f"{TG_API}/deleteWebhook", params={"drop_pending_updates": False}, timeout=10)
    except Exception:
        pass
    threading.Thread(target=telegram_polling_loop, daemon=True).start()
    threading.Thread(target=expire_old_payments_loop, daemon=True).start()
    threading.Thread(target=review_notifier_loop, daemon=True).start()

start_telegram_bot()

@app.get("/")
@app.get("/index.html")
def serve_webapp():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
