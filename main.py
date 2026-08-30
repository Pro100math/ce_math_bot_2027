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

# Наша собственная, 100% легальная база задач-аналогов (Числа изменены)
DATABASE = [
    {
        "year": 2023, "variant": 1, "task_num": "А1", "type": "А", "topic": "Обыкновенные дроби",
        "question": "Среди значений переменной х, равных 16; 13; 14; 17; 15, укажите то, при котором дробь х/14 является правильной.",
        "options": ["16", "13", "14", "17"],
        "correct": 1,
        "explain": "⚠️ Ловушка РИКЗ! По определению, обыкновенная дробь является правильной, если её числитель строго меньше знаменателя (х < 14). Подходит только число 13."
    },
    {
        "year": 2023, "variant": 1, "task_num": "А2", "type": "А", "topic": "Алгебраические выражения",
        "question": "Укажите номер выражения, которое является суммой двух последовательных натуральных чисел, меньшее из которых равно m.",
        "options": ["2m - 2", "2m - 1", "m + 1", "2m + 1"],
        "correct": 3,
        "explain": "⚠️ Ловушка последовательности! Если меньшее число равно m, то следующее за ним равно (m + 1). Их сумма: m + (m + 1) = 2m + 1."
    },
    {
        "year": 2023, "variant": 1, "task_num": "А3", "type": "А", "topic": "Планиметрия. Окружность",
        "question": "Если KM — диаметр, О — центр окружности, а угол LOK = 114° (где точка L лежит на окружности), то градусная мера вписанного угла LMK равна:",
        "options": ["66°", "33°", "57°", "48°"],
        "correct": 2,
        "explain": "⚠️ Ловушка углов! Вписанный угол LMK опирается на ту же дугу LK, что и центральный угол LOK. По теореме он равен его половине: 114° / 2 = 57°."
    },
    {
        "year": 2023, "variant": 1, "task_num": "А4", "type": "А", "topic": "Системы неравенств",
        "question": "Среди чисел √14; √6; √2; √19; √27 укажите то, которое является решением системы неравенств:\n[x ≥ 4,\n[x < 5.",
        "options": ["√14", "√6", "√19", "√27"],
        "correct": 2,
        "explain": "⚠️ Ловушка иррациональности! Границы системы в виде корней: √16 ≤ x < √25. Из предложенного числового ряда подходит только число √19."
    },
    {
        "year": 2023, "variant": 1, "task_num": "А5", "type": "А", "topic": "Свойства степенных функций",
        "question": "Среди значений аргумента х, равных 1/81; 1/3; 1/64; 1/16; 1/100, укажите то, при котором значение функции f(x) = √х меньше 1/9.",
        "options": ["1/81", "1/64", "1/16", "1/100"],
        "correct": 3,
        "explain": "⚠️ Ловушка знаков сравнения! Решаем неравенство: √х < 1/9 => х < 1/81. Среди предложенных дробей только 1/100 строго меньше, чем 1/81."
    },
    {
        "year": 2023, "variant": 1, "task_num": "В1", "type": "В", "topic": "Признаки делимости",
        "question": "Выберите верные утверждения:\n1) число 438 кратно числу 3\n2) число 275 кратно числу 9\n3) число 890 кратно числу 10\n4) число 512 кратно числу 4\n\nОтвет запишите цифрами вариантов в порядке возрастания (например: 134).",
        "options": ["134", "124", "135", "234"],
        "correct": 0,
        "explain": "⚠️ Ловушка признаков делимости! 1) 4+3+8=15 (делится на 3) — верно; 3) оканчивается на 0 — верно; 4) 12 делится на 4 — верно. Правильный ответ: 134."
    },
    {
        "year": 2023, "variant": 1, "task_num": "В4", "type": "В", "topic": "Арифметическая прогрессия",
        "question": "Дана арифметическая прогрессия: 30; 26; 22; ... Найдите сумму шести первых членов этой прогрессии.",
        "options": ["120", "115", "105", "130"],
        "correct": 0,
        "explain": "⚠️ Ловушка знаков! Разность d = 26 - 30 = -4. Шестой член: a₆ = 30 + 5*(-4) = 10. Сумма: S₆ = ((30 + 10) / 2) * 6 = 120."
    }
]

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

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (m.from_user.id, m.from_user.full_name))
    conn.commit(); conn.close()
    
    available_years = [2023, 2024, 2025, 2026]
    b = InlineKeyboardBuilder()
    for y in available_years:
        b.button(text=f"📚 Сборник {y} г.", callback_data=f"year_{y}")
    
    await m.answer(
        "🎓 Комплекс **«ЦЭ 2027: БЕЗ ОШИБОК»**.\n\n"
        "Все задачи-аналоги зашиты в память бота и работают без задержек!\n"
        "Выберите год сборника для тренировки:", 
        reply_markup=b.adjust(2).as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.callback_query(F.data.startswith("year_"))
async def process_year(c: types.CallbackQuery, state: FSMContext):
    year = int(c.data.split("_")[1])
    await state.update_data(year=year)
    
    b = InlineKeyboardBuilder()
    b.button(text="Вариант 1", callback_data="var_1")
    
    await c.message.edit_text(f"Выбран сборник {year} года. 📅\nТеперь выберите вариант:", reply_markup=b.adjust(1).as_markup())
    await state.set_state(TrainerStates.choosing_variant)

@dp.callback_query(F.data.startswith("var_"))
async def process_variant(c: types.CallbackQuery, state: FSMContext):
    var_num = int(c.data.split("_")[1])
    user_data = await state.get_data()
    year = int(user_data['year'])
    
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('UPDATE users SET current_year = ?, current_variant = ?, current_task_idx = 0, score = 0, errors_log = "" WHERE user_id = ?', (year, var_num, c.from_user.id))
    conn.commit(); conn.close()
    
    await c.message.delete()
    await send_local_question(c.from_user.id, state)

async def send_local_question(uid: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    year, var, idx = conn.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (uid,)).fetchone()
    conn.close()
    
    # Фильтруем задачи из встроенного массива под выбранный год и вариант
    filtered_tasks = [t for t in DATABASE if t['year'] == year and t['variant'] == var]
    
    if idx >= len(filtered_tasks):
        conn = sqlite3.connect('ce_math_2027.db')
        score, logs = conn.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (uid,)).fetchone()
        conn.close()
        clean_logs = logs.strip().strip("•").strip() if logs else "Ошибок нет! Полная готовность к 100 баллам! 🏆"
        await bot.send_message(uid, f"🎯 **Тест завершен!**\n\nРезультат: *{score}* из {len(filtered_tasks)}.\n🔍 Темы для повторения:\n_{clean_logs}_", parse_mode="Markdown")
        await state.clear(); return

    q = filtered_tasks[idx]
    await state.update_data(correct_idx=int(q['correct']), current_explain=q['explain'], current_topic=q['topic'])
    
    b = InlineKeyboardBuilder()
    for o_idx, opt in enumerate(q['options']): 
        b.button(text=f"{o_idx+1}) {opt}", callback_data=f"ans_{o_idx}")
        
    await bot.send_message(uid, f"📊 **Задание {q['task_num']} (Часть {q['type']})**\nРаздел: #{q['topic'].replace(' ', '_')}\n\n{q['question']}", reply_markup=b.adjust(1).as_markup())
    await state.set_state(TrainerStates.solving)

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(c: types.CallbackQuery, state: FSMContext):
    ans = int(c.data.split("_")[1])
    d = await state.get_data()
    uid = c.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    if ans == d['correct_idx']:
        conn.execute('UPDATE users SET score = score + 1 WHERE user_id = ?', (uid,))
        txt = f"✅ **Верно!**\n\n{d['current_explain']}"
    else:
        log_res = conn.execute('SELECT errors_log FROM users WHERE user_id = ?', (uid,)).fetchone()
        log = log_res[0] if log_res and log_res[0] else ""
        if d['current_topic'] not in log: 
            conn.execute('UPDATE users SET errors_log = ? WHERE user_id = ?', (f"{log} • {d['current_topic']}", uid))
        txt = f"❌ **Ловушка РИКЗ!**\n\n{d['current_explain']}"
        
    conn.execute('UPDATE users SET current_task_idx = current_task_idx + 1 WHERE user_id = ?', (uid,))
    conn.commit(); conn.close()
    
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
