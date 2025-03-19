import asyncio
import json
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    SuccessfulPayment, PreCheckoutQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta

# Конфигурация
TOKEN = '7597499330:AAFV_qzG1EpcW6cxN-MY2ZJwcwVQWJFL9GQ'
ADMIN_IDS = [1089550963]
MODERATION_GROUP_ID = -1002655701588  # ID супергруппы модерации
CHANNEL_ID = -1002658221513  # ID канала публикаций
PAYMENT_TOKEN = 'YOUR_PAYMENT_PROVIDER_TOKEN'  # Замените на реальный токен платежной системы

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния FSM
class UserStates(StatesGroup):
    main_menu = State()
    adding_images = State()
    confirm_images = State()
    add_description = State()
    preview = State()
    remove_selection = State()
    admin_panel = State()
    enter_user_id = State()
    enter_balance = State()
    enter_vip_price = State()
    adding_vip = State()
    top_up_balance = State()

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                images TEXT,
                description TEXT,
                status TEXT CHECK(status IN ('draft', 'moderation', 'published', 'rejected')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_vip INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS vip_prices (
                price INTEGER PRIMARY KEY
            )
        ''')
        await db.commit()

# Клавиатуры
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить объявление", callback_data="additem")],
        [InlineKeyboardButton(text="VIP-объявление", callback_data="addvip")],
        [InlineKeyboardButton(text="Удалить объявление", callback_data="remove")],
        [InlineKeyboardButton(text="Админка", callback_data="admin")]
    ])

def get_back_kb(state):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"back_{state}")]
    ])

# Обработчик старта
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
        await db.commit()
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (message.from_user.id,))
        balance = (await cursor.fetchone())[0]
    await message.answer(f"Ваш бонусный баланс: {balance} баллов", reply_markup=get_main_kb())
    await state.clear()
    await state.set_state(UserStates.main_menu)

# Обработка обычных объявлений
@dp.callback_query(F.data == "additem", UserStates.main_menu)
async def add_item(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM ads WHERE user_id = ? AND status = "moderation"',
                                  (callback.from_user.id,))
        count = (await cursor.fetchone())[0]
    if count > 0:
        await callback.message.answer("У вас уже есть объявление на модерации. Дождитесь проверки.")
        return
    await callback.message.answer(
        "Отправьте фотографии по одной. После завершения нажмите 'Готово'",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done_images")],
            [InlineKeyboardButton(text="Назад", callback_data="back_main")]
        ])
    )
    await state.set_state(UserStates.adding_images)

@dp.message(UserStates.adding_images, F.photo)
async def process_image(message: Message, state: FSMContext):
    data = await state.get_data()
    images = data.get('images', [])
    images.append(message.photo[-1].file_id)
    await state.update_data(images=images)

@dp.callback_query(F.data == "done_images")
async def confirm_images(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('images'):
        await callback.message.answer("Сначала отправьте хотя бы одну фотографию")
        return
    await callback.message.answer(
        "Все фото добавлены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="confirm_images")],
            [InlineKeyboardButton(text="Добавить еще", callback_data="back_additem")]
        ])
    )
    await state.set_state(UserStates.confirm_images)

@dp.callback_query(F.data == "confirm_images")
async def add_description(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите описание объявления:")
    await state.set_state(UserStates.add_description)

@dp.message(UserStates.add_description)
async def save_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()
    if 'images' not in data or not data['images']:
        await message.answer("Ошибка: Фотографии не найдены. Пожалуйста, начните заново.", reply_markup=get_main_kb())
        await state.clear()
        return
    await bot.send_media_group(
        chat_id=message.chat.id,
        media=[{"type": "photo", "media": img} for img in data['images']]
    )
    await message.answer(
        f"Описание: {data['description']}\n\nОпубликовать?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Публикация", callback_data="publish_regular")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_ad")]
        ])
    )
    await state.set_state(UserStates.preview)

@dp.callback_query(F.data == "publish_regular")
async def publish_regular(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'images' not in data or not data['images']:
        await callback.message.answer("Ошибка: Фотографии не найдены. Пожалуйста, начните заново.", reply_markup=get_main_kb())
        await state.clear()
        return
    images_json = json.dumps(data['images'])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''
            INSERT INTO ads (user_id, images, description, status)
            VALUES (?, ?, ?, "moderation")
        ''', (callback.from_user.id, images_json, data['description']))
        await db.commit()
    try:
        media = [{"type": "photo", "media": img} for img in data['images']]
        await bot.send_media_group(MODERATION_GROUP_ID, media)
        await bot.send_message(
            MODERATION_GROUP_ID,
            f"Объявление от {callback.from_user.id}:\n{data['description']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Забанить", callback_data=f"ban_{callback.from_user.id}")]
            ])
        )
        await callback.message.answer("Объявление отправлено на модерацию!")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
    await state.clear()

# Обработка кнопок "Назад"
@dp.callback_query(F.data.startswith("back_"))
async def handle_back(callback: CallbackQuery, state: FSMContext):
    destination = callback.data.split("_")[1]
    if destination == "main":
        await cmd_start(callback.message, state)
    elif destination == "admin":
        if callback.from_user.id in ADMIN_IDS:
            await admin_panel(callback, state)
        else:
            await callback.answer("Нет доступа")
    else:
        await callback.message.answer("Непредвиденная ошибка навигации", reply_markup=get_main_kb())
    await state.clear()

# VIP объявления
@dp.callback_query(F.data == "addvip", UserStates.main_menu)
async def add_vip(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT price FROM vip_prices')
        price = await cursor.fetchone()
        price = price[0] if price else 50  # Цена по умолчанию
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (callback.from_user.id,))
        balance = (await cursor.fetchone())[0]
    if balance < price:
        await callback.message.answer(
            f"Недостаточно средств! Текущий баланс: {balance}. "
            f"Стоимость VIP-объявления: {price} баллов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пополнить баланс", callback_data="top_up")],
                [InlineKeyboardButton(text="Назад", callback_data="back_main")]
            ])
        )
        return
    await callback.message.answer(
        "Отправьте фото для VIP-объявления",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done_vip_images")],
            [InlineKeyboardButton(text="Назад", callback_data="back_main")]
        ])
    )
    await state.set_state(UserStates.adding_vip)

@dp.message(UserStates.adding_vip, F.photo)
async def process_vip_image(message: Message, state: FSMContext):
    data = await state.get_data()
    images = data.get('vip_images', [])
    images.append(message.photo[-1].file_id)
    await state.update_data(vip_images=images)

@dp.callback_query(F.data == "done_vip_images")
async def confirm_vip_images(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('vip_images'):
        await callback.message.answer("Добавьте хотя бы одну фотографию")
        return
    await callback.message.answer("Введите описание VIP-объявления:")
    await state.set_state(UserStates.add_description)

@dp.message(UserStates.add_description, UserStates.adding_vip)
async def save_vip_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()
    await bot.send_media_group(
        chat_id=message.chat.id,
        media=[{"type": "photo", "media": img} for img in data['vip_images']]
    )
    await message.answer(
        f"VIP-объявление:\n{data['description']}\n\nОпубликовать?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Опубликовать VIP", callback_data="publish_vip")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_ad")]
        ])
    )
    await state.set_state(UserStates.preview)

@dp.callback_query(F.data == "publish_vip")
async def publish_vip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    images_json = json.dumps(data['vip_images'])
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT price FROM vip_prices')
        price = (await cursor.fetchone())[0]
        await db.execute('''
            INSERT INTO ads (user_id, images, description, status, is_vip)
            VALUES (?, ?, ?, "moderation", 1)
        ''', (callback.from_user.id, images_json, data['description']))
        await db.commit()
    try:
        media = [{"type": "photo", "media": img} for img in data['vip_images']]
        await bot.send_media_group(MODERATION_GROUP_ID, media)
        await bot.send_message(
            MODERATION_GROUP_ID,
            f"VIP-объявление от {callback.from_user.id}:{data['description']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Одобрить VIP", callback_data=f"approve_vip_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Забанить", callback_data=f"ban_{callback.from_user.id}")]
            ])
        )
        await callback.message.answer("VIP-объявление отправлено на модерацию!")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
    await state.clear()

# Модерация
@dp.callback_query(F.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    is_vip = "vip" in callback.data
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('''
                SELECT id, images, description FROM ads 
                WHERE user_id = ? AND status = "moderation" AND is_vip = ?
            ''', (user_id, 1 if is_vip else 0))
        ad = await cursor.fetchone()
        if not ad:
            await callback.message.answer("Объявление не найдено")
            return
        ad_id, images_json, description = ad
        images = json.loads(images_json)
        await db.execute('UPDATE ads SET status = "published" WHERE id = ?', (ad_id,))
        if is_vip:
            await db.execute('UPDATE users SET balance = balance - (SELECT price FROM vip_prices) WHERE user_id = ?',
                             (user_id,))
        else:
            await db.execute('UPDATE users SET balance = balance + 10 WHERE user_id = ?', (user_id,))
        await db.commit()
        media = [{"type": "photo", "media": img} for img in images]
        await bot.send_media_group(CHANNEL_ID, media)
        msg = await bot.send_message(
            CHANNEL_ID,
            f"{'VIP: ' if is_vip else ''}{description}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Комментарии", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{msg.message_id}")]
            ]) if is_vip else None
        )
        if is_vip:
            try:
                await bot.pin_chat_message(CHANNEL_ID, msg.message_id)
            except TelegramBadRequest:
                pass
    await bot.send_message(user_id, "Ваше объявление опубликовано!")
    await callback.message.answer("Объявление одобрено")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE ads SET status = "rejected" WHERE user_id = ? AND status = "moderation"', (user_id,))
        await db.commit()
    await bot.send_message(user_id, "Ваше объявление отклонено")
    await callback.message.answer("Объявление отклонено")

@dp.callback_query(F.data.startswith("ban_"))
async def ban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        await db.execute('UPDATE ads SET status = "rejected" WHERE user_id = ?', (user_id,))
        await db.commit()
    await callback.message.answer(f"Пользователь {user_id} забанен")

# Удаление объявлений
@dp.callback_query(F.data == "remove", UserStates.main_menu)
async def remove_ad(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT id, description FROM ads WHERE user_id = ? AND status = ?',
                                  (callback.from_user.id, 'published'))
        ads = await cursor.fetchall()
    if not ads:
        await callback.message.answer("Нет активных объявлений")
        return
    buttons = []
    for ad_id, desc in ads:
        short_desc = desc[:20] + "..." if len(desc) > 20 else desc
        buttons.append([InlineKeyboardButton(text=short_desc, callback_data=f"del_{ad_id}")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_main")])
    await callback.message.answer(
        "Выберите объявление для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(UserStates.remove_selection)

@dp.callback_query(F.data.startswith("del_"), UserStates.remove_selection)
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split("_")[1])
    await state.update_data(ad_id=ad_id)
    await callback.message.answer(
        "Удалить объявление?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="confirm_delete")],
            [InlineKeyboardButton(text="Нет", callback_data="cancel_delete")]
        ])
    )

@dp.callback_query(F.data == "confirm_delete", UserStates.remove_selection)
async def delete_ad(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM ads WHERE id = ?', (data['ad_id'],))
        await db.commit()
    await callback.message.answer("Объявление удалено", reply_markup=get_main_kb())
    await state.clear()

# Подача обычного объявления
@dp.callback_query(F.data == "additem", UserStates.main_menu)
async def add_item(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect('bot.db') as db:
        count = await db.execute_fetchone(
            'SELECT COUNT(*) FROM ads WHERE user_id = ? AND status = ?',
            (callback.from_user.id, 'moderation')
        )
    if count[0] > 0:
        await callback.message.answer("У вас уже есть объявление на модерации. Дождитесь проверки.")
        return
    await callback.message.answer(
        "Отправьте фотографии по одной. После завершения нажмите 'Готово'",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done_images")],
            [InlineKeyboardButton(text="Назад", callback_data="back_main")]
        ])
    )
    await state.set_state(UserStates.adding_images)

@dp.message(UserStates.adding_images, F.photo)
async def process_image(message: Message, state: FSMContext):
    data = await state.get_data()
    images = data.get('images', [])
    images.append(message.photo[-1].file_id)
    await state.update_data(images=images)

@dp.callback_query(F.data == "done_images", UserStates.adding_images)
async def confirm_images(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('images'):
        await callback.message.answer("Сначала отправьте хотя бы одну фотографию")
        return
    await callback.message.answer(
        "Все фото добавлены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="confirm_images")],
            [InlineKeyboardButton(text="Добавить еще", callback_data="back_additem")]
        ])
    )
    await state.set_state(UserStates.confirm_images)

@dp.callback_query(F.data == "confirm_images", UserStates.confirm_images)
async def add_description(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите описание объявления:")
    await state.set_state(UserStates.add_description)

@dp.message(UserStates.add_description)
async def save_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()
    if 'images' not in data or not data['images']:
        await message.answer("Ошибка: Фотографии не найдены. Пожалуйста, начните заново.", reply_markup=get_main_kb())
        await state.clear()
        return
    media = [{"type": "photo", "media": img} for img in data['images']]
    await bot.send_media_group(chat_id=message.chat.id, media=media)
    await message.answer(
        f"Описание: {data['description']}\n"
        f"Опубликовать?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Публикация", callback_data="publish_regular")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_ad")]
        ])
    )
    await state.set_state(UserStates.preview)

@dp.callback_query(F.data == "publish_regular", UserStates.preview)
async def publish_regular(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    images_json = json.dumps(data['images'])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute(
            'INSERT INTO ads (user_id, images, description, status) VALUES (?, ?, ?, ?)',
            (callback.from_user.id, images_json, data['description'], 'moderation')
        )
        await db.commit()
    try:
        media = [{"type": "photo", "media": img} for img in data['images']]
        await bot.send_media_group(MODERATION_GROUP_ID, media)
        await bot.send_message(
            MODERATION_GROUP_ID,
            f"Объявление от {callback.from_user.id}:\n{data['description']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{callback.from_user.id}")],
                [InlineKeyboardButton(text="Забанить", callback_data=f"ban_{callback.from_user.id}")]
            ])
        )
        await callback.message.answer("Объявление отправлено на модерацию!")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
    await state.clear()

# Модерация объявлений
@dp.callback_query(F.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute(
            'SELECT id, images, description FROM ads WHERE user_id = ? AND status = ?',
            (user_id, 'moderation')
        )
        ad = await cursor.fetchone()
        if not ad:
            await callback.message.answer("Объявление не найдено")
            return
        ad_id, images_json, description = ad
        images = json.loads(images_json)
        await db.execute('UPDATE ads SET status = ? WHERE id = ?', ('published', ad_id))
        await db.execute('UPDATE users SET balance = balance + 10 WHERE user_id = ?', (user_id,))
        await db.commit()
        media = [{"type": "photo", "media": img} for img in images]
        await bot.send_media_group(CHANNEL_ID, media)
        msg = await bot.send_message(
            CHANNEL_ID,
            f"{description}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Комментарии", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{msg.message_id}")]
            ])
        )
    await bot.send_message(user_id, "Ваше объявление опубликовано!")
    await callback.message.answer("Объявление одобрено")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE ads SET status = ? WHERE user_id = ? AND status = ?', ('rejected', user_id, 'moderation'))
        await db.commit()
    await bot.send_message(user_id, "Ваше объявление отклонено")
    await callback.message.answer("Объявление отклонено")

@dp.callback_query(F.data.startswith("ban_"))
async def ban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        await db.execute('UPDATE ads SET status = ? WHERE user_id = ?', ('rejected', user_id))
        await db.commit()
    await callback.message.answer(f"Пользователь {user_id} забанен")

# Админ панель
@dp.callback_query(F.data == "admin", UserStates.main_menu)
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    await callback.message.answer(
        "Админ-панель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Бан", callback_data="admin_ban")],
            [InlineKeyboardButton(text="Разбан", callback_data="admin_unban")],
            [InlineKeyboardButton(text="Проверить баланс", callback_data="admin_check_balance")],
            [InlineKeyboardButton(text="Изменить баланс", callback_data="admin_modify_balance")],
            [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="Цена VIP", callback_data="admin_set_vip_price")],
            [InlineKeyboardButton(text="Назад", callback_data="back_main")]
        ])
    )
    await state.set_state(UserStates.admin_panel)

@dp.callback_query(F.data == "admin_ban", UserStates.admin_panel)
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя для бана:", reply_markup=get_back_kb("admin"))
    await state.set_state(UserStates.enter_user_id)

@dp.message(F.text, UserStates.enter_user_id)
async def process_ban(message: Message, state: FSMContext):
    user_id = message.text.strip()
    try:
        user_id = int(user_id)
    except ValueError:
        await message.answer("Введите корректный ID пользователя", reply_markup=get_back_kb("admin"))
        return
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        await db.execute('UPDATE ads SET status = ? WHERE user_id = ?', ('rejected', user_id))
        await db.commit()
    await message.answer(f"Пользователь {user_id} забанен", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_unban", UserStates.admin_panel)
async def admin_unban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя для разбана:", reply_markup=get_back_kb("admin"))
    await state.set_state(UserStates.enter_user_id)

@dp.message(F.text, UserStates.enter_user_id)
async def process_unban(message: Message, state: FSMContext):
    user_id = message.text.strip()
    try:
        user_id = int(user_id)
    except ValueError:
        await message.answer("Введите корректный ID пользователя", reply_markup=get_back_kb("admin"))
        return
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        await db.commit()
    await message.answer(f"Пользователь {user_id} разбанен", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_check_balance", UserStates.admin_panel)
async def admin_check_balance(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя:", reply_markup=get_back_kb("admin"))
    await state.set_state(UserStates.enter_user_id)

@dp.message(F.text, UserStates.enter_user_id)
async def process_check_balance(message: Message, state: FSMContext):
    user_id = message.text.strip()
    try:
        user_id = int(user_id)
    except ValueError:
        await message.answer("Введите корректный ID пользователя", reply_markup=get_back_kb("admin"))
        return
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
    if result:
        balance = result[0]
        await message.answer(f"Баланс пользователя {user_id}: {balance} баллов", reply_markup=get_main_kb())
    else:
        await message.answer("Пользователь не найден", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_modify_balance", UserStates.admin_panel)
async def admin_modify_balance(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя и новое значение баланса через пробел:", reply_markup=get_back_kb("admin"))
    await state.set_state(UserStates.enter_balance)

@dp.message(F.text, UserStates.enter_balance)
async def process_modify_balance(message: Message, state: FSMContext):
    try:
        user_id, new_balance = message.text.split()
        user_id = int(user_id)
        new_balance = int(new_balance)
    except ValueError:
        await message.answer("Неверный формат. Введите: ID новое_значение", reply_markup=get_back_kb("admin"))
        return
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        await db.commit()
    await message.answer(f"Баланс пользователя {user_id} изменен на {new_balance}", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_set_vip_price", UserStates.admin_panel)
async def admin_set_vip_price(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую цену VIP-объявления:", reply_markup=get_back_kb("admin"))
    await state.set_state(UserStates.enter_vip_price)

@dp.message(F.text, UserStates.enter_vip_price)
async def process_set_vip_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("Введите числовое значение", reply_markup=get_back_kb("admin"))
        return
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT OR REPLACE INTO vip_prices (price) VALUES (?)', (price,))
        await db.commit()
    await message.answer(f"Цена VIP установлена: {price} баллов", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_stats", UserStates.admin_panel)
async def admin_stats(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    month_ago = now - timedelta(days=30)
    half_year_ago = now - timedelta(days=180)
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('''
            SELECT COUNT(*), SUM(is_vip) FROM ads 
            WHERE created_at >= ? AND created_at <= ?
        ''', (month_ago.strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d')))
        monthly_stats = await cursor.fetchone()
        cursor = await db.execute('''
            SELECT COUNT(*), SUM(is_vip) FROM ads 
            WHERE created_at >= ? AND created_at <= ?
        ''', (half_year_ago.strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d')))
        half_year_stats = await cursor.fetchone()
    stats_text = (
        "Статистика объявлений:\n"
        f"За последний месяц:\n"
        f"- Всего: {monthly_stats[0]}\n"
        f"- VIP: {monthly_stats[1] or 0}\n"
        f"- Обычных: {monthly_stats[0] - (monthly_stats[1] or 0)}\n"
        f"За последние полгода:\n"
        f"- Всего: {half_year_stats[0]}\n"
        f"- VIP: {half_year_stats[1] or 0}\n"
        f"- Обычных: {half_year_stats[0] - (half_year_stats[1] or 0)}"
    )
    await callback.message.answer(stats_text, reply_markup=get_main_kb())
    await state.clear()

# Запуск бота
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())