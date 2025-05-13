//frontend/src/components/StreamingChatUI.jsx
import { useState, useEffect, useRef } from "react";
import MicButton from "./MicButton";
import OptimizedAudioPlayerWrapper from "./OptimizedAudioPlayerWrapper";

export default function StreamingChatUI() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamText, setStreamText] = useState(null);
  const [streamingText, setStreamingText] = useState("");
  const [metrics, setMetrics] = useState({});
  const API_BASE = import.meta.env.VITE_API_BASE;
  const eventSourceRef = useRef(null);

  // Clean up event source on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const sendStreamingQuery = async () => {
    if (!input.trim()) return;
    setLoading(true);

    // Add user's question
    const userMessage = { role: "user", text: input };
    setChat((prev) => [...prev, userMessage]);

    // Add thinking placeholder with streaming indicator
    const thinkingMsg = {
      role: "system",
      text: "",
      isStreaming: true,
    };
    setChat((prev) => [...prev, thinkingMsg]);
    setInput("");
    setStreamingText("");

    // Close any existing event source
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      // Start streaming request
      const res = await fetch(`${API_BASE}/stream-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });

      // Create reader from the streaming response
      const reader = res.body.getReader();
      let decoder = new TextDecoder();
      let buffer = "";
      let fullResponse = "";
      let isFirstChunk = true;

      // Process the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the chunk
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep any incomplete data in the buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.substring(6));

              // Handle text chunk
              if (data.chunk) {
                fullResponse += data.chunk;
                setStreamingText(fullResponse);

                // Update streaming message in chat
                setChat((prev) =>
                  prev.map((msg, i) =>
                    i === prev.length - 1 && msg.isStreaming
                      ? { ...msg, text: fullResponse }
                      : msg
                  )
                );

                // Start TTS on first substantial chunk (at least 15 chars)
                if (isFirstChunk && fullResponse.length > 20) {
                  isFirstChunk = false;
                  // Only send the first sentence for immediate TTS
                  const firstSentence = fullResponse.split(".")[0] + ".";
                  setStreamText(firstSentence);
                  console.log(
                    "Starting TTS with initial chunk:",
                    firstSentence
                  );
                }

                // Update metrics
                if (data.timings) {
                  setMetrics(data.timings);
                }
              }

              // Handle completion
              if (data.done) {
                // Update final message in chat
                setChat((prev) =>
                  prev.map((msg, i) =>
                    i === prev.length - 1 && msg.isStreaming
                      ? { ...msg, text: fullResponse, isStreaming: false }
                      : msg
                  )
                );

                // Use the full response for TTS
                setStreamText(fullResponse);
                console.log(
                  "Streaming complete, final response:",
                  fullResponse
                );
              }
            } catch (error) {
              console.error("Error parsing SSE message:", error);
            }
          }
        }
      }
    } catch (err) {
      console.error("Error in streaming:", err);
      // Update error state in chat
      setChat((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1 && msg.isStreaming
            ? {
                ...msg,
                text: "Error fetching response. Please try again.",
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 w-full max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Mobeus Assistant (Streaming)</h1>
      <div className="space-y-2 mb-4">
        {chat.map((msg, idx) => (
          <div
            key={idx}
            className={`my-3 flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`px-4 py-3 max-w-[80%] rounded-2xl shadow ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-800"
              }`}
            >
              <strong>{msg.role === "user" ? "You:" : "Mobeus:"}</strong>
              <p className="mt-1 whitespace-pre-line">
                {msg.text}
                {msg.isStreaming && (
                  <span className="inline-block animate-bounce">...</span>
                )}
              </p>
              {metrics.gpt && idx === chat.length - 1 && (
                <div className="text-xs mt-2 text-gray-500">
                  Response time: {metrics.total?.toFixed(2)}s (GPT:{" "}
                  {metrics.gpt?.toFixed(2)}s)
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col items-center w-full mt-6">
        <div className="flex gap-2 w-full max-w-[80%]">
          <textarea
            className="border p-3 flex-1 rounded text-base resize-none w-full min-h-[7rem] h-[7rem]"
            placeholder="Ask something..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendStreamingQuery();
              }
            }}
          />
          <div className="flex flex-col gap-2">
            <MicButton
              onResult={(text) => {
                setInput(text);
                setTimeout(sendStreamingQuery, 100);
              }}
            />
            <button
              onClick={sendStreamingQuery}
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded"
            >
              {loading ? "..." : "Send"}
            </button>
          </div>
        </div>
      </div>

      {streamText && (
        <OptimizedAudioPlayerWrapper text={streamText} voice="nova" />
      )}
    </div>
  );
}
