# Findings & Decisions

## Requirements
- Forward messages to bot → parse with AI
- Extract: brand, request (short), contact name, dates
- Save to database: parsed data AND raw messages
- Status pipeline: new → replied → negotiating → contract → lost
- Message batching: 4 forwarded messages = 1 bot response, 1 AI call
- 5-second debounce for collecting messages
- Group messages by forwarded sender
- Add to existing lead within 30-min window
- "Show Originals" button for raw messages
- Russian language for bot messages

## Technical Stack
- Python 3.11+
- aiogram 3.x (NOT python-telegram-bot!)
- **Supabase** (PostgreSQL) — облачная БД
- OpenAI API (GPT-4o-mini)

## Database Schema Design (Supabase PostgreSQL)

### Table: leads
| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT IDENTITY | Auto-increment (Supabase best practice) |
| contact_telegram_id | BIGINT | From forward_from if available |
| contact_name | TEXT | AI extracted or from forward |
| contact_username | TEXT | @username if available |
| brand | TEXT | AI extracted |
| request | TEXT | AI extracted (short description) |
| dates | TEXT | AI extracted dates/deadlines |
| status | TEXT | new/replied/waiting/negotiating/signing/contract/lost |
| created_at | TIMESTAMPTZ | When lead was created |
| updated_at | TIMESTAMPTZ | Last status change |

### Table: lead_messages
| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT IDENTITY | Auto-increment |
| lead_id | BIGINT | FK to leads (indexed!) |
| raw_text | TEXT | Original message text |
| forward_date | TIMESTAMPTZ | When message was originally sent |
| created_at | TIMESTAMPTZ | When saved to DB |

### Indexes (Supabase best practices)
- `leads_status_idx` on leads(status)
- `leads_contact_telegram_id_idx` on leads(contact_telegram_id)
- `leads_updated_at_idx` on leads(updated_at desc)
- `lead_messages_lead_id_idx` on lead_messages(lead_id) — FK index!

## Status Pipeline
| Emoji | Status | Meaning |
|-------|--------|---------|
| 🆕 | new | Just received |
| 📤 | replied | Waiting for their response |
| ⏳ | waiting | They're deciding |
| 🤝 | negotiating | Discussing terms |
| 📝 | signing | Contract stage |
| ✅ | contract | Active client |
| ❌ | lost | Rejected/gone |

## Message Batching Logic
1. User forwards message → detect via forward_from or forward_sender_name
2. Get sender identifier (telegram_id or sender_name)
3. Add message to buffer[sender_id]
4. Reset/start 5-second timer for that sender
5. On timer expiry → batch all messages → one AI call → one response
6. Clear buffer for that sender

## AI Prompt Design
System: Parse advertising collaboration request. Extract:
- brand: Company/brand name
- request: What they want (1 sentence)
- contact: Contact person name
- dates: Any mentioned dates/deadlines

Return JSON only: {"brand": "", "request": "", "contact": "", "dates": ""}
If not found, use null.

## Bot Response Format
```
📥 Новый лид!

🏢 Бренд: {brand}
📝 Запрос: {request}
👤 Контакт: {contact}
📅 Даты: {dates or "—"}
📨 Сообщений: {count}

📊 Статус: 🆕 New

[🆕] [📤] [⏳] [🤝] [📝] [❌]
[📜 Оригиналы] [✏️ Редактировать]
```

## Environment Variables
- BOT_TOKEN - from BotFather
- OPENAI_API_KEY - from OpenAI
- OWNER_ID=55174158 - authorized user
- SUPABASE_URL - from Supabase Settings → API
- SUPABASE_KEY - anon public key from Supabase

## Resources
- aiogram 3.x docs: https://docs.aiogram.dev/
- OpenAI API: https://platform.openai.com/docs
- Telegram Bot API: https://core.telegram.org/bots/api
- Supabase: https://supabase.com/docs

## Issues Encountered
| Issue | Resolution |
|-------|------------|
|       |            |

---
*Update this file after every 2 view/browser/search operations*
