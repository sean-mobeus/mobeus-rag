import React, { useState, useEffect, useRef } from "react";
import MicrophoneComponent from "./MicrophoneComponent";
import conversationManager from "./ConversationManager";
import speechRecognitionManager from "./SpeechRecognitionManager";
import ttsManager from "./TtsManager";
import audioProcessor from "./AudioProcessor";
import apiAdapter from "./ApiAdapter"; // Reusing your existing API adapter

/**
 * WebRTC Voice Assistant - Main component that integrates all WebRTC audio capabilities
 * with conversation flow, speech recognition, and TTS output.
 */
export default function WebRTCVoiceAssistant() {
  // State
  const [initialized, setInitialized] = useState(false);
  const [chat, setChat] = useState([]);
  const [interimText, setInterimText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [userName, setUserName] = useState("");
  const [errorMessage, setErrorMessage] = useState(null);
  const [metrics, setMetrics] = useState({});
  const [processingQuery, setProcessingQuery] = useState(false);
  const [interrupted, setInterrupted] = useState(false);
  const [audioLevels, setAudioLevels] = useState([]);

  // Refs for stable references
  const abortControllerRef = useRef(null);
  const isInitializedRef = useRef(false);
  const currentResponseRef = useRef("");

  // Initialize on component mount
  useEffect(() => {
    const initializeSystems = async () => {
      try {
        setErrorMessage(null);

        // Skip if already initialized
        if (isInitializedRef.current) return;

        console.log("Initializing WebRTC Voice Assistant...");

        // Initialize conversation manager
        await conversationManager.initialize();

        // Set up callbacks
        conversationManager.onUserMessageReceived = handleUserMessage;
        conversationManager.onAssistantMessageReceived = handleAssistantMessage;
        conversationManager.onUserNameIdentified = handleUserIdentified;
        conversationManager.onInterruptionHandled = handleInterruption;
        conversationManager.onError = (error) => {
          console.error("Conversation error:", error);
          setErrorMessage(error?.message || "Conversation error");
        };

        // Set up TTS manager callbacks
        ttsManager.onPlaybackStart = handleTtsStart;
        ttsManager.onPlaybackEnd = handleTtsEnd;
        ttsManager.onPlaybackError = handleTtsError;
        ttsManager.onPlaybackInterrupted = handleTtsInterrupted;
        ttsManager.onAudioDataUpdate = handleTtsAudioData;

        // Set up speech recognition callbacks
        speechRecognitionManager.onResult = handleSpeechResult;
        // Handle final (user) speech transcripts
        speechRecognitionManager.onFinalResult = handleSpeechEnd;
        // Handle recognition errors
        speechRecognitionManager.onError = (message) => {
          console.error("Speech recognition error:", message);
          setErrorMessage(message);
        };

        // Check for stored user name
        const state = conversationManager.getConversationState();
        if (state.userName) {
          setUserName(state.userName);
        }

        // Load initial messages if available
        if (state.conversationHistory && state.conversationHistory.length > 0) {
          setChat(state.conversationHistory);
        }

        isInitializedRef.current = true;
        setInitialized(true);

        console.log(
          "WebRTC Voice Assistant initialized - waiting for user interaction"
        );

        // DON'T auto-start here - wait for user click
      } catch (error) {
        console.error("Failed to initialize voice assistant:", error);
        setErrorMessage("Failed to initialize voice assistant");
      }
    };

    initializeSystems();

    // Clean up on unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      ttsManager.dispose();
      speechRecognitionManager.dispose();
      conversationManager.dispose();
    };
  }, []);

  // Start the assistant
  const startAssistant = async () => {
    try {
      if (!initialized) {
        await conversationManager.initialize();
        setInitialized(true);
      }

      await conversationManager.startListening();
      setIsListening(true);

      // Start greeting flow if needed
      const state = conversationManager.getConversationState();
      if (!state.isGreetingComplete && !state.userIdentified) {
        conversationManager.startGreetingFlow();
      }
    } catch (error) {
      console.error("Failed to start assistant:", error);
      setErrorMessage("Failed to start assistant");
    }
  };

  // Stop the assistant
  const stopAssistant = () => {
    conversationManager.stopListening();
    setIsListening(false);

    if (isSpeaking) {
      ttsManager.stop();
      setIsSpeaking(false);
    }
  };

  // Handle user messages
  const handleUserMessage = (message) => {
    setChat((prev) => [...prev, message]);
    setInterimText("");
  };

  // Handle assistant messages
  const handleAssistantMessage = (message) => {
    setChat((prev) => [...prev, message]);

    // Speak assistant message
    ttsManager.speak(message.text);
  };

  // Handle user identification
  const handleUserIdentified = (name) => {
    setUserName(name);
  };

  // Handle speech recognition results
  const handleSpeechResult = (transcript, isFinal) => {
    if (!isFinal) {
      setInterimText(transcript);
    } else {
      setInterimText("");
    }
  };

  // Handle interruption
  const handleInterruption = (level) => {
    console.log("Handling interruption in WebRTCVoiceAssistant, level:", level);

    // Set UI state
    setInterrupted(true);

    // IMPORTANT: Stop current TTS immediately
    ttsManager.stop();

    // Abort any ongoing API requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Update UI to show interruption
    setChat((prev) => {
      const updatedChat = [...prev];
      // Find the last assistant message
      for (let i = updatedChat.length - 1; i >= 0; i--) {
        if (updatedChat[i].role === "assistant") {
          // Mark as interrupted
          updatedChat[i] = {
            ...updatedChat[i],
            interrupted: true,
          };
          break;
        }
      }
      return updatedChat;
    });

    // ENSURE recognition is restarted to capture what user said
    // This is a backup call in case the SpeechRecognitionManager doesn't do it
    speechRecognitionManager.restartRecognition();

    // Reset interruption state after a delay
    setTimeout(() => {
      setInterrupted(false);
    }, 1000);
  };

  // Handle TTS playback start
  const handleTtsStart = (text) => {
    setIsSpeaking(true);
    conversationManager.setAssistantSpeaking(true, text);
  };

  // Handle TTS playback end
  const handleTtsEnd = ({ text, duration }) => {
    setIsSpeaking(false);
    conversationManager.setAssistantSpeaking(false, text);
  };

  // Handle TTS playback error
  const handleTtsError = (errorInfo) => {
    console.error("TTS playback error:", errorInfo);
    setIsSpeaking(false);
    setErrorMessage(errorInfo?.message || "TTS playback error");
    conversationManager.setAssistantSpeaking(false, errorInfo?.text || "");
  };

  // Handle TTS playback interrupted
  const handleTtsInterrupted = (text) => {
    console.log("TTS playback interrupted for text:", text);
    setIsSpeaking(false);
    conversationManager.setAssistantSpeaking(false, text);
  };

  // Handle TTS audio data updates for visualization
  const handleTtsAudioData = ({ levels }) => {
    setAudioLevels(levels || []);
  };

  // Process user query through ConversationManager and API
  const processQuery = async (query) => {
    if (!query || processingQuery) return;

    try {
      console.log("Processing query with API:", query);
      setProcessingQuery(true);

      // Create abort controller for this request
      abortControllerRef.current = new AbortController();

      // Add assistant placeholder for streaming response
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "",
          timestamp: new Date().toISOString(),
          isStreaming: true,
        },
      ]);

      // Make sure we have the UUID
      const uuid = localStorage.getItem("uuid") || crypto.randomUUID();
      if (!localStorage.getItem("uuid")) {
        localStorage.setItem("uuid", uuid);
      }

      // Prepare request
      const extraData = userName ? { userName } : {};

      console.log("Making API call with params:", {
        query,
        uuid,
        ...extraData,
      });

      // Use API adapter to send the query
      const response = await apiAdapter.sendQuery(query, {
        streaming: true,
        allowFallback: true,
        extraData: {
          ...extraData,
          uuid, // Make sure UUID is included
        },
        signal: abortControllerRef.current.signal,
      });

      console.log("Got API response:", response);

      // Process streaming response
      const reader = response.body.getReader();
      let decoder = new TextDecoder();
      let buffer = "";
      let fullResponse = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Handle non-streaming response
        if (buffer.startsWith("{") && !buffer.includes("data:")) {
          try {
            const jsonResponse = JSON.parse(buffer);
            fullResponse =
              jsonResponse.response ||
              jsonResponse.text ||
              jsonResponse.answer ||
              "Sorry, I couldn't process that request.";

            // Update chat with final response
            setChat((prev) => {
              const updatedChat = [...prev];
              const lastIndex = updatedChat.length - 1;

              if (lastIndex >= 0 && updatedChat[lastIndex].isStreaming) {
                updatedChat[lastIndex] = {
                  ...updatedChat[lastIndex],
                  text: fullResponse,
                  isStreaming: false,
                };
              }

              return updatedChat;
            });

            // Store for interruption reference
            currentResponseRef.current = fullResponse;

            // Speak the response
            ttsManager.speak(fullResponse);

            break;
          } catch (e) {
            console.error("Error parsing non-streaming response:", e);
          }
        } else {
          // Handle streaming response (SSE)
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.chunk) {
                  fullResponse += data.chunk;

                  // Update chat with streaming chunk
                  setChat((prev) => {
                    const updatedChat = [...prev];
                    const lastIndex = updatedChat.length - 1;

                    if (lastIndex >= 0 && updatedChat[lastIndex].isStreaming) {
                      updatedChat[lastIndex] = {
                        ...updatedChat[lastIndex],
                        text: fullResponse,
                      };
                    }

                    return updatedChat;
                  });

                  // Store for interruption reference
                  currentResponseRef.current = fullResponse;
                }

                if (data.timings) {
                  setMetrics(data.timings);
                }

                if (data.done) {
                  // Finalize response in UI
                  setChat((prev) => {
                    const updatedChat = [...prev];
                    const lastIndex = updatedChat.length - 1;
                    if (lastIndex >= 0 && updatedChat[lastIndex].isStreaming) {
                      updatedChat[lastIndex] = {
                        ...updatedChat[lastIndex],
                        text: fullResponse,
                        isStreaming: false,
                      };
                    }
                    return updatedChat;
                  });
                  // Speak the full response
                  ttsManager.speak(fullResponse);
                }
              } catch (e) {
                console.error("Error parsing streaming chunk:", e);
              }
            }
          }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") {
        console.log("Request aborted due to interruption");
      } else {
        console.error("Error processing query:", err);

        // Show error in chat
        setChat((prev) => {
          const updatedChat = [...prev];
          const lastIndex = updatedChat.length - 1;

          if (lastIndex >= 0 && updatedChat[lastIndex].isStreaming) {
            updatedChat[lastIndex] = {
              ...updatedChat[lastIndex],
              text: "Sorry, I encountered an error. Please try again.",
              isStreaming: false,
              error: true,
            };
          } else {
            updatedChat.push({
              role: "assistant",
              text: "Sorry, I encountered an error. Please try again.",
              timestamp: new Date().toISOString(),
              error: true,
            });
          }

          return updatedChat;
        });
      }
    } finally {
      setProcessingQuery(false);
    }
  };

  // Handle speech from microphone component
  const handleSpeechStart = (level) => {
    // More than just visual feedback
    console.log(`Speech detected, level: ${level.toFixed(2)}`);

    // Check if this might be interrupting the assistant
    if (isSpeaking) {
      console.log(
        "User started speaking while assistant is talking - potential interruption"
      );

      // You could optionally set a state flag here to indicate potential interruption
      // setInterruptionPending(true);
    }
  };

  // Handle final speech end from microphone component (user utterance)
  const handleSpeechEnd = (transcript) => {
    console.log(`Speech ended with transcript: "${transcript}"`);

    if (transcript && transcript.trim().length > 0) {
      // Check for special case - interruption marker
      if (transcript === "*INTERRUPTED*") {
        console.log("Received interruption marker from speech component");
        // Don't add this to chat - just handle the interruption
        return;
      }

      // Check if this might be an echo that wasn't caught
      if (audioProcessor && typeof audioProcessor.isLikelyEcho === "function") {
        if (audioProcessor.isLikelyEcho(transcript)) {
          console.log(
            "Extra echo check caught potential echo, ignoring transcript"
          );
          return;
        }
      }

      // Add user message to chat
      const userMessage = {
        role: "user",
        text: transcript,
        timestamp: new Date().toISOString(),
      };

      setChat((prev) => [...prev, userMessage]);

      // Clear any interim text
      setInterimText("");

      // Process the user query
      console.log(`Processing query: "${transcript}"`);
      processQuery(transcript);
    } else {
      console.log("Empty transcript received, ignoring");
    }
  };

  // Handle interruption from microphone component
  const handleSpeechInterruption = (level) => {
    // Direct, immediate handling in this component
    console.log(
      `🔴 Speech interruption detected directly at level: ${level.toFixed(2)}`
    );

    // Update UI state
    setInterrupted(true);

    // Stop current TTS playback IMMEDIATELY
    if (ttsManager) {
      console.log(
        "Emergency stopping TTS from microphone interruption handler"
      );
      ttsManager.stop();

      // Double-check with timeout as fallback
      setTimeout(() => {
        if (ttsManager.isSpeaking) {
          console.log("Fallback TTS stop triggered");
          ttsManager.stop();
        }
      }, 50);
    }

    // Abort any ongoing API requests
    if (abortControllerRef.current) {
      console.log("Aborting ongoing API request due to interruption");
      abortControllerRef.current.abort();
    }

    // Update UI to show interruption
    setChat((prev) => {
      const updatedChat = [...prev];

      // Find the last assistant message
      for (let i = updatedChat.length - 1; i >= 0; i--) {
        if (updatedChat[i].role === "assistant") {
          // Mark as interrupted
          updatedChat[i] = {
            ...updatedChat[i],
            interrupted: true,
          };
          break;
        }
      }

      return updatedChat;
    });

    // Notify conversation manager about interruption
    if (conversationManager) {
      conversationManager.setAssistantSpeaking(false, "");
    }

    // Force restart speech recognition
    if (speechRecognitionManager) {
      setTimeout(() => {
        console.log("Forcing recognition restart after interruption");

        if (typeof speechRecognitionManager.restartRecognition === "function") {
          speechRecognitionManager.restartRecognition();
        } else if (typeof speechRecognitionManager.start === "function") {
          speechRecognitionManager.start();
        }
      }, 150); // Slightly longer delay to ensure TTS has stopped
    }

    // Reset interruption state after a delay
    setTimeout(() => {
      setInterrupted(false);
    }, 1000);
  };

  return (
    <div className="flex flex-col items-center min-h-screen bg-gradient-to-b from-gray-900 to-black text-white p-6">
      <h1 className="text-3xl font-bold mb-2">Mobeus WebRTC Assistant</h1>

      {/* Status indicators */}
      <div className="flex space-x-4 mb-4">
        <div
          className={`text-sm px-3 py-1 rounded-full ${
            isListening ? "bg-green-600" : "bg-gray-700"
          }`}
        >
          {isListening ? "Listening" : "Microphone Off"}
        </div>

        <div
          className={`text-sm px-3 py-1 rounded-full ${
            isSpeaking ? "bg-blue-600 animate-pulse" : "bg-gray-700"
          }`}
        >
          {isSpeaking ? "Speaking" : "Silent"}
        </div>

        {interrupted && (
          <div className="text-sm px-3 py-1 rounded-full bg-yellow-600 animate-pulse">
            Interrupted
          </div>
        )}
      </div>

      {/* Conversation display */}
      <div className="w-full max-w-2xl bg-gray-800 rounded-lg shadow-lg overflow-hidden flex flex-col">
        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[60vh]">
          {chat.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`px-4 py-3 rounded-2xl shadow max-w-[80%] whitespace-pre-line ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : msg.error
                    ? "bg-red-700 text-white"
                    : msg.interrupted
                    ? "bg-yellow-700 text-white"
                    : "bg-gray-600 text-white"
                }`}
              >
                <div className="font-semibold mb-1">
                  {msg.role === "user" ? userName || "You" : "Mobeus"}
                </div>
                <div>
                  {msg.text}
                  {msg.isStreaming && (
                    <span className="inline-block animate-bounce">...</span>
                  )}
                </div>
                {metrics.gpt && idx === chat.length - 1 && !msg.isStreaming && (
                  <div className="text-xs mt-2 text-gray-300">
                    Response time: {metrics.total?.toFixed(2)}s (GPT:{" "}
                    {metrics.gpt?.toFixed(2)}s)
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Speech recognition interim results */}
          {interimText && (
            <div className="flex justify-end">
              <div className="px-4 py-3 rounded-2xl shadow max-w-[80%] bg-gray-700 text-gray-300">
                <div className="font-semibold mb-1">{userName || "You"}:</div>
                <div className="italic">{interimText}</div>
              </div>
            </div>
          )}
        </div>

        {/* TTS visualization */}
        {isSpeaking && (
          <div className="bg-gray-900 p-2 flex justify-center h-12">
            <div className="flex items-end space-x-1 w-full max-w-md">
              {audioLevels.map((level, i) => (
                <div
                  key={i}
                  className="bg-blue-500 w-2 rounded-t transition-all duration-75"
                  style={{ height: `${level * 100}%` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Microphone component */}
      <div className="mt-8">
        <MicrophoneComponent
          onSpeechStart={handleSpeechStart}
          onSpeechEnd={handleSpeechEnd}
          onInterruption={handleSpeechInterruption}
          assistantSpeaking={isSpeaking} // Important: pass the speaking state
          assistantText={currentResponseRef.current} // Pass current text for echo detection
        />
      </div>

      {/* Error message */}
      {errorMessage && (
        <div className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg">
          {errorMessage}
        </div>
      )}

      {/* Feature status */}
      <div className="mt-6 text-xs text-gray-400 text-center">
        <div>
          WebRTC Audio Processing • Echo Cancellation • Real-time Streaming
        </div>
        <div className="mt-1">
          {userName ? `Recognized as: ${userName}` : "Voice Recognition Ready"}
        </div>
      </div>
      <div className="mt-4">
        <button
          onClick={() => {
            console.log("Testing TTS...");
            ttsManager.speak("This is a test of the text to speech system.");
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded"
        >
          Test TTS
        </button>
      </div>
    </div>
  );
}
