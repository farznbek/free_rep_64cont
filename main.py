import os
import json
import asyncio
import sqlite3
import aiohttp
from typing import List, Dict, Any

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

# ================= SOZLAMALAR =================
# BotFather dan yangi token olib shu yerga qo'ying
BOT_TOKEN = "YANGI_TELEGRAM_BOT_TOKEN"
ADMIN_ID = 8996452952  # O'zingizning aniq Telegram ID raqamingiz
DB_FILE = "unlockword_data.db"
BATCH_SIZE = 20
# ===============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
resume_event = asyncio.Event()

# ================= BAZA BILAN ISHLASH =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS words_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            level TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            level TEXT,
            meaning_uz TEXT,
            meaning_ru TEXT,
            synonym TEXT,
            antonym TEXT,
            examples TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ================= GEMINI API REQUEST =================
SYSTEM_PROMPT = """You are an expert linguist creating a dictionary database.
For each given English word, provide dictionary entries following these strict rules:
1. If a word has multiple core meanings, produce separate entries with independent CEFR levels (A1, A2, B1, B2, C1, C2).
2. "meaning_uz": array of natural Uzbek translations for that specific meaning.
3. "meaning_ru": array of natural Russian translations for that specific meaning.
4. "synonym": a single natural English synonym word or null.
5. "antonym": a single natural English antonym word or null.
6. "examples": array of exactly 2 English sentences (1 simple, 1 advanced). DO NOT include translations in examples.
7. Return ONLY a valid JSON array of objects with keys: "word", "level", "meaning_uz", "meaning_ru", "synonym", "antonym", "examples". No markdown code blocks."""

async def process_batch_with_gemini(words_batch: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    words_text = ", ".join([f"{item['word']} (base level: {item.get('level', 'A1')})" for item in words_batch])
    prompt = f"{SYSTEM_PROMPT}\n\nWords to process:\n{words_text}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=60) as resp:
            if resp.status == 429:
                raise Exception("RATE_LIMIT")
            elif resp.status in (400, 403):
                raise Exception("INVALID_KEY")
            elif resp.status != 200:
                text = await resp.text()
                raise Exception(f"API_ERROR: {resp.status} - {text}")
            
            res_json = await resp.json()
            raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
            return json.loads(raw_text)

# ================= WORKER LOOP =================
async def worker_loop():
    while True:
        is_running = get_setting("is_running", "0")
        if is_running != "1":
            await asyncio.sleep(3)
            continue

        api_key = get_setting("gemini_api_key", "")
        if not api_key:
            set_setting("is_running", "0")
            await bot.send_message(ADMIN_ID, "⚠️ Gemini API kaliti o'rnatilmagan! Iltimos, API kalit yuboring.")
            resume_event.clear()
            await resume_event.wait()
            continue

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, word, level FROM words_queue WHERE status = 'pending' LIMIT ?", (BATCH_SIZE,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            set_setting("is_running", "0")
            await finish_and_send_file()
            continue

        batch = [{"id": r[0], "word": r[1], "level": r[2]} for r in rows]
        ids = [r["id"] for r in batch]

        try:
            results = await process_batch_with_gemini(batch, api_key)
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            for item in results:
                c.execute("""
                    INSERT INTO results (word, level, meaning_uz, meaning_ru, synonym, antonym, examples)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(item.get("word", "")).strip(),
                    item.get("level", "A1"),
                    json.dumps(item.get("meaning_uz", []), ensure_ascii=False),
                    json.dumps(item.get("meaning_ru", []), ensure_ascii=False),
                    item.get("synonym"),
                    item.get("antonym"),
                    json.dumps(item.get("examples", []), ensure_ascii=False)
                ))
            
            c.executemany("UPDATE words_queue SET status = 'done' WHERE id = ?", [(i,) for i in ids])
            conn.commit()

            c.execute("SELECT COUNT(*) FROM words_queue WHERE status = 'done'")
            done_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM words_queue")
            total_count = c.fetchone()[0]
            conn.close()

            last_alert = int(get_setting("last_alert_step", "0"))
            if done_count // 1000 > last_alert:
                set_setting("last_alert_step", str(done_count // 1000))
                remaining = total_count - done_count
                await bot.send_message(
                    ADMIN_ID, 
                    f"📊 **Progress:**\n\n✅ Qayta ishlandi: {done_count} ta\n⏳ Qolgan: {remaining} ta"
                )

            await asyncio.sleep(1.5)

        except Exception as e:
            err = str(e)
            if "RATE_LIMIT" in err or "INVALID_KEY" in err:
                set_setting("is_running", "0")
                await bot.send_message(
                    ADMIN_ID,
                    "⚠️ **Gemini API kalit limitga yetdi yoki yaroqsiz!**\nYangi API kalit yuboring."
                )
                resume_event.clear()
                await resume_event.wait()
            else:
                await bot.send_message(ADMIN_ID, f"⚠️ Xatolik: {err}")
                await asyncio.sleep(5)

# ================= YAKUNIY JSON =================
async def finish_and_send_file():
    await bot.send_message(ADMIN_ID, "🎉 Barcha so'zlar qayta ishlandi! JSON fayl shakllantirilmoqda...")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT word, level, meaning_uz, meaning_ru, synonym, antonym, examples FROM results")
    rows = c.fetchall()
    conn.close()

    level_order = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    formatted_data = []
    seen = set()

    for r in rows:
        word, level, m_uz, m_ru, syn, ant, ex = r
        try:
            m_uz_list = json.loads(m_uz)
            m_ru_list = json.loads(m_ru)
            ex_list = json.loads(ex)
        except:
            continue

        unique_key = (word.lower(), level, tuple(m_uz_list[:1]))
        if unique_key in seen:
            continue
        seen.add(unique_key)

        formatted_data.append({
            "word": word,
            "level": level if level in level_order else "A1",
            "meaning_uz": m_uz_list,
            "meaning_ru": m_ru_list,
            "synonym": syn if syn else None,
            "antonym": ant if ant else None,
            "examples": ex_list[:2]
        })

    formatted_data.sort(key=lambda x: (level_order.get(x["level"], 99), x["word"].lower()))

    final_output = []
    for idx, item in enumerate(formatted_data, start=1):
        final_output.append({
            "id": idx,
            "word": item["word"],
            "level": item["level"],
            "rank": idx,
            "meaning_uz": item["meaning_uz"],
            "meaning_ru": item["meaning_ru"],
            "synonym": item["synonym"],
            "antonym": item["antonym"],
            "examples": item["examples"]
        })

    output_filename = "unlockword_database_final.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    doc = FSInputFile(output_filename)
    await bot.send_document(
        ADMIN_ID, 
        doc, 
        caption=f"✅ **Baza tayyor!**\n\nJami: {len(final_output)} ta yozuv."
    )

# ================= HANDLERS =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Holatni tekshirish"), KeyboardButton(text="🛑 To'xtatish")],
            [KeyboardButton(text="▶️ Davom ettirish")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "👋 **UnlockWord Generator Botiga xush kelibsiz!**\n\n"
        "1. `.json` faylni botga yuboring.\n"
        "2. Gemini API kalitini xabar sifatida yuboring.",
        reply_markup=kb
    )

@dp.message(F.text == "📊 Holatni tekshirish")
async def check_status(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM words_queue")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM words_queue WHERE status = 'done'")
    done = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM results")
    res_count = c.fetchone()[0]
    conn.close()

    is_run = get_setting("is_running", "0")
    status_text = "🟢 Ishlamoqda" if is_run == "1" else "🔴 To'xtatilgan"
    await message.answer(
        f"📊 **Hozirgi holat:** {status_text}\n\n"
        f"📦 Jami so'zlar: {total} ta\n"
        f"✅ Bajarildi: {done} ta\n"
        f"⏳ Qoldi: {total - done} ta\n"
        f"📑 Yaratilgan qatorlar: {res_count} ta"
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

@dp.message(F.document)
async def handle_document(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    doc = message.document
    if not doc.file_name.endswith('.json'):
        await message.answer("❌ Faqat `.json` fayl yuboring.")
        return

    await message.answer("📥 Fayl yuklanmoqda...")
    file_path = f"temp_{doc.file_name}"
    file = await bot.get_file(doc.file_id)
    await bot.download_file(file.file_path, file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            await message.answer("❌ JSON massiv (array) ko'rinishida bo'lishi kerak.")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM words_queue")
        c.execute("DELETE FROM results")

        inserted = 0
        for item in data:
            word = item.get("word")
            level = item.get("level", "A1")
            if word:
                c.execute("INSERT INTO words_queue (word, level, status) VALUES (?, ?, 'pending')", (word.strip(), level))
                inserted += 1

        conn.commit()
        conn.close()
        
        if os.path.exists(file_path):
            os.remove(file_path)

        set_setting("is_running", "1")
        set_setting("last_alert_step", "0")
        resume_event.set()

        await message.answer(f"✅ Baza yuklandi! Jami **{inserted}** ta so'z navbatga qo'yildi.")

    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")

@dp.message(F.text)
async def handle_text(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.strip()
    if text.startswith("AIzaSy") and len(text) > 30:
        set_setting("gemini_api_key", text)
        set_setting("is_running", "1")
        resume_event.set()
        await message.answer("🔑 **API kalit saqlandi!** Jarayon boshlandi...")
    elif text.startswith("/setkey "):
        key = text.split(" ", 1)[1].strip()
        set_setting("gemini_api_key", key)
        set_setting("is_running", "1")
        resume_event.set()
        await message.answer("🔑 **API kalit saqlandi!** Jarayon boshlandi...")

# ================= ASOSIY TIZIM =================
async def main():
    init_db()
    asyncio.create_task(worker_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
