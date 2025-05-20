// MP3StreamPlayerWrapper.jsx - Fixed
import { useEffect, useRef, useState } from "react";
import MP3StreamPlayer from "./MP3StreamPlayer";

export default function MP3StreamPlayerWrapper({ text, voice }) {
  const containerRef = useRef(null);
  const playerRef = useRef(null);
  const [latency, setLatency] = useState(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    if (!text) return;

    console.log("Setting up audio for:", text.substring(0, 20) + "...");
    startTimeRef.current = Date.now();

    // Create player instance if it doesn't exist
    if (!playerRef.current) {
      playerRef.current = new MP3StreamPlayer();
    }

    // Set callback for first chunk
    playerRef.current.setOnFirstChunkCallback(() => {
      const firstChunkTime = Date.now();
      const timeDiff = firstChunkTime - startTimeRef.current;
      setLatency(timeDiff);
      console.log(`First chunk latency: ${timeDiff}ms`);
    });

    // Set up URL for streaming
    const url = `/api/speak-stream?text=${encodeURIComponent(
      text
    )}&voice=${voice}`;

    // Get the audio element and set properties
    const audioElement = playerRef.current.element;
    audioElement.controls = true;
    audioElement.style.width = "100%";
    audioElement.style.marginTop = "10px";

    // Start playing the stream
    playerRef.current.playStream(url);

    // Add the audio element to the container
    if (containerRef.current) {
      // Clear any existing content
      containerRef.current.innerHTML = "";
      containerRef.current.appendChild(audioElement);
    }

    return () => {
      if (playerRef.current) {
        playerRef.current.stop();
      }
    };
  }, [text, voice]);

  return (
    <div className="mt-4">
      <div ref={containerRef}></div>
      {latency && (
        <div className="text-xs text-gray-500 mt-1">
          Initial latency: {(latency / 1000).toFixed(2)}s
        </div>
      )}
    </div>
  );
}
