import asyncio
from datetime import datetime
import io
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import qrcode

TOKEN = "8946349098:AAFQyl3pFcYC5EEnzDPxlYKKvHMe_8"
SUPER_ADMIN_ID = 5874144878

# MUHIM: Quyidagi matnga o'z botingizning USERNAME'ini yozib qo'ying (masalan: t.me/SizningBotingizUz_bot)
BOT_USERNAME = "SizningBotingizUz_bot" 
QR_DEEP_LINK_TEXT = f"https://t.me/{BOT_USERNAME}?start=davomat_2026"

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


def generate_qr_buffer(text: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def get_admin_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📊 Statistika va Panel")],
            [
                types.KeyboardButton(text="✅ Kelganlar"),
                types.KeyboardButton(text="❌ Kelmaganlar"),
            ],
            [types.KeyboardButton(text="📸 Tayyor QR-kodni olish")],
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
async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    args = command.args  # QR kod orqali o'tgandagi maxsus parametr

    # Agar talaba QR kodni skaner qilib kelsa:
    if args == "davomat_2026":
        if user_id in admins:
            await message.answer("Sizadminsiz, o'zingizga davomat kerak emas 😊")
            return
        if user_id not in registered_students:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz! Admin bilan bog'laning.")
            return

        current_time = datetime.now()
        student_data = registered_students[user_id]
        
        attendance_today[user_id] = {
            "name": student_data["name"],
            "course": student_data.get("course", "Nomaʼlum"),
            "time": current_time.strftime("%H:%M:%S"),
        }
        await message.answer(
            "✅ **Davomatingiz muvaffaqiyatli qabul qilindi!** Xush kelibsiz.",
            parse_mode="Markdown",
        )
        return

    # Oddiy holatda /start bosganda:
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

    await message.answer(
        "Xush kelibsiz! Admin kelib QR-kodni ko'rsatganda telefoningiz kamerasi bilan skaner qiling, davomatingiz avtomatik belgilanadi.",
    )


@dp.message(F.text == "📊 Statistika va Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id not in admins:
        return
    total_students = len(registered_students)
    sent_count = len(attendance_today)
    not_sent_count = total_students - sent_count

    await message.answer(
        f"📊 **Yotoqxona Davomat Statistikasi**\n\n"
        f"👥 Jami talabalar: **{total_students} ta**\n"
        f"✅ Kelganlar: **{sent_count} ta**\n"
        f"❌ Kelmaganlar: **{not_sent_count} ta**\n\n"
        f"⏱ **Vaqt qoidalari:**\n"
        f"• Kechki taqiq: `{TIME_RULES['night_start_hour']:02d}:{TIME_RULES['night_start_min']:02d}`\n"
        f"• Ertalabki ruxsat: `{TIME_RULES['morning_end_hour']:02d}:{TIME_RULES['morning_end_min']:02d}`",
        parse_mode="Markdown",
    )


@dp.message(F.text == "📸 Tayyor QR-kodni olish")
async def get_ready_qr(message: types.Message):
    if message.from_user.id not in admins:
        return
    
    qr_io = generate_qr_buffer(QR_DEEP_LINK_TEXT)
    photo = types.BufferedInputFile(qr_io.getvalue(), filename="qrcode.png")
    
    await message.answer_photo(
        photo=photo,
        caption="📱 **Mana tayyor QR-kod!**\nTalaba xonaga borganingizda shu rasmni ko'rsatasiz, u kamerasi bilan skaner qilsa bas — avtomatik tanib oladi.",
        parse_mode="Markdown",
    )


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


@dp.message(F.text == "🌙 Kechki vaqtni o'zgartirish (20:00)")
async def edit_night_time_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer("🌙 Kechki vaqtni kiriting (Masalan: `20:00`):", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_night_time)


@dp.message(AdminStates.waiting_for_night_time, F.text)
async def save_night_time(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        TIME_RULES["night_start_hour"], TIME_RULES["night_start_min"] = hour, minute
        await message.answer(f"✅ Kechki vaqt `{hour:02d}:{minute:02d}` etib o'zgartirildi!", reply_markup=get_admin_keyboard())
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri format. `HH:MM` ko'rinishida yuboring:")


@dp.message(F.text == "🌅 Ertalabki vaqtni o'zgartirish (05:00)")
async def edit_morning_time_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer("🌅 Ertalabki vaqtni kiriting (Masalan: `05:00`):", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_morning_time)


@dp.message(AdminStates.waiting_for_morning_time, F.text)
async def save_morning_time(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        TIME_RULES["morning_end_hour"], TIME_RULES["morning_end_min"] = hour, minute
        await message.answer(f"✅ Ertalabki vaqt `{hour:02d}:{minute:02d}` etib o'zgartirildi!", reply_markup=get_admin_keyboard())
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
        await message.answer(f"✅ `{new_id}` admin qilindi.", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")


@dp.message(F.text == "🗑 Adminni o'chirish")
async def remove_admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN_ID:
        return
    text = "🗑 **Adminlar:**\n" + "\n".join([str(a) for a in admins]) + "\n\nO'chirish uchun ID yuboring:"
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
            await message.answer("✅ Admin o'chirildi.", reply_markup=get_admin_keyboard())
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
    await message.answer("✅ Talaba muvaffaqiyatli qo'shildi!", reply_markup=get_admin_keyboard())
    await state.clear()


@dp.message(F.text == "🗑 Talabani o'chirish")
async def remove_student_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    await message.answer("🗑 O'chirish uchun talabaning ID raqamini yuboring:")
    await state.set_state(AdminStates.waiting_for_remove_student)


@dp.message(AdminStates.waiting_for_remove_student, F.text)
async def save_remove_worker(message: types.Message, state: FSMContext):
    try:
        s_id = int(message.text.strip())
        if s_id in registered_students:
            registered_students.pop(s_id)
            if s_id in attendance_today:
                attendance_today.pop(s_id)
            await message.answer("✅ Talaba o'chirildi.", reply_markup=get_admin_keyboard())
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
    await message.answer("✅ Xabar yuborildi!", reply_markup=get_admin_keyboard())
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
