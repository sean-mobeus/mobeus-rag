// OptimizedAudioPlayerWrapper.jsx
import { useEffect, useRef, useState } from "react";
import OptimizedAudioPlayer from "./OptimizedAudioPlayer";

export default function OptimizedAudioPlayerWrapper({ text, voice = "nova" }) {
  const containerRef = useRef(null);
  const playerRef = useRef(null);
  const [latency, setLatency] = useState(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    if (!text) return;

    // Record start time for latency tracking
    startTimeRef.current = Date.now();

    // Create player instance if it doesn't exist
    if (!playerRef.current) {
      playerRef.current = new OptimizedAudioPlayer();
    }

    // Set callback for first chunk
    playerRef.current.setOnFirstChunkCallback((loadTimeMs) => {
      const totalLatency = Date.now() - startTimeRef.current;
      setLatency(totalLatency);
      console.log(
        `Total latency from request to first audio data: ${totalLatency}ms`
      );
    });

    // Set up URL for streaming
    const url = `/api/speak-stream?text=${encodeURIComponent(
      text
    )}&voice=${encodeURIComponent(voice)}`;

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
      // Clean up when component unmounts or text changes
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
          Response time: {(latency / 1000).toFixed(2)}s
        </div>
      )}
    </div>
  );
}
