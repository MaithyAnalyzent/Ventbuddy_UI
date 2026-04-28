import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import VoiceMicButton from "@/components/VoiceMicButton";
import CrisisBanner from "@/components/CrisisBanner";
import {
  PaperPlaneTilt, SpeakerHigh, SpeakerSlash, Plus, MagnifyingGlass,
  PencilSimple, Trash, Check, X, ChatCircleDots, List as ListIcon,
} from "@phosphor-icons/react";
import axios from "axios";

export default function Chat() {
  const { user } = useAuth();
  const { sessionId: routeSessionId } = useParams();
  const navigate = useNavigate();

  const [sessionId, setSessionId] = useState(routeSessionId || null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const [crisis, setCrisis] = useState(null);

  const [sessions, setSessions] = useState([]);
  const [search, setSearch] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameText, setRenameText] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const audioRef = useRef(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  // Load sessions list
  const loadSessions = async (q = "") => {
    try {
      const { data } = await api.get("/chat/sessions", { params: q ? { q } : {} });
      setSessions(data);
    } catch {}
  };

  useEffect(() => { loadSessions(); }, []);

  // Search debounce
  useEffect(() => {
    const t = setTimeout(() => loadSessions(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  // Load messages on sessionId change
  useEffect(() => {
    setSessionId(routeSessionId || null);
    if (!routeSessionId) {
      setMessages([]);
      setCrisis(null);
      return;
    }
    (async () => {
      try {
        const { data } = await api.get(`/chat/sessions/${routeSessionId}/messages`);
        setMessages(data);
      } catch {}
    })();
  }, [routeSessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [text]);

  const playAudio = (b64) => {
    if (!b64) return;
    const audio = new Audio(`data:audio/mp3;base64,${b64}`);
    if (audioRef.current) audioRef.current.pause();
    audioRef.current = audio;
    audio.play().catch(() => {});
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setCrisis(null);
    setText("");
    setSidebarOpen(false);
    navigate("/chat", { replace: true });
  };

  const openSession = (id) => {
    setSidebarOpen(false);
    navigate(`/chat/${id}`);
  };

  const deleteSession = async (id, e) => {
    e?.stopPropagation();
    if (!window.confirm("Delete this conversation?")) return;
    try {
      await api.delete(`/chat/sessions/${id}`);
      if (sessionId === id) startNewChat();
      await loadSessions(search);
    } catch {}
  };

  const startRename = (s, e) => {
    e?.stopPropagation();
    setRenamingId(s.id);
    setRenameText(s.title || "Untitled");
  };

  const submitRename = async (id) => {
    const t = renameText.trim();
    if (!t) { setRenamingId(null); return; }
    try {
      await api.patch(`/chat/sessions/${id}`, { title: t });
      setRenamingId(null);
      await loadSessions(search);
    } catch {}
  };

  const sendText = async () => {
    if (!text.trim() || sending) return;
    const content = text.trim();
    setText("");
    setSending(true);
    setMessages((m) => [...m, { id: `tmp-${Date.now()}`, role: "user", content, created_at: new Date().toISOString() }]);
    try {
      const { data } = await api.post("/chat/send", {
        text: content,
        mode: user?.mode || "professional",
        session_id: sessionId,
        voice_reply: voiceOn,
      });
      if (!sessionId) {
        setSessionId(data.session_id);
        navigate(`/chat/${data.session_id}`, { replace: true });
      }
      setMessages((m) => [
        ...m,
        { id: `ai-${Date.now()}`, role: "assistant", content: data.reply, created_at: new Date().toISOString() },
      ]);
      if (data.is_crisis) setCrisis(data.crisis_resources);
      else setCrisis(null);
      if (voiceOn && data.audio_b64) playAudio(data.audio_b64);
      loadSessions(search);
    } catch {
      setMessages((m) => [
        ...m,
        { id: `err-${Date.now()}`, role: "assistant", content: "Something hiccupped on my end. Mind sending that again?", created_at: new Date().toISOString() },
      ]);
    } finally {
      setSending(false);
    }
  };

  const sendVoice = async (blob) => {
    if (sending) return;
    setSending(true);
    try {
      const form = new FormData();
      form.append("audio", blob, "voice.webm");
      form.append("mode", user?.mode || "professional");
      if (sessionId) form.append("session_id", sessionId);
      form.append("voice_reply", String(voiceOn));
      const { data } = await axios.post(`${API_BASE}/chat/voice`, form, { withCredentials: true });
      if (!sessionId) {
        setSessionId(data.session_id);
        navigate(`/chat/${data.session_id}`, { replace: true });
      }
      setMessages((m) => [
        ...m,
        { id: `u-${Date.now()}`, role: "user", content: data.transcript, created_at: new Date().toISOString() },
        { id: `ai-${Date.now()}`, role: "assistant", content: data.reply, created_at: new Date().toISOString() },
      ]);
      if (data.is_crisis) setCrisis(data.crisis_resources);
      else setCrisis(null);
      if (voiceOn && data.audio_b64) playAudio(data.audio_b64);
      loadSessions(search);
    } catch {
      setMessages((m) => [
        ...m,
        { id: `err-${Date.now()}`, role: "assistant", content: "I couldn't catch that — try again?", created_at: new Date().toISOString() },
      ]);
    } finally {
      setSending(false);
    }
  };

  const isGenZ = user?.mode === "genz";

  return (
    <div className="-mx-4 -my-8 sm:-mx-6 lg:-mx-8 h-[calc(100vh-4rem)] flex" data-testid="chat-page">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0
          fixed lg:relative inset-y-0 left-0 z-30 w-80 lg:w-72 border-r border-border bg-sand-100
          transition-transform duration-300 flex flex-col`}
      >
        <div className="px-4 py-4 border-b border-border space-y-3">
          <Button
            data-testid="new-chat-button"
            onClick={startNewChat}
            className="w-full h-11 rounded-xl bg-ink-900 text-sand-50 hover:bg-ink-900/90 justify-start gap-2"
          >
            <Plus weight="bold" size={18} />
            New conversation
          </Button>
          <div className="relative">
            <MagnifyingGlass weight="duotone" size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-600" />
            <Input
              data-testid="chat-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations..."
              className="pl-9 h-10 rounded-xl bg-sand-50 border-border focus-visible:ring-sage-400"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          {sessions.length === 0 && (
            <p className="text-xs text-ink-600 text-center py-6 px-3">
              {search ? "No matches." : "No conversations yet — start one above."}
            </p>
          )}
          {sessions.map((s) => {
            const active = s.id === sessionId;
            return (
              <div
                key={s.id}
                data-testid={`session-item-${s.id}`}
                onClick={() => openSession(s.id)}
                className={`group relative cursor-pointer px-3 py-2.5 rounded-xl transition-colors ${
                  active ? "bg-sage-100" : "hover:bg-sand-200/60"
                }`}
              >
                {renamingId === s.id ? (
                  <div className="flex items-center gap-1">
                    <Input
                      autoFocus
                      data-testid={`rename-input-${s.id}`}
                      value={renameText}
                      onChange={(e) => setRenameText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") submitRename(s.id);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="h-8 text-sm rounded-lg bg-sand-50"
                    />
                    <button
                      onClick={(e) => { e.stopPropagation(); submitRename(s.id); }}
                      data-testid={`rename-confirm-${s.id}`}
                      className="p-1 text-sage-700"
                    >
                      <Check weight="bold" size={16} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setRenamingId(null); }}
                      className="p-1 text-ink-600"
                    >
                      <X weight="bold" size={16} />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start gap-2">
                      <ChatCircleDots weight="duotone" size={16} className={`shrink-0 mt-0.5 ${active ? "text-sage-700" : "text-ink-600"}`} />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-ink-900 truncate">
                          {s.title || s.last_message || "New conversation"}
                        </p>
                        <p className="text-xs text-ink-600 truncate mt-0.5">
                          {s.channel === "telegram" ? "📱 " : ""}
                          {s.last_message || "No messages yet"}
                        </p>
                      </div>
                    </div>
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5 bg-sand-50 rounded-lg px-1 shadow-sm">
                      <button
                        onClick={(e) => startRename(s, e)}
                        data-testid={`rename-btn-${s.id}`}
                        className="p-1.5 text-ink-600 hover:text-sage-700"
                        title="Rename"
                      >
                        <PencilSimple size={14} weight="duotone" />
                      </button>
                      <button
                        onClick={(e) => deleteSession(s.id, e)}
                        data-testid={`delete-btn-${s.id}`}
                        className="p-1.5 text-ink-600 hover:text-crisis"
                        title="Delete"
                      >
                        <Trash size={14} weight="duotone" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </aside>

      {/* Sidebar overlay on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-ink-900/30 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main chat */}
      <section className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="px-4 sm:px-6 lg:px-8 py-3 border-b border-border bg-sand-50/80 backdrop-blur flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              data-testid="sidebar-toggle"
              className="lg:hidden p-2 rounded-lg hover:bg-sand-200/60 text-ink-900"
            >
              <ListIcon weight="duotone" size={22} />
            </button>
            <div className="min-w-0">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-sage-700">
                {isGenZ ? "Gen Z mode" : "Professional mode"}
              </span>
              <h2 className="font-heading text-lg font-medium text-ink-900 truncate">
                {sessionId
                  ? (sessions.find((s) => s.id === sessionId)?.title || "Conversation")
                  : (isGenZ ? "what's up?" : "I'm here whenever you're ready.")}
              </h2>
            </div>
          </div>
          <button
            onClick={() => setVoiceOn((v) => !v)}
            data-testid="voice-toggle"
            className={`shrink-0 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider px-3 py-2 rounded-full border ${
              voiceOn ? "bg-sage-400 text-sand-50 border-sage-400" : "bg-sand-50 text-ink-600 border-border"
            }`}
          >
            {voiceOn ? <SpeakerHigh size={16} weight="duotone" /> : <SpeakerSlash size={16} weight="duotone" />}
            <span className="hidden sm:inline">Voice {voiceOn ? "on" : "off"}</span>
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto" data-testid="chat-messages-area">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-5">
            {messages.length === 0 && (
              <div className="text-center py-16">
                <p className="text-xs uppercase tracking-[0.3em] text-ink-600">A safe space</p>
                <h3 className="font-heading text-3xl sm:text-4xl text-ink-900 mt-4 max-w-md mx-auto leading-tight">
                  {isGenZ ? "what's actually going on?" : "Tell me what's on your mind."}
                </h3>
                <p className="text-ink-600 mt-3 text-sm max-w-md mx-auto">
                  {isGenZ ? "voice or text. take your time." : "There's no pressure. Type, or tap the mic."}
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                data-testid={`chat-msg-${m.role}`}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] sm:max-w-[75%] px-5 py-3.5 rounded-2xl text-[15px] leading-[1.65] whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-sage-400 text-sand-50 rounded-br-md"
                      : "bg-sand-50 text-ink-900 border border-border rounded-bl-md"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-sand-50 border border-border px-5 py-3 rounded-2xl text-sm text-ink-600 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-bounce" style={{ animationDelay: "120ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-bounce" style={{ animationDelay: "240ms" }} />
                </div>
              </div>
            )}
            {crisis && <CrisisBanner resources={crisis} embedded />}
          </div>
        </div>

        {/* Sticky composer */}
        <div className="border-t border-border bg-sand-50/95 backdrop-blur sticky bottom-0">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4">
            <div className="flex items-end gap-3">
              <div className="flex-1 bg-sand-50 border border-border rounded-2xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-sage-400 transition">
                <Textarea
                  ref={textareaRef}
                  data-testid="chat-text-input"
                  placeholder={isGenZ ? "say anything..." : "Share what's on your heart..."}
                  rows={1}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendText();
                    }
                  }}
                  className="resize-none border-0 bg-transparent p-0 min-h-[28px] max-h-[200px] focus-visible:ring-0 text-[15px] leading-relaxed"
                />
              </div>
              <Button
                onClick={sendText}
                disabled={sending || !text.trim()}
                data-testid="chat-send-button"
                className="h-11 w-11 p-0 rounded-full bg-ink-900 text-sand-50 hover:bg-ink-900/90 shrink-0"
              >
                <PaperPlaneTilt weight="fill" size={18} />
              </Button>
              <div className="shrink-0 hidden sm:block">
                <CompactMic onRecorded={sendVoice} disabled={sending} />
              </div>
            </div>
            <div className="sm:hidden mt-3 flex justify-center">
              <VoiceMicButton onRecorded={sendVoice} disabled={sending} />
            </div>
            <p className="text-[11px] text-ink-600 mt-2 text-center">
              Mindful is supportive companionship, not a replacement for therapy. Press Enter to send.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

// Compact mic for desktop composer
function CompactMic({ onRecorded, disabled }) {
  const [recording, setRecording] = useState(false);
  const ref = useRef(null);
  const chunks = useRef([]);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size > 0 && chunks.current.push(e.data);
      mr.onstop = () => {
        const blob = new Blob(chunks.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        if (blob.size > 0) onRecorded(blob);
      };
      mr.start();
      ref.current = mr;
      setRecording(true);
    } catch {}
  };
  const stop = () => {
    if (ref.current && ref.current.state !== "inactive") ref.current.stop();
    setRecording(false);
  };

  return (
    <button
      type="button"
      data-testid="push-to-talk-button"
      disabled={disabled}
      onClick={recording ? stop : start}
      className={`relative h-11 w-11 rounded-full grid place-items-center transition-all ${
        recording ? "bg-terracotta-400 text-sand-50" : "bg-sage-100 text-sage-700 hover:bg-sage-400 hover:text-sand-50"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      title={recording ? "Stop" : "Voice message"}
    >
      {recording && <span className="mic-ring animate-pulse-ring" />}
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3z" />
        <path d="M19 10v1a7 7 0 01-14 0v-1H3v1a9 9 0 008 8.94V22h2v-2.06A9 9 0 0021 11v-1z" />
      </svg>
    </button>
  );
}
