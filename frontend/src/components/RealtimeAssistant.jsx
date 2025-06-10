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
  // Video state
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoMode, setVideoMode] = useState(false);
  const [videoLatency, setVideoLatency] = useState(null);
  const [didMode, setDidMode] = useState("text"); // 'text' or 'audio'

  // User state
  const [userName, setUserName] = useState(
    localStorage.getItem("userName") || ""
  );
  const [userUuid] = useState(
    localStorage.getItem("uuid") || crypto.randomUUID()
  );

  const [isClearing, setIsClearing] = useState(false);
  const [sessionData, setSessionData] = useState(null);

  // Audio visualization
  const [audioLevels, setAudioLevels] = useState([]);
  const [isInterrupted, setIsInterrupted] = useState(false);

  // Refs
  const messagesEndRef = useRef(null);
  const audioContextRef = useRef(null);
  const animationRef = useRef(null);
  const clientRef = useRef(webSocketRealtimeClient);
  const videoRef = useRef(null);
  const videoModeRef = useRef(videoMode);
  const didModeRef = useRef(didMode);

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

  useEffect(() => {
    videoModeRef.current = videoMode;
  }, [videoMode]);

  useEffect(() => {
    didModeRef.current = didMode;
  }, [didMode]);

  useEffect(() => {
    if (videoMode && !videoUrl) {
      // Show a placeholder or loading state immediately
      setVideoUrl("loading"); // Special value to show overlay
    } else if (!videoMode) {
      // Clear video when video mode is disabled
      setVideoUrl(null);
    }
  }, [videoMode]);

  useEffect(() => {
    if (webSocketRealtimeClient) {
      webSocketRealtimeClient.setAudioEnabled(!videoMode);
    }
  }, [videoMode]);

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
    client.on("did_talk_generated", handleDidTalkGenerated);
    client.on("did_talk_error", handleDidTalkError);

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

  const handleDidTalkGenerated = (event) => {
    console.log("🎬 D-ID video received:", event);
    setVideoUrl(event.video_url);
    setVideoLatency(event.latency);
    // Video will autoplay when set
  };

  const handleDidTalkError = (event) => {
    console.error("❌ D-ID video error:", event);
    showToast(`Video generation failed: ${event.error}`, "error");
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

    // Send current video mode preference using ref value
    if (videoModeRef.current) {
      console.log("🎬 Sending initial video mode preference:", {
        enabled: videoModeRef.current,
        audio_mode: didModeRef.current,
      });
      webSocketRealtimeClient.sendEvent({
        type: "update_video_mode",
        enabled: videoModeRef.current,
        audio_mode: didModeRef.current,
      });
    }

    try {
      const resMem = await fetch(
        `${BACKEND_BASE_URL}/memory/session/${userUuid}`
      );
      if (resMem.ok) {
        const data = await resMem.json();
        console.log("📥 Loaded session memory:", data);
        setSessionData(data);
      } else {
        console.error(
          "❌ Failed to load session memory:",
          resMem.status,
          await resMem.text()
        );
      }
    } catch (e) {
      console.error("❌ Error fetching session memory:", e);
      showToast(`Error fetching memory: ${e.message}`, "error");
    }
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
    // Interrupt video if playing
    if (videoRef.current && videoUrl) {
      videoRef.current.pause();
      setVideoUrl(null);
      console.log("🎬 Video interrupted");
    }
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
      console.log(`📤 Sending request to ${BACKEND_BASE_URL}/memory/clear`);

      const response = await fetch(`${BACKEND_BASE_URL}/memory/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uuid: userUuid }),
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

  const handleAppendSummary = async () => {
    const info = window.prompt(
      "Enter information to append to memory summary:"
    );
    if (!info) return;
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/memory/summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uuid: userUuid, info }),
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Status ${res.status}: ${errText}`);
      }
      showToast("Memory summary updated", "success");
    } catch (error) {
      console.error("❌ Append summary error:", error);
      showToast(`Error appending summary: ${error.message}`, "error");
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
        {showMessages && !videoMode && (
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
            {/* Video Mode Toggle */}
            <button
              onClick={() => {
                const newMode = !videoMode;
                setVideoMode(newMode);

                console.log("🎬 Video toggle clicked:", {
                  connected,
                  newMode,
                  didMode,
                  clientAvailable: !!webSocketRealtimeClient,
                });

                // Send mode to backend
                if (connected) {
                  webSocketRealtimeClient.sendEvent({
                    type: "update_video_mode",
                    enabled: newMode,
                    audio_mode: didMode, // Also send whether to use audio or text
                  });
                } else {
                  console.log("❌ Not connected, can't send update");
                }
              }}
              className={`p-2 rounded-full transition-colors ${
                videoMode
                  ? "text-blue-500 bg-blue-50"
                  : "text-gray-500 hover:text-blue-500 hover:bg-blue-50"
              }`}
              title={videoMode ? "Disable video mode" : "Enable video mode"}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polygon points="23 7 16 12 23 17 23 7"></polygon>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
              </svg>
            </button>
            {/* D-ID Mode Toggle (only show when video mode is on) */}
            {videoMode && (
              <button
                onClick={() => {
                  const newDidMode = didMode === "text" ? "audio" : "text";
                  setDidMode(newDidMode);

                  console.log("🎬 Sending video mode update:", {
                    enabled: videoMode,
                    audio_mode: newDidMode,
                  });

                  // Update backend
                  if (connected) {
                    webSocketRealtimeClient.sendEvent({
                      type: "update_video_mode",
                      enabled: videoMode,
                      audio_mode: newDidMode,
                    });
                  }

                  showToast(
                    `Video mode: ${
                      newDidMode === "text"
                        ? "Fast (text)"
                        : "Voice preserved (audio)"
                    }`,
                    "info"
                  );
                }}
                className="p-2 rounded-full text-gray-500 hover:text-purple-500 hover:bg-purple-50 transition-colors"
                title={`Current: ${
                  didMode === "text"
                    ? "Fast text mode"
                    : "Audio mode (preserves voice)"
                }`}
              >
                {didMode === "text" ? "T" : "A"}
              </button>
            )}

            <button
              onClick={handleAppendSummary}
              className="p-2 rounded-full text-gray-500 hover:text-blue-500 hover:bg-blue-50 transition-colors"
              title="Append to memory summary"
            >
              📑
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
        {showMessages && !videoMode && (
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
        {/* {/* Video Overlay */}
        {videoMode && (videoUrl || videoMode) && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100vw",
              height: "100vh",
              backgroundColor: "black",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 100,
            }}
          >
            {videoUrl && videoUrl !== "loading" ? (
              <video
                ref={videoRef}
                src={videoUrl}
                autoPlay
                onEnded={() => {
                  console.log("🎬 Video ended");
                  setVideoUrl("loading"); // Back to loading state
                }}
                onError={(e) => {
                  console.error("🎬 Video error:", e);
                  setVideoUrl("loading"); // Back to loading state
                }}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <div style={{ color: "white", fontSize: "24px" }}>
                <div className="animate-pulse">Preparing avatar...</div>
              </div>
            )}

            {/* Control Bar */}
            <div
              style={{
                position: "absolute",
                bottom: 0,
                left: 0,
                right: 0,
                padding: "20px",
                background:
                  "linear-gradient(to top, rgba(0,0,0,0.8), transparent)",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "20px",
              }}
            >
              {/* Microphone Button */}
              <button
                onClick={toggleConnection}
                disabled={connecting}
                className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 border-2 ${
                  connecting
                    ? "bg-yellow-500 border-yellow-600 cursor-wait"
                    : connected
                    ? listening
                      ? "bg-green-500 border-green-600 shadow-lg scale-105"
                      : speaking
                      ? "bg-blue-500 border-blue-600 shadow-lg"
                      : "bg-gray-700 border-gray-600 hover:bg-gray-600"
                    : "bg-gray-700 border-gray-600 hover:bg-gray-600"
                }`}
              >
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                </svg>
              </button>

              {/* Video toggle */}
              <button
                onClick={() => {
                  const newMode = !videoMode;
                  setVideoMode(newMode);
                  // ... rest of toggle logic
                }}
                className="p-3 rounded-full bg-gray-700 hover:bg-gray-600 text-white"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polygon points="23 7 16 12 23 17 23 7"></polygon>
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
                </svg>
              </button>

              {/* Mode toggle */}
              <button
                onClick={() => {
                  const newDidMode = didMode === "text" ? "audio" : "text";
                  setDidMode(newDidMode);
                  // ... rest of mode toggle logic
                }}
                className="px-4 py-2 rounded-full bg-gray-700 hover:bg-gray-600 text-white text-sm"
              >
                {didMode === "text" ? "Text Mode" : "Audio Mode"}
              </button>

              {/* Latency display */}
              {videoLatency && (
                <div className="text-white text-sm">
                  Latency: {videoLatency.toFixed(2)}s
                </div>
              )}
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
