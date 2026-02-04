import os
import random
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
TOKEN = "ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА"
DB_FILE = "database.json"
ESCAPE_CHANCE = 15  # Шанс побега лисика (%)
MAX_TRANSFER = 20000  # Макс. сумма перевода
TRANSFER_COOLDOWN_HOURS = 1  # Кулдаун на перевод (часов)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ПУТИ К ПАПКАМ ---
PATHS = {
    "Обычная": "images/common",
    "Редкая": "images/rare",
    "Упоротая": "images/derpy"
}

# --- НАГРАДЫ ---
REWARDS = {
    "Обычная": 1000,
    "Редкая": 5000,
    "Упоротая": 10000
}

CHANCES = ["Обычная"] * 70 + ["Редкая"] * 25 + ["Упоротая"] * 5

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- ИГРОВАЯ ЛОГИКА ---

# 1. Получение лисика (команды: лис, лисик)
@dp.message(F.text.lower().in_({"лис", "лисик", "/лис", "/лисик"}))
async def give_fox(message: types.Message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    now = datetime.now()
    thread_id = message.message_thread_id
    
    data = load_data()
    
    # Регистрация
    if user_id not in data:
        data[user_id] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": user_name}
    else:
        data[user_id]["name"] = user_name

    # Кулдаун получения лиса (1 час)
    if data[user_id].get("last_time"):
        last_time = datetime.fromisoformat(data[user_id]["last_time"])
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

    # Шанс побега
    if random.randint(1, 100) <= ESCAPE_CHANCE:
        data[user_id]["last_time"] = now.isoformat()
        save_data(data)
        await message.answer(
            "💨 Ой! Лисик увидел что-то странное и убежал...\nАлмазов не будет. Жди час!",
            message_thread_id=thread_id
        )
        return

    # Выбор картинки
    rarity = random.choice(CHANCES)
    folder = PATHS[rarity]
    
    try:
        if not os.path.exists(folder):
            await message.answer(f"⚠ Ошибка: Папка {folder} не создана!", message_thread_id=thread_id)
            return
        
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if not files:
            await message.answer(f"⚠ Ошибка: В папке {folder} пусто!", message_thread_id=thread_id)
            return
        
        photo_name = random.choice(files)
        fox_name = os.path.splitext(photo_name)[0]
        photo = FSInputFile(os.path.join(folder, photo_name))
        
        # Начисление
        reward = REWARDS[rarity]
        data[user_id]["diamonds"] += reward
        data[user_id]["last_time"] = now.isoformat()
        save_data(data)
        
        caption = (
            f"🦊 Вам выпал: **{fox_name}**\n\n"
            f"✨ Редкость: **{rarity}**\n"
            f"💰 Награда: +{reward} алмазов\n"
            f"📊 Твой баланс: {data[user_id]['diamonds']}"
        )
        await message.answer_photo(photo, caption=caption, parse_mode="Markdown", message_thread_id=thread_id)
        
    except Exception as e:
        print(f"Error: {e}")
        await message.answer("⚠ Ошибка поиска картинки.", message_thread_id=thread_id)

# 2. Перевод алмазов (команда: подарить [сумма])
@dp.message(F.text.lower().startswith("подарить") | F.text.lower().startswith("/подарить"))
async def transfer_money(message: types.Message):
    thread_id = message.message_thread_id
    
    # Проверка: Это должен быть ответ на сообщение
    if not message.reply_to_message:
        await message.answer("⚠ Чтобы подарить алмазы, **ответь** на сообщение друга этой командой!", message_thread_id=thread_id)
        return

    # Проверка: Нельзя дарить самому себе
    if message.from_user.id == message.reply_to_message.from_user.id:
        await message.answer("🤔 Самому себе дарить нельзя.", message_thread_id=thread_id)
        return
    
    # Проверка: Это не бот
    if message.reply_to_message.from_user.is_bot:
        await message.answer("🤖 Ботам алмазы не нужны!", message_thread_id=thread_id)
        return

    sender_id = str(message.from_user.id)
    receiver_id = str(message.reply_to_message.from_user.id)
    receiver_name = message.reply_to_message.from_user.full_name
    
    data = load_data()
    now = datetime.now()

    # Проверка регистрации отправителя
    if sender_id not in data:
        await message.answer("У тебя еще нет алмазов! Напиши 'Лисик', чтобы начать играть.", message_thread_id=thread_id)
        return

    # --- ПРОВЕРКА КУЛДАУНА ПЕРЕВОДА ---
    last_transfer = data[sender_id].get("last_transfer")
    if last_transfer:
        last_transfer_dt = datetime.fromisoformat(last_transfer)
        wait_until = last_transfer_dt + timedelta(hours=TRANSFER_COOLDOWN_HOURS)
        if now < wait_until:
            remaining = wait_until - now
            minutes = int(remaining.total_seconds() // 60)
            await message.answer(f"⏳ Ты уже дарил недавно! Следующий перевод через **{minutes} мин.**", message_thread_id=thread_id)
            return

    # Парсинг суммы
    try:
        # Разбиваем сообщение "подарить 500" -> берем второе слово
        amount = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("⚠ Используй формат: `подарить 1000`", parse_mode="Markdown", message_thread_id=thread_id)
        return

    # Проверка валидности суммы
    if amount <= 0:
        await message.answer("🌚 Нельзя подарить ноль или отрицательное число!", message_thread_id=thread_id)
        return
    
    if amount > MAX_TRANSFER:
        await message.answer(f"❌ Максимальная сумма подарка: **{MAX_TRANSFER}** алмазов!", parse_mode="Markdown", message_thread_id=thread_id)
        return

    if data[sender_id]["diamonds"] < amount:
        await message.answer(f"💸 У тебя не хватает алмазов! Твой баланс: {data[sender_id]['diamonds']}", message_thread_id=thread_id)
        return

    # --- СОВЕРШЕНИЕ ПЕРЕВОДА ---
    
    # Если получателя нет в базе, создаем его
    if receiver_id not in data:
        data[receiver_id] = {"diamonds": 0, "last_time": None, "last_transfer": None, "name": receiver_name}

    # Списываем и начисляем
    data[sender_id]["diamonds"] -= amount
    data[receiver_id]["diamonds"] += amount
    
    # Обновляем время перевода для отправителя
    data[sender_id]["last_transfer"] = now.isoformat()
    
    save_data(data)

    await message.answer(
        f"🎁 **Успешно!**\n"
        f"Ты подарил {amount} 💎 пользователю {receiver_name}.\n"
        f"У него теперь: {data[receiver_id]['diamonds']}\n"
        f"У тебя осталось: {data[sender_id]['diamonds']}",
        parse_mode="Markdown",
        message_thread_id=thread_id
    )

# 3. Баланс
@dp.message(F.text.lower().in_({"баланс", "/баланс"}))
async def check_balance(message: types.Message):
    data = load_data()
    user_data = data.get(str(message.from_user.id), {"diamonds": 0})
    await message.answer(
        f"💎 Твой баланс: {user_data['diamonds']} алмазов.",
        message_thread_id=message.message_thread_id
    )

# 4. Топ игроков
@dp.message(F.text.lower().in_({"топ", "топчик", "/топ", "/топчик"}))
async def show_top(message: types.Message):
    data = load_data()
    thread_id = message.message_thread_id
    
    if not data:
        await message.answer("🏆 Список пока пуст!", message_thread_id=thread_id)
        return

    sorted_users = sorted(
        data.items(), 
        key=lambda x: x[1].get('diamonds', 0), 
        reverse=True
    )[:10]
    
    top_msg = "🏆 **ТОП-10 Богачей:**\n\n"
    for i, (user_id, info) in enumerate(sorted_users, 1):
        name = info.get("name") or "Аноним"
        diamonds = info.get("diamonds", 0)
        top_msg += f"{i}. {name} — 💎 {diamonds}\n"
    
    await message.answer(top_msg, parse_mode="Markdown", message_thread_id=thread_id)

async def main():
    print("Бот запущен! (Команды: Лис, Подарить, Топчик)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())