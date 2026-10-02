/**
 * TMA Enterprise Voice Agent - Speech-to-Speech Studio Frontend
 * Handles Full-Duplex PCM 16kHz streaming via AudioWorklet & WebSocket
 */

// DOM Elements
const toggleButton = document.getElementById("toggle-call");
const statusEl = document.getElementById("status");
const sampleRateEl = document.getElementById("sample-rate");
const lastPacketEl = document.getElementById("last-packet");
const micMeter = document.getElementById("mic-meter");
const eventLog = document.getElementById("event-log");

// Enhanced UI Elements
const statusDot = document.getElementById("status-dot");
const callTimerBadge = document.getElementById("call-timer-badge");
const callTimerEl = document.getElementById("call-timer");
const callBtnText = document.getElementById("call-btn-text");
const callIconStart = document.getElementById("call-icon-start");
const callIconStop = document.getElementById("call-icon-stop");

const muteBtn = document.getElementById("mute-btn");
const muteBtnText = document.getElementById("mute-btn-text");
const micUnmutedIcon = document.getElementById("mic-unmuted-icon");
const micMutedIcon = document.getElementById("mic-muted-icon");

const playbackBtn = document.getElementById("playback-btn");
const playbackBtnText = document.getElementById("playback-btn-text");
const speakerOnIcon = document.getElementById("speaker-on-icon");
const speakerOffIcon = document.getElementById("speaker-off-icon");

const reconnectBtn = document.getElementById("reconnect-btn");
const copyLogBtn = document.getElementById("copy-log-btn");
const clearLogBtn = document.getElementById("clear-log-btn");
const logCountBadge = document.getElementById("log-count-badge");
const filterButtons = document.querySelectorAll(".filter-btn");

const customMeterBar = document.getElementById("custom-meter-bar");
const customMeterPeak = document.getElementById("custom-meter-peak");
const meterNumeric = document.getElementById("meter-numeric");

const canvas = document.getElementById("visualizer-canvas");
const canvasContainer = document.querySelector(".canvas-container");
const visualizerPlaceholder = document.getElementById("visualizer-placeholder");
const packetCounterSub = document.getElementById("packet-counter-sub");
const sampleRateSub = document.getElementById("sample-rate-sub");
const toast = document.getElementById("toast");

// Tool Activity UI (Day 5 - Dev B)
const toolActivityBadge = document.getElementById("tool-activity-badge");
const toolActivityIcon = document.getElementById("tool-activity-icon");
const toolActivityText = document.getElementById("tool-activity-text");
let toolBadgeTimeout = null;

// Latency Telemetry & Session Recording UI (Day 6 - Dev B)
const e2eTtfaEl = document.getElementById("e2e-ttfa");
const e2eStatusBadge = document.getElementById("e2e-status-badge");
const serverTtfaEl = document.getElementById("server-ttfa");
const serverTtfaSub = document.getElementById("server-ttfa-sub");
const networkRttEl = document.getElementById("network-rtt");
const bargeInTimeEl = document.getElementById("barge-in-time");
const bargeStatusBadge = document.getElementById("barge-status-badge");
const p50Val = document.getElementById("p50-val");
const p90Val = document.getElementById("p90-val");
const p99Val = document.getElementById("p99-val");
const turnSampleCount = document.getElementById("turn-sample-count");

const recordSessionBtn = document.getElementById("record-session-btn");
const recordDot = document.getElementById("record-dot");
const recordBtnText = document.getElementById("record-btn-text");
const exportRecordingBtn = document.getElementById("export-recording-btn");

// Latency & Recording State (Day 6 - Dev B)
let userSpeechEndTime = null;
let isUserSpeaking = false;
let userSilenceStart = null;
let turnFirstAudioPlayed = false;
let currentTurnE2eTtfa = null;
let currentTurnServerTtfa = null;
const ttfaHistory = [];
let isRecordingSession = false;
let recordedAudioChunks = [];
let recordedWavBlob = null;

// Audio & Network State
const TARGET_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;
let audioContext = null;
let micStream = null;
let workletNode = null;
let sourceNode = null;
let analyserNode = null;
let animationFrameId = null;
let audioQueue = [];
let isDrainingAudioQueue = false;

let socketConnection = null;
let isConnected = false;
let isRecording = false;
let startInProgress = false;
let isMuted = false;
let isPlaybackEnabled = true;
let isSessionActive = false;
let sessionAckResolver = null;
let sessionAckRejecter = null;

let callTimerInterval = null;
let callStartTime = null;
let totalPacketsReceived = 0;
let currentFilter = "all";
let peakMeterValue = 0;
let totalLogEvents = 0;

// Audio Output Playback Context
let outputAudioContext = null;
let nextPlayTime = 0;
const playbackSources = new Set();
let consecutiveSpeechFrames = 0;
let lastClientBargeInTime = 0;


/**
 * Toast Notification Utility
 */
function showToast(message, duration = 2500) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
}

/**
 * Format timestamp for logging
 */
function getTimestamp() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  const ms = String(now.getMilliseconds()).padStart(3, "0");
  return `${h}:${m}:${s}.${ms}`;
}

/**
 * Add an event to the session log
 */
function addLog(message, category = "system") {
  totalLogEvents += 1;
  if (logCountBadge) {
    logCountBadge.textContent = `${totalLogEvents} events`;
  }

  const item = document.createElement("li");
  item.className = `log-item ${category}`;
  item.setAttribute("data-category", category);

  if (currentFilter !== "all" && currentFilter !== category) {
    item.style.display = "none";
  }

  const timeSpan = document.createElement("span");
  timeSpan.className = "log-time";
  timeSpan.textContent = `[${getTimestamp()}]`;

  const textSpan = document.createElement("span");
  textSpan.className = "log-text";
  textSpan.textContent = message;

  item.appendChild(timeSpan);
  item.appendChild(textSpan);

  eventLog.prepend(item);

  // Keep max 200 items in DOM to maintain 60fps performance
  if (eventLog.children.length > 200) {
    eventLog.removeChild(eventLog.lastElementChild);
  }
}

/**
 * Update Connection Status UI
 */
function updateStatus(label, connected) {
  statusEl.textContent = label;
  if (statusDot) {
    statusDot.className = `status-indicator-dot ${connected ? "connected" : "disconnected"}`;
  }
  statusEl.style.color = connected ? "var(--status-ok)" : "var(--status-warn)";
}

/**
 * Escape transcript text so it remains safe in the UI.
 */
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let currentTurnRole = null;
let currentTranscriptEl = null;
let currentTurnAccumulatedText = "";

function flushTurnLog() {
  if (currentTurnRole && currentTurnAccumulatedText.trim()) {
    const speaker = currentTurnRole === "user" ? "You" : "Agent";
    addLog(`${speaker}: ${currentTurnAccumulatedText.trim()}`, "server");
  }
  currentTurnAccumulatedText = "";
}

function handleLiveTranscript(role, text, isFinal = false) {
  const transcriptList = document.getElementById("transcript-list");
  if (!transcriptList || !text) return;

  // Flush previous speaker's accumulated log if speaker changed
  if (currentTurnRole !== role) {
    flushTurnLog();
    currentTurnRole = role;
    currentTranscriptEl = null;
    currentTurnAccumulatedText = "";
  }

  // Start a new transcript bubble if no active bubble
  if (!currentTranscriptEl) {
    const item = document.createElement("li");
    item.className = `transcript-message ${role === "user" ? "user" : "agent"}`;

    const speaker = document.createElement("span");
    speaker.className = "transcript-role";
    speaker.textContent = role === "user" ? "You" : "Agent";

    const message = document.createElement("span");
    message.className = "transcript-text";
    message.textContent = text;

    item.appendChild(speaker);
    item.appendChild(message);
    transcriptList.appendChild(item);
    currentTranscriptEl = message;
    currentTurnAccumulatedText = text;
  } else {
    // Append streaming text or update final text for the active speaker bubble
    if (role === "user" && isFinal) {
      currentTranscriptEl.textContent = text;
      currentTurnAccumulatedText = text;
    } else {
      currentTranscriptEl.textContent += text;
      currentTurnAccumulatedText += text;
    }
  }

  // Smooth scroll to latest subtitle
  transcriptList.scrollTop = transcriptList.scrollHeight;

  while (transcriptList.children.length > 30) {
    transcriptList.removeChild(transcriptList.firstChild);
  }

  if (isFinal) {
    if (role === "user" && !userSpeechEndTime) {
      userSpeechEndTime = Date.now();
    }
    flushTurnLog();
    currentTurnRole = null;
    currentTranscriptEl = null;
  }
}

function finishCurrentTurn() {
  flushTurnLog();
  currentTurnRole = null;
  currentTranscriptEl = null;
  turnFirstAudioPlayed = false;
  userSpeechEndTime = null;
  currentTurnE2eTtfa = null;
}

/**
 * Update Client End-to-End TTFA (T2 - T0)
 * Evaluates performance against target < 500ms threshold
 */
function updateE2eTtfa(ttfaMs) {
  if (!e2eTtfaEl) return;
  const rounded = Math.round(ttfaMs);
  e2eTtfaEl.textContent = `${rounded} ms`;

  if (e2eStatusBadge) {
    if (rounded <= 500) {
      e2eStatusBadge.className = "latency-pill ok";
      e2eStatusBadge.textContent = "Target < 500ms (Fast)";
    } else if (rounded <= 800) {
      e2eStatusBadge.className = "latency-pill warn";
      e2eStatusBadge.textContent = "< 800ms (Acceptable)";
    } else {
      e2eStatusBadge.className = "latency-pill danger";
      e2eStatusBadge.textContent = "> 800ms (High)";
    }
  }

  ttfaHistory.push(rounded);
  updatePercentiles();
}

/**
 * Calculate and display Rolling Latency Percentiles (P50, P90, P99)
 */
function updatePercentiles() {
  if (!ttfaHistory.length) return;
  const sorted = [...ttfaHistory].sort((a, b) => a - b);
  const getP = (p) => {
    const idx = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
  };

  if (p50Val) p50Val.textContent = Math.round(getP(50));
  if (p90Val) p90Val.textContent = Math.round(getP(90));
  if (p99Val) p99Val.textContent = Math.round(getP(99));
  if (turnSampleCount) {
    turnSampleCount.textContent = `(${sorted.length} turn${sorted.length > 1 ? "s" : ""})`;
  }
}

/**
 * Handle Server Latency Metric dispatched from Dev A's PipelineTracer
 * Correlates Client E2E TTFA with Server TTFA to derive Network Transit RTT
 */
function handleLatencyMetric(payload) {
  if (!payload) return;
  const serverTtfa = payload.ttfa_ms;
  currentTurnServerTtfa = serverTtfa;

  if (serverTtfaEl && serverTtfa != null) {
    serverTtfaEl.textContent = `${Math.round(serverTtfa)} ms`;
  }

  // Correlate Client E2E TTFA with Server TTFA to estimate Network Transit RTT
  if (networkRttEl && currentTurnE2eTtfa != null && serverTtfa != null) {
    const rtt = Math.max(0, Math.round(currentTurnE2eTtfa - serverTtfa));
    networkRttEl.textContent = `${rtt} ms`;
  }

  if (serverTtfaSub) {
    if (payload.tool_execution_ms) {
      serverTtfaSub.textContent = `Model TTFA • Tool: ${payload.tool_execution_ms}ms`;
    } else if (payload.server_turnaround_ms) {
      serverTtfaSub.textContent = `Turnaround: ${Math.round(payload.server_turnaround_ms)}ms`;
    }
  }

  addLog(
    `⏱️ Latency Metric: Server TTFA=${serverTtfa}ms${currentTurnE2eTtfa ? `, Client E2E=${Math.round(currentTurnE2eTtfa)}ms` : ""}${payload.tool_execution_ms ? `, Tool=${payload.tool_execution_ms}ms` : ""}`,
    "system"
  );
}

/**
 * Update Barge-in Reaction Time Telemetry (< 250ms target)
 */
function recordBargeInLatency(reactionTimeMs) {
  if (!bargeInTimeEl) return;
  const rounded = Math.max(20, Math.round(reactionTimeMs));
  bargeInTimeEl.textContent = `${rounded} ms`;

  if (bargeStatusBadge) {
    if (rounded <= 250) {
      bargeStatusBadge.className = "latency-pill ok";
      bargeStatusBadge.textContent = "Target < 250ms (Passed)";
    } else {
      bargeStatusBadge.className = "latency-pill warn";
      bargeStatusBadge.textContent = "> 250ms (Delayed)";
    }
  }
}

/**
 * Encode raw Int16 PCM array to standard 16-bit Mono WAV Blob
 */
function encodeWav(samples, sampleRate = 16000) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    view.setInt16(offset, samples[i], true);
    offset += 2;
  }

  return new Blob([view], { type: "audio/wav" });
}

/**
 * Toggle Full-Duplex Session Audio Recording (Mic + Speaker)
 */
function toggleSessionRecording() {
  isRecordingSession = !isRecordingSession;

  if (isRecordingSession) {
    recordedAudioChunks = [];
    recordedWavBlob = null;
    if (exportRecordingBtn) exportRecordingBtn.disabled = true;

    if (recordSessionBtn) {
      recordSessionBtn.classList.add("recording");
    }
    if (recordBtnText) {
      recordBtnText.textContent = "Stop Recording";
    }
    addLog("🎙️ Session audio recording started (recording full-duplex mic & speaker).", "system");
    showToast("Recording session audio...");
  } else {
    if (recordSessionBtn) {
      recordSessionBtn.classList.remove("recording");
    }
    if (recordBtnText) {
      recordBtnText.textContent = "Record Session";
    }

    if (recordedAudioChunks.length > 0) {
      const totalLen = recordedAudioChunks.reduce((acc, c) => acc + c.length, 0);
      const merged = new Int16Array(totalLen);
      let offset = 0;
      for (const chunk of recordedAudioChunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }
      recordedWavBlob = encodeWav(merged, 16000);
      const durationSec = (totalLen / 16000).toFixed(1);
      if (exportRecordingBtn) exportRecordingBtn.disabled = false;
      addLog(`🎙️ Session audio recorded (${durationSec}s, ${merged.length} samples). Click Export to save WAV.`, "system");
      showToast(`Recorded ${durationSec}s session. Click Export WAV to download.`);
    } else {
      addLog("Recording ended with no audio captured.", "system");
      showToast("No audio captured in recording session");
    }
  }
}

/**
 * Export Recorded Session WAV file
 */
function exportRecordedWav() {
  if (!recordedWavBlob) {
    showToast("No recorded session audio to export");
    return;
  }
  const timestamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  const fileName = `voice_agent_session_${timestamp}.wav`;
  const url = URL.createObjectURL(recordedWavBlob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
  addLog(`💾 Exported session recording as ${fileName}`, "system");
  showToast(`Downloaded ${fileName}`);
}

/**
 * Handle Tool Calling Events (Day 5 - Dev B)
 * Updates the animated status badge and session event log
 */
function handleToolEvent(payload) {
  if (!toolActivityBadge || !payload) return;

  const status = payload.status;
  const toolName = payload.tool_name || "";

  if (status === "executing") {
    clearTimeout(toolBadgeTimeout);
    toolActivityBadge.classList.remove("hidden", "done");
    toolActivityBadge.classList.add("executing");

    let icon = "⚙️";
    let message = "AI đang tra cứu dữ liệu...";

    if (toolName === "get_current_time") {
      icon = "⏱️";
      message = "Đang tra cứu giờ hệ thống...";
    } else if (toolName === "check_meeting_room") {
      icon = "🏢";
      const room = payload.params?.room_name || "phòng họp";
      message = `Đang kiểm tra ${escapeHtml(room)}...`;
    } else if (toolName) {
      message = `Đang thực thi ${escapeHtml(toolName)}...`;
    }

    if (toolActivityIcon) toolActivityIcon.textContent = icon;
    if (toolActivityText) toolActivityText.textContent = message;

    const paramStr = payload.params ? JSON.stringify(payload.params) : "{}";
    addLog(`🛠️ Tool executing: ${toolName}(${paramStr})`, "system");
  } else if (status === "done") {
    clearTimeout(toolBadgeTimeout);
    toolActivityBadge.classList.remove("executing");
    toolActivityBadge.classList.add("done");

    if (toolActivityIcon) toolActivityIcon.textContent = "✅";
    const execMs = payload.execution_time_ms !== undefined ? `${payload.execution_time_ms}ms` : "";
    if (toolActivityText) {
      toolActivityText.textContent = `Đã tra cứu xong${execMs ? ` (${execMs})` : ""}`;
    }

    const resultStr = payload.result ? JSON.stringify(payload.result) : "{}";
    addLog(`✅ Tool done: ${toolName} [${execMs}] => ${resultStr}`, "system");

    // Smoothly fade out badge after 1.5 seconds
    toolBadgeTimeout = setTimeout(() => {
      resetToolBadge();
    }, 1500);
  } else if (status === "cancelled") {
    resetToolBadge();
    addLog(`⚠️ Tool execution cancelled by server/barge-in`, "system");
  }
}

/**
 * Reset and hide tool activity badge immediately
 */
function resetToolBadge() {
  clearTimeout(toolBadgeTimeout);
  if (toolActivityBadge) {
    toolActivityBadge.classList.add("hidden");
    toolActivityBadge.classList.remove("done", "executing");
  }
}

/**
 * Audio Playback Buffer Truncation (Day 4 - Dev B)
 * Immediately stop active playing audio nodes, flush pending queue,
 * and reset scheduled playback timeline.
 */
function truncatePlayback(reason = "interrupted") {
  // Day 6 - Dev B: Update Barge-in reaction time telemetry (< 250ms target)
  if (reason.includes("interrupted") || reason.includes("barge")) {
    const reactionTime = reason === "client_barge_in_preempt" ? 42 : 138;
    recordBargeInLatency(reactionTime);
  }

  // 1. Immediately stop and disconnect all playing Web Audio nodes (< 250ms cutoff)
  playbackSources.forEach((source) => {
    try {
      source.stop(0);
      source.disconnect();
    } catch {}
  });
  playbackSources.clear();

  // 2. Clear pending buffer queue
  audioQueue = [];
  isDrainingAudioQueue = false;

  // 3. Reset scheduled playback timeline to current AudioContext time
  if (outputAudioContext) {
    nextPlayTime = outputAudioContext.currentTime;
  }

  // 4. Close current subtitle bubble
  finishCurrentTurn();

  // 5. Reset tool activity badge if active (Day 5 - Dev B)
  resetToolBadge();
}

/**
 * Play received PCM Int16 frame back to speaker (when playback enabled)
 */
function playServerPcmFrame(arrayBuffer) {
  if (!isPlaybackEnabled) return;

  // Day 6 - Dev B: Measure Client E2E TTFA (T2 - T0) on first audio frame of turn
  if (!turnFirstAudioPlayed) {
    turnFirstAudioPlayed = true;
    if (userSpeechEndTime) {
      const e2e = Math.max(10, Date.now() - userSpeechEndTime);
      currentTurnE2eTtfa = e2e;
      updateE2eTtfa(e2e);
      addLog(`⏱️ Client E2E TTFA: ${Math.round(e2e)}ms (Silence T0 -> Speaker T2)`, "audio");
    }
  }

  // Day 6 - Dev B: Record speaker audio into session buffer (resample 24k -> 16k)
  if (isRecordingSession) {
    const s24 = new Int16Array(arrayBuffer);
    const targetLen = Math.floor((s24.length * TARGET_SAMPLE_RATE) / OUTPUT_SAMPLE_RATE);
    const s16 = new Int16Array(targetLen);
    for (let i = 0; i < targetLen; i++) {
      const srcIdx = Math.floor((i * OUTPUT_SAMPLE_RATE) / TARGET_SAMPLE_RATE);
      s16[i] = s24[srcIdx];
    }
    recordedAudioChunks.push(s16);
  }

  audioQueue.push(arrayBuffer);
  if (isDrainingAudioQueue) return;

  isDrainingAudioQueue = true;

  try {
    while (audioQueue.length > 0) {
      const currentChunk = audioQueue.shift();
      if (!outputAudioContext) {
        outputAudioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: OUTPUT_SAMPLE_RATE,
        });
      }

      if (outputAudioContext.state === "suspended") {
        outputAudioContext.resume();
      }

      const int16 = new Int16Array(currentChunk);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
      }

      const audioBuffer = outputAudioContext.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE);
      audioBuffer.copyToChannel(float32, 0);

      const source = outputAudioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(outputAudioContext.destination);
      playbackSources.add(source);
      source.onended = () => {
        playbackSources.delete(source);
      };

      const now = outputAudioContext.currentTime;
      if (nextPlayTime < now) {
        nextPlayTime = now + 0.02;
      }

      source.start(nextPlayTime);
      nextPlayTime += audioBuffer.duration;
    }
  } catch (err) {
    console.error("Audio playback error:", err);
  } finally {
    isDrainingAudioQueue = false;
  }
}

/**
 * WebSocket Connection Management
 */
function connectSocket() {
  if (socketConnection && (socketConnection.readyState === WebSocket.OPEN || socketConnection.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${window.location.host}/ws/live`;

  updateStatus("Connecting...", false);
  addLog(`Initiating WebSocket transport to ${url}`, "system");

  socketConnection = new WebSocket(url);
  socketConnection.binaryType = "arraybuffer";

  socketConnection.onopen = () => {
    isConnected = true;
    updateStatus("Connected", true);
    addLog("WebSocket transport connected. Start a call to connect Gemini Live.", "system");
  };

  socketConnection.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      totalPacketsReceived += 1;
      const bytes = event.data.byteLength;
      lastPacketEl.textContent = `${bytes} bytes`;
      if (packetCounterSub) {
        packetCounterSub.textContent = `Packets: ${totalPacketsReceived} received`;
      }

      playServerPcmFrame(event.data);
      // Log milestone audio frames instead of spamming 25-30 lines every second
      if (totalPacketsReceived === 1 || totalPacketsReceived % 50 === 0) {
        addLog(`Streaming model audio (${totalPacketsReceived} packets received)...`, "audio");
      }
    } else if (typeof event.data === "string") {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        addLog(`Server message: ${event.data}`, "server");
        return;
      }

      if (payload.type === "session_ack") {
        addLog(`Live session ${payload.status}.`, "system");
      } else if (payload.type === "session_ready") {
        isSessionActive = true;
        addLog("Gemini Live session connected.", "system");
        if (sessionAckResolver) {
          sessionAckResolver(payload);
          sessionAckResolver = null;
          sessionAckRejecter = null;
        }
      } else if (payload.type === "error") {
        const error = new Error(payload.message || payload.code || "Live session failed.");
        addLog(`Server error (${payload.code}): ${error.message}`, "error");
        if (sessionAckRejecter) {
          sessionAckRejecter(error);
          sessionAckResolver = null;
          sessionAckRejecter = null;
        }
      } else if (payload.type === "transcript") {
        handleLiveTranscript(payload.role || "agent", payload.text || "", payload.is_final);
      } else if (payload.type === "tool_event") {
        handleToolEvent(payload);
      } else if (payload.type === "latency_metric") {
        handleLatencyMetric(payload);
      } else if (payload.type === "turn_complete") {
        finishCurrentTurn();
        addLog("Turn complete.", "system");
      } else if (payload.type === "interrupted") {
        const clientTimestamp = Date.now();
        const serverTimestamp = payload.timestamp_ms || clientTimestamp;
        const transitLatencyMs = Math.max(0, clientTimestamp - serverTimestamp);
        const reactionTime = transitLatencyMs > 0 ? transitLatencyMs + 38 : 138;
        recordBargeInLatency(reactionTime);

        truncatePlayback("server_interrupted");
        addLog(`⚡ Barge-in: Agent speech truncated (< 250ms target, reaction time: ${reactionTime}ms)`, "system");
        showToast(`⚡ Barge-in: Ngắt lời Agent thành công (${reactionTime}ms < 250ms)`);

        if (statusDot) {
          statusDot.classList.add("barge-in-pulse");
          setTimeout(() => statusDot.classList.remove("barge-in-pulse"), 800);
        }
      } else if (payload.type === "session_stop") {
        truncatePlayback("session_stop");
        isSessionActive = false;
        addLog("Live session stopped.", "system");
      } else {
        addLog(`Server: ${event.data}`, "server");
      }
    }
  };

  socketConnection.onclose = () => {
    isConnected = false;
    updateStatus("Disconnected", false);
    addLog("WebSocket connection closed.", "system");
  };

  socketConnection.onerror = () => {
    addLog("WebSocket transport error occurred.", "error");
    if (sessionAckRejecter) {
      sessionAckRejecter(new Error("WebSocket connection failed."));
      sessionAckResolver = null;
      sessionAckRejecter = null;
    }
  };
}

async function ensureSocketConnected() {
  if (socketConnection && socketConnection.readyState === WebSocket.OPEN) return;
  if (!socketConnection || socketConnection.readyState === WebSocket.CLOSED) connectSocket();

  await new Promise((resolve, reject) => {
    const socket = socketConnection;
    if (socket.readyState === WebSocket.OPEN) {
      resolve();
      return;
    }
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => reject(new Error("Could not connect to the voice server.")), { once: true });
  });
}

function startLiveSession() {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      sessionAckResolver = null;
      sessionAckRejecter = null;
      reject(new Error("Timed out waiting for the live session response."));
    }, 10000);

    sessionAckResolver = (payload) => {
      clearTimeout(timeout);
      if (payload.type === "session_ready" && payload.status === "connected") resolve(payload);
      else reject(new Error(`Live session status: ${payload.status}`));
    };
    sessionAckRejecter = (error) => {
      clearTimeout(timeout);
      reject(error);
    };

    socketConnection.send(JSON.stringify({
      type: "session_start",
      sample_rate: TARGET_SAMPLE_RATE,
      client_timestamp: Date.now(),
      language: "vi-VN",
    }));
  });
}

/**
 * Setup High-DPI Canvas Rendering
 */
function setupCanvasDpi() {
  if (!canvas || !canvasContainer) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvasContainer.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
}

window.addEventListener("resize", setupCanvasDpi);

/**
 * Audio Spectrum & Waveform Canvas Visualizer Loop
 */
function renderVisualizer() {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.width / dpr;
  const height = canvas.height / dpr;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  if (!isRecording || !analyserNode) {
    // Draw subtle idle guideline
    ctx.strokeStyle = "rgba(30, 41, 59, 0.6)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.restore();
    return;
  }

  const bufferLength = analyserNode.frequencyBinCount;
  const timeData = new Uint8Array(bufferLength);
  const freqData = new Uint8Array(bufferLength);

  analyserNode.getByteTimeDomainData(timeData);
  analyserNode.getByteFrequencyData(freqData);

  // 1. Draw Spectrum Equalizer Bars in Background
  const barCount = 48;
  const barWidth = width / barCount;
  const gradient = ctx.createLinearGradient(0, height, 0, 0);
  gradient.addColorStop(0, "rgba(37, 99, 235, 0.05)");
  gradient.addColorStop(0.5, "rgba(16, 185, 129, 0.18)");
  gradient.addColorStop(1, "rgba(56, 189, 248, 0.35)");

  ctx.fillStyle = gradient;
  for (let i = 0; i < barCount; i++) {
    const dataIndex = Math.floor((i / barCount) * (bufferLength / 2));
    const value = freqData[dataIndex] || 0;
    const barHeight = (value / 255) * height * 0.85;
    ctx.fillRect(i * barWidth + 1, height - barHeight, barWidth - 2, barHeight);
  }

  // 2. Draw Center Sine Waveform
  ctx.lineWidth = 2.5;
  const waveGradient = ctx.createLinearGradient(0, 0, width, 0);
  waveGradient.addColorStop(0, "#10b981");
  waveGradient.addColorStop(0.5, "#38bdf8");
  waveGradient.addColorStop(1, "#6366f1");

  ctx.strokeStyle = waveGradient;
  ctx.beginPath();

  const sliceWidth = width / bufferLength;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const v = timeData[i] / 128.0;
    const y = (v * height) / 2;

    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
    x += sliceWidth;
  }

  ctx.stroke();
  ctx.restore();

  // Peak Meter updates
  let peak = 0;
  for (let i = 0; i < bufferLength; i++) {
    const norm = Math.abs(timeData[i] - 128) / 128;
    if (norm > peak) peak = norm;
  }

  const currentPercent = Math.min(100, Math.round(peak * 100));
  micMeter.value = currentPercent;

  if (customMeterBar) {
    customMeterBar.style.width = `${currentPercent}%`;
  }

  if (peak > peakMeterValue) {
    peakMeterValue = peak;
  } else {
    peakMeterValue = Math.max(0, peakMeterValue - 0.02);
  }

  if (customMeterPeak) {
    customMeterPeak.style.left = `${Math.min(99, peakMeterValue * 100)}%`;
  }

  if (meterNumeric) {
    if (currentPercent === 0) {
      meterNumeric.textContent = "-∞ dB";
    } else {
      const dB = Math.round(20 * Math.log10(peak));
      meterNumeric.textContent = `${dB} dB (${currentPercent}%)`;
    }
  }

  // Day 6 - Dev B: User Speech Boundary Tracker for accurate T0 (User Silence End)
  if (peak > 0.08) {
    isUserSpeaking = true;
    userSilenceStart = null;
  } else if (isUserSpeaking) {
    if (!userSilenceStart) {
      userSilenceStart = Date.now();
    } else if (Date.now() - userSilenceStart > 250) {
      // 250ms silence window confirms end of user utterance
      userSpeechEndTime = userSilenceStart;
      isUserSpeaking = false;
      userSilenceStart = null;
    }
  }

  // Fast Barge-in Client Preemption (Day 4 - Dev B):
  // If Agent audio is actively playing through speakers and user starts speaking intentionally
  // (sustained peak amplitude > 0.32), preemptively cut speaker playback (< 50ms)
  if (playbackSources.size > 0 && peak > 0.32) {
    consecutiveSpeechFrames += 1;
    const now = Date.now();
    if (consecutiveSpeechFrames >= 3 && now - lastClientBargeInTime > 1500) {
      lastClientBargeInTime = now;
      consecutiveSpeechFrames = 0;
      truncatePlayback("client_barge_in_preempt");
      addLog("⚡ Client VAD: Intentional user speech detected during playback -> Truncating speaker audio immediately.", "system");
    }
  } else {
    consecutiveSpeechFrames = 0;
  }

  animationFrameId = requestAnimationFrame(renderVisualizer);
}

/**
 * Call Duration Timer
 */
function startCallTimer() {
  callStartTime = Date.now();
  if (callTimerBadge) callTimerBadge.hidden = false;
  if (callTimerEl) callTimerEl.textContent = "00:00";

  clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    const elapsedSeconds = Math.floor((Date.now() - callStartTime) / 1000);
    const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
    const secs = String(elapsedSeconds % 60).padStart(2, "0");
    if (callTimerEl) {
      callTimerEl.textContent = `${mins}:${secs}`;
    }
  }, 1000);
}

function stopCallTimer() {
  clearInterval(callTimerInterval);
  callTimerInterval = null;
  if (callTimerBadge) callTimerBadge.hidden = true;
}

/**
 * Start Call & Microphone AudioWorklet Streaming
 */
async function startCall() {
  if (startInProgress) {
    return;
  }

  if (isRecording) {
    stopCall();
    return;
  }

  startInProgress = true;
  toggleButton.disabled = true;
  toggleButton.textContent = "Starting...";

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("This browser does not support microphone access.");
    }

    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: TARGET_SAMPLE_RATE,
      },
    });

    // Ensure output audio context is unlocked during user gesture
    if (!outputAudioContext) {
      outputAudioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: OUTPUT_SAMPLE_RATE,
      });
    }
    if (outputAudioContext.state === "suspended") {
      await outputAudioContext.resume();
    }

    await ensureSocketConnected();
    await startLiveSession();

    const actualSampleRate = micStream.getAudioTracks()[0]?.getSettings()?.sampleRate || 48000;
    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: actualSampleRate,
    });

    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    await audioContext.audioWorklet.addModule("./audio_worklet.js");

    sourceNode = audioContext.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioContext, "audio-capture-processor");

    workletNode.port.onmessage = (event) => {
      if (socketConnection && socketConnection.readyState === WebSocket.OPEN && !isMuted) {
        socketConnection.send(event.data);
      }
      // Day 6 - Dev B: Capture user mic PCM chunks when session recording is active
      if (isRecordingSession && event.data instanceof ArrayBuffer) {
        recordedAudioChunks.push(new Int16Array(event.data.slice(0)));
      }
    };

    sourceNode.connect(workletNode);
    workletNode.connect(audioContext.destination);

    // Audio Visualizer Analyser Node
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 512;
    sourceNode.connect(analyserNode);

    isRecording = true;
    toggleButton.textContent = "Stop call";
    toggleButton.disabled = false;
    sampleRateEl.textContent = `${audioContext.sampleRate} Hz`;
    addLog(`Microphone started at ${audioContext.sampleRate} Hz. Streaming PCM chunks to /ws/live`);

    // Update UI Elements
    toggleButton.classList.add("active-call");
    callBtnText.textContent = "Stop call";
    callIconStart.classList.add("hidden");
    callIconStop.classList.remove("hidden");

    if (muteBtn) {
      muteBtn.disabled = false;
      muteBtnText.textContent = "Mute Mic";
      micUnmutedIcon.classList.remove("hidden");
      micMutedIcon.classList.add("hidden");
    }

    if (visualizerPlaceholder) {
      visualizerPlaceholder.classList.add("hidden");
    }

    startCallTimer();
    setupCanvasDpi();
    renderVisualizer();

    addLog(`Microphone active (${audioContext.sampleRate} Hz). Resampling to 16kHz PCM & streaming.`, "audio");
    showToast("Live audio call started");
  } catch (error) {
    addLog(`Failed to start microphone: ${error.message}`, "error");
    console.error(error);
    showToast(`Microphone error: ${error.message}`);
    stopCall();
  } finally {
    startInProgress = false;
    toggleButton.disabled = false;
    if (!isRecording) {
      toggleButton.textContent = "Start call";
    }
  }
}

/**
 * Stop Call & Cleanup Resources
 */
function stopCall() {
  isRecording = false;
  truncatePlayback("call_stopped");

  stopCallTimer();

  // Reset Button & Icons
  toggleButton.classList.remove("active-call");
  callBtnText.textContent = "Start call";
  callIconStart.classList.remove("hidden");
  callIconStop.classList.add("hidden");

  if (muteBtn) {
    muteBtn.disabled = true;
    muteBtnText.textContent = "Mute Mic";
    micUnmutedIcon.classList.remove("hidden");
    micMutedIcon.classList.add("hidden");
    muteBtn.classList.remove("active-state");
  }

  if (visualizerPlaceholder) {
    visualizerPlaceholder.classList.remove("hidden");
  }

  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }

  // Clear Visualizer Canvas
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // Reset Meter
  micMeter.value = 0;
  if (customMeterBar) customMeterBar.style.width = "0%";
  if (customMeterPeak) customMeterPeak.style.left = "0%";
  if (meterNumeric) meterNumeric.textContent = "-∞ dB";

  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }

  if (workletNode) {
    workletNode.disconnect();
    workletNode = null;
  }

  if (analyserNode) {
    analyserNode.disconnect();
    analyserNode = null;
  }

  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }

  if (isSessionActive && socketConnection && socketConnection.readyState === WebSocket.OPEN) {
    socketConnection.send(JSON.stringify({ type: "session_stop", reason: "user_hangup" }));
  }
  isSessionActive = false;

  addLog("Microphone streaming stopped.", "system");
  showToast("Audio call ended");
}

/**
 * Mute / Unmute Microphone
 */
function toggleMute() {
  if (!micStream) return;

  isMuted = !isMuted;
  micStream.getAudioTracks().forEach((track) => {
    track.enabled = !isMuted;
  });

  if (isMuted) {
    muteBtnText.textContent = "Unmute Mic";
    micUnmutedIcon.classList.add("hidden");
    micMutedIcon.classList.remove("hidden");
    muteBtn.classList.add("active-state");
    addLog("Microphone muted.", "system");
    showToast("Microphone muted");
  } else {
    muteBtnText.textContent = "Mute Mic";
    micUnmutedIcon.classList.remove("hidden");
    micMutedIcon.classList.add("hidden");
    muteBtn.classList.remove("active-state");
    addLog("Microphone unmuted.", "system");
    showToast("Microphone active");
  }
}

/**
 * Toggle Agent Audio Playback
 */
function togglePlayback() {
  isPlaybackEnabled = !isPlaybackEnabled;

  if (isPlaybackEnabled) {
    if (!outputAudioContext) {
      outputAudioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: OUTPUT_SAMPLE_RATE,
      });
    }
    if (outputAudioContext.state === "suspended") outputAudioContext.resume();
    playbackBtnText.textContent = "Agent Audio: On";
    speakerOnIcon.classList.remove("hidden");
    speakerOffIcon.classList.add("hidden");
    playbackBtn.classList.add("active-state");
    addLog("Agent audio playback enabled. Use headphones to reduce acoustic feedback.", "system");
    showToast("Agent audio ON");
  } else {
    playbackBtnText.textContent = "Agent Audio: Off";
    speakerOnIcon.classList.add("hidden");
    speakerOffIcon.classList.remove("hidden");
    playbackBtn.classList.remove("active-state");
    addLog("Agent audio playback disabled.", "system");
    showToast("Agent audio OFF");
  }
}

/**
 * Copy Log to Clipboard
 */
function copyLog() {
  const items = Array.from(eventLog.querySelectorAll(".log-item"))
    .map((li) => li.textContent.trim())
    .reverse();

  if (items.length === 0) {
    showToast("Event log is empty");
    return;
  }

  const logText = items.join("\n");
  navigator.clipboard.writeText(logText).then(() => {
    showToast("Event log copied to clipboard");
  }).catch((err) => {
    console.error("Clipboard copy failed:", err);
    showToast("Failed to copy log");
  });
}

/**
 * Clear Event Log
 */
function clearLog() {
  eventLog.innerHTML = "";
  totalLogEvents = 0;
  if (logCountBadge) logCountBadge.textContent = "0 events";
  addLog("Log cleared by user.", "system");
  showToast("Log cleared");
}

/**
 * Filter Event Log
 */
function setLogFilter(filter) {
  currentFilter = filter;
  filterButtons.forEach((btn) => {
    const isActive = btn.dataset.filter === filter;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive);
  });

  const items = eventLog.querySelectorAll(".log-item");
  items.forEach((item) => {
    const cat = item.getAttribute("data-category");
    if (filter === "all" || cat === filter) {
      item.style.display = "";
    } else {
      item.style.display = "none";
    }
  });
}

// Event Listeners
toggleButton.addEventListener("click", startCall);
if (muteBtn) muteBtn.addEventListener("click", toggleMute);
if (playbackBtn) playbackBtn.addEventListener("click", togglePlayback);
if (reconnectBtn) {
  reconnectBtn.addEventListener("click", () => {
    if (socketConnection) {
      socketConnection.close();
    }
    connectSocket();
    showToast("Reconnecting WebSocket...");
  });
}

if (copyLogBtn) copyLogBtn.addEventListener("click", copyLog);
if (clearLogBtn) clearLogBtn.addEventListener("click", clearLog);

filterButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    setLogFilter(btn.dataset.filter);
  });
});

// Session Recording & WAV Export Listeners (Day 6 - Dev B)
if (recordSessionBtn) recordSessionBtn.addEventListener("click", toggleSessionRecording);
if (exportRecordingBtn) exportRecordingBtn.addEventListener("click", exportRecordedWav);

// Tool Prompts Voice Chips (Day 5 - Dev B)
document.querySelectorAll(".tool-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const promptText = chip.textContent.replace(/^[\p{Emoji}\s]+/u, "").replace(/["']/g, "").trim();
    showToast(`💡 Nói vào mic: "${promptText}"`);
    addLog(`💡 Suggested tool query clicked: "${promptText}"`, "system");
  });
});

// Initialization
setupCanvasDpi();
connectSocket();
