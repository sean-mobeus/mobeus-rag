import React, { useState, useEffect } from "react";
import "./App.css";
import DiagnosticPage from "./components/DiagnosticPage";
import DebugUI from "./components/DebugUI";

// Simplified App with toggle between DiagnosticPage and DebugUI
function App() {
  // mode: 'diagnostic' or 'debug'
  const [mode, setMode] = useState("diagnostic");

  // Initialize mode from URL parameter '?debug=true'
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("debug") === "true") {
      setMode("debug");
    }
  }, []);

  // Toggle between modes
  const toggleMode = () => {
    setMode((prev) => (prev === "diagnostic" ? "debug" : "diagnostic"));
  };

  return (
    <div className="app">
      {/* Floating toggle button */}
      <div
        className="fixed top-2 right-2 bg-gray-800 text-white px-3 py-1 rounded shadow cursor-pointer z-50"
        onClick={toggleMode}
      >
        {mode === "diagnostic" ? "🛠️ Debug Mode" : "📋 Diagnostic Mode"}
      </div>

      {/* Render based on mode */}
      {mode === "diagnostic" ? <DiagnosticPage /> : <DebugUI />}
    </div>
  );
}

export default App;
