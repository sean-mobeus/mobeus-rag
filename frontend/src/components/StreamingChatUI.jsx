import { useState, useEffect, useRef } from "react";
import MicButton from "./MicButton";
import OptimizedAudioPlayerWrapper from "./OptimizedAudioPlayerWrapper";

export default function StreamingChatUI() {
  const [chat, setChat] = useState([]);
  const [streamText, setStreamText] = useState(null);
  const [streamingText, setStreamingText] = useState("");
  const [metrics, setMetrics] = useState({});
  const API_BASE = import.meta.env.VITE_API_BASE;
  const eventSourceRef = useRef(null);
  const recognizerRef = useRef(null);
  const isLoopingRef = useRef(false);

  useEffect(() => {
    if (!localStorage.getItem("uuid")) {
      localStorage.setItem("uuid", crypto.randomUUID());
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const sendStreamingQuery = async (input) => {
    if (!input.trim()) return;

    setChat((prev) => [...prev, { role: "user", text: input }]);
    setChat((prev) => [
      ...prev,
      { role: "system", text: "", isStreaming: true },
    ]);
    setStreamingText("");

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const res = await fetch(`${API_BASE}/stream-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: input,
          uuid: localStorage.getItem("uuid"),
        }),
      });

      const reader = res.body.getReader();
      let decoder = new TextDecoder();
      let buffer = "";
      let fullResponse = "";
      let isFirstChunk = true;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.chunk) {
                fullResponse += data.chunk;
                setStreamingText(fullResponse);
                setChat((prev) =>
                  prev.map((msg, i) =>
                    i === prev.length - 1 && msg.isStreaming
                      ? { ...msg, text: fullResponse }
                      : msg
                  )
                );

                if (isFirstChunk && fullResponse.length > 20) {
                  isFirstChunk = false;

                  // Temporarily pause mic while speaking
                  recognizerRef.current?.stop();

                  const firstSentence = fullResponse.split(".")[0] + ".";
                  setStreamText(firstSentence);
                }

                if (data.timings) {
                  setMetrics(data.timings);
                }
              }

              if (data.done) {
                setChat((prev) =>
                  prev.map((msg, i) =>
                    i === prev.length - 1 && msg.isStreaming
                      ? { ...msg, text: fullResponse, isStreaming: false }
                      : msg
                  )
                );
                setStreamText(fullResponse);

                // Resume mic after estimated speech duration
                setTimeout(() => {
                  if (isLoopingRef.current && recognizerRef.current) {
                    recognizerRef.current.start();
                  }
                }, Math.max(2000, fullResponse.length * 50)); // crude estimation
              }
            } catch (error) {
              console.error("Error parsing SSE message:", error);
            }
          }
        }
      }
    } catch (err) {
      console.error("Error in streaming:", err);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white">
      <h1 className="text-3xl font-bold mb-6">Mobeus Assistant</h1>

      <div className="mb-6">
        <MicButton
          onResult={(text) => {
            sendStreamingQuery(text);
          }}
          setRecognizerRef={(ref) => (recognizerRef.current = ref)}
          isLoopingRef={isLoopingRef}
        />
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

      {streamText && (
        <OptimizedAudioPlayerWrapper text={streamText} voice="nova" />
      )}
    </div>
  );
}
