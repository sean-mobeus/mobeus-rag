/**
 * WebRTC Signaling Service
 *
 * Handles the WebRTC signaling process to establish peer connections
 * between the client and the voice assistant backend.
 */
class SignalingService {
  constructor(config = {}) {
    // Configuration
    this.config = {
      serverUrl: "/api/webrtc",
      reconnectInterval: 5000,
      maxReconnectAttempts: 5,
      ...config,
    };

    // State
    this.connected = false;
    this.connecting = false;
    this.reconnectAttempts = 0;
    this.sessionId = null;
    this.socket = null;

    // Event callbacks
    this.onConnected = null;
    this.onDisconnected = null;
    this.onMessage = null;
    this.onError = null;
  }

  /**
   * Connect to the signaling server
   */
  async connect() {
    if (this.connected || this.connecting) {
      return;
    }

    this.connecting = true;

    try {
      // Create WebSocket connection
      const socket = new WebSocket(this.config.serverUrl);

      // Set up event handlers
      socket.onopen = this.handleOpen.bind(this);
      socket.onclose = this.handleClose.bind(this);
      socket.onmessage = this.handleMessage.bind(this);
      socket.onerror = this.handleError.bind(this);

      this.socket = socket;
    } catch (error) {
      this.connecting = false;
      this.handleError(error);
    }
  }

  /**
   * Disconnect from the signaling server
   */
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.connected = false;
    this.connecting = false;
    this.reconnectAttempts = 0;
    this.sessionId = null;
  }

  /**
   * Send a message to the signaling server
   * @param {string} type - Message type
   * @param {Object} data - Message data
   */
  send(type, data = {}) {
    if (!this.connected || !this.socket) {
      return false;
    }

    try {
      const message = {
        type,
        data: {
          ...data,
          sessionId: this.sessionId,
        },
      };

      this.socket.send(JSON.stringify(message));
      return true;
    } catch (error) {
      this.handleError(error);
      return false;
    }
  }

  /**
   * Send an offer to the signaling server
   * @param {RTCSessionDescription} offer - WebRTC offer
   */
  sendOffer(offer) {
    return this.send("offer", { offer });
  }

  /**
   * Send an answer to the signaling server
   * @param {RTCSessionDescription} answer - WebRTC answer
   */
  sendAnswer(answer) {
    return this.send("answer", { answer });
  }

  /**
   * Send an ICE candidate to the signaling server
   * @param {RTCIceCandidate} candidate - WebRTC ICE candidate
   */
  sendCandidate(candidate) {
    return this.send("candidate", { candidate });
  }

  /**
   * Handle WebSocket open event
   */
  handleOpen() {
    this.connected = true;
    this.connecting = false;
    this.reconnectAttempts = 0;

    // Request a session
    this.send("join", { capabilities: ["audio"] });

    if (this.onConnected) {
      this.onConnected();
    }
  }

  /**
   * Handle WebSocket close event
   */
  handleClose(event) {
    const wasConnected = this.connected;

    this.connected = false;
    this.connecting = false;

    if (wasConnected && this.onDisconnected) {
      this.onDisconnected(event);
    }

    // Auto-reconnect if not a normal closure
    if (event.code !== 1000 && event.code !== 1001) {
      this.attemptReconnect();
    }
  }

  /**
   * Handle WebSocket message event
   */
  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);

      // Handle session initialization
      if (message.type === "session" && message.data?.sessionId) {
        this.sessionId = message.data.sessionId;
      }

      // Pass message to callback
      if (this.onMessage) {
        this.onMessage(message);
      }
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Handle WebSocket error event
   */
  handleError(error) {
    if (this.onError) {
      this.onError(error);
    }
  }

  /**
   * Attempt to reconnect to the signaling server
   */
  attemptReconnect() {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      return;
    }

    this.reconnectAttempts++;

    setTimeout(() => {
      this.connect();
    }, this.config.reconnectInterval);
  }
}

export default SignalingService;
