import React from "react";
import { useState, useEffect, useRef } from "react";
import MicButton from "./MicButton";
import OptimizedAudioPlayerWrapper from "./OptimizedAudioPlayerWrapper";

export default function MinimalChatUI() {
  const [chat, setChat] = useState([]);
  const [streamText, setStreamText] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [logs, setLogs] = useState([]);
  const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8010";
  const recognizerRef = useRef(null);

  // Generate a UUID only once on component load
  const [uuid] = useState(() => {
    // Check for existing UUID in localStorage
    const existingUuid = localStorage.getItem("uuid");
    if (existingUuid) {
      addLog(`Using existing UUID: ${existingUuid}`);
      return existingUuid;
    }

    // Generate a new UUID
    let newUuid;
    try {
      newUuid = crypto.randomUUID();
    } catch (e) {
      newUuid = "user-" + Math.random().toString(36).substring(2, 15);
    }

    addLog(`Generated new UUID: ${newUuid}`);
    localStorage.setItem("uuid", newUuid);
    return newUuid;
  });

  // Helper function for logging events
  function addLog(message) {
    const timestamp = new Date().toLocaleTimeString();
    const logMessage = `${timestamp}: ${message}`;
    console.log(logMessage);
    setLogs((prev) => [logMessage, ...prev].slice(0, 50));
  }

  const sendQuery = async (text) => {
    if (!text.trim()) return;

    addLog(`Sending query: "${text}"`);
    setChat((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    setError(null);

    try {
      const endpoint = `${API_BASE}/api/query`;
      addLog(`Calling endpoint: ${endpoint}`);

      // Create a timeout for the fetch
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          uuid: uuid,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      addLog(`Response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server returned ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      addLog(`Received response with ${Object.keys(data).length} keys`);

      const answer =
        data.answer ||
        data.text ||
        data.response ||
        "Sorry, I received an empty response.";
      setChat((prev) => [...prev, { role: "assistant", text: answer }]);
      setStreamText(answer);
    } catch (err) {
      addLog(`Error: ${err.message}`);
      setError(err.message);
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "I'm having trouble connecting to the server. Please check the logs for details.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white">
      <h1 className="text-3xl font-bold mb-6">Mobeus Minimal Chat</h1>
      <div className="text-sm text-gray-400 mb-2">UUID: {uuid}</div>

      <div className="mb-6">
        <MicButton
          onResult={(text) => {
            sendQuery(text);
          }}
        />

        {/* Add a text input for testing without mic */}
        <div className="mt-4 flex gap-2">
          <input
            type="text"
            placeholder="Type a message..."
            className="px-3 py-2 rounded bg-gray-700 text-white w-64"
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.target.value.trim()) {
                sendQuery(e.target.value);
                e.target.value = "";
              }
            }}
          />
          <button
            className="bg-blue-600 text-white px-4 py-2 rounded"
            onClick={() => {
              const input = document.querySelector("input");
              if (input && input.value.trim()) {
                sendQuery(input.value);
                input.value = "";
              }
            }}
          >
            Send
          </button>
        </div>
      </div>

      <div className="w-full max-w-2xl px-4 space-y-2">
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
                  : "bg-gray-200 text-gray-800"
              }`}
            >
              <strong>{msg.role === "user" ? "You:" : "Mobeus:"}</strong>
              <p className="mt-1">
                {msg.text}
                {loading && idx === chat.length - 1 && msg.role === "user" && (
                  <span className="inline-block animate-bounce ml-2">...</span>
                )}
              </p>
            </div>
          </div>
        ))}

        {loading && chat.length === 0 && (
          <div className="text-center py-4 text-gray-400">
            Loading response...
          </div>
        )}

        {error && (
          <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mt-4">
            <p className="font-bold">Error</p>
            <p>{error}</p>
          </div>
        )}
      </div>

      {streamText && (
        <OptimizedAudioPlayerWrapper text={streamText} voice="nova" />
      )}

      <div className="w-full max-w-2xl mt-8 bg-gray-800 p-2 rounded-lg">
        <details>
          <summary className="cursor-pointer text-gray-300 p-1">
            Debug Logs ({logs.length})
          </summary>
          <div className="mt-2 max-h-60 overflow-y-auto text-xs text-gray-400 font-mono p-2">
            {logs.map((log, idx) => (
              <div key={idx} className="py-1 border-b border-gray-700">
                {log}
              </div>
            ))}
          </div>
        </details>
      </div>
    </div>
  );
}
