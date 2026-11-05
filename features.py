"""
features.py — bot.py ga qo'shimcha funksiyalar:
  1) 🎁 Kunlik bonus (ketma-ket kunlar uchun oshib boradigan Stars)
  2) 🏅 Referal bosqich bonuslari (5 / 10 / 25 / 50 do'st)
  3) 🛡 Anti-flood (tugmani tez-tez bosishdan himoya)
  4) 🛠 Admin buyruqlari: /msg, /topbalans, /bugun, /cancel
  5) 📊 Har kuni soat 21:00 da adminlarga avtomatik hisobot
"""
import asyncio
import html
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

TZ = timezone(timedelta(hours=5))  # Toshkent

# bot.py dagi configure() chaqiruvi shu qiymatlarni to'ldiradi
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
ADMIN_IDS: set[int] = set()
ADMIN_ID = 0

# ---------------- SOZLAMALAR (o'zingizga moslang) ----------------
# Kunlik bonus: ketma-ket 1-kun, 2-kun, ... 7-kun uchun Stars (7-kundan keyin qaytadan boshlanadi)
DAILY_REWARDS = [1, 1, 1, 2, 2, 2, 3]
# Referal bosqichlari: {nechta faol do'st: beriladigan bonus Stars}
MILESTONES = {5: 3, 10: 7, 25: 20, 50: 50}
REPORT_HOUR = 21  # kunlik hisobot soati (Toshkent vaqti)

DAILY_BTN = {"uz": "🎁 Kunlik bonus", "ru": "🎁 Ежедневный бонус"}

TX = {
    "uz": {
        "daily_ok": (
            "🎁 <b>Kunlik bonus olindi!</b>\n\n"
            "⭐️ Sizga <b>{reward} ta Stars</b> qo'shildi.\n"
            "🔥 Ketma-ket kunlar: <b>{streak}</b>\n\n"
            "Ertaga qaytib keling — ketma-ket kirsangiz bonus oshadi! 🚀"
        ),
        "daily_done": (
            "⏳ Bugungi bonusni allaqachon olgansiz.\n"
            "🔥 Ketma-ket kunlar: <b>{streak}</b>\n\n"
            "Ertaga yana keling! 🎁"
        ),
        "milestone": (
            "🏅 <b>Tabriklaymiz!</b>\n\n"
            "Siz <b>{m}</b> ta faol do'st taklif qildingiz va bonus oldingiz:\n"
            "⭐️ <b>+{bonus} ta Stars</b>"
        ),
        "cancel": "❌ Amaliyot bekor qilindi.",
    },
    "ru": {
        "daily_ok": (
            "🎁 <b>Ежедневный бонус получен!</b>\n\n"
            "⭐️ Вам зачислено <b>{reward} Stars</b>.\n"
            "🔥 Дней подряд: <b>{streak}</b>\n\n"
            "Приходите завтра — чем дольше серия, тем больше бонус! 🚀"
        ),
        "daily_done": (
            "⏳ Сегодняшний бонус уже получен.\n"
            "🔥 Дней подряд: <b>{streak}</b>\n\n"
            "Приходите завтра! 🎁"
        ),
        "milestone": (
            "🏅 <b>Поздравляем!</b>\n\n"
            "Вы пригласили <b>{m}</b> активных друзей и получили бонус:\n"
            "⭐️ <b>+{bonus} Stars</b>"
        ),
        "cancel": "❌ Действие отменено.",
    },
}


def tx(lang: str, key: str, **kw) -> str:
    return TX.get(lang, TX["uz"])[key].format(**kw)


router = Router()


def configure(db_path: str, admin_ids: set[int], admin_id: int):
    global DB_PATH, ADMIN_IDS, ADMIN_ID
    DB_PATH, ADMIN_IDS, ADMIN_ID = db_path, set(admin_ids), admin_id


async def ensure_columns():
    """Yangi ustunlarni qo'shadi (baza almashtirilgan bo'lsa ham xavfsiz)."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("PRAGMA table_info(users)")
            have = {r[1] for r in await cur.fetchall()}
            if not have:
                return
            for col in ("daily_day", "daily_streak", "ref_milestone"):
                if col not in have:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
            await db.commit()
    except Exception as e:
        logging.warning("ensure_columns xato: %s", e)


async def _lang(uid: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
    return row[0] if row and row[0] in ("uz", "ru") else "uz"


# ================== 1) KUNLIK BONUS ==================
async def claim_daily(uid: int):
    await ensure_columns()
    today = datetime.now(TZ).date().toordinal()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(daily_day,0), COALESCE(daily_streak,0) FROM users WHERE id=?", (uid,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        last, streak = row
        if last >= today:
            return "done", streak, 0
        streak = streak + 1 if last == today - 1 else 1
        reward = DAILY_REWARDS[(streak - 1) % len(DAILY_REWARDS)]
        cur = await db.execute(
            "UPDATE users SET stars = stars + ?, daily_day=?, daily_streak=? "
            "WHERE id=? AND COALESCE(daily_day,0) < ?",
            (reward, today, streak, uid, today),
        )
        await db.commit()
        if cur.rowcount == 0:
            return "done", streak, 0
        return "ok", streak, reward


@router.message(F.text.in_(set(DAILY_BTN.values())))
async def daily_bonus(m: Message, state: FSMContext):
    await state.clear()
    lang = await _lang(m.from_user.id)
    res = await claim_daily(m.from_user.id)
    if res is None:
        return
    status, streak, reward = res
    if status == "ok":
        await m.answer(tx(lang, "daily_ok", reward=reward, streak=streak))
    else:
        await m.answer(tx(lang, "daily_done", streak=streak))


# ================== 2) REFERAL BOSQICH BONUSLARI ==================
async def check_milestones(bot: Bot, referrer_id: int):
    """try_reward_referrer ichidan chaqiriladi: yangi bosqichga yetgan bo'lsa bonus beradi."""
    if not referrer_id:
        return
    await ensure_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id=? AND rewarded=1", (referrer_id,)
        )
        count = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COALESCE(ref_milestone,0) FROM users WHERE id=?", (referrer_id,)
        )
        row = await cur.fetchone()
        if not row:
            return
        paid = row[0]
        new = [m for m in sorted(MILESTONES) if count >= m > paid]
        if not new:
            return
        bonus = sum(MILESTONES[m] for m in new)
        top = new[-1]
        cur = await db.execute(
            "UPDATE users SET stars = stars + ?, ref_milestone=? "
            "WHERE id=? AND COALESCE(ref_milestone,0)=?",
            (bonus, top, referrer_id, paid),
        )
        await db.commit()
        if cur.rowcount == 0:
            return
    try:
        lang = await _lang(referrer_id)
        await bot.send_message(referrer_id, tx(lang, "milestone", m=top, bonus=bonus))
    except Exception:
        pass


# ================== 3) ANTI-FLOOD ==================
class ThrottleMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan `delay` soniyadan tez kelgan xabar/tugmani o'tkazib yuboradi."""

    def __init__(self, delay: float = 0.6):
        self.delay = delay
        self.last: dict[int, float] = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if (
            not user
            or user.id in ADMIN_IDS
            or getattr(event, "successful_payment", None)
        ):
            return await handler(event, data)
        now = time.monotonic()
        if now - self.last.get(user.id, 0) < self.delay:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
            return
        self.last[user.id] = now
        if len(self.last) > 20000:  # xotira to'lib ketmasligi uchun
            cutoff = now - 60
            self.last = {k: v for k, v in self.last.items() if v > cutoff}
        return await handler(event, data)


# ================== 4) ADMIN BUYRUQLARI ==================
@router.message(Command("cancel"))
async def cancel_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(tx(await _lang(m.from_user.id), "cancel"))


@router.message(Command("msg"))
async def admin_msg(m: Message, command: CommandObject):
    if m.from_user.id not in ADMIN_IDS:
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        return await m.answer("⚠️ Format: <code>/msg ID matn</code>\nMasalan: <code>/msg 123456789 Salom!</code>")
    try:
        await m.bot.send_message(int(parts[0]), f"📩 <b>Admin xabari:</b>\n\n{html.escape(parts[1])}")
        await m.answer("✅ Xabar yuborildi.")
    except Exception as e:
        await m.answer(f"❌ Yuborilmadi: {html.escape(str(e))}")


@router.message(Command("topbalans"))
async def admin_top_balance(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, full_name, username, balance, stars FROM users "
            "ORDER BY balance DESC, stars DESC LIMIT 10"
        )
        rows = await cur.fetchall()
    if not rows:
        return await m.answer("📭 Foydalanuvchilar yo'q.")
    lines = []
    for i, (uid, name, uname, bal, stars) in enumerate(rows, 1):
        u = f" (@{html.escape(uname)})" if uname else ""
        lines.append(
            f"{i}. <b>{html.escape(name or 'Noma`lum')}</b>{u}\n"
            f"    🆔 <code>{uid}</code> | 💰 {bal:,} so'm | ⭐️ {stars} ta"
        )
    await m.answer("🏦 <b>Balansi eng katta 10 ta foydalanuvchi:</b>\n\n" + "\n".join(lines))


# ================== 5) KUNLIK HISOBOT ==================
async def build_report() -> str:
    start = int(datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        async def one(q: str, p: tuple = ()) -> int:
            cur = await db.execute(q, p)
            r = await cur.fetchone()
            return (r[0] or 0) if r else 0

        total = await one("SELECT COUNT(*) FROM users")
        new_today = await one("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (start,))
        top_n = await one("SELECT COUNT(*) FROM topups WHERE status='ok' AND created_at >= ?", (start,))
        top_sum = await one("SELECT SUM(amount) FROM topups WHERE status='ok' AND created_at >= ?", (start,))
        top_pend = await one("SELECT COUNT(*) FROM topups WHERE status='pending'")
        gift_pend = await one("SELECT COUNT(*) FROM withdraws WHERE status='pending'")
        slot_n = await one("SELECT COUNT(*) FROM star_payments WHERE created_at >= ?", (start,))
        slot_sum = await one("SELECT SUM(amount) FROM star_payments WHERE created_at >= ?", (start,))
    return (
        f"📊 <b>Kunlik hisobot</b> — {datetime.now(TZ):%d.%m.%Y}\n\n"
        f"👥 Jami foydalanuvchi: <b>{total}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{new_today}</b>\n\n"
        f"💳 Bugun tasdiqlangan to'ldirishlar: <b>{top_n}</b> ta — <b>{top_sum:,}</b> so'm\n"
        f"🎰 Bugungi slot to'lovlari: <b>{slot_n}</b> ta — <b>{slot_sum}</b> ⭐️\n\n"
        f"⏳ Kutilayotgan cheklar: <b>{top_pend}</b>\n"
        f"⏳ Kutilayotgan giftlar: <b>{gift_pend}</b>"
    )


@router.message(Command("bugun"))
async def admin_today(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    await m.answer(await build_report())


async def daily_report_loop(bot: Bot):
    last_sent = None
    while True:
        try:
            now = datetime.now(TZ)
            if now.hour == REPORT_HOUR and last_sent != now.date():
                last_sent = now.date()
                text = await build_report()
                for admin in ADMIN_IDS:
                    try:
                        await bot.send_message(admin, text)
                    except Exception as e:
                        logging.warning("Hisobot yuborilmadi (%s): %s", admin, e)
        except Exception as e:
            logging.error("daily_report_loop xato: %s", e)
        await asyncio.sleep(60)
