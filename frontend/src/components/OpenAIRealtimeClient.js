import { EventEmitter } from "events";

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
  }

  /** Connect to backend websocket */
  async connect(userUuid = null, instructions = null) {
    if (this.connecting || this.connected) return false;
    this.connecting = true;
    const protocol = this.backendUrl.startsWith("https") ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/api/realtime/chat?user_uuid=${encodeURIComponent(
      userUuid || ""
    )}&instructions=${encodeURIComponent(instructions || "")}`;
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.connected = true;
      this.connecting = false;
      this.emit("connected");
    };

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
    this.sendEvent({ type: "response.create", response: { modalities: ["text", "audio"] } });
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
        this.emit("message.completed", { role: event.item.role, text: event.item.text || "" });
        break;
      case "error":
        this.emit("error", event.error);
        break;
      default:
        this.emit(type, event);
        break;
    }
  }
}

export default new OpenAIRealtimeClient();
