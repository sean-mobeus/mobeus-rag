import React, { useState, useEffect, useRef } from "react";
import audioProcessor from "./AudioProcessor";
import speechRecognitionManager from "./SpeechRecognitionManager";

/**
 * Enhanced microphone component with WebRTC audio processing
 *
 * Features:
 * - Professional audio visualization
 * - WebRTC-based voice activity detection
 * - Voice analysis and interruption detection
 * - Assistant speaking state visualization
 */
export default function MicrophoneComponent({
  onSpeechStart,
  onSpeechEnd,
  onInterruption,
  assistantSpeaking = false,
  assistantText = "",
}) {
  // State
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [audioLevels, setAudioLevels] = useState([]);
  const [errorMessage, setErrorMessage] = useState(null);
  const [volume, setVolume] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Refs
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const assistantTextRef = useRef("");
  const interruptionTimeoutRef = useRef(null);

  // Constants
  const BAR_COUNT = 32;
  const MIN_BAR_HEIGHT = 3;

  // Update assistant speaking state when prop changes
  useEffect(() => {
    console.log(
      `MicrophoneComponent: Assistant speaking state changed to ${assistantSpeaking}`
    );
    assistantTextRef.current = assistantText;

    // Ensure audio processor is updated about assistant speaking state
    if (audioProcessor) {
      console.log(
        `Updating audio processor: assistant speaking = ${assistantSpeaking}`
      );
      audioProcessor.setAssistantSpeaking(assistantSpeaking, assistantText);
    }
  }, [assistantSpeaking, assistantText]);

  // Initialize audio processor
  useEffect(() => {
    const initializeAudio = async () => {
      try {
        setIsProcessing(true);
        setErrorMessage(null);

        // Check browser support
        if (!audioProcessor.constructor.isSupported()) {
          setErrorMessage(
            "Your browser doesn't support WebRTC audio processing"
          );
          setIsProcessing(false);
          return;
        }

        // Initialize the audio processor
        await audioProcessor.initialize();

        // Set up enhanced callbacks
        audioProcessor.onSpeechStart = (level) => {
          console.log(`Speech detected, level: ${level.toFixed(2)}`);
          setIsSpeaking(true);
          if (onSpeechStart) onSpeechStart(level);
        };

        audioProcessor.onSpeechEnd = (utterance) => {
          console.log(`Speech ended: "${utterance}"`);
          setIsSpeaking(false);
          if (onSpeechEnd) onSpeechEnd(utterance);
        };

        // Enhanced interruption handling
        audioProcessor.onInterruption = (level) => {
          console.log(
            `🔊 Interruption detected in MicrophoneComponent, level: ${level.toFixed(
              2
            )}`
          );

          // Only trigger if assistant is actually speaking
          if (assistantSpeaking) {
            console.log("Assistant is speaking - handling interruption");

            // Clear any existing timeout
            if (interruptionTimeoutRef.current) {
              clearTimeout(interruptionTimeoutRef.current);
            }

            // Provide visual feedback
            setIsSpeaking(true);

            // Call parent component's interruption handler
            if (onInterruption) {
              console.log("Calling parent interruption handler");
              onInterruption(level);
            }
          } else {
            console.log("Ignoring interruption - assistant not speaking");
          }
        };

        // Enhanced volume visualization
        audioProcessor.onVolumeUpdate = (newVolume, isActive) => {
          // Amplify for better visualization
          setVolume(Math.min(1, newVolume * 1.5));

          // Generate bar levels for visualization
          const newLevels = [];

          // Create a frequency distribution with higher values in the middle
          for (let i = 0; i < BAR_COUNT; i++) {
            // Create a natural-looking curve
            const normalizedPosition = (i / (BAR_COUNT - 1)) * 2 - 1; // -1 to 1
            const curve = 1 - normalizedPosition * normalizedPosition; // Parabola

            // Modulate with volume
            const value = Math.max(
              MIN_BAR_HEIGHT,
              Math.min(100, curve * newVolume * 100 * (isActive ? 1 : 0.3))
            );

            newLevels.push(value);
          }

          setAudioLevels(newLevels);
        };

        setIsProcessing(false);
      } catch (error) {
        console.error("Error initializing audio:", error);
        setErrorMessage(`Microphone initialization failed: ${error.message}`);
        setIsProcessing(false);
      }
    };

    initializeAudio();

    // Clean up on unmount
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }

      if (interruptionTimeoutRef.current) {
        clearTimeout(interruptionTimeoutRef.current);
      }

      audioProcessor.dispose();
    };
  }, [onSpeechStart, onSpeechEnd, onInterruption]);

  // Start/stop listening (speech recognition)
  const toggleListening = async () => {
    if (isListening) {
      // Stop speech recognition (this also stops audio capture)
      try {
        console.log("Stopping speech recognition");
        speechRecognitionManager.stop();
      } catch (e) {
        console.error("Error stopping recognition:", e);
      }
      setIsListening(false);
      setIsSpeaking(false);
    } else {
      try {
        setIsProcessing(true);
        setErrorMessage(null);

        console.log("Starting speech recognition");

        // Ensure audio processor is initialized for visualization
        await audioProcessor.initialize();

        // Start speech recognition (starts WebRTC capture internally)
        await speechRecognitionManager.start();
        setIsListening(true);
      } catch (error) {
        console.error("Error starting listening:", error);
        setErrorMessage(`Microphone access failed: ${error.message}`);
      } finally {
        setIsProcessing(false);
      }
    }
  };

  // Get appropriate status text based on current state
  const getStatusText = () => {
    if (isProcessing) return "Initializing...";

    if (!isListening) return "Tap to Start";

    if (isSpeaking) return "I'm listening...";

    if (assistantSpeaking) return "Assistant speaking...";

    return "Tap to Stop";
  };

  return (
    <div className="flex flex-col items-center">
      {/* Visualization */}
      <div className="mb-4 bg-gray-900 rounded-lg overflow-hidden p-2 w-64 h-24 flex justify-center items-end">
        {/* Audio bars visualization */}
        <div className="flex w-full h-full items-end space-x-1">
          {audioLevels.map((level, i) => (
            <div
              key={i}
              className={`w-1 rounded-t transition-all duration-75 ${
                isListening
                  ? isSpeaking
                    ? "bg-green-500" // User speaking
                    : assistantSpeaking
                    ? "bg-purple-500" // Assistant speaking - NEW!
                    : "bg-blue-500" // Listening but silent
                  : "bg-gray-600" // Mic off
              }`}
              style={{
                height: `${level}%`,
                opacity: isSpeaking ? 1 : assistantSpeaking ? 0.85 : 0.7,
              }}
            />
          ))}
        </div>
      </div>

      {/* Volume indicator with assistant state */}
      <div className="w-64 h-4 bg-gray-800 rounded-full mb-4 relative">
        <div
          className={`h-full rounded-full transition-all duration-75 ${
            isSpeaking
              ? "bg-green-500"
              : assistantSpeaking
              ? "bg-purple-500"
              : "bg-blue-500"
          }`}
          style={{ width: `${volume * 100}%` }}
        />

        {/* Assistant speaking indicator */}
        {assistantSpeaking && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-white font-semibold">
            Assistant Speaking
          </div>
        )}
      </div>

      {/* Microphone button with visual indicators */}
      <div className="relative">
        <button
          onClick={toggleListening}
          disabled={isProcessing}
          className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
            isProcessing
              ? "bg-gray-500 cursor-wait"
              : isListening
              ? isSpeaking
                ? "bg-green-600 hover:bg-green-700 animate-pulse"
                : assistantSpeaking
                ? "bg-purple-600 hover:bg-purple-700" // Purple for assistant speaking
                : "bg-red-600 hover:bg-red-700"
              : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-white"
          >
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
        </button>

        {/* Indicator badge for assistant speaking */}
        {assistantSpeaking && (
          <div className="absolute -top-2 -right-2 bg-purple-500 text-white text-xs rounded-full w-6 h-6 flex items-center justify-center animate-pulse">
            AI
          </div>
        )}
      </div>

      {/* Status text with enhanced state display */}
      <div className="mt-2 text-sm font-medium">{getStatusText()}</div>

      {/* Error message */}
      {errorMessage && (
        <div className="mt-2 text-red-500 text-sm text-center max-w-xs">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
