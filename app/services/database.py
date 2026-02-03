"""Database operations using Supabase with multi-user support."""
from datetime import datetime, timedelta
from typing import Optional
from app.services.supabase import supabase


async def create_lead(
    user_id: int,
    contact_telegram_id: Optional[int],
    contact_name: Optional[str],
    contact_username: Optional[str],
    brand: Optional[str],
    request: Optional[str],
    dates: Optional[str],
    raw_messages: list[dict]
) -> int:
    """Create a new lead with messages."""
    lead_data = {
        "user_id": user_id,
        "contact_telegram_id": contact_telegram_id,
        "contact_name": contact_name,
        "contact_username": contact_username,
        "brand": brand,
        "request": request,
        "dates": dates,
        "status": "new"
    }

    result = supabase.table("leads").insert(lead_data).execute()
    lead_id = result.data[0]["id"]

    if raw_messages:
        messages_data = [
            {
                "lead_id": lead_id,
                "raw_text": msg["text"],
                "forward_date": msg.get("forward_date")
            }
            for msg in raw_messages
        ]
        supabase.table("lead_messages").insert(messages_data).execute()

    return lead_id


async def add_messages_to_lead(lead_id: int, raw_messages: list[dict]):
    """Add messages to existing lead and update timestamp."""
    if raw_messages:
        messages_data = [
            {
                "lead_id": lead_id,
                "raw_text": msg["text"],
                "forward_date": msg.get("forward_date")
            }
            for msg in raw_messages
        ]
        supabase.table("lead_messages").insert(messages_data).execute()

    supabase.table("leads").update({
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", lead_id).execute()


async def update_lead_parsed_data(
    lead_id: int,
    brand: Optional[str],
    request: Optional[str],
    contact_name: Optional[str],
    dates: Optional[str]
):
    """Update lead with re-parsed data."""
    update_data = {
        "brand": brand,
        "request": request,
        "dates": dates,
        "updated_at": datetime.utcnow().isoformat()
    }

    if contact_name:
        update_data["contact_name"] = contact_name

    supabase.table("leads").update(update_data).eq("id", lead_id).execute()


async def get_lead(lead_id: int, user_id: int) -> Optional[dict]:
    """Get lead by ID (only if belongs to user)."""
    result = supabase.table("leads")\
        .select("*")\
        .eq("id", lead_id)\
        .eq("user_id", user_id)\
        .execute()
    return result.data[0] if result.data else None


async def get_lead_messages(lead_id: int) -> list[dict]:
    """Get all messages for a lead."""
    result = supabase.table("lead_messages")\
        .select("*")\
        .eq("lead_id", lead_id)\
        .order("created_at")\
        .execute()
    return result.data


async def update_lead_status(lead_id: int, user_id: int, status: str):
    """Update lead status (only if belongs to user)."""
    supabase.table("leads").update({
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", lead_id).eq("user_id", user_id).execute()


async def toggle_lead_hot(lead_id: int, user_id: int) -> bool:
    """Toggle is_hot flag for a lead. Returns new value."""
    # Get current value
    result = supabase.table("leads")\
        .select("is_hot")\
        .eq("id", lead_id)\
        .eq("user_id", user_id)\
        .single()\
        .execute()
    
    current = result.data.get("is_hot", False) if result.data else False
    new_value = not current
    
    supabase.table("leads").update({
        "is_hot": new_value,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", lead_id).eq("user_id", user_id).execute()
    
    return new_value


async def update_lead_field(lead_id: int, user_id: int, field: str, value: str):
    """Update a specific lead field (only if belongs to user)."""
    supabase.table("leads").update({
        field: value,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", lead_id).eq("user_id", user_id).execute()


async def get_leads_by_status(user_id: int, status: Optional[str] = None) -> list[dict]:
    """Get user's leads, optionally filtered by status."""
    query = supabase.table("leads").select("*").eq("user_id", user_id)

    if status:
        query = query.eq("status", status)

    result = query.order("updated_at", desc=True).execute()
    return result.data


async def search_leads(user_id: int, query: str) -> list[dict]:
    """Search user's leads by brand or contact name."""
    search_pattern = f"%{query}%"

    result = supabase.table("leads")\
        .select("*")\
        .eq("user_id", user_id)\
        .or_(f"brand.ilike.{search_pattern},contact_name.ilike.{search_pattern},contact_username.ilike.{search_pattern}")\
        .order("updated_at", desc=True)\
        .execute()

    return result.data


async def get_recent_lead_by_contact(
    user_id: int,
    contact_telegram_id: Optional[int],
    contact_name: Optional[str],
    minutes: int = 30
) -> Optional[dict]:
    """Find recent lead from same contact within time window (for this user)."""
    cutoff_time = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()

    if contact_telegram_id:
        result = supabase.table("leads")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("contact_telegram_id", contact_telegram_id)\
            .gte("updated_at", cutoff_time)\
            .order("updated_at", desc=True)\
            .limit(1)\
            .execute()
    elif contact_name:
        result = supabase.table("leads")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("contact_name", contact_name)\
            .gte("updated_at", cutoff_time)\
            .order("updated_at", desc=True)\
            .limit(1)\
            .execute()
    else:
        return None

    return result.data[0] if result.data else None


async def get_stats(user_id: int) -> dict:
    """Get conversion statistics for user."""
    leads_result = supabase.table("leads")\
        .select("status")\
        .eq("user_id", user_id)\
        .execute()

    status_counts = {}
    for lead in leads_result.data:
        status = lead["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    total_leads = len(leads_result.data)

    # Get message count for user's leads
    leads_ids = supabase.table("leads")\
        .select("id")\
        .eq("user_id", user_id)\
        .execute()

    total_messages = 0
    if leads_ids.data:
        lead_ids_list = [l["id"] for l in leads_ids.data]
        for lid in lead_ids_list:
            msg_result = supabase.table("lead_messages")\
                .select("id", count="exact")\
                .eq("lead_id", lid)\
                .execute()
            total_messages += msg_result.count or 0

    return {
        "total_leads": total_leads,
        "total_messages": total_messages,
        "by_status": status_counts
    }


async def get_all_messages_text(lead_id: int) -> str:
    """Get all messages combined as text for re-parsing."""
    messages = await get_lead_messages(lead_id)
    return "\n\n---\n\n".join([m["raw_text"] for m in messages])
