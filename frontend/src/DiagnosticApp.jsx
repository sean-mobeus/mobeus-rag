import React, { useState, useEffect } from "react";
import "./App.css";
import MinimalChatUI from "./components/MinimalChatUI";
import DiagnosticPage from "./components/DiagnosticPage";

function SimpleApp() {
  console.log("App component rendering");

  // Read debug parameter from URL
  const debugParam = new URLSearchParams(window.location.search).get("debug");
  console.log("Debug param:", debugParam);

  // Use state to track which UI to show
  const [showDebug, setShowDebug] = useState(debugParam === "true");

  // Function to toggle between UIs
  const toggleView = () => {
    console.log("Toggle clicked, current state:", showDebug);
    const newState = !showDebug;
    setShowDebug(newState);

    // Update URL to reflect new state
    const url = new URL(window.location);
    if (newState) {
      url.searchParams.set("debug", "true");
    } else {
      url.searchParams.delete("debug");
    }

    console.log("Updating URL to:", url.toString());
    window.history.pushState({}, "", url);
  };

  // Log when component state changes
  useEffect(() => {
    console.log("Component state updated, showDebug =", showDebug);
  }, [showDebug]);

  return (
    <div className="app relative">
      {/* Toggle button - Prominent design */}
      <button
        onClick={toggleView}
        className="fixed top-4 right-4 z-50 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-5 rounded-lg shadow-lg transition-colors"
        style={{ fontSize: "16px" }}
      >
        {showDebug ? "💬 Switch to Chat" : "🛠️ Switch to Debug"}
      </button>

      {/* Content based on state */}
      {showDebug ? <DiagnosticPage /> : <MinimalChatUI />}
    </div>
  );
}

export default SimpleApp;
