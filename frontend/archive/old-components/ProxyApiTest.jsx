import React, { useState } from "react";

export default function ProxyApiTest() {
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [endpoint, setEndpoint] = useState("/api/query");
  const [showConfig, setShowConfig] = useState(false);
  const [debugOutput, setDebugOutput] = useState([]);
  const [payload, setPayload] = useState(
    JSON.stringify(
      {
        query: "Hello, test message",
        uuid: "test-123",
      },
      null,
      2
    )
  );

  // Add to debug log
  const addDebug = (message) => {
    const timestamp = new Date().toISOString().substr(11, 8);
    const logEntry = `${timestamp}: ${message}`;
    console.log(logEntry);
    setDebugOutput((prev) => [logEntry, ...prev].slice(0, 20));
  };

  // Test the API through your environment's standard approach
  const testProxiedApi = async () => {
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      addDebug(`Sending request to: ${endpoint}`);
      addDebug(
        `With payload: ${payload.substring(0, 50)}${
          payload.length > 50 ? "..." : ""
        }`
      );

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      addDebug(`Response status: ${response.status}`);

      const text = await response.text();
      addDebug(`Response length: ${text.length} characters`);

      let jsonResponse;
      try {
        // Try to parse as JSON
        jsonResponse = JSON.parse(text);
        addDebug(
          `Parsed JSON successfully: ${Object.keys(jsonResponse).length} keys`
        );
      } catch (parseError) {
        // If not JSON, just use text
        addDebug(`Failed to parse as JSON: ${parseError.message}`);
        jsonResponse = { text, error: "Not valid JSON" };
      }

      setResponse(jsonResponse);
    } catch (err) {
      addDebug(`ERROR: ${err.name}: ${err.message}`);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 bg-gray-800 text-white rounded-lg max-w-3xl mx-auto my-8">
      <h2 className="text-xl font-bold mb-4">API Proxy Test Tool</h2>

      <div className="mb-4">
        <label className="block mb-1">API Endpoint:</label>
        <input
          type="text"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          className="w-full p-2 bg-gray-700 rounded"
        />
        <div className="text-xs text-gray-400 mt-1">
          For your backend with mounted routes, this should be /api/query
        </div>
      </div>

      <div className="mb-4">
        <label className="block mb-1">Request Payload (JSON):</label>
        <textarea
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          className="w-full p-2 bg-gray-700 rounded font-mono text-sm h-32"
        />
      </div>

      <div className="flex gap-4 mb-4">
        <button
          onClick={testProxiedApi}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Sending..." : "Test API Call"}
        </button>

        <button
          onClick={() => setShowConfig(!showConfig)}
          className="px-4 py-2 bg-gray-600 rounded hover:bg-gray-700"
        >
          {showConfig ? "Hide" : "Show"} Environment
        </button>
      </div>

      {showConfig && (
        <div className="mb-4 p-3 bg-gray-700 rounded">
          <h3 className="font-bold mb-2">Environment Info:</h3>
          <div>
            <strong>VITE_API_BASE:</strong>{" "}
            {import.meta.env.VITE_API_BASE || "Not set"}
          </div>
          <div>
            <strong>NODE_ENV:</strong> {process.env.NODE_ENV}
          </div>
          <div>
            <strong>Browser URL:</strong> {window.location.href}
          </div>
        </div>
      )}

      <div className="mb-4">
        <h3 className="font-bold mb-2">Debug Log:</h3>
        <div className="bg-gray-900 p-2 rounded h-32 overflow-y-auto text-xs font-mono">
          {debugOutput.length > 0 ? (
            debugOutput.map((log, i) => (
              <div key={i} className="py-1 border-b border-gray-800">
                {log}
              </div>
            ))
          ) : (
            <div className="text-gray-500 italic">No logs yet</div>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-900 p-3 rounded mb-4">
          <strong>Error:</strong> {error}
        </div>
      )}

      {response && (
        <div>
          <h3 className="font-bold mb-2">Response:</h3>
          <pre className="bg-gray-900 p-3 rounded overflow-auto max-h-96 text-green-400 text-sm">
            {JSON.stringify(response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
