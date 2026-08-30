import asyncio
import sqlite3
import logging
import os
import aiohttp
import json
import re
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TrainerStates(StatesGroup):
    choosing_year = State()
    choosing_variant = State()
    solving = State()

MODELS_PROMPTS = {
    "А1": "Определение правильной обыкновенной дроби. Дай числовой ряд, спроси при каком x дробь правильная.",
    "А2": "Составление выражения суммы двух последовательных натуральных чисел, меньшее равно m.",
    "А3": "Геометрия. Свойства вписанного и центрального угла на одной дуге. Дай значение центрального угла, спроси вписанный угол.",
    "А4": "Система неравенств [x >= a, x < b], варианты ответов в виде квадратных корней.",
    "А5": "Свойства f(x) = sqrt(x). Дай неравенство sqrt(x) < 1/n и числовой ряд дробей.",
    "А6": "Нули 5 функций с ОДЗ. Найти при каком х результат 0 для отрицательного числа.",
    "А7": "Текстовая задача на движение с ловушкой перевода часов в минуты в конце.",
    "А8": "Упрощение выражения с модулями |a - x| - |-y| при условии a > x.",
    "А9": "Стереометрия. Длина пространственной ломаной по ребрам прямоугольного параллелепипеда.",
    "А10": "Теория множеств. Выбор номеров пар равносильных неравенств.",
    "В1": "Выбор утверждений на признаки делимости (на 3, 4, 6, 9, 10). Ответ цифрами по возрастанию.",
    "В4": "Арифметическая прогрессия. Сумма первых n членов убывающей прогрессии (d < 0).",
    "В6": "Тригонометрия. Значение n*sqrt(3) * tg(Alpha) с отбрасыванием периодов.",
    "В8": "Экономическая задача на проценты с изменением базы и невозвратным сервисным сбором."
}

async def generate_ai_task(task_num: str, year: int, variant: int):
    url = f"https://googleapis.com{GEMINI_API_KEY}"
    base_prompt = MODELS_PROMPTS.get(task_num, "Задача по математике повышенной сложности уровня ЦЭ.")
    
    prompt = f"""
    Ты составитель тестов РИКЗ в Беларуси. Сгенерируй аналог Задания {task_num} из сборника {year} года, вариант {variant}.
    Модель: {base_prompt}. Измени сюжет и числа, чтобы не нарушать авторские права, но сохрани ловушку РИКЗ!
    Выдай ответ СТРОГО в формате JSON на русском языке. Никакого другого текста вокруг!
    Формат ответа:
    {{"question": "текст", "options": ["Вариант1","Вариант2","Вариант3","Вариант4"], "correct": 0, "explain": "разбор ловушки"}}
    Где correct - строго число (индекс правильного ответа от 0 до 3).
    """
    
    # Включаем принудительный режим Structured Outputs
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=20) as response:
                if response.status == 200:
                    res_data = await response.json()
                    raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
                    return json.loads(raw_text.strip())
                else:
                    logging.error(f"Gemini API Error Code: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"Gemini Connection Exception: {e}")
        return None

def init_db():
    conn = sqlite3.connect('ce_math_2027.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            username TEXT, 
            score INTEGER DEFAULT 0, 
            current_year INTEGER, 
            current_variant INTEGER, 
            current_task_idx INTEGER DEFAULT 0, 
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
    conn.commit()
    conn.close()
    
    available_years = [2023, 2024, 2025, 2026]
    b = InlineKeyboardBuilder()
    for y in available_years:
        b.button(text=f"📚 Сборник {y} г.", callback_data=f"year_{y}")
    
    await m.answer(
        "🎓 Комплекс **«ЦЭ 2027: НЕЙРО-НАСТАВНИК»**.\n"
        "🤖 ИИ генерирует легальные аналоги задач РИКЗ на лету!\n\n"
        "Выберите год сборника для тренировки:", 
        reply_markup=b.adjust(2).as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.callback_query(F.data.startswith("year_"))
async def process_year(c: types.CallbackQuery, state: FSMContext):
    year = int(c.data.split("_")[1])
    await state.update_data(year=year)
    
    b = InlineKeyboardBuilder()
    for v in range(1, 11): 
        b.button(text=f"Вар {v}", callback_data=f"var_{v}")
        
    await c.message.edit_text("📅 Выберите номер варианта (1-10):", reply_markup=b.adjust(5).as_markup())
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
    await send_ai_question(c.from_user.id, state)

async def send_ai_question(uid: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    row = conn.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (uid,)).fetchone()
    conn.close()
    
    if not row:
        await bot.send_message(uid, "⚠️ Ошибка сессии. Нажмите /start.")
        return
        
    year, var, idx = row
    seq = ["А1", "А2", "А3", "А4", "А5", "А6", "А7", "А8", "А9", "А10", "В1", "В4", "В6", "В8"]
    
    if idx >= len(seq):
        conn = sqlite3.connect('ce_math_2027.db')
        score, logs = conn.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (uid,)).fetchone()
        conn.close()
        
        clean_logs = logs.strip().strip("•").strip() if logs else "Ошибок нет! Полная готовность к 100 баллам ЦЭ! 🏆"
        await bot.send_message(uid, f"🎯 **Тест завершен!**\n\nРезультат: *{score}* из {len(seq)}.\n🔍 Темы для повторения:\n_{clean_logs}_", parse_mode="Markdown")
        await state.clear()
        return

    task = seq[idx]
    msg = await bot.send_message(uid, f"🤖 *ИИ генерирует аналог задания {task}...*", parse_mode="Markdown")
    q = await generate_ai_task(task, year, var)
    await msg.delete()
    
    if not q or 'options' not in q or 'question' not in q:
        await bot.send_message(uid, "⚠️ Ошибка генерации или связи с ИИ. Нажмите /start для сброса.")
        return
        
    await state.update_data(correct_idx=int(q['correct']), current_explain=q['explain'], current_topic=task)
    
    b = InlineKeyboardBuilder()
    for o_idx, opt in enumerate(q['options']): 
        b.button(text=f"{o_idx+1}) {opt}", callback_data=f"ans_{o_idx}")
        
    await bot.send_message(uid, f"🤖 **Задание {task}** ({year} г. Вариант {var})\n\n{q['question']}", reply_markup=b.adjust(1).as_markup())
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
    conn.commit()
    conn.close()
    
    b = InlineKeyboardBuilder().button(text="Дальше ➡️", callback_data="next_ai_task")
    await c.message.answer(txt, reply_markup=b.as_markup())

@dp.callback_query(F.data == "next_ai_task")
async def handle_next(c: types.CallbackQuery, state: FSMContext):
    await c.message.delete()
    await send_ai_question(c.from_user.id, state)

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
