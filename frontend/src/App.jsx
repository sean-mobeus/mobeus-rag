//frontend/src/App.jsx
import "./App.css";
import { useState } from "react";
import ChatUI from "./components/ChatUI";
import StreamingChatUI from "./components/StreamingChatUI";

function App() {
  const [useStreaming, setUseStreaming] = useState(true);

  return (
    <div className="app">
      <div className="flex justify-center mb-4 p-2">
        <div className="inline-flex rounded-md shadow-sm" role="group">
          <button
            onClick={() => setUseStreaming(false)}
            className={`px-4 py-2 text-sm font-medium rounded-l-lg ${
              !useStreaming
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-900 border border-gray-200"
            }`}
          >
            Standard Chat
          </button>
          <button
            onClick={() => setUseStreaming(true)}
            className={`px-4 py-2 text-sm font-medium rounded-r-lg ${
              useStreaming
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-900 border border-gray-200"
            }`}
          >
            Streaming Chat
          </button>
        </div>
      </div>

      {useStreaming ? <StreamingChatUI /> : <ChatUI />}
    </div>
  );
}

export default App;
