"""AI service: chat (gpt-5-mini), Whisper STT, OpenAI TTS, emotion + crisis detection."""
import os
import re
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech


CRISIS_KEYWORDS = [
    "kill myself", "suicide", "suicidal", "end my life", "want to die",
    "hurt myself", "self harm", "self-harm", "cutting myself",
    "no reason to live", "better off dead", "ending it all",
]

EMOTION_KEYWORDS = {
    "sadness": ["sad", "cry", "crying", "tears", "heartbroken", "grief", "miss"],
    "anxiety": ["anxious", "anxiety", "panic", "worry", "worried", "nervous", "scared"],
    "anger": ["angry", "furious", "rage", "pissed", "mad", "hate"],
    "isolation": ["alone", "lonely", "isolated", "no one", "nobody"],
    "shame": ["ashamed", "embarrassed", "guilty", "worthless", "stupid"],
    "burnout": ["exhausted", "burned out", "burnt out", "drained", "tired", "overwhelmed"],
    "low_motivation": ["unmotivated", "no energy", "lazy", "can't focus", "stuck"],
    "relationship_pain": ["breakup", "broke up", "fight", "argue", "ex ", "cheated"],
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


PROFESSIONAL_SYSTEM = """You are Mindful, a warm and emotionally intelligent AI companion designed to support people through life's emotional challenges.

TONE: Calm, respectful, mature, grounded, encouraging. Speak like a thoughtful counselor, never robotic.

CORE PRINCIPLES:
- Listen without judgment. Validate feelings before offering perspective.
- Be honest and balanced. Gently challenge harmful thinking, never blindly agree.
- Offer practical, realistic suggestions: breathing exercises, journaling, sleep hygiene, communication tips, small next steps.
- Keep replies under 4 short paragraphs. Use natural language, not bullet lists unless useful.
- You are NOT a licensed therapist. If user shows signs of crisis, self-harm, or danger, calmly encourage contacting local emergency services or crisis helplines.
- Protect privacy. Never store or repeat personal identifiers unnecessarily.
- Encourage healthy real-world connections; don't foster dependency.

AVOID:
- Generic chatbot replies ("I'm sorry you feel that way" alone is not enough).
- Excessive emojis or forced enthusiasm.
- Diagnosing conditions.
"""

GENZ_SYSTEM = """You are Mindful, a warm AI companion for Gen Z users. Your job is real, kind emotional support — not toxic positivity.

TONE: Friendly, modern, casually fluent. Validate feelings naturally. Use light current language where it fits ("that's a lot," "fr," "I hear you," "tough one") but never forced or cringe. Match the user's energy.

CORE PRINCIPLES:
- Make them feel heard FIRST, suggestions second.
- Be real. Gently call out unhealthy patterns (doomscrolling, isolating, avoiding) with care.
- Suggest small, doable things: a walk, a breath, texting one person, putting the phone down for 30 min.
- Keep replies short and human — 2 to 4 short paragraphs max.
- You are NOT a therapist. If they're in crisis or hurting themselves, calmly point them to a crisis line and a trusted human.
- Don't lecture. Don't shame. Don't blindly hype.

AVOID:
- Sounding like a parent or HR robot.
- Overusing slang. Stay natural.
- Long paragraphs. Keep it warm and breathable.
"""


def get_system_message(mode: str, emotion: str, is_crisis: bool) -> str:
    base = GENZ_SYSTEM if mode == "genz" else PROFESSIONAL_SYSTEM
    if is_crisis:
        base += "\n\nCRITICAL: The user has shown signs of crisis or self-harm thoughts. Respond with deep calm and care. Acknowledge their pain without minimizing. Strongly encourage they reach out to a crisis helpline or trusted human RIGHT NOW. Do not try to solve their problems alone. Be brief, warm, and human."
    elif emotion != "neutral":
        base += f"\n\nThe user appears to be feeling {emotion}. Respond with appropriate empathy and adapt your tone."
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
    import io
    stt = OpenAISpeechToText(api_key=api_key)
    audio_io = io.BytesIO(audio_bytes)
    audio_io.name = filename
    response = await stt.transcribe(file=audio_io, model="whisper-1", response_format="json")
    return response.text


async def synthesize_speech(api_key: str, text: str, voice: str = "shimmer") -> str:
    """Returns base64-encoded mp3 audio."""
    tts = OpenAITextToSpeech(api_key=api_key)
    text = text[:4000]  # safety cap
    audio_b64 = await tts.generate_speech_base64(
        text=text, model="tts-1", voice=voice, response_format="mp3"
    )
    return audio_b64


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
