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

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TrainerStates(StatesGroup):
    choosing_year = State()
    choosing_variant = State()
    solving = State()

def get_database_by_year(year: int):
    """Динамически подключаем нужный файл с заданиями в зависимости от года или финала"""
    try:
        if year == 2023:
            from tasks_2023 import DATABASE
            return DATABASE
        elif year == 2024:
            from tasks_2024 import DATABASE
            return DATABASE
        elif year == 2025:
            from tasks_2025 import DATABASE
            return DATABASE
        elif year == 2026:
            from tasks_2026 import DATABASE
            return DATABASE
        elif year == 2027:
            from tasks_final import DATABASE
            return DATABASE
    except ImportError:
        logging.error(f"Не удалось загрузить файл заданий для {year} года")
    return []

def init_db():
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, score INTEGER DEFAULT 0,
            current_year INTEGER, current_variant INTEGER, current_task_idx INTEGER DEFAULT 0,
            errors_log TEXT DEFAULT ""
        )
    ''')
    conn.close()

async def show_main_menu(message: types.Message, state: FSMContext, user_id: int, full_name: str):
    await state.clear()
    init_db()
    
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, full_name))
    conn.commit()
    conn.close()
    
    # СТРОКА НАМЕРТВО ИСПРАВЛЕНА: Прописан список ваших 4 сборников ЦЭ
    available_years = [2023, 2024, 2025, 2026]
    
    b = InlineKeyboardBuilder()
    for y in available_years:
        b.button(text=f"📚 Сборник {y} г.", callback_data=f"year_{y}")
    
    # Кнопка комплексного финального теста на закрепление материала
    b.button(text="🎯 ТЕСТ НА ЗАКРЕПЛЕНИЕ (ФИНАЛ)", callback_data="year_2027")
    
    # Подключаем учебный теоретический комплекс
    b.button(text="📖 ТЕОРЕТИЧЕСКИЙ СПРАВОЧНИК", callback_data="open_theory")
    
    await message.answer(
        "🎓 Комплекс **«ЦЭ 2027: НЕЙРО-НАСТАВНИК»**.\n\n"
        "Все учебные базы и теоретические модули успешно подключены!\n"
        "Выберите раздел для работы:", 
        reply_markup=b.adjust(2, 2, 1, 1).as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await show_main_menu(m, state, m.from_user.id, m.from_user.full_name)

@dp.callback_query(F.data == "open_theory")
async def process_theory_menu(c: types.CallbackQuery):
    """Меню выбора разделов теории по кодификатору РИКЗ"""
    b = InlineKeyboardBuilder()
    b.button(text="🔢 Числа и вычисления", callback_data="th_numbers")
    b.button(text="📐 Выражения и степени", callback_data="th_expressions")
    b.button(text="⚖️ Уравнения и неравенства", callback_data="th_equations")
    b.button(text="📈 Функции и их свойства", callback_data="th_functions")
    b.button(text="📐 Геометрия (2D и 3D)", callback_data="th_geometry")
    b.button(text="🎲 Вероятность и комбинаторика", callback_data="th_probability")
    b.button(text="⬅️ В главное меню", callback_data="back_to_start")
    
    await c.message.edit_text(
        "📖 **МЕТОДИЧЕСКИЙ СПРАВОЧНИК ЦЭ 2027**\n\n"
        "Выберите интересующий вас раздел математики для изучения теории и разбора ловушек РИКЗ:",
        reply_markup=b.adjust(1).as_markup()
    )

@dp.callback_query(F.data.startswith("th_"))
async def show_theory_content(c: types.CallbackQuery):
    """Вывод расширенного текста теории из файла theory_base.py"""
    try:
        from theory_base import THEORY_DATA
        text = THEORY_DATA.get(c.data, "⚠️ Раздел находится на наполнении.")
    except ImportError:
        text = "⚠️ Ошибка подключения модуля теории. Проверьте наличие theory_base.py на GitHub."
        
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад к разделам", callback_data="open_theory")
    b.button(text="🏠 В главное меню", callback_data="back_to_start")
    
    await c.message.edit_text(text, parse_mode="Markdown", reply_markup=b.adjust(1).as_markup())

@dp.callback_query(F.data.startswith("year_"))
async def process_year(c: types.CallbackQuery, state: FSMContext):
    year = int(c.data.split("_")[1])
    await state.update_data(year=year)
    
    b = InlineKeyboardBuilder()
    b.button(text="Вариант 1", callback_data="var_1")
    
    title_text = "Контрольный тест на закрепление" if year == 2027 else f"Сборник {year} года"
    await c.message.edit_text(f"Выбран: {title_text}. 📅\nТеперь выберите вариант:", reply_markup=b.adjust(1).as_markup())
    await state.set_state(TrainerStates.choosing_variant)

@dp.callback_query(F.data.startswith("var_"))
async def process_variant(c: types.CallbackQuery, state: FSMContext):
    var_num = int(c.data.split("_")[1])
    user_data = await state.get_data()
    year = int(user_data['year'])
    
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('UPDATE users SET current_year = ?, current_variant = ?, current_task_idx = 0, score = 0, errors_log = "" WHERE user_id = ?', (year, var_num, c.from_user.id))
    conn.commit()
    conn.close()
    
    await c.message.delete()
    await send_local_question(c.from_user.id, state)

async def send_local_question(uid: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    row = conn.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (uid,)).fetchone()
    conn.close()
    
    if not row:
        await bot.send_message(uid, "⚠️ Ошибка сессии. Нажмите /start.")
        return
        
    year, var, idx = row
    current_database = get_database_by_year(year)
    filtered_tasks = [t for t in current_database if t['year'] == year and t['variant'] == var]
    
    if not filtered_tasks:
        await bot.send_message(uid, f"⚠️ База данных для этого раздела ещё наполняется методистом.")
        return

    if idx >= len(filtered_tasks):
        conn = sqlite3.connect('ce_math_2027.db')
        score, logs = conn.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (uid,)).fetchone()
        conn.close()
        
        clean_logs = logs.strip().strip("•").strip() if logs else "Ошибок нет! Идеальный уровень закрепления материала! 🏆"
        
        b = InlineKeyboardBuilder()
        b.button(text="🔄 Вернуться в начало", callback_data="back_to_start")
        
        await bot.send_message(
            uid, 
            f"🎯 **Тест завершен!**\n\nИтоговый результат: *{score}* из {len(filtered_tasks)}.\n🔍 Зоны для повторения:\n_{clean_logs}_", 
            parse_mode="Markdown",
            reply_markup=b.as_markup()
        )
        await state.clear()
        return

    q = filtered_tasks[idx]
    await state.update_data(correct_idx=int(q['correct']), current_explain=q['explain'], current_topic=q['topic'])
    
    b = InlineKeyboardBuilder()
    for o_idx, opt in enumerate(q['options']): 
        b.button(text=f"{o_idx+1}) {opt}", callback_data=f"ans_{o_idx}")
        
    await bot.send_message(uid, f"📊 **Задание {q['task_num']} (Часть {q['type']})**\nРаздел: #{q['topic'].replace(' ', '_')}\n\n{q['question']}", reply_markup=b.adjust(1).as_markup())
    await state.set_state(TrainerStates.solving)

@dp.callback_query(F.data == "back_to_start")
async def handle_back_to_start(c: types.CallbackQuery, state: FSMContext):
    await c.message.delete()
    await show_main_menu(c.message, state, c.from_user.id, c.from_user.full_name)

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(c: types.CallbackQuery, state: FSMContext):
    ans = int(c.data.split("_")[1])
    d = await state.get_data()
    uid = c.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    if ans == d['correct_idx']:
        conn.execute('UPDATE users SET score = score + 1 WHERE user_id = ?', (uid,))
        txt = f"✅ **Абсолютно верно! Ловушка успешно обойдена.**\n\n{d['current_explain']}"
    else:
        log_res = conn.execute('SELECT errors_log FROM users WHERE user_id = ?', (uid,)).fetchone()
        log = log_res if log_res and log_res else ""
        if d['current_topic'] not in log: 
            conn.execute('UPDATE users SET errors_log = ? WHERE user_id = ?', (f"{log} • {d['current_topic']}", uid))
        txt = f"❌ **Попадание в капкан РИКЗ!**\n\n{d['current_explain']}"
        
    conn.execute('UPDATE users SET current_task_idx = current_task_idx + 1 WHERE user_id = ?', (uid,))
    conn.commit()
    conn.close()
    
    b = InlineKeyboardBuilder().button(text="Дальше ➡️", callback_data="next_local_task")
    await c.message.answer(txt, reply_markup=b.as_markup())

@dp.callback_query(F.data == "next_local_task")
async def handle_next(c: types.CallbackQuery, state: FSMContext):
    await c.message.delete()
    await send_local_question(c.from_user.id, state)

@dp.message(Command("report"))
async def make_report(m: types.Message):
    conn = sqlite3.connect('ce_math_2027.db')
    df = pd.read_sql_query("SELECT username AS 'Имя', score AS 'Баллы', errors_log AS 'Ошибки' FROM users", conn)
    conn.close()
    df.to_excel("Отчет.xlsx", index=False)
    await m.answer_document(types.FSInputFile("Отчет.xlsx"), caption="📊 Отчёт класса.")
    os.remove("Отчет.xlsx")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
