// TtsManager.js - Enhanced TTS streaming and playback management

/**
 * TTS Manager handles text-to-speech processing, streaming, and playback
 * with support for interruptions and optimized audio quality.
 */
class TtsManager {
  constructor() {
    // Audio elements
    this.audioContext = null;
    this.audioElement = null;
    this.audioSource = null;
    this.gainNode = null;
    this.analyserNode = null;

    // TTS state
    this.isInitialized = false;
    this.isSpeaking = false;
    this.isWaiting = false;
    this.isPaused = false;
    this.abortController = null;

    // Playback tracking
    this.currentText = null;
    this.currentVoice = "nova"; // Default voice
    this.playbackStartTime = null;
    this.playbackEndTime = null;
    this.textQueue = [];

    // Audio analysis
    this.audioLevels = [];
    this.volumeCallback = null;

    // Callbacks
    this.onPlaybackStart = null;
    this.onPlaybackEnd = null;
    this.onPlaybackError = null;
    this.onPlaybackInterrupted = null;
    this.onAudioDataUpdate = null;
  }

  /**
   * Initialize the TTS manager
   */
  async initialize() {
    if (this.isInitialized) return true;

    try {
      // DON'T create audio context here automatically
      // Instead, store a flag that we need to initialize it later
      this.needsInitialization = true;
      this.isInitialized = true; // Mark as initialized even though we'll lazy-load
      return true;
    } catch (error) {
      console.error("Failed to initialize TTS manager:", error);
      return false;
    }
  }

  // Then add a new method:
  async ensureAudioContext() {
    if (!this.audioContext && this.needsInitialization) {
      // Create audio context after user interaction
      this.audioContext = new (window.AudioContext ||
        window.webkitAudioContext)();

      // Create audio element
      this.audioElement = new Audio();
      this.audioElement.autoplay = true; // Auto-play is fine after gesture
      this.audioElement.preload = "auto";

      // Create nodes
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 256;
      this.gainNode = this.audioContext.createGain();

      // Connect audio element to Web Audio API nodes
      this.audioSource = this.audioContext.createMediaElementSource(
        this.audioElement
      );
      this.audioSource.connect(this.analyserNode);
      this.analyserNode.connect(this.gainNode);
      this.gainNode.connect(this.audioContext.destination);

      // Set up event listeners
      this.setupEventListeners();

      this.needsInitialization = false;
      console.log("Audio context initialized after user gesture");
    } else if (this.audioContext && this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
    return !!this.audioContext;
  }

  /**
   * Set up audio element event listeners
   */
  setupEventListeners() {
    const audio = this.audioElement;

    audio.addEventListener("playing", () => {
      console.log("TTS playback started");
      this.isSpeaking = true;
      this.isWaiting = false;
      this.playbackStartTime = Date.now();

      if (this.onPlaybackStart) {
        this.onPlaybackStart(this.currentText);
      }

      // Start volume monitoring
      this.startVolumeMonitoring();
    });

    audio.addEventListener("ended", () => {
      console.log("TTS playback ended naturally");
      this.handlePlaybackEnd();
    });

    audio.addEventListener("pause", () => {
      if (!this.isPaused && this.isSpeaking) {
        console.log("TTS playback paused");
        this.isPaused = true;
      }
    });

    audio.addEventListener("error", (e) => {
      if (audio.error) {
        console.error(
          "TTS playback error:",
          audio.error.code,
          audio.error.message
        );

        if (this.onPlaybackError) {
          this.onPlaybackError({
            code: audio.error.code,
            message: audio.error.message,
            text: this.currentText,
          });
        }
      }

      this.handlePlaybackEnd(true);
    });
  }

  /**
   * Start volume monitoring for visualization
   */
  startVolumeMonitoring() {
    if (!this.analyserNode || !this.isSpeaking) return;

    const bufferLength = this.analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const updateVolume = () => {
      if (!this.isSpeaking) return;

      // Get frequency data
      this.analyserNode.getByteFrequencyData(dataArray);

      // Calculate levels for visualization
      const levels = [];
      const bands = 32; // Number of visualization bands
      const step = Math.floor(bufferLength / bands);

      for (let i = 0; i < bands; i++) {
        const start = i * step;
        let sum = 0;

        for (let j = 0; j < step; j++) {
          sum += dataArray[start + j];
        }

        levels.push(sum / step / 255); // Normalize to 0-1
      }

      this.audioLevels = levels;

      // Calculate overall volume
      let totalVolume = 0;
      for (let i = 0; i < bufferLength; i++) {
        totalVolume += dataArray[i];
      }
      const volume = totalVolume / bufferLength / 255;

      // Call volume callback if set
      if (this.onAudioDataUpdate) {
        this.onAudioDataUpdate({
          volume,
          levels,
          isSpeaking: this.isSpeaking,
          isPaused: this.isPaused,
        });
      }

      // Continue monitoring
      requestAnimationFrame(updateVolume);
    };

    // Start monitoring loop
    updateVolume();
  }

  /**
   * Handle playback end
   */
  handlePlaybackEnd(isError = false) {
    this.isSpeaking = false;
    this.isPaused = false;
    this.playbackEndTime = Date.now();

    // Calculate playback duration
    const duration =
      this.playbackEndTime - (this.playbackStartTime || this.playbackEndTime);

    if (this.onPlaybackEnd) {
      this.onPlaybackEnd({
        text: this.currentText,
        duration,
        isError,
      });
    }

    this.currentText = null;

    // Process next item in queue if any
    if (this.textQueue.length > 0) {
      const next = this.textQueue.shift();
      setTimeout(() => {
        this.speak(next.text, next.voice);
      }, 250); // Small delay between utterances
    }
  }

  /**
   * Speak text using TTS
   */
  async speak(text, voice = null) {
    if (!text || text.trim() === "") return false;

    // If already speaking, queue this text
    if (this.isSpeaking || this.isWaiting) {
      this.textQueue.push({ text, voice: voice || this.currentVoice });
      console.log("Text queued for TTS playback:", text);
      return true;
    }

    try {
      // Initialize if needed
      if (!this.isInitialized) {
        await this.initialize();
      }
      // Ensure audio context is initialized
      await this.ensureAudioContext();

      // Set state
      this.isWaiting = true;
      this.currentText = text;
      this.currentVoice = voice || this.currentVoice;

      // Create abort controller for fetch
      this.abortController = new AbortController();

      // Create URL for streaming
      const url = `/api/speak-stream?text=${encodeURIComponent(
        text
      )}&voice=${encodeURIComponent(this.currentVoice)}`;

      // Start audio context if suspended
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }

      // Set audio source
      this.audioElement.src = url;

      // Load and play
      this.audioElement.load();
      const playPromise = this.audioElement.play();

      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          console.error("TTS playback failed:", error);
          this.isWaiting = false;

          if (this.onPlaybackError) {
            this.onPlaybackError({
              message: error.message,
              text,
            });
          }
        });
      }

      return true;
    } catch (error) {
      console.error("Failed to start TTS playback:", error);
      this.isWaiting = false;

      if (this.onPlaybackError) {
        this.onPlaybackError({
          message: error.message,
          text,
        });
      }

      return false;
    }
  }

  /**
   * Stop current TTS playback
   */
  stop() {
    if (!this.isSpeaking && !this.isWaiting) {
      console.log("TTS stop called, but not currently speaking or waiting");
      return;
    }
    console.log(
      "TTS playback stopping. Was speaking:",
      this.isSpeaking,
      "Was waiting:",
      this.isWaiting
    );

    // Abort any pending fetch
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    // Stop audio
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.currentTime = 0;
    }

    const wasInterrupted = this.isSpeaking;

    // Reset state
    this.isSpeaking = false;
    this.isWaiting = false;
    this.isPaused = false;

    // Trigger interrupted callback
    if (wasInterrupted && this.onPlaybackInterrupted) {
      console.log("Triggering TTS interrupted callback");
      this.onPlaybackInterrupted(this.currentText);
    }

    this.currentText = null;

    // Clear queue
    this.textQueue = [];

    console.log("TTS playback stopped successfully");
  }

  /**
   * Pause TTS playback
   */
  pause() {
    if (!this.isSpeaking) return;

    this.audioElement.pause();
    this.isPaused = true;

    console.log("TTS playback paused");
  }

  /**
   * Resume TTS playback
   */
  resume() {
    if (!this.isPaused) return;

    this.audioElement.play().catch((error) => {
      console.error("Failed to resume TTS playback:", error);
    });

    this.isPaused = false;

    console.log("TTS playback resumed");
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.stop();

    if (this.audioElement) {
      this.audioElement.removeAttribute("src");
      this.audioElement.load();
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
    console.log("TTS manager disposed");
  }
}

// Export singleton instance
const ttsManager = new TtsManager();
export default ttsManager;
