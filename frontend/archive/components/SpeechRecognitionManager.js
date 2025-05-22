// SpeechRecognitionManager.js - Handles recognition with WebRTC integration

import audioProcessor from "./AudioProcessor";

/**
 * Speech Recognition Manager integrates WebRTC audio with speech recognition
 * to provide continuous, high-quality speech-to-text with echo cancellation.
 */
class SpeechRecognitionManager {
  constructor() {
    // Speech recognition
    this.recognition = null;
    this.isListening = false;
    this.isProcessing = false;
    this.isSpeaking = false;
    this.restartTimeout = null;
    this.resultTimeout = null;

    // Recognition config
    this.language = "en-US";
    this.continuous = true;
    this.interimResults = true;
    this.maxAlternatives = 3;

    // Speech processing
    this.currentInterimResult = "";
    this.finalResult = "";
    this.previousResults = [];
    this.resultBuffer = [];
    this.maxBufferSize = 5;

    // Echo detection
    this.assistantSpeaking = false;
    this.assistantUtterances = [];
    this.maxUtterances = 5;

    // Callbacks
    this.onSpeechStart = null;
    this.onResult = null;
    this.onFinalResult = null;
    this.onError = null;
    this.onListeningChange = null;
  }

  /**
   * Initialize speech recognition
   */
  initialize() {
    try {
      // Check if Speech Recognition is supported
      if (
        !("webkitSpeechRecognition" in window) &&
        !("SpeechRecognition" in window)
      ) {
        throw new Error("Speech recognition not supported in this browser");
      }

      // Create recognition instance
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new SpeechRecognition();

      // Configure recognizer
      this.recognition.lang = this.language;
      this.recognition.continuous = this.continuous;
      this.recognition.interimResults = this.interimResults;
      this.recognition.maxAlternatives = this.maxAlternatives;

      // Set up event handlers
      this.setupRecognitionEvents();

      // Initialize audio processor
      return audioProcessor.initialize();
    } catch (error) {
      console.error("Failed to initialize speech recognition:", error);
      throw error;
    }
  }

  /**
   * Set up speech recognition event handlers
   */
  setupRecognitionEvents() {
    if (!this.recognition) return;

    // Start event
    this.recognition.onstart = () => {
      console.log("Speech recognition started");
      this.isListening = true;

      if (this.onListeningChange) {
        this.onListeningChange(true);
      }
    };

    // Result event
    this.recognition.onresult = (event) => {
      const results = event.results;
      const resultIndex = event.resultIndex;

      // Process new results
      for (let i = resultIndex; i < results.length; i++) {
        const result = results[i];
        const transcript = result[0].transcript;

        if (result.isFinal) {
          this.handleFinalResult(transcript);
        } else {
          this.handleInterimResult(transcript);
        }
      }
    };

    // Error event
    this.recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);

      // Handle different error types
      switch (event.error) {
        case "network":
          this.handleError("Network error. Check your connection.");
          break;
        case "not-allowed":
        case "service-not-allowed":
          this.handleError("Microphone access denied. Please allow access.");
          break;
        case "aborted":
          // Usually happens when stopping recognition, no need to report
          break;
        case "no-speech":
          // No speech detected, can restart automatically
          this.restartRecognition();
          break;
        default:
          this.handleError(`Error: ${event.error}`);
      }
    };

    // End event
    this.recognition.onend = () => {
      console.log("Speech recognition ended");
      this.isListening = false;

      if (this.onListeningChange) {
        this.onListeningChange(false);
      }

      // Auto-restart if we're supposed to be listening
      if (this.isProcessing && !this.assistantSpeaking) {
        this.restartRecognition();
      }
    };
  }

  /**
   * Start speech recognition
   */
  async start() {
    if (this.isProcessing) return;

    try {
      this.isProcessing = true;

      // Make sure recognition is initialized
      if (!this.recognition) {
        await this.initialize();
      }

      // Start audio processor first
      audioProcessor.startListening();

      // Set up audio processor callbacks
      audioProcessor.onSpeechStart = (volume) => {
        this.isSpeaking = true;

        // Trigger speech start callback
        if (this.onSpeechStart) {
          this.onSpeechStart(volume);
        }
      };

      audioProcessor.onSpeechEnd = (utterance) => {
        this.isSpeaking = false;

        // Process any final results that may have come in
        if (this.currentInterimResult) {
          this.handleFinalResult(this.currentInterimResult);
          this.currentInterimResult = "";
        }
      };

      audioProcessor.onInterruption = (level) => {
        // If the assistant is interrupted, handle the interruption properly
        if (this.assistantSpeaking) {
          console.log("Interruption detected in SRM, level:", level);

          // Ensure recognition is paused (safety measure)
          this.pauseRecognition();

          // Process any buffered speech
          this.processBufferedSpeech();

          // IMPORTANT ADDITION: Restart recognition after a short delay
          // This ensures we capture what the user is saying after interrupting
          setTimeout(() => {
            if (this.isProcessing) {
              console.log("Restarting recognition after interruption");
              this.restartRecognition();
            }
          }, 100);
        }
      };

      // Start recognition
      this.recognition.start();

      console.log("Speech recognition and audio processing started");
    } catch (error) {
      this.isProcessing = false;
      console.error("Failed to start speech recognition:", error);

      if (this.onError) {
        this.onError(error.message);
      }
    }
  }

  /**
   * Stop speech recognition
   */
  stop() {
    this.isProcessing = false;

    // Clear timeouts
    if (this.restartTimeout) {
      clearTimeout(this.restartTimeout);
      this.restartTimeout = null;
    }

    if (this.resultTimeout) {
      clearTimeout(this.resultTimeout);
      this.resultTimeout = null;
    }

    // Stop recognition
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {
        console.error("Error stopping recognition:", e);
      }
    }

    // Stop audio processor
    audioProcessor.stopListening();

    // Reset state
    this.currentInterimResult = "";
    this.isSpeaking = false;

    console.log("Speech recognition stopped");
  }

  /**
   * Restart recognition after pause or error
   */
  restartRecognition() {
    // Clear existing timeout
    if (this.restartTimeout) {
      clearTimeout(this.restartTimeout);
    }

    // Set timeout to restart (avoids rapid restart failures)
    this.restartTimeout = setTimeout(() => {
      if (this.isProcessing && !this.isListening && !this.assistantSpeaking) {
        try {
          console.log("Restarting speech recognition...");
          this.recognition.start();
        } catch (e) {
          console.error("Failed to restart recognition:", e);

          // Try again with longer delay
          this.restartTimeout = setTimeout(() => {
            if (this.isProcessing) {
              try {
                this.recognition.start();
              } catch (innerError) {
                console.error(
                  "Failed to restart recognition again:",
                  innerError
                );
              }
            }
          }, 1000);
        }
      }
    }, 500);
  }

  /**
   * Handle interim speech recognition result
   */
  handleInterimResult(transcript) {
    if (this.assistantSpeaking) {
      // During assistant speech, buffer interim results
      this.resultBuffer.push(transcript);

      // Limit buffer size
      if (this.resultBuffer.length > this.maxBufferSize) {
        this.resultBuffer.shift();
      }

      return;
    }

    // Update current interim result
    this.currentInterimResult = transcript;

    // Skip if likely an echo
    if (audioProcessor.isLikelyEcho(transcript)) {
      console.log("Filtered echo in interim result:", transcript);
      return;
    }

    // Send interim result to callback
    if (this.onResult) {
      this.onResult(transcript, false);
    }
  }

  /**
   * Handle final speech recognition result
   */
  handleFinalResult(transcript) {
    // Skip if likely an echo
    if (audioProcessor.isLikelyEcho(transcript)) {
      console.log("Filtered echo in final result:", transcript);
      return;
    }

    // Add to processed speech history
    audioProcessor.addProcessedSpeech(transcript);

    // Update history
    this.previousResults.push(transcript);
    if (this.previousResults.length > this.maxBufferSize) {
      this.previousResults.shift();
    }

    // Reset interim result
    this.finalResult = transcript;
    this.currentInterimResult = "";

    // Send final result to callback
    if (this.onFinalResult) {
      this.onFinalResult(transcript);
    }
  }

  /**
   * Process buffered speech (after interruption)
   */
  processBufferedSpeech() {
    if (this.resultBuffer.length === 0) return;

    // Combine buffered results and process as a single utterance
    const combinedTranscript = this.resultBuffer.join(" ").trim();

    if (combinedTranscript.length > 0) {
      // Skip if likely an echo
      if (!audioProcessor.isLikelyEcho(combinedTranscript)) {
        console.log("Processing buffered speech:", combinedTranscript);

        // Send to callback
        if (this.onFinalResult) {
          this.onFinalResult(combinedTranscript);
        }
      }
    }

    // Clear buffer
    this.resultBuffer = [];
  }

  /**
   * Handle recognition error
   */
  handleError(message) {
    console.error("Recognition error:", message);

    if (this.onError) {
      this.onError(message);
    }
  }

  /**
   * Set assistant speaking state
   */
  setAssistantSpeaking(isSpeaking, utterance = null) {
    this.assistantSpeaking = isSpeaking;

    // Update audio processor state
    audioProcessor.setAssistantSpeaking(isSpeaking, utterance);

    if (isSpeaking) {
      // Pause recognition during assistant speech to prevent echo loops
      this.pauseRecognition();
    } else if (utterance) {
      // Add to assistant utterance history for echo detection
      this.assistantUtterances.unshift(utterance);

      // Limit history size
      if (this.assistantUtterances.length > this.maxUtterances) {
        this.assistantUtterances.pop();
      }

      // Restart recognition after pause
      if (this.isProcessing) {
        this.restartRecognition();
      }
    }
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.stop();
    this.recognition = null;
  }

  /**
   * Check if speech recognition is supported
   */
  static isSupported() {
    return !!(
      "webkitSpeechRecognition" in window || "SpeechRecognition" in window
    );
  }
}

// Export singleton instance
const speechRecognitionManager = new SpeechRecognitionManager();
export default speechRecognitionManager;
