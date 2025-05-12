//frontend/src/components/ChatUI.jsx
import { useState } from "react";
import MicButton from "./MicButton";
import StreamedAudioPlayer from "./StreamedAudioPlayer";

export default function ChatUI() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamText, setStreamText] = useState(null);
  const API_BASE = import.meta.env.VITE_API_BASE;

  console.log("✅ VITE_API_BASE:", import.meta.env.VITE_API_BASE);

  const sendQuery = async () => {
    if (!input.trim()) return;
    setLoading(true);

    // Add user's question
    const userMessage = { role: "user", text: input };
    setChat((prev) => [...prev, userMessage]);

    // Add thinking placeholder
    const thinkingMsg = {
      role: "system",
      text: "Mobeus is thinking",
      isPlaceholder: true,
    };
    setChat((prev) => [...prev, thinkingMsg]);
    setInput("");

    try {
      // Fetch answer
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });
      const data = await res.json();

      console.log("🧠 Speaking query:", data.answer);

      // Trigger TTS stream
      setStreamText(data.answer);

      // Replace the thinking message with the real assistant message
      setChat((prev) => [
        ...prev.filter((msg) => !msg.isPlaceholder),
        {
          role: "system",
          text: data.answer,
          sources: data.sources || [],
        },
      ]);
    } catch (err) {
      console.error("Error:", err);
    }

    setLoading(false);
  };

  return (
    <div className="p-4 w-full max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Mobeus Assistant</h1>
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
              } ${msg.isPlaceholder ? "animate-pulse" : ""}`}
            >
              <strong>{msg.role === "user" ? "You:" : "Mobeus:"}</strong>
              <p
                className={`mt-1 whitespace-pre-line ${
                  msg.isPlaceholder ? "text-gray-500 italic" : ""
                }`}
              >
                {msg.text}
                {msg.isPlaceholder && (
                  <span className="inline-block animate-bounce">...</span>
                )}
              </p>
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
                sendQuery();
              }
            }}
          />
          <div className="flex flex-col gap-2">
            <MicButton
              onResult={(text) => {
                setInput(text);
                setTimeout(sendQuery, 100);
              }}
            />
            <button
              onClick={sendQuery}
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded"
            >
              {loading ? "..." : "Send"}
            </button>
          </div>
        </div>
      </div>

      {streamText && <StreamedAudioPlayer text={streamText} voice="nova" />}
    </div>
  );
}
