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

# Реальная учебная база данных заданий-аналогов напрямую в коде
RAW_TASKS = [
    (2023, 1, "А1", "А", "Обыкновенные дроби", "Среди значений переменной х, равных 16; 13; 14; 17; 15, укажите то, при котором дробь х/14 является правильной.", "13", "⚠️ Ловушка РИКЗ! По определению, дробь правильная, если числитель меньше знаменателя (х < 14). Подходит только 13."),
    (2023, 1, "А2", "А", "Алгебраические выражения", "Укажите номер выражения, которое является суммой двух последовательных натуральных чисел, меньшее из которых равно m.", "2m+1", "⚠️ Ловушка последовательности! Числа равны m и (m + 1). Их сумма: m + m + 1 = 2m + 1."),
    (2023, 1, "А3", "А", "Планиметрия. Окружность", "Если KM — диаметр, О — центр окружности, а угол LOK = 114° (точка L лежит на окружности), то градусная мера вписанного угла LMK равна:", "57", "⚠️ Ловушка углов! Вписанный угол LMK опирается на ту же дугу, что и центральный угол LOK. Он равен его половине: 114° / 2 = 57°."),
    (2023, 1, "А4", "А", "Системы неравенств", "Среди чисел √14; √6; √2; √19; √27 укажите то, которое является решением системы неравенств:\n[x ≥ 4,\n[x < 5.", "√19", "⚠️ Ловушка корней! Границы системы: √16 ≤ x < √25. Из предложенных чисел под этот промежуток подходит только √19."),
    (2023, 1, "А5", "А", "Свойства степенных функций", "Среди значений аргумента х, равных 1/81; 1/3; 1/64; 1/16; 1/100, укажите то, при котором f(x) = √х меньше 1/9.", "1/100", "⚠️ Ловушка знаков! √х < 1/9 => х < 1/81. Из всех дробей только 1/100 строго меньше 1/81."),
    (2023, 1, "А6", "А", "Нули функции", "Укажите номера функций, для которых аргумент -5 является нулем:\n1) f(x)=log₄(x+6)\n2) f(x)=x²-25\n3) f(x)=x²-6x+5\n4) f(x)=x-5\n5) f(x)=√(x+5)\nЗапишите цифры верных вариантов без пробелов (например: 125).", "125", "⚠️ Ловушка ОДЗ! При подстановке -5 в функции 1, 2 и 5 результат равен 0, и ОДЗ не нарушается."),
    (2023, 1, "А7", "А", "Текстовые задачи. Движение", "Мотоциклист за 4 ч проехал 48 км. За какое время (в минутах) он преодолеет в 1.5 раза больший путь с той же скоростью?", "360", "⚠️ Ловушка единиц времени! Скорость 12 км/ч. Новый путь: 48 * 1.5 = 72 км. Время: 72 / 12 = 6 часов. Переводим в минуты: 6 * 60 = 360 минут."),
    (2023, 1, "А8", "А", "Преобразование выражений с модулем", "Упростите выражение |a - 15| - |-8| при условии, что переменная a > 15.", "a-23", "⚠️ Ловушка раскрытия модуля! Так как a > 15, первый модуль раскрывается со знаком плюс: a - 15. Второй модуль |-8| = 8. Получаем: a - 15 - 8 = a - 23."),
    (2023, 1, "А9", "А", "Стереометрия", "ABCDA₁B₁C₁D₁ — прямоугольный параллелепипед: AB = 5, AD = 12, AA₁ = 2√7. Найдите длину пространственной ломаной B₁A₁CD.", "19", "⚠️ Ловушка 3D геометрии! Звенья равны: B₁A₁ = 5, A₁C = 13 (по Пифагору), CD = 5. Сумма: 5 + 13 + 5 = 19."),
    (2023, 1, "А10", "А", "Равносильные неравенства", "Какие пары равносильны:\n1) x≥√15 и x²≥15\n2) (x-12)²≥0 и x²-x+12>0\n3) 5x²>12x и 5x>12\n4) x²-x-20<0 и (x-5)(x+4)<0\n5) (0.5)ˣ<0.5 и x>1\nЗапишите цифры без пробелов.", "245", "⚠️ Ловушка равносильности! Пары 2, 4 и 5 имеют абсолютно идентичные множества решений."),
    (2023, 1, "В1", "В", "Признаки делимости", "Выберите верные утверждения:\n1) 438 кратно 3\n2) 275 кратно 9\n3) 890 кратно 10\n4) 512 кратно 4\n5) 315 кратно 6\nЗапишите цифры в порядке возрастания.", "134", "⚠️ Ловушка признаков! 1) 4+3+8=15 (делится); 3) делится на 10; 4) 12 делится на 4. Ответ: 134."),
    (2023, 1, "В4", "В", "Арифметическая прогрессия", "Дана арифметическая прогрессия: 30; 26; 22; ... Найдите сумму шести первых членов этой прогрессии.", "120", "⚠️ Ловушка знака! Разность d = -4. Находим a₆ = 30 + 5*(-4) = 10. Сумма S₆ = ((30 + 10) / 2) * 6 = 120."),
    (2023, 1, "В6", "В", "Тригонометрические выражения", "Найдите числовое значение выражения: 18√3 · tg(11π/3)", "-54", "⚠️ Ловушка периодов тангенса! tg(11π/3) = tg(-π/3) = -√3. Значение: 18√3 * (-√3) = 18 * (-3) = -54."),
    (2023, 1, "В8", "В", "Экономические задачи", "Через мобильный сервис куплен билет за 60 руб. (включая сбор 5 руб.). При возврате возвращают 80% стоимости самого билета. Сколько рублей потеряет покупатель?", "16", "⚠️ Ловушка базы! Билет стоит 55 р. Вернут 80% от 55 = 44 р. Потеря на билете 11 р. + сбор 5 р. = 16 р.")
]

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
    
    # Полностью очищаем старую зависшую таблицу перед заливкой
    cursor.execute('DELETE FROM exam_tasks')
    cursor.executemany('''
        INSERT INTO exam_tasks (year, variant, task_num, task_type, topic, question, correct_ans, explain_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', RAW_TASKS)
    
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    
    user_id = message.from_user.id
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, message.from_user.full_name))
    
    cursor.execute('SELECT COUNT(*) FROM exam_tasks')
    count = cursor.fetchone()[0]
    conn.close()
    
    # Стабильный, жестко зафиксированный список лет
    available_years = [2023]
    
    builder = InlineKeyboardBuilder()
    for year in available_years:
        builder.button(text=f"📚 Сборник {year} г.", callback_data=f"year_{year}")
    builder.adjust(2)
    
    await message.answer(
        f"Приветствуем! 👋 Вы запустили Всебелорусский ИИ-тренажёр **«ЦЭ 2027: БЕЗ ОШИБОК»**.\n\n"
        f"🔥 В систему успешно интегрировано: **{count}** экзаменационных заданий РИКЗ.\n\n"
        f"Выберите год сборника для тренировки:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(TrainerStates.choosing_year)

@dp.callback_query(F.data.startswith("year_"))
async def process_year(callback: types.CallbackQuery, state: FSMContext):
    year = int(callback.data.split("_")[1])
    await state.update_data(year=year)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Вариант 1", callback_data="var_1")
    builder.adjust(1)
    
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
    await send_db_question(user_id, state)

async def send_db_question(user_id: int, state: FSMContext):
    conn = sqlite3.connect('ce_math_2027.db')
    cursor = conn.cursor()
    cursor.execute('SELECT current_year, current_variant, current_task_idx FROM users WHERE user_id = ?', (user_id,))
    year, var, idx = cursor.fetchone()
    
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
        f"✏️ **Решите задачу и введите числовой ответ:**"
    )
    await state.set_state(TrainerStates.solving)

@dp.message(TrainerStates.solving)
async def check_answer(message: types.Message, state: FSMContext):user_ans = message.text.strip().lower()user_data = await state.get_data()t_id = user_data['current_task_id']user_id = message.from_user.idconn = sqlite3.connect('ce_math_2027.db')cursor = conn.cursor()cursor.execute('SELECT correct_ans, explain_text, topic FROM exam_tasks WHERE id = ?', (t_id,))correct_ans, explain, topic = cursor.fetchone()if str(user_ans) == str(correct_ans).strip().lower():cursor.execute('UPDATE users SET score = score + 1 WHERE user_id = ?', (user_id,))status_text = f"✅ Абсолютно верно!\n\n{explain}"else:cursor.execute('SELECT errors_log FROM users WHERE user_id = ?', (user_id,))res = cursor.fetchone()current_log = res[0] if res and res[0] else ""if topic not in current_log:new_log = f"{current_log} • {topic}"cursor.execute('UPDATE users SET errors_log = ? WHERE user_id = ?', (new_log, user_id))status_text = f"❌ Ошибка в ответе!\n\n{explain}"cursor.execute('UPDATE users SET current_task_idx = current_task_idx + 1 WHERE user_id = ?', (user_id,))conn.commit()conn.close()builder = InlineKeyboardBuilder()builder.button(text="Следующее задание ➡️", callback_data="next_db_task")await message.answer(status_text, reply_markup=builder.as_markup())@dp.callback_query(F.data == "next_db_task")async def handle_next(callback: types.CallbackQuery, state: FSMContext):await callback.message.delete()await send_db_question(callback.from_user.id, state)@dp.message(Command("report"))async def make_report(message: types.Message):conn = sqlite3.connect('ce_math_2027.db')df = pd.read_sql_query("SELECT username AS 'Имя', score AS 'Баллы', errors_log AS 'Ошибки' FROM users", conn)conn.close()file_name = "Отчет_Успеваемости.xlsx"df.to_excel(file_name, index=False)await message.answer_document(types.FSInputFile(file_name), caption="📊 Отчёт успеваемости класса.")os.remove(file_name)async def main():init_db()await dp.start_polling(bot)if name == 'main':asyncio.run(main())