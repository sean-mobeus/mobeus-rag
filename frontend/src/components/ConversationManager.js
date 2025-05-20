// ConversationManager.js - Manages conversation state and flow

import speechRecognitionManager from "./SpeechRecognitionManager";
import audioProcessor from "./AudioProcessor";

// ------------ EMERGENCY PATCH START ------------
// Ensure speechRecognitionManager has all required methods
console.log(
  "Applying emergency compatibility patch to speechRecognitionManager"
);

if (speechRecognitionManager) {
  // Check if pauseRecognition is missing
  if (!speechRecognitionManager.pauseRecognition) {
    console.warn(
      "⚠️ speechRecognitionManager.pauseRecognition is missing - adding compatibility method"
    );

    // Add compatibility method
    speechRecognitionManager.pauseRecognition = function () {
      console.log("Using compatibility pauseRecognition method");
      // Just call stop on the recognition object directly
      try {
        if (this.recognition) {
          this.recognition.stop();
          console.log("Recognition paused via compatibility method");
        }
      } catch (e) {
        console.error("Error in compatibility pauseRecognition:", e);
      }
    };
  }

  // Check if restartRecognition is missing
  if (!speechRecognitionManager.restartRecognition) {
    console.warn(
      "⚠️ speechRecognitionManager.restartRecognition is missing - adding compatibility method"
    );

    // Add compatibility method
    speechRecognitionManager.restartRecognition = function () {
      console.log("Using compatibility restartRecognition method");
      const self = this;

      // Set timeout to restart (avoids rapid restart failures)
      setTimeout(() => {
        try {
          if (self.recognition) {
            console.log("Restarting recognition via compatibility method");
            self.recognition.start();
          }
        } catch (e) {
          console.error("Error in compatibility restartRecognition:", e);

          // Try again with longer delay
          setTimeout(() => {
            try {
              if (self.recognition) {
                self.recognition.start();
              }
            } catch (innerError) {
              console.error("Failed second restart attempt:", innerError);
            }
          }, 1000);
        }
      }, 500);
    };
  }
}
// ------------ EMERGENCY PATCH END ------------

/**
 * Conversation Manager handles the overall flow of conversation,
 * user identification, and state transitions between listening and responding.
 */
class ConversationManager {
  constructor() {
    // Conversation state
    this.isInitialized = false;
    this.isProcessingQuery = false;
    this.assistantIsSpeaking = false;
    this.isGreetingComplete = false;
    this.currentQuery = null;
    this.lastResponse = null;
    this.conversationHistory = [];
    this.maxHistoryItems = 20;
    this.interruptionDetected = false;

    // User identification
    this.userName = null;
    this.userIdentified = false;
    this.awaitingUserName = false;

    // Callbacks
    this.onUserMessageReceived = null;
    this.onAssistantMessageReceived = null;
    this.onUserNameIdentified = null;
    this.onInterruptionHandled = null;
    this.onConversationStateChanged = null;
    this.onError = null;
  }

  /**
   * Initialize the conversation manager
   */
  async initialize() {
    if (this.isInitialized) return true;

    try {
      // Load saved user name if available
      this.loadUserName();

      // Initialize speech recognition
      await speechRecognitionManager.initialize();

      // Set up speech recognition callbacks
      speechRecognitionManager.onSpeechStart =
        this.handleSpeechStart.bind(this);
      speechRecognitionManager.onResult = this.handleInterimResult.bind(this);
      speechRecognitionManager.onFinalResult =
        this.handleFinalResult.bind(this);
      speechRecognitionManager.onError = this.handleRecognitionError.bind(this);

      // Set up audio processor callbacks
      audioProcessor.onInterruption = this.handleInterruption.bind(this);

      this.isInitialized = true;
      this.updateConversationState();

      console.log(
        "Conversation manager initialized, user identified:",
        this.userIdentified
      );
      return true;
    } catch (error) {
      console.error("Failed to initialize conversation manager:", error);

      if (this.onError) {
        this.onError("Failed to initialize conversation system", error);
      }

      return false;
    }
  }

  /**
   * Start listening for user input
   */
  async startListening() {
    if (!this.isInitialized) {
      await this.initialize();
    }

    try {
      await speechRecognitionManager.start();

      // If user is not identified, trigger greeting flow
      if (!this.userIdentified && !this.isGreetingComplete) {
        this.startGreetingFlow();
      }

      this.updateConversationState();
      return true;
    } catch (error) {
      console.error("Failed to start listening:", error);

      if (this.onError) {
        this.onError("Failed to start listening", error);
      }

      return false;
    }
  }

  /**
   * Stop listening
   */
  stopListening() {
    speechRecognitionManager.stop();
    this.updateConversationState();
  }

  /**
   * Start the greeting flow to identify the user
   */
  startGreetingFlow() {
    // Skip if already greeted or user is known
    if (this.isGreetingComplete || this.userIdentified) return;

    this.awaitingUserName = true;

    // Add greeting message to conversation
    const greeting = "Hello! I'm Mobeus Assistant. What's your name?";

    this.addAssistantMessage(greeting);
    this.updateConversationState({ isGreeting: true });

    console.log("Started greeting flow, awaiting user name");
  }

  /**
   * Handle speech start event
   */
  handleSpeechStart(volume) {
    // Update conversation state
    this.updateConversationState({ userSpeaking: true });
  }

  /**
   * Handle interim speech result
   */
  handleInterimResult(transcript, isFinal) {
    // We don't need to process this for conversation state
    // It's handled at the UI level for real-time feedback
  }

  /**
   * Handle final speech result
   */
  handleFinalResult(transcript) {
    if (!transcript || transcript.trim().length === 0) return;

    console.log("Final speech result:", transcript);

    // Handle name identification if awaiting name
    if (this.awaitingUserName && !this.userIdentified) {
      this.processNameFromSpeech(transcript);
      return;
    }

    // Add user message to conversation
    this.addUserMessage(transcript);

    // Process the query
    this.processUserQuery(transcript);
  }

  /**
   * Process name from speech during greeting flow
   */
  processNameFromSpeech(transcript) {
    // Skip very short inputs
    if (transcript.length < 2) return;

    // Add user message to conversation
    this.addUserMessage(transcript);

    // Extract name from common patterns
    const namePhrases = [
      { pattern: /my name is (.+)$/i, group: 1 },
      { pattern: /i am (.+)$/i, group: 1 },
      { pattern: /call me (.+)$/i, group: 1 },
      { pattern: /i'm (.+)$/i, group: 1 },
      { pattern: /name's (.+)$/i, group: 1 },
    ];

    let extractedName = "";

    // Try each pattern
    for (const { pattern, group } of namePhrases) {
      const match = transcript.match(pattern);
      if (match && match[group]) {
        // Extract just the first word as the name
        extractedName = match[group].split(/\s+/)[0];
        break;
      }
    }

    if (extractedName) {
      // Format name (capitalize first letter)
      const formattedName =
        extractedName.charAt(0).toUpperCase() +
        extractedName.substring(1).toLowerCase();

      // Set user name
      this.userName = formattedName;
      this.userIdentified = true;
      this.awaitingUserName = false;
      this.isGreetingComplete = true;

      // Save user name
      this.saveUserName(formattedName);

      // Generate welcome message
      const welcomeMessage = `Nice to meet you, ${formattedName}! How can I help you today?`;
      this.addAssistantMessage(welcomeMessage);

      // Trigger callback
      if (this.onUserNameIdentified) {
        this.onUserNameIdentified(formattedName);
      }

      this.updateConversationState();

      console.log("User identified as:", formattedName);
    }
  }

  /**
   * Process user query
   */
  processUserQuery(query) {
    // Skip if already processing or no query
    if (this.isProcessingQuery || !query) return;

    this.isProcessingQuery = true;
    this.currentQuery = query;

    // Update state
    this.updateConversationState();

    // This will be replaced with actual API call in StreamingChatUI
    // Here we just prepare the state
    console.log("Processing user query:", query);
  }

  /**
   * Handle recognition error
   */
  handleRecognitionError(message) {
    console.error("Recognition error:", message);

    if (this.onError) {
      this.onError("Speech recognition error", { message });
    }

    this.updateConversationState();
  }

  /**
   * Handle interruption
   */
  handleInterruption(level) {
    if (!this.assistantIsSpeaking) return;

    console.log("Interruption detected, level:", level);

    this.interruptionDetected = true;

    // Trigger callback
    if (this.onInterruptionHandled) {
      this.onInterruptionHandled(level);
    }

    this.updateConversationState({ interrupted: true });
  }

  /**
   * Set assistant speaking state
   * @param {boolean} isSpeaking - Whether the assistant is speaking
   * @param {string} text - The text being spoken
   */
  setAssistantSpeaking(isSpeaking, text) {
    // Update internal state
    this.assistantIsSpeaking = isSpeaking;

    console.log(
      `ConversationManager: Setting assistant speaking to ${isSpeaking}`
    );

    // Update audio processor state
    if (audioProcessor) {
      audioProcessor.setAssistantSpeaking(isSpeaking, text);
    }

    // Update speech recognition manager state
    if (speechRecognitionManager) {
      try {
        // Use the method we're sure exists through our emergency patch
        speechRecognitionManager.setAssistantSpeaking(isSpeaking, text);
      } catch (error) {
        console.error(
          "Error calling speechRecognitionManager.setAssistantSpeaking:",
          error
        );

        // Fallback to direct method calls if setAssistantSpeaking fails
        if (isSpeaking) {
          try {
            console.log("Using pauseRecognition fallback");
            speechRecognitionManager.pauseRecognition();
          } catch (e) {
            console.error("Error in fallback pauseRecognition:", e);
          }
        } else if (this.isListening) {
          try {
            console.log("Using restartRecognition fallback");
            speechRecognitionManager.restartRecognition();
          } catch (e) {
            console.error("Error in fallback restartRecognition:", e);
          }
        }
      }
    }

    // Notify any listeners
    if (this.onAssistantSpeakingChange) {
      this.onAssistantSpeakingChange(isSpeaking);
    }
  }

  /**
   * Add user message to conversation history
   */
  addUserMessage(text) {
    const message = {
      role: "user",
      text,
      timestamp: new Date().toISOString(),
    };

    this.conversationHistory.push(message);

    // Limit history size
    if (this.conversationHistory.length > this.maxHistoryItems) {
      this.conversationHistory.shift();
    }

    // Trigger callback
    if (this.onUserMessageReceived) {
      this.onUserMessageReceived(message);
    }

    return message;
  }

  /**
   * Add assistant message to conversation history
   */
  addAssistantMessage(text) {
    const message = {
      role: "assistant",
      text,
      timestamp: new Date().toISOString(),
    };

    this.conversationHistory.push(message);

    // Limit history size
    if (this.conversationHistory.length > this.maxHistoryItems) {
      this.conversationHistory.shift();
    }

    // Trigger callback
    if (this.onAssistantMessageReceived) {
      this.onAssistantMessageReceived(message);
    }

    return message;
  }

  /**
   * Save user name to localStorage
   */
  saveUserName(name) {
    try {
      localStorage.setItem("userName", name);
    } catch (e) {
      console.error("Failed to save user name:", e);
    }
  }

  /**
   * Load user name from localStorage
   */
  loadUserName() {
    try {
      const name = localStorage.getItem("userName");
      if (name) {
        this.userName = name;
        this.userIdentified = true;
        console.log("User name loaded from storage:", name);
      }
    } catch (e) {
      console.error("Failed to load user name:", e);
    }
  }

  /**
   * Get the current conversation state
   */
  getConversationState() {
    return {
      isInitialized: this.isInitialized,
      isProcessingQuery: this.isProcessingQuery,
      assistantIsSpeaking: this.assistantIsSpeaking,
      userIdentified: this.userIdentified,
      userName: this.userName,
      awaitingUserName: this.awaitingUserName,
      isGreetingComplete: this.isGreetingComplete,
      currentQuery: this.currentQuery,
      interruptionDetected: this.interruptionDetected,
      conversationHistory: this.conversationHistory,
    };
  }

  /**
   * Update conversation state and notify listeners
   */
  updateConversationState(additionalState = {}) {
    const state = {
      ...this.getConversationState(),
      ...additionalState,
    };

    // Notify listeners
    if (this.onConversationStateChanged) {
      this.onConversationStateChanged(state);
    }

    return state;
  }

  /**
   * Clean up resources
   */
  dispose() {
    speechRecognitionManager.stop();
    speechRecognitionManager.dispose();
  }
}

// Export singleton instance
const conversationManager = new ConversationManager();
export default conversationManager;
