"""Message formatters for the bot."""
from app.config import STATUSES, STATUS_NAMES


def format_lead(lead: dict, message_count: int = 0) -> str:
    """Format lead info for display."""
    status = lead.get("status", "new")
    status_emoji = STATUSES.get(status, "🆕")
    status_name = STATUS_NAMES.get(status, "New")
    is_hot = lead.get("is_hot", False)

    brand = lead.get("brand") or "—"
    request = lead.get("request") or "—"
    contact = lead.get("contact_name") or "—"
    dates = lead.get("dates") or "—"
    
    hot_badge = "🔥 " if is_hot else ""

    return f"""{hot_badge}📥 Лид #{lead['id']}

🏢 Бренд: {brand}
📝 Запрос: {request}
👤 Контакт: {contact}
📅 Даты: {dates}
📨 Сообщений: {message_count}

📊 Статус: {status_emoji} {status_name}"""


def format_new_lead(lead: dict, message_count: int) -> str:
    """Format new lead announcement."""
    status = lead.get("status", "new")
    status_emoji = STATUSES.get(status, "🆕")
    status_name = STATUS_NAMES.get(status, "New")

    brand = lead.get("brand") or "—"
    request = lead.get("request") or "—"
    contact = lead.get("contact_name") or "—"
    dates = lead.get("dates") or "—"

    return f"""📥 Новый лид!

🏢 Бренд: {brand}
📝 Запрос: {request}
👤 Контакт: {contact}
📅 Даты: {dates}
📨 Сообщений: {message_count}

📊 Статус: {status_emoji} {status_name}"""


def format_lead_short(lead: dict) -> str:
    """Format lead for list view."""
    status_emoji = STATUSES.get(lead.get("status", "new"), "🆕")
    brand = lead.get("brand") or "Без бренда"
    contact = lead.get("contact_name") or ""

    text = f"{status_emoji} #{lead['id']} {brand}"
    if contact:
        text += f" ({contact})"
    return text


def format_originals(messages: list[dict]) -> str:
    """Format original messages for display."""
    if not messages:
        return "Нет сохранённых сообщений."

    result = "📜 Оригинальные сообщения:\n\n"

    for i, msg in enumerate(messages, 1):
        date_str = ""
        if msg.get("forward_date"):
            date_str = f" | {msg['forward_date']}"

        result += f"— Сообщение {i}{date_str} —\n"
        result += msg.get("raw_text", "") + "\n\n"

    return result.strip()


def format_stats(stats: dict) -> str:
    """Format statistics for display."""
    result = "📊 Статистика CRM\n\n"
    result += f"📥 Всего лидов: {stats['total_leads']}\n"
    result += f"📨 Всего сообщений: {stats['total_messages']}\n\n"

    result += "По статусам:\n"
    for status, emoji in STATUSES.items():
        count = stats['by_status'].get(status, 0)
        name = STATUS_NAMES.get(status, status)
        result += f"{emoji} {name}: {count}\n"

    total = stats['total_leads']
    contracts = stats['by_status'].get('contract', 0)
    if total > 0:
        rate = (contracts / total) * 100
        result += f"\n✅ Конверсия в контракт: {rate:.1f}%"

    return result


def format_leads_by_status(leads: list[dict]) -> str:
    """Format leads grouped by status."""
    if not leads:
        return "Нет лидов."

    grouped = {}
    for lead in leads:
        status = lead.get("status", "new")
        if status not in grouped:
            grouped[status] = []
        grouped[status].append(lead)

    result = "📋 Все лиды:\n"

    for status, emoji in STATUSES.items():
        if status in grouped:
            status_leads = grouped[status]
            name = STATUS_NAMES.get(status, status)
            result += f"\n{emoji} {name} ({len(status_leads)}):\n"

            for lead in status_leads:
                brand = lead.get("brand") or "Без бренда"
                result += f"  • #{lead['id']} {brand}\n"

    return result.strip()
