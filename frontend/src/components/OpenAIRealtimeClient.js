// OpenAIRealtimeClient.js - WebRTC client for OpenAI Realtime API
import { EventEmitter } from "events";

/**
 * WebRTC client for OpenAI Realtime API
 * Connects directly to OpenAI using ephemeral tokens from our backend
 */
class OpenAIRealtimeClient extends EventEmitter {
  constructor() {
    super();

    // Connection state
    this.peerConnection = null;
    this.dataChannel = null;
    this.connected = false;
    this.connecting = false;

    // Session info
    this.sessionId = null;
    this.ephemeralToken = null;
    this.userUuid = null;

    // Audio handling
    this.audioElement = null;
    this.mediaStream = null;
    this.audioTrack = null;

    // Tool calling
    this.pendingTools = new Map();

    // Configuration
    this.model = "gpt-4o-realtime-preview-2024-12-17";
    this.voice = "alloy";

    // Our backend base URL
    this.backendUrl = window.location.origin;

    // Track audio transcript across events
    this.accumulatedAudioTranscript = "";
    this.currentAssistantItemId = null;
    // Track streaming text parts for assistant messages
    this.accumulatedContentParts = new Map();
  }

  /**
   * Connect to OpenAI Realtime API via WebRTC
   */
  async connect(userUuid = null, customInstructions = null) {
    if (this.connecting || this.connected) {
      return false;
    }

    try {
      this.connecting = true;
      this.userUuid = userUuid;

      // Step 1: Get ephemeral token from our backend
      console.log("Getting ephemeral token from backend...");
      const tokenResponse = await this.getEphemeralToken(
        userUuid,
        customInstructions
      );

      this.ephemeralToken = tokenResponse.client_secret.value;
      this.sessionId = tokenResponse.session_id;

      console.log("Got ephemeral token, creating WebRTC connection...");

      // Step 2: Create WebRTC peer connection
      await this.createPeerConnection();

      // Step 3: Add audio track
      await this.setupAudioTrack();

      // Step 4: Create data channel for events
      this.setupDataChannel();

      // Step 5: Create and send offer to OpenAI
      await this.createAndSendOffer();

      return true;
    } catch (error) {
      console.error("Failed to connect:", error);
      this.connecting = false;
      this.emit("error", error);
      throw error;
    }
  }

  /**
   * Get ephemeral token from our backend
   */
  async getEphemeralToken(userUuid, instructions) {
    const response = await fetch(`${this.backendUrl}/api/realtime/session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_uuid: userUuid,
        model: this.model,
        voice: this.voice,
        instructions: instructions,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to get ephemeral token: ${error}`);
    }

    return await response.json();
  }

  /**
   * Create WebRTC peer connection
   */
  async createPeerConnection() {
    // Create peer connection with standard configuration
    this.peerConnection = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });

    // Handle incoming audio tracks from OpenAI
    this.peerConnection.ontrack = (event) => {
      console.log("Received audio track from OpenAI");

      if (event.track.kind === "audio") {
        // Create audio element to play OpenAI's response
        if (!this.audioElement) {
          this.audioElement = document.createElement("audio");
          this.audioElement.autoplay = true;
          this.audioElement.controls = false;
        }

        this.audioElement.srcObject = event.streams[0];
        this.emit("audio.track_received", event.streams[0]);
      }
    };

    // Handle connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      console.log(
        "WebRTC connection state:",
        this.peerConnection.connectionState
      );

      if (this.peerConnection.connectionState === "connected") {
        this.connected = true;
        this.connecting = false;
        this.emit("connected");
      } else if (
        this.peerConnection.connectionState === "disconnected" ||
        this.peerConnection.connectionState === "failed"
      ) {
        this.connected = false;
        this.emit("disconnected");
      }
    };

    // Handle ICE connection state
    this.peerConnection.oniceconnectionstatechange = () => {
      console.log(
        "ICE connection state:",
        this.peerConnection.iceConnectionState
      );
    };
  }

  /**
   * Setup audio track for microphone input
   */
  async setupAudioTrack() {
    try {
      // Get user media (microphone)
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 24000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Add audio track to peer connection
      this.audioTrack = this.mediaStream.getAudioTracks()[0];
      this.peerConnection.addTrack(this.audioTrack, this.mediaStream);

      console.log("Audio track added to peer connection");
      this.emit("audio.track_added");
    } catch (error) {
      console.error("Failed to get user media:", error);
      throw new Error("Microphone access required for voice chat");
    }
  }

  /**
   * Setup data channel for sending/receiving events
   */
  setupDataChannel() {
    // Create data channel with OpenAI's expected label
    this.dataChannel = this.peerConnection.createDataChannel("oai-events");

    // Handle data channel events
    this.dataChannel.onopen = () => {
      console.log("Data channel opened");
      this.emit("datachannel.opened");
    };

    this.dataChannel.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleRealtimeEvent(message);
      } catch (error) {
        console.error("Failed to parse data channel message:", error);
      }
    };

    this.dataChannel.onclose = () => {
      console.log("Data channel closed");
      this.emit("datachannel.closed");
    };

    this.dataChannel.onerror = (error) => {
      console.error("Data channel error:", error);
      this.emit("datachannel.error", error);
    };
  }

  /**
   * Create offer and send to OpenAI
   */
  async createAndSendOffer() {
    // Create offer
    const offer = await this.peerConnection.createOffer();
    await this.peerConnection.setLocalDescription(offer);

    // Send offer to OpenAI
    const baseUrl = "https://api.openai.com/v1/realtime";
    const response = await fetch(`${baseUrl}?model=${this.model}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.ephemeralToken}`,
        "Content-Type": "application/sdp",
      },
      body: offer.sdp,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI WebRTC handshake failed: ${error}`);
    }

    // Set remote description from OpenAI's answer
    const answerSdp = await response.text();
    const answer = {
      type: "answer",
      sdp: answerSdp,
    };

    await this.peerConnection.setRemoteDescription(answer);
    console.log("WebRTC handshake completed with OpenAI");
  }

  /**
   * Handle incoming Realtime API events
   */
  handleRealtimeEvent(event) {
    const { type } = event;

    console.log("Received OpenAI event:", type, event);

    switch (type) {
      case "session.created":
        this.emit("session.created", event.session);

        // Send initial greeting when session is created
        setTimeout(() => {
          this.sendEvent({
            type: "response.create",
            response: {
              modalities: ["text", "audio"],
              instructions:
                "Say: Hello, I'm Mobeus Assistant. How can I help you today?",
            },
          });
        }, 500);
        break;

      case "conversation.item.created":
        this.emit("conversation.item.created", event.item);

        // New: Check if this is a message from the assistant
        if (
          event.item &&
          event.item.type === "message" &&
          event.item.role === "assistant"
        ) {
          // Extract and concatenate all text segments from content
          let text = "";
          if (Array.isArray(event.item.content)) {
            for (const contentItem of event.item.content) {
              if (contentItem.type === "text") {
                text += contentItem.text || "";
              }
            }
          }

          if (text) {
            console.log(`Assistant message created: "${text}"`);
            this.emit("message.completed", {
              role: "assistant",
              text,
              item: event.item,
            });
          }
        }
        break;

      case "conversation.item.completed":
        this.handleConversationItemCompleted(event.item);
        break;

      case "response.text.delta":
        this.emit("response.text.delta", event.delta);
        break;

      case "response.text.done":
        // Emit streaming text done event
        this.emit("response.text.done", event.text);
        // Emit completed assistant message for UI
        this.emit("message.completed", {
          role: "assistant",
          text: event.text,
        });
        break;

      case "response.audio.delta":
        // Audio is handled by WebRTC track, but we can emit for visualization
        this.emit("response.audio.delta", event);
        break;

      case "response.audio.done":
        this.emit("response.audio.done");
        break;

      case "response.function_call_arguments.delta":
        this.handleFunctionCallDelta(event);
        break;

      case "response.function_call_arguments.done":
        this.handleFunctionCallDone(event);
        break;

      case "input_audio_buffer.speech_started":
        this.emit("speech.started");
        break;

      case "input_audio_buffer.speech_stopped":
        this.emit("speech.stopped");
        break;

      case "error":
        // Generic error event
        this.emit("error", event.error);
        break;
      case "rate_limit":
        // Handle rate-limit signals from the Realtime API
        console.error("OpenAI Realtime rate limit reached:", event);
        this.emit("error", new Error("Rate limit exceeded, please try again later."));
        break;

      // Handle streaming content parts for assistant messages
      case "response.content_part.done": {
        const { item_id, content } = event;
        if (content && content.type === "text") {
          const prev = this.accumulatedContentParts.get(item_id) || "";
          this.accumulatedContentParts.set(item_id, prev + (content.text || ""));
        }
        break;
      }
      // Handle final output item for assistant messages or other items
      case "response.output_item.done": {
        // DEBUG: inspect the full item payload
        console.log("DEBUG response.output_item.done full item:", JSON.stringify(event.item, null, 2));
        const msgItem = event.item;
        if (msgItem && msgItem.type === "message" && msgItem.role === "assistant") {
          // Determine assistant text: prefer accumulated streaming parts
          let text = this.accumulatedContentParts.get(msgItem.id) || "";
          // If no streamed text, extract directly from content array (text or audio transcripts)
          if (!text && Array.isArray(msgItem.content)) {
            for (const contentItem of msgItem.content) {
              if (contentItem.type === "text" && contentItem.text) {
                text += contentItem.text;
              } else if (contentItem.type === "audio" && contentItem.transcript) {
                text += contentItem.transcript;
              }
            }
          }
          // Emit completed assistant message
          this.emit("message.completed", { role: "assistant", text, item: msgItem });
          // Clean up accumulated parts
          this.accumulatedContentParts.delete(msgItem.id);
        } else if (msgItem) {
          // Other items (e.g., function calls)
          this.handleConversationItemCompleted(msgItem);
        }
        break;
      }

      default:
        // Emit generic event
        this.emit(type, event);
        break;
    }

    // Handle special event for input audio transcription
    if (type === "conversation.item.input_audio_transcription.completed") {
      const transcript = event.transcript || "";
      const item_id = event.item_id;

      if (transcript) {
        console.log(`Input audio transcription: "${transcript}"`);
        this.emit("message.completed", {
          role: "user",
          text: transcript.replace(/\n$/, ""), // Remove trailing newline
          itemId: item_id,
        });
      }
    }
  }

  /**
   * Handle completed conversation item
   */
  handleConversationItemCompleted(item) {
    // DEBUG: inspect full conversation.item.completed payload
    console.log("DEBUG handleConversationItemCompleted full item:", JSON.stringify(item, null, 2));

    if (item.type === "message") {
      const { role } = item;

      // Extract and concatenate all text or audio transcript segments from content
      let text = "";
      if (Array.isArray(item.content)) {
        for (const contentItem of item.content) {
          if (contentItem.type === "text" && contentItem.text) {
            text += contentItem.text;
          } else if (contentItem.type === "audio" && contentItem.transcript) {
            text += contentItem.transcript;
          }
        }
      }

      console.log(`Extracted message - ${role}: "${text}"`);

      this.emit("message.completed", {
        role,
        text,
        item,
      });

    }
  }

  /**
   * Handle function call delta (streaming function arguments)
   */
  handleFunctionCallDelta(event) {
    const { call_id, arguments: args } = event;

    // Handle undefined arguments
    if (!args || args === "undefined") {
      console.warn(`Received undefined arguments for call_id: ${call_id}`);
      return;
    }

    if (!this.pendingTools.has(call_id)) {
      this.pendingTools.set(call_id, "");
    }

    const currentArgs = this.pendingTools.get(call_id);
    this.pendingTools.set(call_id, currentArgs + args);

    this.emit("function_call.delta", { call_id, arguments: args });
  }

  /**
   * Handle completed function call
   */
  async handleFunctionCallDone(event) {
    const { call_id, name } = event;
    const arguments_str = this.pendingTools.get(call_id) || "";

    try {
      // Handle possible undefined argument strings
      let arguments_obj = {};
      if (arguments_str && arguments_str !== "undefined") {
        try {
          arguments_obj = JSON.parse(arguments_str);
        } catch (e) {
          console.warn(`Invalid function arguments: ${arguments_str}`, e);
          arguments_obj = { error: "Failed to parse arguments" };
        }
      }

      this.emit("function_call.done", {
        call_id,
        name,
        arguments: arguments_obj,
      });

      // Execute the function call
      await this.executeFunctionCall(call_id, name, arguments_obj);

      // Clean up
      this.pendingTools.delete(call_id);
    } catch (error) {
      console.error("Failed to handle function call:", error);

      // Send error back to OpenAI
      this.sendFunctionResult(call_id, {
        error: error.message,
      });
    }
  }

  /**
   * Execute function call by calling our backend
   */
  async executeFunctionCall(callId, functionName, args) {
    try {
      console.log(`Executing function: ${functionName}`, args);

      let result;

      if (functionName === "search_knowledge_base") {
        // Call our RAG endpoint - use absolute URL to backend
        const backendUrl = window.location.origin.replace(":5173", ":8010");
        const response = await fetch(
          `${backendUrl}/api/realtime/tools/search_knowledge_base`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: args.query || "Mobeus",
              user_uuid: this.userUuid,
            }),
          }
        );
        result = await response.json();
        console.log("Search result:", result);
      } else if (functionName === "update_user_memory") {
        // Call our memory update endpoint - use absolute URL to backend
        const backendUrl = window.location.origin.replace(":5173", ":8010");
        const response = await fetch(
          `${backendUrl}/api/realtime/tools/update_user_memory`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              information: args.information || "",
              user_uuid: args.user_uuid || this.userUuid || "default",
            }),
          }
        );
        result = await response.json();
      } else {
        result = { error: `Unknown function: ${functionName}` };
      }

      // Send result back to OpenAI
      this.sendFunctionResult(callId, result);
    } catch (error) {
      console.error(`Error executing function ${functionName}:`, error);
      this.sendFunctionResult(callId, { error: error.message });
    }
  }

  /**
   * Send function result back to OpenAI
   */
  sendFunctionResult(callId, result) {
    console.log(`Sending function result for call ${callId}:`, result);

    // Ensure result is serializable
    const safeResult = JSON.parse(JSON.stringify(result));

    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: callId,
        output: JSON.stringify(safeResult),
      },
    });

    // Generate response after function result
    this.sendEvent({
      type: "response.create",
      response: {
        modalities: ["text", "audio"],
      },
    });
  }

  /**
   * Send event to OpenAI via data channel
   */
  sendEvent(event) {
    if (this.dataChannel && this.dataChannel.readyState === "open") {
      this.dataChannel.send(JSON.stringify(event));
      return true;
    }
    console.warn("Data channel not ready, cannot send event:", event);
    return false;
  }

  /**
   * Send text message to OpenAI
   */
  sendText(text) {
    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [
          {
            type: "text",
            text: text,
          },
        ],
      },
    });

    // Generate response
    this.sendEvent({
      type: "response.create",
      response: {
        modalities: ["text", "audio"],
      },
    });
  }

  /**
   * Cancel current response
   */
  cancelResponse() {
    this.sendEvent({
      type: "response.cancel",
    });
  }

  /**
   * Log interaction to our backend
   */
  async logInteraction(role, message) {
    if (!this.userUuid) return;

    try {
      // Send interaction logs to backend (development port 8010)
      const logUrl = window.location.origin.replace(
        ":5173",
        ":8010"
      );
      const response = await fetch(`${logUrl}/api/user-identity/log-interaction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          uuid: this.userUuid,
          role,
          message,
        }),
      });
      // Silently ignore non-OK responses
      if (!response.ok) {
        return;
      }
    } catch (error) {
      console.warn("Failed to log interaction:", error);
    }
  }

  /**
   * Disconnect from OpenAI
   */
  disconnect() {
    // Stop audio track
    if (this.audioTrack) {
      this.audioTrack.stop();
    }

    // Close media stream
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
    }

    // Close data channel
    if (this.dataChannel) {
      this.dataChannel.close();
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
    }

    // Clean up audio element
    if (this.audioElement) {
      this.audioElement.srcObject = null;
    }

    // Reset state
    this.connected = false;
    this.connecting = false;
    this.sessionId = null;
    this.ephemeralToken = null;

    this.emit("disconnected");
  }

  /**
   * Check if client is connected
   */
  isConnected() {
    return this.connected;
  }

  /**
   * Get connection status
   */
  getStatus() {
    return {
      connected: this.connected,
      connecting: this.connecting,
      sessionId: this.sessionId,
      userUuid: this.userUuid,
      peerConnectionState: this.peerConnection?.connectionState,
      dataChannelState: this.dataChannel?.readyState,
    };
  }
}

// Export singleton instance
export default new OpenAIRealtimeClient();
