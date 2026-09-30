const toggleButton = document.getElementById("toggle-call");
const statusEl = document.getElementById("status");
const sampleRateEl = document.getElementById("sample-rate");
const lastPacketEl = document.getElementById("last-packet");
const micMeter = document.getElementById("mic-meter");
const eventLog = document.getElementById("event-log");

const TARGET_SAMPLE_RATE = 16000;
let audioContext = null;
let micStream = null;
let workletNode = null;
let sourceNode = null;
let socketConnection = null;
let isConnected = false;
let isRecording = false;

function addLog(message) {
  const item = document.createElement("li");
  item.textContent = message;
  eventLog.prepend(item);
}

function updateStatus(label, connected) {
  statusEl.textContent = label;
  statusEl.style.color = connected ? "#34d399" : "#f59e0b";
}

function connectSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${window.location.host}/ws/live`;

  socketConnection = new WebSocket(url);
  socketConnection.binaryType = "arraybuffer";

  socketConnection.onopen = () => {
    isConnected = true;
    updateStatus("Connected", true);
    addLog(`WebSocket connected to ${url}`);
    socketConnection.send(JSON.stringify({ type: "session_start", sample_rate: TARGET_SAMPLE_RATE, client_timestamp: Date.now(), language: "vi-VN" }));
  };

  socketConnection.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      lastPacketEl.textContent = `${event.data.byteLength} bytes`;
      addLog(`Server echoed ${event.data.byteLength} bytes.`);
    }

    if (typeof event.data === "string") {
      addLog(`Server: ${event.data}`);
    }
  };

  socketConnection.onclose = () => {
    isConnected = false;
    updateStatus("Disconnected", false);
    addLog("WebSocket closed.");
  };

  socketConnection.onerror = () => {
    addLog("WebSocket error.");
  };
}

async function startCall() {
  if (isRecording) {
    stopCall();
    return;
  }

  if (!isConnected) {
    connectSocket();
  }

  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: TARGET_SAMPLE_RATE,
      },
    });

    const actualSampleRate = micStream.getAudioTracks()[0]?.getSettings()?.sampleRate || 48000;
    audioContext = new AudioContext({ sampleRate: actualSampleRate });

    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    sampleRateEl.textContent = `${TARGET_SAMPLE_RATE} Hz target`;

    await audioContext.audioWorklet.addModule("./audio_worklet.js");

    sourceNode = audioContext.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioContext, "audio-capture-processor");

    workletNode.port.onmessage = (event) => {
      if (socketConnection && socketConnection.readyState === WebSocket.OPEN) {
        socketConnection.send(event.data);
        lastPacketEl.textContent = `${event.data.byteLength} bytes`;
      }
    };

    sourceNode.connect(workletNode);
    workletNode.connect(audioContext.destination);

    isRecording = true;
    toggleButton.textContent = "Stop call";
    sampleRateEl.textContent = `${audioContext.sampleRate} Hz`;
    addLog(`Microphone started at ${audioContext.sampleRate} Hz. Streaming PCM chunks to /ws/live`);

    const analyser = audioContext.createAnalyser();
    sourceNode.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);

    const tick = () => {
      if (!isRecording) {
        return;
      }
      analyser.getByteTimeDomainData(data);
      let peak = 0;
      for (const value of data) {
        const normalized = Math.abs(value - 128) / 128;
        if (normalized > peak) {
          peak = normalized;
        }
      }
      micMeter.value = Math.min(100, peak * 100);
      requestAnimationFrame(tick);
    };

    tick();
  } catch (error) {
    addLog(`Failed to start microphone: ${error.message}`);
    console.error(error);
    stopCall();
  }
}

function stopCall() {
  isRecording = false;
  toggleButton.textContent = "Start call";

  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }

  if (workletNode) {
    workletNode.disconnect();
    workletNode = null;
  }

  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }

  if (socketConnection && socketConnection.readyState === WebSocket.OPEN) {
    socketConnection.send(JSON.stringify({ type: "session_stop", reason: "user_hangup" }));
  }

  addLog("Microphone stopped.");
}

toggleButton.addEventListener("click", startCall);
connectSocket();
