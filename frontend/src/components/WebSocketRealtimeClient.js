// Simple EventEmitter implementation for browser
class EventEmitter {
  constructor() {
    this.events = {};
  }

  on(event, listener) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(listener);
  }

  emit(event, ...args) {
    if (this.events[event]) {
      this.events[event].forEach((listener) => listener(...args));
    }
  }

  removeAllListeners() {
    this.events = {};
  }
}

/**
 * WebSocket-based client for OpenAI Realtime API via backend relay
 * Handles audio input/output through the browser while using WebSocket for communication
 */
class WebSocketRealtimeClient extends EventEmitter {
  constructor() {
    super();

    // Connection state
    this.socket = null;
    this.connected = false;
    this.connecting = false;

    // Audio handling
    this.audioContext = null;
    this.mediaRecorder = null;
    this.audioStream = null;
    this.isRecording = false;
    this._startedRecordingOnce = false;
    this._sessionRecordingOK = false;

    // Audio playback queue
    this.audioQueue = [];
    this.isPlaying = false;
    this.nextStartTime = 0;
    // Track current audio source for interruption
    this.currentSource = null;
    // Track all active audio sources and timeouts
    this.activeSources = new Set();
    this.scheduledTimeouts = new Set();

    // User context
    this.userUuid = null;

    // Backend URL
    this.backendUrl = window.location.origin;

    // Tool strategy tracking
    this.currentStrategy = "auto";
    this.strategyChangeCallbacks = [];
  }

  /**
   * Send strategy update to backend
   */
  sendStrategyUpdate(strategy) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("⚠️ Cannot send strategy update - WebSocket not ready");
      return false;
    }

    const strategyMessage = {
      type: "strategy_update",
      strategy: strategy,
      timestamp: new Date().toISOString(),
    };

    this.socket.send(JSON.stringify(strategyMessage));
    this.currentStrategy = strategy;

    console.log(`🎛️ Strategy update sent: ${strategy}`);

    // Notify callbacks
    this.strategyChangeCallbacks.forEach((callback) => {
      try {
        callback(strategy);
      } catch (error) {
        console.error("Error in strategy change callback:", error);
      }
    });

    return true;
  }

  /**
   * Get current strategy
   */
  getCurrentStrategy() {
    return this.currentStrategy;
  }

  /**
   * Register callback for strategy changes
   */
  onStrategyChange(callback) {
    if (typeof callback === "function") {
      this.strategyChangeCallbacks.push(callback);
    }
  }

  /**
   * Remove strategy change callback
   */
  offStrategyChange(callback) {
    const index = this.strategyChangeCallbacks.indexOf(callback);
    if (index > -1) {
      this.strategyChangeCallbacks.splice(index, 1);
    }
  }

  /** Connect to backend websocket */
  async connect(
    userUuid = null,
    instructions = null,
    initialStrategy = "auto"
  ) {
    if (this.connecting || this.connected) return false;

    this.connecting = true;
    this.userUuid = userUuid;
    this.currentStrategy = initialStrategy;

    try {
      // Initialize audio context early
      await this.initializeAudio();

      // Connect to backend WebSocket
      const protocol = this.backendUrl.startsWith("https") ? "wss" : "ws";
      const url = `${protocol}://${
        window.location.host
      }/api/realtime/chat?user_uuid=${encodeURIComponent(
        userUuid || ""
      )}&instructions=${encodeURIComponent(
        instructions || ""
      )}&tool_strategy=${encodeURIComponent(initialStrategy)}`;

      console.log("🔗 Connecting to backend WebSocket:", url);
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        console.log("✅ Connected to backend WebSocket");
        this.connected = true;
        this.connecting = false;
        this.emit("connected");
      };

      this.socket.onerror = (e) => {
        console.error("❌ WebSocket error:", e);
        this.emit("error", e);
      };

      this.socket.onclose = () => {
        console.log("🔌 WebSocket closed");
        this.connected = false;
        this.connecting = false;
        this.emit("disconnected");
      };

      this.socket.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          this.handleRealtimeEvent(msg);
        } catch (err) {
          console.error("❌ Bad realtime message", err);
        }
      };

      return true;
    } catch (error) {
      console.error("❌ Connection failed:", error);
      this.connecting = false;
      throw error;
    }
  }

  /** Initialize audio context and elements */
  async initializeAudio() {
    try {
      // Create audio context with 24kHz to match OpenAI default
      this.audioContext = new (window.AudioContext ||
        window.webkitAudioContext)({
        sampleRate: 24000,
      });

      console.log(
        `🎵 Audio context initialized at ${this.audioContext.sampleRate}Hz`
      );
    } catch (error) {
      console.error("❌ Failed to initialize audio:", error);
      throw error;
    }
  }

  /** Resume audio context after user gesture */
  async resumeAudioContext() {
    if (this.audioContext && this.audioContext.state === "suspended") {
      await this.audioContext.resume();
      console.log("🎧 AudioContext resumed");
    }
  }

  /** Start recording audio from microphone */
  async startRecording() {
    if (this.isRecording || !this.connected) {
      console.log(
        "❌ Cannot start recording - already recording or not connected"
      );
      return false;
    }

    try {
      console.log("🎤 Requesting microphone access...");

      // Get microphone access with settings that match OpenAI expectations
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 24000, // Match OpenAI's expected rate
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      console.log("🎤 Microphone access granted");

      // Create AudioContext source for real-time processing
      const source = this.audioContext.createMediaStreamSource(
        this.audioStream
      );

      // Create ScriptProcessor for real-time audio capture
      const processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      processor.onaudioprocess = (event) => {
        if (this.connected && this.isRecording) {
          const inputBuffer = event.inputBuffer;
          const inputData = inputBuffer.getChannelData(0);
          this.processAudioBuffer(inputData);
        }
      };

      // Connect audio pipeline
      source.connect(processor);
      processor.connect(this.audioContext.destination);

      // Store references for cleanup
      this.audioSource = source;
      this.audioProcessor = processor;
      this.isRecording = true;

      console.log("🎤 Started recording successfully");
      this.emit("recording.started");
      return true;
    } catch (error) {
      console.error("❌ Failed to start recording:", error);
      this.emit("error", error);
      return false;
    }
  }

  /** Process audio buffer and convert to PCM16 for OpenAI */
  processAudioBuffer(float32Data) {
    // Convert Float32 to PCM16 as expected by OpenAI
    const pcm16 = new Int16Array(float32Data.length);
    for (let i = 0; i < float32Data.length; i++) {
      // Clamp to [-1, 1] and convert to 16-bit integer
      const sample = Math.max(-1, Math.min(1, float32Data[i]));
      pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }

    // Convert to base64 for transmission
    const pcmBytes = new Uint8Array(pcm16.buffer);
    const base64Audio = btoa(String.fromCharCode(...pcmBytes));

    // Send to OpenAI via backend
    this.sendEvent({
      type: "input_audio_buffer.append",
      audio: base64Audio,
    });
  }

  /** Stop recording audio */
  stopRecording() {
    if (!this.isRecording) return;

    // Disconnect audio pipeline
    if (this.audioSource) {
      this.audioSource.disconnect();
      this.audioSource = null;
    }

    if (this.audioProcessor) {
      this.audioProcessor.disconnect();
      this.audioProcessor = null;
    }

    // Stop media stream
    if (this.audioStream) {
      this.audioStream.getTracks().forEach((track) => track.stop());
      this.audioStream = null;
    }

    this.isRecording = false;
    console.log("🔇 Stopped recording");
    this.emit("recording.stopped");
  }

  /** Send event to backend */
  sendEvent(event) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(event));
      return true;
    }
    console.warn("⚠️ WebSocket not ready", event);
    return false;
  }

  /** Send user text */
  sendText(text) {
    // Send user message with correct content type
    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    });
    this.sendEvent({
      type: "response.create",
      response: { modalities: ["text", "audio"] },
    });
  }

  /** Cancel current response - IMPROVED VERSION */
  cancelResponse() {
    console.log("🛑 Cancelling response and clearing audio");

    // Request cancellation of current LLM response
    this.sendEvent({ type: "response.cancel" });

    // Stop ALL active audio sources immediately
    this.activeSources.forEach((source) => {
      try {
        source.stop();
      } catch (e) {
        // Source might already be stopped, ignore error
      }
    });
    this.activeSources.clear();

    // Clear current source reference
    this.currentSource = null;

    // Cancel all scheduled timeouts
    this.scheduledTimeouts.forEach((timeoutId) => {
      clearTimeout(timeoutId);
    });
    this.scheduledTimeouts.clear();

    // Clear audio queue completely
    this.audioQueue = [];
    this.isPlaying = false;
    this.nextStartTime = 0;

    console.log("✅ Audio playback cancelled and queue cleared");
  }

  /** Disconnect */
  disconnect() {
    this.stopRecording();

    if (this.socket) {
      this.socket.close();
    }

    // Cancel any ongoing audio playback
    this.cancelResponse();

    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.connected = false;
    this.connecting = false;
    // Reset recording state so we can start recording on next session
    this._startedRecordingOnce = false;
  }

  /** Check connection status */
  isConnected() {
    return this.connected;
  }

  /** Get status */
  getStatus() {
    return {
      connected: this.connected,
      connecting: this.connecting,
      recording: this.isRecording,
    };
  }

  /** Handle events from backend/OpenAI */
  handleRealtimeEvent(event) {
    const { type } = event;
    console.log("📨 Received event:", type);

    // Handle strategy-related events
    if (type === "strategy_updated") {
      console.log("🎛️ Strategy update confirmed:", event.strategy);
      this.currentStrategy = event.strategy;
      this.emit("strategy.updated", event);
      // Notify callbacks
      this.strategyChangeCallbacks.forEach((callback) => {
        try {
          callback(event.strategy);
        } catch (error) {
          console.error("Error in strategy change callback:", error);
        }
      });
      return;
    }

    switch (type) {
      case "session.created":
        console.log("🎯 Session created");
        this.emit("session.created", event.session);

        // only the first time…
        if (!this._startedRecordingOnce) {
          this._startedRecordingOnce = true;
          console.log("🔔 First session.created — startRecording()");
          this.startRecording();
        }
        break;

      case "session.updated":
        console.log("🔧 Session updated");
        this.emit("session.updated", event);
        break;

      case "response.text.delta":
        this.emit("response.text.delta", event.text);
        break;

      case "response.audio.delta":
        console.log("🔊 Got audio delta chunk");
        this.queueAudioChunk(event.audio || event.delta);
        this.emit("response.audio.delta", event);
        break;

      case "response.audio_transcript.delta":
        // Handle AI speech transcripts for display
        this.emit("response.text.delta", event.text || event.delta || "");
        break;

      case "response.text.done":
        this.emit("response.text.done", event.text);
        this.emit("message.completed", { role: "assistant", text: event.text });
        break;

      case "strategy_update_broadcast":
        console.log("🎛️ Strategy update broadcast received:", event.strategy);
        this.currentStrategy = event.strategy;
        this.emit("strategy.updated", event);

        // Send confirmation back to backend
        this.sendEvent({
          type: "strategy_update",
          strategy: event.strategy,
          source: "dashboard_broadcast",
        });
        break;

      case "response.audio.done":
        console.log("🔊 Audio response complete");
        this.emit("response.audio.done");
        break;

      case "response.audio_transcript.done":
        // Complete transcript of what AI said
        if (event.transcript) {
          this.emit("message.completed", {
            role: "assistant",
            text: event.transcript,
          });
        }
        break;

      case "input_audio_buffer.speech_started":
        console.log("🎤 Speech started - INTERRUPTING ASSISTANT");
        // CRITICAL FIX: Cancel current response when user starts speaking
        this.cancelResponse();
        this.emit("speech.started");
        break;

      case "input_audio_buffer.speech_stopped":
        console.log("🔇 Speech stopped");
        this.emit("speech.stopped");
        break;

      case "input_audio_buffer.committed":
        console.log("📝 Audio buffer committed");
        this.emit("audio.committed");
        break;

      case "conversation.item.input_audio_transcription.completed":
        const transcript = event.transcript || "";
        if (transcript) {
          console.log("📝 User transcript:", transcript);
          this.emit("message.completed", {
            role: "user",
            text: transcript.replace(/\n$/, ""),
          });
        }
        break;

      case "conversation.item.created":
        console.log("💬 Conversation item created:", event.item?.type);
        if (event.item && event.item.role && event.item.content) {
          let text = "";
          for (const contentItem of event.item.content) {
            // Handle plain text
            if (
              contentItem.type === "text" ||
              contentItem.type === "input_text"
            ) {
              text = contentItem.text || "";
              break;
            }
            // Handle audio transcription of user speech
            if (contentItem.type === "input_audio" && contentItem.transcript) {
              text = contentItem.transcript;
              break;
            }
          }
          if (text) {
            this.emit("message.completed", {
              role: event.item.role,
              text: text,
            });
          }
        }
        break;

      case "response.created":
        console.log("🔄 Response created");
        this.emit("response.created", event);
        break;

      case "response.done":
        console.log("✅ Response done");
        this.emit("response.done", event);
        break;

      case "error":
        // Suppress non-critical errors
        if (
          event.error &&
          (event.error.code === "conversation_already_has_active_response" ||
            event.error.code === "response_cancel_not_active")
        ) {
          console.warn("⚠️ Ignoring non-critical error:", event.error.code);
          break;
        }
        console.error("❌ OpenAI error:", event.error);
        this.emit("error", event.error);
        break;

      default:
        console.log("📨 Unhandled event:", type);
        this.emit(type, event);
        break;
    }
  }

  /**
   * Tool Strategy Presets
   */

  static TOOL_STRATEGIES = {
    auto: {
      label: "Auto",
      color: "blue",
      description: "Let AI decide when to use tools (balanced approach)",
    },
    conservative: {
      label: "Minimal",
      color: "green",
      description: "Prefer direct responses, minimal tool usage",
    },
    aggressive: {
      label: "Comprehensive",
      color: "purple",
      description: "Proactive tool usage for detailed responses",
    },
    none: {
      label: "Direct Only",
      color: "gray",
      description: "Never use tools, direct responses only",
    },
    required: {
      label: "Always Search",
      color: "red",
      description: "Always use tools before responding",
    },
  };

  /**
   * Get strategy information
   */
  getStrategyInfo(strategy) {
    return WebSocketRealtimeClient.TOOL_STRATEGIES[strategy] || null;
  }

  /**
   * Get available strategies
   */
  getAvailableStrategies() {
    return WebSocketRealtimeClient.TOOL_STRATEGIES;
  }

  /** Queue audio chunk for smooth playback */
  queueAudioChunk(base64Audio) {
    if (!base64Audio || !this.audioContext) return;

    try {
      // Decode base64 to get PCM16 data
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert PCM16 to Float32 for AudioContext
      const pcm16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768.0; // Convert to [-1, 1] range
      }

      // Apply gentle fade-in/fade-out to reduce crackling
      const fadeLength = Math.min(64, float32.length / 4); // Small fade
      for (let i = 0; i < fadeLength; i++) {
        const fadeIn = i / fadeLength;
        const fadeOut = (fadeLength - i) / fadeLength;
        float32[i] *= fadeIn; // Fade in
        float32[float32.length - 1 - i] *= fadeOut; // Fade out
      }

      // Create AudioBuffer
      const audioBuffer = this.audioContext.createBuffer(
        1, // mono
        float32.length,
        this.audioContext.sampleRate
      );

      audioBuffer.copyToChannel(float32, 0);

      // Add to queue
      this.audioQueue.push(audioBuffer);

      // Start playing if not already playing
      if (!this.isPlaying) {
        this.playNextAudioChunk();
      }

      console.log(`🔊 Queued audio chunk: ${float32.length} samples`);
    } catch (error) {
      console.error("❌ Failed to queue audio chunk:", error);
    }
  }

  /** Play the next audio chunk in queue - IMPROVED VERSION */
  playNextAudioChunk() {
    if (this.audioQueue.length === 0) {
      this.isPlaying = false;
      this.nextStartTime = 0; // Reset timing
      return;
    }

    this.isPlaying = true;
    const audioBuffer = this.audioQueue.shift();

    const source = this.audioContext.createBufferSource();
    // Track current playing source for interruption
    this.currentSource = source;
    // Track all active sources
    this.activeSources.add(source);

    source.buffer = audioBuffer;

    // Add a gain node for smoother transitions
    const gainNode = this.audioContext.createGain();
    source.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    // Calculate precise timing
    const currentTime = this.audioContext.currentTime;
    const startTime = Math.max(currentTime + 0.005, this.nextStartTime);

    // Gentle gain ramp to avoid clicks
    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(1, startTime + 0.002);
    gainNode.gain.setValueAtTime(1, startTime + audioBuffer.duration - 0.002);
    gainNode.gain.linearRampToValueAtTime(0, startTime + audioBuffer.duration);

    // Remove from active sources when done
    source.onended = () => {
      this.activeSources.delete(source);
    };

    source.start(startTime);

    // Perfect timing for next chunk (no overlap needed with fading)
    this.nextStartTime = startTime + audioBuffer.duration - 0.002;

    // Schedule next chunk with improved timeout tracking
    const timeUntilNext = (this.nextStartTime - currentTime - 0.05) * 1000;
    const timeoutId = setTimeout(() => {
      this.scheduledTimeouts.delete(timeoutId);
      this.playNextAudioChunk();
    }, Math.max(0, timeUntilNext));

    // Track timeout so it can be cancelled during interruption
    this.scheduledTimeouts.add(timeoutId);

    console.log(
      `🔊 Playing audio chunk: ${
        audioBuffer.length
      } samples at ${startTime.toFixed(3)}s`
    );
  }
}

export default new WebSocketRealtimeClient();
