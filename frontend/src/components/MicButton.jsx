//frontend/src/components/MicButton.jsx
import { useState, useEffect } from "react";

export default function MicButton({ onResult }) {
  const [listening, setListening] = useState(false);
  const [recognizer, setRecognizer] = useState(null);
  const [countdown, setCountdown] = useState(10); // 10-second timer

  useEffect(() => {
    let timer;
    if (listening && countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    } else if (listening && countdown === 0 && recognizer) {
      recognizer.stop();
    }
    return () => clearTimeout(timer);
  }, [listening, countdown, recognizer]);

  const toggleListening = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Sorry, your browser does not support speech recognition.");
      return;
    }

    if (listening && recognizer) {
      recognizer.stop();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setListening(true);
      setCountdown(10);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = (e) => console.error("Speech error:", e);

    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      onResult(transcript);
    };

    recognition.start();
    setRecognizer(recognition);
  };

  return (
    <div className="flex flex-col items-center">
      <button
        onClick={toggleListening}
        className={`${
          listening ? "bg-red-600" : "bg-green-600"
        } text-white px-3 py-2 rounded`}
      >
        {listening ? `🛑 Stop (${countdown}s)` : "🎤 Mic"}
      </button>
      {listening && (
        <div className="text-xs text-gray-500 mt-1 animate-pulse">
          Listening... you have {countdown} seconds
        </div>
      )}
    </div>
  );
}
