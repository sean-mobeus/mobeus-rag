import React from "react";
import { useState, useEffect, useRef } from "react";
import MicButton from "./MicButton";
import OptimizedAudioPlayerWrapper from "./OptimizedAudioPlayerWrapper";

export default function StreamingChatUI() {
  const [chat, setChat] = useState([]);
  const [streamText, setStreamText] = useState(null);
  const [streamingText, setStreamingText] = useState("");
  const [metrics, setMetrics] = useState({});
  const [userName, setUserName] = useState("");
  const [isInitialGreeting, setIsInitialGreeting] = useState(true);
  const API_BASE = import.meta.env.VITE_API_BASE;
  const eventSourceRef = useRef(null);
  const recognizerRef = useRef(null);
  const isLoopingRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const audioTimeoutRef = useRef(null);
  const silenceTimeoutRef = useRef(null);
  const lastTranscriptRef = useRef("");
  const transcriptBufferRef = useRef([]);

  useEffect(() => {
    // Set up UUID for session tracking
    if (!localStorage.getItem("uuid")) {
      localStorage.setItem("uuid", crypto.randomUUID());
    }

    // Check if we have a stored user name
    const storedName = localStorage.getItem("userName");
    if (storedName) {
      setUserName(storedName);
      setIsInitialGreeting(false);
    }

    // Initial greeting if needed
    if (isInitialGreeting) {
      setTimeout(() => {
        const greeting = "Hello! I'm Mobeus Assistant. What's your name?";
        setChat([{ role: "system", text: greeting }]);
        setStreamText(greeting);
      }, 1000);
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      clearTimeout(audioTimeoutRef.current);
      clearTimeout(silenceTimeoutRef.current);
    };
  }, []);

  // Handle silence/unclear speech
  const handleSilence = () => {
    if (isLoopingRef.current && !isSpeakingRef.current) {
      if (transcriptBufferRef.current.length === 0) {
        // If no speech detected for a while, ask for clarification
        const clarificationMsg =
          "I didn't quite catch that. Could you please speak again?";
        setChat((prev) => [
          ...prev,
          { role: "system", text: clarificationMsg },
        ]);
        setStreamText(clarificationMsg);
      } else {
        // Process accumulated speech if we have some partial transcripts
        const fullTranscript = transcriptBufferRef.current.join(" ");
        if (fullTranscript.trim() !== "") {
          processUserSpeech(fullTranscript);
          transcriptBufferRef.current = [];
        }
      }
    }
  };

  // Process user speech and detect name during initial greeting
  const processUserSpeech = (text) => {
    // Avoid processing if it's too similar to the last transcript (potential echo)
    if (
      lastTranscriptRef.current &&
      (text === lastTranscriptRef.current ||
        text.includes(lastTranscriptRef.current) ||
        lastTranscriptRef.current.includes(text))
    ) {
      console.log("Ignored potential echo:", text);
      return;
    }

    lastTranscriptRef.current = text;

    // Handle the initial name capturing
    if (isInitialGreeting && !userName) {
      // Simple name extraction logic - could be improved with NLP
      const namePhrases = [
        "my name is ",
        "i am ",
        "call me ",
        "i'm ",
        "name's ",
      ];

      let extractedName = "";
      let match = false;

      // Try to extract name from common phrases
      for (const phrase of namePhrases) {
        if (text.toLowerCase().includes(phrase)) {
          const parts = text.toLowerCase().split(phrase);
          if (parts.length > 1) {
            // Take the first word after the phrase as the name
            extractedName = parts[1].split(" ")[0];
            match = true;
            break;
          }
        }
      }

      // If no structured phrase found, try to use the whole input as name
      if (!match && text.trim().length > 0) {
        // Use first word as name if no phrase patterns matched
        extractedName = text.trim().split(" ")[0];
      }

      if (extractedName) {
        // Capitalize the first letter
        const formattedName =
          extractedName.charAt(0).toUpperCase() + extractedName.slice(1);
        setUserName(formattedName);
        localStorage.setItem("userName", formattedName);

        const welcomeMessage = `Nice to meet you, ${formattedName}! How can I help you today?`;
        setChat((prev) => [
          ...prev,
          { role: "user", text: text },
          { role: "system", text: welcomeMessage },
        ]);
        setStreamText(welcomeMessage);
        setIsInitialGreeting(false);
        return;
      }
    }

    // Regular query processing
    sendStreamingQuery(text);
  };

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
      // Set speaking state to prevent echo
      isSpeakingRef.current = true;

      // Pause mic during assistant speech to prevent echo
      if (recognizerRef.current) {
        recognizerRef.current.stop();
      }

      const res = await fetch(`${API_BASE}/stream-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: input,
          uuid: localStorage.getItem("uuid"),
          userName: userName, // Send user name with each query
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

                // Calculate estimated speech duration (roughly 80ms per character)
                const estimatedSpeechDuration = Math.max(
                  3000,
                  fullResponse.length * 80
                );

                // Clear any existing timeout
                clearTimeout(audioTimeoutRef.current);

                // Set timeout to resume mic after estimated speech duration plus buffer
                audioTimeoutRef.current = setTimeout(() => {
                  isSpeakingRef.current = false;

                  // Only restart mic if we're still in looping mode
                  if (isLoopingRef.current && recognizerRef.current) {
                    recognizerRef.current.start();

                    // Set up silence detection after speech ends
                    silenceTimeoutRef.current = setTimeout(handleSilence, 5000);
                  }
                }, estimatedSpeechDuration + 500); // Add 500ms buffer
              }
            } catch (error) {
              console.error("Error parsing SSE message:", error);
            }
          }
        }
      }
    } catch (err) {
      console.error("Error in streaming:", err);
      isSpeakingRef.current = false;

      // Attempt to restart mic on error
      if (isLoopingRef.current && recognizerRef.current) {
        try {
          recognizerRef.current.start();
        } catch (micErr) {
          console.error("Failed to restart mic after error:", micErr);
        }
      }
    }
  };

  // Handle speech recognition result
  const handleSpeechResult = (text) => {
    // If the assistant is speaking, buffer the transcript
    if (isSpeakingRef.current) {
      transcriptBufferRef.current.push(text);
      return;
    }

    // Otherwise process immediately
    processUserSpeech(text);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white">
      <h1 className="text-3xl font-bold mb-6">Mobeus Assistant</h1>

      <div className="mb-6">
        <MicButton
          onResult={handleSpeechResult}
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
              <strong>
                {msg.role === "user"
                  ? userName
                    ? `${userName}:`
                    : "You:"
                  : "Mobeus:"}
              </strong>
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

      {/* Status indicator for speech/listening state */}
      <div className="mt-4 text-xs text-gray-400">
        {isSpeakingRef.current
          ? "Assistant is speaking..."
          : isLoopingRef.current
          ? "Listening..."
          : "Mic off"}
      </div>
    </div>
  );
}
