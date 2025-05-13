// StreamedAudioPlayerWrapper.jsx - Original path structure
import { useEffect, useRef, useState } from "react";
import StreamedAudioPlayerV2 from "./StreamedAudioPlayerV2";

const StreamedAudioPlayerWrapper = ({ text, voice = "nova" }) => {
  const playerRef = useRef(null);
  const playerInstance = useRef(null);
  const [playerState, setPlayerState] = useState("idle"); // idle, loading, playing, error

  useEffect(() => {
    if (!text) return;

    setPlayerState("loading");

    // Clean up previous instance
    if (playerInstance.current) {
      playerInstance.current.stop();
    }

    playerInstance.current = new StreamedAudioPlayerV2();

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
    audioElement.style.display = "none"; // Hide controls by default

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

  // Optional: Add UI controls for debugging
  return (
    <div className="audio-player-wrapper">
      {/* Audio element will be attached here */}
      <div
        ref={(el) => {
          if (el && !playerRef.current) playerRef.current = el;
        }}
      />

      {/* Debug information */}
      <div className="text-xs text-gray-400 mt-1">
        Player State: {playerState}
      </div>

      {/* Status indicator */}
      {playerState === "loading" && (
        <div className="text-sm text-gray-500 mt-2">Loading audio...</div>
      )}
      {playerState === "error" && (
        <div className="text-sm text-red-500 mt-2">
          Error playing audio. Check console for details.
        </div>
      )}
    </div>
  );
};

export default StreamedAudioPlayerWrapper;
