"""Bot configuration."""
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Batching settings
BATCH_TIMEOUT_SECONDS = 1.0  # Wait 1 second for more messages
SAME_LEAD_WINDOW_MINUTES = 30  # Window to add to existing lead

# Bot username (without @) for deep links
BOT_USERNAME = os.getenv("BOT_USERNAME", "savefornow_bot")

# Status definitions
STATUSES = {
    "new": "🆕",
    "replied": "📤",
    "waiting": "⏳",
    "negotiating": "🤝",
    "signing": "📝",
    "contract": "✅",
    "lost": "❌",
}

STATUS_NAMES = {
    "new": "New",
    "replied": "Replied",
    "waiting": "Waiting",
    "negotiating": "Negotiating",
    "signing": "Signing",
    "contract": "Contract",
    "lost": "Lost",
}

# Order for displaying leads (top to bottom)
STATUS_ORDER = ["contract", "signing", "negotiating", "waiting", "replied", "new", "lost"]

# Pagination
LEADS_PER_PAGE = 15
