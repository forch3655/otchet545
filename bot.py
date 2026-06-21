import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== КОНФИГ ==========
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"  # Замените на ваш токен
GROUP_ID = -1001234567890    # ID вашей группы (отрицательное число)
# ============================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('reports.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            count INTEGER,
            photo_id TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ========== СОСТОЯНИЯ ==========
class ReportForm(StatesGroup):
    waiting_for_count = State()
    waiting_for_photo = State()

# ========== КОМАНДА /START ==========
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Проверяем, есть ли уже сегодня отчет от этого пользователя
    conn = sqlite3.connect('reports.db')
    cur = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cur.execute('''
        SELECT id FROM reports 
        WHERE user_id = ? AND date = ?
    ''', (message.from_user.id, today))
    existing = cur.fetchone()
    conn.close()

    if existing:
        await message.answer("❌ Вы уже отправляли отчет сегодня! Следующий отчет можно будет отправить завтра.")
        return

    await message.answer(
        "🌱 *Начинаем отчет по моркови!*\n\n"
        "1️⃣ Сколько моркови вы успели собрать за сегодня? (введите число)",
        parse_mode="Markdown"
    )
    await state.set_state(ReportForm.waiting_for_count)

# ========== ПРИЕМ КОЛИЧЕСТВА ==========
@dp.message(ReportForm.waiting_for_count, F.text)
async def process_count(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите число (только цифры).")
        return
    
    count = int(message.text)
    await state.update_data(count=count)
    
    await message.answer(
        "📸 Отлично! Теперь пришлите *фото* с участка или урожая как доказательство.",
        parse_mode="Markdown"
    )
    await state.set_state(ReportForm.waiting_for_photo)

# ========== ПРИЕМ ФОТО ==========
@dp.message(ReportForm.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    count = data.get('count')
    
    # Получаем данные пользователя
    user_id = message.from_user.id
    username = message.from_user.username or "Не указан"
    
    # Сохраняем в базу
    conn = sqlite3.connect('reports.db')
    cur = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    cur.execute('''
        INSERT INTO reports (user_id, username, count, photo_id, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, count, message.photo[-1].file_id, today))
    conn.commit()
    conn.close()
    
    # Отправляем отчет в группу
    caption = (
        f"📊 *Новый отчет по моркови!*\n"
        f"👤 ID: `{user_id}`\n"
        f"🔹 Юзернейм: @{username if username != 'Не указан' else 'Не указан'}\n"
        f"🥕 Собрано: *{count}* шт.\n"
        f"📅 Дата: {today}"
    )
    
    await bot.send_photo(
        chat_id=GROUP_ID,
        photo=message.photo[-1].file_id,
        caption=caption,
        parse_mode="Markdown"
    )
    
    await message.answer("✅ Отчет успешно отправлен в группу! Спасибо!")
    await state.clear()

# ========== ОТВЕТ, ЕСЛИ НЕ ФОТО ==========
@dp.message(ReportForm.waiting_for_photo)
async def process_photo_invalid(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно фото.")

# ========== КОМАНДА /TOP ==========
@dp.message(Command("top"))
async def cmd_top(message: Message):
    conn = sqlite3.connect('reports.db')
    cur = conn.cursor()
    
    # Собираем сумму по каждому пользователю за всё время
    cur.execute('''
        SELECT user_id, username, SUM(count) as total
        FROM reports
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT 10
    ''')
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("📭 Пока нет ни одного отчета. Будьте первым!")
        return
    
    text = "🏆 *ТОП сборщиков моркови (за всё время)*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, row in enumerate(rows):
        user_id, username, total = row
        medal = medals[i] if i < 3 else f"{i+1}."
        username_display = f"@{username}" if username != "Не указан" else f"ID: {user_id}"
        text += f"{medal} *{total}* шт. — {username_display}\n"
    
    await message.answer(text, parse_mode="Markdown")

# ========== ЗАПУСК ==========
async def main():
    print("🚀 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())