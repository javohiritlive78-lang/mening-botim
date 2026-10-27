import asyncio
import html
import logging
import os
import random
import re
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
)

# ================== SOZLAMALAR ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Token: BOT_TOKEN muhit o'zgaruvchisidan olinadi, bo'lmasa quyidagi qatorga YANGI tokenni yozing
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8603889269:AAE2H-QM1kpz0uwi0KmLVwVZUumjCbNMjgQ"
ADMIN_ID = 8327302562
OTZIV_CHAT_ID = "@vip_starsgift"  # Buyurtmalar boradigan kanal username yoki IDsi
# Baza doim bot.py yonida saqlanadi (qaysi papkadan ishga tushirilishidan qat'i nazar)
DB_PATH = os.getenv("DB_PATH") or os.path.join(BASE_DIR, "bot.db")

REF_REWARD = 2  # Taklif qilingan do'st kanallarga obuna bo'lsa beriladigan stars
RETURN_WINDOW = 72 * 3600  # chiqib ketgan do'st qaytishi uchun vaqt (72 soat)

# ---- Slot (Open) sozlamalari ----
SPIN_COST = 2  # bitta aylantirish narxi (Telegram hisobidan to'lanadigan stars)
WIN_EVERY = 4  # har nechanchi aylantirishda 777 tushadi
WIN_PRIZE = 5  # 777 tushganda botdagi balansga beriladigan stars

# Stars paketlari: {stars_soni: narx (so'm)}  — narxlarni o'zingizga moslab o'zgartiring
PACKS = {50: 12000, 100: 21000, 200: 44000, 500: 110000}
# Gift yechish uchun variantlar (stars)
GIFTS = (15, 25)

# Hisob to'ldirish uchun karta ma'lumoti (o'zingiznikini yozing)
CARD_INFO = (
    "💳 Karta raqami: <code>9860 1201 6397 2181</code>\n"
    "👤 Karta egasi: <b>N E</b>"
)

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti
BACKUP_INTERVAL = 24 * 3600  # Avtomatik zaxira oralig'i (soniya)

CREATOR = "@N_57001"
CREATED_DATE = "20/10/2026"

# ================== MATNLAR (UZ / RU) ==================
T = {
    "uz": {
        "welcome": "👋 Assalomu alaykum! Botimizga xush kelibsiz.",
        "main_menu": "💻 <b>Asosiy menyudasiz!</b>",
        "sub_text": (
            "❌ Kechirasiz, botimizdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak!\n\n"
            "{chs}\n\n👇 Obuna bo'lgach <b>✅ Tekshirish</b> tugmasini bosing."
        ),
        "check_btn": "✅ Tekshirish",
        "sub_first": "❌ Avval kanallarga obuna bo'ling!",
        "sub_not_all": "❌ Siz hali hamma kanalga obuna bo'lmadingiz!",
        "banned": "❌ Siz botdan bloklangansiz!",
        "stars_menu": "⭐️ <b>Telegram Stars sotib olish</b> ⭐️\n\nKerakli miqdorni tanlang:\n\n{lines}",
        "pack_line": "• {n} ta Stars = {price} so'm",
        "pack_btn": "⭐️ {n} ta Stars — {price} so'm",
        "no_funds": "❌ Hisobingizda yetarli mablag' mavjud emas!",
        "buy_ok": (
            "✅ <b>Stars xaridi muvaffaqiyatli amalga oshirildi!</b>\n\n"
            "⭐️ Miqdori: {n} ta Stars\n💵 Narxi: {price}\n"
            "💰 Balansingizdan yechildi va Starslar qo'shildi!"
        ),
        "withdraw_menu": (
            "🎁 <b>Gift yechish bo'limi</b> 🎁\n\n"
            "Hisobingizdagi starstan gift sifatida yechib olishingiz mumkin:\n\n{lines}"
        ),
        "gift_line": "• {n} ta Stars",
        "gift_btn": "🎁 {n} ta Stars yechish",
        "no_stars": "❌ Hisobingizda yetarli Stars mavjud emas! (Sizda: {have} ta ⭐️)",
        "withdraw_ok": (
            "✅ <b>Gift yechish so'rovingiz qabul qilindi!</b>\n\n"
            "⭐️ Miqdori: {n} ta Stars\n💰 Hisobingizdan yechildi.\n\n"
            "⏳ Admin ko'rib chiqadi, natija haqida xabar beramiz."
        ),
        "gift_done": "✅ <b>Giftingiz yuborildi!</b>\n\n⭐️ {n} ta Stars gift so'rovingiz bajarildi. Rahmat! 🎉",
        "gift_rejected": (
            "❌ <b>Gift so'rovingiz rad etildi.</b>\n\n"
            "⭐️ {n} ta Stars hisobingizga qaytarildi. Savol bo'lsa, ☎️ Murojaat orqali yozing."
        ),
        "ref_text": (
            "🗣 <b>Referal tizimi</b> 🗣\n\n🔗 Sizning havolangiz:\n<code>{link}</code>\n\n"
            "👥 Taklif qilgan do'stlaringiz: <b>{total}</b> ta\n"
            "✅ Hozir obuna bo'lib turganlar: <b>{active}</b> ta\n\n"
            "🎁 Har bir do'stingiz <b>barcha kanallarga obuna bo'lsa</b>, "
            "sizga <b>{reward} ta Stars</b> beriladi!"
        ),
        "ref_list_title": "👥 <b>Siz taklif qilganlar ro'yxati:</b>",
        "ref_line": "{i}. 👤 {label} | 🆔 <code>{rid}</code>\n    Status: {status}",
        "ref_ok": "✅ obuna bo'lgan",
        "ref_wait": "⏳ obuna bo'lmagan",
        "ref_left": "⚠️ chiqib ketgan (24 soatda qaytsa hisoblanadi)",
        "ref_expired": "🚫 24 soatda qaytmagan (hisoblanmaydi)",
        "ref_summary": "📊 <b>Natija:</b> ✅ {ok} ta obuna | ⏳ {wait} ta kutilmoqda | ⚠️ {left} ta chiqib ketgan",
        "ref_notify": (
            "🎉 Siz taklif qilgan <b>{name}</b> kanallarga obuna bo'ldi!\n"
            "⭐️ Hisobingizga <b>{reward} ta Stars</b> qo'shildi!"
        ),
        "orders_buy_title": "📦 <b>Stars xaridlaringiz:</b>",
        "orders_gift_title": "📦 <b>Gift yechish buyurtmalaringiz:</b>",
        "orders_none": "📭 <b>Sizda hali buyurtmalar yo'q</b>",
        "order_buy_line": "✅ ⭐️ {s} ta stars — 💵 {p}",
        "order_gift_line": "🎁 ⭐️ {s} ta stars gift yechish — {status}",
        "st_pending": "⏳ kutilmoqda",
        "st_done": "✅ bajarildi",
        "st_rejected": "❌ rad etildi",
        "account": (
            "👤 <b>Mening hisobim</b>\n\n🆔 ID: <code>{uid}</code>\n"
            "💰 Balans: <b>{bal}</b> so'm\n⭐️ Stars: <b>{stars}</b> ta"
        ),
        "topup_info": (
            "💰 <b>Hisob to'ldirish</b>\n\n{card}\n\n"
            "1️⃣ Yuqoridagi kartaga pul o'tkazing\n"
            "2️⃣ <b>📤 Chek yuborish</b> tugmasini bosing\n"
            "3️⃣ To'lov chekining rasmini yuboring\n\n"
            "Admin tekshirib, hisobingizni to'ldiradi ✅"
        ),
        "topup_btn": "📤 Chek yuborish",
        "topup_ask": (
            "📸 To'lov chekining <b>rasmini</b> yuboring (xohlasangiz, summani izohga yozing).\n"
            "Bekor qilish uchun /start bosing."
        ),
        "topup_need_photo": "⚠️ Iltimos, chek <b>rasmini</b> yuboring.",
        "topup_sent": "✅ Chekingiz adminga yuborildi. Tez orada hisobingiz to'ldiriladi 📨",
        "topup_ok": "🎉 Hisobingiz <b>{amount} so'm</b>ga to'ldirildi! 💰",
        "topup_no": "❌ Afsuski, to'lov chekingiz tasdiqlanmadi. Savol bo'lsa, ☎️ Murojaat orqali yozing.",
        "guide": (
            "📚 <b>Qo'llanma</b>\n\n"
            "1️⃣ <b>⭐️ Stars olish</b> — hisobingizdagi pul hisobiga Stars sotib oling.\n"
            "2️⃣ <b>💰 Hisob to'ldirish</b> — kartaga pul o'tkazib, chek yuboring.\n"
            "3️⃣ <b>🗣 Referal</b> — do'stlaringizni taklif qiling, har biri uchun {reward} ta Stars oling.\n"
            "4️⃣ <b>🎁 Gift yechish</b> — to'plagan Starslaringizni gift qilib oling.\n"
            "5️⃣ <b>🎟 Promokod</b> — promokodni yozing va sovg'a oling.\n"
            "6️⃣ <b>🏆 TOP referal</b> — eng faol foydalanuvchilar reytingi."
        ),
        "support_prompt": "✍️ <b>Savolingizni yozib qoldiring</b> — admin tez orada javob beradi 📨",
        "support_sent": "✅ Savolingiz adminga yuborildi. Tez orada javob beramiz 📨",
        "info": "ℹ️ <b>Ma'lumot</b>\n\n👨‍💻 Yaratuvchi: {creator}\n📅 Sana: {date}",
        "promo_ask": "🎟 <b>Promokod</b>\n\nPromokodni yozing 👇",
        "promo_ok_stars": "🎉 Promokod qabul qilindi!\n⭐️ Hisobingizga <b>{amount} ta Stars</b> qo'shildi!",
        "promo_ok_balance": "🎉 Promokod qabul qilindi!\n💰 Hisobingizga <b>{amount} so'm</b> qo'shildi!",
        "promo_bad": "❌ Bunday promokod topilmadi.",
        "promo_used": "⚠️ Siz bu promokodni allaqachon ishlatgansiz.",
        "promo_over": "😔 Bu promokodning limiti tugagan.",
        "top_title": "🏆 <b>TOP 10 — eng ko'p do'st taklif qilganlar</b>\n\n{lines}",
        "top_line": "{medal} {name} — <b>{n}</b> ta",
        "top_empty": "📭 Hozircha reyting bo'sh. Birinchi bo'ling! 🚀",
        "top_me": "📍 Sizning o'rningiz: <b>{rank}</b> ({n} ta taklif)",
        "top_me_none": "📍 Siz hali do'st taklif qilmagansiz. <b>🗣 Referal</b> bo'limidan havolangizni oling!",
        "lang_choose": "🌐 Tilni tanlang / Выберите язык:",
        "lang_set": "✅ Til o'zgartirildi: 🇺🇿 O'zbekcha",
        "cnt_title": "📊 <b>Majburiy kanallar va qo'shilganlar soni</b>\n\n{lines}",
        "cnt_line": "📢 {name} — 👥 <b>{n}</b> ta odam bot orqali qo'shilgan",
        "cnt_empty": "📭 Hozircha majburiy kanallar yo'q.",
    },
    "ru": {
        "welcome": "👋 Здравствуйте! Добро пожаловать в наш бот.",
        "main_menu": "💻 <b>Вы в главном меню!</b>",
        "sub_text": (
            "❌ Извините, чтобы пользоваться ботом, подпишитесь на следующие каналы!\n\n"
            "{chs}\n\n👇 После подписки нажмите <b>✅ Проверить</b>."
        ),
        "check_btn": "✅ Проверить",
        "sub_first": "❌ Сначала подпишитесь на каналы!",
        "sub_not_all": "❌ Вы подписались не на все каналы!",
        "banned": "❌ Вы заблокированы в боте!",
        "stars_menu": "⭐️ <b>Покупка Telegram Stars</b> ⭐️\n\nВыберите нужное количество:\n\n{lines}",
        "pack_line": "• {n} Stars = {price} сум",
        "pack_btn": "⭐️ {n} Stars — {price} сум",
        "no_funds": "❌ Недостаточно средств на счёте!",
        "buy_ok": (
            "✅ <b>Покупка Stars успешно выполнена!</b>\n\n"
            "⭐️ Количество: {n} Stars\n💵 Цена: {price}\n"
            "💰 Сумма списана с баланса, Stars зачислены!"
        ),
        "withdraw_menu": (
            "🎁 <b>Вывод подарка</b> 🎁\n\n"
            "Вы можете вывести Stars со счёта в виде подарка:\n\n{lines}"
        ),
        "gift_line": "• {n} Stars",
        "gift_btn": "🎁 Вывести {n} Stars",
        "no_stars": "❌ Недостаточно Stars! (У вас: {have} ⭐️)",
        "withdraw_ok": (
            "✅ <b>Заявка на вывод подарка принята!</b>\n\n"
            "⭐️ Количество: {n} Stars\n💰 Списано с вашего счёта.\n\n"
            "⏳ Админ рассмотрит заявку, мы сообщим о результате."
        ),
        "gift_done": "✅ <b>Ваш подарок отправлен!</b>\n\n⭐️ Заявка на {n} Stars выполнена. Спасибо! 🎉",
        "gift_rejected": (
            "❌ <b>Ваша заявка на подарок отклонена.</b>\n\n"
            "⭐️ {n} Stars возвращены на ваш счёт. Если есть вопросы, напишите через ☎️ Обращение."
        ),
        "ref_text": (
            "🗣 <b>Реферальная система</b> 🗣\n\n🔗 Ваша ссылка:\n<code>{link}</code>\n\n"
            "👥 Приглашено друзей: <b>{total}</b>\n"
            "✅ Сейчас подписаны: <b>{active}</b>\n\n"
            "🎁 За каждого друга, который <b>подпишется на все каналы</b>, "
            "вы получите <b>{reward} Stars</b>!"
        ),
        "ref_list_title": "👥 <b>Список приглашённых вами:</b>",
        "ref_line": "{i}. 👤 {label} | 🆔 <code>{rid}</code>\n    Статус: {status}",
        "ref_ok": "✅ подписан",
        "ref_wait": "⏳ не подписан",
        "ref_left": "⚠️ отписался (вернётся за 24 ч — засчитается)",
        "ref_expired": "🚫 не вернулся за 24 часа (не учитывается)",
        "ref_summary": "📊 <b>Итог:</b> ✅ {ok} подписаны | ⏳ {wait} ожидают | ⚠️ {left} отписались",
        "ref_notify": (
            "🎉 Приглашённый вами <b>{name}</b> подписался на каналы!\n"
            "⭐️ На ваш счёт зачислено <b>{reward} Stars</b>!"
        ),
        "orders_buy_title": "📦 <b>Ваши покупки Stars:</b>",
        "orders_gift_title": "📦 <b>Ваши заявки на вывод подарков:</b>",
        "orders_none": "📭 <b>У вас пока нет заказов</b>",
        "order_buy_line": "✅ ⭐️ {s} Stars — 💵 {p}",
        "order_gift_line": "🎁 ⭐️ Вывод {s} Stars — {status}",
        "st_pending": "⏳ ожидает",
        "st_done": "✅ выполнено",
        "st_rejected": "❌ отклонено",
        "account": (
            "👤 <b>Мой счёт</b>\n\n🆔 ID: <code>{uid}</code>\n"
            "💰 Баланс: <b>{bal}</b> сум\n⭐️ Stars: <b>{stars}</b>"
        ),
        "topup_info": (
            "💰 <b>Пополнение счёта</b>\n\n{card}\n\n"
            "1️⃣ Переведите деньги на карту выше\n"
            "2️⃣ Нажмите кнопку <b>📤 Отправить чек</b>\n"
            "3️⃣ Отправьте фото чека об оплате\n\n"
            "Админ проверит и пополнит ваш счёт ✅"
        ),
        "topup_btn": "📤 Отправить чек",
        "topup_ask": (
            "📸 Отправьте <b>фото</b> чека об оплате (при желании укажите сумму в подписи).\n"
            "Для отмены нажмите /start."
        ),
        "topup_need_photo": "⚠️ Пожалуйста, отправьте <b>фото</b> чека.",
        "topup_sent": "✅ Ваш чек отправлен админу. Счёт скоро будет пополнен 📨",
        "topup_ok": "🎉 Ваш счёт пополнен на <b>{amount} сум</b>! 💰",
        "topup_no": "❌ К сожалению, ваш чек не подтверждён. Если есть вопросы, напишите через ☎️ Обращение.",
        "guide": (
            "📚 <b>Инструкция</b>\n\n"
            "1️⃣ <b>⭐️ Купить Stars</b> — покупайте Stars за деньги на счёте.\n"
            "2️⃣ <b>💰 Пополнить счёт</b> — переведите деньги на карту и отправьте чек.\n"
            "3️⃣ <b>🗣 Рефералы</b> — приглашайте друзей и получайте по {reward} Stars за каждого.\n"
            "4️⃣ <b>🎁 Вывод подарка</b> — выводите накопленные Stars в виде подарка.\n"
            "5️⃣ <b>🎟 Промокод</b> — введите промокод и получите бонус.\n"
            "6️⃣ <b>🏆 ТОП рефералов</b> — рейтинг самых активных пользователей."
        ),
        "support_prompt": "✍️ <b>Напишите свой вопрос</b> — админ скоро ответит 📨",
        "support_sent": "✅ Ваш вопрос отправлен админу. Скоро ответим 📨",
        "info": "ℹ️ <b>Информация</b>\n\n👨‍💻 Создатель: {creator}\n📅 Дата: {date}",
        "promo_ask": "🎟 <b>Промокод</b>\n\nНапишите промокод 👇",
        "promo_ok_stars": "🎉 Промокод принят!\n⭐️ На ваш счёт зачислено <b>{amount} Stars</b>!",
        "promo_ok_balance": "🎉 Промокод принят!\n💰 На ваш счёт зачислено <b>{amount} сум</b>!",
        "promo_bad": "❌ Такой промокод не найден.",
        "promo_used": "⚠️ Вы уже использовали этот промокод.",
        "promo_over": "😔 Лимит этого промокода исчерпан.",
        "top_title": "🏆 <b>ТОП 10 — больше всех пригласивших друзей</b>\n\n{lines}",
        "top_line": "{medal} {name} — <b>{n}</b>",
        "top_empty": "📭 Рейтинг пока пуст. Станьте первым! 🚀",
        "top_me": "📍 Ваше место: <b>{rank}</b> (приглашено: {n})",
        "top_me_none": "📍 Вы ещё никого не пригласили. Возьмите ссылку в разделе <b>🗣 Рефералы</b>!",
        "lang_choose": "🌐 Tilni tanlang / Выберите язык:",
        "lang_set": "✅ Язык изменён: 🇷🇺 Русский",
        "cnt_title": "📊 <b>Обязательные каналы и количество подписавшихся</b>\n\n{lines}",
        "cnt_line": "📢 {name} — 👥 <b>{n}</b> чел. подписались через бота",
        "cnt_empty": "📭 Обязательных каналов пока нет.",
    },
}

BTN = {
    "uz": {
        "stars": "⭐️ Stars olish",
        "withdraw": "🎁 Gift yechish",
        "orders": "📦 Buyurtmalar",
        "account": "👤 Mening hisobim",
        "ref": "🗣 Referal",
        "topup": "💰 Hisob to'ldirish",
        "promo": "🎟 Promokod",
        "top": "🏆 TOP referal",
        "support": "☎️ Murojaat",
        "guide": "📚 Qo'llanma",
        "info": "ℹ️ Ma'lumot",
        "slot": "🎰 Open",
        "lang": "🌐 Til",
        "son": "📊 Son",
        "admin": "🛠 Admin panel",
    },
    "ru": {
        "stars": "⭐️ Купить Stars",
        "withdraw": "🎁 Вывод подарка",
        "orders": "📦 Заказы",
        "account": "👤 Мой счёт",
        "ref": "🗣 Рефералы",
        "topup": "💰 Пополнить счёт",
        "promo": "🎟 Промокод",
        "top": "🏆 ТОП рефералов",
        "support": "☎️ Обращение",
        "guide": "📚 Инструкция",
        "info": "ℹ️ Информация",
        "slot": "🎰 Open",
        "lang": "🌐 Язык",
        "son": "📊 Количество",
        "admin": "🛠 Admin panel",
    },
}

BTN_REV = {text: key for lang in BTN for key, text in BTN[lang].items()}
ALL_BTNS = set(BTN_REV)


def tr(lang: str, key: str, **kw) -> str:
    text = T.get(lang, T["uz"]).get(key) or T["uz"][key]
    return text.format(**kw) if kw else text


def btn(lang: str, key: str) -> str:
    return BTN.get(lang, BTN["uz"])[key]


router = Router()


class States(StatesGroup):
    waiting_support = State()
    waiting_channel = State()
    waiting_ban = State()
    waiting_topup = State()
    waiting_minus = State()
    waiting_st_plus = State()
    waiting_st_minus = State()
    waiting_reply = State()
    waiting_broadcast = State()
    ad_pick = State()
    ad_text = State()
    waiting_promo = State()
    waiting_receipt = State()
    promo_new = State()
    topup_amount = State()
    waiting_find = State()
    sched_msg = State()
    sched_time = State()


# ================== YORDAMCHI ==================
def user_label(full_name, username) -> str:
    name = html.escape(full_name or "Noma'lum")
    uname = f"@{html.escape(username)}" if username else "username yo'q"
    return f"<b>{name}</b> ({uname})"


def parse_int(text: str) -> int | None:
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else None


def fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M")


async def send_chunks(message: Message, lines: list[str], per_chunk: int = 20, sep: str = "\n\n"):
    for i in range(0, len(lines), per_chunk):
        await message.answer(sep.join(lines[i:i + per_chunk]))


def topup_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=tr(lang, "topup_btn"), callback_data="send_receipt")]]
    )


# ================== BAZA ==================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,
                referrer_id INTEGER,
                rewarded INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                lang TEXT DEFAULT 'uz',
                joined_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stars INTEGER,
                price TEXT
            );
            CREATE TABLE IF NOT EXISTS withdraws(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stars INTEGER,
                status TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS channels(
                username TEXT PRIMARY KEY,
                title TEXT
            );
            CREATE TABLE IF NOT EXISTS promo_codes(
                code TEXT PRIMARY KEY,
                kind TEXT,
                amount INTEGER,
                max_uses INTEGER DEFAULT 0,
                used INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS promo_uses(
                code TEXT,
                user_id INTEGER,
                PRIMARY KEY(code, user_id)
            );
            CREATE TABLE IF NOT EXISTS topups(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                ftype TEXT,
                caption TEXT,
                amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS scheduled(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT,
                message_id INTEGER,
                run_at INTEGER,
                done INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS star_payments(
                charge_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                created_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS ch_joins(
                username TEXT,
                user_id INTEGER,
                joined_at INTEGER,
                PRIMARY KEY(username, user_id)
            );
            """
        )
        # Baza avval yaratilgan bo'lsa, yangi ustunlarni qo'shib qo'yish
        for ddl in (
            "ALTER TABLE users ADD COLUMN stars INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'",
            "ALTER TABLE users ADD COLUMN joined_at INTEGER",
            "ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN left_at INTEGER",
            "ALTER TABLE users ADD COLUMN spin_count INTEGER DEFAULT 0",
        ):
            try:
                await db.execute(ddl)
            except Exception:
                pass
        try:
            # Ustun bir marta qo'shiladi: eski foydalanuvchilar ref_new=0 bo'ladi, yangilari 1
            await db.execute("ALTER TABLE users ADD COLUMN ref_new INTEGER DEFAULT 1")
            await db.execute("UPDATE users SET ref_new=0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE withdraws ADD COLUMN status TEXT DEFAULT 'pending'")
            # Eski so'rovlar allaqachon ko'rib chiqilgan deb hisoblanadi
            await db.execute("UPDATE withdraws SET status='done'")
        except Exception:
            pass

        cur = await db.execute("SELECT COUNT(*) FROM channels")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT OR IGNORE INTO channels(username, title) VALUES(?, ?)",
                [("@Luckasuzb", "📢 Luckasuzb"), ("@vip_starsgift", "📢 VIP Stars Gift")],
            )
        await db.commit()


async def safe_fetchone(sql: str, params: tuple = ()):
    """Jadval yo'q bo'lib qolsa (baza o'chirilgan/almashtirilgan), bazani qayta yaratib so'rovni takrorlaydi."""
    for attempt in (1, 2):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(sql, params)
                return await cur.fetchone()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e) and attempt == 1:
                logging.warning("Jadval topilmadi, baza qayta yaratilmoqda: %s", DB_PATH)
                await init_db()
                continue
            raise


async def get_channels() -> list[tuple[str, str]]:
    for attempt in (1, 2):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT username, title FROM channels")
                return await cur.fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e) and attempt == 1:
                await init_db()
                continue
            raise


async def get_lang(uid: int) -> str:
    row = await safe_fetchone("SELECT lang FROM users WHERE id=?", (uid,))
    return row[0] if row and row[0] in ("uz", "ru") else "uz"


async def add_user(user, ref: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE id=?", (user.id,))
        exists = await cur.fetchone()
        if not exists:
            ref_ok = None
            if ref and ref != user.id:
                c2 = await db.execute("SELECT 1 FROM users WHERE id=?", (ref,))
                if await c2.fetchone():
                    ref_ok = ref
            await db.execute(
                "INSERT INTO users(id, username, full_name, referrer_id, joined_at) VALUES(?,?,?,?,?)",
                (user.id, user.username, user.full_name, ref_ok, int(time.time())),
            )
        else:
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE id=?",
                (user.username, user.full_name, user.id),
            )
        await db.commit()


async def get_user_data(uid: int) -> tuple[int, int]:
    row = await safe_fetchone("SELECT balance, stars FROM users WHERE id=?", (uid,))
    return (row[0], row[1]) if row else (0, 0)


def main_kb(uid: int, lang: str) -> ReplyKeyboardMarkup:
    b = lambda k: KeyboardButton(text=btn(lang, k))  # noqa: E731
    rows = [
        [b("stars"), b("withdraw")],
        [b("orders"), b("account")],
        [b("ref"), b("topup")],
        [b("promo"), b("top")],
        [b("support"), b("guide")],
        [b("slot"), b("son")],
        [b("info"), b("lang")],
    ]
    if uid == ADMIN_ID:
        rows.append([b("admin")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def sub_kb(channels: list[tuple[str, str]], lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, url=f"https://t.me/{username.lstrip('@')}")]
        for username, title in channels
    ]
    rows.append([InlineKeyboardButton(text=tr(lang, "check_btn"), callback_data="check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================== MAJBURIY OBUNA ==================
def _is_member(m) -> bool:
    if m.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        return False
    if m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", True) is False:
        return False
    return True


async def get_missing(bot: Bot, uid: int) -> list[tuple[str, str]]:
    missing = []
    for ch, title in await get_channels():
        try:
            m = await bot.get_chat_member(ch, uid)
            if not _is_member(m):
                missing.append((ch, title))
        except Exception as e:
            logging.warning("get_chat_member xato (%s): %s", ch, e)
    return missing


def sub_text(missing: list[tuple[str, str]], lang: str) -> str:
    return tr(lang, "sub_text", chs="\n".join(f"📢 {ch}" for ch, _ in missing))


# ================== REFERAL MUKOFOTI ==================
async def try_reward_referrer(bot: Bot, uid: int, already_checked: bool = False) -> bool:
    """True qaytarsa — do'st hozir hisoblanadi (mukofot berilgan)."""
    if not already_checked and await get_missing(bot, uid):
        return False
    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT referrer_id, full_name, rewarded, left_at FROM users WHERE id=?", (uid,)
        )
        row = await cur.fetchone()
        if not row or row[0] is None:
            return False
        referrer_id, full_name, rewarded, left_at = row
        if rewarded == 1:
            return True
        if left_at is not None and now - left_at > RETURN_WINDOW:
            return False  # 24 soatdan o'tib ketgan
        cur = await db.execute(
            "UPDATE users SET rewarded=1, left_at=NULL WHERE id=? AND rewarded=0", (uid,)
        )
        if cur.rowcount == 0:
            await db.commit()
            return True
        await db.execute("UPDATE users SET stars = stars + ? WHERE id=?", (REF_REWARD, referrer_id))
        await db.commit()

    try:
        ref_lang = await get_lang(referrer_id)
        await bot.send_message(
            referrer_id,
            tr(ref_lang, "ref_notify", name=html.escape(full_name or "user"), reward=REF_REWARD),
        )
    except Exception:
        pass
    return True


async def mark_left(uid: int):
    """Do'st kanaldan chiqib ketdi: hisobdan chiqariladi, 24 soat ichida qaytsa yana qo'shiladi."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT referrer_id, ref_new FROM users WHERE id=? AND rewarded=1", (uid,))
        row = await cur.fetchone()
        if not row:
            return
        referrer_id, ref_new = row
        # Eski (ref_new=0) lar qaytib kela olmaydi: left_at=1 => muddati o'tgan
        cur = await db.execute(
            "UPDATE users SET rewarded=0, left_at=? WHERE id=? AND rewarded=1",
            (now if ref_new == 1 else 1, uid),
        )
        if cur.rowcount and ref_new == 1 and referrer_id:
            await db.execute(
                "UPDATE users SET stars = MAX(stars - ?, 0) WHERE id=?", (REF_REWARD, referrer_id)
            )
        await db.commit()


# ================== MIDDLEWARE (BAN + OBUNA) ==================
class SubMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        if not user:
            return await handler(event, data)

        row = await safe_fetchone("SELECT is_banned, lang FROM users WHERE id=?", (user.id,))
        lang = row[1] if row and row[1] in ("uz", "ru") else "uz"
        if row and row[0] == 1:
            if isinstance(event, Message):
                await event.answer(tr(lang, "banned"))
            elif isinstance(event, CallbackQuery):
                await event.answer(tr(lang, "banned"), show_alert=True)
            return

        if isinstance(event, CallbackQuery):
            msg = event.message
            if msg is None or msg.chat.type != "private":
                return await handler(event, data)
            if event.data == "check" or user.id == ADMIN_ID:
                return await handler(event, data)
            missing = await get_missing(event.bot, user.id)
            if not missing:
                return await handler(event, data)
            await event.answer(tr(lang, "sub_first"), show_alert=True)
            return

        # To'lov xabari obuna tekshiruvida yo'qolmasligi uchun
        if getattr(event, "successful_payment", None):
            return await handler(event, data)

        if event.chat.type != "private":
            return
        text = event.text or ""

        if text.startswith("/start"):
            return await handler(event, data)

        await add_user(user)
        if user.id == ADMIN_ID:
            return await handler(event, data)

        missing = await get_missing(event.bot, user.id)
        if not missing:
            return await handler(event, data)

        await event.answer(sub_text(missing, lang), reply_markup=sub_kb(missing, lang))


# ================== /start ==================
@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    ref = int(command.args) if command.args and command.args.isdigit() else None
    await add_user(m.from_user, ref)
    lang = await get_lang(m.from_user.id)
    missing = [] if m.from_user.id == ADMIN_ID else await get_missing(m.bot, m.from_user.id)
    if not missing:
        await m.answer(tr(lang, "welcome"), reply_markup=main_kb(m.from_user.id, lang))
        await record_joins(m.from_user.id)
        await try_reward_referrer(m.bot, m.from_user.id, already_checked=True)
    else:
        await m.answer(sub_text(missing, lang), reply_markup=sub_kb(missing, lang))


@router.callback_query(F.data == "check")
async def check(c: CallbackQuery):
    await add_user(c.from_user)
    lang = await get_lang(c.from_user.id)
    missing = await get_missing(c.bot, c.from_user.id)
    if not missing:
        try:
            await c.message.delete()
        except Exception:
            pass
        await c.message.answer(tr(lang, "main_menu"), reply_markup=main_kb(c.from_user.id, lang))
        await c.answer()
        await record_joins(c.from_user.id)
        await try_reward_referrer(c.bot, c.from_user.id, already_checked=True)
    else:
        await c.answer(tr(lang, "sub_not_all"), show_alert=True)


# ================== TIL TANLASH ==================
@router.callback_query(F.data.in_({"lang_uz", "lang_ru"}))
async def set_language(c: CallbackQuery):
    new_lang = c.data.replace("lang_", "")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET lang=? WHERE id=?", (new_lang, c.from_user.id))
        await db.commit()
    try:
        await c.message.delete()
    except Exception:
        pass
    await c.message.answer(tr(new_lang, "lang_set"), reply_markup=main_kb(c.from_user.id, new_lang))
    await c.answer()


# ================== REFERAL BO'LIMI (JONLI OBUNA HOLATI BILAN) ==================
async def show_referrals(m: Message, uid: int, lang: str):
    me = await m.bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, full_name, username, rewarded, left_at FROM users WHERE referrer_id=? ORDER BY rowid",
            (uid,),
        )
        invited = await cur.fetchall()

    # Jonli tekshiruv: 5 tadan parallel, eng ko'pi bilan 100 ta (Telegram limitiga tushmaslik uchun)
    sem = asyncio.Semaphore(5)

    async def check_one(rid: int) -> tuple[int, bool]:
        async with sem:
            return rid, not await get_missing(m.bot, rid)

    live: dict[int, bool] = {}
    if invited:
        results = await asyncio.gather(*(check_one(r[0]) for r in invited[:100]))
        live = dict(results)

    lines: list[str] = []
    ok_n = wait_n = left_n = 0
    now = int(time.time())
    for i, (rid, name, uname, rewarded, left_at) in enumerate(invited, 1):
        subscribed = live.get(rid)
        if subscribed is None:
            subscribed = rewarded == 1

        if subscribed:
            if await try_reward_referrer(m.bot, rid, already_checked=True):
                status_key = "ref_ok"
                ok_n += 1
            else:
                status_key = "ref_expired"
                left_n += 1
        elif rewarded == 1:
            await mark_left(rid)
            status_key = "ref_left"
            left_n += 1
        elif left_at is not None:
            status_key = "ref_expired" if now - left_at > RETURN_WINDOW else "ref_left"
            left_n += 1
        else:
            status_key = "ref_wait"
            wait_n += 1

        label = f'<a href="tg://user?id={rid}">{html.escape(name or "Noma`lum")}</a>'
        if uname:
            label += f" (@{html.escape(uname)})"
        lines.append(tr(lang, "ref_line", i=i, label=label, rid=rid, status=tr(lang, status_key)))

    await m.answer(
        tr(lang, "ref_text", link=link, total=len(invited), active=ok_n, reward=REF_REWARD)
    )
    if lines:
        await m.answer(tr(lang, "ref_list_title"))
        await send_chunks(m, lines, per_chunk=20, sep="\n\n")
        await m.answer(tr(lang, "ref_summary", ok=ok_n, wait=wait_n, left=left_n))


# ================== ASOSIY MENYU ==================
@router.message(F.text.in_(ALL_BTNS))
async def menu(m: Message, state: FSMContext):
    await state.clear()
    key = BTN_REV[m.text]
    uid = m.from_user.id
    lang = await get_lang(uid)

    if key == "stars":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=tr(lang, "pack_btn", n=n, price=f"{p:,}"), callback_data=f"buy_{n}")]
                for n, p in PACKS.items()
            ]
        )
        lines = "\n".join(tr(lang, "pack_line", n=n, price=f"{p:,}") for n, p in PACKS.items())
        await m.answer(tr(lang, "stars_menu", lines=lines) + "\n\n" + CARD_INFO, reply_markup=kb)

    elif key == "withdraw":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=tr(lang, "gift_btn", n=n), callback_data=f"withdraw_{n}")]
                for n in GIFTS
            ]
        )
        lines = "\n".join(tr(lang, "gift_line", n=n) for n in GIFTS)
        await m.answer(tr(lang, "withdraw_menu", lines=lines), reply_markup=kb)

    elif key == "ref":
        await show_referrals(m, uid, lang)

    elif key == "orders":
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT stars, price FROM orders WHERE user_id=? ORDER BY id DESC", (uid,))
            rows = await cur.fetchall()
            cur2 = await db.execute("SELECT stars, status FROM withdraws WHERE user_id=? ORDER BY id DESC", (uid,))
            w_rows = await cur2.fetchall()

        text_parts = []
        if rows:
            lines = [tr(lang, "order_buy_line", s=s, p=p) for s, p in rows]
            text_parts.append(tr(lang, "orders_buy_title") + "\n" + "\n".join(lines))
        if w_rows:
            smap = {"pending": "st_pending", "done": "st_done", "rejected": "st_rejected"}
            w_lines = [
                tr(lang, "order_gift_line", s=s, status=tr(lang, smap.get(st or "pending", "st_pending")))
                for s, st in w_rows
            ]
            text_parts.append(tr(lang, "orders_gift_title") + "\n" + "\n".join(w_lines))

        await m.answer("\n\n".join(text_parts) if text_parts else tr(lang, "orders_none"))

    elif key == "account":
        bal, stars = await get_user_data(uid)
        await m.answer(
            tr(lang, "account", uid=uid, bal=bal, stars=stars) + "\n\n" + CARD_INFO,
            reply_markup=topup_kb(lang),
        )

    elif key == "topup":
        await m.answer(tr(lang, "topup_info", card=CARD_INFO), reply_markup=topup_kb(lang))

    elif key == "guide":
        await m.answer(tr(lang, "guide", reward=REF_REWARD) + "\n\n" + CARD_INFO)

    elif key == "support":
        await state.set_state(States.waiting_support)
        await m.answer(tr(lang, "support_prompt"))

    elif key == "info":
        await m.answer(tr(lang, "info", creator=CREATOR, date=CREATED_DATE))

    elif key == "promo":
        await state.set_state(States.waiting_promo)
        await m.answer(tr(lang, "promo_ask"))

    elif key == "top":
        await show_top(m, uid, lang)

    elif key == "lang":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
            ]
        )
        await m.answer(tr(lang, "lang_choose"), reply_markup=kb)

    elif key == "son":
        await show_counts(m, uid, lang)

    elif key == "slot":
        await show_slot(m, uid, lang)

    elif key == "admin":
        if uid != ADMIN_ID:
            return await m.answer("❌ Siz admin emassiz!")
        await m.answer("🛠 <b>Admin panelga xush kelibsiz!</b>", reply_markup=admin_kb())


def admin_kb() -> InlineKeyboardMarkup:
    def b(text, data):
        return InlineKeyboardButton(text=text, callback_data=data)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b("👥 Foydalanuvchilar", "users"), b("📊 Statistika", "admin_stats")],
            [b("🔍 Qidirish", "admin_find"), b("🔗 Referallar", "admin_refs")],
            [b("📢 Reklama tarqatish", "admin_broadcast"), b("📣 Kanallarga xabar", "admin_ad_menu")],
            [b("⏰ Rejalashtirish", "admin_sched_menu"), b("🎟 Promokod yaratish", "admin_promo_menu")],
            [b("📋 Promokodlar", "promo_list"), b("💾 Baza zaxirasi", "admin_backup")],
            [b("🚫 Ban / Unban qilish", "admin_ban_menu")],
            [b("💰 Pul qo'shish", "admin_topup_menu"), b("💸 Pul ayirish", "admin_minus_menu")],
            [b("⭐️ Stars qo'shish", "admin_st_plus_menu"), b("📉 Stars ayirish", "admin_st_minus_menu")],
            [b("➕ Kanal qo'shish", "add_ch"), b("🗑 Kanalni o'chirish", "del_ch_menu")],
        ]
    )


# ================== SON (KANALLAR STATISTIKASI) ==================
async def record_joins(uid: int):
    """Foydalanuvchi hozir barcha kanalda a'zo ekanini bazaga yozib qo'yadi."""
    if uid == ADMIN_ID:
        return
    now = int(time.time())
    chs = await get_channels()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO ch_joins(username, user_id, joined_at) VALUES(?,?,?)",
            [(ch, uid, now) for ch, _ in chs],
        )
        await db.commit()


async def show_counts(m: Message, uid: int, lang: str):
    channels = await get_channels()
    if not channels:
        return await m.answer(tr(lang, "cnt_empty"))
    await record_joins(uid)  # middleware o'tkazgan bo'lsa, u obunachi
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT username, COUNT(*) FROM ch_joins GROUP BY username")
        counts = dict(await cur.fetchall())

    lines = [
        tr(lang, "cnt_line", name=html.escape(username), n=counts.get(username, 0))
        for username, _ in channels
    ]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, url=f"https://t.me/{username.lstrip('@')}")]
            for username, title in channels
        ]
    )
    await m.answer(tr(lang, "cnt_title", lines="\n".join(lines)), reply_markup=kb)


# ================== TOP REFERAL ==================
async def show_top(m: Message, uid: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT referrer_id, COUNT(*) AS c FROM users "
            "WHERE rewarded=1 AND referrer_id IS NOT NULL "
            "GROUP BY referrer_id ORDER BY c DESC, referrer_id"
        )
        rows = await cur.fetchall()
        names = {}
        for rid, _ in rows[:10]:
            c2 = await db.execute("SELECT full_name FROM users WHERE id=?", (rid,))
            r = await c2.fetchone()
            names[rid] = (r[0] if r and r[0] else "Noma'lum")[:25]

    if not rows:
        return await m.answer(tr(lang, "top_empty"))

    medals = ["🥇", "🥈", "🥉"]
    lines = [
        tr(lang, "top_line", medal=medals[i - 1] if i <= 3 else f"{i}.", name=html.escape(names[rid]), n=n)
        for i, (rid, n) in enumerate(rows[:10], 1)
    ]
    text = tr(lang, "top_title", lines="\n".join(lines))
    mine = next(((i, n) for i, (rid, n) in enumerate(rows, 1) if rid == uid), None)
    text += "\n\n" + (tr(lang, "top_me", rank=mine[0], n=mine[1]) if mine else tr(lang, "top_me_none"))
    await m.answer(text)


# ================== PROMOKOD (FOYDALANUVCHI) ==================
async def redeem_promo(uid: int, code: str) -> tuple[str, str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT kind, amount, max_uses, used, active FROM promo_codes WHERE code=?", (code,)
        )
        row = await cur.fetchone()
        if not row or row[4] != 1:
            return "bad", "", 0
        kind, amount, max_uses, used, _ = row
        if max_uses and used >= max_uses:
            return "over", kind, amount
        try:
            await db.execute("INSERT INTO promo_uses(code, user_id) VALUES(?, ?)", (code, uid))
        except sqlite3.IntegrityError:
            return "used", kind, amount
        cur = await db.execute(
            "UPDATE promo_codes SET used = used + 1 WHERE code=? AND (max_uses=0 OR used < max_uses)",
            (code,),
        )
        if cur.rowcount == 0:
            await db.execute("DELETE FROM promo_uses WHERE code=? AND user_id=?", (code, uid))
            await db.commit()
            return "over", kind, amount
        column = "stars" if kind == "stars" else "balance"
        await db.execute(f"UPDATE users SET {column} = {column} + ? WHERE id=?", (amount, uid))
        await db.commit()
    return "ok", kind, amount


@router.message(States.waiting_promo, F.text)
async def promo_enter(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    lang = await get_lang(uid)
    status, kind, amount = await redeem_promo(uid, m.text.strip().lower())
    if status == "ok":
        await m.answer(tr(lang, "promo_ok_stars" if kind == "stars" else "promo_ok_balance", amount=amount))
    else:
        await m.answer(tr(lang, {"bad": "promo_bad", "used": "promo_used", "over": "promo_over"}[status]))


# ================== STARS SOTIB OLISH ==================
@router.callback_query(F.data.regexp(r"^buy_\d+$"))
async def process_buy_stars(c: CallbackQuery):
    u = c.from_user
    lang = await get_lang(u.id)
    stars_count = int(c.data.replace("buy_", ""))
    price_val = PACKS.get(stars_count)
    if price_val is None:
        return await c.answer("❌", show_alert=True)
    price_str = f"{price_val:,} so'm"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET balance = balance - ?, stars = stars + ? WHERE id=? AND balance >= ?",
            (price_val, stars_count, u.id, price_val),
        )
        if cur.rowcount == 0:
            await db.commit()
            await c.answer(tr(lang, "no_funds"), show_alert=True)
            # Mablag' yetmasa, karta ma'lumotini darrov ko'rsatamiz
            await c.message.answer(tr(lang, "topup_info", card=CARD_INFO), reply_markup=topup_kb(lang))
            return
        await db.execute("INSERT INTO orders(user_id, stars, price) VALUES(?, ?, ?)", (u.id, stars_count, price_str))
        await db.commit()

    uname = f"@{u.username}" if u.username else "mavjud emas"
    order_text = (
        f"⭐️ <b>Yangi Stars Xaridi!</b>\n\n"
        f"👤 Xaridor: {html.escape(u.full_name)}\n"
        f"🔗 Username: {uname}\n"
        f"🆔 ID: <code>{u.id}</code>\n\n"
        f"⭐️ Miqdori: <b>{stars_count} ta Stars</b>\n"
        f"💵 Narxi: <b>{price_str}</b>"
    )

    try:
        await c.bot.send_message(OTZIV_CHAT_ID, order_text)
    except Exception as e:
        logging.error("Xaridni kanalga yuborishda xatolik: %s", e)

    try:
        await c.bot.send_message(ADMIN_ID, f"🔔 <b>Yangi xarid amalga oshirildi!</b>\n\n{order_text}")
    except Exception as e:
        logging.error("Xaridni adminga yuborishda xatolik: %s", e)

    await c.message.edit_text(tr(lang, "buy_ok", n=stars_count, price=price_str))
    await c.answer()


# ================== GIFT YECHISH ==================
@router.callback_query(F.data.regexp(r"^withdraw_\d+$"))
async def process_withdraw(c: CallbackQuery):
    u = c.from_user
    lang = await get_lang(u.id)
    stars_count = int(c.data.replace("withdraw_", ""))
    if stars_count not in GIFTS:
        return await c.answer("❌", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET stars = stars - ? WHERE id=? AND stars >= ?",
            (stars_count, u.id, stars_count),
        )
        if cur.rowcount == 0:
            await db.commit()
            _, have = await get_user_data(u.id)
            return await c.answer(tr(lang, "no_stars", have=have), show_alert=True)
        cur = await db.execute(
            "INSERT INTO withdraws(user_id, stars, status) VALUES(?, ?, 'pending')", (u.id, stars_count)
        )
        wid = cur.lastrowid
        await db.commit()

    uname = f"@{u.username}" if u.username else "mavjud emas"
    order_text = (
        f"🎁 <b>Yangi Gift Yechish So'rovi!</b>\n\n"
        f"👤 Foydalanuvchi: {html.escape(u.full_name)}\n"
        f"🔗 Username: {uname}\n"
        f"🆔 ID: <code>{u.id}</code>\n\n"
        f"⭐️ Miqdori: <b>{stars_count} ta Stars</b>"
    )

    try:
        await c.bot.send_message(OTZIV_CHAT_ID, order_text)
    except Exception as e:
        logging.error("Gift so'rovini kanalga yuborishda xatolik: %s", e)

    admin_kb_gift = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"gift_ok_{wid}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"gift_no_{wid}"),
        ]]
    )
    try:
        await c.bot.send_message(
            ADMIN_ID, f"🔔 <b>Yangi gift so'rovi tushdi!</b> (#{wid})\n\n{order_text}", reply_markup=admin_kb_gift
        )
    except Exception as e:
        logging.error("Gift so'rovini adminga yuborishda xatolik: %s", e)

    await c.message.edit_text(tr(lang, "withdraw_ok", n=stars_count))
    await c.answer()


@router.callback_query(F.data.regexp(r"^gift_(ok|no)_\d+$"))
async def admin_gift_decide(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    _, action, wid = c.data.split("_")
    wid = int(wid)
    new_status = "done" if action == "ok" else "rejected"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE withdraws SET status=? WHERE id=? AND status='pending'", (new_status, wid)
        )
        if cur.rowcount == 0:
            await db.commit()
            return await c.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        cur = await db.execute("SELECT user_id, stars FROM withdraws WHERE id=?", (wid,))
        user_id, stars = await cur.fetchone()
        if new_status == "rejected":
            await db.execute("UPDATE users SET stars = stars + ? WHERE id=?", (stars, user_id))
        await db.commit()

    try:
        lang = await get_lang(user_id)
        await c.bot.send_message(user_id, tr(lang, "gift_done" if action == "ok" else "gift_rejected", n=stars))
    except Exception:
        pass

    mark = "✅ <b>Bajarildi</b>" if action == "ok" else "❌ <b>Rad etildi</b> (stars qaytarildi)"
    try:
        await c.message.edit_text(c.message.html_text + f"\n\n{mark}", reply_markup=None)
    except Exception:
        await c.message.answer(mark)
    await c.answer()


# ================== HISOB TO'LDIRISH (CHEK) ==================
@router.callback_query(F.data == "send_receipt")
async def receipt_start(c: CallbackQuery, state: FSMContext):
    lang = await get_lang(c.from_user.id)
    await state.set_state(States.waiting_receipt)
    await c.message.answer(tr(lang, "topup_ask"))
    await c.answer()


@router.message(States.waiting_receipt, F.photo | F.document)
async def receipt_received(m: Message, state: FSMContext):
    await state.clear()
    u = m.from_user
    lang = await get_lang(u.id)
    if m.photo:
        file_id, ftype = m.photo[-1].file_id, "photo"
    else:
        file_id, ftype = m.document.file_id, "document"
    caption = m.caption or ""

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO topups(user_id, file_id, ftype, caption, created_at) VALUES(?,?,?,?,?)",
            (u.id, file_id, ftype, caption, int(time.time())),
        )
        tid = cur.lastrowid
        await db.commit()

    uname = f"@{u.username}" if u.username else "yo'q"
    text = (
        f"💳 <b>Yangi to'lov cheki</b> (#{tid})\n\n"
        f"👤 {html.escape(u.full_name)}\n🔗 Username: {uname}\n🆔 <code>{u.id}</code>"
        + (f"\n\n💬 {html.escape(caption)}" if caption else "")
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"topup_ok_{tid}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"topup_no_{tid}"),
        ]]
    )
    try:
        if ftype == "photo":
            await m.bot.send_photo(ADMIN_ID, file_id, caption=text, reply_markup=kb)
        else:
            await m.bot.send_document(ADMIN_ID, file_id, caption=text, reply_markup=kb)
    except Exception as e:
        logging.warning("Chek adminga yuborilmadi: %s", e)
    await m.answer(tr(lang, "topup_sent"))


@router.message(States.waiting_receipt)
async def receipt_wrong(m: Message):
    lang = await get_lang(m.from_user.id)
    await m.answer(tr(lang, "topup_need_photo"))


@router.callback_query(F.data.regexp(r"^topup_(ok|no)_\d+$"))
async def admin_topup_decide(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    _, action, tid = c.data.split("_")
    tid = int(tid)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, status FROM topups WHERE id=?", (tid,))
        row = await cur.fetchone()
        if not row or row[1] != "pending":
            return await c.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        user_id = row[0]

        if action == "no":
            await db.execute("UPDATE topups SET status='no' WHERE id=? AND status='pending'", (tid,))
            await db.commit()

    if action == "no":
        try:
            lang = await get_lang(user_id)
            await c.bot.send_message(user_id, tr(lang, "topup_no"))
        except Exception:
            pass
        try:
            await c.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await c.message.answer(f"❌ Chek #{tid} rad etildi.")
        return await c.answer()

    await state.set_state(States.topup_amount)
    await state.update_data(topup_id=tid, msg_id=c.message.message_id)
    await c.message.answer(f"💰 Chek #{tid}: hisobga qo'shiladigan <b>summani</b> yozing (so'mda):")
    await c.answer()


@router.message(States.topup_amount, F.text)
async def admin_topup_amount(m: Message, state: FSMContext):
    amount = parse_int(m.text)
    if not amount:
        return await m.answer("⚠️ Faqat summani raqam bilan yozing. Masalan: <code>21000</code>")
    data = await state.get_data()
    tid, msg_id = data["topup_id"], data.get("msg_id")
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE topups SET status='ok', amount=? WHERE id=? AND status='pending'", (amount, tid)
        )
        if cur.rowcount == 0:
            await db.commit()
            return await m.answer("Bu chek allaqachon ko'rib chiqilgan.")
        cur = await db.execute("SELECT user_id FROM topups WHERE id=?", (tid,))
        user_id = (await cur.fetchone())[0]
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
        await db.commit()

    try:
        lang = await get_lang(user_id)
        await m.bot.send_message(user_id, tr(lang, "topup_ok", amount=amount))
    except Exception:
        pass
    if msg_id:
        try:
            await m.bot.edit_message_reply_markup(chat_id=ADMIN_ID, message_id=msg_id, reply_markup=None)
        except Exception:
            pass
    await m.answer(f"✅ Chek #{tid} tasdiqlandi. <code>{user_id}</code> hisobiga <b>{amount} so'm</b> qo'shildi.")


# ================== ADMIN: BAN / UNBAN ==================
@router.callback_query(F.data == "admin_ban_menu")
async def admin_ban_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_ban)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📋 Bandan olish menyusi", callback_data="unban_list")]]
    )
    await c.message.answer("🚫 Ban qilmoqchi bo'lgan foydalanuvchi <b>ID sini</b> yuboring:", reply_markup=kb)
    await c.answer()


@router.message(States.waiting_ban, F.text)
async def confirm_ban_user(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return await m.answer("⚠️ Faqat raqamdan iborat foydalanuvchi ID sini yuboring:")

    target_id = int(m.text)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚨 Ha, Banlash", callback_data=f"do_ban_{target_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_admin")],
        ]
    )
    await m.answer(f"❓ Foydalanuvchi ID: <code>{target_id}</code>\nNima qilmoqchisiz?", reply_markup=kb)


@router.callback_query(F.data.regexp(r"^do_ban_\d+$"))
async def execute_ban(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    target_id = int(c.data.replace("do_ban_", ""))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE id=?", (target_id,))
        await db.commit()

    try:
        await c.bot.send_message(target_id, "❌ Siz botdan bloklandingiz!")
    except Exception:
        pass

    await c.message.edit_text(f"✅ <code>{target_id}</code> ID raqamli foydalanuvchi muvaffaqiyatli ban qilindi!")
    await c.answer()


@router.callback_query(F.data == "unban_list")
async def unban_list_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, full_name FROM users WHERE is_banned=1")
        rows = await cur.fetchall()

    if not rows:
        return await c.answer("📭 Ban qilingan foydalanuvchilar yo'q.", show_alert=True)

    rows_kb = [
        [InlineKeyboardButton(text=f"✅ Bandan olish: {name} ({uid})", callback_data=f"unban_{uid}")]
        for uid, name in rows
    ]
    await c.message.edit_text(
        "📋 Ban qilinganlar ro'yxati (bandan olish uchun bosing):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows_kb),
    )
    await c.answer()


@router.callback_query(F.data.regexp(r"^unban_\d+$"))
async def execute_unban(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    target_id = int(c.data.replace("unban_", ""))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE id=?", (target_id,))
        await db.commit()

    try:
        await c.bot.send_message(target_id, "✅ Bandan olindingiz! Endi botdan yana foydalanishingiz mumkin 🎉")
    except Exception:
        pass

    await c.message.edit_text(f"✅ <code>{target_id}</code> ID li foydalanuvchi bandan olindi!")
    await c.answer()


# ================== ADMIN: PUL QO'SHISH ==================
@router.callback_query(F.data == "admin_topup_menu")
async def admin_topup_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_topup)
    await c.message.answer(
        "💰 <b>Pul qo'shish uchun quyidagi formatda yuboring:</b>\n\n"
        "<code>[summa] [foydalanuvchi_id]</code>\n"
        "Masalan: <code>11000 8327302562</code>"
    )
    await c.answer()


@router.message(States.waiting_topup, F.text)
async def process_topup(m: Message, state: FSMContext):
    parts = m.text.strip().split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await m.answer(
            "⚠️ Xato format! Qaytadan quyidagicha yuboring:\n"
            "<code>[summa] [foydalanuvchi_id]</code> (Masalan: <code>11000 8327302562</code>)"
        )

    summa = int(parts[0])
    target_id = int(parts[1])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE id=?", (target_id,))
        if not await cur.fetchone():
            return await m.answer(f"❌ <code>{target_id}</code> ID raqamli foydalanuvchi bazadan topilmadi!")

        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (summa, target_id))
        await db.commit()

    try:
        await m.bot.send_message(target_id, f"🎉 Sizning hisobingizga <b>{summa} so'm</b> qo'shildi! 💰")
    except Exception:
        pass

    await m.answer(f"✅ Muvaffaqiyatli! <code>{target_id}</code> ID raqamli foydalanuvchiga <b>{summa} so'm</b> qo'shildi.")


# ================== ADMIN: PUL AYIRISH ==================
@router.callback_query(F.data == "admin_minus_menu")
async def admin_minus_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_minus)
    await c.message.answer(
        "💸 <b>Pul ayirish uchun quyidagi formatda yuboring:</b>\n\n"
        "<code>[summa] [foydalanuvchi_id]</code>\n"
        "Masalan: <code>5000 8327302562</code> yoki <code>ayir 5000 8327302562</code>"
    )
    await c.answer()


@router.message(States.waiting_minus, F.text)
async def process_minus_balance(m: Message, state: FSMContext):
    text = m.text.strip()
    if text.lower().startswith("ayir"):
        text = text[4:].strip()

    parts = text.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await m.answer(
            "⚠️ Xato format! Qaytadan quyidagicha yuboring:\n"
            "<code>[summa] [foydalanuvchi_id]</code> (Masalan: <code>5000 8327302562</code>)"
        )

    summa = int(parts[0])
    target_id = int(parts[1])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance FROM users WHERE id=?", (target_id,))
        row = await cur.fetchone()
        if not row:
            return await m.answer(f"❌ <code>{target_id}</code> ID raqamli foydalanuvchi bazadan topilmadi!")

        await db.execute("UPDATE users SET balance = balance - ? WHERE id=?", (summa, target_id))
        await db.commit()

    try:
        await m.bot.send_message(target_id, f"⚠️ Sizning hisobingizdan <b>{summa} so'm</b> ayirildi! 💸")
    except Exception:
        pass

    await m.answer(f"✅ Muvaffaqiyatli! <code>{target_id}</code> ID li foydalanuvchidan <b>{summa} so'm</b> ayirildi.")


# ================== ADMIN: STARS QO'SHISH ==================
@router.callback_query(F.data == "admin_st_plus_menu")
async def admin_st_plus_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_st_plus)
    await c.message.answer(
        "⭐️ <b>Stars qo'shish uchun quyidagi formatda yuboring:</b>\n\n"
        "<code>[stars_soni] [foydalanuvchi_id]</code>\n"
        "Yoki: <code>st [stars_soni] [foydalanuvchi_id]</code>\n"
        "Masalan: <code>10 8327302562</code>"
    )
    await c.answer()


@router.message(States.waiting_st_plus, F.text)
async def process_st_plus(m: Message, state: FSMContext):
    text = m.text.strip()
    if text.lower().startswith("st"):
        text = text[2:].strip()

    parts = text.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await m.answer(
            "⚠️ Xato format! Qaytadan quyidagicha yuboring:\n"
            "<code>[stars_soni] [foydalanuvchi_id]</code> (Masalan: <code>10 8327302562</code>)"
        )

    stars = int(parts[0])
    target_id = int(parts[1])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE id=?", (target_id,))
        if not await cur.fetchone():
            return await m.answer(f"❌ <code>{target_id}</code> ID raqamli foydalanuvchi bazadan topilmadi!")

        await db.execute("UPDATE users SET stars = stars + ? WHERE id=?", (stars, target_id))
        await db.commit()

    try:
        await m.bot.send_message(target_id, f"🎉 Sizga admin tomonidan <b>{stars} ta ⭐️ Stars</b> qo'shildi!")
    except Exception:
        pass

    await m.answer(f"✅ Muvaffaqiyatli! <code>{target_id}</code> ID li foydalanuvchiga <b>{stars} ta ⭐️ Stars</b> qo'shildi.")


# ================== ADMIN: STARS AYIRISH ==================
@router.callback_query(F.data == "admin_st_minus_menu")
async def admin_st_minus_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_st_minus)
    await c.message.answer(
        "📉 <b>Stars ayirish uchun quyidagi formatda yuboring:</b>\n\n"
        "<code>[stars_soni] [foydalanuvchi_id]</code>\n"
        "Yoki: <code>sta [stars_soni] [foydalanuvchi_id]</code>\n"
        "Masalan: <code>5 8327302562</code>"
    )
    await c.answer()


@router.message(States.waiting_st_minus, F.text)
async def process_st_minus(m: Message, state: FSMContext):
    text = m.text.strip()
    if text.lower().startswith("sta") or text.lower().startswith("st"):
        text = text[3:].strip() if text.lower().startswith("sta") else text[2:].strip()

    parts = text.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await m.answer(
            "⚠️ Xato format! Qaytadan quyidagicha yuboring:\n"
            "<code>[stars_soni] [foydalanuvchi_id]</code> (Masalan: <code>5 8327302562</code>)"
        )

    stars = int(parts[0])
    target_id = int(parts[1])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT stars FROM users WHERE id=?", (target_id,))
        row = await cur.fetchone()
        if not row:
            return await m.answer(f"❌ <code>{target_id}</code> ID raqamli foydalanuvchi bazadan topilmadi!")

        await db.execute("UPDATE users SET stars = stars - ? WHERE id=?", (stars, target_id))
        await db.commit()

    try:
        await m.bot.send_message(target_id, f"⚠️ Hisobingizdan admin tomonidan <b>{stars} ta ⭐️ Stars</b> ayirildi!")
    except Exception:
        pass

    await m.answer(f"✅ Muvaffaqiyatli! <code>{target_id}</code> ID li foydalanuvchidan <b>{stars} ta ⭐️ Stars</b> ayirildi.")


# ================== ADMIN: KANAL QO'SHISH/O'CHIRISH ==================
@router.callback_query(F.data == "add_ch")
async def admin_add_channel(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_channel)
    await c.message.answer(
        "📢 Yangi kanal username-ini yuboring (masalan: <code>@kanal_username</code>):\n\n"
        "⚠️ Avval botni shu kanalga <b>admin</b> qilib qo'shing!"
    )
    await c.answer()


@router.message(States.waiting_channel, F.text)
async def save_new_channel(m: Message, state: FSMContext):
    ch_username = m.text.strip()
    if not ch_username.startswith("@") or " " in ch_username:
        return await m.answer("⚠️ Xato format! Username <code>@</code> bilan boshlanishi kerak:")

    try:
        chat = await m.bot.get_chat(ch_username)
        me = await m.bot.get_me()
        bot_member = await m.bot.get_chat_member(ch_username, me.id)
    except Exception:
        return await m.answer("⚠️ Kanal topilmadi yoki bot u yerda admin emas. Qaytadan yuboring:")

    if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return await m.answer("⚠️ Bot bu kanalda <b>admin emas</b>! Botni admin qiling va qaytadan yuboring:")

    await state.clear()
    title = f"📢 {chat.title or ch_username[1:]}"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO channels(username, title) VALUES(?, ?)", (ch_username, title))
        await db.commit()

    await m.answer(f"✅ <b>{html.escape(ch_username)}</b> majburiy obuna ro'yxatiga qo'shildi! 🎉")


@router.callback_query(F.data == "del_ch_menu")
async def delete_channel_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    channels = await get_channels()
    if not channels:
        return await c.answer("📭 Hozircha ulangan kanallar yo'q", show_alert=True)

    rows = [
        [InlineKeyboardButton(text=f"❌ O'chirish: {title}", callback_data=f"delch_{username}")]
        for username, title in channels
    ]
    await c.message.answer("🗑 O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()


@router.callback_query(F.data.startswith("delch_"))
async def remove_channel(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    ch_username = c.data.replace("delch_", "", 1)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE username=?", (ch_username,))
        await db.commit()

    await c.message.edit_text(f"✅ <b>{html.escape(ch_username)}</b> majburiy obunadan olib tashlandi!")
    await c.answer()


# ================== MUROJAAT + ADMIN JAVOBI ==================
@router.message(States.waiting_support, F.text)
async def support_msg(m: Message, state: FSMContext):
    await state.clear()
    u = m.from_user
    lang = await get_lang(u.id)
    uname = f"@{u.username}" if u.username else "yo'q"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"reply_{u.id}_{m.message_id}")
        ]]
    )
    try:
        await m.bot.send_message(
            ADMIN_ID,
            "☎️ <b>Yangi murojaat</b>\n\n"
            f"👤 {html.escape(u.full_name)}\n🔗 Username: {uname}\n🆔 <code>{u.id}</code>\n\n"
            f"💬 {html.escape(m.text)}",
            reply_markup=kb,
        )
    except Exception as e:
        logging.warning("Adminga yuborilmadi: %s", e)
    await m.answer(tr(lang, "support_sent"))


@router.callback_query(F.data.regexp(r"^reply_\d+_\d+$"))
async def admin_reply_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    _, uid, mid = c.data.split("_")
    await state.set_state(States.waiting_reply)
    await state.update_data(target_id=int(uid), target_msg_id=int(mid))
    await c.message.answer(
        f"✍️ <code>{uid}</code> ga yuboriladigan javobni yozing.\n"
        "Bekor qilish uchun /start bosing."
    )
    await c.answer()


@router.message(States.waiting_reply, F.text)
async def admin_reply_send(m: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    target_msg_id = data["target_msg_id"]
    await state.clear()

    text = f"📩 <b>Admin javobi:</b>\n\n{html.escape(m.text)}"
    try:
        await m.bot.send_message(target_id, text, reply_to_message_id=target_msg_id)
    except Exception:
        try:
            await m.bot.send_message(target_id, text)
        except Exception as e:
            logging.warning("Javob yuborilmadi: %s", e)
            return await m.answer("❌ Javob yuborilmadi (foydalanuvchi botni bloklagan bo'lishi mumkin).")

    await m.answer("✅ Javob foydalanuvchiga yuborildi.")


@router.callback_query(F.data == "cancel_admin")
async def cancel_admin(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("❌ Amaliyot bekor qilindi.")
    await c.answer()


# ================== ADMIN: FOYDALANUVCHILAR ==================
@router.callback_query(F.data == "users")
async def users_list(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT u.id, u.username, u.full_name, u.balance, u.stars,
                   (SELECT COUNT(*) FROM users r WHERE r.referrer_id = u.id)
            FROM users u ORDER BY u.rowid
            """
        )
        rows = await cur.fetchall()
    await c.answer()
    if not rows:
        return await c.message.answer("📭 Foydalanuvchilar yo'q")

    lines = []
    for i, (uid, username, full_name, bal, stars, invited) in enumerate(rows, 1):
        uname = f"@{html.escape(username)}" if username else "username yo'q"
        name = html.escape(full_name or "Noma'lum")
        lines.append(
            f"{i}. 👤 <b>{name}</b>\n"
            f"    🔗 {uname}\n"
            f"    🆔 <code>{uid}</code> | 💰 {bal} so'm | ⭐️ {stars} ta Stars | 👥 {invited} ta taklif"
        )

    await c.message.answer(f"👥 <b>Foydalanuvchilar: {len(rows)} ta</b>")
    await send_chunks(c.message, lines, per_chunk=20)


# ================== ADMIN: REFERALLAR ==================
def ulink(uid: int, full_name, username) -> str:
    name = html.escape(full_name or "Noma`lum")
    link = f'<a href="tg://user?id={uid}">{name}</a>'
    return link + (f" (@{html.escape(username)})" if username else "")


async def send_packed(message: Message, lines: list[str], limit: int = 3800):
    """Qatorlarni Telegram limitiga (4096 belgi) sig'adigan xabarlarga bo'lib yuboradi."""
    buf = ""
    for ln in lines:
        if buf and len(buf) + len(ln) + 1 > limit:
            await message.answer(buf)
            buf = ""
        buf += ("\n" if buf else "") + ln[:limit]
    if buf:
        await message.answer(buf)


@router.callback_query(F.data == "admin_refs")
async def admin_refs(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT u.id, u.full_name, u.username,
                   r.id, r.full_name, r.username, r.rewarded
            FROM users r
            JOIN users u ON r.referrer_id = u.id
            ORDER BY u.id, r.rowid
            """
        )
        rows = await cur.fetchall()
    await c.answer()
    if not rows:
        return await c.message.answer("📭 Hali hech kim hech kimni taklif qilmagan.")

    groups: dict[int, dict] = {}
    for uid, u_full, u_name, r_id, r_name, r_uname, rewarded in rows:
        g = groups.setdefault(uid, {"label": ulink(uid, u_full, u_name), "items": [], "ok": 0})
        g["items"].append((r_id, r_name, r_uname, rewarded))
        if rewarded == 1:
            g["ok"] += 1

    ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]["items"]), kv[0]))

    # 1) Umumiy reyting: kim nechta odam taklif qilgan
    await c.message.answer(
        f"🔗 <b>Referallar: {len(rows)} ta taklif</b>\n"
        f"👥 Taklif qilganlar: <b>{len(groups)}</b> kishi\n"
        f"✅ Obuna bo'lgani: <b>{sum(g['ok'] for g in groups.values())}</b> ta"
    )
    summary = ["🏆 <b>Kim nechta odam taklif qilgan:</b>\n"]
    for i, (uid, g) in enumerate(ranked, 1):
        summary.append(
            f"{i}. {g['label']} | 🆔 <code>{uid}</code>\n"
            f"    👥 <b>{len(g['items'])}</b> ta taklif (✅ {g['ok']} obuna | ⏳ {len(g['items']) - g['ok']} obuna emas)"
        )
    await send_packed(c.message, summary)

    # 2) Batafsil: kim kimlarni taklif qilgan
    detail = ["📋 <b>Batafsil: kim kimlarni taklif qilgan:</b>"]
    for uid, g in ranked:
        detail.append(f"\n👤 {g['label']} | 🆔 <code>{uid}</code> — <b>{len(g['items'])}</b> ta:")
        for n, (r_id, r_name, r_uname, rewarded) in enumerate(g["items"], 1):
            status = "✅ obuna" if rewarded == 1 else "⏳ obuna emas"
            detail.append(f"    {n}. {ulink(r_id, r_name, r_uname)} | <code>{r_id}</code> — {status}")
    await send_packed(c.message, detail)


# ================== ADMIN: STATISTIKA ==================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await c.answer()
    today = int(datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    async with aiosqlite.connect(DB_PATH) as db:
        async def one(q: str, p: tuple = ()) -> int:
            cur = await db.execute(q, p)
            r = await cur.fetchone()
            return (r[0] or 0) if r else 0

        total = await one("SELECT COUNT(*) FROM users")
        new_today = await one("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (today,))
        banned = await one("SELECT COUNT(*) FROM users WHERE is_banned=1")
        blocked_bot = await one("SELECT COUNT(*) FROM users WHERE blocked=1")
        by_ref = await one("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL")
        rewarded = await one("SELECT COUNT(*) FROM users WHERE rewarded=1")
        sum_bal = await one("SELECT SUM(balance) FROM users")
        sum_stars = await one("SELECT SUM(stars) FROM users")
        orders_n = await one("SELECT COUNT(*) FROM orders")
        cur = await db.execute("SELECT price FROM orders")
        orders_sum = sum(parse_int(p) or 0 for (p,) in await cur.fetchall())
        top_n = await one("SELECT COUNT(*) FROM topups WHERE status='ok'")
        top_sum = await one("SELECT SUM(amount) FROM topups WHERE status='ok'")
        top_pending = await one("SELECT COUNT(*) FROM topups WHERE status='pending'")
        gifts_pending = await one("SELECT COUNT(*) FROM withdraws WHERE status='pending'")
        gifts_done = await one("SELECT COUNT(*) FROM withdraws WHERE status='done'")
        promos = await one("SELECT COUNT(*) FROM promo_codes WHERE active=1")
        sched = await one("SELECT COUNT(*) FROM scheduled WHERE done=0")

    await c.message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchi: <b>{total}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{new_today}</b>\n"
        f"🚫 Banlangan: <b>{banned}</b>\n"
        f"⛔️ Botni bloklaganlar: <b>{blocked_bot}</b>\n"
        f"🔗 Referal orqali kelgan: <b>{by_ref}</b> (mukofot berilgan: {rewarded})\n\n"
        f"💰 Foydalanuvchilar balansi: <b>{sum_bal:,}</b> so'm\n"
        f"⭐️ Foydalanuvchilar starsi: <b>{sum_stars:,}</b> ta\n\n"
        f"🛒 Stars xaridlari: <b>{orders_n}</b> ta — <b>{orders_sum:,}</b> so'm\n"
        f"💳 Tasdiqlangan to'ldirishlar: <b>{top_n}</b> ta — <b>{top_sum:,}</b> so'm\n"
        f"🎁 Bajarilgan giftlar: <b>{gifts_done}</b> ta\n\n"
        f"⏳ Kutilayotgan cheklar: <b>{top_pending}</b>\n"
        f"⏳ Kutilayotgan giftlar: <b>{gifts_pending}</b>\n"
        f"🎟 Faol promokodlar: <b>{promos}</b>\n"
        f"⏰ Rejalashtirilgan xabarlar: <b>{sched}</b>"
    )


# ================== ADMIN: FOYDALANUVCHINI QIDIRISH ==================
@router.callback_query(F.data == "admin_find")
async def admin_find_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_find)
    await c.message.answer(
        "🔍 Foydalanuvchi <b>ID</b> sini yoki <b>@username</b> ini yuboring:\n"
        "Bekor qilish uchun /start bosing."
    )
    await c.answer()


@router.message(States.waiting_find, F.text)
async def admin_find_result(m: Message, state: FSMContext):
    await state.clear()
    q = m.text.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        if q.isdigit():
            cur = await db.execute(
                "SELECT id, username, full_name, balance, stars, referrer_id, rewarded, is_banned, lang, joined_at "
                "FROM users WHERE id=?", (int(q),),
            )
        else:
            cur = await db.execute(
                "SELECT id, username, full_name, balance, stars, referrer_id, rewarded, is_banned, lang, joined_at "
                "FROM users WHERE LOWER(username)=?", (q.lstrip("@").lower(),),
            )
        row = await cur.fetchone()
        if not row:
            return await m.answer("❌ Foydalanuvchi topilmadi.")
        uid, username, full_name, bal, stars, ref_id, rewarded, banned, lang, joined = row

        async def one(sql: str, p: tuple) -> int:
            c2 = await db.execute(sql, p)
            return (await c2.fetchone())[0] or 0

        invited = await one("SELECT COUNT(*) FROM users WHERE referrer_id=?", (uid,))
        invited_ok = await one("SELECT COUNT(*) FROM users WHERE referrer_id=? AND rewarded=1", (uid,))
        n_orders = await one("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
        n_gifts = await one("SELECT COUNT(*) FROM withdraws WHERE user_id=?", (uid,))
        n_topups = await one("SELECT COUNT(*) FROM topups WHERE user_id=? AND status='ok'", (uid,))
        sum_topups = await one("SELECT SUM(amount) FROM topups WHERE user_id=? AND status='ok'", (uid,))
        ref_line = "yo'q"
        if ref_id:
            c3 = await db.execute("SELECT full_name, username FROM users WHERE id=?", (ref_id,))
            r = await c3.fetchone()
            ref_line = (user_label(r[0], r[1]) if r else "") + f" | <code>{ref_id}</code>"

    await m.answer(
        "🔍 <b>Foydalanuvchi ma'lumoti</b>\n\n"
        f"👤 {user_label(full_name, username)}\n"
        f"🆔 <code>{uid}</code>\n"
        f"📅 Qo'shilgan: {fmt_ts(joined) if joined else 'noma`lum'}\n"
        f"🌐 Til: {lang or 'uz'}\n"
        f"🚫 Ban: {'ha' if banned else 'yo`q'}\n\n"
        f"💰 Balans: <b>{bal}</b> so'm\n⭐️ Stars: <b>{stars}</b> ta\n\n"
        f"🔗 Uni taklif qilgan: {ref_line}\n"
        f"👥 Taklif qilgani: <b>{invited}</b> ta (mukofotli: {invited_ok})\n\n"
        f"🛒 Xaridlar: <b>{n_orders}</b> ta\n🎁 Gift so'rovlari: <b>{n_gifts}</b> ta\n"
        f"💳 To'ldirishlar: <b>{n_topups}</b> ta — <b>{sum_topups}</b> so'm"
    )


# ================== ADMIN: PROMOKODLAR ==================
@router.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Stars beradigan", callback_data="pnew_stars")],
            [InlineKeyboardButton(text="💰 Pul (so'm) beradigan", callback_data="pnew_balance")],
        ]
    )
    await c.message.answer("🎟 <b>Promokod nima beradi?</b> Tanlang 👇", reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.in_({"pnew_stars", "pnew_balance"}))
async def promo_new_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    kind = c.data.replace("pnew_", "")
    await state.set_state(States.promo_new)
    await state.update_data(kind=kind)
    unit = "ta ⭐️ Stars" if kind == "stars" else "so'm"
    await c.message.answer(
        "🎟 Promokodni quyidagi formatda yozing:\n\n"
        "<code>[kod] [miqdor] [limit]</code>\n\n"
        f"Masalan: <code>salom 5 50</code> — «salom» kodi, 5 {unit}, 50 kishi ishlata oladi.\n"
        "Limit yozilmasa, 100 kishi bo'ladi. Har bir foydalanuvchi kodni faqat 1 marta ishlata oladi."
    )
    await c.answer()


@router.message(States.promo_new, F.text)
async def promo_new_save(m: Message, state: FSMContext):
    parts = m.text.strip().split()
    amount = parse_int(parts[1]) if len(parts) >= 2 else None
    limit = parse_int(parts[2]) if len(parts) >= 3 else 100
    if len(parts) not in (2, 3) or not amount or not limit or len(parts[0]) > 30:
        return await m.answer(
            "⚠️ Xato format! Masalan: <code>salom 5 50</code> (kod, miqdor, limit)\nQaytadan yozing:"
        )
    data = await state.get_data()
    kind = data["kind"]
    code = parts[0].lower()

    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO promo_codes(code, kind, amount, max_uses) VALUES(?,?,?,?)",
                (code, kind, amount, limit),
            )
            await db.commit()
        except sqlite3.IntegrityError:
            return await m.answer("⚠️ Bu kod allaqachon mavjud. Boshqa kod yozing:")

    await state.clear()
    unit = f"{amount} ta ⭐️ Stars" if kind == "stars" else f"{amount} so'm"

    # Promokodni otziv kanaliga e'lon qilish
    posted = True
    try:
        me = await m.bot.get_me()
        await m.bot.send_message(
            OTZIV_CHAT_ID,
            "🎟 <b>Yangi PROMOKOD!</b> 🎉\n\n"
            f"🔑 Kod: <code>{html.escape(code)}</code>\n"
            f"🎁 Mukofot: <b>{unit}</b>\n"
            f"👥 Faqat birinchi <b>{limit}</b> kishi uchun!\n\n"
            f"👉 Botga kiring: @{me.username}\n"
            "🎟 <b>Promokod</b> tugmasini bosing va kodni yozing. Shoshiling! 🚀",
        )
    except Exception as e:
        posted = False
        logging.error("Promokodni kanalga yuborishda xatolik: %s", e)

    await m.answer(
        f"✅ <b>Promokod yaratildi!</b>\n\n🎟 Kod: <code>{html.escape(code)}</code>\n"
        f"🎁 Beradi: <b>{unit}</b>\n👥 Limit: <b>{limit}</b> kishi\n\n"
        + (
            f"📣 {html.escape(OTZIV_CHAT_ID)} kanaliga e'lon qilindi."
            if posted
            else f"⚠️ {html.escape(OTZIV_CHAT_ID)} kanaliga yuborib bo'lmadi. Bot u yerda admin ekanini tekshiring."
        )
    )


@router.callback_query(F.data == "promo_list")
async def promo_list(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT rowid, code, kind, amount, max_uses, used FROM promo_codes ORDER BY rowid DESC LIMIT 30"
        )
        rows = await cur.fetchall()
    if not rows:
        return await c.answer("📭 Promokodlar yo'q.", show_alert=True)

    lines, kb_rows = [], []
    for rid, code, kind, amount, max_uses, used in rows:
        unit = f"⭐️{amount}" if kind == "stars" else f"💰{amount}"
        lines.append(f"🎟 <code>{html.escape(code)}</code> — {unit} | {used}/{max_uses or '∞'}")
        kb_rows.append([InlineKeyboardButton(text=f"🗑 {code}", callback_data=f"pdel_{rid}")])
    await c.message.answer(
        "📋 <b>Promokodlar</b> (ishlatilgan/limit):\n\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
    await c.answer()


@router.callback_query(F.data.regexp(r"^pdel_\d+$"))
async def promo_delete(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    rid = int(c.data.replace("pdel_", ""))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT code FROM promo_codes WHERE rowid=?", (rid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Allaqachon o'chirilgan.", show_alert=True)
        await db.execute("DELETE FROM promo_codes WHERE rowid=?", (rid,))
        await db.execute("DELETE FROM promo_uses WHERE code=?", (row[0],))
        await db.commit()
    await c.message.answer(f"🗑 <code>{html.escape(row[0])}</code> promokodi o'chirildi.")
    await c.answer()


# ================== XABAR YUBORISH YORDAMCHILARI ==================
async def _copy_with_retry(bot: Bot, chat_id, from_chat_id: int, message_id: int) -> str:
    """Natija: 'ok' | 'blocked' (bot bloklangan/chat yo'q) | 'other' (boshqa xato)."""
    for _ in range(3):
        try:
            await bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
            return "ok"
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            return "blocked"
        except TelegramBadRequest as e:
            msg = str(e).lower()
            if "chat not found" in msg or "deactivated" in msg:
                return "blocked"
            return "other"
        except Exception:
            return "other"
    return "other"


def report_text(res: dict, title: str = "✅ <b>Reklama tarqatildi!</b>") -> str:
    failed = res["blocked"] + res["other"]
    return (
        f"{title}\n\n"
        f"👥 Jami: <b>{res['total']}</b> ta\n"
        f"📬 Yuborildi: <b>{res['ok']}</b> ta\n"
        f"❌ Yuborilmadi: <b>{failed}</b> ta\n"
        f"   🚫 Botni bloklaganlar: <b>{res['blocked']}</b> ta\n"
        f"   ⚠️ Boshqa xato: <b>{res['other']}</b> ta"
    )


async def send_to_users(bot: Bot, msg_id: int, progress=None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE is_banned=0")
        ids = [r[0] for r in await cur.fetchall()]

    res = {"total": len(ids), "ok": 0, "blocked": 0, "other": 0}
    ok_ids, blocked_ids = [], []
    last = time.time()
    for n, uid in enumerate(ids, 1):
        st = await _copy_with_retry(bot, uid, ADMIN_ID, msg_id)
        if st == "ok":
            res["ok"] += 1
            ok_ids.append(uid)
        elif st == "blocked":
            res["blocked"] += 1
            blocked_ids.append(uid)
        else:
            res["other"] += 1
        await asyncio.sleep(0.05)  # sekundiga ~20 ta xabar
        if progress and time.time() - last >= 5:
            last = time.time()
            await progress(n, len(ids), res)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany("UPDATE users SET blocked=1 WHERE id=?", [(i,) for i in blocked_ids])
            await db.executemany("UPDATE users SET blocked=0 WHERE id=?", [(i,) for i in ok_ids])
            await db.commit()
    except Exception as e:
        logging.error("blocked belgisini yozishda xato: %s", e)
    return res


async def send_to_channels(bot: Bot, msg_id: int) -> tuple[list[str], list[str]]:
    ok_list, fail_list = [], []
    for ch, _ in await get_channels():
        if await _copy_with_retry(bot, ch, ADMIN_ID, msg_id) == "ok":
            ok_list.append(ch)
        else:
            fail_list.append(ch)
        await asyncio.sleep(0.3)
    return ok_list, fail_list


# Botni bloklash / blokdan chiqarishni jonli kuzatish
@router.my_chat_member()
async def on_my_chat_member(ev: ChatMemberUpdated):
    if ev.chat.type != "private":
        return
    blocked = 1 if ev.new_chat_member.status == ChatMemberStatus.KICKED else 0
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET blocked=? WHERE id=?", (blocked, ev.chat.id))
            await db.commit()
    except Exception as e:
        logging.warning("my_chat_member xato: %s", e)


# ================== ADMIN: REKLAMA TARQATISH ==================
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await state.set_state(States.waiting_broadcast)
    await c.message.answer(
        "📢 <b>Reklama tarqatish</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing "
        "(matn, rasm, video — istalgani bo'ladi).\n"
        "Bekor qilish uchun /start bosing."
    )
    await c.answer()


@router.message(States.waiting_broadcast)
async def broadcast_preview(m: Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
        total = (await cur.fetchone())[0]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Yuborish ({total} ta)", callback_data=f"bc_yes_{m.message_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_admin")],
        ]
    )
    await m.answer(
        f"❓ Yuqoridagi xabar <b>{total} ta</b> foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=kb,
        reply_to_message_id=m.message_id,
    )


_bg_tasks: set = set()
BROADCAST_RUNNING = False


async def run_broadcast(bot: Bot, msg: Message, msg_id: int):
    global BROADCAST_RUNNING
    BROADCAST_RUNNING = True

    async def progress(done: int, total: int, res: dict):
        try:
            await msg.edit_text(
                f"⏳ Yuborilmoqda... <b>{done}/{total}</b>\n"
                f"📬 {res['ok']} | 🚫 bloklagan {res['blocked']} | ⚠️ xato {res['other']}"
            )
        except Exception:
            pass

    try:
        res = await send_to_users(bot, msg_id, progress)
        text = report_text(res)
    except Exception as e:
        logging.error("Reklama xato: %s", e)
        text = f"❌ Reklama yuborishda xatolik: {html.escape(str(e))}"
    finally:
        BROADCAST_RUNNING = False

    try:
        await msg.edit_text(text)
    except Exception:
        await bot.send_message(ADMIN_ID, text)


@router.callback_query(F.data.regexp(r"^bc_yes_\d+$"))
async def broadcast_send(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    if BROADCAST_RUNNING:
        return await c.answer("⏳ Oldingi reklama hali yuborilmoqda, kuting.", show_alert=True)
    msg_id = int(c.data.replace("bc_yes_", ""))
    await c.answer()
    await c.message.edit_text("⏳ Xabar yuborilmoqda...")
    # Fon rejimida ishlaydi — bot boshqa foydalanuvchilarga javob berishda davom etadi
    task = asyncio.create_task(run_broadcast(c.bot, c.message, msg_id))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# ================== ADMIN: KANALLARGA XABAR YUBORISH ==================
def ad_channels_kb(channels: list[tuple[str, str]], selected: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if username in selected else ''}{username}",
                callback_data=f"adch_{username}",
            )
        ]
        for username, _ in channels
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin_ad_menu")
async def admin_ad_menu(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    channels = await get_channels()
    if not channels:
        return await c.answer("📭 Hozircha ulangan kanallar yo'q", show_alert=True)

    await state.clear()
    await state.set_state(States.ad_pick)
    await state.update_data(ad_sel=[])
    await c.message.answer(
        "📣 <b>Qaysi kanalga xabar yubormoqchisiz?</b>\n\nKanalni tanlang 👇",
        reply_markup=ad_channels_kb(channels, []),
    )
    await c.answer()


@router.callback_query(F.data.startswith("adch_"))
async def admin_ad_pick(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    username = c.data.replace("adch_", "", 1)
    data = await state.get_data()
    selected: list[str] = data.get("ad_sel", [])

    if username in selected:
        return await c.answer("Bu kanal allaqachon tanlangan.", show_alert=True)

    selected.append(username)
    await state.set_state(States.ad_pick)
    await state.update_data(ad_sel=selected)

    try:
        await c.message.edit_reply_markup(reply_markup=ad_channels_kb(await get_channels(), selected))
    except Exception:
        pass

    await c.message.answer(
        f"✅ <b>{html.escape(username)}</b> tanlandi.\n\n"
        "Yana kanal tanlaysizmi? Agar yo'q bo'lsa <code>/ad next</code> deb yozing."
    )
    await c.answer()


@router.message(Command("ad"))
async def admin_ad_next(m: Message, command: CommandObject, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    if (command.args or "").strip().lower() != "next":
        return await m.answer("⚠️ To'g'ri buyruq: <code>/ad next</code>")

    data = await state.get_data()
    selected: list[str] = data.get("ad_sel", [])
    if not selected:
        return await m.answer("⚠️ Avval admin paneldan kanal tanlang.")

    await state.set_state(States.ad_text)
    names = "\n".join(f"📢 {html.escape(u)}" for u in selected)
    await m.answer(
        f"📣 <b>Tanlangan kanallar:</b>\n{names}\n\n"
        "✍️ Yubormoqchi bo'lgan matningizni tashlang.\n"
        "Bekor qilish uchun /start bosing."
    )


@router.message(States.ad_text)
async def admin_ad_send(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    selected: list[str] = data.get("ad_sel", [])
    await state.clear()

    ok_list, fail_list = [], []
    for ch in selected:
        if await _copy_with_retry(m.bot, ch, m.chat.id, m.message_id) == "ok":
            ok_list.append(ch)
        else:
            fail_list.append(ch)
        await asyncio.sleep(0.3)

    text = "✅ <b>Xabar yuborildi!</b>\n\n"
    if ok_list:
        text += "📬 Yuborildi:\n" + "\n".join(f"• {html.escape(c)}" for c in ok_list) + "\n"
    if fail_list:
        text += (
            "\n🚫 Yuborilmadi (bot u yerda admin emas yoki xabar yuborish huquqi yo'q):\n"
            + "\n".join(f"• {html.escape(c)}" for c in fail_list)
        )
    await m.answer(text)


# ================== ADMIN: REJALASHTIRILGAN XABAR ==================
def parse_when(text: str) -> int | None:
    mt = re.fullmatch(r"\s*(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?\s+(\d{1,2}):(\d{2})\s*", text)
    if not mt:
        return None
    d, mo, y, h, mi = mt.groups()
    year = int(y) if y else datetime.now(TZ).year
    try:
        return int(datetime(year, int(mo), int(d), int(h), int(mi), tzinfo=TZ).timestamp())
    except ValueError:
        return None


@router.callback_query(F.data == "admin_sched_menu")
async def admin_sched_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilarga", callback_data="sched_new_users")],
            [InlineKeyboardButton(text="📣 Barcha kanallarga", callback_data="sched_new_channels")],
            [InlineKeyboardButton(text="📋 Rejalashtirilganlar", callback_data="sched_list")],
        ]
    )
    await c.message.answer("⏰ <b>Rejalashtirilgan xabar</b>\n\nKimga yuborilsin?", reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.in_({"sched_new_users", "sched_new_channels"}))
async def sched_new_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    kind = c.data.replace("sched_new_", "")
    await state.set_state(States.sched_msg)
    await state.update_data(kind=kind)
    await c.message.answer(
        "✍️ Yuboriladigan xabarni tashlang (matn, rasm, video — istalgani).\n"
        "Bekor qilish uchun /start bosing."
    )
    await c.answer()


@router.message(States.sched_msg)
async def sched_got_msg(m: Message, state: FSMContext):
    await state.update_data(mid=m.message_id)
    await state.set_state(States.sched_time)
    now = datetime.now(TZ).strftime("%d.%m %H:%M")
    await m.answer(
        "🕒 Qachon yuborilsin? (Toshkent vaqti)\n\n"
        "Formati: <code>kun.oy soat:daqiqa</code>\n"
        f"Masalan: <code>{now}</code>"
    )


@router.message(States.sched_time, F.text)
async def sched_got_time(m: Message, state: FSMContext):
    ts = parse_when(m.text)
    if ts is None:
        return await m.answer("⚠️ Xato format! Masalan: <code>25.10 18:30</code>")
    if ts <= int(time.time()):
        return await m.answer("⚠️ Bu vaqt o'tib ketgan. Kelajakdagi vaqtni yozing:")

    data = await state.get_data()
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO scheduled(kind, message_id, run_at) VALUES(?,?,?)",
            (data["kind"], data["mid"], ts),
        )
        sid = cur.lastrowid
        await db.commit()
    target = "👥 foydalanuvchilarga" if data["kind"] == "users" else "📣 kanallarga"
    await m.answer(f"✅ Rejalashtirildi! (#{sid})\n\n🕒 {fmt_ts(ts)}\n🎯 {target}")


@router.callback_query(F.data == "sched_list")
async def sched_list(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, kind, run_at FROM scheduled WHERE done=0 ORDER BY run_at")
        rows = await cur.fetchall()
    if not rows:
        return await c.answer("📭 Rejalashtirilgan xabar yo'q.", show_alert=True)

    lines = [
        f"#{sid} • {fmt_ts(ts)} • {'👥 foydalanuvchilar' if kind == 'users' else '📣 kanallar'}"
        for sid, kind, ts in rows
    ]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"❌ #{sid} ni bekor qilish", callback_data=f"sched_del_{sid}")]
                         for sid, _, _ in rows]
    )
    await c.message.answer("⏰ <b>Rejalashtirilganlar:</b>\n\n" + "\n".join(lines), reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.regexp(r"^sched_del_\d+$"))
async def sched_delete(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    sid = int(c.data.replace("sched_del_", ""))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("UPDATE scheduled SET done=1 WHERE id=? AND done=0", (sid,))
        await db.commit()
    await c.answer("Bekor qilindi." if cur.rowcount else "Allaqachon yuborilgan yoki bekor qilingan.", show_alert=True)


async def scheduler_loop(bot: Bot):
    while True:
        try:
            now = int(time.time())
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(
                    "SELECT id, kind, message_id FROM scheduled WHERE done=0 AND run_at<=?", (now,)
                )
                due = await cur.fetchall()
            for sid, kind, mid in due:
                async with aiosqlite.connect(DB_PATH) as db:
                    cur = await db.execute("UPDATE scheduled SET done=1 WHERE id=? AND done=0", (sid,))
                    await db.commit()
                    if cur.rowcount == 0:
                        continue
                if kind == "users":
                    res = await send_to_users(bot, mid)
                    report = report_text(res, "📊 <b>Natija:</b>")
                else:
                    ok_l, fail_l = await send_to_channels(bot, mid)
                    report = f"📬 Yuborildi: <b>{len(ok_l)}</b> ta kanal\n🚫 Yuborilmadi: <b>{len(fail_l)}</b> ta kanal"
                try:
                    await bot.send_message(ADMIN_ID, f"⏰ <b>Rejalashtirilgan xabar yuborildi!</b> (#{sid})\n\n{report}")
                except Exception:
                    pass
        except Exception as e:
            logging.error("scheduler_loop xato: %s", e)
            if "no such table" in str(e):
                try:
                    await init_db()
                except Exception:
                    pass
        await asyncio.sleep(20)


# ================== ADMIN: BAZA ZAXIRASI ==================
def _backup_sync(path: str):
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


async def send_backup(bot: Bot, caption: str = "💾 Baza zaxirasi"):
    name = f"bot_backup_{datetime.now(TZ):%Y%m%d_%H%M}.db"
    path = os.path.join(tempfile.gettempdir(), name)
    await asyncio.to_thread(_backup_sync, path)
    try:
        await bot.send_document(ADMIN_ID, FSInputFile(path, filename=name), caption=caption)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@router.callback_query(F.data == "admin_backup")
async def admin_backup(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("❌ Ruxsat yo'q", show_alert=True)
    await c.answer("⏳ Zaxira tayyorlanmoqda...")
    try:
        await send_backup(c.bot)
    except Exception as e:
        logging.error("Zaxira xato: %s", e)
        await c.message.answer("❌ Zaxira yuborilmadi.")


async def backup_loop(bot: Bot):
    while True:
        await asyncio.sleep(BACKUP_INTERVAL)
        try:
            await send_backup(bot, "💾 Avtomatik kunlik zaxira")
        except Exception as e:
            logging.error("Avtomatik zaxira xato: %s", e)


# =====================================================================
# 🎰 SLOT (OPEN) — har bir aylantirish FOYDALANUVCHINING TELEGRAM hisobidagi
# Stars orqali to'lanadi (invoice). Botdagi stars balansi aylantirishga ishlatilmaydi,
# u faqat yutuqlar va "Gift yechish" uchun.
# =====================================================================
SL = {
    "uz": {
        "screen": (
            "🎰 <b>SLOT — Open</b>\n\n"
            "┃ 🎰 ┃ 🎰 ┃ 🎰 ┃\n\n"
            "💵 Aylantirish narxi: <b>{cost} ⭐️</b> (Telegram hisobingizdan to'lanadi)\n"
            "🏆 Har <b>omadingizda </b> 7️⃣7️⃣7️⃣ tushishi mumkin — yutuq: <b>{prize} ⭐️</b>\n"

            "⭐️ Botdagi balansingiz (yutuqlar): <b>{stars}</b> ta"
        ),
        "spin_btn": "🎰 Aylantirish ({cost} ⭐️)",
        "inv_title": "🎰 Slot — 1 ta aylantirish",
        "inv_desc": "Telegram hisobingizdan {n} ⭐️ yechiladi va slot aylanadi",
        "paid_wait": "✅ To'lov qabul qilindi! Slot aylanmoqda...",
        "rolling": "🎰 <b>Aylanmoqda...</b>\n\n┃ {a} ┃ {b} ┃ {c} ┃",
        "lose": "🎰 <b>Natija</b>\n\n┃ {a} ┃ {b} ┃ {c} ┃\n\n😔 Bu safar yutuq yo'q. Yana urinib ko'ring!\n🎯 Yutush uchun: omad kerak\n⭐️ Botdagi balans: <b>{stars}</b>",
        "win": "🎰 <b>Natija</b>\n\n┃ 7️⃣ ┃ 7️⃣ ┃ 7️⃣ ┃\n\n🎉 <b>777! Siz yutdingiz — {prize} ⭐️!</b>\n⭐️ Botdagi balans: <b>{stars}</b>",
    },
    "ru": {
        "screen": (
            "🎰 <b>СЛОТ — Open</b>\n\n"
            "┃ 🎰 ┃ 🎰 ┃ 🎰 ┃\n\n"
            "💵 Цена вращения: <b>{cost} ⭐️</b> (оплата с вашего счёта Telegram)\n"
            "🏆 Каждое <b>{every}-е вращение</b> гарантированно даёт 7️⃣7️⃣7️⃣ — выигрыш: <b>{prize} ⭐️</b>\n"
            "🎯 До выигрыша: <b>{left}</b> вращ.\n\n"
            "⭐️ Баланс в боте (выигрыши): <b>{stars}</b>"
        ),
        "spin_btn": "🎰 Крутить ({cost} ⭐️)",
        "inv_title": "🎰 Слот — 1 вращение",
        "inv_desc": "С вашего счёта Telegram спишется {n} ⭐️ и слот прокрутится",
        "paid_wait": "✅ Оплата получена! Слот вращается...",
        "rolling": "🎰 <b>Вращается...</b>\n\n┃ {a} ┃ {b} ┃ {c} ┃",
        "lose": "🎰 <b>Результат</b>\n\n┃ {a} ┃ {b} ┃ {c} ┃\n\n😔 В этот раз без выигрыша. Попробуйте ещё!\n🎯 До выигрыша: <b>{left}</b> вращ.\n⭐️ Баланс в боте: <b>{stars}</b>",
        "win": "🎰 <b>Результат</b>\n\n┃ 7️⃣ ┃ 7️⃣ ┃ 7️⃣ ┃\n\n🎉 <b>777! Вы выиграли — {prize} ⭐️!</b>\n⭐️ Баланс в боте: <b>{stars}</b>",
    },
}

SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]


def sl(lang: str, key: str, **kw) -> str:
    text = SL.get(lang, SL["uz"])[key]
    return text.format(**kw) if kw else text


async def _slot_state(uid: int) -> tuple[int, int]:
    row = await safe_fetchone("SELECT stars, spin_count FROM users WHERE id=?", (uid,))
    if not row:
        return 0, 0
    return row[0] or 0, row[1] or 0


def _slot_kb(lang: str) -> InlineKeyboardMarkup:
    # Tugma doim bitta: bosilganda Telegram Stars invoice chiqadi
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=sl(lang, "spin_btn", cost=SPIN_COST), callback_data="slot_spin")]]
    )


def _left(cnt: int) -> int:
    return WIN_EVERY - (cnt % WIN_EVERY)


async def show_slot(m: Message, uid: int, lang: str):
    stars, cnt = await _slot_state(uid)
    await m.answer(
        sl(lang, "screen", cost=SPIN_COST, every=WIN_EVERY, prize=WIN_PRIZE, left=_left(cnt), stars=stars),
        reply_markup=_slot_kb(lang),
    )


# ---------- Aylantirish tugmasi: Telegram hisobidan to'lov (invoice) ----------
@router.callback_query(F.data == "slot_spin")
async def slot_spin(c: CallbackQuery):
    u = c.from_user
    lang = await get_lang(u.id)
    await c.answer()
    await c.message.answer_invoice(
        title=sl(lang, "inv_title"),
        description=sl(lang, "inv_desc", n=SPIN_COST),
        payload=f"slot_spin:{u.id}:{int(time.time())}",
        currency="XTR",  # Telegram Stars (foydalanuvchining o'z Telegram hisobi)
        prices=[LabeledPrice(label="1 spin", amount=SPIN_COST)],
    )


@router.pre_checkout_query()
async def slot_pre_checkout(q: PreCheckoutQuery):
    ok = q.invoice_payload.startswith(f"slot_spin:{q.from_user.id}:") and q.total_amount == SPIN_COST
    await q.answer(ok=ok, error_message=None if ok else "Xato to'lov / Ошибка платежа")


# ---------- To'lov o'tgach slot aylanadi ----------
@router.message(F.successful_payment)
async def slot_paid(m: Message):
    sp = m.successful_payment
    u = m.from_user
    if not sp.invoice_payload.startswith(f"slot_spin:{u.id}:"):
        return
    lang = await get_lang(u.id)

    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO star_payments(charge_id, user_id, amount, created_at) VALUES(?,?,?,?)",
                (sp.telegram_payment_charge_id, u.id, sp.total_amount, int(time.time())),
            )
        except sqlite3.IntegrityError:
            return  # bu to'lov allaqachon hisobga olingan
        # Aylantirish hisobi oshadi (botdagi stars'ga tegilmaydi)
        await db.execute("UPDATE users SET spin_count = COALESCE(spin_count,0) + 1 WHERE id=?", (u.id,))
        cur = await db.execute("SELECT spin_count FROM users WHERE id=?", (u.id,))
        cnt = (await cur.fetchone())[0]
        await db.commit()

    win = cnt % WIN_EVERY == 0

    msg = await m.answer(sl(lang, "paid_wait"))
    for _ in range(4):
        a, b, cc = (random.choice(SLOT_SYMBOLS) for _ in range(3))
        try:
            await msg.edit_text(sl(lang, "rolling", a=a, b=b, c=cc))
        except Exception:
            pass
        await asyncio.sleep(0.6)

    if win:
        # Yutuq botdagi stars balansiga qo'shiladi
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET stars = stars + ? WHERE id=?", (WIN_PRIZE, u.id))
            await db.commit()
        stars, _ = await _slot_state(u.id)
        text = sl(lang, "win", prize=WIN_PRIZE, stars=stars)
        try:
            uname = f"@{u.username}" if u.username else "yo'q"
            await m.bot.send_message(
                ADMIN_ID,
                f"🎰 <b>Bu odam 777 tushirdi!</b>\n\n👤 {html.escape(u.full_name)} ({uname})\n"
                f"🆔 <code>{u.id}</code>\n🏆 Yutuq: <b>{WIN_PRIZE} ⭐️</b> (aylantirish #{cnt})",
            )
        except Exception:
            pass
    else:
        while True:
            a, b, cc = (random.choice(SLOT_SYMBOLS) for _ in range(3))
            if not (a == b == cc):
                break
        stars, _ = await _slot_state(u.id)
        text = sl(lang, "lose", a=a, b=b, c=cc, left=_left(cnt), stars=stars)

    try:
        await msg.edit_text(text, reply_markup=_slot_kb(lang))
    except Exception:
        await m.answer(text, reply_markup=_slot_kb(lang))

    # Adminga har bir to'lov haqida xabar
    try:
        await m.bot.send_message(
            ADMIN_ID,
            f"💳 <b>Slot to'lovi:</b> {html.escape(u.full_name)} (<code>{u.id}</code>) — "
            f"<b>{sp.total_amount} ⭐️</b> (spin #{cnt})",
        )
    except Exception:
        pass


# ================== MAIN (ISHGA TUSHIRISH) ==================
async def main():
    logging.basicConfig(level=logging.INFO)
    if ":" not in BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN to'g'ri emas! Faylning tepasida BOT_TOKEN = \"...\" qatoriga "
            "@BotFather bergan haqiqiy (yangi) tokenni yozing (yoki BOT_TOKEN muhit o'zgaruvchisini o'rnating)."
        )
    await init_db()
    logging.info("Baza fayli: %s", DB_PATH)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    sub_mw = SubMiddleware()
    router.message.middleware(sub_mw)
    router.callback_query.middleware(sub_mw)
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)

    tasks = [asyncio.create_task(scheduler_loop(bot)), asyncio.create_task(backup_loop(bot))]
    try:
        await dp.start_polling(bot)
    finally:
        for t in tasks:
            t.cancel()


if __name__ == "__main__":
    asyncio.run(main())