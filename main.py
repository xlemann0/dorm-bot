import asyncio
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8946349098:AAFQKMlUCyl3pFcYC5EEnzDPxlYKKvHMe_8"
SUPER_ADMIN_ID = 5874144878

# Hozirgi aktiv QR / Maxfiy so'z (Buni admin yangilab turadi)
CURRENT_QR_CODE = "TTJ_DAVOMAT_2026_SESSION"  # Buni admin o'zgartirishi mumkin

TIME_RULES = {
    "night_start_hour": 20,
    "night_start_min": 0,
    "morning_end_hour": 5,
    "morning_end_min": 0,
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

admins = {SUPER_ADMIN_ID}
attendance_today = {}
registered_students = {}


class AdminStates(StatesGroup):
    waiting_for_new_admin_id = State()
    waiting_for_remove_admin_id = State()
    waiting_for_student_id = State()
    waiting_for_student_name = State()
    waiting_for_student_course = State()
    waiting_for_student_phone = State()
    waiting_for_remove_student = State()
    waiting_for_broadcast = State()
    waiting_for_night_time = State()
    waiting_for_morning_time = State()
    waiting_for_new_qr_code = State()  # Yangi QR kod / so'z kiritish


def get_admin_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📊 Statistika va Panel")],
            [
                types.KeyboardButton(text="✅ Kelganlar"),
                types.KeyboardButton(text="❌ Kelmaganlar"),
            ],
            [types.KeyboardButton(text="📸 QR-kodni yangilash")],
            [
                types.KeyboardButton(
                    text="🌙 Kechki vaqtni o'zgartirish (20:00)"
                ),
                types.KeyboardButton(
                    text="🌅 Ertalabki vaqtni o'zgartirish (05:00)"
                ),
            ],
            [
                types.KeyboardButton(text="➕ Admin qo'shish"),
                types.KeyboardButton(text="🗑 Adminni o'chirish"),
            ],
            [
                types.KeyboardButton(text="👤 Talaba qo'shish"),
                types.KeyboardButton(text="🗑 Talabani o'chirish"),
            ],
            [types.KeyboardButton(text="📢 Xabar yollash")],
        ],
        resize_keyboard=True,
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    if user_id in admins:
        await message.answer(
            "Salomat, Admin! Boshqaruv paneliga xush kelibsiz.",
            reply_markup=get_admin_keyboard(),
        )
        return

    if user_id not in registered_students:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[[
                types.InlineKeyboardButton(
                    text="💬 Adminga murojaat qilish", url="https://t.me/xlemann"
                )
            ]]
        )
        await message.answer(
            "❌ Siz adminlar tomonidan hali ro'yxatdan o'tkazilmagansiz!\n"
            "Botdan foydalanish uchun administratorga murojaat qiling.",
            reply_markup=keyboard,
        )
        return

    # Talaba uchun menyu (QR kodni skaner qilib yuborish uchun)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text="📷 QR-kodni yuborish / Skaner qilish")
        ]],
        resize_keyboard=True,
    )
    await message.answer(
        "Xush kelibsiz! Davomat qilish uchun xonadagi **QR-kodni skaner qilib** rasmini yuboring yoki maxsus kodni kiriting:",
        reply_markup=keyboard,
    )


@dp.message(F.text == "📊 Statistika va Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id not in admins:
        return
    total_students = len(registered_students)
    sent_count = len(attendance_today)
    not_sent_count = total_students - sent_count

    await message.answer(
        f"📊 **Yotoqxona Davomat Statistikasi (QR)**\n\n"
        f"👥 Jami talabalar: **{total_students} ta**\n"
        f"✅ Kelganlar: **{sent_count} ta**\n"
        f"❌ Kelmaganlar: **{not_sent_count} ta**\n\n"
        f"🔑 Hozirgi aktiv QR kaliti/so'zi: `{CURRENT_QR_CODE}`\n\n"
        f"⏱ **Vaqt qoidalari:**\n"
        f"• Kechki taqiq: `{TIME_RULES['night_start_hour']:02d}:{TIME_RULES['night_start_min']:02d}`\n"
        f"• Ertalabki ruxsat: `{TIME_RULES['morning_end_hour']:02d}:{TIME_RULES['morning_end_min']:02d}`",
        parse_mode="Markdown",
    )


@dp.message(F.text == "📸 QR-kodni yangilash")
async def update_qr_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer(
        "📸 Yangi QR-kod matnini yoki uning maxfiy kalitini yuboring (Talabalar shu kodni kiritadi yoki skaner qiladi):",
        parse_mode="Markdown",
    )
    await state.set_state(AdminStates.waiting_for_new_qr_code)


@dp.message(AdminStates.waiting_for_new_qr_code, F.text)
async def save_new_qr(message: types.Message, state: FSMContext):
    global CURRENT_QR_CODE
    CURRENT_QR_CODE = message.text.strip()
    await message.answer(
        f"✅ QR-kod kaliti muvaffaqiyatli yangilandi!\n🔑 Yangi kod: `{CURRENT_QR_CODE}`",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )
    await state.clear()


@dp.message(F.text == "✅ Kelganlar")
async def check_present_students(message: types.Message):
    if message.from_user.id not in admins:
        return
    if not attendance_today:
        await message.answer("⚠️ Hozircha hech kim davomat qilmadi.")
        return

    present_list = []
    for s_id, data in attendance_today.items():
        present_list.append(
            f"👤 {data['name']} ({data.get('course', 'Nomaʼlum')}) | ⏰ Vaqt:"
            f" {data['time']} | 🆔 `{s_id}`"
        )

    text = f"✅ **Kelganlar ({len(attendance_today)} ta):**\n\n" + "\n".join(
        present_list
    )
    if len(text) > 4096:
        text = text[:4096]
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "❌ Kelmaganlar")
async def check_absent_students(message: types.Message):
    if message.from_user.id not in admins:
        return

    absent_list = []
    for s_id, data in registered_students.items():
        if s_id not in attendance_today:
            absent_list.append(
                f"👤 {data['name']} ({data.get('course', 'Nomaʼlum')}) | 📞"
                f" {data['phone']} | 🆔 `{s_id}`"
            )

    if not absent_list:
        await message.answer("✅ Hamma ro'yxatdagi talabalar keldi!")
    else:
        text = f"❌ **Kelmaganlar ({len(absent_list)} ta):**\n\n" + "\n".join(
            absent_list
        )
        if len(text) > 4096:
            text = text[:4096]
        await message.answer(text, parse_mode="Markdown")


# Talaba QR kod tugmasini bosganda
@dp.message(F.text == "📷 QR-kodni yuborish / Skaner qilish")
async def scan_qr_prompt(message: types.Message):
    if message.from_user.id in admins:
        return
    if message.from_user.id not in registered_students:
        return

    await message.answer(
        "📲 Xonadagi QR-kodni skaner qiling. Agar telefoningiz skaner qilmasa, admin bergan **maxfiy matnni** shu yerga yozib yuboring:"
    )


# Talaba matnli kod yoki QR matnini yuborganda tekshirish
@dp.message(
    F.text
    & ~F.text.in_({
        "📊 Statistika va Panel",
        "✅ Kelganlar",
        "❌ Kelmaganlar",
        "📸 QR-kodni yangilash",
        "➕ Admin qo'shish",
        "🗑 Adminni o'chirish",
        "👤 Talaba qo'shish",
        "🗑 Talabani o'chirish",
        "📢 Xabar yollash",
    })
)
async def process_qr_text(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in admins or user_id not in registered_students:
        return

    # Agar biron FSM holatida bo'lmasa va oddiy matn yuborsa (demak QR kod matni yoki paroli)
    current_state = await state.get_state()
    if current_state is not None:
        return  # Boshqa holatda bo'lsa aralashmaymiz

    sent_text = message.text.strip()

    if sent_text == CURRENT_QR_CODE:
        student_data = registered_students[user_id]
        current_time = datetime.now()

        attendance_today[user_id] = {
            "name": student_data["name"],
            "course": student_data.get("course", "Nomaʼlum"),
            "time": current_time.strftime("%H:%M:%S"),
        }
        await message.answer(
            "✅ **Davomatingiz muvaffaqiyatli qabul qilindi!** Xush kelibsiz.",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            "❌ **Xato QR-kod!** Iltimos, xonadagi to'g'ri QR-kodni skaner qiling yoki admin bergan oxirgi kodni kiriting.",
            parse_mode="Markdown",
        )


# Vaqtlarni o'zgartirish handlerlari
@dp.message(F.text == "🌙 Kechki vaqtni o'zgartirish (20:00)")
async def edit_night_time_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer(
        "🌙 Kechki vaqtni kiriting (Masalan: `20:00`):", parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_night_time)


@dp.message(AdminStates.waiting_for_night_time, F.text)
async def save_night_time(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        TIME_RULES["night_start_hour"], TIME_RULES["night_start_min"] = (
            hour,
            minute,
        )
        await message.answer(
            f"✅ Kechki vaqt `{hour:02d}:{minute:02d}` etib o'zgartirildi!",
            reply_markup=get_admin_keyboard(),
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri format. `HH:MM` ko'rinishida yuboring:")


@dp.message(F.text == "🌅 Ertalabki vaqtni o'zgartirish (05:00)")
async def edit_morning_time_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer(
        "🌅 Ertalabki vaqtni kiriting (Masalan: `05:00`):", parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_morning_time)


@dp.message(AdminStates.waiting_for_morning_time, F.text)
async def save_morning_time(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        TIME_RULES["morning_end_hour"], TIME_RULES["morning_end_min"] = (
            hour,
            minute,
        )
        await message.answer(
            f"✅ Ertalabki vaqt `{hour:02d}:{minute:02d}` etib o'zgartirildi!",
            reply_markup=get_admin_keyboard(),
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri format. `HH:MM` ko'rinishida yuboring:")


@dp.message(F.text == "➕ Admin qo'shish")
async def add_admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN_ID:
        return
    await message.answer("🆔 Yangi adminning Telegram ID raqamini yuboring:")
    await state.set_state(AdminStates.waiting_for_new_admin_id)


@dp.message(AdminStates.waiting_for_new_admin_id, F.text)
async def save_new_admin(message: types.Message, state: FSMContext):
    try:
        new_id = int(message.text.strip())
        admins.add(new_id)
        await message.answer(
            f"✅ `{new_id}` admin qilindi.",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown",
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")


@dp.message(F.text == "🗑 Adminni o'chirish")
async def remove_admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN_ID:
        return
    text = (
        "🗑 **Adminlar:**\n"
        + "\n".join([str(a) for a in admins])
        + "\n\nO'chirish uchun ID yuboring:"
    )
    await message.answer(text, parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_remove_admin_id)


@dp.message(AdminStates.waiting_for_remove_admin_id, F.text)
async def save_remove_admin(message: types.Message, state: FSMContext):
    try:
        target_id = int(message.text.strip())
        if target_id == SUPER_ADMIN_ID:
            await message.answer("❌ Super Adminni o'chirib bo'lmaydi!")
            return
        if target_id in admins:
            admins.remove(target_id)
            await message.answer(
                "✅ Admin o'chirildi.", reply_markup=get_admin_keyboard()
            )
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam yuboring:")


@dp.message(F.text == "👤 Talaba qo'shish")
async def add_student_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer("🆔 Talabaning Telegram ID raqamini yuboring:")
    await state.set_state(AdminStates.waiting_for_student_id)


@dp.message(AdminStates.waiting_for_student_id, F.text)
async def get_student_id(message: types.Message, state: FSMContext):
    try:
        await state.update_data(student_id=int(message.text.strip()))
        await message.answer("✍️ Talabaning Ism va Familiyasini kiriting:")
        await state.set_state(AdminStates.waiting_for_student_name)
    except ValueError:
        await message.answer("❌ Faqat raqamli ID kiriting.")


@dp.message(AdminStates.waiting_for_student_name, F.text)
async def get_student_name(message: types.Message, state: FSMContext):
    await state.update_data(student_name=message.text)
    await message.answer("🎓 Talabaning kursini kiriting (masalan: 1-kurs):")
    await state.set_state(AdminStates.waiting_for_student_course)


@dp.message(AdminStates.waiting_for_student_course, F.text)
async def get_student_course(message: types.Message, state: FSMContext):
    await state.update_data(student_course=message.text.strip())
    await message.answer("📞 Talabaning telefon raqamini kiriting:")
    await state.set_state(AdminStates.waiting_for_student_phone)


@dp.message(AdminStates.waiting_for_student_phone, F.text)
async def get_student_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    registered_students[data["student_id"]] = {
        "name": data["student_name"],
        "course": data["student_course"],
        "phone": message.text,
    }
    await message.answer(
        "✅ Talaba muvaffaqiyatli qo'shildi!",
        reply_markup=get_admin_keyboard(),
    )
    await state.clear()


@dp.message(F.text == "🗑 Talabani o'chirish")
async def remove_student_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer(
        "🗑 O'chirish uchun talabaning ID raqamini yuboring:"
    )
    await state.set_state(AdminStates.waiting_for_remove_student)


@dp.message(AdminStates.waiting_for_remove_student, F.text)
async def save_remove_student(message: types.Message, state: FSMContext):
    try:
        s_id = int(message.text.strip())
        if s_id in registered_students:
            registered_students.pop(s_id)
            if s_id in attendance_today:
                attendance_today.pop(s_id)
            await message.answer(
                "✅ Talaba o'chirildi.", reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer("❌ Topilmadi. Qaytadan ID yuboring:")
            return
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam yuboring:")


@dp.message(F.text == "📢 Xabar yollash")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer("📢 E'lon matnini yozing:")
    await state.set_state(AdminStates.waiting_for_broadcast)


@dp.message(AdminStates.waiting_for_broadcast, F.text)
async def send_broadcast(message: types.Message, state: FSMContext):
    for student_id in registered_students.keys():
        try:
            await bot.send_message(student_id, f"📢 **E'lon:**\n\n{message.text}")
        except Exception:
            pass
    await message.answer(
        "✅ Xabar yuborildi!", reply_markup=get_admin_keyboard()
    )
    await state.clear()


async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = 10000
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    await web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
