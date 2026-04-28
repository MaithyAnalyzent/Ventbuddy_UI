"""Mindful Companion - AI Mental Wellness Agent backend."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, date
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    set_auth_cookies, clear_auth_cookies,
    get_current_user as _get_current_user,
    seed_admin, decode_token,
)
from ai_service import (
    detect_crisis, detect_emotion,
    get_system_message, generate_chat_response,
    transcribe_audio, synthesize_speech,
    get_journal_prompts, get_crisis_resources,
    auto_title,
)
from telegram_bot import build_application as build_tg_app


# ---- DB ----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]

app = FastAPI(title="Mindful Companion API")
api = APIRouter(prefix="/api")


# ---- Helpers ----
def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def current_user(request: Request) -> dict:
    return await _get_current_user(request, db)


# ---- Models ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str = "user"
    mode: str = "professional"
    voice: str = "shimmer"


class ChatIn(BaseModel):
    text: str
    mode: Literal["professional", "genz"] = "professional"
    session_id: Optional[str] = None
    voice_reply: bool = False


class ModeUpdateIn(BaseModel):
    mode: Literal["professional", "genz"]


class VoiceUpdateIn(BaseModel):
    voice: str


class MoodIn(BaseModel):
    score: int = Field(ge=1, le=10)
    energy: int = Field(ge=1, le=10)
    sleep_quality: int = Field(ge=1, le=10)
    triggers: List[str] = []
    note: Optional[str] = ""


class JournalIn(BaseModel):
    prompt: Optional[str] = ""
    content: str = Field(min_length=1)
    mood_tag: Optional[str] = ""


class HabitIn(BaseModel):
    name: str
    icon: str = "leaf"
    target_per_week: int = 7


class HabitLogIn(BaseModel):
    habit_id: str
    completed: bool = True


class BreathingIn(BaseModel):
    technique: str = "box"
    duration_seconds: int


class CheckinRespondIn(BaseModel):
    feeling: str
    note: Optional[str] = ""


# ---- Auth Endpoints ----
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "role": "user",
        "mode": "professional",
        "voice": "shimmer",
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return user_doc


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = create_access_token(user["id"], email)
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return user


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"ok": True}


# ---- User Settings ----
@api.patch("/user/mode")
async def update_mode(payload: ModeUpdateIn, user: dict = Depends(current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"mode": payload.mode}})
    return {"mode": payload.mode}


@api.patch("/user/voice")
async def update_voice(payload: VoiceUpdateIn, user: dict = Depends(current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"voice": payload.voice}})
    return {"voice": payload.voice}


# ---- Chat ----
@api.post("/chat/send")
async def chat_send(payload: ChatIn, user: dict = Depends(current_user)):
    session_id = payload.session_id or str(uuid.uuid4())
    is_crisis = detect_crisis(payload.text)
    emotion = detect_emotion(payload.text)
    system_msg = get_system_message(payload.mode, emotion, is_crisis)

    # Save user message
    user_msg_id = str(uuid.uuid4())
    await db.messages.insert_one({
        "id": user_msg_id,
        "user_id": user["id"],
        "session_id": session_id,
        "role": "user",
        "content": payload.text,
        "emotion": emotion,
        "is_crisis": is_crisis,
        "mode": payload.mode,
        "created_at": now_iso(),
    })

    # Generate AI reply
    try:
        # Use scoped session for memory continuity per session_id+user
        scoped_id = f"{user['id']}_{session_id}_{payload.mode}"
        reply = await generate_chat_response(EMERGENT_KEY, scoped_id, system_msg, payload.text)
    except Exception as e:
        logging.exception("LLM error")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    ai_msg_id = str(uuid.uuid4())
    await db.messages.insert_one({
        "id": ai_msg_id,
        "user_id": user["id"],
        "session_id": session_id,
        "role": "assistant",
        "content": reply,
        "emotion": emotion,
        "is_crisis": is_crisis,
        "mode": payload.mode,
        "created_at": now_iso(),
    })

    # Upsert session metadata; set title from first user message
    existing_session = await db.sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0, "title": 1})
    set_fields = {
        "id": session_id, "user_id": user["id"], "mode": payload.mode,
        "last_message": reply[:160], "last_emotion": emotion,
        "updated_at": now_iso(), "channel": "web",
    }
    set_on_insert = {"created_at": now_iso(), "title": auto_title(payload.text)}
    if existing_session and not existing_session.get("title"):
        set_fields["title"] = auto_title(payload.text)
    await db.sessions.update_one(
        {"id": session_id, "user_id": user["id"]},
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )

    audio_b64 = None
    if payload.voice_reply:
        try:
            audio_b64 = await synthesize_speech(EMERGENT_KEY, reply, voice=user.get("voice", "shimmer"))
        except Exception:
            logging.exception("TTS failed")

    return {
        "session_id": session_id,
        "reply": reply,
        "emotion": emotion,
        "is_crisis": is_crisis,
        "crisis_resources": get_crisis_resources() if is_crisis else None,
        "audio_b64": audio_b64,
    }


@api.post("/chat/voice")
async def chat_voice(
    audio: UploadFile = File(...),
    mode: str = Form("professional"),
    session_id: Optional[str] = Form(None),
    voice_reply: bool = Form(True),
    user: dict = Depends(current_user),
):
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio")
    try:
        text = await transcribe_audio(EMERGENT_KEY, audio_bytes, audio.filename or "audio.webm")
    except Exception as e:
        logging.exception("STT failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Could not understand audio")

    sid = session_id or str(uuid.uuid4())
    is_crisis = detect_crisis(text)
    emotion = detect_emotion(text)
    system_msg = get_system_message(mode, emotion, is_crisis)

    await db.messages.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "session_id": sid,
        "role": "user", "content": text, "emotion": emotion, "is_crisis": is_crisis,
        "mode": mode, "created_at": now_iso(),
    })

    scoped_id = f"{user['id']}_{sid}_{mode}"
    reply = await generate_chat_response(EMERGENT_KEY, scoped_id, system_msg, text)

    await db.messages.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "session_id": sid,
        "role": "assistant", "content": reply, "emotion": emotion, "is_crisis": is_crisis,
        "mode": mode, "created_at": now_iso(),
    })

    existing_session = await db.sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0, "title": 1})
    set_fields = {
        "id": sid, "user_id": user["id"], "mode": mode,
        "last_message": reply[:160], "last_emotion": emotion,
        "updated_at": now_iso(), "channel": "web",
    }
    set_on_insert = {"created_at": now_iso(), "title": auto_title(text)}
    if existing_session and not existing_session.get("title"):
        set_fields["title"] = auto_title(text)
    await db.sessions.update_one(
        {"id": sid, "user_id": user["id"]},
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )

    audio_b64 = None
    if voice_reply:
        try:
            audio_b64 = await synthesize_speech(EMERGENT_KEY, reply, voice=user.get("voice", "shimmer"))
        except Exception:
            logging.exception("TTS failed")

    return {
        "session_id": sid,
        "transcript": text,
        "reply": reply,
        "emotion": emotion,
        "is_crisis": is_crisis,
        "crisis_resources": get_crisis_resources() if is_crisis else None,
        "audio_b64": audio_b64,
    }


@api.get("/chat/sessions")
async def list_sessions(user: dict = Depends(current_user), q: Optional[str] = None):
    query = {"user_id": user["id"]}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"last_message": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.sessions.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return docs


@api.patch("/chat/sessions/{session_id}")
async def rename_session(session_id: str, payload: dict, user: dict = Depends(current_user)):
    title = (payload.get("title") or "").strip()[:120]
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    res = await db.sessions.update_one(
        {"id": session_id, "user_id": user["id"]},
        {"$set": {"title": title, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "title": title}


@api.get("/chat/sessions/{session_id}/messages")
async def get_messages(session_id: str, user: dict = Depends(current_user)):
    docs = await db.messages.find(
        {"user_id": user["id"], "session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    return docs


@api.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(current_user)):
    await db.messages.delete_many({"user_id": user["id"], "session_id": session_id})
    await db.sessions.delete_one({"id": session_id, "user_id": user["id"]})
    return {"ok": True}


# ---- Mood ----
@api.post("/mood")
async def log_mood(payload: MoodIn, user: dict = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "score": payload.score,
        "energy": payload.energy,
        "sleep_quality": payload.sleep_quality,
        "triggers": payload.triggers,
        "note": payload.note or "",
        "created_at": now_iso(),
    }
    await db.moods.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/mood")
async def list_moods(user: dict = Depends(current_user)):
    docs = await db.moods.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(60)
    return docs


@api.get("/mood/trends")
async def mood_trends(user: dict = Depends(current_user)):
    docs = await db.moods.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(30)
    docs.reverse()
    if not docs:
        return {"items": [], "avg_score": 0, "avg_energy": 0, "avg_sleep": 0}
    avg_score = sum(d["score"] for d in docs) / len(docs)
    avg_energy = sum(d["energy"] for d in docs) / len(docs)
    avg_sleep = sum(d["sleep_quality"] for d in docs) / len(docs)
    return {
        "items": docs,
        "avg_score": round(avg_score, 1),
        "avg_energy": round(avg_energy, 1),
        "avg_sleep": round(avg_sleep, 1),
    }


# ---- Journal ----
@api.get("/journal/prompts")
async def journal_prompts(user: dict = Depends(current_user)):
    return {"prompts": get_journal_prompts(user.get("mode", "professional"))}


@api.post("/journal")
async def create_journal(payload: JournalIn, user: dict = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "prompt": payload.prompt or "",
        "content": payload.content,
        "mood_tag": payload.mood_tag or "",
        "created_at": now_iso(),
    }
    await db.journals.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/journal")
async def list_journals(user: dict = Depends(current_user)):
    docs = await db.journals.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return docs


@api.delete("/journal/{entry_id}")
async def delete_journal(entry_id: str, user: dict = Depends(current_user)):
    await db.journals.delete_one({"id": entry_id, "user_id": user["id"]})
    return {"ok": True}


# ---- Habits ----
@api.post("/habits")
async def create_habit(payload: HabitIn, user: dict = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": payload.name,
        "icon": payload.icon,
        "target_per_week": payload.target_per_week,
        "created_at": now_iso(),
    }
    await db.habits.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/habits")
async def list_habits(user: dict = Depends(current_user)):
    docs = await db.habits.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    # Attach today's log status for each
    today = date.today().isoformat()
    for h in docs:
        log = await db.habit_logs.find_one(
            {"habit_id": h["id"], "user_id": user["id"], "log_date": today},
            {"_id": 0},
        )
        h["completed_today"] = bool(log and log.get("completed"))
        # Consecutive-day streak (walking back from today/yesterday)
        logs = await db.habit_logs.find(
            {"habit_id": h["id"], "user_id": user["id"], "completed": True},
            {"_id": 0, "log_date": 1},
        ).sort("log_date", -1).to_list(365)
        completed_dates = {l["log_date"] for l in logs}
        from datetime import timedelta
        streak = 0
        cursor = date.today()
        # Allow streak to start at today OR yesterday (so it doesn't reset before user logs today)
        if cursor.isoformat() not in completed_dates:
            cursor = cursor - timedelta(days=1)
        while cursor.isoformat() in completed_dates:
            streak += 1
            cursor = cursor - timedelta(days=1)
        h["streak"] = streak
    return docs


@api.post("/habits/log")
async def log_habit(payload: HabitLogIn, user: dict = Depends(current_user)):
    today = date.today().isoformat()
    await db.habit_logs.update_one(
        {"habit_id": payload.habit_id, "user_id": user["id"], "log_date": today},
        {"$set": {
            "habit_id": payload.habit_id, "user_id": user["id"],
            "log_date": today, "completed": payload.completed,
            "logged_at": now_iso(),
        }},
        upsert=True,
    )
    return {"ok": True, "completed": payload.completed}


@api.delete("/habits/{habit_id}")
async def delete_habit(habit_id: str, user: dict = Depends(current_user)):
    await db.habits.delete_one({"id": habit_id, "user_id": user["id"]})
    await db.habit_logs.delete_many({"habit_id": habit_id, "user_id": user["id"]})
    return {"ok": True}


# ---- Breathing ----
@api.post("/breathing/sessions")
async def log_breathing(payload: BreathingIn, user: dict = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "technique": payload.technique,
        "duration_seconds": payload.duration_seconds,
        "created_at": now_iso(),
    }
    await db.breathing.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/breathing/sessions")
async def list_breathing(user: dict = Depends(current_user)):
    docs = await db.breathing.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return docs


# ---- Daily Check-in ----
@api.get("/checkin/today")
async def checkin_today(user: dict = Depends(current_user)):
    today = date.today().isoformat()
    doc = await db.checkins.find_one(
        {"user_id": user["id"], "log_date": today}, {"_id": 0}
    )
    prompts_pro = [
        "How are you feeling today?",
        "What feels heavy right now?",
        "Name one win from today.",
        "What do you need most this evening?",
    ]
    prompts_genz = [
        "Real check — how are you actually doing?",
        "What's been on your mind today?",
        "One small win from today?",
        "What do you need rn?",
    ]
    prompts = prompts_genz if user.get("mode") == "genz" else prompts_pro
    return {"completed": bool(doc), "checkin": doc, "prompts": prompts}


@api.post("/checkin/respond")
async def checkin_respond(payload: CheckinRespondIn, user: dict = Depends(current_user)):
    today = date.today().isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "log_date": today,
        "feeling": payload.feeling,
        "note": payload.note or "",
        "created_at": now_iso(),
    }
    await db.checkins.update_one(
        {"user_id": user["id"], "log_date": today},
        {"$set": doc}, upsert=True,
    )
    doc.pop("_id", None)
    return doc


# ---- Therapist Bridge ----
@api.get("/therapist/summary")
async def therapist_summary(user: dict = Depends(current_user)):
    moods = await db.moods.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(14)
    journals = await db.journals.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    sessions = await db.sessions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(20)

    avg_score = sum(m["score"] for m in moods) / len(moods) if moods else None
    avg_sleep = sum(m["sleep_quality"] for m in moods) / len(moods) if moods else None
    triggers = {}
    for m in moods:
        for t in m.get("triggers", []):
            triggers[t] = triggers.get(t, 0) + 1
    top_triggers = sorted(triggers.items(), key=lambda x: -x[1])[:5]
    emotions = {}
    for s in sessions:
        e = s.get("last_emotion", "neutral")
        emotions[e] = emotions.get(e, 0) + 1

    summary_text = ""
    if moods:
        summary_text += f"Over the past {len(moods)} mood logs, average mood was {round(avg_score, 1)}/10 "
        summary_text += f"and average sleep quality was {round(avg_sleep, 1)}/10. "
    if top_triggers:
        summary_text += f"Most reported triggers: {', '.join(t for t, _ in top_triggers)}. "
    if emotions:
        top_em = sorted(emotions.items(), key=lambda x: -x[1])[:3]
        summary_text += f"Recurring emotional themes in conversations: {', '.join(e for e, _ in top_em)}. "
    if journals:
        summary_text += f"{len(journals)} journal reflections in this period. "
    if not summary_text:
        summary_text = "Not enough data yet — log moods, journals, or chat to build your reflection."

    reflection_topics = [
        "How does sleep quality correlate with my mood?",
        "What recurring triggers can I prepare for in advance?",
        "Which coping strategies have actually helped this week?",
    ]

    return {
        "summary": summary_text,
        "avg_mood": round(avg_score, 1) if avg_score else None,
        "avg_sleep": round(avg_sleep, 1) if avg_sleep else None,
        "top_triggers": [{"name": t, "count": c} for t, c in top_triggers],
        "recurring_emotions": emotions,
        "reflection_topics": reflection_topics,
        "mood_count": len(moods),
        "journal_count": len(journals),
        "session_count": len(sessions),
    }


# ---- Crisis Resources (always available) ----
@api.get("/crisis/resources")
async def crisis_resources():
    return get_crisis_resources()


# ---- Telegram public info ----
@api.get("/integrations/telegram")
async def telegram_info():
    username = getattr(app.state, "tg_bot_username", None)
    name = os.environ.get("TELEGRAM_BOT_NAME", "VentBuddy")
    if not username:
        return {"enabled": False, "name": name}
    return {
        "enabled": True,
        "name": name,
        "username": username,
        "url": f"https://t.me/{username}",
    }


# ---- Health ----
@api.get("/")
async def root():
    return {"service": "Mindful Companion", "status": "ok"}


# ---- Mount ----
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("mindful")


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index("telegram_chat_id", sparse=True)
    await db.messages.create_index([("user_id", 1), ("session_id", 1), ("created_at", 1)])
    await db.sessions.create_index([("user_id", 1), ("updated_at", -1)])
    await db.moods.create_index([("user_id", 1), ("created_at", -1)])
    await db.journals.create_index([("user_id", 1), ("created_at", -1)])
    await db.habits.create_index([("user_id", 1)])
    await db.habit_logs.create_index([("habit_id", 1), ("user_id", 1), ("log_date", 1)], unique=True)
    await db.checkins.create_index([("user_id", 1), ("log_date", 1)], unique=True)
    await seed_admin(db)
    logger.info("Mindful Companion ready")

    # Launch Telegram bot (long polling) in the background
    if os.environ.get("TELEGRAM_TOKEN"):
        try:
            tg_app = build_tg_app(db, EMERGENT_KEY)
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            app.state.tg_app = tg_app
            try:
                me = await tg_app.bot.get_me()
                app.state.tg_bot_username = me.username
                logger.info(f"VentBuddy Telegram bot polling as @{me.username}")
            except Exception:
                logger.exception("Could not fetch bot info")
                logger.info("VentBuddy Telegram bot polling")
        except Exception:
            logger.exception("Failed to start Telegram bot")


@app.on_event("shutdown")
async def on_shutdown():
    tg_app = getattr(app.state, "tg_app", None)
    if tg_app is not None:
        try:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        except Exception:
            logger.exception("Error stopping Telegram bot")
    client.close()
