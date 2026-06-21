import asyncio
import logging
import sqlite3
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== КОНФИГ ==========
BOT_TOKEN = "8430753136:AAF6B4LzUlBNEK-9Cq2MZLjPIuewgnw4550"  # Ваш токе
GROUP_ID = -5223331104  # ID вашей группы
# =============================

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    try:
        conn = sqlite3.connect('carrot.db')
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS carrot_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                count INTEGER,
                photo_id TEXT,
                date TEXT
            )
        ''')
        conn.commit()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
    finally:
        conn.close()

init_db()

# ========== СОСТОЯНИЯ FSM ==========
class CarrotForm(StatesGroup):
    waiting_for_count = State()
    waiting_for_photo = State()

# ========== КОМАНДА /START ==========
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        
        conn = sqlite3.connect('carrot.db')
        cur = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cur.execute(
            'SELECT id FROM carrot_purchases WHERE user_id = ? AND date = ?',
            (user_id, today)
        )
        existing = cur.fetchone()
        conn.close()
        
        if existing:
            await message.answer(
                "❌ Вы уже отправляли отчет сегодня!\n"
                "Следующий отчет можно будет отправить завтра."
            )
            return
        
        await message.answer(
            "🥕 *Отчет по моркови*\n\n"
            "1️⃣ Сколько вы купили моркови за сегодня?",
            parse_mode="Markdown"
        )
        await state.set_state(CarrotForm.waiting_for_count)
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

# ========== ПРИЕМ КОЛИЧЕСТВА ==========
@dp.message(CarrotForm.waiting_for_count, F.text)
async def process_count(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите число (только цифры).")
        return
    
    count = int(message.text)
    if count <= 0:
        await message.answer("⚠️ Количество должно быть больше 0.")
        return
    
    await state.update_data(count=count)
    
    await message.answer(
        "📸 2️⃣ Отправьте доказательство:",
        parse_mode="Markdown"
    )
    await state.set_state(CarrotForm.waiting_for_photo)

# ========== ПРИЕМ ФОТО ==========
@dp.message(CarrotForm.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        count = data.get('count')
        
        user_id = message.from_user.id
        username = message.from_user.username or "Не указан"
        first_name = message.from_user.first_name or ""
        
        conn = sqlite3.connect('carrot.db')
        cur = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cur.execute(
            '''INSERT INTO carrot_purchases (user_id, username, count, photo_id, date)
               VALUES (?, ?, ?, ?, ?)''',
            (user_id, username, count, message.photo[-1].file_id, today)
        )
        conn.commit()
        conn.close()
        
        caption = (
            f"🥕 *Покупка моркови*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {first_name}\n"
            f"🆔 `{user_id}`\n"
            f"🔹 @{username if username != 'Не указан' else 'Не указан'}\n"
            f"📊 {count} шт.\n"
            f"📅 {today}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        
        await bot.send_photo(
            chat_id=GROUP_ID,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode="Markdown"
        )
        
        await message.answer("✅ Отчет был отправлен")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_photo: {e}")
        await message.answer("⚠️ Ошибка при отправке отчета. Попробуйте позже.")

# ========== ОТВЕТ НА НЕ ФОТО ==========
@dp.message(CarrotForm.waiting_for_photo)
async def process_photo_invalid(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно фото.")

# ========== КОМАНДА /TOP (ПОКАЗЫВАЕТ ВСЕХ) ==========
@dp.message(Command("top"))
async def cmd_top(message: Message):
    try:
        conn = sqlite3.connect('carrot.db')
        cur = conn.cursor()
        
        # Убираем LIMIT - показываем всех
        cur.execute('''
            SELECT user_id, username, SUM(count) as total
            FROM carrot_purchases
            GROUP BY user_id
            ORDER BY total DESC
        ''')
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            await message.answer("📭 Пока нет ни одного отчета.")
            return
        
        text = "🏆 *ТОП покупателей моркови*\n"
        text += "━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Медали для всех
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, row in enumerate(rows):
            user_id, username, total = row
            
            # Если место с 1 по 10 - показываем эмодзи
            if i < 10:
                medal = medals[i]
            else:
                # Для остальных просто номер
                medal = f"{i+1}."
            
            if username and username != "Не указан":
                display = f"@{username}"
            else:
                display = f"ID: {user_id}"
            
            text += f"{medal} *{total}* шт. — {display}\n"
        
        # Добавляем итоговое количество участников
        text += f"\n━━━━━━━━━━━━━━━━━━━\n"
        text += f"👥 Всего участников: {len(rows)}"
        
        await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_top: {e}")
        await message.answer("⚠️ Ошибка при загрузке топа.")

# ========== ЗАПУСК ==========
async def main():
    logger.info("🚀 Бот для отчетов о покупке моркови запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
