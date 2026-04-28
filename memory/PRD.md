# Mindful Companion — PRD

## Original Problem Statement
Build an AI Mental Wellness Agent that supports users emotionally through intelligent conversations, voice interaction, empathetic responses, and actionable guidance. Must feel safe, human-centered, emotionally intelligent and useful while remaining ethical and balanced.

## Architecture
- **Backend:** FastAPI + MongoDB (Motor async). All routes under `/api`. JWT cookie auth (httpOnly, samesite=none).
- **Frontend:** React 19 + react-router-dom + Tailwind + shadcn/ui + Phosphor icons + Framer Motion + Recharts.
- **AI:** OpenAI gpt-5-mini (chat), Whisper (STT), OpenAI TTS (mp3 base64) — all via `emergentintegrations` library + Emergent Universal LLM Key.
- **Auth:** JWT email/password with bcrypt, httpOnly cookies, admin seeding on startup.

## User Personas
- Adult user under stress / burnout (Professional mode).
- Gen Z user dealing with loneliness, identity, breakups (Gen Z mode).
- Late-night overthinkers (Sleep Companion mode).
- Therapy-engaged users wanting between-session reflections.

## Core Requirements (static)
- Empathy-first conversational AI with emotion + crisis detection.
- Voice input (push-to-talk) and voice output (TTS reply).
- Two conversation modes (Professional / Gen Z).
- Mood tracking, journaling, habits, breathing, daily check-ins, sleep mode, therapist bridge.
- Privacy: per-user scoped data; no cross-user leakage.
- Safety: crisis resources surfaced immediately, never claims to replace therapy.

## Implemented (2026-04-28)
- ✅ JWT auth (register/login/logout/me/refresh) with httpOnly cookies + brute-force-ready
- ✅ Real LLM chat with `gpt-5-mini`, session memory per conversation, Pro/Gen Z modes
- ✅ Voice chat: Whisper transcription + OpenAI TTS reply (base64 mp3)
- ✅ Crisis keyword detection + resources (US/UK/IN/AU + IASP)
- ✅ Emotion detection (sadness, anxiety, anger, isolation, shame, burnout, low_motivation, relationship_pain)
- ✅ Mood logging (score/energy/sleep/triggers/note) + 30-log Recharts trend
- ✅ Journal with mode-aware prompts, mood tags, list/delete
- ✅ Habits with consecutive-day streak calculation, weekly target
- ✅ Breathing techniques: box, 4-7-8, simple — animated Framer Motion circle
- ✅ Daily check-in (idempotent same-day upsert)
- ✅ Sleep Companion mode (dark UI with starscape, gentle voice, quick prompts)
- ✅ Therapist Bridge summary (avg mood/sleep, top triggers, recurring emotions, reflection topics, copy-to-clipboard)
- ✅ Mode toggle (Pro / Gen Z) persisted on user
- ✅ Earthy organic design system (sage/sand/terracotta), Outfit + DM Sans, Phosphor duotone icons
- ✅ 50/50 backend tests passing

## Iteration 2 (2026-04-28)
- ✅ **Humanized AI prompts** — rewrote PROFESSIONAL_SYSTEM and GENZ_SYSTEM to actively forbid robotic openers ("I'm sorry to hear", "It sounds like you're feeling"), enforce real-friend tone, length-matched replies, contractions, follow-up curiosity over advice lists.
- ✅ **Chat history sidebar** with auto-titled sessions (from first user message), search (regex-escaped), rename (PATCH /api/chat/sessions/:id), delete (consistent 404 on non-owned).
- ✅ **New conversation button** — always available, resets context cleanly.
- ✅ **Redesigned Talk tab** — full-height viewport, sticky composer, larger message bubbles (15px / 1.65 line-height), auto-growing textarea, animated typing indicator, mobile drawer for sidebar.
- ✅ **Telegram bot VentBuddy** (@VentBuddyBot) — long-polling integration with python-telegram-bot 22.7. Commands: /start, /new, /mode pro|genz, /voice on|off, /checkin, /help. Supports text + voice notes (Whisper STT) with optional TTS voice replies (Opus). Each Telegram user gets a linked Mindful user record (`tg_<id>@telegram.local`) with persistent session state.
- ✅ **Multi-channel sessions** — sessions tagged with `channel` field (web | telegram); UI shows 📱 prefix for Telegram-originated chats.
- ✅ **GET /api/integrations/telegram** returns bot username for web → Telegram deep link.
- ✅ Dashboard "Available on Telegram" callout with Open in Telegram CTA.
- ✅ 59/59 backend tests passing (50 regression + 9 new).

## Backlog (P0/P1/P2)
### P1
- ElevenLabs voice option for richer TTS character
- Streaming chat responses (token-by-token) for snappier UX
- Per-mode voice presets (echo for sleep, shimmer for day)
- Mobile-only push notifications for daily check-ins

### P2
- Therapist sharing (email or link with redacted summary)
- Anonymous moderated community spaces
- Couples / Group mode
- Habit reminders with timezone-aware scheduling
- Multi-language support (Whisper supports many; UI strings need i18n)

## Test Credentials
- Admin: `admin@mindful.app` / `Admin@123`
- Test user: `test@mindful.app` / `Test@123` (created during testing)

## Known limitations
- Crisis detection is keyword-based (best-effort safety net, not primary safeguard).
- CORS currently `*` for dev; tighten to FRONTEND_URL for production.
- No login rate limiting yet (P1).
