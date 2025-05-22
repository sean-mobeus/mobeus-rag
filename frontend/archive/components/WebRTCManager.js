// WebRTCManager.js - Core WebRTC initialization and management

/**
 * WebRTCManager handles all WebRTC functionality for the voice assistant
 * including audio capture, processing, and echo cancellation.
 */
class WebRTCManager {
  constructor() {
    // Audio context and processing nodes
    this.audioContext = null;
    this.mediaStream = null;
    this.inputNode = null;
    this.processorNode = null;
    this.analyserNode = null;

    // WebRTC constraints for professional-grade audio
    this.audioConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      // Higher sample rate for better voice quality
      sampleRate: 48000,
      // Prioritize voice clarity
      channelCount: 1, // Mono for speech recognition
      // Stable latency for better processing
      latency: 0.01,
    };

    // Audio processing configuration
    this.sampleRate = 48000;
    this.fftSize = 1024;
    this.bufferSize = 4096;

    // Analysis data
    this.audioLevels = [];
    this.frequencyData = new Uint8Array(this.fftSize / 2);
    this.voiceDetected = false;
    this.silenceCounter = 0;
    this.silenceThreshold = 0.05;
    this.silenceThresholdFrames = 10;

    // Event callbacks
    this.onVoiceStart = null;
    this.onVoiceEnd = null;
    this.onAudioProcess = null;
    this.onAudioLevelsUpdate = null;

    // State
    this.isInitialized = false;
    this.isCapturing = false;
    this.isProcessing = false;
  }

  /**
   * Initialize WebRTC and audio context
   */
  async initialize() {
    if (this.isInitialized) return true;

    try {
      // Create audio context
      this.audioContext = new (window.AudioContext ||
        window.webkitAudioContext)({
        sampleRate: this.sampleRate,
        latencyHint: "interactive",
      });

      // Successfully initialized
      this.isInitialized = true;
      console.log(
        "WebRTC Manager initialized with sample rate:",
        this.audioContext.sampleRate
      );
      return true;
    } catch (error) {
      console.error("Failed to initialize WebRTC Manager:", error);
      return false;
    }
  }

  /**
   * Start audio capture with WebRTC
   */
  async startCapture() {
    if (!this.isInitialized) {
      await this.initialize();
    }

    if (this.isCapturing) return true;

    try {
      // Get user media with optimized constraints
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: this.audioConstraints,
        video: false,
      });

      // Create input node from microphone stream
      this.inputNode = this.audioContext.createMediaStreamSource(
        this.mediaStream
      );

      // Create analyzer node for visualizations and voice activity detection
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = this.fftSize;
      this.analyserNode.smoothingTimeConstant = 0.5;

      // Connect input to analyzer
      this.inputNode.connect(this.analyserNode);

      // Set up ScriptProcessorNode for custom processing
      // Note: ScriptProcessorNode is deprecated but still widely used
      // Could be replaced with AudioWorklet for production
      this.processorNode = this.audioContext.createScriptProcessor(
        this.bufferSize,
        1, // Input channels (mono)
        1 // Output channels (mono)
      );

      // Process audio data
      this.processorNode.onaudioprocess = this.handleAudioProcess.bind(this);

      // Connect nodes: input -> analyzer -> processor -> destination
      this.inputNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);

      // Start audio analysis loop
      this.isCapturing = true;
      this.startAnalysis();

      console.log("WebRTC audio capture started");
      return true;
    } catch (error) {
      console.error("Failed to start audio capture:", error);
      return false;
    }
  }

  /**
   * Stop audio capture
   */
  stopCapture() {
    if (!this.isCapturing) return;

    // Disconnect all nodes
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }

    if (this.analyserNode) {
      this.analyserNode.disconnect();
    }

    if (this.inputNode) {
      this.inputNode.disconnect();
      this.inputNode = null;
    }

    // Stop all media tracks
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    // Reset state
    this.isCapturing = false;
    this.isProcessing = false;
    this.voiceDetected = false;
    this.silenceCounter = 0;

    console.log("WebRTC audio capture stopped");
  }

  /**
   * Handle audio processing
   */
  handleAudioProcess(event) {
    if (!this.isCapturing) return;

    // Get input data
    const inputData = event.inputBuffer.getChannelData(0);

    // Calculate RMS (root mean square) for volume
    let rms = 0;
    for (let i = 0; i < inputData.length; i++) {
      rms += inputData[i] * inputData[i];
    }
    rms = Math.sqrt(rms / inputData.length);

    // Voice activity detection
    const voiceDetected = rms > this.silenceThreshold;

    // Count silence frames for end-of-speech detection
    if (!voiceDetected && this.voiceDetected) {
      this.silenceCounter++;

      // If silence persists for enough frames, mark end of voice
      if (this.silenceCounter >= this.silenceThresholdFrames) {
        this.voiceDetected = false;
        this.silenceCounter = 0;

        // Trigger voice end callback
        if (this.onVoiceEnd) {
          this.onVoiceEnd();
        }
      }
    } else if (voiceDetected && !this.voiceDetected) {
      // Voice start detected
      this.voiceDetected = true;
      this.silenceCounter = 0;

      // Trigger voice start callback
      if (this.onVoiceStart) {
        this.onVoiceStart(rms);
      }
    } else if (voiceDetected) {
      // Reset silence counter during active speech
      this.silenceCounter = 0;
    }

    // Pass audio data to callback if registered
    if (this.onAudioProcess) {
      this.onAudioProcess(inputData, rms, this.voiceDetected);
    }
  }

  /**
   * Start audio analysis loop for visualizations
   */
  startAnalysis() {
    if (!this.isCapturing || !this.analyserNode) return;

    // Create analysis loop
    const analyzeAudio = () => {
      if (!this.isCapturing) return;

      // Get frequency data for visualization
      this.analyserNode.getByteFrequencyData(this.frequencyData);

      // Calculate audio levels for visualization (reduce to 64 bands)
      const levels = [];
      const bands = 64;
      const step = Math.floor(this.frequencyData.length / bands);

      for (let i = 0; i < bands; i++) {
        const start = i * step;
        let sum = 0;

        // Average each band
        for (let j = 0; j < step; j++) {
          sum += this.frequencyData[start + j];
        }

        levels.push(sum / step / 255); // Normalize to 0-1
      }

      this.audioLevels = levels;

      // Call visualization update callback
      if (this.onAudioLevelsUpdate) {
        this.onAudioLevelsUpdate(levels, this.voiceDetected);
      }

      // Continue loop
      requestAnimationFrame(analyzeAudio);
    };

    // Start analysis loop
    analyzeAudio();
  }

  /**
   * Check if the system supports WebRTC
   */
  static isSupported() {
    return !!(
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      window.AudioContext
    );
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.stopCapture();

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
  }
}

// Export as singleton
const webRTCManager = new WebRTCManager();
export default webRTCManager;
