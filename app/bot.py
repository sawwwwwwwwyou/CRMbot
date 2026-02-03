"""Main bot module with message batching and multi-user support."""
import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN, BATCH_TIMEOUT_SECONDS, SAME_LEAD_WINDOW_MINUTES, BOT_USERNAME, STATUS_ORDER, STATUSES, LEADS_PER_PAGE
from app.services.database import (
    create_lead, get_lead, get_lead_messages, update_lead_status,
    get_leads_by_status, search_leads, get_stats, get_recent_lead_by_contact,
    add_messages_to_lead, update_lead_parsed_data, get_all_messages_text,
    update_lead_field, toggle_lead_hot
)
from app.services.ai_parser import parse_messages
from app.utils.keyboards import (
    get_lead_keyboard, get_add_to_lead_keyboard,
    get_back_keyboard, get_edit_keyboard, get_leads_list_keyboard
)
from app.utils.formatters import (
    format_lead, format_new_lead, format_originals, format_stats,
    format_leads_by_status, format_lead_short
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# FSM States for editing
class EditStates(StatesGroup):
    waiting_for_value = State()


# Message buffer for batching
# Structure: {(user_id, sender_key): {"messages": [...], "task": asyncio.Task, "chat_id": int, "user_id": int}}
message_buffer: dict = {}

# Pending messages for add-to-lead flow
# Structure: {(user_id, chat_id): {"messages": [...], "sender_info": {...}}}
pending_messages: dict = {}


def get_sender_key(message: Message) -> tuple[Optional[int], Optional[str]]:
    """Extract sender identifier from forwarded message."""
    if message.forward_from:
        return (message.forward_from.id, None)
    elif message.forward_sender_name:
        return (None, message.forward_sender_name)
    return (None, None)


def get_sender_info(message: Message) -> dict:
    """Extract sender info from forwarded message."""
    info = {
        "telegram_id": None,
        "name": None,
        "username": None
    }

    if message.forward_from:
        info["telegram_id"] = message.forward_from.id
        info["name"] = message.forward_from.full_name
        info["username"] = message.forward_from.username
    elif message.forward_sender_name:
        info["name"] = message.forward_sender_name

    return info


async def process_batch(buffer_key: str, chat_id: int, user_id: int):
    """Process batched messages after timeout."""
    async with ChatActionSender.typing(bot=bot, chat_id=chat_id):
        await asyncio.sleep(BATCH_TIMEOUT_SECONDS)

    if buffer_key not in message_buffer:
        return

    batch_data = message_buffer.pop(buffer_key)
    messages = batch_data["messages"]
    sender_info = batch_data["sender_info"]

    if not messages:
        return

    logger.info(f"Processing batch of {len(messages)} messages for user {user_id}")

    # Check for recent lead from same contact (for this user)
    recent_lead = await get_recent_lead_by_contact(
        user_id,
        sender_info["telegram_id"],
        sender_info["name"],
        SAME_LEAD_WINDOW_MINUTES
    )

    if recent_lead:
        pending_key = (user_id, chat_id)
        pending_messages[pending_key] = {
            "messages": messages,
            "sender_info": sender_info
        }

        brand = recent_lead.get("brand") or "Без названия"
        await bot.send_message(
            chat_id,
            f"🔄 Найден недавний лид от этого контакта:\n#{recent_lead['id']} — {brand}\n\nДобавить сообщения к существующему лиду?",
            reply_markup=get_add_to_lead_keyboard(recent_lead["id"], brand)
        )
        return

    await create_new_lead_from_messages(chat_id, user_id, messages, sender_info)


async def create_new_lead_from_messages(chat_id: int, user_id: int, messages: list[dict], sender_info: dict):
    """Create a new lead from collected messages."""
    combined_text = "\n\n---\n\n".join([m["text"] for m in messages])

    parsed = await parse_messages(combined_text)
    logger.info(f"AI parsed: {parsed}")

    lead_id = await create_lead(
        user_id=user_id,
        contact_telegram_id=sender_info["telegram_id"],
        contact_name=parsed.get("contact") or sender_info["name"],
        contact_username=sender_info["username"],
        brand=parsed.get("brand"),
        request=parsed.get("request"),
        dates=parsed.get("dates"),
        raw_messages=messages
    )

    lead = await get_lead(lead_id, user_id)
    message_count = len(messages)

    await bot.send_message(
        chat_id,
        format_new_lead(lead, message_count),
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )


# === COMMAND HANDLERS ===

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command with deep link support."""
    user_id = message.from_user.id
    
    # Check for deep link parameters
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1]
        
        # Handle lead deep link: lead_123 or lead_123_page_2
        if param.startswith("lead_"):
            parts = param.replace("lead_", "").split("_page_")
            lead_id = int(parts[0])
            
            lead = await get_lead(lead_id, user_id)
            if not lead:
                await message.answer("❌ Лид не найден или у вас нет доступа.")
                return
            
            messages = await get_lead_messages(lead_id)
            await message.answer(
                format_lead(lead, len(messages)),
                reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
            )
            return
        
        # Handle leads page deep link: leads_page_2
        if param.startswith("leads_page_"):
            page = int(param.replace("leads_page_", ""))
            await show_leads_page(message, user_id, page)
            return
    
    # Default start message
    await message.answer(
        "🤖 CRM Бот запущен!\n\n"
        "Перешлите мне сообщения от рекламодателей, и я создам лид.\n\n"
        "Команды:\n"
        "/leads — все лиды\n"
        "/search <запрос> — поиск\n"
        "/stats — статистика"
    )


def format_leads_as_links(leads: list[dict], page: int = 1) -> tuple[str, int]:
    """Format leads as clickable deep links.
    Hot leads shown at the top, then grouped by status.
    Returns (text, total_pages)."""
    
    # Separate hot and regular leads
    hot_leads = [l for l in leads if l.get("is_hot")]
    regular_leads = [l for l in leads if not l.get("is_hot")]
    
    # Group regular leads by status
    by_status = {}
    for lead in regular_leads:
        status = lead.get("status", "new")
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(lead)
    
    lines = ["📋 *Все лиды:*\n"]
    all_leads_ordered = []
    
    # Show hot leads first
    if hot_leads:
        lines.append("\n*🔥 ВАЖНЫЕ*")
        for lead in hot_leads:
            all_leads_ordered.append(lead)
            status_emoji = STATUSES.get(lead.get("status", "new"), "❓")
            brand = lead.get("brand") or "Без бренда"
            if len(brand) > 25:
                brand = brand[:22] + "..."
            link = f"[🔥{status_emoji} #{lead['id']} {brand}](https://t.me/{BOT_USERNAME}?start=lead_{lead['id']})"
            lines.append(link)
    
    # Then show rest by status
    for status in STATUS_ORDER:
        if status in by_status:
            status_emoji = STATUSES.get(status, "❓")
            lines.append(f"\n*{status_emoji} {status.upper()}*")
            
            for lead in by_status[status]:
                all_leads_ordered.append(lead)
                brand = lead.get("brand") or "Без бренда"
                if len(brand) > 25:
                    brand = brand[:22] + "..."
                link = f"[{status_emoji} #{lead['id']} {brand}](https://t.me/{BOT_USERNAME}?start=lead_{lead['id']})"
                lines.append(link)
    
    total_leads = len(all_leads_ordered)
    total_pages = (total_leads + LEADS_PER_PAGE - 1) // LEADS_PER_PAGE
    if total_pages == 0:
        total_pages = 1
    
    # Add pagination info
    if total_pages > 1:
        lines.append(f"\n📄 Страница {page}/{total_pages}")
    
    return "\n".join(lines), total_pages


async def show_leads_page(message: Message, user_id: int, page: int = 1):
    """Show leads list with pagination."""
    leads = await get_leads_by_status(user_id)
    
    if not leads:
        await message.answer("📋 Нет лидов.")
        return
    
    text, total_pages = format_leads_as_links(leads, page)
    
    # Build pagination keyboard if needed
    keyboard = None
    if total_pages > 1:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = []
        if page > 1:
            buttons.append(InlineKeyboardButton(
                text="⬅️ Назад",
                url=f"https://t.me/{BOT_USERNAME}?start=leads_page_{page-1}"
            ))
        if page < total_pages:
            buttons.append(InlineKeyboardButton(
                text="Вперёд ➡️",
                url=f"https://t.me/{BOT_USERNAME}?start=leads_page_{page+1}"
            ))
        if buttons:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)


@router.message(Command("leads"))
async def cmd_leads(message: Message):
    """Handle /leads command."""
    user_id = message.from_user.id
    await show_leads_page(message, user_id, page=1)


@router.message(Command("search"))
async def cmd_search(message: Message):
    """Handle /search command."""
    user_id = message.from_user.id

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /search <запрос>")
        return

    query = parts[1].strip()
    leads = await search_leads(user_id, query)

    if not leads:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
        return

    result = f"🔍 Результаты по «{query}»:\n\n"
    for lead in leads:
        result += format_lead_short(lead) + "\n"

    await message.answer(result)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command."""
    user_id = message.from_user.id
    stats = await get_stats(user_id)
    await message.answer(format_stats(stats))


# === FORWARDED MESSAGES HANDLER ===

@router.message(F.forward_date)
async def handle_forwarded(message: Message):
    """Handle forwarded messages with batching."""
    user_id = message.from_user.id
    sender_key = get_sender_key(message)

    if sender_key == (None, None):
        sender_key = (None, f"unknown_{message.message_id}")

    # Buffer key includes user_id for multi-user support
    buffer_key = f"{user_id}:{sender_key}"
    sender_info = get_sender_info(message)

    msg_data = {
        "text": message.text or message.caption or "[Медиа без текста]",
        "forward_date": message.forward_date.isoformat() if message.forward_date else None
    }

    if buffer_key in message_buffer:
        message_buffer[buffer_key]["messages"].append(msg_data)

        old_task = message_buffer[buffer_key].get("task")
        if old_task and not old_task.done():
            old_task.cancel()
    else:
        message_buffer[buffer_key] = {
            "messages": [msg_data],
            "sender_info": sender_info,
            "chat_id": message.chat.id,
            "user_id": user_id
        }

    task = asyncio.create_task(process_batch(buffer_key, message.chat.id, user_id))
    message_buffer[buffer_key]["task"] = task

    logger.info(f"Buffered message for user {user_id}, total: {len(message_buffer[buffer_key]['messages'])}")


# === CALLBACK HANDLERS ===

@router.callback_query(F.data.startswith("status:"))
async def handle_status_change(callback: CallbackQuery):
    """Handle status button clicks."""
    user_id = callback.from_user.id
    _, lead_id, new_status = callback.data.split(":")
    lead_id = int(lead_id)

    await update_lead_status(lead_id, user_id, new_status)

    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    messages = await get_lead_messages(lead_id)

    await callback.message.edit_text(
        format_lead(lead, len(messages)),
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )
    await callback.answer("Статус изменён")


@router.callback_query(F.data.startswith("toggle_hot:"))
async def handle_toggle_hot(callback: CallbackQuery):
    """Toggle hot/important flag for a lead."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])

    new_value = await toggle_lead_hot(lead_id, user_id)

    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    messages = await get_lead_messages(lead_id)

    await callback.message.edit_text(
        format_lead(lead, len(messages)),
        reply_markup=get_lead_keyboard(lead_id, is_hot=new_value)
    )
    await callback.answer("🔥 Важный!" if new_value else "Снято")


@router.callback_query(F.data.startswith("originals:"))
async def handle_show_originals(callback: CallbackQuery):
    """Show original messages."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])

    # Verify lead belongs to user
    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    messages = await get_lead_messages(lead_id)

    text = format_originals(messages)

    if len(text) > 4000:
        text = text[:4000] + "\n\n... (сообщение обрезано)"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(lead_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back:"))
async def handle_back(callback: CallbackQuery):
    """Return to lead view."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])

    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    messages = await get_lead_messages(lead_id)

    await callback.message.edit_text(
        format_lead(lead, len(messages)),
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_lead:"))
async def handle_view_lead(callback: CallbackQuery):
    """Handle clicking on a lead in the list."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])

    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    messages = await get_lead_messages(lead_id)

    await callback.message.edit_text(
        format_lead(lead, len(messages)),
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:"))
async def handle_edit_menu(callback: CallbackQuery):
    """Show edit menu."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])

    # Verify lead belongs to user
    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    await callback.message.edit_text(
        "✏️ Выберите поле для редактирования:",
        reply_markup=get_edit_keyboard(lead_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def handle_edit_field(callback: CallbackQuery, state: FSMContext):
    """Start editing a specific field."""
    user_id = callback.from_user.id
    _, lead_id, field = callback.data.split(":")
    lead_id = int(lead_id)

    # Verify lead belongs to user
    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    field_info = {
        "brand": ("бренд", "Название компании, например: Magssory"),
        "request": ("запрос", "Кратко что хотят, например: Интеграция в Reels"),
        "contact": ("контакт", "Имя контактного лица"),
        "dates": ("даты", "Любой формат: 12.02.2026, февраль, Q1 и т.д.")
    }
    
    field_name, hint = field_info.get(field, (field, ""))

    await state.set_state(EditStates.waiting_for_value)
    await state.set_data({"lead_id": lead_id, "field": field})

    # Cancel keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_edit:{lead_id}")]
    ])

    await callback.message.edit_text(
        f"✏️ Редактирование: *{field_name}*\n\n"
        f"💡 {hint}\n\n"
        f"Введите новое значение или нажмите Отмена:",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_edit:"))
async def handle_cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Cancel editing and return to lead."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])
    
    await state.clear()
    
    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return
    
    messages = await get_lead_messages(lead_id)
    
    await callback.message.edit_text(
        format_lead(lead, len(messages)),
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )
    await callback.answer("Редактирование отменено")


@router.message(EditStates.waiting_for_value)
async def handle_edit_value(message: Message, state: FSMContext):
    """Process edited value."""
    user_id = message.from_user.id
    new_value = message.text.strip()
    
    # Check for cancel keywords
    cancel_keywords = ["нет", "отмена", "cancel", "-", "/cancel"]
    if new_value.lower() in cancel_keywords:
        data = await state.get_data()
        lead_id = data["lead_id"]
        await state.clear()
        
        lead = await get_lead(lead_id, user_id)
        if lead:
            messages = await get_lead_messages(lead_id)
            await message.answer(
                f"❌ Редактирование отменено.\n\n{format_lead(lead, len(messages))}",
                reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
            )
        else:
            await message.answer("❌ Редактирование отменено.")
        return

    data = await state.get_data()
    lead_id = data["lead_id"]
    field = data["field"]

    field_map = {
        "brand": "brand",
        "request": "request",
        "contact": "contact_name",
        "dates": "dates"
    }

    db_field = field_map.get(field, field)
    await update_lead_field(lead_id, user_id, db_field, new_value)

    await state.clear()

    lead = await get_lead(lead_id, user_id)
    messages = await get_lead_messages(lead_id)

    await message.answer(
        f"✅ Обновлено!\n\n{format_lead(lead, len(messages))}",
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )


@router.callback_query(F.data.startswith("add_to_lead:"))
async def handle_add_to_lead(callback: CallbackQuery):
    """Add pending messages to existing lead."""
    user_id = callback.from_user.id
    lead_id = int(callback.data.split(":")[1])
    chat_id = callback.message.chat.id

    pending_key = (user_id, chat_id)
    if pending_key not in pending_messages:
        await callback.answer("Сообщения не найдены")
        return

    # Verify lead belongs to user
    lead = await get_lead(lead_id, user_id)
    if not lead:
        await callback.answer("Лид не найден")
        return

    pending = pending_messages.pop(pending_key)
    messages = pending["messages"]

    await add_messages_to_lead(lead_id, messages)

    all_text = await get_all_messages_text(lead_id)
    parsed = await parse_messages(all_text)

    await update_lead_parsed_data(
        lead_id,
        parsed.get("brand"),
        parsed.get("request"),
        parsed.get("contact"),
        parsed.get("dates")
    )

    lead = await get_lead(lead_id, user_id)
    all_messages = await get_lead_messages(lead_id)

    await callback.message.edit_text(
        f"📎 Добавлено {len(messages)} сообщений!\n\n{format_lead(lead, len(all_messages))}",
        reply_markup=get_lead_keyboard(lead_id, lead.get("is_hot", False))
    )
    await callback.answer()


@router.callback_query(F.data == "create_new_lead")
async def handle_create_new_lead(callback: CallbackQuery):
    """Create new lead from pending messages."""
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    pending_key = (user_id, chat_id)
    if pending_key not in pending_messages:
        await callback.answer("Сообщения не найдены")
        return

    pending = pending_messages.pop(pending_key)

    await callback.message.delete()
    await create_new_lead_from_messages(chat_id, user_id, pending["messages"], pending["sender_info"])
    await callback.answer()


# === MAIN ===

async def start_bot():
    """Main entry point."""
    logger.info("🤖 Bot starting...")
    await dp.start_polling(bot)
