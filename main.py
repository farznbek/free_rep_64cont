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
# Railway'da bu qiymatlarni "Variables" bo'limida BOT_TOKEN / ADMIN_ID / DB_FILE
# nomlari bilan qo'ying -- shunda quyidagi fallback qiymatlar ishlatilmaydi.
# Bu tokenni hech kim (Sizdan boshqa) ishlata olmaydi, chunki har bir handler
# is_admin() orqali faqat ADMIN_ID mos kelgan foydalanuvchiga javob beradi.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8667568468:AAGtXf0m4vfYCN61v7t5RdSwZ6fdzmDpwrw")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8996452952"))
DB_FILE = os.environ.get("DB_FILE", "unlockword_data.db")
BATCH_SIZE = 20
MAX_RETRIES = 3
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
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0
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

def word_already_known(conn, word: str) -> bool:
    """Check (case-insensitive) if a word already exists anywhere in the
    queue or in the results table, so we never queue the same word twice."""
    c = conn.cursor()
    wl = word.strip().lower()
    c.execute("SELECT 1 FROM words_queue WHERE LOWER(word) = ? LIMIT 1", (wl,))
    if c.fetchone():
        return True
    c.execute("SELECT 1 FROM results WHERE LOWER(word) = ? LIMIT 1", (wl,))
    if c.fetchone():
        return True
    return False

# ================= GEMINI API REQUEST =================
SYSTEM_PROMPT = """You are an expert linguist creating a dictionary database.
For each given English word, provide dictionary entries following these strict rules:
1. If a word has multiple core meanings, produce separate entries with independent CEFR levels (A1, A2, B1, B2, C1, C2).
2. "meaning_uz": array of natural Uzbek translations for that specific meaning.
3. "meaning_ru": array of natural Russian translations for that specific meaning.
4. "synonym": a single natural English synonym WORD (not a phrase) or null if none exists.
5. "antonym": a single natural English antonym WORD (not a phrase) or null if none exists.
6. The synonym/antonym must match the SAME sense given in that entry's meaning_uz/meaning_ru.
7. "examples": array of exactly 2 English sentences (1 simple, 1 advanced), matching that specific sense. DO NOT include translations in examples.
8. Do not include a "type" field, "frequency_score" field, or the word "UNCLASSIFIED" anywhere.
9. Return ONLY a valid JSON array of objects with keys: "word", "level", "meaning_uz", "meaning_ru", "synonym", "antonym", "examples". No markdown code blocks, no extra commentary.
10. You MUST return one or more entries for EVERY word given in the input list -- never skip a word."""

async def process_batch_with_gemini(words_batch: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    words_text = ", ".join([f"{item['word']} (base level: {item.get('level') or 'unknown'})" for item in words_batch])
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
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status == 429:
                raise Exception("RATE_LIMIT")
            elif resp.status in (400, 403):
                raise Exception("INVALID_KEY")
            elif resp.status != 200:
                text = await resp.text()
                raise Exception(f"API_ERROR: {resp.status} - {text}")

            res_json = await resp.json()
            raw_text = res_json['candidates'][0]['content']['parts'][0]['text']

    # JSON parsing is separated from the network call so a malformed model
    # response is handled distinctly from a real API/network error.
    try:
        parsed = json.loads(raw_text)
        if not isinstance(parsed, list):
            raise ValueError("Gemini javobi JSON array emas")
        return parsed
    except Exception as e:
        raise Exception(f"PARSE_ERROR: {e}")

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
        c.execute("SELECT id, word, level FROM words_queue WHERE status = 'pending' AND retry_count < ? LIMIT ?", (MAX_RETRIES, BATCH_SIZE))
        rows = c.fetchall()
        conn.close()

        if not rows:
            set_setting("is_running", "0")
            await finish_and_send_file()
            continue

        batch = [{"id": r[0], "word": r[1], "level": r[2]} for r in rows]
        ids_by_word_lower = {}
        for item in batch:
            ids_by_word_lower.setdefault(item["word"].strip().lower(), []).append(item["id"])
        all_ids = [item["id"] for item in batch]

        try:
            results = await process_batch_with_gemini(batch, api_key)

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            covered_words_lower = set()
            new_bonus_words = []

            for item in results:
                word = str(item.get("word", "")).strip()
                if not word:
                    continue
                covered_words_lower.add(word.lower())

                c.execute("""
                    INSERT INTO results (word, level, meaning_uz, meaning_ru, synonym, antonym, examples)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    word,
                    item.get("level", "A1"),
                    json.dumps(item.get("meaning_uz", []), ensure_ascii=False),
                    json.dumps(item.get("meaning_ru", []), ensure_ascii=False),
                    item.get("synonym"),
                    item.get("antonym"),
                    json.dumps(item.get("examples", []), ensure_ascii=False)
                ))

                # Any synonym/antonym word that doesn't already have its own
                # entry (original queue OR results OR already-queued bonus
                # word) gets queued as a brand new word to process, so it
                # ends up as its own flat entry too -- per the project spec.
                for field in ("synonym", "antonym"):
                    cand = item.get(field)
                    if not cand or not isinstance(cand, str):
                        continue
                    cand = cand.strip()
                    if not cand or " " in cand:  # skip phrases, only single words
                        continue
                    cand_lower = cand.lower()
                    if cand_lower in covered_words_lower or cand_lower in [w.lower() for w in new_bonus_words]:
                        continue
                    if not word_already_known(conn, cand):
                        new_bonus_words.append(cand)

            for w in new_bonus_words:
                c.execute("INSERT INTO words_queue (word, level, status) VALUES (?, ?, 'pending')", (w, None))

            # Only mark the ids whose word was actually returned by Gemini as
            # done. Anything missing stays pending and will be retried (up to
            # MAX_RETRIES), so a word can never be silently dropped.
            done_ids = []
            retry_ids = []
            for wl, id_list in ids_by_word_lower.items():
                if wl in covered_words_lower:
                    done_ids.extend(id_list)
                else:
                    retry_ids.extend(id_list)

            if done_ids:
                c.executemany("UPDATE words_queue SET status = 'done' WHERE id = ?", [(i,) for i in done_ids])
            if retry_ids:
                c.executemany("UPDATE words_queue SET retry_count = retry_count + 1 WHERE id = ?", [(i,) for i in retry_ids])

            conn.commit()

            c.execute("SELECT COUNT(*) FROM words_queue WHERE status = 'done'")
            done_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM words_queue")
            total_count = c.fetchone()[0]
            conn.close()

            if retry_ids:
                await bot.send_message(ADMIN_ID, f"⚠️ {len(retry_ids)} ta so'z ushbu partiyada qaytarilmadi, qayta urinib ko'riladi.")

            last_alert = int(get_setting("last_alert_step", "0"))
            if done_count // 1000 > last_alert:
                set_setting("last_alert_step", str(done_count // 1000))
                remaining = total_count - done_count
                await bot.send_message(
                    ADMIN_ID,
                    f"📊 **Progress:**\n\n✅ Qayta ishlandi: {done_count} ta\n⏳ Qolgan: {remaining} ta\n📦 Jami (bonus so'zlar bilan): {total_count} ta"
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
                # Network/parse error for this whole batch: bump retry_count
                # for every id in it so a permanently-failing word eventually
                # gets skipped instead of looping forever.
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.executemany("UPDATE words_queue SET retry_count = retry_count + 1 WHERE id = ?", [(i,) for i in all_ids])
                c.execute("SELECT word FROM words_queue WHERE retry_count >= ? AND status = 'pending'", (MAX_RETRIES,))
                skipped = [r[0] for r in c.fetchall()]
                if skipped:
                    c.executemany("UPDATE words_queue SET status = 'skipped' WHERE word = ?", [(w,) for w in skipped])
                conn.commit()
                conn.close()
                if skipped:
                    await bot.send_message(ADMIN_ID, f"⚠️ {MAX_RETRIES} marta urinishdan so'ng o'tkazib yuborildi: {', '.join(skipped[:20])}")
                await bot.send_message(ADMIN_ID, f"⚠️ Xatolik: {err}")
                await asyncio.sleep(5)

# ================= YAKUNIY JSON =================
async def finish_and_send_file():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM words_queue WHERE status = 'skipped'")
    skipped_count = c.fetchone()[0]
    conn.close()

    msg = "🎉 Barcha so'zlar qayta ishlandi! JSON fayl shakllantirilmoqda..."
    if skipped_count:
        msg += f"\n⚠️ Diqqat: {skipped_count} ta so'z {MAX_RETRIES} marta urinishdan keyin ham xato berdi va o'tkazib yuborildi."
    await bot.send_message(ADMIN_ID, msg)

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
        except Exception:
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
    c.execute("SELECT COUNT(*) FROM words_queue WHERE status = 'skipped'")
    skipped = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM results")
    res_count = c.fetchone()[0]
    conn.close()

    is_run = get_setting("is_running", "0")
    status_text = "🟢 Ishlamoqda" if is_run == "1" else "🔴 To'xtatilgan"
    await message.answer(
        f"📊 **Hozirgi holat:** {status_text}\n\n"
        f"📦 Jami so'zlar (bonus bilan): {total} ta\n"
        f"✅ Bajarildi: {done} ta\n"
        f"⏳ Qoldi: {total - done - skipped} ta\n"
        f"⚠️ O'tkazib yuborildi: {skipped} ta\n"
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
        seen_words = set()
        for item in data:
            word = item.get("word")
            level = item.get("level", "A1")
            if word:
                wl = word.strip().lower()
                if wl in seen_words:
                    continue
                seen_words.add(wl)
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
