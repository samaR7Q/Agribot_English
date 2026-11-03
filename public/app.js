// Kisan Dost Bashir (English) – browser client.
// The browser talks to Gemini Live directly with a one-call token from /api/session;
// tool calls go to /api/tool, where the rules live. See docs/PLAN_2026-11-02.md.

const WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained";
const IDLE_LIMIT_MS = 2 * 60 * 1000;     // after this the connection is closed; the next tap resumes it
const MAX_RECORDING_MS = 45 * 1000;
// Backstop for the prompt's English-only rule: a reply whose transcript has non-English letters
// (any non-ASCII letter, e.g. Spanish ñ/¿ or Hindi/Urdu script) or common Spanish words is cut off.
const NOT_ENGLISH = /[^\x00-\x7F\u2010-\u2027\u20A8\u00A0]|\b(lo siento|por favor|puedo|usted|gracias|cultivos|ganado|relacionados|agricultura)\b/i;
const RETRY_IN_ENGLISH = "[Your last reply was not in English, so it was cut off and the farmer did not hear it. Reply again in English only. If the farmer spoke another language, give the English-only refusal.]";
const HISTORY_KEY = "agribot_en_history";
const PASSCODE_KEY = "agribot_en_passcode";

const $ = (id) => document.getElementById(id);
const els = {
  chat: $("chat"), status: $("status"), mic: $("micBtn"), plus: $("newChatBtn"),
  avatar: $("avatar"), video: $("avatarVideo"), back: $("backBtn"),
  historyBtn: $("historyBtn"), historyPanel: $("historyPanel"), historyList: $("historyList"),
  historyClose: $("historyClose"), speakerIcon: $("speakerIcon"),
};

// ── small helpers ────────────────────────────────────────────────────────────
const safeStorage = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};

function randomId() {
  const a = new Uint8Array(8);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}

function b64FromBuffer(buffer) {
  const bytes = new Uint8Array(buffer);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function int16FromB64(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Int16Array(bytes.buffer, 0, bytes.length >> 1);
}

async function api(path, body, retried = false) {
  const passcode = safeStorage.get(PASSCODE_KEY, "");
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(passcode ? { "x-demo-passcode": passcode } : {}) },
    body: JSON.stringify(body),
    keepalive: path === "/api/log",
  });
  if (res.status === 401 && !retried) {
    const code = window.prompt("Enter the demo passcode");
    if (!code) throw new Error("Passcode needed");
    safeStorage.set(PASSCODE_KEY, code.trim());
    return api(path, body, true);
  }
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}

// ── audio out ────────────────────────────────────────────────────────────────
class Player {
  constructor(onSpeaking) {
    this.ctx = new AudioContext({ sampleRate: 24000 });
    this.next = 0;
    this.sources = new Set();
    this.onSpeaking = onSpeaking || (() => {});
  }

  enqueue(int16) {
    if (!int16.length) return;
    const buf = this.ctx.createBuffer(1, int16.length, 24000);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < int16.length; i++) ch[i] = int16[i] / 0x8000;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    const start = Math.max(this.ctx.currentTime + 0.03, this.next);
    src.start(start);
    this.next = start + buf.duration;
    this.sources.add(src);
    if (this.sources.size === 1) this.onSpeaking(true);
    src.onended = () => {
      this.sources.delete(src);
      if (!this.sources.size) this.onSpeaking(false);
    };
  }

  stop() {
    for (const s of this.sources) { try { s.stop(); } catch { /* already stopped */ } }
    this.sources.clear();
    this.next = 0;
    this.onSpeaking(false);
  }

  close() { this.stop(); this.ctx.close().catch(() => {}); }
}

// ── chat UI ──────────────────────────────────────────────────────────────────
const ui = {
  userBubble: null,
  botBubble: null,
  replay: null,

  clear() {
    els.chat.textContent = "";
    this.userBubble = this.botBubble = null;
  },

  note(text) {
    const div = document.createElement("div");
    div.className = "bubble note";
    div.textContent = text;
    els.chat.appendChild(div);
    this.scroll();
  },

  bubble(role, text = "") {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    const span = document.createElement("span");
    span.className = "text";
    span.textContent = text;
    div.appendChild(span);
    els.chat.appendChild(div);
    this.scroll();
    return div;
  },

  addSpeaker(bubble, chunks) {
    const btn = document.createElement("button");
    btn.className = "speak";
    btn.setAttribute("aria-label", "Play again");
    btn.appendChild(els.speakerIcon.content.cloneNode(true));
    btn.disabled = !chunks || !chunks.length;
    btn.addEventListener("click", () => {
      if (!this.replay) this.replay = new Player();
      this.replay.stop();
      this.replay.ctx.resume();
      chunks.forEach((c) => this.replay.enqueue(c));
    });
    bubble.appendChild(btn);
  },

  userText(text) {
    if (!this.userBubble) {
      this.endBot();
      this.userBubble = this.bubble("user");
      this.userBubble.dataset.text = "";
    }
    this.userBubble.dataset.text += text;
    this.userBubble.querySelector(".text").textContent = this.userBubble.dataset.text.trim();
    this.scroll();
  },

  ensureBot() {
    if (!this.botBubble) {
      this.endUser();
      this.botBubble = this.bubble("bot");
      this.botBubble.dataset.text = "";
      this.botBubble._chunks = [];
    }
    return this.botBubble;
  },

  botText(text) {
    const b = this.ensureBot();
    b.dataset.text += text;
    b.querySelector(".text").textContent = b.dataset.text.trim();
    this.scroll();
  },

  botAudio(int16) { this.ensureBot()._chunks.push(int16); },

  endUser() {
    if (!this.userBubble) return null;
    const text = this.userBubble.dataset.text.trim();
    if (!text) this.userBubble.remove();
    this.userBubble = null;
    return text || null;
  },

  endBot(interrupted = false) {
    if (!this.botBubble) return null;
    const b = this.botBubble;
    const text = b.dataset.text.trim() + (interrupted ? " …" : "");
    b.querySelector(".text").textContent = text;
    if (!text && !b._chunks.length) b.remove();
    else this.addSpeaker(b, b._chunks);
    this.botBubble = null;
    return text || null;
  },

  scroll() { els.chat.scrollTop = els.chat.scrollHeight; },
};

// mode: "idle" | "connecting" | "ready" (connected, not recording) | "recording"
function setMic(mode, label) {
  els.mic.classList.toggle("recording", mode === "recording");
  els.mic.classList.toggle("connecting", mode === "connecting");
  els.mic.setAttribute("aria-label", mode === "recording" ? "Stop recording" : "Start recording");
  els.status.textContent = label;
}

function setSpeaking(on) {
  els.avatar.classList.toggle("speaking", on);
  if (on) { els.video.play().catch(() => {}); } else { els.video.pause(); }
  if (call && call.ready && !call.recording) setMic("ready", on ? "Bashir is speaking… tap to interrupt" : "Tap the mic to speak");
}

// ── history (per device) ─────────────────────────────────────────────────────
const history = {
  list() { return safeStorage.get(HISTORY_KEY, []); },
  save(chat) {
    if (!chat.turns.some((t) => t.role === "user")) return;
    const all = this.list().filter((c) => c.id !== chat.id);
    all.unshift(chat);
    safeStorage.set(HISTORY_KEY, all.slice(0, 50));
  },
};

let viewing = false;

function openHistory() {
  els.historyList.textContent = "";
  const chats = history.list();
  if (!chats.length) {
    const p = document.createElement("p");
    p.className = "history-empty";
    p.textContent = "No past chats yet.";
    els.historyList.appendChild(p);
  }
  for (const chat of chats) {
    const btn = document.createElement("button");
    btn.className = "history-item";
    const when = document.createElement("div");
    when.className = "when";
    when.textContent = new Date(chat.started).toLocaleString();
    const first = document.createElement("div");
    first.className = "first";
    first.textContent = (chat.turns.find((t) => t.role === "user") || {}).text || "(no words)";
    btn.append(when, first);
    btn.addEventListener("click", () => showPastChat(chat));
    els.historyList.appendChild(btn);
  }
  els.historyPanel.hidden = false;
}

function showPastChat(chat) {
  if (call && call.active) call.end("Call ended.");
  els.historyPanel.hidden = true;
  ui.clear();
  viewing = true;
  for (const t of chat.turns) ui.bubble(t.role, t.text);
  ui.note("This is a past chat. Tap + to start a new one.");
  setMic("idle", "Past chat");
}

// ── the call ─────────────────────────────────────────────────────────────────
class LiveCall {
  constructor() {
    this.sessionId = randomId();
    this.state = null;
    this.handle = null;
    this.active = false;
    this.ready = false;
    this.greeted = false;
    this.reconnecting = false;
    this.sleeping = false;     // connection closed after idle; the next tap resumes it
    this.recording = false;
    this.generating = false;   // Bashir's current answer is still arriving
    this.dropping = false;     // farmer tapped over that answer: ignore the rest of it
    this.langRetried = false;  // one English retry per farmer turn
    this.logBuffer = [];
    this.chat = { id: this.sessionId, started: Date.now(), turns: [] };
    this.lastActivity = Date.now();
  }

  log(event) {
    this.logBuffer.push({ client_ts: new Date().toISOString(), ...event });
    if (this.logBuffer.length >= 20) this.flushLogs();
  }

  flushLogs() {
    if (!this.logBuffer.length) return;
    const events = this.logBuffer.splice(0);
    api("/api/log", { session_id: this.sessionId, events }).catch(() => {});
  }

  send(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  async start() {
    this.active = true;
    setMic("connecting", "Connecting…");
    this.player = new Player(setSpeaking);
    await this.player.ctx.resume();
    await this.openMic();
    await this.connect(false);
    this.timers = [
      setInterval(() => {
        if (this.ready && !this.recording && !this.player.sources.size && Date.now() - this.lastActivity > IDLE_LIMIT_MS) this.sleep();
      }, 10000),
      setInterval(() => this.flushLogs(), 5000),
    ];
  }

  async openMic() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    this.micCtx = new AudioContext();
    await this.micCtx.audioWorklet.addModule("mic-worklet.js");
    const src = this.micCtx.createMediaStreamSource(this.stream);
    this.micNode = new AudioWorkletNode(this.micCtx, "mic-processor");
    const sink = this.micCtx.createGain();
    sink.gain.value = 0;
    src.connect(this.micNode).connect(sink).connect(this.micCtx.destination);
    this.micNode.port.onmessage = (e) => {
      if (this.ready && this.recording) this.send({ realtimeInput: { audio: { data: b64FromBuffer(e.data), mimeType: "audio/pcm;rate=16000" } } });
    };
  }

  async connect(resume) {
    const s = await api("/api/session", { session_id: this.sessionId, resume });
    if (!this.state) this.state = s.state;
    this.greetingTrigger = s.greeting_trigger;
    if (!this.maxTimer) {
      this.maxTimer = setTimeout(() => this.end(`Call ended after ${s.max_call_minutes} minutes.`), s.max_call_minutes * 60000);
    }
    await new Promise((resolve, reject) => {
      const ws = new WebSocket(`${WS_URL}?access_token=${encodeURIComponent(s.token)}`);
      this.ws = ws;
      const timeout = setTimeout(() => reject(new Error("Gemini did not answer")), 15000);
      ws.onopen = () => {
        const setup = { model: `models/${s.model}` };
        setup.sessionResumption = this.handle ? { handle: this.handle } : {};
        ws.send(JSON.stringify({ setup }));
      };
      ws.onmessage = async (ev) => {
        const raw = typeof ev.data === "string" ? ev.data : await ev.data.text();
        let msg;
        try { msg = JSON.parse(raw); } catch { return; }
        if (msg.setupComplete) { clearTimeout(timeout); resolve(); }
        this.onMessage(msg);
      };
      ws.onerror = () => this.log({ event: "ws_error" });
      ws.onclose = (ev) => {
        clearTimeout(timeout);
        reject(new Error(ev.reason || `closed (${ev.code})`));
        if (ws === this.ws) this.onClose(ev);
      };
    });
    this.ready = true;
    this.log({ event: resume ? "ws_resumed" : "ws_ready" });
    if (!this.greeted) {
      this.greeted = true;
      this.send({ realtimeInput: { text: this.greetingTrigger } });
    }
    setMic("ready", this.player.sources.size ? "Bashir is speaking… tap to interrupt" : "Tap the mic to speak");
  }

  // ── tap-to-talk ──
  startRecording() {
    if (!this.ready || this.recording) return;
    if (this.generating) this.dropping = true;
    this.player.stop();
    this.finishTurn(true);
    this.recording = true;
    this.langRetried = false;
    this.lastActivity = Date.now();
    this.send({ realtimeInput: { activityStart: {} } });
    setMic("recording", "Listening… tap when done");
    this.recTimer = setTimeout(() => this.stopRecording(), MAX_RECORDING_MS);
  }

  stopRecording() {
    if (!this.recording) return;
    this.recording = false;
    clearTimeout(this.recTimer);
    this.lastActivity = Date.now();
    this.send({ realtimeInput: { activityEnd: {} } });
    setMic("ready", "Bashir is thinking…");
  }

  closeMic() {
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.micCtx) this.micCtx.close().catch(() => {});
    this.stream = this.micCtx = null;
  }

  sleep() {
    this.sleeping = true;
    this.ready = false;
    const ws = this.ws;
    this.ws = null;
    try { ws && ws.close(); } catch { /* ignore */ }
    this.closeMic();
    this.log({ event: "sleep" });
    setMic("idle", "Tap the mic to continue");
  }

  async wake() {
    this.sleeping = false;
    setMic("connecting", "Connecting…");
    await this.player.ctx.resume();
    await this.openMic();
    await this.connect(true);
    this.startRecording();
  }

  onMessage(msg) {
    if (msg.serverContent) this.onServerContent(msg.serverContent);
    if (msg.toolCall) this.onToolCall(msg.toolCall);
    if (msg.toolCallCancellation) this.log({ event: "tool_cancelled", ids: msg.toolCallCancellation.ids });
    if (msg.sessionResumptionUpdate && msg.sessionResumptionUpdate.resumable && msg.sessionResumptionUpdate.newHandle) {
      this.handle = msg.sessionResumptionUpdate.newHandle;
    }
    if (msg.usageMetadata) this.log({ event: "usage", usage: msg.usageMetadata });
    if (msg.goAway) {
      this.log({ event: "go_away", timeLeft: msg.goAway.timeLeft });
      this.reconnect();
    }
  }

  onServerContent(sc) {
    if (sc.inputTranscription && sc.inputTranscription.text) {
      this.lastActivity = Date.now();
      ui.userText(sc.inputTranscription.text);
    }
    if (sc.interrupted || sc.turnComplete) {
      const dropped = this.dropping;
      this.generating = this.dropping = false;
      if (dropped) return;
    }
    if (this.dropping) return;
    if (sc.modelTurn && sc.modelTurn.parts) {
      this.generating = true;
      for (const part of sc.modelTurn.parts) {
        if (part.inlineData && part.inlineData.data) {
          const pcm = int16FromB64(part.inlineData.data);
          this.player.enqueue(pcm);
          ui.botAudio(pcm);
        }
      }
    }
    if (sc.outputTranscription && sc.outputTranscription.text) {
      const sofar = (ui.botBubble ? ui.botBubble.dataset.text : "") + sc.outputTranscription.text;
      if (NOT_ENGLISH.test(sofar)) { this.blockNonEnglish(sofar); return; }
      ui.botText(sc.outputTranscription.text);
    }
    if (sc.interrupted) {
      this.player.stop();
      this.finishTurn(true);
    }
    if (sc.turnComplete) this.finishTurn(false);
  }

  blockNonEnglish(text) {
    this.player.stop();
    this.log({ event: "non_english_blocked", text });
    if (ui.botBubble) { ui.botBubble.remove(); ui.botBubble = null; }
    if (this.generating) this.dropping = true;
    if (this.langRetried) { ui.note("Bashir only talks in English. Please ask your question in English."); return; }
    this.langRetried = true;
    this.send({ realtimeInput: { text: RETRY_IN_ENGLISH } });
  }

  finishTurn(interrupted) {
    const user = ui.endUser();
    if (user) { this.chat.turns.push({ role: "user", text: user }); this.log({ event: "user", text: user }); }
    const bot = ui.endBot(interrupted);
    if (bot) { this.chat.turns.push({ role: "bot", text: bot }); this.log({ event: "bot", text: bot, interrupted }); }
    this.lastActivity = Date.now();
    history.save(this.chat);
  }

  async onToolCall(toolCall) {
    // Sequential on purpose: each tool may change the state the next one reads.
    const functionResponses = [];
    for (const fc of toolCall.functionCalls || []) {
      let result;
      try {
        const r = await api("/api/tool", { session_id: this.sessionId, call_id: fc.id, name: fc.name, args: fc.args || {}, state: this.state });
        this.state = r.state;
        result = r.result;
      } catch (err) {
        result = { status: "error", instruction: "The lookup failed. Apologise briefly and ask the farmer to try again." };
        this.log({ event: "tool_error", name: fc.name, error: String(err) });
      }
      functionResponses.push({ id: fc.id, name: fc.name, response: result });
    }
    this.send({ toolResponse: { functionResponses } });
  }

  onClose(ev) {
    this.ready = false;
    this.log({ event: "ws_closed", code: ev.code, reason: ev.reason });
    if (!this.active || this.reconnecting || this.sleeping) return;
    if (this.handle) this.reconnect();
    else this.end(`Connection closed${ev.reason ? `: ${ev.reason}` : ""}. Tap the mic to start again.`);
  }

  async reconnect() {
    if (this.reconnecting || !this.active) return;
    this.reconnecting = true;
    this.ready = false;
    if (this.recording) { this.recording = false; clearTimeout(this.recTimer); }
    const old = this.ws;
    this.ws = null;
    try { old && old.close(); } catch { /* ignore */ }
    try {
      setMic("connecting", "Reconnecting…");
      await this.connect(true);
    } catch (err) {
      this.end("Connection lost. Tap the mic to start again.");
    } finally {
      this.reconnecting = false;
    }
  }

  end(note) {
    if (!this.active) return;
    this.active = false;
    this.ready = false;
    this.finishTurn(true);
    (this.timers || []).forEach(clearInterval);
    clearTimeout(this.maxTimer);
    clearTimeout(this.recTimer);
    this.recording = false;
    const ws = this.ws;
    this.ws = null;
    try { ws && ws.close(); } catch { /* ignore */ }
    this.closeMic();
    if (this.player) this.player.close();
    this.log({ event: "call_ended", note: note || "" });
    this.flushLogs();
    history.save(this.chat);
    setSpeaking(false);
    setMic("idle", "Tap the mic to start");
    if (note) ui.note(note);
  }
}

let call = null;

// One button: the first tap connects (Bashir greets); after that each tap starts or stops recording.
async function onMicTap() {
  if (call && call.active) {
    if (call.sleeping) {
      try { await call.wake(); } catch (err) { call.end(`Couldn't reconnect: ${err.message || err}`); }
    } else if (call.recording) call.stopRecording();
    else call.startRecording();
    return;
  }
  if (viewing) { ui.clear(); viewing = false; }
  call = new LiveCall();
  try {
    await call.start();
  } catch (err) {
    const msg = err && err.name === "NotAllowedError"
      ? "Microphone permission is needed to talk to Bashir."
      : `Couldn't start the call: ${err.message || err}`;
    call.end(msg);
  }
}

function newChat() {
  if (call && call.active) call.end();
  call = null;
  viewing = false;
  ui.clear();
  ui.note("Tap the green mic to start. Then tap it to speak, and tap again when you finish.");
  setMic("idle", "Tap the mic to start");
}

els.mic.addEventListener("click", onMicTap);
els.plus.addEventListener("click", newChat);
els.historyBtn.addEventListener("click", openHistory);
els.historyClose.addEventListener("click", () => { els.historyPanel.hidden = true; });
els.back.addEventListener("click", () => {
  if (!els.historyPanel.hidden) els.historyPanel.hidden = true;
  else if (viewing) newChat();
});
window.addEventListener("pagehide", () => { if (call) call.flushLogs(); });

newChat();
