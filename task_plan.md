# Task Plan: Telegram CRM Bot for Ad Requests

## Goal
Build a Telegram bot that acts as a CRM for managing advertising/collaboration requests with AI-powered parsing, message batching, and status pipeline tracking.

## Current Phase
Phase 6 - COMPLETE

## Phases

### Phase 1: Project Setup & Database Schema
- [x] Create project structure
- [x] Setup requirements.txt with dependencies
- [x] Design SQLite database schema (leads + messages tables)
- [x] Create database module
- **Status:** complete

### Phase 2: Core Bot Infrastructure
- [x] Setup aiogram 3.x bot foundation
- [x] Implement message forwarding detection
- [x] Build 5-second message batching system (debounce)
- [x] Create message buffer with grouping by forwarded sender
- **Status:** complete

### Phase 3: AI Parsing Integration
- [x] Setup OpenAI client
- [x] Create prompt for extracting: brand, request, contact, dates
- [x] Implement batch parsing (all messages → one AI call)
- [x] Handle parsing errors gracefully
- **Status:** complete

### Phase 4: Lead Management & UI
- [x] Create lead with parsed data + raw messages
- [x] Build inline keyboard for status changes
- [x] Implement "Show Originals" button
- [x] Handle adding messages to existing lead (30-min window)
- **Status:** complete

### Phase 5: Commands & Features
- [x] /leads command - grouped by status
- [x] /search command - find by name/brand
- [x] /stats command - conversion stats
- [x] Edit lead functionality
- **Status:** complete

### Phase 6: Testing & Deployment
- [x] Test message batching (4 messages = 1 response)
- [x] Test AI parsing accuracy
- [x] Test status pipeline
- [x] Write deployment instructions
- [x] Create systemd service file
- **Status:** complete

## Key Questions
1. How to identify forwarded sender for grouping? → Use forward_from.id or forward_sender_name
2. How to handle multiple rapid forwards? → 5-sec debounce timer per sender
3. How to detect "same contact" for 30-min window? → Match by telegram_id or sender_name

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Python + aiogram 3.x | User requirement, async support |
| SQLite + aiosqlite | Simple, no external DB needed |
| GPT-4o-mini | Cost-effective for parsing |
| 5-sec debounce | Balance between batching and responsiveness |
| Forward sender grouping | Natural way to batch related messages |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- Bot messages in Russian
- OWNER_ID=55174158 - only owner can use bot
- MVP scope: batching, parsing, storage, status buttons, /leads
- Phase 2 (later): contracts, reminders, stats
