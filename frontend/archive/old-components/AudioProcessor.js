// AudioProcessor.js - Advanced audio signal processing and speech features

import webRTCManager from "./WebRTCManager";

/**
 * AudioProcessor handles advanced signal processing tasks
 * including speech detection, feature extraction, and interruption detection.
 */
class AudioProcessor {
  constructor() {
    // Speech processing configuration
    this.vadThreshold = 0.08; // Voice activity detection threshold
    this.interruptionThreshold = 0.15; // Interruption detection threshold

    // Speech state tracking
    this.isSpeaking = false; // User is currently speaking
    this.isListening = false; // System is actively listening
    this.interruptionDetected = false; // Interruption was detected
    this.continuousSpeechFrames = 0; // Count of continuous speech frames
    this.requiredSpeechFrames = 3; // Frames required to confirm speech
    this.silenceFrames = 0; // Count of silence frames
    this.silenceTimeout = 15; // Frames of silence to end speech
    this.interruptionCounter = 0; // Counter for potential interruptions
    this.requiredInterruptionFrames = 5; // Frames required to confirm interruption

    // Assistant state tracking
    this.assistantIsSpeaking = false; // Assistant is speaking
    this.assistantSpeechBuffer = []; // Recent assistant speech for echo detection
    this.maxAssistantBufferSize = 5; // Number of assistant responses to remember

    // User speech processing
    this.currentUtterance = []; // Buffer of current audio segments
    this.recentUtterances = []; // Recently processed utterances
    this.maxUtterances = 5; // Number of utterances to remember

    // Echo detection
    this.lastProcessedSpeech = null; // Last speech we processed
    this.echoThreshold = 0.7; // Echo detection similarity threshold

    // Callbacks
    this.onSpeechStart = null; // Speech start detected
    this.onSpeechEnd = null; // Speech end detected
    this.onInterruption = null; // User interrupted assistant
    this.onVolumeUpdate = null; // Real-time volume updates
    this.onEchoDetected = null; // Echo detected
  }

  /**
   * Initialize the audio processor
   */
  async initialize() {
    if (!webRTCManager.isInitialized) {
      await webRTCManager.initialize();
    }

    // Set up WebRTC Manager callbacks
    webRTCManager.onVoiceStart = this.handleVoiceStart.bind(this);
    webRTCManager.onVoiceEnd = this.handleVoiceEnd.bind(this);
    webRTCManager.onAudioProcess = this.processAudio.bind(this);
    webRTCManager.onAudioLevelsUpdate = (levels, isActive) => {
      if (this.onVolumeUpdate) {
        // Calculate single volume value (0-1)
        const volume =
          levels.reduce((sum, level) => sum + level, 0) / levels.length;
        this.onVolumeUpdate(volume, isActive);
      }
    };

    return true;
  }

  /**
   * Start listening for speech
   */
  async startListening() {
    if (this.isListening) return true;

    if (!webRTCManager.isInitialized) {
      await this.initialize();
    }

    // Start WebRTC audio capture
    await webRTCManager.startCapture();

    // Reset state
    this.isListening = true;
    this.currentUtterance = [];
    this.continuousSpeechFrames = 0;
    this.silenceFrames = 0;

    console.log("Audio processor started listening");
    return true;
  }

  /**
   * Stop listening for speech
   */
  stopListening() {
    if (!this.isListening) return;

    // Stop WebRTC capture
    webRTCManager.stopCapture();

    // Reset state
    this.isListening = false;
    this.isSpeaking = false;
    this.currentUtterance = [];

    console.log("Audio processor stopped listening");
  }

  /**
   * Handle voice start event from WebRTC Manager
   */
  handleVoiceStart(volume) {
    if (!this.isListening) return;

    // Increment continuous speech frames counter
    this.continuousSpeechFrames++;

    // Only trigger speech start after enough continuous frames
    if (
      this.continuousSpeechFrames >= this.requiredSpeechFrames &&
      !this.isSpeaking
    ) {
      this.isSpeaking = true;

      // Check for interruption if assistant is speaking
      if (this.assistantIsSpeaking) {
        this.interruptionCounter++;

        // Confirm interruption after enough frames
        if (
          this.interruptionCounter >= this.requiredInterruptionFrames &&
          !this.interruptionDetected
        ) {
          this.interruptionDetected = true;

          console.log("Interruption detected!", volume);

          // Trigger interruption callback
          if (this.onInterruption) {
            this.onInterruption(volume);
          }
        }
      } else {
        // Reset interruption state if assistant isn't speaking
        this.interruptionDetected = false;
        this.interruptionCounter = 0;
      }

      // Trigger speech start callback
      if (this.onSpeechStart) {
        this.onSpeechStart(volume);
      }

      console.log("Speech started, volume:", volume);
    }
  }

  /**
   * Handle voice end event from WebRTC Manager
   */
  handleVoiceEnd() {
    if (!this.isListening || !this.isSpeaking) return;

    // Increment silence frames counter
    this.silenceFrames++;

    // End speech after enough silence frames
    if (this.silenceFrames >= this.silenceTimeout) {
      // Process the complete utterance
      const utterance = this.currentUtterance.join("");

      // Reset state
      this.isSpeaking = false;
      this.continuousSpeechFrames = 0;
      this.silenceFrames = 0;
      this.currentUtterance = [];

      // Reset interruption detection
      if (this.interruptionDetected) {
        this.interruptionDetected = false;
        this.interruptionCounter = 0;
      }

      // Trigger speech end callback
      if (this.onSpeechEnd) {
        this.onSpeechEnd(utterance);
      }

      console.log("Speech ended");
    }
  }

  /**
   * Process audio data from WebRTC Manager
   */
  processAudio(audioData, volume, isActive) {
    if (!this.isListening) return;

    // Reset silence counter if we hear sound
    if (isActive) {
      this.silenceFrames = 0;
    }

    // Check for interruption during assistant speech
    if (this.assistantIsSpeaking && isActive) {
      // More aggressive interruption detection
      if (volume > this.interruptionThreshold) {
        this.interruptionCounter++;

        // Add debug logging
        if (this.interruptionCounter === 1) {
          console.log(
            `⚠️ Potential interruption. Volume: ${volume.toFixed(
              2
            )}, Threshold: ${this.interruptionThreshold}`
          );
        }

        // Log progress
        if (this.interruptionCounter % 2 === 0) {
          console.log(
            `🔊 Interruption build-up: ${this.interruptionCounter}/${this.requiredInterruptionFrames}`
          );
        }

        if (
          this.interruptionCounter >= this.requiredInterruptionFrames &&
          !this.interruptionDetected
        ) {
          this.interruptionDetected = true;
          console.log(
            `🚨 INTERRUPTION CONFIRMED! Volume: ${volume.toFixed(2)}`
          );

          if (this.onInterruption) {
            this.onInterruption(volume);
          }
        }
      } else {
        // Decay counter slowly instead of resetting immediately (allows for slight volume dips)
        if (this.interruptionCounter > 0) {
          this.interruptionCounter--;
        }
      }
    } else if (this.interruptionCounter > 0) {
      // Reset counter when assistant isn't speaking
      this.interruptionCounter = 0;
    }
  }

  /**
   * Set assistant speaking state and update echo detection
   */
  setAssistantSpeaking(isSpeaking, text = null) {
    this.assistantIsSpeaking = isSpeaking;

    // Add to speech buffer for echo detection
    if (!isSpeaking && text) {
      this.assistantSpeechBuffer.unshift(text);

      // Limit buffer size
      if (this.assistantSpeechBuffer.length > this.maxAssistantBufferSize) {
        this.assistantSpeechBuffer.pop();
      }
    }

    // Reset interruption state when assistant starts speaking
    if (isSpeaking) {
      this.interruptionDetected = false;
      this.interruptionCounter = 0;
    }
  }

  /**
   * Check if a transcript is likely an echo of the assistant
   */
  isLikelyEcho(transcript) {
    if (
      !transcript ||
      typeof transcript !== "string" ||
      transcript.trim().length === 0
    )
      return false;

    // Clean and normalize text for comparison
    const normalizedTranscript = transcript.toLowerCase().trim();

    // Skip very short transcripts (less likely to be meaningful)
    if (normalizedTranscript.length < 5) return false;

    // Check against recent assistant responses
    for (const assistantText of this.assistantSpeechBuffer) {
      const normalizedAssistantText = assistantText.toLowerCase();

      // Direct substring match (transcript appears in assistant text)
      if (normalizedAssistantText.includes(normalizedTranscript)) {
        if (this.onEchoDetected) {
          this.onEchoDetected(transcript, assistantText);
        }
        return true;
      }

      // Check word-level similarity for partial matches
      const transcriptWords = normalizedTranscript.split(/\s+/);
      const assistantWords = normalizedAssistantText.split(/\s+/);

      // Calculate Jaccard similarity or similar metric
      const wordSet = new Set([...transcriptWords, ...assistantWords]);
      const intersection = transcriptWords.filter((word) =>
        assistantWords.includes(word)
      );

      // Weighted similarity score based on transcript length
      const weightedScore =
        (intersection.length / transcriptWords.length) *
        (1.5 - Math.min(1, transcriptWords.length / 10));

      if (weightedScore > this.echoThreshold) {
        if (this.onEchoDetected) {
          this.onEchoDetected(transcript, assistantText);
        }
        return true;
      }
    }

    return false;
  }

  /**
   * Add a processed transcript to history
   */
  addProcessedSpeech(transcript) {
    if (!transcript || transcript.trim().length === 0) return;

    this.lastProcessedSpeech = transcript;
    this.recentUtterances.unshift(transcript);

    // Limit history size
    if (this.recentUtterances.length > this.maxUtterances) {
      this.recentUtterances.pop();
    }
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.stopListening();
  }

  /**
   * Check if WebRTC and audio processing are supported
   */
  static isSupported() {
    // Delegate to WebRTCManager's support check via its constructor
    return webRTCManager.constructor.isSupported();
  }
}

// Export singleton instance
const audioProcessor = new AudioProcessor();
export default audioProcessor;
