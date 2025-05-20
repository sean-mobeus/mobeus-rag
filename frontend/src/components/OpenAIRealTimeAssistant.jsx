import React, { useState, useEffect, useRef } from "react";
import openaiRealtimeClient from "./OpenAIRealtimeClient";

/**
 * OpenAI Realtime Voice Assistant using WebRTC
 *
 * This component uses WebRTC to connect directly to OpenAI's Realtime API
 * while integrating with our backend for RAG and memory management.
 */
export default function OpenAIRealtimeAssistant() {
  // State
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentResponse, setCurrentResponse] = useState("");
  const [functionCalls, setFunctionCalls] = useState([]);

  // User state
  const [userName, setUserName] = useState(
    localStorage.getItem("userName") || ""
  );
  const [userUuid] = useState(
    localStorage.getItem("uuid") || crypto.randomUUID()
  );

  // Audio visualization
  const [audioContext, setAudioContext] = useState(null);
  const [audioAnalyser, setAudioAnalyser] = useState(null);
  const [audioLevels, setAudioLevels] = useState([]);

  // Refs
  const animationRef = useRef(null);
  const audioElementRef = useRef(null);

  // Initialize UUID
  useEffect(() => {
    localStorage.setItem("uuid", userUuid);
  }, [userUuid]);

  // Initialize client and event listeners
  useEffect(() => {
    // Set up event listeners
    openaiRealtimeClient.on("connected", handleConnected);
    openaiRealtimeClient.on("disconnected", handleDisconnected);
    openaiRealtimeClient.on("error", handleError);
    openaiRealtimeClient.on("session.created", handleSessionCreated);
    openaiRealtimeClient.on("message.completed", handleMessageCompleted);
    openaiRealtimeClient.on("response.text.delta", handleTextDelta);
    openaiRealtimeClient.on("response.text.done", handleTextDone);
    openaiRealtimeClient.on("response.audio.delta", handleAudioDelta);
    openaiRealtimeClient.on("response.audio.done", handleAudioDone);
    openaiRealtimeClient.on("speech.started", handleSpeechStarted);
    openaiRealtimeClient.on("speech.stopped", handleSpeechStopped);
    openaiRealtimeClient.on("function_call.done", handleFunctionCall);
    openaiRealtimeClient.on("audio.track_received", handleAudioTrackReceived);

    // Cleanup on unmount
    return () => {
      openaiRealtimeClient.removeAllListeners();
      disconnect();
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  // Event handlers
  const handleConnected = () => {
    console.log("Connected to OpenAI Realtime API");
    setConnected(true);
    setConnecting(false);
    setError(null);
  };

  const handleDisconnected = () => {
    console.log("Disconnected from OpenAI Realtime API");
    setConnected(false);
    setConnecting(false);
    setSpeaking(false);
    setListening(false);
  };

  const handleError = (error) => {
    console.error("OpenAI Realtime API error:", error);
    setError(error.message || "An error occurred");
    setConnecting(false);
  };

  const handleSessionCreated = (session) => {
    console.log("Session created:", session);

    // If user doesn't have a name, OpenAI will ask for it
    if (!userName) {
      // OpenAI will automatically start the conversation based on our instructions
    }
  };

  const handleMessageCompleted = ({ role, text }) => {
    console.log(`Message completed - ${role}: ${text}`);

    setMessages((prev) => [
      ...prev,
      {
        role,
        text,
        timestamp: new Date().toISOString(),
      },
    ]);

    // Extract user name from first interaction if needed
    if (role === "user" && !userName && text.length > 0) {
      extractUserName(text);
    }

    // Clear current response
    setCurrentResponse("");
  };

  const handleTextDelta = (delta) => {
    setCurrentResponse((prev) => prev + delta);
  };

  const handleTextDone = (text) => {
    console.log("Text response completed:", text);
  };

  const handleAudioDelta = (event) => {
    // Audio is handled by WebRTC, but we can use this for visualization
    setSpeaking(true);
  };

  const handleAudioDone = () => {
    console.log("Audio response completed");
    setSpeaking(false);
  };

  const handleSpeechStarted = () => {
    console.log("User speech started");
    setListening(true);
  };

  const handleSpeechStopped = () => {
    console.log("User speech stopped");
    setListening(false);
  };

  const handleFunctionCall = ({ call_id, name, arguments: args }) => {
    console.log("Function call completed:", name, args);

    setFunctionCalls((prev) => [
      ...prev,
      {
        id: call_id,
        name,
        arguments: args,
        timestamp: new Date().toISOString(),
      },
    ]);

    // Clear old function calls (keep last 5)
    setFunctionCalls((prev) => prev.slice(-5));
  };

  const handleAudioTrackReceived = (stream) => {
    console.log("Audio track received from OpenAI");

    // Set up audio visualization
    setupAudioVisualization(stream);
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

    // If no pattern matched and it's a short response, use as name
    if (!extractedName && text.trim().split(" ").length === 1) {
      extractedName = text.trim();
    }

    if (extractedName) {
      const formattedName =
        extractedName.charAt(0).toUpperCase() +
        extractedName.slice(1).toLowerCase();
      setUserName(formattedName);
      localStorage.setItem("userName", formattedName);
    }
  };

  // Audio visualization setup
  const setupAudioVisualization = (stream) => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(stream);

      analyser.fftSize = 256;
      source.connect(analyser);

      setAudioContext(audioCtx);
      setAudioAnalyser(analyser);

      // Start visualization loop
      visualizeAudio(analyser);
    } catch (error) {
      console.warn("Could not set up audio visualization:", error);
    }
  };

  // Audio visualization loop
  const visualizeAudio = (analyser) => {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const animate = () => {
      if (speaking) {
        analyser.getByteFrequencyData(dataArray);

        // Calculate levels for visualization bars
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

        setAudioLevels(levels);
      } else {
        // Decay levels when not speaking
        setAudioLevels((prev) =>
          prev.map((level) => Math.max(0, level * 0.95))
        );
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();
  };

  // Connection functions
  const connect = async () => {
    if (connecting || connected) return;

    setConnecting(true);
    setError(null);

    try {
      await openaiRealtimeClient.connect(userUuid);
    } catch (error) {
      setError(error.message);
      setConnecting(false);
    }
  };

  const disconnect = () => {
    openaiRealtimeClient.disconnect();
    if (audioContext) {
      audioContext.close();
      setAudioContext(null);
      setAudioAnalyser(null);
    }
  };

  // Send text message
  const sendText = (text) => {
    if (connected && text.trim()) {
      openaiRealtimeClient.sendText(text);
    }
  };

  // Cancel current response
  const cancelResponse = () => {
    openaiRealtimeClient.cancelResponse();
    setCurrentResponse("");
    setSpeaking(false);
  };

  // Get status indicator color
  const getStatusColor = () => {
    if (error) return "text-red-500";
    if (connected && listening) return "text-green-500";
    if (connected && speaking) return "text-blue-500";
    if (connected) return "text-emerald-500";
    if (connecting) return "text-yellow-500";
    return "text-gray-500";
  };

  return (
    <div className="flex flex-col min-h-screen bg-gradient-to-b from-gray-900 to-black text-white">
      {/* Header */}
      <div className="p-6 border-b border-gray-800">
        <h1 className="text-3xl font-bold mb-4">Mobeus AI Assistant</h1>
        <p className="text-gray-400 mb-4">
          WebRTC connection to OpenAI Realtime API
        </p>

        {/* Status indicators */}
        <div className="flex flex-wrap gap-3">
          <div
            className={`px-3 py-1 rounded-full text-sm border ${
              connected
                ? "border-green-600 bg-green-900"
                : connecting
                ? "border-yellow-600 bg-yellow-900"
                : "border-gray-600 bg-gray-800"
            }`}
          >
            <span
              className={`inline-block w-2 h-2 rounded-full mr-2 ${getStatusColor()} animate-pulse`}
            ></span>
            {connecting
              ? "Connecting..."
              : connected
              ? "Connected"
              : "Disconnected"}
          </div>

          <div
            className={`px-3 py-1 rounded-full text-sm ${
              listening ? "bg-green-600 animate-pulse" : "bg-gray-700"
            }`}
          >
            🎤 {listening ? "Listening" : "Standby"}
          </div>

          <div
            className={`px-3 py-1 rounded-full text-sm ${
              speaking ? "bg-blue-600 animate-pulse" : "bg-gray-700"
            }`}
          >
            🔊 {speaking ? "AI Speaking" : "Silent"}
          </div>

          {userName && (
            <div className="px-3 py-1 rounded-full text-sm bg-purple-600">
              👤 {userName}
            </div>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-3 p-3 bg-red-900 border border-red-600 rounded-lg">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Function calls display */}
        {functionCalls.length > 0 && (
          <div className="mt-3 p-3 bg-blue-900 border border-blue-600 rounded-lg">
            <strong>Active Tools:</strong> {functionCalls.slice(-1)[0].name}
          </div>
        )}
      </div>

      {/* Main content area */}
      <div className="flex-1 flex">
        {/* Chat area */}
        <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-6">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-6">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] p-4 rounded-2xl shadow ${
                    message.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-white"
                  }`}
                >
                  <div className="font-semibold mb-1">
                    {message.role === "user" ? userName || "You" : "Mobeus AI"}
                  </div>
                  <div className="whitespace-pre-wrap">{message.text}</div>
                  <div className="text-xs opacity-70 mt-1">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}

            {/* Current response */}
            {currentResponse && (
              <div className="flex justify-start">
                <div className="max-w-[80%] p-4 rounded-2xl bg-gray-700 text-white shadow">
                  <div className="font-semibold mb-1">Mobeus AI</div>
                  <div className="whitespace-pre-wrap">
                    {currentResponse}
                    <span className="inline-block animate-pulse ml-1">▊</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Audio visualization */}
          {speaking && audioLevels.length > 0 && (
            <div className="mb-6 bg-gray-800 rounded-lg p-4">
              <div className="text-center text-sm text-gray-400 mb-2">
                AI Speaking
              </div>
              <div className="flex items-end justify-center space-x-1 h-16">
                {audioLevels.map((level, i) => (
                  <div
                    key={i}
                    className="bg-blue-500 w-2 rounded-t transition-all duration-100"
                    style={{ height: `${Math.max(4, level * 100)}%` }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex flex-col items-center space-y-4">
            {/* Main connect/disconnect button */}
            {!connected ? (
              <button
                onClick={connect}
                disabled={connecting}
                className="px-8 py-3 bg-green-600 hover:bg-green-700 rounded-lg font-semibold disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
              >
                {connecting ? "Connecting..." : "Start Voice Chat"}
              </button>
            ) : (
              <div className="flex space-x-3">
                <button
                  onClick={disconnect}
                  className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors"
                >
                  Disconnect
                </button>

                {(speaking || currentResponse) && (
                  <button
                    onClick={cancelResponse}
                    className="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg font-medium transition-colors"
                  >
                    Interrupt
                  </button>
                )}
              </div>
            )}

            {/* Instructions */}
            <div className="text-center text-gray-400 text-sm max-w-md">
              {!connected
                ? "Connect to start talking with Mobeus AI. Voice recognition and responses are powered by OpenAI."
                : listening
                ? "I'm listening... speak naturally"
                : speaking
                ? "AI is responding..."
                : "Connected and ready - just start talking!"}
            </div>

            {/* Debug info (only in development) */}
            {process.env.NODE_ENV === "development" && connected && (
              <details className="text-xs text-gray-500">
                <summary>Debug Info</summary>
                <pre className="mt-2">
                  {JSON.stringify(openaiRealtimeClient.getStatus(), null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>

        {/* Side panel for function calls */}
        {functionCalls.length > 0 && (
          <div className="w-80 border-l border-gray-800 p-4">
            <h3 className="text-lg font-semibold mb-4">Tool Activity</h3>
            <div className="space-y-3">
              {functionCalls
                .slice(-5)
                .reverse()
                .map((call) => (
                  <div key={call.id} className="p-3 bg-gray-800 rounded-lg">
                    <div className="font-medium text-blue-400">{call.name}</div>
                    <div className="text-sm text-gray-400 mt-1">
                      {call.name === "search_knowledge_base" &&
                        call.arguments.query}
                      {call.name === "update_user_memory" &&
                        call.arguments.information}
                    </div>
                    <div className="text-xs text-gray-500 mt-2">
                      {new Date(call.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
