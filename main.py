import asyncio
import sqlite3
import logging
import os
import json
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

# Загрузка базы данных аналогов из JSON
with open('tasks.json', 'r', encoding='utf-8') as f:
    DATABASE = json.load(f)

def init_db():
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.full_name or "Абитуриент"
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()
    
    years = sorted(list(set([int(task['year']) for task in DATABASE])))
    
    builder = InlineKeyboardBuilder()
    for year in years:
        builder.button(text=f"📚 Сборник {year} г.", callback_data=f"year_{year}")
    builder.adjust(2)
    
    await message.answer(
        f"Приветствуем, {username}! 👋\n"
        f"Вы запустили официальный тренажёр-аналог **«ЦЭ 2027: БЕЗ ОШИБОК»**.\n\n"
        f"Все задачи переработаны на основе тестов РИКЗ с изменёнными числами.\n\n"
        f"Выберите год сборника для тренировки:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.callback_query(F.data.startswith("year_"))
async def process_year(callback: types.CallbackQuery, state: FSMContext):
    year = int(callback.data.split("_")[1])
    await state.update_data(year=year)
    
    variants = sorted(list(set([int(task['variant']) for task in DATABASE if int(task['year']) == year])))
    
    builder = InlineKeyboardBuilder()
    for v in variants:
        builder.button(text=f"Вариант {v}", callback_data=f"var_{v}")
    builder.adjust(3)
    
    await callback.message.edit_text(
        f"Выбран сборник {year} года. 📅\nТеперь выберите номер варианта:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.choosing_variant)

@dp.callback_query(F.data.startswith("var_"))
async def process_variant(callback: types.CallbackQuery, state: FSMContext):
    var_num = int(callback.data.split("_")[1])
    user_data = await state.get_data()
    year = int(user_data['year'])
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET current_year = ?, current_variant = ?, current_task_idx = 0, score = 0, errors_log = "" WHERE user_id = ?', (year, var_num, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.delete()
    await send_json_question(user_id, state)

async def send_json_question(user_id: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (user_id,))
    year, var, idx = cursor.fetchone()
    conn.close()
    
    # Жесткое приведение к int для стабильной фильтрации
    filtered_tasks = [task for task in DATABASE if int(task['year']) == int(year) and int(task['variant']) == int(var)]
    
    if idx >= len(filtered_tasks):
        conn = sqlite3.connect('ce_math_2027.db')
        cursor = conn.cursor()
        cursor.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (user_id,))
        score, logs = cursor.fetchone()
        conn.close()
        
        errors_val = logs.strip().strip("•").strip() if logs else "Ошибок нет! Вы полностью готовы к ЦЭ на 100 баллов! 🏆"
        await bot.send_message(
            user_id, 
            f"🎯 **Вариант {var} ({year} г.) успешно пройден!**\n\n"
            f"Ваш итоговый результат: *{score}* из {len(filtered_tasks)}.\n\n"
            f"🔍 Темы, требующие бдительности:\n_{errors_val}_",
            parse_mode="Markdown"
        )
        await state.clear()
        return

    q = filtered_tasks[idx]
    
    builder = InlineKeyboardBuilder()
    for o_idx, opt in enumerate(q["options"]):
        builder.button(text=f"{o_idx+1}) {opt}", callback_data=f"ans_{idx}_{o_idx}")
    builder.adjust(1)
    
    await bot.send_message(
        user_id, 
        f"📊 **Задание {q['task_num']} (Часть {q['type']})**\n"
        f"Раздел: #{q['topic'].replace(' ', '_')}\n\n"
        f"{q['question']}", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.solving)

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    _, idx, ans_idx = callback.data.split("_")
    idx, ans_idx = int(idx), int(ans_idx)
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('SELECT current_year, current_variant FROM users WHERE user_id = ?', (user_id,))
    year, var = cursor.fetchone()
    
    filtered_tasks = [task for task in DATABASE if int(task['year']) == int(year) and int(task['variant']) == int(var)]
    q = filtered_tasks[idx]
    
    if ans_idx == q["correct"]:
        cursor.execute('UPDATE users SET score = score + 1 WHERE user_id = ?', (user_id,))
        status_text = f"✅ **Абсолютно верно!**\n\n{q['explain']}"
    else:
        cursor.execute('SELECT errors_log FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        current_log = res[0] if res and res[0] else ""
        if q['topic'] not in current_log:
            new_log = f"{current_log} • {q['topic']}"
            cursor.execute('UPDATE users SET errors_log = ? WHERE user_id = ?', (new_log, user_id))
        status_text = f"❌ **Попадание в ловушку!**\n\n{q['explain']}"
        
    cursor.execute('UPDATE users SET current_task_idx = current_task_idx + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    full_text = (
        f"📊 **Задание {q['task_num']} (Часть {q['type']})**\n"
        f"Раздел: #{q['topic'].replace(' ', '_')}\n\n"
        f"{q['question']}\n\n"
        f"---------------------------\n"
        f"{status_text}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующее задание ➡️", callback_data="next_json_task")
    await callback.message.edit_text(full_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_json_task")
async def handle_next(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await send_json_question(callback.from_user.id, state)

@dp.message(Command("report"))
async def make_report(message: types.Message):
    conn = sqlite3.connect('ce_math_2027.db')
    df = pd.read_sql_query("SELECT username AS 'Имя ученика', score AS 'Баллы', errors_log AS 'Допущенные ошибки' FROM users", conn)
    conn.close()
    
    file_name = "Отчет_Успеваемости_ЦЭ_2027.xlsx"
    df.to_excel(file_name, index=False)
    await message.answer_document(types.FSInputFile(file_name), caption="📊 Актуальный отчёт успеваемости класса.")
    os.remove(file_name)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
