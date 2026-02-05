import os
import random
import json
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
TOKEN = "8224326431:AAFMXZyRPrXXtTV04Y979w61EkvvUb0iYC0"
DB_FILE = "database.json"
ESCAPE_CHANCE = 15
MAX_TRANSFER = 20000
TRANSFER_COOLDOWN_HOURS = 1

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATABASE_CACHE = {}

PATHS = {
    "Обычная": "images/common",
    "Редкая": "images/rare",
    "Упоротая": "images/derpy"
}

REWARDS = {
    "Обычная": 1000,
    "Редкая": 5000,
    "Упоротая": 10000
}

CHANCES = ["Обычная"] * 70 + ["Редкая"] * 25 + ["Упоротая"] * 5

# --- БД ---
def load_db_to_memory():
    global DATABASE_CACHE
    if not os.path.exists(DB_FILE):
        DATABASE_CACHE = {}
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            DATABASE_CACHE = json.loads(content) if content else {}
    except Exception as e:
        logging.error(f"Ошибка БД: {e}")
        DATABASE_CACHE = {}

def save_db_from_memory():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DATABASE_CACHE, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")

# Универсальная функция ответа (фиксит ошибку с темами)
async def safe_answer(message: types.Message, text: str, photo: str = None, caption: str = None):
    # Если это группа с темами, берем ID темы, иначе None
    tid = message.message_thread_id if message.chat.type in ["supergroup", "group"] else None
    
    try:
        if photo:
            return await message.answer_photo(FSInputFile(photo), caption=caption, parse_mode="Markdown", message_thread_id=tid)
        return await message.answer(text, parse_mode="Markdown", message_thread_id=tid)
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")

# --- ЛОГИКА ---

@dp.message(F.text.lower().in_({"лис", "лисик", "/лис", "/лисик"}))
async def give_fox(message: types.Message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    
    if user_id not in DATABASE_CACHE:
        DATABASE_CACHE[user_id] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": message.from_user.full_name}
    
    # Кулдаун
    if DATABASE_CACHE[user_id].get("last_time"):
        last_time = datetime.fromisoformat(DATABASE_CACHE[user_id]["last_time"])
        if now < last_time + timedelta(hours=1):
            rem = (last_time + timedelta(hours=1)) - now
            await safe_answer(message, f"⏳ Отдыхай! Жди еще {rem.seconds // 60} мин.")
            return

    # Побег
    if random.randint(1, 100) <= ESCAPE_CHANCE:
        DATABASE_CACHE[user_id]["last_time"] = now.isoformat()
        save_db_from_memory()
        await safe_answer(message, "💨 Лисик убежал! Алмазов нет.")
        return

    rarity = random.choice(CHANCES)
    folder = PATHS[rarity]
    
    try:
        files = [f.name for f in os.scandir(folder) if f.is_file()]
        if not files:
            await safe_answer(message, f"⚠ Папка {folder} пуста!")
            return
        
        fname = random.choice(files)
        reward = REWARDS[rarity]
        DATABASE_CACHE[user_id]["diamonds"] += reward
        DATABASE_CACHE[user_id]["last_time"] = now.isoformat()
        save_db_from_memory()
        
        cap = f"🦊 Вам выпал: **{os.path.splitext(fname)[0]}**\n✨ Редкость: **{rarity}**\n💰 +{reward} 💎\n📊 Баланс: {DATABASE_CACHE[user_id]['diamonds']}"
        await safe_answer(message, "", photo=os.path.join(folder, fname), caption=cap)
    except Exception:
        await safe_answer(message, "⚠ Ошибка папок.")

@dp.message(F.text.lower().startswith(("подарить", "/подарить")))
async def gift(message: types.Message):
    if not message.reply_to_message:
        await safe_answer(message, "⚠ Ответь на сообщение друга!")
        return
    
    sid, rid = str(message.from_user.id), str(message.reply_to_message.from_user.id)
    if sid == rid: return

    try:
        amt = int(message.text.split()[1])
        if amt <= 0 or amt > MAX_TRANSFER: raise ValueError
    except:
        await safe_answer(message, f"⚠ Сумма от 1 до {MAX_TRANSFER}")
        return

    if DATABASE_CACHE.get(sid, {}).get("diamonds", 0) < amt:
        await safe_answer(message, "💸 Нет алмазов!")
        return

    # Перевод
    if rid not in DATABASE_CACHE:
        DATABASE_CACHE[rid] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": message.reply_to_message.from_user.full_name}
    
    DATABASE_CACHE[sid]["diamonds"] -= amt
    DATABASE_CACHE[rid]["diamonds"] += amt
    save_db_from_memory()
    await safe_answer(message, f"🎁 Подарено {amt} 💎 пользователю {DATABASE_CACHE[rid]['name']}")

@dp.message(F.text.lower().in_({"баланс", "/баланс"}))
async def bal(message: types.Message):
    d = DATABASE_CACHE.get(str(message.from_user.id), {"diamonds": 0})["diamonds"]
    await safe_answer(message, f"💎 Баланс: {d}")

@dp.message(F.text.lower().in_({"топ", "топчик", "/топ", "/топчик"}))
async def top(message: types.Message):
    if not DATABASE_CACHE: return
    sorted_u = sorted(DATABASE_CACHE.items(), key=lambda x: x[1].get('diamonds', 0), reverse=True)[:10]
    msg = "🏆 **ТОП-10:**\n\n" + "\n".join([f"{i+1}. {u[1].get('name','Аноним')} — 💎 {u[1].get('diamonds',0)}" for i, u in enumerate(sorted_u)])
    await safe_answer(message, msg)

async def main():
    load_db_to_memory()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
