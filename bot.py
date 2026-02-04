import os
import random
import json
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
TOKEN = "ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА"
DB_FILE = "database.json"
ESCAPE_CHANCE = 15
MAX_TRANSFER = 20000
TRANSFER_COOLDOWN_HOURS = 1

# Включаем логирование (чтобы видеть ошибки в консоли)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальная переменная для хранения базы в оперативной памяти
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

# --- ОПТИМИЗИРОВАННАЯ РАБОТА С БД ---
def load_db_to_memory():
    """Загружает базу в память при старте"""
    global DATABASE_CACHE
    if not os.path.exists(DB_FILE):
        DATABASE_CACHE = {}
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            DATABASE_CACHE = json.load(f)
        logging.info("База данных успешно загружена в память.")
    except Exception as e:
        logging.error(f"Ошибка чтения БД: {e}")
        DATABASE_CACHE = {}

def save_db_from_memory():
    """Сохраняет текущее состояние памяти на диск"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DATABASE_CACHE, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка сохранения БД: {e}")

# --- ИГРОВАЯ ЛОГИКА ---

@dp.message(F.text.lower().in_({"лис", "лисик", "/лис", "/лисик"}))
async def give_fox(message: types.Message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    now = datetime.now()
    thread_id = message.message_thread_id
    
    # Работаем с переменной в памяти, а не читаем файл!
    if user_id not in DATABASE_CACHE:
        DATABASE_CACHE[user_id] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": user_name}
    else:
        DATABASE_CACHE[user_id]["name"] = user_name

    # Кулдаун
    if DATABASE_CACHE[user_id].get("last_time"):
        try:
            last_time = datetime.fromisoformat(DATABASE_CACHE[user_id]["last_time"])
            wait_until = last_time + timedelta(hours=1)
            
            if now < wait_until:
                remaining = wait_until - now
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                await message.answer(
                    f"⏳ Твой Лисик еще отдыхает! \nПриходи через **{minutes} мин. {seconds} сек.**",
                    message_thread_id=thread_id
                )
                return
        except ValueError:
            DATABASE_CACHE[user_id]["last_time"] = None # Сброс, если время записалось криво

    # Шанс побега
    if random.randint(1, 100) <= ESCAPE_CHANCE:
        DATABASE_CACHE[user_id]["last_time"] = now.isoformat()
        save_db_from_memory() # Сохраняем изменения
        await message.answer(
            "💨 Ой! Лисик убежал...\nАлмазов не будет. Жди час!",
            message_thread_id=thread_id
        )
        return

    rarity = random.choice(CHANCES)
    folder = PATHS[rarity]
    
    try:
        if not os.path.exists(folder):
            await message.answer(f"⚠ Папка {folder} не найдена!", message_thread_id=thread_id)
            return

        # Получаем список файлов (оптимизировано)
        files = [f.name for f in os.scandir(folder) if f.is_file()]
        
        if not files:
            await message.answer(f"⚠ Папка {folder} пуста!", message_thread_id=thread_id)
            return
        
        photo_name = random.choice(files)
        fox_name = os.path.splitext(photo_name)[0]
        photo_path = os.path.join(folder, photo_name)
        
        # Обновляем данные в памяти
        reward = REWARDS[rarity]
        DATABASE_CACHE[user_id]["diamonds"] += reward
        DATABASE_CACHE[user_id]["last_time"] = now.isoformat()
        
        # Сохраняем на диск
        save_db_from_memory()
        
        caption = (
            f"🦊 Вам выпал: **{fox_name}**\n\n"
            f"✨ Редкость: **{rarity}**\n"
            f"💰 Награда: +{reward} алмазов\n"
            f"📊 Твой баланс: {DATABASE_CACHE[user_id]['diamonds']}"
        )
        
        # Отправляем файл
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo, caption=caption, parse_mode="Markdown", message_thread_id=thread_id)
        
    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        await message.answer("⚠ Ошибка бота. Проверь консоль.", message_thread_id=thread_id)

@dp.message(F.text.lower().startswith("подарить") | F.text.lower().startswith("/подарить"))
async def transfer_money(message: types.Message):
    thread_id = message.message_thread_id
    if not message.reply_to_message:
        await message.answer("⚠ Ответь на сообщение друга, чтобы подарить!", message_thread_id=thread_id)
        return

    if message.from_user.id == message.reply_to_message.from_user.id:
        await message.answer("🌚 Себе дарить нельзя.", message_thread_id=thread_id)
        return

    if message.reply_to_message.from_user.is_bot:
        return

    sender_id = str(message.from_user.id)
    receiver_id = str(message.reply_to_message.from_user.id)
    receiver_name = message.reply_to_message.from_user.full_name
    now = datetime.now()

    if sender_id not in DATABASE_CACHE:
        await message.answer("У тебя нет алмазов! Напиши 'Лисик'.", message_thread_id=thread_id)
        return

    # Кулдаун перевода
    last_transfer = DATABASE_CACHE[sender_id].get("last_transfer")
    if last_transfer:
        try:
            last_transfer_dt = datetime.fromisoformat(last_transfer)
            wait_until = last_transfer_dt + timedelta(hours=TRANSFER_COOLDOWN_HOURS)
            if now < wait_until:
                remaining = wait_until - now
                minutes = int(remaining.total_seconds() // 60)
                await message.answer(f"⏳ Следующий подарок через {minutes} мин.", message_thread_id=thread_id)
                return
        except ValueError:
             DATABASE_CACHE[sender_id]["last_transfer"] = None

    try:
        amount = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("⚠ Пример: `подарить 1000`", parse_mode="Markdown", message_thread_id=thread_id)
        return

    if amount <= 0 or amount > MAX_TRANSFER:
        await message.answer(f"❌ Сумма от 1 до {MAX_TRANSFER}!", message_thread_id=thread_id)
        return

    if DATABASE_CACHE[sender_id]["diamonds"] < amount:
        await message.answer("💸 Не хватает алмазов!", message_thread_id=thread_id)
        return

    # Перевод
    if receiver_id not in DATABASE_CACHE:
        DATABASE_CACHE[receiver_id] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": receiver_name}

    DATABASE_CACHE[sender_id]["diamonds"] -= amount
    DATABASE_CACHE[receiver_id]["diamonds"] += amount
    DATABASE_CACHE[sender_id]["last_transfer"] = now.isoformat()
    
    save_db_from_memory()

    await message.answer(
        f"🎁 **Перевод успешен!**\nОтправил: {amount} 💎\nПолучил: {receiver_name}",
        parse_mode="Markdown",
        message_thread_id=thread_id
    )

@dp.message(F.text.lower().in_({"баланс", "/баланс"}))
async def check_balance(message: types.Message):
    user_data = DATABASE_CACHE.get(str(message.from_user.id), {"diamonds": 0})
    await message.answer(
        f"💎 Твой баланс: {user_data['diamonds']} алмазов.",
        message_thread_id=message.message_thread_id
    )

@dp.message(F.text.lower().in_({"топ", "топчик", "/топ", "/топчик"}))
async def show_top(message: types.Message):
    if not DATABASE_CACHE:
        await message.answer("🏆 Список пуст!", message_thread_id=message.message_thread_id)
        return

    # Сортировка (быстрая, так как данные уже в памяти)
    sorted_users = sorted(
        DATABASE_CACHE.items(), 
        key=lambda x: x[1].get('diamonds', 0), 
        reverse=True
    )[:10]
    
    top_msg = "🏆 **ТОП-10 Богачей:**\n\n"
    for i, (user_id, info) in enumerate(sorted_users, 1):
        name = info.get("name") or "Аноним"
        diamonds = info.get("diamonds", 0)
        top_msg += f"{i}. {name} — 💎 {diamonds}\n"
    
    await message.answer(top_msg, parse_mode="Markdown", message_thread_id=message.message_thread_id)

async def main():
    load_db_to_memory() # Загружаем базу один раз
    print("✅ Бот запущен! Очередь старых сообщений очищена.")
    # drop_pending_updates=True удаляет все сообщения, которые пришли, пока бот спал
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
