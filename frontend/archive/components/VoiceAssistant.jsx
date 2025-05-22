import React, { useState, useEffect, useRef } from "react";
import AudioCapture from "./AudioCapture";
import AudioPlayback from "./AudioPlayback";
import WebRTCManager from "../lib/utils/WebRTCManager";
import SignalingService from "../services/SignalingService";

/**
 * WebRTC Voice Assistant
 *
 * Main component that integrates audio capture, WebRTC communication,
 * and audio playback for a complete voice assistant experience.
 */
function VoiceAssistant() {
  // State
  const [status, setStatus] = useState("initializing");
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [messages, setMessages] = useState([]);
  const [userName, setUserName] = useState(
    localStorage.getItem("userName") || ""
  );
  const [errorMessage, setErrorMessage] = useState("");

  // Refs
  const webrtcRef = useRef(new WebRTCManager());
  const signalingRef = useRef(null);
  const audioPlaybackRef = useRef(null);
  const currentMessageRef = useRef("");
  const playbackCtxRef = useRef(null);

  // Initialize WebRTC and signaling
  useEffect(() => {
    // Ensure UUID exists
    if (!localStorage.getItem("uuid")) {
      const uuid = crypto.randomUUID();
      localStorage.setItem("uuid", uuid);
    }

    // Create signaling service
    const signaling = new SignalingService({
      serverUrl: `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${
        window.location.host
      }/api/webrtc`,
    });

    signaling.onConnected = handleSignalingConnected;
    signaling.onDisconnected = handleSignalingDisconnected;
    signaling.onMessage = handleSignalingMessage;
    signaling.onError = handleSignalingError;

    signalingRef.current = signaling;

    // Configure WebRTC
    const webrtc = webrtcRef.current;

    webrtc.onConnected = handleWebRTCConnected;
    webrtc.onDisconnected = handleWebRTCDisconnected;
    webrtc.onMessage = handleWebRTCMessage;
    webrtc.onTrack = handleWebRTCTrack;
    webrtc.onError = handleWebRTCError;
    webrtc.onStateChange = handleWebRTCStateChange;

    // Check WebRTC support
    if (!WebRTCManager.isSupported()) {
      setStatus("error");
      setErrorMessage("WebRTC is not supported in this browser");
      return;
    }

    setStatus("initialized");

    // Clean up on unmount
    return () => {
      disconnect();
    };
  }, []);

  // Connect to voice assistant
  const connect = async () => {
    setStatus("connecting");
    setErrorMessage("");

    try {
      // Initialize WebRTC (create local offer)
      const webrtc = webrtcRef.current;
      await webrtc.initialize({ audio: true, video: false, initiator: true });

      // Connect to signaling server
      const signaling = signalingRef.current;
      await signaling.connect();

      // Mark as connected and send initial greeting
      setStatus("connected");
      setIsConnected(true);
      const greeting = !userName
        ? "Hello! I'm Mobeus Assistant. What's your name?"
        : `Hello ${userName}! How can I help you today?`;
      // Send greeting over data channel
      webrtc.sendMessage({ type: "assistant_message", text: greeting });
      // Display greeting in chat
      setMessages((prev) => [...prev, { role: "assistant", text: greeting }]);
      // Speak greeting using browser TTS for debugging
      if (window.speechSynthesis) {
        const utter = new SpeechSynthesisUtterance(greeting);
        window.speechSynthesis.speak(utter);
      }
    } catch (error) {
      console.error("Connection error:", error);
      setStatus("error");
      setErrorMessage(`Connection failed: ${error.message}`);
    }
  };

  // Disconnect from voice assistant
  const disconnect = () => {
    const webrtc = webrtcRef.current;
    const signaling = signalingRef.current;

    // Close WebRTC connection
    if (webrtc) {
      webrtc.closeConnection();
    }

    // Close signaling connection
    if (signaling) {
      signaling.disconnect();
    }

    setIsConnected(false);
    setStatus("disconnected");
  };

  // Handle signaling events
  const handleSignalingConnected = () => {
    console.log("Signaling connected");
  };

  const handleSignalingDisconnected = () => {
    console.log("Signaling disconnected");
    setIsConnected(false);
    setStatus("disconnected");
  };

  const handleSignalingMessage = (message) => {
    const webrtc = webrtcRef.current;
    const signaling = signalingRef.current;

    console.log("Signaling message:", message.type);

    switch (message.type) {
      case "offer":
        // Process offer from server
        webrtc.processOffer(message.data.offer).then((answer) => {
          signaling.sendAnswer(answer);
        });
        break;

      case "answer":
        // Process answer from server
        webrtc.processAnswer(message.data.answer);
        break;

      case "candidate":
        // Add ICE candidate
        webrtc.addIceCandidate(message.data.candidate);
        break;

      case "session":
        // Session established
        console.log("Session established:", message.data.sessionId);

        // Send local offer
        if (webrtc.peerConnection && webrtc.peerConnection.localDescription) {
          signaling.sendOffer(webrtc.peerConnection.localDescription);
        }
        break;

      case "ready":
        // Assistant is ready
        setStatus("connected");
        setIsConnected(true);

        // Send initial greeting
        if (!userName) {
          webrtc.sendMessage({
            type: "assistant_message",
            text: "Hello! I'm Mobeus Assistant. What's your name?",
          });
        } else {
          webrtc.sendMessage({
            type: "assistant_message",
            text: `Hello ${userName}! How can I help you today?`,
          });
        }
        break;
    }
  };

  const handleSignalingError = (error) => {
    console.error("Signaling error:", error);
    setStatus("error");
    setErrorMessage(`Signaling error: ${error.message}`);
  };

  // Handle WebRTC events
  const handleWebRTCConnected = () => {
    console.log("WebRTC connected");

    // Send capabilities
    const webrtc = webrtcRef.current;
    webrtc.sendMessage({
      type: "capabilities",
      audio: true,
      video: false,
    });
  };

  const handleWebRTCDisconnected = () => {
    console.log("WebRTC disconnected");
    setIsConnected(false);
    setStatus("disconnected");
  };

  const handleWebRTCMessage = (message) => {
    console.log("WebRTC message:", message);

    switch (message.type) {
      case "user_message":
        // Add user message to chat
        addMessage({
          role: "user",
          text: message.text,
        });
        break;

      case "assistant_message":
        // Add assistant message to chat
        addMessage({
          role: "assistant",
          text: message.text,
        });

        // Check for name extraction
        if (!userName && message.text.includes("What's your name?")) {
          setIsListening(true);
        }
        break;

      case "audio_chunk":
        // Play audio chunk
        if (audioPlaybackRef.current && message.data) {
          audioPlaybackRef.current.playAudio(message.data, message.id);
          setIsSpeaking(true);
        }
        break;

      case "audio_end":
        // End of audio stream
        setIsSpeaking(false);
        break;
    }
  };

  const handleWebRTCTrack = (event) => {
    console.log("WebRTC track:", event);

    // Handle incoming audio track
    if (event.track.kind === "audio") {
      const stream = event.streams[0];

      // Create audio element and play
      const audio = new Audio();
      audio.srcObject = stream;
      audio.autoplay = true;

      // Listen for audio playback
      audio.onplaying = () => {
        setIsSpeaking(true);
      };

      audio.onended = () => {
        setIsSpeaking(false);
      };
    }
  };

  const handleWebRTCError = (error) => {
    console.error("WebRTC error:", error);
    setStatus("error");
    setErrorMessage(`WebRTC error: ${error.message}`);
  };

  const handleWebRTCStateChange = (event) => {
    console.log("WebRTC state change:", event);
  };

  // Handle audio capture events
  const handleAudioData = (data) => {
    // Local playback for debugging (echo microphone)
    try {
      const floatData = data.mono || data.raw;
      if (floatData && floatData.length) {
        if (!playbackCtxRef.current) {
          playbackCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = playbackCtxRef.current;
        const buffer = ctx.createBuffer(1, floatData.length, 24000);
        const channelData = buffer.getChannelData(0);
        for (let i = 0; i < floatData.length; i++) {
          channelData[i] = floatData[i];
        }
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(ctx.destination);
        src.start();
      }
    } catch (e) {
      console.warn('Local playback error:', e);
    }
    // TODO: send audio data to server when connected
  };

  const handleAudioCaptureState = (state) => {
    console.log("Audio capture state:", state);

    if (state.state === "recording") {
      setIsListening(true);

      // If assistant is speaking, interrupt
      if (isSpeaking && audioPlaybackRef.current) {
        audioPlaybackRef.current.interruptPlayback();
      }
    } else if (state.state === "paused") {
      setIsListening(false);

      // Send end of speech marker
      const webrtc = webrtcRef.current;
      webrtc.sendMessage({
        type: "audio_end",
      });
    }
  };

  // Handle audio playback events
  const handleAudioPlaybackState = (state) => {
    console.log("Audio playback state:", state);

    if (state.state === "methods" && state.methods) {
      audioPlaybackRef.current = state.methods;
    } else if (state.state === "playing") {
      setIsSpeaking(true);
    } else if (state.state === "ended" || state.state === "interrupted") {
      setIsSpeaking(false);
    }
  };

  // Add message to chat
  const addMessage = (message) => {
    // Process special messages
    if (
      message.role === "user" &&
      !userName &&
      currentMessageRef.current.includes("What's your name?")
    ) {
      // Extract name from user message
      const namePhrases = [
        "my name is ",
        "i am ",
        "call me ",
        "i'm ",
        "name's ",
      ];

      let extractedName = "";
      let match = false;

      // Try to extract name from common phrases
      for (const phrase of namePhrases) {
        if (message.text.toLowerCase().includes(phrase)) {
          const parts = message.text.toLowerCase().split(phrase);
          if (parts.length > 1) {
            extractedName = parts[1].split(" ")[0];
            match = true;
            break;
          }
        }
      }

      // If no structured phrase found, use the input as name
      if (!match && message.text.trim().length > 0) {
        extractedName = message.text.trim().split(" ")[0];
      }

      if (extractedName) {
        // Capitalize first letter
        const formattedName =
          extractedName.charAt(0).toUpperCase() + extractedName.slice(1);
        setUserName(formattedName);
        localStorage.setItem("userName", formattedName);

        // Send welcome message
        const webrtc = webrtcRef.current;
        const welcomeMessage = `Nice to meet you, ${formattedName}! How can I help you today?`;

        webrtc.sendMessage({
          type: "assistant_message",
          text: welcomeMessage,
        });

        // Add welcome message to chat
        setMessages((prev) => [
          ...prev,
          message,
          {
            role: "assistant",
            text: welcomeMessage,
          },
        ]);

        return;
      }
    }

    // Update current assistant message for context
    if (message.role === "assistant") {
      currentMessageRef.current = message.text;
    }

    // Add message to state
    setMessages((prev) => [...prev, message]);
  };

  return (
    <div className="voice-assistant">
      <div className="assistant-header">
        <h1>Mobeus WebRTC Voice Assistant</h1>
        <div className="assistant-status">
          Status: <span className={`status-${status}`}>{status}</span>
          {errorMessage && <div className="error-message">{errorMessage}</div>}
        </div>

        <div className="assistant-controls">
          {!isConnected ? (
            <button
              className="connect-button"
              onClick={connect}
              disabled={status === "connecting"}
            >
              {status === "connecting" ? "Connecting..." : "Connect"}
            </button>
          ) : (
            <button className="disconnect-button" onClick={disconnect}>
              Disconnect
            </button>
          )}
        </div>
      </div>

      <div className="assistant-content">
        <div className="assistant-messages">
          {messages.map((message, index) => (
            <div key={index} className={`message message-${message.role}`}>
              <div className="message-sender">
                {message.role === "user" ? userName || "You" : "Mobeus"}
              </div>
              <div className="message-text">{message.text}</div>
            </div>
          ))}
        </div>

        <div className="assistant-indicators">
          {isSpeaking && (
            <div className="speaking-indicator">Assistant is speaking...</div>
          )}
          {isListening && (
            <div className="listening-indicator">Listening...</div>
          )}
        </div>
      </div>

      <div className="assistant-audio">
        <div className="audio-capture-container">
          <h3>Microphone</h3>
          <AudioCapture
            onAudioData={handleAudioData}
            onStateChange={handleAudioCaptureState}
          />
        </div>

        <div className="audio-playback-container">
          <h3>Speaker</h3>
          <AudioPlayback onStateChange={handleAudioPlaybackState} />
        </div>
      </div>
    </div>
  );
}

export default VoiceAssistant;
