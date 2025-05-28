import { EventEmitter } from "events";
import { BACKEND_BASE_URL } from "../config";

/**
 * Client for realtime chat via backend websocket proxy.
 */
class OpenAIRealtimeClient extends EventEmitter {
  constructor() {
    super();
    this.socket = null;
    this.connected = false;
    this.connecting = false;
    this.backendUrl = window.location.origin;
    this.currentStrategy = "auto";
    this.strategyChangeCallbacks = [];
  }

  /**
   * Tool Strategy Control Methods
   * Send strategy update to backend
   */
  sendStrategyUpdate(strategy) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("⚠️ Cannot send strategy update - WebSocket not ready");
      return false;
    }

    const strategyMessage = {
      type: "strategy_update",
      strategy: strategy,
      timestamp: new Date().toISOString(),
    };

    this.socket.send(JSON.stringify(strategyMessage));
    this.currentStrategy = strategy;

    console.log(`🎛️ Strategy update sent: ${strategy}`);

    // Notify callbacks
    this.strategyChangeCallbacks.forEach((callback) => {
      try {
        callback(strategy);
      } catch (error) {
        console.error("Error in strategy change callback:", error);
      }
    });

    return true;
  }

  /**
   * Get current strategy
   */
  getCurrentStrategy() {
    return this.currentStrategy;
  }

  /**
   * Register callback for strategy changes
   */
  onStrategyChange(callback) {
    if (typeof callback === "function") {
      this.strategyChangeCallbacks.push(callback);
    }
  }

  /**
   * Remove strategy change callback
   */
  offStrategyChange(callback) {
    const index = this.strategyChangeCallbacks.indexOf(callback);
    if (index > -1) {
      this.strategyChangeCallbacks.splice(index, 1);
    }
  }

  /** Connect to backend websocket */
  async connect(
    userUuid = null,
    instructions = null,
    initialStrategy = "auto"
  ) {
    if (this.connecting || this.connected) return false;
    this.connecting = true;
    this.userUuid = userUuid;
    this.currentStrategy = initialStrategy;
    try {
      // Initialize audio context early
      await this.initializeAudio();
      // Include strategy in connection URL
      const protocol = this.backendUrl.startsWith("https") ? "wss" : "ws";
      const url = `${protocol}://${
        window.location.host
      }/api/realtime/chat?user_uuid=${encodeURIComponent(
        userUuid || ""
      )}&instructions=${encodeURIComponent(
        instructions || ""
      )}&tool_strategy=${encodeURIComponent(initialStrategy)}`;

      console.log("🔗 Connecting to backend WebSocket:", url);
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.connected = true;
        this.connecting = false;
        this.emit("connected");
      };
    } catch (error) {
      this.socket.onerror = (e) => {
        this.emit("error", e);
      };

      this.socket.onclose = () => {
        this.connected = false;
        this.connecting = false;
        this.emit("disconnected");
      };

      this.socket.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          this.handleRealtimeEvent(msg);
        } catch (err) {
          console.error("Bad realtime message", err);
        }
      };

      return true;
    }
  }

  /** Send event to backend */
  sendEvent(event) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(event));
      return true;
    }
    console.warn("WebSocket not ready", event);
    return false;
  }

  /** Send user text */
  sendText(text) {
    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "text", text }],
      },
    });
    this.sendEvent({
      type: "response.create",
      response: { modalities: ["text", "audio"] },
    });
  }

  cancelResponse() {
    this.sendEvent({ type: "response.cancel" });
  }

  disconnect() {
    if (this.socket) this.socket.close();
    this.connected = false;
    this.connecting = false;
  }

  isConnected() {
    return this.connected;
  }

  getStatus() {
    return { connected: this.connected, connecting: this.connecting };
  }

  /** Handle events coming from backend/OpenAI */
  handleRealtimeEvent(event) {
    const { type } = event;

    // Handle strategy-related events
    if (type === "strategy_updated") {
      console.log("🎛️ Strategy update confirmed:", event.strategy);
      this.currentStrategy = event.strategy;
      this.emit("strategy.updated", event);

      // Notify callbacks
      this.strategyChangeCallbacks.forEach((callback) => {
        try {
          callback(event.strategy);
        } catch (error) {
          console.error("Error in strategy change callback:", error);
        }
      });
      return;
    }
    // Handle other event types
    switch (type) {
      case "session.created":
        this.emit("session.created", event.session);
        break;
      case "response.text.delta":
        this.emit("response.text.delta", event.delta);
        break;
      case "response.text.done":
        this.emit("response.text.done", event.text);
        this.emit("message.completed", { role: "assistant", text: event.text });
        break;
      case "response.audio.delta":
        this.emit("response.audio.delta", event);
        break;
      case "response.audio.done":
        this.emit("response.audio.done");
        break;
      case "conversation.item.completed":
        this.emit("message.completed", {
          role: event.item.role,
          text: event.item.text || "",
        });
        break;
      case "error":
        this.emit("error", event.error);
        break;
      default:
        this.emit(type, event);
        break;
    }
  }
  /**
   * Tool Strategy Presets
   */

  static TOOL_STRATEGIES = {
    auto: {
      label: "Auto",
      color: "blue",
      description: "Let AI decide when to use tools (balanced approach)",
    },
    conservative: {
      label: "Minimal",
      color: "green",
      description: "Prefer direct responses, minimal tool usage",
    },
    aggressive: {
      label: "Comprehensive",
      color: "purple",
      description: "Proactive tool usage for detailed responses",
    },
    none: {
      label: "Direct Only",
      color: "gray",
      description: "Never use tools, direct responses only",
    },
    required: {
      label: "Always Search",
      color: "red",
      description: "Always use tools before responding",
    },
  };

  /**
   * Get strategy information
   */
  getStrategyInfo(strategy) {
    return WebSocketRealtimeClient.TOOL_STRATEGIES[strategy] || null;
  }

  /**
   * Get available strategies
   */
  getAvailableStrategies() {
    return WebSocketRealtimeClient.TOOL_STRATEGIES;
  }
}

export default new OpenAIRealtimeClient();
