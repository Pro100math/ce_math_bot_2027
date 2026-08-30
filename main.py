import asyncio
import sqlite3
import logging
import os
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8839101630:AAEGaxK1Z7bOh2KbsiF4KlLFKSJQC0Mz_eo"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

class TrainerStates(StatesGroup):
    choosing_year = State()
    choosing_variant = State()
    solving = State()

def init_db():
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            score INTEGER DEFAULT 0,
            current_year INTEGER,
            current_variant INTEGER,
            current_task_idx INTEGER DEFAULT 0,
            errors_log TEXT DEFAULT ''
        )
    ''')
    # Таблица ВСЕХ 1200 задач ЦЭ/ЦТ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            variant INTEGER,
            task_num TEXT,
            task_type TEXT,
            topic TEXT,
            question TEXT,
            correct_ans TEXT,
            explain_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (message.from_user.id, message.from_user.full_name))
    
    # Проверяем, сколько задач в базе
    cursor.execute('SELECT COUNT(*) FROM exam_tasks')
    count = cursor.fetchone()[0]
    conn.close()
    
    builder = InlineKeyboardBuilder()
    for year in:
        builder.button(text=f"📚 Сборник {year} г.", callback_data=f"year_{year}")
    builder.adjust(2)
    
    await message.answer(
        f"Приветствуем! 👋 Вы запустили Всебелорусский ИИ-тренажёр **«ЦЭ 2027: БЕЗ ОШИБОК»**.\n\n"
        f"🔥 В систему интегрировано: **{count}** экзаменационных заданий РИКЗ.\n\n"
        f"Выберите год сборника для тренировки:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.callback_query(F.data.startswith("year_"))
async def process_year(callback: types.CallbackQuery, state: FSMContext):
    year = int(callback.data.split("_"))
    await state.update_data(year=year)
    
    builder = InlineKeyboardBuilder()
    for v in range(1, 11): # Все 10 вариантов сборника
        builder.button(text=f"Вар {v}", callback_data=f"var_{v}")
    builder.adjust(5)
    
    await callback.message.edit_text(
        f"Выбран сборник {year} года. 📅\nТеперь выберите номер варианта (1-10):", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.choosing_variant)

@dp.callback_query(F.data.startswith("var_"))
async def process_variant(callback: types.CallbackQuery, state: FSMContext):
    var_num = int(callback.data.split("_"))
    user_data = await state.get_data()
    year = int(user_data['year'])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET current_year = ?, current_variant = ?, current_task_idx = 0, score = 0, errors_log = "" WHERE user_id = ?', (year, var_num, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.delete()
    await send_db_question(user_id, state)

async def send_db_question(user_id: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (user_id,))
    year, var, idx = cursor.fetchone()
    
    # Извлекаем задачу по очереди (OFFSET) из базы данных сервера
    cursor.execute('SELECT task_num, task_type, topic, question, id FROM exam_tasks WHERE year = ? AND variant = ? LIMIT 1 OFFSET ?', (year, var, idx))
    task = cursor.fetchone()
    
    if not task:
        cursor.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (user_id,))
        score, logs = cursor.fetchone()
        cursor.execute('SELECT COUNT(*) FROM exam_tasks WHERE year = ? AND variant = ?', (year, var))
        total = cursor.fetchone()[0]
        conn.close()
        
        errors_val = logs.strip().strip("•").strip() if logs else "Ошибок нет! Вы полностью готовы к ЦЭ на 100 баллов! 🏆"
        await bot.send_message(
            user_id, 
            f"🎯 **Вариант {var} ({year} г.) успешно пройден!**\n\n"
            f"Ваш результат: *{score}* из {total}.\n\n"
            f"🔍 Темы, требующие повторения:\n_{errors_val}_",
            parse_mode="Markdown"
        )
        await state.clear()
        return
        
    t_num, t_type, t_topic, t_quest, t_id = task
    conn.close()
    
    await state.update_data(current_task_id=t_id)
    
    await bot.send_message(
        user_id, 
        f"📊 **Задание {t_num} (Часть {t_type})**\n"
        f"Раздел: #{t_topic.replace(' ', '_')}\n\n"
        f"{t_quest}\n\n"
        f"✏️ **Решите задачу и введите числовой ответ (или цифры вариантов для части А):**"
    )
    await state.set_state(TrainerStates.solving)

@dp.message(TrainerStates.solving)
async def check_answer(message: types.Message, state: FSMContext):
    user_ans = message.text.strip().lower()
    user_data = await state.get_data()
    t_id = user_data['current_task_id']
    user_id = message.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('SELECT correct_ans, explain_text, topic FROM exam_tasks WHERE id = ?', (t_id,))
    correct_ans, explain, topic = cursor.fetchone()
    
    if str(user_ans) == str(correct_ans).strip().lower():
        cursor.execute('UPDATE users SET score = score + 1 WHERE user_id = ?', (user_id,))
        status_text = f"✅ **Абсолютно верно!**\n\n{explain}"
    else:
        cursor.execute('SELECT errors_log FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        current_log = res[0] if res and res[0] else ""
        if topic not in current_log:
            new_log = f"{current_log} • {topic}"
            cursor.execute('UPDATE users SET errors_log = ? WHERE user_id = ?', (new_log, user_id))
        status_text = f"❌ **Ошибка в ответе!**\n\n{explain}"
        
    cursor.execute('UPDATE users SET current_task_idx = current_task_idx + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующее задание ➡️", callback_data="next_db_task")
    await message.answer(status_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_db_task")
async def handle_next(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await send_db_question(callback.from_user.id, state)

@dp.message(Command("report"))
async def make_report(message: types.Message):
    conn = sqlite3.connect('ce_math_2027.db')
    df = pd.read_sql_query("SELECT username AS 'Имя', score AS 'Баллы', errors_log AS 'Ошибки' FROM users", conn)
    conn.close()
    
    file_name = "Отчет_Успеваемости.xlsx"
    df.to_excel(file_name, index=False)
    await message.answer_document(types.FSInputFile(file_name), caption="📊 Отчёт успеваемости класса.")
    os.remove(file_name)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
