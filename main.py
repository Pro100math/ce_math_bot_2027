import asyncio
import sqlite3
import logging
import os
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем нашу огромную базу задач из файла tasks.py
from tasks import DATABASE

TOKEN = "8839101630:AAEGaxK1Z7bOh2KbsiF4KlLFKSJQC0Mz_eo"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            score INTEGER DEFAULT 0,
            errors_log TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.full_name or "Абитуриент"
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"Приветствуем, {username}! 👋\n"
        f"Интеллектуальный ИИ-тренажёр **«ЦЭ 2027: Математика без ошибок»** готов.\n\n"
        f"В базу загружено **{len(DATABASE)}** реальных заданий ЦЭ (2023–2026 гг.) со всеми скрытыми ловушками РИКЗ!\n\n"
        f"Нажмите /test, чтобы запустить тестирование!", 
        parse_mode="Markdown"
    )

@dp.message(Command("test"))
async def start_test(message: types.Message):
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET score = 0, errors_log = "" WHERE user_id = ?', (message.from_user.id,))
    conn.commit()
    conn.close()
    await send_question(message.from_user.id, question_index=0)

async def send_question(user_id: int, question_index: int):
    if question_index >= len(DATABASE):
        conn = sqlite3.connect('ce_math_2027.db')
        cursor = conn.cursor()
        cursor.execute('SELECT score, errors_log FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        conn.close()
        
        score_val = res[0] if res else 0
        errors_val = res[1].strip().strip("•").strip() if res and res[1] else "Ошибок нет! Вы полностью готовы к ЦЭ на 100 баллов! 🏆"
        
        await bot.send_message(
            user_id, 
            f"🎯 **Тестирование успешно завершено!**\n\n"
            f"Ваш итоговый результат: *{score_val}* из {len(DATABASE)}.\n\n"
            f"🔍 Темы, где были допущены ошибки (требуют внимания):\n_{errors_val}_",
            parse_mode="Markdown"
        )
        return

    q = DATABASE[question_index]
    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(q["options"]):
        builder.button(text=f"{idx+1}) {opt}", callback_data=f"ans_{question_index}_{idx}")
    builder.adjust(1)
    
    await bot.send_message(
        user_id, 
        f"📊 **Задание {q['id']} (Часть {q['type']})**\n"
        f"Раздел: #{q['topic'].replace(' ', '_').replace('(','').replace(')','')}\n\n"
        f"{q['question']}", 
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery):
    _, q_idx, ans_idx = callback.data.split("_")
    q_idx, ans_idx = int(q_idx), int(ans_idx)
    q = DATABASE[q_idx]
    user_id = callback.from_user.id
    
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    
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
        
    conn.commit()
    conn.close()
    
    full_text = (
        f"📊 **Задание {q['id']} (Часть {q['type']})**\n"
        f"Раздел: #{q['topic'].replace(' ', '_').replace('(','').replace(')','')}\n\n"
        f"{q['question']}\n\n"
        f"---------------------------\n"
        f"{status_text}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующее задание ➡️", callback_data=f"next_{q_idx + 1}")
    await callback.message.edit_text(full_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("next_"))
async def handle_next(callback: types.CallbackQuery):
    next_idx = int(callback.data.split("_")[1])
    await callback.message.delete()
    await send_question(callback.from_user.id, next_idx)

@dp.message(Command("report"))
async def make_report(message: types.Message):
    conn = sqlite3.connect('ce_math_2027.db')
    df = pd.read_sql_query("SELECT username AS 'Имя ученика', score AS 'Баллы', errors_log AS 'Допущенные ошибки' FROM users", conn)
    conn.close()
    
    file_name = "Отчет_Успеваемости_ЦЭ_2027.xlsx"
    df.to_excel(file_name, index=False)
    
    file_input = types.FSInputFile(file_name)
    await message.answer_document(file_input, caption="📊 Актуальный отчёт успеваемости класса по ловушкам ЦЭ.")
    os.remove(file_name)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
