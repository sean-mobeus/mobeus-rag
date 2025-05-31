// frontend/src/components/RealtimeAssistant.jsx
import React, { useState, useEffect, useRef } from "react";
import webSocketRealtimeClient from "./RealtimeClient";
import { BACKEND_BASE_URL } from "../config.js";

/**
 * Realtime Voice Assistant - Polished UI
 *
 * Clean, modern interface with chat bubbles and central microphone
 */
export default function RealtimeAssistant() {
  // State
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentResponse, setCurrentResponse] = useState("");
  const [toolStrategy, setToolStrategy] = useState("auto");
  const [strategySource, setStrategySource] = useState("default");
  const [showMessages, setShowMessages] = useState(true);
  const [toast, setToast] = useState(null);

  // User state
  const [userName, setUserName] = useState(
    localStorage.getItem("userName") || ""
  );
  const [userUuid] = useState(
    localStorage.getItem("uuid") || crypto.randomUUID()
  );

  const [isClearing, setIsClearing] = useState(false);

  // Audio visualization
  const [audioLevels, setAudioLevels] = useState([]);
  const [isInterrupted, setIsInterrupted] = useState(false);

  // Refs
  const messagesEndRef = useRef(null);
  const audioContextRef = useRef(null);
  const animationRef = useRef(null);
  const clientRef = useRef(webSocketRealtimeClient);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, currentResponse]);

  // Initialize UUID
  useEffect(() => {
    localStorage.setItem("uuid", userUuid);
  }, [userUuid]);

  useEffect(() => {
    localStorage.setItem("userName", userName);
  }, [userName]);

  // Initialize client and event listeners
  useEffect(() => {
    const client = clientRef.current;

    // Set up event listeners using the working logic
    client.on("connected", handleConnected);
    client.on("session.created", handleSessionCreated);
    client.on("disconnected", handleDisconnected);
    client.on("error", handleError);
    client.on("message.completed", handleMessageCompleted);
    client.on("response.text.delta", handleTextDelta);
    client.on("speech.started", handleSpeechStarted);
    client.on("speech.stopped", handleSpeechStopped);
    client.on("response.audio.delta", handleAudioDelta);
    client.on("response.audio.done", handleAudioDone);
    client.on("strategy_updated", handleStrategyUpdated);
    client.on("strategy_update_broadcast", handleStrategyUpdateBroadcast);

    // Cleanup on unmount
    return () => {
      client.removeAllListeners();
      client.disconnect();
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  // Event handlers - using working logic
  const handleConnected = () => {
    console.log("Connected to backend");
    setConnecting(true); // Will be set to false by session.created
  };

  const handleStrategyUpdated = (event) => {
    console.log("🎛️ Strategy updated:", event);
    setToolStrategy(event.strategy);
    setStrategySource(event.source || "direct");

    // Show user feedback about strategy change
    if (event.source === "dashboard_broadcast") {
      // This came from the dashboard - show special notification
      showStrategyChangeNotification(event.strategy, true);
    } else {
      // This was a direct update
      showStrategyChangeNotification(event.strategy, false);
    }
  };

  const handleStrategyUpdateBroadcast = (event) => {
    console.log("📡 Strategy broadcast received:", event);
    // This is handled the same as regular strategy updates
    handleStrategyUpdated(event);
  };

  async function handleSessionCreated(session) {
    console.log("Session ready:", session);
    setConnected(true);
    setConnecting(false);
    setError(null);

    // Store audio context reference
    audioContextRef.current = clientRef.current.audioContext;

    // Resume audio context on user gesture (required by browsers)
    if (audioContextRef.current) {
      await audioContextRef.current.resume();
      console.log("🎧 AudioContext resumed");
    }

    setListening(true);
  }

  const handleDisconnected = () => {
    setConnected(false);
    setConnecting(false);
    setSpeaking(false);
    setListening(false);
    // Clear any residual errors on disconnect
    setError(null);
  };

  const handleError = (error) => {
    console.error("Client error:", error);
    const errMsg =
      typeof error === "string"
        ? error
        : error && error.message
        ? error.message
        : JSON.stringify(error);
    setError(errMsg);
    setConnecting(false);
  };

  const handleMessageCompleted = ({ role, text }) => {
    console.log(`UI: Message completed - role=${role}, text=${text}`);

    const newMessage = {
      role,
      text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, newMessage]);

    // Extract user name from any message if the user explicitly provides it
    if (role === "user" && text.length > 0) {
      extractUserName(text);
    }

    // Clear current response
    setCurrentResponse("");
  };

  // Handle text delta (streaming text as it's generated)
  const handleTextDelta = (delta) => {
    setCurrentResponse((prev) => prev + delta);
  };

  const handleAudioDelta = (event) => {
    setSpeaking(true);
    // Simple audio visualization - create random-ish levels based on audio activity
    if (speaking) {
      const levels = Array.from(
        { length: 12 },
        () => Math.random() * 0.7 + 0.3
      );
      setAudioLevels(levels);
    }
  };

  const handleAudioDone = () => {
    setSpeaking(false);
    setListening(true);
  };

  const handleSpeechStarted = () => {
    console.log("🎤 User speech started - interrupting assistant");

    // Immediately stop speaking and show interruption feedback
    if (speaking) {
      setSpeaking(false);
      setIsInterrupted(true);
      // Clear current response since it was interrupted
      setCurrentResponse("");
      // Clear audio levels
      setAudioLevels([]);

      // Reset interruption indicator after a moment
      setTimeout(() => setIsInterrupted(false), 1500);
    }

    setListening(true);
  };

  const handleSpeechStopped = () => {
    setListening(true); // Keep listening for next input
  };

  // User name extraction
  const extractUserName = (text) => {
    const namePhrases = [
      /my name is (\w+)/i,
      /i am (\w+)/i,
      /call me (\w+)/i,
      /i'm (\w+)/i,
      /name's (\w+)/i,
    ];

    let extractedName = "";
    for (const pattern of namePhrases) {
      const match = text.match(pattern);
      if (match) {
        extractedName = match[1];
        break;
      }
    }

    if (extractedName) {
      const formattedName =
        extractedName.charAt(0).toUpperCase() +
        extractedName.slice(1).toLowerCase();
      setUserName(formattedName);
      localStorage.setItem("userName", formattedName);
    }
  };

  const showStrategyChangeNotification = (newStrategy, fromDashboard) => {
    // You can implement a toast notification here
    console.log(
      `🎛️ Strategy changed to: ${newStrategy} ${
        fromDashboard ? "(from dashboard)" : ""
      }`
    );
  };

  // Audio visualization loop
  useEffect(() => {
    if (!speaking) {
      // Fade out audio levels when not speaking
      const fadeOut = () => {
        setAudioLevels((prev) => prev.map((level) => Math.max(0, level * 0.9)));
      };

      const interval = setInterval(fadeOut, 50);
      return () => clearInterval(interval);
    }
  }, [speaking]);

  // Connection/interruption toggle
  const toggleConnection = async () => {
    console.log(
      `UI: toggleConnection called - connected=${connected}, connecting=${connecting}, speaking=${speaking}`
    );
    if (!connected) {
      console.log("UI: initiating connection");
      await connect();
    } else if (speaking) {
      console.log("UI: manually interrupting assistant");
      clientRef.current.cancelResponse();
      setSpeaking(false);
      setCurrentResponse("");
      setAudioLevels([]);
      setIsInterrupted(true);
      setTimeout(() => setIsInterrupted(false), 1000);
    } else {
      console.log("UI: disconnecting client");
      disconnect();
    }
  };

  const connect = async () => {
    if (connecting || connected) {
      console.log(
        `UI: connect() skipped (connecting=${connecting}, connected=${connected})`
      );
      return;
    }

    console.log("UI: connect() initiating");
    setConnecting(true);
    setError(null);

    try {
      await clientRef.current.connect(userUuid, null, toolStrategy);
    } catch (error) {
      setError(error.toString());
      setConnecting(false);
    }
  };

  const disconnect = () => {
    console.log("UI: disconnect() called");
    clientRef.current.disconnect();
    if (audioContextRef.current) {
      // Only close if not already closed to avoid InvalidStateError
      if (audioContextRef.current.state !== "closed") {
        audioContextRef.current
          .close()
          .catch((err) => console.warn("AudioContext close error:", err));
      }
      audioContextRef.current = null;
    }
    setAudioLevels([]);
  };

  // Get status text (always returns a string)
  const getStatusText = () => {
    let status;
    if (error) {
      status = error;
    } else if (connecting) {
      status = "Connecting...";
    } else if (!connected) {
      status = "Ready to chat";
    } else if (isInterrupted) {
      status = "Interrupted - listening...";
    } else if (listening) {
      status = "Listening...";
    } else if (speaking) {
      status = currentResponse ? "AI speaking..." : "AI thinking...";
    } else {
      status = "Connected";
    }
    return typeof status === "string" ? status : JSON.stringify(status);
  };

  // Get status color
  const getStatusColor = () => {
    if (error) return "text-red-500";
    if (isInterrupted) return "text-yellow-600";
    if (listening) return "text-green-600";
    if (speaking) return "text-blue-600";
    if (connected) return "text-emerald-600";
    return "text-gray-500";
  };

  const StrategyDisplay = () => {
    if (!connected) return null;
  };

  const strategyLabels = {
    auto: "Auto",
    conservative: "Minimal",
    aggressive: "Comprehensive",
    none: "Direct Only",
    required: "Always Search",
  };

  const strategyColors = {
    auto: "text-blue-400",
    conservative: "text-green-400",
    aggressive: "text-purple-400",
    none: "text-gray-400",
    required: "text-red-400",
  };

  // Toast functions
  const showToast = (message, type = "info") => {
    setToast({ message, type });

    // Clear after 3 seconds
    setTimeout(() => setToast(null), 3000);
  };

  // Clear memory functions
  const handleClearMemory = async () => {
    console.log("🗑️ Clear memory button clicked!");
    console.log("🔍 User UUID:", userUuid);

    try {
      console.log(`📤 Sending request to ${BACKEND_BASE_URL}/api/clear-memory`);

      const response = await fetch(`${BACKEND_BASE_URL}/api/clear-memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uuid: userUuid, query: "" }),
      });

      console.log("📥 Response status:", response.status);
      console.log("📥 Response ok:", response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ Response error:", errorText);
        throw new Error(
          `Failed to clear memory: ${response.status} - ${errorText}`
        );
      }

      const result = await response.json();
      console.log("✅ Clear memory result:", result);

      const { cleared } = result;

      if (cleared.total_chars > 0) {
        showToast(
          `Memory cleared: ${cleared.session_messages} messages, ${cleared.total_chars} characters`,
          "success"
        );
      } else {
        showToast("No memory to clear", "info");
      }

      // Clear local messages as well
      setMessages([]);
      setCurrentResponse("");
    } catch (error) {
      console.error("❌ Clear memory error:", error);
      showToast(`Failed to clear memory: ${error.message}`, "error");
    }
  };

  // Confirmation wrapper
  const confirmClearMemory = async () => {
    if (isClearing) {
      console.log("🚫 Clear memory already in progress, ignoring click");
      return;
    }

    try {
      const messageCount = messages.length;
      const confirmed = window.confirm(
        `This will permanently delete all conversation history${
          messageCount > 0 ? ` (${messageCount} messages)` : ""
        }.\n\nAre you sure you want to continue?`
      );

      if (confirmed) {
        setIsClearing(true);
        await handleClearMemory();
        setTimeout(() => setIsClearing(false), 1000);
      }
    } catch (error) {
      console.error("Error in confirmation:", error);
      showToast("Error checking memory status", "error");
      setIsClearing(false);
    }
  };

  // Toast Component
  const Toast = ({ message, type }) => {
    const bgColor =
      type === "error"
        ? "bg-red-500"
        : type === "success"
        ? "bg-green-500"
        : "bg-blue-500";

    return (
      <div
        className={`fixed top-4 right-4 ${bgColor} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300`}
      >
        {message}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-xl font-medium">Mobeus AI Assistant</h1>
          {userName && (
            <p className="text-gray-500 text-sm mt-1">
              Welcome back, {userName}
            </p>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex max-w-6xl mx-auto w-full">
        {/* Left Side - User Messages */}
        {showMessages && (
          <div className="flex-1 p-4">
            <div className="h-full flex flex-col">
              <h2 className="text-sm font-medium text-gray-600 mb-3">You</h2>
              <div className="flex-1 space-y-2 overflow-y-auto">
                {messages
                  .filter((msg) => msg.role === "user")
                  .map((message, index) => (
                    <div key={`user-${index}`} className="flex justify-end">
                      <div className="bg-blue-500 text-white rounded-lg rounded-br-sm px-3 py-2 max-w-xs text-sm shadow-sm">
                        <p>{message.text}</p>
                        <p className="text-blue-100 text-xs mt-1 opacity-75">
                          {new Date(message.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* Center - Microphone & Controls */}
        <div className="w-64 flex flex-col items-center justify-center p-4 bg-white border-x border-gray-200">
          {/* Control Buttons */}
          <div className="mb-4 flex space-x-2">
            {/* Clear Memory Button */}
            <button
              onClick={confirmClearMemory}
              disabled={isClearing}
              className={`p-2 rounded-full transition-colors ${
                isClearing
                  ? "text-gray-300 cursor-not-allowed"
                  : "text-gray-500 hover:text-red-500 hover:bg-red-50"
              }`}
              title="Clear all memory"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M3 6h18" />
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              </svg>
            </button>

            {/* Toggle Messages Button */}
            <button
              onClick={() => setShowMessages(!showMessages)}
              className="p-2 rounded-full text-gray-500 hover:text-blue-500 hover:bg-blue-50 transition-colors"
              title={showMessages ? "Hide messages" : "Show messages"}
            >
              {showMessages ? (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

          {/* Audio Visualization */}
          {(speaking || audioLevels.length > 0) && (
            <div className="mb-6 flex items-end justify-center space-x-1 h-12">
              {audioLevels.map((level, i) => (
                <div
                  key={i}
                  className={`w-2 rounded-full transition-all duration-75 ${
                    speaking ? "bg-blue-400" : "bg-gray-300"
                  }`}
                  style={{
                    height: `${Math.max(4, level * 60)}%`,
                    opacity: speaking ? 1 : 0.3,
                    transform: speaking
                      ? `scaleY(${1 + Math.sin(Date.now() * 0.01 + i) * 0.2})`
                      : "scaleY(1)",
                  }}
                />
              ))}
            </div>
          )}

          {/* Main Microphone Button */}
          <button
            onClick={toggleConnection}
            disabled={connecting}
            className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 border-2 ${
              connecting
                ? "bg-yellow-500 border-yellow-600 cursor-wait"
                : connected
                ? listening
                  ? "bg-green-500 border-green-600 shadow-lg scale-105"
                  : speaking
                  ? "bg-blue-500 border-blue-600 shadow-lg"
                  : "bg-gray-100 border-gray-300 hover:bg-gray-200 shadow-md"
                : "bg-gray-100 border-gray-300 hover:bg-gray-200"
            } ${listening || speaking ? "animate-pulse" : ""} ${
              isInterrupted ? "ring-4 ring-yellow-400 ring-opacity-75" : ""
            }`}
          >
            {/* Microphone Icon */}
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`${
                connected && (listening || speaking)
                  ? "text-white"
                  : "text-gray-600"
              }`}
            >
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" x2="12" y1="19" y2="22" />
            </svg>
          </button>

          {/* Status Text */}
          <div className="mt-4 text-center">
            <p className={`text-sm font-medium ${getStatusColor()}`}>
              {getStatusText()}
            </p>
            {connected && !error && (
              <p className="text-xs text-gray-400 mt-1">
                {isInterrupted
                  ? "Interrupted - continue speaking"
                  : listening
                  ? "Speak naturally"
                  : speaking
                  ? "AI is responding"
                  : "Tap to start talking"}
              </p>
            )}
          </div>

          {/* Error Display */}
          {error && (
            <div className="mt-4 p-2 bg-red-50 border border-red-200 rounded-lg text-center max-w-xs">
              <p className="text-red-600 text-xs">{error}</p>
            </div>
          )}
        </div>

        {/* Right Side - Assistant Messages */}
        {showMessages && (
          <div className="flex-1 p-4">
            <div className="h-full flex flex-col">
              <h2 className="text-sm font-medium text-gray-600 mb-3">
                Mobeus AI
              </h2>
              <div className="flex-1 space-y-2 overflow-y-auto">
                {messages
                  .filter((msg) => msg.role === "assistant")
                  .map((message, index) => (
                    <div
                      key={`assistant-${index}`}
                      className="flex justify-start"
                    >
                      <div className="bg-gray-100 rounded-lg rounded-bl-sm px-3 py-2 max-w-xs text-sm shadow-sm">
                        <p className="text-gray-800">{message.text}</p>
                        <p className="text-gray-500 text-xs mt-1 opacity-75">
                          {new Date(message.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </div>
                  ))}

                {/* Current Response */}
                {currentResponse && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-lg rounded-bl-sm px-3 py-2 max-w-xs text-sm shadow-sm border border-gray-200 animate-pulse">
                      <p className="text-gray-800">
                        {currentResponse}
                        <span className="inline-block w-1 h-4 bg-gray-400 ml-1 animate-pulse" />
                      </p>
                    </div>
                  </div>
                )}

                {/* Auto-scroll target */}
                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-white border-t border-gray-200 p-3">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-xs text-gray-400">
            Powered by OpenAI Realtime API • WebSocket Connection
            {connected && (
              <span className="ml-2 inline-flex items-center">
                <span className="w-1.5 h-1.5 bg-green-400 rounded-full mr-1" />
                Live
              </span>
            )}
          </p>
        </div>
      </div>
      {toast && <Toast message={toast.message} type={toast.type} />}
    </div>
  );
}
