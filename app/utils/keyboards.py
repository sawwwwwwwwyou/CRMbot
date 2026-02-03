"""Inline keyboards for the bot."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import STATUSES


def get_lead_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """Create keyboard with status buttons and actions."""
    status_buttons = [
        InlineKeyboardButton(
            text=emoji,
            callback_data=f"status:{lead_id}:{status}"
        )
        for status, emoji in STATUSES.items()
    ]

    # Split into two rows (4 + 3)
    status_row1 = status_buttons[:4]
    status_row2 = status_buttons[4:]

    action_buttons = [
        InlineKeyboardButton(text="📜 Оригиналы", callback_data=f"originals:{lead_id}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{lead_id}")
    ]

    return InlineKeyboardMarkup(inline_keyboard=[
        status_row1,
        status_row2,
        action_buttons
    ])


def get_add_to_lead_keyboard(existing_lead_id: int, brand: str) -> InlineKeyboardMarkup:
    """Keyboard for adding messages to existing lead."""
    brand_short = brand[:20] if brand else "лид"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"📎 Добавить к «{brand_short}»",
                callback_data=f"add_to_lead:{existing_lead_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🆕 Создать новый лид",
                callback_data="create_new_lead"
            )
        ]
    ])


def get_back_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """Simple back button to return to lead."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back:{lead_id}")]
    ])


def get_edit_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """Keyboard for editing lead fields."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏢 Бренд", callback_data=f"edit_field:{lead_id}:brand"),
            InlineKeyboardButton(text="📝 Запрос", callback_data=f"edit_field:{lead_id}:request")
        ],
        [
            InlineKeyboardButton(text="👤 Контакт", callback_data=f"edit_field:{lead_id}:contact"),
            InlineKeyboardButton(text="📅 Даты", callback_data=f"edit_field:{lead_id}:dates")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back:{lead_id}")]
    ])


def get_leads_list_keyboard(leads: list[dict]) -> InlineKeyboardMarkup:
    """Create keyboard with clickable leads."""
    from app.config import STATUSES
    
    buttons = []
    for lead in leads[:20]:  # Limit to 20 leads
        status_emoji = STATUSES.get(lead.get("status", "new"), "🆕")
        brand = lead.get("brand") or "Без бренда"
        # Truncate brand name if too long
        if len(brand) > 25:
            brand = brand[:22] + "..."
        
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} #{lead['id']} {brand}",
                callback_data=f"view_lead:{lead['id']}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
