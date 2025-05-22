// SimplifiedAudioPlayerWrapper.jsx
import { useEffect, useRef, useState } from "react";
import SimplifiedAudioPlayer from "./SimplifiedAudioPlayer";

const SimplifiedAudioPlayerWrapper = ({ text, voice = "nova" }) => {
  const playerRef = useRef(null);
  const playerInstance = useRef(null);
  const [playerState, setPlayerState] = useState("idle"); // idle, loading, playing, error
  const [latency, setLatency] = useState(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    if (!text) return;

    setPlayerState("loading");
    startTimeRef.current = Date.now();

    // Clean up previous instance
    if (playerInstance.current) {
      playerInstance.current.stop();
    }

    // Create new player instance
    playerInstance.current = new SimplifiedAudioPlayer();

    // Set callback for first chunk arrival
    playerInstance.current.setOnFirstChunkCallback(() => {
      const firstChunkTime = Date.now();
      const timeDiff = firstChunkTime - startTimeRef.current;
      setLatency(timeDiff);
      setPlayerState("buffering");
    });

    // Using the original relative URL path that worked before
    const url = `/api/speak-stream?text=${encodeURIComponent(
      text
    )}&voice=${voice}`;

    console.log("Streaming audio from URL:", url);

    // Start the audio stream
    playerInstance.current
      .playStream(url)
      .then(() => {
        setPlayerState("playing");
      })
      .catch((error) => {
        console.error("Audio playback error:", error);
        setPlayerState("error");
      });

    // Set up audio element in the DOM
    const audioElement = playerInstance.current.element;
    audioElement.controls = true;
    audioElement.style.display = "block"; // Show controls for debugging
    audioElement.style.width = "100%";
    audioElement.style.marginTop = "10px";

    // Add event listeners for playback state
    audioElement.onplaying = () => setPlayerState("playing");
    audioElement.onpause = () => setPlayerState("paused");
    audioElement.onended = () => setPlayerState("ended");

    // Replace the existing element
    if (playerRef.current) {
      playerRef.current.replaceWith(audioElement);
    }
    playerRef.current = audioElement;

    // Clean up on unmount
    return () => {
      if (playerInstance.current) {
        playerInstance.current.stop();
      }
    };
  }, [text, voice]);

  return (
    <div className="audio-player-wrapper">
      {/* Audio element will be attached here */}
      <div
        ref={(el) => {
          if (el && !playerRef.current) playerRef.current = el;
        }}
      />

      {/* Status display */}
      <div className="text-xs text-gray-500 mt-1">
        {playerState === "loading" && "Loading audio stream..."}
        {playerState === "buffering" && "Buffering audio..."}
        {playerState === "playing" && "Playing audio"}
        {playerState === "paused" && "Audio paused"}
        {playerState === "ended" && "Audio playback complete"}
        {playerState === "error" && "Error playing audio"}

        {/* Display latency for the first chunk */}
        {latency !== null && ` (First chunk latency: ${latency}ms)`}
      </div>
    </div>
  );
};

export default SimplifiedAudioPlayerWrapper;
