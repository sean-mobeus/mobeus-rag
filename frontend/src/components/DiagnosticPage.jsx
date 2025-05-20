import React, { useEffect, useState } from "react";

// Super simple component with no dependencies or complex logic
export default function DiagnosticPage() {
  const [mounted, setMounted] = useState(false);
  const [timeElapsed, setTimeElapsed] = useState(0);

  // Simple effect to track component mounting
  useEffect(() => {
    console.log("DiagnosticPage mounted at:", new Date().toISOString());
    setMounted(true);

    // Set up a timer to verify the component stays mounted
    const interval = setInterval(() => {
      setTimeElapsed((prev) => prev + 1);
    }, 1000);

    return () => {
      console.log("DiagnosticPage unmounted at:", new Date().toISOString());
      clearInterval(interval);
    };
  }, []);

  // Simple counter to verify state updates work
  const [counter, setCounter] = useState(0);
  const incrementCounter = () => setCounter((prev) => prev + 1);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-4">
      <h1 className="text-3xl font-bold mb-8">Frontend Diagnostic Page</h1>

      <div className="bg-gray-800 p-6 rounded-lg shadow-lg max-w-md w-full">
        <div className="mb-4">
          <div className="font-bold">Component Status:</div>
          <div className="text-green-400">✅ Rendered successfully</div>
          <div>Mounted: {mounted ? "Yes" : "No"}</div>
          <div>Time since mount: {timeElapsed} seconds</div>
        </div>

        <div className="mb-4">
          <div className="font-bold">State Update Test:</div>
          <div>Counter: {counter}</div>
          <button
            onClick={incrementCounter}
            className="mt-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Increment Counter
          </button>
        </div>

        <div className="mb-4">
          <div className="font-bold">Environment Variables:</div>
          <div>NODE_ENV: {process.env.NODE_ENV}</div>
          <div>VITE_API_BASE: {import.meta.env.VITE_API_BASE || "Not set"}</div>
        </div>

        <div className="mb-4">
          <div className="font-bold">Browser Info:</div>
          <div>User Agent: {navigator.userAgent}</div>
          <div>URL: {window.location.href}</div>
        </div>
      </div>

      <div className="mt-8 flex gap-4">
        <a
          href="/"
          className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
        >
          Go to App
        </a>
        <a
          href="/?debug=true"
          className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
        >
          Go to Debug Mode
        </a>
        <button
          onClick={() => window.location.reload(true)}
          className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
        >
          Force Reload
        </button>
      </div>
    </div>
  );
}
