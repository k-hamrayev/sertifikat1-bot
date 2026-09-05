# -*- coding: utf-8 -*-
import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent
from PIL import Image, ImageDraw, ImageFont

TOKEN = "8668050445:AAGxV-kUSKmoDsyrtCYFvrX6RTEv42E2eUY"
CHANNEL_USERNAME = "@RMMM_Angor_tumani"

QUESTION_TIME_LIMIT = 15  # ⏱ ҳар бир савол учун сония

dp = Dispatcher()

# chat_id -> asyncio.Task (савол учун ишлаётган таймер)
active_timers: dict[int, asyncio.Task] = {}

# Фойдаланувчилар кесишиб кетишининг олдини олиш учун қулфлар (Locks)
user_locks: dict[int, asyncio.Lock] = {}

def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


class TestState(StatesGroup):
    question_index = State()
    score = State()


QUESTIONS = [
    {
        "question": "1. Амир Темур 1370 йилда ҳокимиятни қўлга киритгач, нега дарҳол ўзини «хон» деб эълон қилмаган?",
        "options": [
            "Чиғатой сулоласидан бўлмагани учун хон унвонидан фойдаланиб, Суюрғатмишхонни номига хон қилиб қўйган",
            "У ҳали Самарқандни тўлиқ эгалламагани учун",
            "У Хуросондаги ҳукмдордан рухсат кутаётгани учун",
            "У Темурийлар сулоласини ҳали тузмагани учун"
        ],
        "correct": 0
    },
    {
        "question": "2. Мирзо Улуғбекнинг фожиали ўлими билан боғлиқ қайси сана тарихда аниқ қайд этилган?",
        "options": [
            "1447 йил 12 март",
            "1449 йил 25 октябрь",
            "1450 йил 8 май",
            "1449 йил 1 сентябрь"
        ],
        "correct": 1
    },
    {
        "question": "3. 1526 йилги Биринчи Панипат жангида Бобур қўшинининг устунлиги фақат сон ёки жасорат билан эмас, асосан қайси икки омил билан боғлиқ эди?",
        "options": [
            "Жанговар филлар ва денгиз флоти",
            "Артиллерия ҳамда «тулғама» ва «араба» тактикалари",
            "Отлиқ аскарларнинг оғир совути ва камончилар",
            "Фақат порохли милтиқлар"
        ],
        "correct": 1
    },
    {
        "question": "4. 1740 йилда Нодиршоҳ Бухоро ҳукмдори Абулфайзхонни мағлуб этгач, унинг мақоми қандай бўлиб қолди?",
        "options": [
            "Бухоро Нодиршоҳ давлатига тўлиқ қўшиб юборилди",
            "Абулфайзхон тахтдан туширилиб, Бухоро мустақил республикага айланди",
            "Абулфайзхон Нодиршоҳнинг тобе ҳукмдори сифатида қолдирилди",
            "Аштархонийлар сулоласи шу заҳоти бутунлай тугатилди"
        ],
        "correct": 2
    },
    {
        "question": "5. 1865 йил Тошкент мудофаасида Қўқон хонлиги қўшинларига амалда ким раҳбарлик қилган?",
        "options": [
            "Худоёрхон",
            "Мулла Олимхон",
            "Алимқул",
            "Насриддинхон"
        ],
        "correct": 2
    },
    {
        "question": "6. 1917 йилда Тошкентда тузилган «Шўрои Исломия» ташкилотининг асосий мақсади қайси жавобда тўғри берилган?",
        "options": [
            "Большевиклар ҳокимиятини ўрнатиш",
            "Чор ҳукуматини тиклаш",
            "Туркистон мусулмон аҳолисининг миллий-сиёсий манфаатларини ифода этиш ва сиёсий фаоллигини кучайтириш",
            "Фақат диний маросимларни назорат қилиш"
        ],
        "correct": 2
    },
    {
        "question": "7. 1898 йилда Андижонда Россия империяси мустамлакачилигига қарши қўзғолонга ким раҳбарлик қилган?",
        "options": [
            "Маҳмудхўжа Беҳбудий",
            "Муҳаммад Али Ҳалфа — Дукчи Эшон",
            "Мунавварқори Абдурашидхонов",
            "Фитрат"
        ],
        "correct": 1
    },
    {
        "question": "8. Иброҳимбек Лақайнинг совет ҳокимиятига қарши кураши қайси йилгача давом этган?",
        "options": [
            "1924 йилгача",
            "1927 йилгача",
            "1931 йилгача",
            "1937 йилгача"
        ],
        "correct": 2
    },
    {
        "question": "9. 1916 йилда Туркистонда кенг кўламли халқ қўзғолонига бевосита туртки бўлган асосий сабаб нима эди?",
        "options": [
            "Ер-сув ислоҳотларининг бекор қилиниши",
            "Жадид мактабларининг ёпилиши",
            "Маҳаллий аҳолини фронт орти ишларига мажбуран сафарбар қилиш ҳақидаги фармон",
            "Бухоро амирлигининг тугатилиши"
        ],
        "correct": 2
    },
    {
        "question": "10. Акмал Икромов 1937 йилда қайси сиёсий жараён доирасида ҳибсга олинган?",
        "options": [
            "Қўқон мухторияти иши",
            "Сталин давридаги катта сиёсий қатағонлар",
            "Иккинчи жаҳон уруши билан боғлиқ ҳарбий иш",
            "Бухоро амирлигини тиклаш ҳаракати"
        ],
        "correct": 1
    },
    {
        "question": "11. Иккинчи жаҳон уруши йилларида Ўзбекистонга жуда кўплаб завод-фабрикаларнинг кўчирилишига асосий сабаб нима эди?",
        "options": [
            "Ўзбекистонда нефть захиралари кўплиги",
            "Тошкентнинг денгиз портларига яқинлиги",
            "СССРнинг ғарбий ҳудудларидаги корхоналарни фронтдан узоқроқ, хавфсиз ҳудудларга эвакуация қилиш зарурати",
            "Ўзбекистонда барча заводлар аввалдан мавжуд бўлгани"
        ],
        "correct": 2
    },
    {
        "question": "12. «Буюк ипак йўли» атамасини илмий муомалага биринчи бўлиб қандай олим киритган?",
        "options": [
            "Аҳмад Фарғоний",
            "Фердинанд фон Рихтгофен",
            "Василий Бартольд",
            "Алексей Бертельс"
        ],
        "correct": 1
    },
    {
        "question": "13. Шароф Рашидов Ўзбекистон Компартияси Марказий Комитетининг биринчи котиби сифатида қайси йиллар оралиғида раҳбарлик қилди?",
        "options": [
            "1953–1964 йиллар",
            "1959–1983 йиллар",
            "1966–1989 йиллар",
            "1946–1970 йиллар"
        ],
        "correct": 1
    },
    {
        "question": "14. Туркистон мухториятининг биринчи раҳбари ким бўлган?",
        "options": [
            "Мунавварқори Абдурашидхонов",
            "Муҳаммаджон Тинишбоев",
            "Маҳмудхўжа Беҳбудий",
            "Абдурауф Фитрат"
        ],
        "correct": 1
    },
    {
        "question": "15. Ўзбекистонда миллий валюта — сўм қачон муомалага киритилган?",
        "options": [
            "1991 йил 1 сентябрь",
            "1992 йил 8 декабрь",
            "1993 йил 1 ноябрь",
            "1994 йил 1 июль"
        ],
        "correct": 3
    }
]

# ---------------------------------------------------------------------------
# СЕРТИФИКАТ ГЕНЕРАЦИЯСИ
# ---------------------------------------------------------------------------
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "DejaVuSerif-Bold.ttf",
    "LiberationSerif-Bold.ttf",
    "timesbd.ttf",
    "arialbd.ttf",
    "arial.ttf",
]

CERT_BG_PATH = "certificate_bg.jpg"
CERT_TEXT_COLOR = "#111827"
CERT_MAX_TEXT_WIDTH_RATIO = 0.62 
CERT_BASE_FONT_SIZE = 65
CERT_MIN_FONT_SIZE = 30
CERT_TEXT_Y_RATIO = 0.53


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_certificate(user_name: str) -> str:
    cert_filename = f"cert_{user_name.replace(' ', '_')}.png"

    if os.path.exists(CERT_BG_PATH):
        img = Image.open(CERT_BG_PATH).convert("RGB")
    else:
        img = Image.new("RGB", (1200, 850), color=(255, 255, 255))

    draw = ImageDraw.Draw(img)
    width, height = img.size

    max_width_px = width * CERT_MAX_TEXT_WIDTH_RATIO
    font_size = CERT_BASE_FONT_SIZE
    font = _load_font(font_size)

    while font_size > CERT_MIN_FONT_SIZE:
        bbox = draw.textbbox((0, 0), user_name, font=font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width_px:
            break
        font_size -= 2
        font = _load_font(font_size)

    text_x = width / 2
    text_y = height * CERT_TEXT_Y_RATIO

    draw.text((text_x, text_y), user_name, fill=CERT_TEXT_COLOR, anchor="mm", font=font)

    img.save(cert_filename)
    return cert_filename


# ---------------------------------------------------------------------------
# ОБУНАНИ ТЕКШИРИШ
# ---------------------------------------------------------------------------
async def check_subscription(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logging.error(f"Обунани текширишда хатолик: {e}")
    return False


# ---------------------------------------------------------------------------
# ТАЙМЕР БОШҚАРУВИ
# ---------------------------------------------------------------------------
def _cancel_timer(chat_id: int) -> None:
    task = active_timers.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


async def _question_timeout_watcher(message: Message, state: FSMContext, expected_index: int, user_id: int) -> None:
    try:
        await asyncio.sleep(QUESTION_TIME_LIMIT)

        async with get_user_lock(user_id):
            data = await state.get_data()
            if data.get("question_index") != expected_index:
                return

            await state.update_data(question_index=expected_index + 1)

            try:
                await message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass

            await send_question_new(message, state, user_id=user_id)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Taymerda xatolik: {e}")


# ---------------------------------------------------------------------------
# ЯНГИ САВОЛ ЮБОРИШ ФУНКЦИЯЛАРИ
# ---------------------------------------------------------------------------
async def send_question_new(message: Message, state: FSMContext, user_id: int = 0) -> None:
    data = await state.get_data()
    q_index = data.get("question_index")

    _cancel_timer(message.chat.id)

    if q_index is not None and q_index < len(QUESTIONS):
        q_data = QUESTIONS[q_index]

        text = f"<b>{q_data['question']}</b>\n\n"
        letters = ["A", "B", "C", "D"]
        for i, option in enumerate(q_data["options"]):
            text += f"<b>{letters[i]})</b> {option}\n"

        text += f"\n⏱ <i>{QUESTION_TIME_LIMIT} soniya ichida javob bering!</i>"
        text += f"\n<i>(Савол {q_index + 1} / {len(QUESTIONS)})</i>"

        # Ҳар бир тугмага савол индекси қўшиб берилади (ans_variant_index)
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="A", callback_data=f"ans_0_{q_index}"),
                InlineKeyboardButton(text="B", callback_data=f"ans_1_{q_index}"),
                InlineKeyboardButton(text="C", callback_data=f"ans_2_{q_index}"),
                InlineKeyboardButton(text="D", callback_data=f"ans_3_{q_index}"),
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        new_msg = await message.answer(text, reply_markup=keyboard)

        timer_task = asyncio.create_task(
            _question_timeout_watcher(new_msg, state, q_index, user_id)
        )
        active_timers[message.chat.id] = timer_task

    else:
        score = data.get("score", 0)
        total = len(QUESTIONS)
        user_name = message.chat.full_name or "Foydalanuvchi"

        try:
            await message.answer(
                f"🎉 <b>Тест якунланди!</b>\n\n"
                f"Сизнинг натижангиз: <b>{score} / {total}</b> та тўғри жавоб.\n\n"
                f"🏆 Мана сизнинг шахсий сертификатингиз тайёрланмоқда..."
            )
        except TelegramBadRequest:
            pass

        cert_path = generate_certificate(user_name)
        photo = FSInputFile(cert_path)

        await message.answer_photo(
            photo=photo,
            caption=f"🏆 Табриклайман, {html.bold(user_name)}!\nСиз сертификатни муваффақиятли қўлга киритдингиз!"
        )

        if os.path.exists(cert_path):
            os.remove(cert_path)

        await state.clear()


# ---------------------------------------------------------------------------
# ХЕНДЛЕРЛАР
# ---------------------------------------------------------------------------
@dp.message(CommandStart())
async def command_start_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    is_subscribed = await check_subscription(bot, user_id)

    if not is_subscribed:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Каналга обуна бўлиш", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="🔄 Обунани текшириш", callback_data="check_sub")]
        ])
        await message.answer(
            "⚠️ Ботдан фойдаланиш учун қуйидаги каналга обуна бўлишингиз керак!",
            reply_markup=keyboard
        )
    else:
        user_name = message.from_user.full_name
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Тестни бошлаш", callback_data="start_test")]
        ])
        await message.answer(
            f"Салом, {html.bold(user_name)}! Ангор тумани тарих тест ботига хуш келибсиз. 🚀\n"
            f"Бу ерда сизни Ўзбекистон тарихидан 15 та тест кутмоқда ва юқори натижа учун шахсий сертификат берилади!\n"
            f"⏱ Ҳар бир саволга {QUESTION_TIME_LIMIT} сониядан вақт берилади.\n\n"
            f"Тайёр бўлсангиз тугмани босинг:",
            reply_markup=keyboard
        )


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(bot, user_id)

    if is_subscribed:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Тестни бошлаш", callback_data="start_test")]
        ])
        try:
            await callback.message.edit_text(
                "Раҳмат! Сиз каналга обуна бўлдингиз. ✅\nЭнди тестни бошлашингиз мумкин.",
                reply_markup=keyboard
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "Раҳмат! Сиз каналга обуна бўлдингиз. ✅\nЭнди тестни бошлашингиз мумкин.",
                reply_markup=keyboard
            )
    else:
        await callback.answer("❌ Сиз ҳали каналга обуна бўлмадингиз!", show_alert=True)


@dp.callback_query(F.data == "start_test")
async def start_test(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    async with get_user_lock(user_id):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await state.set_state(TestState.question_index)
        await state.update_data(question_index=0, score=0)
        await send_question_new(callback.message, state, user_id=user_id)
        await callback.answer()


@dp.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    
    async with get_user_lock(user_id):
        try:
            parts = callback.data.split("_")
            selected_option = int(parts[1])
            btn_question_index = int(parts[2])  # Тугма босилган саволнинг аниқ индекси

            data = await state.get_data()
            current_q_index = data.get("question_index")
            score = data.get("score", 0)

            # Агар тест аллақачон тугаган бўлса
            if current_q_index is None:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                await callback.answer("Бу тест аллақачон якунланган.", show_alert=True)
                return

            # Агар фойдаланувчи ЭСКИ (аллақачон ўтиб кетган ёки жавоб берилган) саволнинг тугмасини босса:
            if btn_question_index != current_q_index:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                await callback.answer("Бу савол учун вақт аллақачон ўтган ёки жавоб берилган!", show_alert=True)
                return

            # Ҳозирги фаол тугмани ўчирамиз
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            # Таймерни тўхтатамиз
            _cancel_timer(callback.message.chat.id)

            q_data = QUESTIONS[current_q_index]
            if selected_option == q_data["correct"]:
                score += 1

            await state.update_data(question_index=current_q_index + 1, score=score)
            await send_question_new(callback.message, state, user_id=user_id)
            await callback.answer()
        except Exception:
            logging.exception("process_answer ichida xatolik")
            await callback.answer("⚠️ Хатолик юз берди, қайта уриниб кўринг.", show_alert=True)


@dp.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    logging.exception(
        f"Global xatolik: update={event.update.model_dump_json(exclude_none=True)}",
        exc_info=event.exception,
    )
    return True


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
