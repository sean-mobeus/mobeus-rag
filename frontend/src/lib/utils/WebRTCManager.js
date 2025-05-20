/**
 * WebRTC Manager for handling real-time audio communication
 */
class WebRTCManager {
  constructor() {
    // WebRTC components
    this.peerConnection = null;
    this.dataChannel = null;
    this.localStream = null;
    this.remoteStream = null;

    // Connection state
    this.connected = false;
    this.connecting = false;
    this.sessionId = null;
    this.streamId = null;

    // Event callbacks
    this.onConnected = null;
    this.onDisconnected = null;
    this.onMessage = null;
    this.onTrack = null;
    this.onError = null;
    this.onStateChange = null;

    // Statistics
    this.lastBytesSent = 0;
    this.lastBytesReceived = 0;
    this.statsInterval = null;
  }

  /**
   * Check if WebRTC is supported in this browser
   */
  static isSupported() {
    return !!(
      window.RTCPeerConnection &&
      window.RTCSessionDescription &&
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia
    );
  }

  /**
   * Get the current connection state
   */
  getConnectionState() {
    if (!this.peerConnection) {
      return "disconnected";
    }

    // Use connectionState if available (not supported in all browsers)
    if (this.peerConnection.connectionState) {
      return this.peerConnection.connectionState;
    }

    // Fallback to iceConnectionState
    return this.peerConnection.iceConnectionState;
  }

  /**
   * Initialize a WebRTC connection
   * @param {Object} config - Configuration options
   * @param {string} config.serverUrl - Signaling server URL
   * @param {RTCIceServer[]} config.iceServers - ICE servers for STUN/TURN
   * @param {boolean} config.audio - Enable audio
   * @param {boolean} config.video - Enable video
   */
  async initialize(config = {}) {
    if (this.connecting || this.connected) {
      throw new Error("WebRTC connection already established or in progress");
    }

    this.connecting = true;

    try {
      // Default configuration
      const defaultConfig = {
        serverUrl: null,
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
        audio: true,
        video: false,
      };

      const mergedConfig = { ...defaultConfig, ...config };

      // Create peer connection
      this.peerConnection = new RTCPeerConnection({
        iceServers: mergedConfig.iceServers,
      });

      // Set up event handlers
      this.setupEventHandlers();

      // Create data channel
      this.dataChannel = this.peerConnection.createDataChannel(
        "voiceAssistant",
        {
          ordered: true,
        }
      );

      this.setupDataChannel();

      // Create offer if we're initiating
      if (mergedConfig.initiator) {
        // Get user media if needed
        if (mergedConfig.audio || mergedConfig.video) {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: mergedConfig.audio,
            video: mergedConfig.video,
          });

          this.localStream = stream;

          // Add tracks to peer connection
          stream.getTracks().forEach((track) => {
            this.peerConnection.addTrack(track, stream);
          });
        }

        // Create and set local description
        const offer = await this.peerConnection.createOffer();
        await this.peerConnection.setLocalDescription(offer);

        // Return the offer to be sent to the remote peer
        return {
          type: "offer",
          sdp: this.peerConnection.localDescription,
        };
      }

      return true;
    } catch (error) {
      this.connecting = false;
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Set up WebRTC event handlers
   */
  setupEventHandlers() {
    const pc = this.peerConnection;

    // ICE gathering state change
    pc.addEventListener("icegatheringstatechange", () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "icegatheringstate",
          state: pc.iceGatheringState,
        });
      }
    });

    // ICE connection state change
    pc.addEventListener("iceconnectionstatechange", () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "iceconnectionstate",
          state: pc.iceConnectionState,
        });
      }

      if (
        pc.iceConnectionState === "failed" ||
        pc.iceConnectionState === "closed"
      ) {
        this.closeConnection();
      }
    });

    // Connection state change (not supported in all browsers)
    pc.addEventListener("connectionstatechange", () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "connectionstate",
          state: pc.connectionState,
        });
      }

      if (pc.connectionState === "connected") {
        this.connected = true;
        this.connecting = false;

        // Start stats interval
        this.startStatsInterval();

        if (this.onConnected) {
          this.onConnected();
        }
      } else if (
        pc.connectionState === "failed" ||
        pc.connectionState === "closed"
      ) {
        this.closeConnection();
      }
    });

    // Signaling state change
    pc.addEventListener("signalingstatechange", () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "signalingstate",
          state: pc.signalingState,
        });
      }
    });

    // ICE candidate
    pc.addEventListener("icecandidate", (event) => {
      if (event.candidate) {
        // Send candidate to signaling server
        // This will be implemented by the app using this manager
        if (this.onStateChange) {
          this.onStateChange({
            type: "icecandidate",
            candidate: event.candidate,
          });
        }
      }
    });

    // Remote track
    pc.addEventListener("track", (event) => {
      this.remoteStream = event.streams[0];

      if (this.onTrack) {
        this.onTrack(event);
      }
    });

    // Data channel
    pc.addEventListener("datachannel", (event) => {
      this.dataChannel = event.channel;
      this.setupDataChannel();
    });
  }

  /**
   * Set up data channel event handlers
   */
  setupDataChannel() {
    if (!this.dataChannel) return;

    this.dataChannel.onopen = () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "datachannel",
          state: "open",
        });
      }
    };

    this.dataChannel.onclose = () => {
      if (this.onStateChange) {
        this.onStateChange({
          type: "datachannel",
          state: "closed",
        });
      }
    };

    this.dataChannel.onmessage = (event) => {
      if (this.onMessage) {
        try {
          const message = JSON.parse(event.data);
          this.onMessage(message);
        } catch (e) {
          // Raw data, not JSON
          this.onMessage({ type: "raw", data: event.data });
        }
      }
    };

    this.dataChannel.onerror = (error) => {
      if (this.onError) {
        this.onError(error);
      }
    };
  }

  /**
   * Process a WebRTC SDP offer from the remote peer
   * @param {RTCSessionDescriptionInit} offer - Remote offer
   */
  async processOffer(offer) {
    if (!this.peerConnection) {
      throw new Error("WebRTC not initialized");
    }

    try {
      await this.peerConnection.setRemoteDescription(offer);

      // Create answer
      const answer = await this.peerConnection.createAnswer();
      await this.peerConnection.setLocalDescription(answer);

      return {
        type: "answer",
        sdp: this.peerConnection.localDescription,
      };
    } catch (error) {
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Process a WebRTC SDP answer from the remote peer
   * @param {RTCSessionDescriptionInit} answer - Remote answer
   */
  async processAnswer(answer) {
    if (!this.peerConnection) {
      throw new Error("WebRTC not initialized");
    }

    try {
      await this.peerConnection.setRemoteDescription(answer);
      return true;
    } catch (error) {
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Add an ICE candidate from the remote peer
   * @param {RTCIceCandidateInit} candidate - ICE candidate
   */
  async addIceCandidate(candidate) {
    if (!this.peerConnection) {
      throw new Error("WebRTC not initialized");
    }

    try {
      await this.peerConnection.addIceCandidate(candidate);
      return true;
    } catch (error) {
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Send a message over the data channel
   * @param {Object|string} message - Message to send
   */
  sendMessage(message) {
    if (!this.dataChannel || this.dataChannel.readyState !== "open") {
      console.warn("Data channel not open");
      return false;
    }

    try {
      // Convert object to JSON string if needed
      const data =
        typeof message === "object" ? JSON.stringify(message) : message;

      this.dataChannel.send(data);
      return true;
    } catch (error) {
      if (this.onError) {
        this.onError(error);
      }
      return false;
    }
  }

  /**
   * Start collecting statistics from the peer connection
   */
  startStatsInterval() {
    // Clear any existing interval
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
    }

    this.statsInterval = setInterval(async () => {
      if (!this.peerConnection) return;

      try {
        const stats = await this.peerConnection.getStats();
        let bytesReceived = 0;
        let bytesSent = 0;
        let audioLevel = 0;

        stats.forEach((report) => {
          if (report.type === "inbound-rtp" && report.kind === "audio") {
            bytesReceived = report.bytesReceived;
          } else if (
            report.type === "outbound-rtp" &&
            report.kind === "audio"
          ) {
            bytesSent = report.bytesSent;
          } else if (
            report.type === "media-source" &&
            report.kind === "audio"
          ) {
            if ("audioLevel" in report) {
              audioLevel = report.audioLevel;
            }
          }
        });

        // Calculate bitrates
        const bytesReceivedDelta = bytesReceived - this.lastBytesReceived;
        const bytesSentDelta = bytesSent - this.lastBytesSent;

        const receiveBitrate = (bytesReceivedDelta * 8) / 1000; // kbps
        const sendBitrate = (bytesSentDelta * 8) / 1000; // kbps

        this.lastBytesReceived = bytesReceived;
        this.lastBytesSent = bytesSent;

        // Emit statistics
        if (this.onStateChange) {
          this.onStateChange({
            type: "stats",
            stats: {
              receiveBitrate,
              sendBitrate,
              audioLevel,
              bytesReceived,
              bytesSent,
            },
          });
        }
      } catch (error) {
        console.error("Error getting stats:", error);
      }
    }, 1000);
  }

  /**
   * Close the WebRTC connection
   */
  closeConnection() {
    // Stop stats collection
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
      this.statsInterval = null;
    }

    // Close data channel
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }

    // Stop local media tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
      this.localStream = null;
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }

    // Update state
    const wasConnected = this.connected;
    this.connected = false;
    this.connecting = false;

    // Trigger disconnected callback
    if (wasConnected && this.onDisconnected) {
      this.onDisconnected();
    }
  }
}

export default WebRTCManager;
