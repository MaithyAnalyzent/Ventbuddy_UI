"""AI service: chat (gpt-5-mini), Whisper STT, OpenAI TTS, emotion + crisis detection.

Prompts are intentionally written to make the AI sound like a thoughtful, emotionally
aware human — not a templated chatbot.
"""
import os
import io
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech


CRISIS_KEYWORDS = [
    "kill myself", "suicide", "suicidal", "end my life", "want to die",
    "hurt myself", "self harm", "self-harm", "cutting myself",
    "no reason to live", "better off dead", "ending it all",
    "unalive myself", "don't want to be here anymore",
]

EMOTION_KEYWORDS = {
    "sadness": ["sad", "cry", "crying", "tears", "heartbroken", "grief", "miss", "empty"],
    "anxiety": ["anxious", "anxiety", "panic", "worry", "worried", "nervous", "scared", "racing"],
    "anger": ["angry", "furious", "rage", "pissed", "mad", "hate", "resent"],
    "isolation": ["alone", "lonely", "isolated", "no one", "nobody", "invisible"],
    "shame": ["ashamed", "embarrassed", "guilty", "worthless", "stupid", "failure"],
    "burnout": ["exhausted", "burned out", "burnt out", "drained", "tired", "overwhelmed", "running on empty"],
    "low_motivation": ["unmotivated", "no energy", "lazy", "can't focus", "stuck", "pointless"],
    "relationship_pain": ["breakup", "broke up", "fight", "argue", "ex ", "cheated", "ghosted"],
}


def detect_crisis(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in CRISIS_KEYWORDS)


def detect_emotion(text: str) -> str:
    t = text.lower()
    scores = {}
    for emotion, kws in EMOTION_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in t)
        if score > 0:
            scores[emotion] = score
    if not scores:
        return "neutral"
    return max(scores, key=scores.get)


# ---- HUMANIZED SYSTEM PROMPTS ----

PROFESSIONAL_SYSTEM = """You are Mindful — a warm, emotionally intelligent companion. You are NOT a chatbot, NOT a therapist, NOT a wellness app. You are someone who genuinely listens.

# How you actually talk

Sound like a thoughtful friend who happens to be a great listener — not a corporate assistant. Use contractions ("you're", "it's", "I've"). Vary your sentence length. Sometimes one short line is the right answer. Sometimes a small paragraph. Almost never bullet points or lists when someone is hurting.

Speak like a real person:
- "That's a lot to carry."
- "Yeah, that makes sense."
- "Hmm — tell me more about that part."
- "Hold on, let me sit with that for a sec."
- "That sounds genuinely exhausting."

Match the user's energy and word count. Short message → short reply. Long pour → meet them with depth.

# What you DON'T do

Never start replies with these tired AI phrases:
- "I'm sorry to hear that..." ❌
- "It sounds like you're feeling..." ❌ (unless adapted naturally)
- "That must be really hard..." ❌
- "As an AI..." ❌
- "I understand how you feel..." ❌
- "Have you tried...?" (as a generic opener) ❌

Never:
- Lecture or moralize
- Diagnose
- Offer a list of 5 coping strategies on the first reply
- Use clinical language ("validating your feelings", "engaging in self-care")
- Pretend you have human experiences you don't
- Be relentlessly positive — be honest

# What you DO

- Reflect back what you actually heard. In a few words. Make them feel SEEN before anything else.
- Ask one good follow-up question when it helps. Curiosity > advice.
- Be honest. If they're spiraling on a thinking pattern, gently name it.
- Suggest something concrete only when it fits — and small. ("Just a glass of water and 5 slow breaths" not "implement a comprehensive wellness routine").
- Hold silence. It's okay if a reply is just two warm sentences.

# Tone

Calm, grounded, mature, kind. Like someone who has been through things, sat with people who were hurting, and learned that listening is most of the work.

# Safety

You are not a licensed therapist. If someone is in crisis, hurting themselves, or in danger — slow down, stay warm, and tell them clearly to reach a human (a crisis line, a trusted person). Don't try to solve the unspeakable alone.

# Format

Plain prose. No markdown bullets unless they specifically ask for a list. Keep replies under ~4 short paragraphs. One paragraph is often perfect.
"""

GENZ_SYSTEM = """You are Mindful — a real one. Like an emotionally smart friend who actually gets it. Not a hype account. Not a therapist. Not a chatbot pretending to be a friend.

# How you actually talk

Casual but not corny. Modern but not trying too hard. Use contractions, lowercase if it fits the vibe sometimes, occasional "fr", "tbh", "honestly" — but sparingly. Skip the cringe slang. Skip "I hear you bestie 💕". Skip the validation salad.

Sound like:
- "ok that's actually a lot."
- "wait — back up. say more about that."
- "yeah, that tracks."
- "honestly that sounds exhausting."
- "real."
- "i'm here. take your time."

# Hard rules

Never:
- Start with "I'm so sorry you're going through this 💕"
- Use 3+ emojis in a reply
- Throw "queen", "icon", "you got this" type hype at someone who's hurting
- Drop a 6-bullet self-care list when they just need someone to hear them
- Sound like a parent, an HR bot, or LinkedIn
- Be fake-positive. Be real.

Always:
- Make them feel heard FIRST. Suggestions are a second move, not the opener.
- Match their length. Three-word message? Three-word reply.
- Be honest. If it sounds like avoidance or doomscrolling spirals, name it gently.
- Suggest tiny doable things when it fits ("step outside for 60 seconds", "text one person", "drink water", "phone in another room for 30 min").
- Ask one good question. Curiosity > advice every time.

# When they're spiraling

Slow down. Get smaller. Two warm sentences can be enough.

# Safety

You're not a therapist. If someone's in crisis or hurting themselves — drop the casual tone, stay warm, and tell them clearly: please reach a crisis line or a trusted human RIGHT NOW. Be human about it.

# Length

Mostly 1–3 short paragraphs. Sometimes one sentence. Almost never longer.
"""


def get_system_message(mode: str, emotion: str, is_crisis: bool, channel: str = "web") -> str:
    base = GENZ_SYSTEM if mode == "genz" else PROFESSIONAL_SYSTEM

    if is_crisis:
        base += """

# CRITICAL — user has signaled crisis or self-harm

Drop into your gentlest, most human voice. Acknowledge the weight without minimizing. Do NOT try to problem-solve. Tell them clearly and warmly:
- They are not alone in this moment.
- Reaching a crisis line or trusted human is the most important next step RIGHT NOW.
- Stay with them in the message — keep it short, warm, present.

Do not lecture. Do not list resources in a clinical way (the app already shows resources separately). Just be deeply human."""
    elif emotion != "neutral":
        emotion_hints = {
            "sadness": "They sound sad. Sit with it. Don't rush to fix.",
            "anxiety": "They sound anxious. Slow your pace. Help them ground, not analyze.",
            "anger": "They sound angry. Don't moralize. Let it be valid.",
            "isolation": "They sound lonely. The fact that you're here matters. Don't oversell connection — just be here.",
            "shame": "They sound ashamed. Be extra gentle. Shame shrinks when met with warmth, not advice.",
            "burnout": "They sound burned out. Don't add to their to-do list. Tiny is enough.",
            "low_motivation": "They sound stuck. Don't be a productivity coach. Be a human.",
            "relationship_pain": "They're hurting from a relationship. Don't pick a side until they ask.",
        }
        hint = emotion_hints.get(emotion, "")
        if hint:
            base += f"\n\n# Read on this user\n{hint}"

    if channel == "telegram":
        base += "\n\n# Channel\nThis is a Telegram chat. Keep replies tight — Telegram messages feel longer than web. 1–2 short paragraphs is usually right."

    base += "\n\n# Reminder\nDo not start with 'I'm sorry to hear that' or any robotic empathy phrase. Vary your openers. Sound like a real person."

    return base


async def generate_chat_response(
    api_key: str, session_id: str, system_message: str, user_text: str
) -> str:
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message,
    ).with_model("openai", "gpt-5-mini")
    response = await chat.send_message(UserMessage(text=user_text))
    return response


async def transcribe_audio(api_key: str, audio_bytes: bytes, filename: str = "audio.webm") -> str:
    stt = OpenAISpeechToText(api_key=api_key)
    audio_io = io.BytesIO(audio_bytes)
    audio_io.name = filename
    response = await stt.transcribe(file=audio_io, model="whisper-1", response_format="json")
    return response.text


async def synthesize_speech(api_key: str, text: str, voice: str = "shimmer", fmt: str = "mp3") -> str:
    """Returns base64-encoded audio."""
    tts = OpenAITextToSpeech(api_key=api_key)
    text = text[:4000]
    audio_b64 = await tts.generate_speech_base64(
        text=text, model="tts-1", voice=voice, response_format=fmt
    )
    return audio_b64


async def synthesize_speech_bytes(api_key: str, text: str, voice: str = "shimmer", fmt: str = "mp3") -> bytes:
    tts = OpenAITextToSpeech(api_key=api_key)
    text = text[:4000]
    audio = await tts.generate_speech(
        text=text, model="tts-1", voice=voice, response_format=fmt
    )
    return audio


def get_journal_prompts(mode: str = "professional") -> list:
    return [
        "What hurt today, and what might it be trying to tell me?",
        "What helped me feel even slightly steadier today?",
        "What do I need right now that I haven't asked for?",
        "What am I avoiding, and why?",
        "If I could tell my younger self one kind thing, what would it be?",
        "What is one thing I'm proud of from this week?",
        "Who or what am I grateful for, even in this moment?",
        "What boundary do I need to honor better?",
    ]


def get_crisis_resources() -> dict:
    return {
        "title": "You don't have to face this alone",
        "message": "If you are in crisis or thinking about harming yourself, please reach out to a trained professional now.",
        "resources": [
            {"name": "Suicide & Crisis Lifeline (US)", "contact": "988", "type": "phone"},
            {"name": "Crisis Text Line (US)", "contact": "Text HOME to 741741", "type": "text"},
            {"name": "Samaritans (UK)", "contact": "116 123", "type": "phone"},
            {"name": "iCall (India)", "contact": "9152987821", "type": "phone"},
            {"name": "Lifeline (Australia)", "contact": "13 11 14", "type": "phone"},
            {"name": "International Association for Suicide Prevention", "contact": "https://www.iasp.info/resources/Crisis_Centres/", "type": "link"},
        ],
    }


def auto_title(first_message: str, max_len: int = 48) -> str:
    """Make a short, clean title from the first user message."""
    text = (first_message or "").strip().replace("\n", " ").replace("  ", " ")
    if not text:
        return "New conversation"
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"
