import asyncio
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8946349098:AAFQKMlUCyl3pFcYC5EEnzDPxlYKKvHMe_8"
SUPER_ADMIN_ID = 5874144878

dorm_location = {"lat": 40.785500, "lon": 72.343100}
ALLOWABLE_RADIUS = 150  # Metr

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
  waiting_for_student_id = State()
  waiting_for_student_name = State()
  waiting_for_student_course = State()  # Kursni so'rash uchun state
  waiting_for_student_phone = State()
  waiting_for_remove_student = State()  # Talabani o'chirish uchun state
  waiting_for_broadcast = State()
  waiting_for_dorm_location = State()
  waiting_for_night_time = State()
  waiting_for_morning_time = State()


def calculate_distance(lat1, lon1, lat2, lon2):
  R = 6371000
  dlat = radians(lat2 - lat1)
  dlon = radians(lon2 - lon1)
  a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(
      dlon / 2
  ) ** 2
  c = 2 * atan2(sqrt(a), sqrt(1 - a))
  return R * c


def get_admin_keyboard():
  return types.ReplyKeyboardMarkup(
      keyboard=[
          [types.KeyboardButton(text="📊 Statistika va Panel")],
          [
              types.KeyboardButton(text="✅ Lokatsiya yuborganlar"),
              types.KeyboardButton(text="❌ Lokatsiya yubormaganlar"),
          ],
          [types.KeyboardButton(text="📍 Yotoqxona manzilini o'zgartash")],
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
              types.KeyboardButton(text="👤 Talaba qo'shish"),
          ],
          [types.KeyboardButton(text="🗑 Talabani o'chirish")],
          [types.KeyboardButton(text="📢 Xabar yollash")],
      ],
      resize_keyboard=True,
  )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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

  keyboard = types.ReplyKeyboardMarkup(
      keyboard=[[
          types.KeyboardButton(
              text="📍 Davomat uchun lokatsiya yuborish", request_location=True
          )
      ]],
      resize_keyboard=True,
  )
  await message.answer(
      "Xush kelibsiz! Davomat belgilash uchun quyidagi tugmani bosing:",
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
      f"📊 **Yotoqxona Davomat Statistikasi**\n\n"
      f"👥 Jami botdagi talabalar: **{total_students} ta**\n"
      f"✅ Lokatsiya yuborganlar: **{sent_count} ta**\n"
      f"❌ Lokatsiya yubormaganlar: **{not_sent_count} ta**\n\n"
      f"⏱ **Hozirgi vaqt qoidalari:**\n"
      f"• Kechki taqiqlanish boshlanishi: `{TIME_RULES['night_start_hour']:02d}:{TIME_RULES['night_start_min']:02d}`\n"
      f"• Ertalabki ruxsat tugashi: `{TIME_RULES['morning_end_hour']:02d}:{TIME_RULES['morning_end_min']:02d}`\n\n"
      f"📍 Yotoqxona koordinatalari: `{dorm_location['lat']}, {dorm_location['lon']}`",
      parse_mode="Markdown",
  )


@dp.message(F.text == "✅ Lokatsiya yuborganlar")
async def check_present_students(message: types.Message):
  if message.from_user.id not in admins:
    return
  if not attendance_today:
    await message.answer("⚠️ Hozircha hech kim lokatsiya yubormadi.")
    return

  present_list = []
  for s_id, data in attendance_today.items():
    present_list.append(
        f"👤 {data['name']} ({data.get('course', 'Nomaʼlum')} - kurs) | ⏰ Vaqt:"
        f" {data['time']} | 🆔 `{s_id}`"
    )

  text = (
      f"✅ **Lokatsiya yuborganlar ({len(attendance_today)} ta):**\n\n"
      + "\n".join(present_list)
  )
  if len(text) > 4096:
    text = text[:4096]
  await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "❌ Lokatsiya yubormaganlar")
async def check_absent_students(message: types.Message):
  if message.from_user.id not in admins:
    return

  absent_list = []
  for s_id, data in registered_students.items():
    if s_id not in attendance_today:
      absent_list.append(
          f"👤 {data['name']} ({data.get('course', 'Nomaʼlum')} - kurs) | 📞"
          f" {data['phone']} | 🆔 `{s_id}`"
      )

  if not absent_list:
    await message.answer("✅ Hamma ro'yxatdagi talabalar lokatsiya yuborgan!")
  else:
    text = (
        f"❌ **Lokatsiya yubormaganlar ({len(absent_list)} ta):**\n\n"
        + "\n".join(absent_list)
    )
    if len(text) > 4096:
      text = text[:4096]
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "📍 Yotoqxona manzilini o'zgartash")
async def edit_dorm_location(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  keyboard = types.ReplyKeyboardMarkup(
      keyboard=[[
          types.KeyboardButton(
              text="📍 Yotoqxona lokatsiyasini yuborish", request_location=True
          )
      ]],
      resize_keyboard=True,
  )
  await message.answer(
      "📍 Yotoqxonaning yangi joylashuvini yuborish uchun pastdagi tugmani bosing:",
      reply_markup=keyboard,
  )
  await state.set_state(AdminStates.waiting_for_dorm_location)


@dp.message(AdminStates.waiting_for_dorm_location, F.location)
async def save_dorm_location(message: types.Message, state: FSMContext):
  dorm_location["lat"] = message.location.latitude
  dorm_location["lon"] = message.location.longitude

  await message.answer(
      "✅ Yotoqxona manzili muvaffaqiyatli yangilandi!",
      reply_markup=get_admin_keyboard(),
  )
  await state.clear()


# --- VAQTNI TAHRIRLASH ---


@dp.message(F.text == "🌙 Kechki vaqtni o'zgartirish (20:00)")
async def edit_night_time_start(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  await message.answer(
      "🌙 Kechki taqiqlanish boshlanadigan yangi vaqtni kiriting (Masalan:"
      " `20:00`):",
      parse_mode="Markdown",
  )
  await state.set_state(AdminStates.waiting_for_night_time)


@dp.message(AdminStates.waiting_for_night_time, F.text)
async def save_night_time(message: types.Message, state: FSMContext):
  try:
    parts = message.text.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
      raise ValueError()

    TIME_RULES["night_start_hour"] = hour
    TIME_RULES["night_start_min"] = minute

    await message.answer(
        f"✅ Kechki vaqt muvaffaqiyatli `{hour:02d}:{minute:02d}` etib"
        " o'zgartirildi!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )
    await state.clear()
  except ValueError:
    await message.answer(
        "❌ Noto'g'ri format. Iltimos, `HH:MM` ko'rinishida yuboring (masalan,"
        " `20:00`):",
        parse_mode="Markdown",
    )


@dp.message(F.text == "🌅 Ertalabki vaqtni o'zgartirish (05:00)")
async def edit_morning_time_start(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  await message.answer(
      "🌅 Ertalabki ruxsat tugaydigan yangi vaqtni kiriting (Masalan:"
      " `05:00`):",
      parse_mode="Markdown",
  )
  await state.set_state(AdminStates.waiting_for_morning_time)


@dp.message(AdminStates.waiting_for_morning_time, F.text)
async def save_morning_time(message: types.Message, state: FSMContext):
  try:
    parts = message.text.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
      raise ValueError()

    TIME_RULES["morning_end_hour"] = hour
    TIME_RULES["morning_end_min"] = minute

    await message.answer(
        f"✅ Ertalabki vaqt muvaffaqiyatli `{hour:02d}:{minute:02d}` etib"
        " o'zgartirildi!",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown",
    )
    await state.clear()
  except ValueError:
    await message.answer(
        "❌ Noto'g'ri format. Iltimos, `HH:MM` ko'rinishida yuboring (masalan,"
        " `05:00`):",
        parse_mode="Markdown",
    )


@dp.message(F.text == "➕ Admin qo'shish")
async def add_admin_start(message: types.Message, state: FSMContext):
  if message.from_user.id != SUPER_ADMIN_ID:
    return
  await message.answer("🆔 Yangi adminning Telegram ID raqamini yuboring:")
  await state.set_state(AdminStates.waiting_for_new_admin_id)


@dp.message(AdminStates.waiting_for_new_admin_id, F.text)
async def save_new_admin(message: types.Message, state: FSMContext):
  try:
    new_id = int(message.text)
    admins.add(new_id)
    await message.answer(
        f"✅ {new_id} ID raqamli foydalanuvchi admin qilindi.",
        reply_markup=get_admin_keyboard(),
    )
  except ValueError:
    await message.answer("❌ Noto'g'ri raqam.")
  await state.clear()


# --- TALABA QO'SHISH (BOSQICHMA-BOSQICH) ---


@dp.message(F.text == "👤 Talaba qo'shish")
async def add_student_start(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  await message.answer("🆔 Talabaning Telegram ID raqamini yuboring:")
  await state.set_state(AdminStates.waiting_for_student_id)


@dp.message(AdminStates.waiting_for_student_id, F.text)
async def get_student_id(message: types.Message, state: FSMContext):
  try:
    s_id = int(message.text)
    await state.update_data(student_id=s_id)
    await message.answer(
        "✍️ Talabaning **Ism va Familiyasini** kiriting (masalan: Alisher"
        " Valiyev):"
    )
    await state.set_state(AdminStates.waiting_for_student_name)
  except ValueError:
    await message.answer("❌ Noto'g'ri ID format. Faqat raqam kiriting.")


@dp.message(AdminStates.waiting_for_student_name, F.text)
async def get_student_name(message: types.Message, state: FSMContext):
  await state.update_data(student_name=message.text)
  
  # Kursni tanlash uchun klaviatura chiqaramiz
  keyboard = types.ReplyKeyboardMarkup(
      keyboard=[
          [types.KeyboardButton(text="1-kurs"), types.KeyboardButton(text="2-kurs")],
          [types.KeyboardButton(text="3-kurs"), types.KeyboardButton(text="4-kurs")]
      ],
      resize_keyboard=True,
      one_time_keyboard=True
  )
  await message.answer(
      "🎓 Talabaning **nechanchi bosqich (kurs)** talabasi ekanini tanlang yoki yozib yuboring:",
      reply_markup=keyboard
  )
  await state.set_state(AdminStates.waiting_for_student_course)


@dp.message(AdminStates.waiting_for_student_course, F.text)
async def get_student_course(message: types.Message, state: FSMContext):
  await state.update_data(student_course=message.text.strip())
  await message.answer(
      "📞 Talabaning **Telefon raqamini** kiriting (masalan: +998901234567):",
      reply_markup=types.ReplyKeyboardRemove()
  )
  await state.set_state(AdminStates.waiting_for_student_phone)


@dp.message(AdminStates.waiting_for_student_phone, F.text)
async def get_student_phone(message: types.Message, state: FSMContext):
  data = await state.get_data()
  s_id = data["student_id"]
  s_name = data["student_name"]
  s_course = data["student_course"]
  s_phone = message.text

  registered_students[s_id] = {
      "name": s_name,
      "course": s_course,
      "phone": s_phone,
  }

  await message.answer(
      f"✅ Talaba muvaffaqiyatli ro'yxatdan o'tkazildi!\n\n"
      f"👤 Ism: {s_name}\n"
      f"🎓 Kurs: {s_course}\n"
      f"📞 Tel: {s_phone}\n"
      f"🆔 ID: `{s_id}`",
      reply_markup=get_admin_keyboard(),
      parse_mode="Markdown",
  )

  try:
    await bot.send_message(
        s_id,
        "🎉 Siz admin tomonidan yotoqxona davomat botiga ro'yxatdan"
        " o'tkazildingiz! /start bosing.",
    )
  except Exception:
    pass

  await state.clear()


# --- TALABANI RO'YXATDAN O'CHIRISH ---


@dp.message(F.text == "🗑 Talabani o'chirish")
async def remove_student_start(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  if not registered_students:
    await message.answer("⚠️ Hozircha ro'yxatda talabalar yo'q.")
    return

  student_list = []
  for s_id, data in registered_students.items():
    student_list.append(
        f"👤 {data['name']} ({data.get('course', 'Nomaʼlum')}) — 🆔 `{s_id}`"
    )

  text = (
      "🗑 **Ro'yxatdan chiqarib tashlash uchun talabaning ID raqamini yuboring:**\n\n"
      + "\n".join(student_list)
  )
  await message.answer(text, parse_mode="Markdown")
  await state.set_state(AdminStates.waiting_for_remove_student)


@dp.message(AdminStates.waiting_for_remove_student, F.text)
async def save_remove_student(message: types.Message, state: FSMContext):
  try:
    s_id = int(message.text.strip())
    if s_id in registered_students:
      removed_data = registered_students.pop(s_id)
      # Agar bugun lokatsiya yuborgan bo'lsa, undan ham o'chiramiz
      if s_id in attendance_today:
        attendance_today.pop(s_id)

      await message.answer(
          f"✅ {removed_data['name']} muvaffaqiyatli ro'yxatdan chiqarib yuborildi!",
          reply_markup=get_admin_keyboard(),
      )
      try:
        await bot.send_message(
            s_id, "❌ Siz yotoqxona davomat botidan chiqarib yuborildingiz."
        )
      except Exception:
        pass
    else:
      await message.answer(
          "❌ Bunday ID raqamli talaba topilmadi. Qaytadan urinib ko'ring yoki"
          " boshqa ID yuboring:"
      )
      return
  except ValueError:
    await message.answer(
        "❌ Noto'g'ri format. Iltimos, faqat talabaning raqamli ID'sini yuboring:"
    )
    return

  await state.clear()


@dp.message(F.text == "📢 Xabar yollash")
async def broadcast_start(message: types.Message, state: FSMContext):
  if message.from_user.id not in admins:
    return
  await message.answer("📢 Talabalarga yuboriladigan xatni yozing:")
  await state.set_state(AdminStates.waiting_for_broadcast)


@dp.message(AdminStates.waiting_for_broadcast, F.text)
async def send_broadcast(message: types.Message, state: FSMContext):
  for student_id in registered_students.keys():
    try:
      await bot.send_message(student_id, f"📢 **E'lon:**\n\n{message.text}")
    except Exception:
      pass
  await message.answer(
      "✅ Xabar barcha talabalarga yuborildi!",
      reply_markup=get_admin_keyboard(),
  )
  await state.clear()


@dp.message(F.location)
async def handle_location(message: types.Message):
  user_id = message.from_user.id
  if user_id in admins:
    return

  if user_id not in registered_students:
    await message.answer("❌ Siz ro'yxatdan o'tmagansiz!")
    return

  user_lat = message.location.latitude
  user_lon = message.location.longitude

  distance = calculate_distance(
      user_lat, user_lon, dorm_location["lat"], dorm_location["lon"]
  )
  student_data = registered_students[user_id]
  student_name = student_data["name"]
  student_course = student_data.get("course", "Nomaʼlum")
  student_phone = student_data["phone"]

  current_time = datetime.now()
  current_total_minutes = current_time.hour * 60 + current_time.minute

  night_minutes = (
      TIME_RULES["night_start_hour"] * 60 + TIME_RULES["night_start_min"]
  )
  morning_minutes = (
      TIME_RULES["morning_end_hour"] * 60 + TIME_RULES["morning_end_min"]
  )

  if distance <= ALLOWABLE_RADIUS:
    attendance_today[user_id] = {
        "name": student_name,
        "course": student_course,
        "time": current_time.strftime("%H:%M:%S"),
    }
    await message.answer(
        f"✅ Davomatingiz qabul qilindi! Yotoqxona hududasiz ({int(distance)}"
        " metr)."
    )
  else:
    await message.answer(
        f"❌ **Diqqat! Siz yotoqxona hududidan tashqaridasiz!**\n\n"
        f"📍 Yotoqxonagacha bo'lgan masofa: {int(distance)} metr.\n"
        f"⚠️ Ruxsat etilgan radius: {ALLOWABLE_RADIUS} metrdan oshmasligi kerak.",
        parse_mode="Markdown",
    )

    is_restricted_time = False
    if night_minutes > morning_minutes:
      if (
          current_total_minutes >= night_minutes
          or current_total_minutes < morning_minutes
      ):
        is_restricted_time = True
    else:
      if morning_minutes <= current_total_minutes < night_minutes:
        is_restricted_time = True

    if is_restricted_time:
      alert_text = (
          f"🚨 **RUXSAT ETILMAGAN VAQTda CHIQISH!**\n\n"
          f"👤 Talaba: {student_name} ({student_course})\n"
          f"📞 Tel: {student_phone}\n"
          f"🆔 ID: `{user_id}`\n"
          f"📍 Masofa: {int(distance)} metr\n"
          f"⏰ Vaqt: {current_time.strftime('%H:%M:%S')}"
      )
      for admin_id in admins:
        try:
          await bot.send_message(admin_id, alert_text, parse_mode="Markdown")
        except Exception:
          pass

      await message.answer(
          "⚠️ **DIQQAT!** Belgilangan taqiqlangan vaqt oralig'ida yotoqxona"
          " hududidan 150 metrdan ortiq masofaga chiqib ketganingiz qayd etildi"
          " va administratorlarga xabar berildi!"
      )


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
