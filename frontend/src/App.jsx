import React from "react";
// Use the original WebRTC-based assistant for audio capture/processing
import WebRTCVoiceAssistant from "./components/WebRTCVoiceAssistant";
import "./App.css";

/**
 * Main App component that renders the WebRTC Voice Assistant
 */
function App() {
  return (
    <div className="app">
      <WebRTCVoiceAssistant />
    </div>
  );
}

export default App;
