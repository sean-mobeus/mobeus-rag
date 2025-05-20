import React from "react";
import { useState, useEffect, useRef } from "react";

export default function DebugUI() {
  const [testStatus, setTestStatus] = useState({});
  const [uuid, setUuid] = useState("");
  const [query, setQuery] = useState("Hello, how are you?");
  const [backendUrl, setBackendUrl] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Get existing UUID from localStorage
    const storedUuid = localStorage.getItem("uuid");
    if (storedUuid) {
      setUuid(storedUuid);
    } else {
      // Generate and store a new UUID
      try {
        const newUuid = crypto.randomUUID();
        localStorage.setItem("uuid", newUuid);
        setUuid(newUuid);
      } catch (e) {
        const fallbackUuid =
          "user-" + Math.random().toString(36).substring(2, 15);
        localStorage.setItem("uuid", fallbackUuid);
        setUuid(fallbackUuid);
      }
    }

    // Get API base URL from environment
    const apiBase = import.meta.env.VITE_API_BASE || "";
    setBackendUrl(apiBase);

    // Run initial connection tests
    runConnectionTests();
  }, []);

  const runConnectionTests = async () => {
    setTestStatus((prev) => ({ ...prev, running: true }));

    // Test 1: Check if we can access the debug endpoint (proxy health check)
    try {
      // Determine base URL or path prefix for API
      const trimmedBase = backendUrl
        ? backendUrl.replace(/\/+$/, "")
        : "http://localhost:8010";
      const rootUrl = `${trimmedBase}/debug`;
      console.log(`Testing debug endpoint at: ${rootUrl}`);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const rootResponse = await fetch(rootUrl, {
        signal: controller.signal,
        method: "GET",
      }).catch((e) => {
        if (e.name === "AbortError") {
          throw new Error("Connection timed out");
        }
        throw e;
      });

      clearTimeout(timeoutId);

      setTestStatus((prev) => ({
        ...prev,
        rootConnection: rootResponse.ok ? "success" : "failed",
        rootStatus: rootResponse.status,
      }));
    } catch (e) {
      console.error("Root connection test failed:", e);
      setTestStatus((prev) => ({
        ...prev,
        rootConnection: "error",
        rootError: e.message,
      }));
    }

    // Test 2: Try a simple query to the RAG API
    try {
      // Build API query URL, respecting proxy base if set
      const trimmedBase = backendUrl
        ? backendUrl.replace(/\/+$/, "")
        : "http://localhost:8010";
      const apiUrl = backendUrl
        ? `${trimmedBase}/query`
        : `${trimmedBase}/api/query`;
      console.log(`Testing API query to: ${apiUrl}`);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const queryResponse = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: "Hello, test query",
          uuid: uuid,
        }),
        signal: controller.signal,
      }).catch((e) => {
        if (e.name === "AbortError") {
          throw new Error("API query timed out");
        }
        throw e;
      });

      clearTimeout(timeoutId);

      // Check HTTP status and parse accordingly
      if (!queryResponse.ok) {
        const errorText = await queryResponse.text().catch((e) => e.message);
        throw new Error(`API returned status ${queryResponse.status}: ${errorText}`);
      }
      let data;
      try {
        data = await queryResponse.json();
      } catch (e) {
        throw new Error(`Failed to parse response: ${e.message}`);
      }
      setTestStatus((prev) => ({
        ...prev,
        apiQuery: "success",
        apiStatus: queryResponse.status,
        apiResponse: data,
      }));
    } catch (e) {
      console.error("API query test failed:", e);
      setTestStatus((prev) => ({
        ...prev,
        apiQuery: "error",
        apiError: e.message,
      }));
    }

    setTestStatus((prev) => ({ ...prev, running: false }));
  };

  const sendManualQuery = async () => {
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // Determine base URL or path prefix for API
      const trimmedBase = backendUrl
        ? backendUrl.replace(/\/+$/, "")
        : "http://localhost:8010";
      // Construct query endpoint
      const apiUrl = backendUrl
        ? `${trimmedBase}/query`
        : `${trimmedBase}/api/query`;
      console.log(`Sending manual query to: ${apiUrl}`);
      console.log(`Payload:`, { query, uuid });

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const queryResponse = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query,
          uuid: uuid,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!queryResponse.ok) {
        const errorText = await queryResponse.text();
        throw new Error(
          `API returned status ${queryResponse.status}: ${errorText}`
        );
      }

      const data = await queryResponse.json();
      console.log("API Response:", data);
      setResponse(data);
    } catch (e) {
      console.error("Manual query failed:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Mobeus Debug Panel</h1>

      <div className="mb-6 bg-gray-100 p-4 rounded-lg">
        <h2 className="text-lg font-semibold mb-2">Connection Info</h2>
        <div className="mb-2">
          <strong>UUID:</strong> {uuid || "Not set"}
        </div>
        <div className="mb-2">
          <strong>Backend URL:</strong> {backendUrl || "http://localhost:8010"}
        </div>
        <button
          onClick={runConnectionTests}
          disabled={testStatus.running}
          className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {testStatus.running ? "Running Tests..." : "Test Connection"}
        </button>
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Connection Test Results</h2>

        <div className="mb-4 p-3 border rounded">
          <h3 className="font-medium">Root Connection</h3>
          <div className="mt-1">
            Status:{" "}
            {testStatus.rootConnection === "success" && (
              <span className="text-green-600">Success</span>
            )}
            {testStatus.rootConnection === "failed" && (
              <span className="text-orange-600">
                Failed ({testStatus.rootStatus})
              </span>
            )}
            {testStatus.rootConnection === "error" && (
              <span className="text-red-600">
                Error: {testStatus.rootError}
              </span>
            )}
            {!testStatus.rootConnection && (
              <span className="text-gray-500">Not tested</span>
            )}
          </div>
        </div>

        <div className="mb-4 p-3 border rounded">
          <h3 className="font-medium">API Query</h3>
          <div className="mt-1">
            Status:{" "}
            {testStatus.apiQuery === "success" && (
              <span className="text-green-600">Success</span>
            )}
            {testStatus.apiQuery === "failed" && (
              <span className="text-orange-600">
                Failed ({testStatus.apiStatus})
              </span>
            )}
            {testStatus.apiQuery === "error" && (
              <span className="text-red-600">Error: {testStatus.apiError}</span>
            )}
            {!testStatus.apiQuery && (
              <span className="text-gray-500">Not tested</span>
            )}
          </div>

          {testStatus.apiResponse && (
            <div className="mt-2">
              <div className="text-sm">Response preview:</div>
              <pre className="bg-gray-800 text-white p-2 rounded text-xs overflow-auto mt-1">
                {JSON.stringify(testStatus.apiResponse, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Manual API Test</h2>

        <div className="mb-3">
          <label className="block text-sm font-medium mb-1">
            UUID:
            <input
              type="text"
              value={uuid}
              onChange={(e) => {
                setUuid(e.target.value);
                localStorage.setItem("uuid", e.target.value);
              }}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </label>
        </div>

        <div className="mb-3">
          <label className="block text-sm font-medium mb-1">
            Query:
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </label>
        </div>

        <button
          onClick={sendManualQuery}
          disabled={loading || !query.trim() || !uuid.trim()}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Sending..." : "Send Query"}
        </button>
      </div>

      {error && (
        <div className="mb-6 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          <strong>Error:</strong> {error}
        </div>
      )}

      {response && (
        <div className="mb-6">
          <h3 className="font-medium mb-2">Response:</h3>
          <pre className="bg-gray-800 text-white p-3 rounded overflow-auto max-h-80">
            {JSON.stringify(response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
