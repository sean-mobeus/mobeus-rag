import { useState, useEffect, useRef } from "react";

export default function MicButton({ onResult }) {
  const [listening, setListening] = useState(false);
  const recognizerRef = useRef(null);
  const isLoopingRef = useRef(false);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Sorry, your browser does not support speech recognition.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setListening(true);

    recognition.onend = () => {
      setListening(false);
      if (isLoopingRef.current) {
        recognition.start();
      }
    };

    recognition.onerror = (e) => {
      console.error("Speech error:", e);
      setListening(false);
    };

    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      onResult(transcript);
    };

    recognizerRef.current = recognition;
  }, []);

  const toggleListening = () => {
    const recognizer = recognizerRef.current;
    if (!recognizer) return;

    if (listening || isLoopingRef.current) {
      isLoopingRef.current = false;
      recognizer.stop();
    } else {
      isLoopingRef.current = true;
      recognizer.start();
    }
  };

  return (
    <div className="flex flex-col items-center">
      <button
        onClick={toggleListening}
        className={`${
          listening ? "bg-red-600" : "bg-green-600"
        } text-white px-4 py-2 rounded-full text-lg w-28`}
      >
        {listening ? "🛑 Stop" : "🎤 Speak"}
      </button>
      {isLoopingRef.current && (
        <div className="text-xs text-gray-400 mt-2 animate-pulse">
          Listening continuously...
        </div>
      )}
    </div>
  );
}
