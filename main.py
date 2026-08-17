import os
import json
import time
import asyncio
import sqlite3
import aiohttp
from typing import List, Dict, Any, Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8667568468:AAGtXf0m4vfYCN61v7t5RdSwZ6fdzmDpwrw")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_FILE = os.environ.get("DB_FILE", "unlockword_data.db")
BATCH_SIZE = 20
MAX_RETRIES = 3
RATE_LIMIT_COOLDOWN = 60          # seconds a rate-limited key is skipped for
AUTO_BACKUP_EVERY = 500           # send a .db backup every N completed words

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
resume_event = asyncio.Event()

SYSTEM_PROMPT = """You are an expert linguist creating a dictionary database.
For each given English word, provide dictionary entries following these strict rules:
1. If a word has multiple core meanings, produce separate entries with independent CEFR levels (A1, A2, B1, B2, C1, C2).
2. meaning_uz: array of natural Uzbek translations for that specific meaning.
3. meaning_ru: array of natural Russian translations for that specific meaning.
4. synonym: a single natural English synonym WORD or null.
5. antonym: a single natural English antonym WORD or null.
6. Synonym/antonym must match the same sense.
7. examples: exactly 2 English sentences, one simple and one advanced.
8. Do not include type, frequency_score, or UNCLASSIFIED.
9. Return ONLY valid JSON in the form {"entries":[...]}.
10. Return at least one entry for EVERY input word.
"""

# --------------------------------------------------------------------------
# DB setup
# --------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS words_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL,
        level TEXT,
        status TEXT DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT,
        level TEXT,
        meaning_uz TEXT,
        meaning_ru TEXT,
        synonym TEXT,
        antonym TEXT,
        examples TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,
        api_key TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        cooldown_until REAL DEFAULT 0,
        last_used REAL DEFAULT 0,
        UNIQUE(provider, api_key))""")
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        (key, str(value))
    )
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def word_already_known(conn, word: str) -> bool:
    wl = word.strip().lower()
    return bool(
        conn.execute(
            "SELECT 1 FROM words_queue WHERE LOWER(word)=? LIMIT 1", (wl,)
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM results WHERE LOWER(word)=? LIMIT 1", (wl,)
        ).fetchone()
    )

# --------------------------------------------------------------------------
# API key pool (multi-provider automatic failover)
# --------------------------------------------------------------------------

def add_api_key(provider: str, api_key: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO api_keys(provider, api_key, status)
               VALUES(?,?, 'active')""",
            (provider, api_key),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()

def mark_key(key_id: int, status: str, cooldown_seconds: float = 0):
    conn = sqlite3.connect(DB_FILE)
    cooldown_until = time.time() + cooldown_seconds if cooldown_seconds else 0
    conn.execute(
        "UPDATE api_keys SET status=?, cooldown_until=?, last_used=? WHERE id=?",
        (status, cooldown_until, time.time(), key_id),
    )
    conn.commit()
    conn.close()

def touch_key(key_id: int):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE api_keys SET last_used=? WHERE id=?", (time.time(), key_id))
    conn.commit()
    conn.close()

def get_usable_keys():
    """Return all keys that are usable right now (active, or rate_limited whose cooldown passed),
    ordered so the least-recently-used key comes first (round robin)."""
    now = time.time()
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        """SELECT id, provider, api_key, status, cooldown_until FROM api_keys
           WHERE status='active'
              OR (status='rate_limited' AND cooldown_until<=?)
           ORDER BY last_used ASC""",
        (now,),
    ).fetchall()
    conn.close()
    return rows

def get_all_keys_summary():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT id, provider, api_key, status FROM api_keys ORDER BY provider, id"
    ).fetchall()
    conn.close()
    return rows

# --------------------------------------------------------------------------
# JSON extraction helper
# --------------------------------------------------------------------------

def extract_json(raw: str, label: str) -> List[Dict[str, Any]]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "", 1).replace("```", "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
            except Exception as e:
                raise Exception(f"PARSE_ERROR: {label}: {e}")
        else:
            raise Exception(f"PARSE_ERROR: {label}: invalid JSON")

    if isinstance(data, dict):
        entries = data.get("entries")
        if entries is None:
            for value in data.values():
                if isinstance(value, list):
                    entries = value
                    break
        data = entries

    if not isinstance(data, list):
        raise Exception(f"PARSE_ERROR: {label}: JSON array not found")
    return data

# --------------------------------------------------------------------------
# Provider callers
# --------------------------------------------------------------------------

async def process_batch_openai_compatible(
    words_batch, api_key, url, model, label, use_json_mode=True
):
    words_text = ", ".join(
        f"{x['word']} (base level: {x.get('level') or 'unknown'})"
        for x in words_batch
    )
    prompt = (
        f"{SYSTEM_PROMPT}\n\nWords to process:\n{words_text}\n\n"
        'Return {"entries":[...]} only.'
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if use_json_mode:
        payload["response_format"] = {"type": "json_object"}

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()
            if resp.status == 429:
                raise Exception(f"RATE_LIMIT: {text[:300]}")
            if resp.status in (401, 403):
                raise Exception(f"INVALID_KEY: {text[:300]}")
            if resp.status != 200:
                raise Exception(f"API_ERROR: {resp.status} - {text[:500]}")
            try:
                data = json.loads(text)
                raw = data["choices"][0]["message"]["content"]
            except Exception as e:
                raise Exception(f"API_RESPONSE_ERROR: {e}")
    return extract_json(raw, label)

async def process_batch_with_gemini(words_batch, api_key):
    words_text = ", ".join(
        f"{x['word']} (base level: {x.get('level') or 'unknown'})"
        for x in words_batch
    )
    prompt = f"{SYSTEM_PROMPT}\n\nWords to process:\n{words_text}"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url, params={"key": api_key}, json=payload
        ) as resp:
            text = await resp.text()
            if resp.status == 429:
                raise Exception(f"RATE_LIMIT: {text[:300]}")
            if resp.status in (400, 401, 403):
                raise Exception(f"INVALID_KEY: {text[:300]}")
            if resp.status != 200:
                raise Exception(f"API_ERROR: {resp.status} - {text[:500]}")
            data = json.loads(text)
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
    return extract_json(raw, "Gemini")

async def process_batch_with_anthropic(words_batch, api_key):
    words_text = ", ".join(
        f"{x['word']} (base level: {x.get('level') or 'unknown'})"
        for x in words_batch
    )
    prompt = f"{SYSTEM_PROMPT}\n\nWords to process:\n{words_text}"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        ) as resp:
            text = await resp.text()
            if resp.status == 429:
                raise Exception(f"RATE_LIMIT: {text[:300]}")
            if resp.status in (400, 401, 403):
                raise Exception(f"INVALID_KEY: {text[:300]}")
            if resp.status != 200:
                raise Exception(f"API_ERROR: {resp.status} - {text[:500]}")
            data = json.loads(text)
            raw = data["content"][0]["text"]
    return extract_json(raw, "Claude")

def _oai(url, model, label, json_mode=True):
    async def handler(words_batch, api_key):
        return await process_batch_openai_compatible(
            words_batch, api_key, url, model, label, json_mode
        )
    return handler

PROVIDERS = {
    "gemini": (process_batch_with_gemini, ["AIzaSy", "AQ."]),
    "groq": (_oai(
        "https://api.groq.com/openai/v1/chat/completions",
        "llama-3.3-70b-versatile", "Groq"
    ), ["gsk_"]),
    "anthropic": (process_batch_with_anthropic, ["sk-ant-"]),
    "openrouter": (_oai(
        "https://openrouter.ai/api/v1/chat/completions",
        "openai/gpt-oss-20b:free", "OpenRouter"
    ), ["sk-or-"]),
    "huggingface": (_oai(
        "https://router.huggingface.co/v1/chat/completions",
        "meta-llama/Llama-3.1-8B-Instruct", "HuggingFace"
    ), ["hf_"]),
    "nvidia": (_oai(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        "meta/llama-3.3-70b-instruct", "NVIDIA NIM"
    ), ["nvapi-"]),
    "mistral": (_oai(
        "https://api.mistral.ai/v1/chat/completions",
        "mistral-large-latest", "Mistral"
    ), []),
    "deepseek": (_oai(
        "https://api.deepseek.com/chat/completions",
        "deepseek-v4-flash", "DeepSeek"
    ), []),
    "fireworks": (_oai(
        "https://api.fireworks.ai/inference/v1/chat/completions",
        "accounts/fireworks/models/llama-v3p3-70b-instruct", "Fireworks"
    ), []),
    "cerebras": (_oai(
        "https://api.cerebras.ai/v1/chat/completions",
        "llama-3.3-70b", "Cerebras"
    ), []),
    "together": (_oai(
        "https://api.together.xyz/v1/chat/completions",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free", "Together AI"
    ), []),
}

PROVIDER_LIST_TEXT = (
    "🤖 **Qo'llab-quvvatlanadigan provayderlar:**\n\n"
    "Avto-aniqlanadigan (kalitni shunchaki yuboring):\n"
    "• Gemini (`AIzaSy...`)\n"
    "• Groq (`gsk_...`)\n"
    "• Claude (`sk-ant-...`)\n"
    "• OpenRouter (`sk-or-...`)\n"
    "• HuggingFace (`hf_...`)\n"
    "• NVIDIA NIM (`nvapi-...`)\n\n"
    "Qo'lda: `/setprovider <nom> <kalit>`\n"
    "• mistral, deepseek, fireworks, cerebras, together\n\n"
    "❗ Bir nechta kalit/provayder qo'shishingiz mumkin — bot ularning "
    "orasida avtomatik almashadi, biri ishlamasa keyingisiga o'tadi.\n"
    "`/keys` — qo'shilgan kalitlar holatini ko'rish."
)

# --------------------------------------------------------------------------
# Backup / restore helpers
# --------------------------------------------------------------------------

async def send_db_backup(caption: str = "💾 Baza zaxira nusxasi"):
    if not os.path.exists(DB_FILE):
        return
    await bot.send_document(ADMIN_ID, FSInputFile(DB_FILE), caption=caption)

def maybe_auto_backup_step(done_count: int) -> bool:
    last = int(get_setting("last_backup_step", "0"))
    step = done_count // AUTO_BACKUP_EVERY
    if step > last:
        set_setting("last_backup_step", str(step))
        return True
    return False

# --------------------------------------------------------------------------
# Worker loop
# --------------------------------------------------------------------------

async def worker_loop():
    while True:
        if get_setting("is_running", "0") != "1":
            await asyncio.sleep(3)
            continue

        usable_keys = get_usable_keys()
        if not usable_keys:
            # is anything at all configured, just cooling down or all dead?
            all_keys = get_all_keys_summary()
            set_setting("is_running", "0")
            if not all_keys:
                await bot.send_message(
                    ADMIN_ID,
                    "⚠️ Hech qanday API kaliti qo'shilmagan! /providers"
                )
            else:
                await bot.send_message(
                    ADMIN_ID,
                    "⚠️ Barcha API kalitlar vaqtincha ishlamayapti "
                    "(limit yoki noto'g'ri). Yangi kalit yuboring yoki "
                    "birozdan keyin '▶️ Davom ettirish' bosing."
                )
            resume_event.clear()
            await resume_event.wait()
            continue

        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            """SELECT id, word, level FROM words_queue
               WHERE status='pending' AND retry_count < ?
               LIMIT ?""",
            (MAX_RETRIES, BATCH_SIZE),
        ).fetchall()
        conn.close()

        if not rows:
            set_setting("is_running", "0")
            await finish_and_send_file()
            continue

        batch = [{"id": r[0], "word": r[1], "level": r[2]} for r in rows]
        ids_by_word = {}
        for item in batch:
            ids_by_word.setdefault(
                item["word"].strip().lower(), []
            ).append(item["id"])
        all_ids = [x["id"] for x in batch]

        # try each usable key in turn until one succeeds or all fail
        results = None
        last_err = None
        used_key_row = None
        for key_row in usable_keys:
            key_id, provider, api_key, status, cooldown_until = key_row
            if provider not in PROVIDERS:
                continue
            try:
                results = await PROVIDERS[provider][0](batch, api_key)
                used_key_row = key_row
                touch_key(key_id)
                break
            except Exception as e:
                err = str(e)
                last_err = err
                if err.startswith("RATE_LIMIT"):
                    mark_key(key_id, "rate_limited", RATE_LIMIT_COOLDOWN)
                    continue
                if err.startswith("INVALID_KEY"):
                    mark_key(key_id, "invalid")
                    detail = err.split(":", 1)[1].strip() if ":" in err else err
                    await bot.send_message(
                        ADMIN_ID,
                        f"❌ {provider.capitalize()} kaliti ishlamayapti "
                        f"(o'chirildi), keyingi kalitga o'tildi.\n\n"
                        f"🔍 Google/provayder qaytargan xato:\n`{detail}`"
                    )
                    continue
                # generic API/network error on this key: try next key too
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ {provider.capitalize()} xato qaytardi (kalit "
                    f"o'chirilmadi, qayta urinib ko'riladi):\n`{err[:400]}`"
                )
                touch_key(key_id)
                continue

        if results is None:
            # every usable key failed on this batch
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.executemany(
                "UPDATE words_queue SET retry_count=retry_count+1 WHERE id=?",
                [(i,) for i in all_ids],
            )
            c.execute(
                """UPDATE words_queue SET status='skipped'
                   WHERE status='pending' AND retry_count>=?""",
                (MAX_RETRIES,),
            )
            skipped = c.execute(
                """SELECT word FROM words_queue
                   WHERE status='skipped' AND retry_count=?""",
                (MAX_RETRIES,),
            ).fetchall()
            conn.commit()
            conn.close()

            if skipped:
                await bot.send_message(
                    ADMIN_ID,
                    "⚠️ O'tkazib yuborildi: " +
                    ", ".join(x[0] for x in skipped[:20])
                )
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ Ushbu partiya uchun barcha kalitlar xato berdi.\n"
                f"🔍 Oxirgi xato:\n`{str(last_err)[:400]}`"
            )
            await asyncio.sleep(5)
            continue

        # -- success: persist results --
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        covered = set()
        bonus_words = set()

        for item in results:
            if not isinstance(item, dict):
                continue
            word = str(item.get("word", "")).strip()
            if not word:
                continue

            covered.add(word.lower())
            level = str(item.get("level") or "A1").upper()
            if level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                level = "A1"

            def arr(value):
                return value if isinstance(value, list) else (
                    [value] if value else []
                )

            c.execute(
                """INSERT INTO results
                (word,level,meaning_uz,meaning_ru,synonym,antonym,examples)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    word,
                    level,
                    json.dumps(arr(item.get("meaning_uz")), ensure_ascii=False),
                    json.dumps(arr(item.get("meaning_ru")), ensure_ascii=False),
                    item.get("synonym") if isinstance(item.get("synonym"), str) else None,
                    item.get("antonym") if isinstance(item.get("antonym"), str) else None,
                    json.dumps(arr(item.get("examples")), ensure_ascii=False),
                ),
            )

            for field in ("synonym", "antonym"):
                cand = item.get(field)
                if isinstance(cand, str):
                    cand = cand.strip()
                    if cand and " " not in cand:
                        if cand.lower() not in covered and not word_already_known(conn, cand):
                            bonus_words.add(cand)

        for word in bonus_words:
            c.execute(
                "INSERT INTO words_queue(word,level,status) VALUES(?,?,'pending')",
                (word, None),
            )

        done_ids = []
        retry_ids = []
        for wl, ids in ids_by_word.items():
            if wl in covered:
                done_ids.extend(ids)
            else:
                retry_ids.extend(ids)

        if done_ids:
            c.executemany(
                "UPDATE words_queue SET status='done' WHERE id=?",
                [(i,) for i in done_ids],
            )
        if retry_ids:
            c.executemany(
                "UPDATE words_queue SET retry_count=retry_count+1 WHERE id=?",
                [(i,) for i in retry_ids],
            )

        conn.commit()
        done_count = c.execute(
            "SELECT COUNT(*) FROM words_queue WHERE status='done'"
        ).fetchone()[0]
        total_count = c.execute(
            "SELECT COUNT(*) FROM words_queue"
        ).fetchone()[0]
        conn.close()

        if retry_ids:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ {len(retry_ids)} ta so'z qaytarilmadi, qayta uriniladi."
            )

        last_alert = int(get_setting("last_alert_step", "0"))
        step = done_count // 1000
        if step > last_alert:
            set_setting("last_alert_step", str(step))
            await bot.send_message(
                ADMIN_ID,
                f"📊 **Progress:**\n\n"
                f"✅ Qayta ishlandi: {done_count} ta\n"
                f"⏳ Qolgan: {max(0, total_count - done_count)} ta\n"
                f"📦 Jami: {total_count} ta"
            )

        if maybe_auto_backup_step(done_count):
            await send_db_backup(
                f"💾 Avto-zaxira ({done_count}/{total_count} bajarildi)\n"
                "Qayta deploy qilsangiz, shu faylni qayta yuklab "
                "davom ettirasiz."
            )

        await asyncio.sleep(1.5)

async def finish_and_send_file():
    await bot.send_message(
        ADMIN_ID,
        "🎉 Barcha so'zlar qayta ishlandi! JSON fayl shakllantirilmoqda..."
    )

    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        """SELECT word,level,meaning_uz,meaning_ru,synonym,antonym,examples
           FROM results"""
    ).fetchall()
    skipped = conn.execute(
        "SELECT COUNT(*) FROM words_queue WHERE status='skipped'"
    ).fetchone()[0]
    conn.close()

    order = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    output = []
    seen = set()

    for row in rows:
        word, level, muz, mru, syn, ant, ex = row
        try:
            muz, mru, ex = json.loads(muz), json.loads(mru), json.loads(ex)
        except Exception:
            continue

        key = (word.lower(), level, tuple(muz[:1]))
        if key in seen:
            continue
        seen.add(key)

        output.append({
            "word": word,
            "level": level if level in order else "A1",
            "meaning_uz": muz,
            "meaning_ru": mru,
            "synonym": syn or None,
            "antonym": ant or None,
            "examples": ex[:2],
        })

    output.sort(key=lambda x: (order.get(x["level"], 99), x["word"].lower()))
    final = [
        {"id": i, "word": x["word"], "level": x["level"], "rank": i,
         "meaning_uz": x["meaning_uz"], "meaning_ru": x["meaning_ru"],
         "synonym": x["synonym"], "antonym": x["antonym"],
         "examples": x["examples"]}
        for i, x in enumerate(output, 1)
    ]

    filename = "unlockword_database_final.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    caption = f"✅ **Baza tayyor!**\n\nJami: {len(final)} ta yozuv."
    if skipped:
        caption += f"\n⚠️ O'tkazib yuborilgan: {skipped} ta"

    await bot.send_document(
        ADMIN_ID, FSInputFile(filename), caption=caption
    )
    await send_db_backup("💾 Yakuniy baza zaxira nusxasi (.db)")

# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Holatni tekshirish"),
             KeyboardButton(text="🛑 To'xtatish")],
            [KeyboardButton(text="▶️ Davom ettirish"),
             KeyboardButton(text="💾 Zaxira olish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "👋 **UnlockWord Generator Botiga xush kelibsiz!**\n\n"
        "1. `.json` so'zlar ro'yxatini yuboring (yangi loyiha uchun) "
        "YOKI oldingi `.db` zaxira faylini yuboring (davom ettirish uchun).\n"
        "2. API kalit(lar) yuboring (`/providers`). Bir nechtasini "
        "qo'shishingiz mumkin — biri ishlamasa bot avtomatik keyingisiga o'tadi.",
        reply_markup=kb,
    )

@dp.message(F.text == "📊 Holatni tekshirish")
async def check_status(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    conn = sqlite3.connect(DB_FILE)
    total = conn.execute("SELECT COUNT(*) FROM words_queue").fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM words_queue WHERE status='done'"
    ).fetchone()[0]
    skipped = conn.execute(
        "SELECT COUNT(*) FROM words_queue WHERE status='skipped'"
    ).fetchone()[0]
    results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    conn.close()

    running = get_setting("is_running", "0")
    status = "🟢 Ishlamoqda" if running == "1" else "🔴 To'xtatilgan"
    usable = len(get_usable_keys())
    total_keys = len(get_all_keys_summary())

    await message.answer(
        f"📊 **Hozirgi holat:** {status}\n\n"
        f"🔑 Kalitlar: {usable}/{total_keys} ishlatilishi mumkin\n"
        f"📦 Jami: {total} ta\n"
        f"✅ Bajarildi: {done} ta\n"
        f"⏳ Qoldi: {max(0, total - done - skipped)} ta\n"
        f"⚠️ O'tkazib yuborildi: {skipped} ta\n"
        f"📑 Yaratilgan qatorlar: {results} ta"
    )

@dp.message(F.text == "🛑 To'xtatish")
async def pause_process(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_setting("is_running", "0")
    await message.answer("🛑 Jarayon to'xtatildi.")

@dp.message(F.text == "▶️ Davom ettirish")
async def resume_process(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_setting("is_running", "1")
    resume_event.set()
    await message.answer("▶️ Jarayon davom ettirilmoqda...")

@dp.message(F.text == "💾 Zaxira olish")
@dp.message(F.text.startswith("/backup"))
async def backup_command(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📤 Baza yuborilmoqda...")
    await send_db_backup(
        "💾 Joriy baza zaxira nusxasi. Qayta deploy qilishdan oldin/keyin "
        "shu faylni saqlab qo'ying va kerak bo'lsa botga qayta yuboring."
    )

@dp.message(F.text.startswith("/keys"))
async def list_keys(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    rows = get_all_keys_summary()
    if not rows:
        await message.answer("🔑 Hozircha kalit qo'shilmagan. /providers")
        return
    icons = {"active": "🟢", "rate_limited": "🟡", "invalid": "🔴"}
    lines = ["🔑 **Qo'shilgan kalitlar:**\n"]
    for key_id, provider, api_key, status in rows:
        masked = api_key[:6] + "…" + api_key[-4:] if len(api_key) > 12 else "****"
        lines.append(f"{icons.get(status, '⚪')} `#{key_id}` {provider}: `{masked}` ({status})")
    await message.answer("\n".join(lines))

@dp.message(F.document)
async def handle_document(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    doc = message.document
    fname = (doc.file_name or "").lower()
    if not (fname.endswith(".json") or fname.endswith((".db", ".sqlite", ".sqlite3"))):
        await message.answer("❌ Faqat `.json` (so'zlar ro'yxati) yoki `.db` (baza zaxirasi) fayl yuboring.")
        return

    file_path = f"temp_{doc.file_name}"
    await message.answer("📥 Fayl yuklanmoqda...")

    try:
        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, file_path)

        if fname.endswith((".db", ".sqlite", ".sqlite3")):
            # restore a previous backup — replace the live database
            set_setting("is_running", "0")
            if os.path.exists(DB_FILE):
                try:
                    os.replace(DB_FILE, DB_FILE + ".before_restore.bak")
                except Exception:
                    pass
            os.replace(file_path, DB_FILE)

            conn = sqlite3.connect(DB_FILE)
            total = conn.execute("SELECT COUNT(*) FROM words_queue").fetchone()[0]
            done = conn.execute(
                "SELECT COUNT(*) FROM words_queue WHERE status='done'"
            ).fetchone()[0]
            conn.close()

            await message.answer(
                f"✅ Baza tiklandi! {done}/{total} ta so'z allaqachon bajarilgan.\n"
                "Davom ettirish uchun '▶️ Davom ettirish' tugmasini bosing."
            )
            return

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON massiv (array) bo'lishi kerak.")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM words_queue")
        c.execute("DELETE FROM results")

        seen = set()
        inserted = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            word = item.get("word")
            if not isinstance(word, str) or not word.strip():
                continue
            word = word.strip()
            key = word.lower()
            if key in seen:
                continue
            seen.add(key)
            c.execute(
                """INSERT INTO words_queue(word,level,status)
                   VALUES(?,?, 'pending')""",
                (word, item.get("level", "A1")),
            )
            inserted += 1

        conn.commit()
        conn.close()

        set_setting("is_running", "1")
        set_setting("last_alert_step", "0")
        set_setting("last_backup_step", "0")
        resume_event.set()

        await message.answer(
            f"✅ Baza yuklandi! Jami **{inserted}** ta so'z navbatga qo'yildi."
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@dp.message(F.text.startswith("/providers"))
async def list_providers(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer(PROVIDER_LIST_TEXT)

@dp.message(F.text.startswith("/setprovider"))
async def set_provider_manual(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) != 3:
        await message.answer(
            "Format: `/setprovider <nom> <kalit>`\n\n" + PROVIDER_LIST_TEXT
        )
        return

    _, name, key = parts
    name = name.lower().strip()
    key = key.strip()

    if name not in PROVIDERS:
        await message.answer(
            f"❓ `{name}` tanilmadi.\n\n" + PROVIDER_LIST_TEXT
        )
        return

    added = add_api_key(name, key)
    set_setting("is_running", "1")
    resume_event.set()
    if added:
        await message.answer(
            f"🔑 **{name.capitalize()} kaliti qo'shildi!** Jarayon boshlandi..."
        )
    else:
        await message.answer(
            f"ℹ️ Bu {name.capitalize()} kaliti allaqachon qo'shilgan. Jarayon davom etmoqda..."
        )

@dp.message(F.text)
async def handle_text(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if text.startswith("/setkey "):
        text = text.split(" ", 1)[1].strip()

    provider = None
    for name, (_, prefixes) in PROVIDERS.items():
        if any(text.startswith(p) and len(text) > len(p) + 10 for p in prefixes):
            provider = name
            break

    if provider:
        added = add_api_key(provider, text)
        set_setting("is_running", "1")
        resume_event.set()
        if added:
            await message.answer(
                f"🔑 **{provider.capitalize()} kaliti qo'shildi!** Jarayon boshlandi..."
            )
        else:
            await message.answer(
                f"ℹ️ Bu {provider.capitalize()} kaliti allaqachon qo'shilgan."
            )
    else:
        await message.answer(
            "❓ Kalit avtomatik tanilmadi.\n\n"
            "Mistral/DeepSeek/Fireworks/Cerebras/Together uchun:\n"
            "`/setprovider <nom> <kalit>`\n\n" + PROVIDER_LIST_TEXT
        )

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID environment variable is missing")
    init_db()
    asyncio.create_task(worker_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
