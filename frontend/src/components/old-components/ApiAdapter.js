// ApiAdapter.js - Handles API compatibility
import { v4 as uuidv4 } from "uuid"; // You may need to install this package

class ApiAdapter {
  constructor(baseUrl) {
    this.baseUrl = baseUrl || import.meta.env.VITE_API_BASE || "";
    this.uuid = localStorage.getItem("uuid") || this._generateUuid();
    this._saveUuid(this.uuid);
  }

  // Generate a UUID for session tracking
  _generateUuid() {
    let uuid;
    try {
      // Try using crypto API first
      uuid = crypto.randomUUID();
    } catch (e) {
      // Fallback to other methods
      try {
        // Use uuid package if available
        uuid = uuidv4();
      } catch (e2) {
        // Simple fallback
        uuid = "user-" + Math.random().toString(36).substring(2, 15);
      }
    }
    return uuid;
  }

  // Save UUID to localStorage
  _saveUuid(uuid) {
    localStorage.setItem("uuid", uuid);
    this.uuid = uuid;
  }

  // Get stored UUID or generate new one
  getUuid() {
    if (!this.uuid) {
      this.uuid = this._generateUuid();
      this._saveUuid(this.uuid);
    }
    return this.uuid;
  }

  // Send query to backend with necessary UUID
  async sendQuery(queryText, options = {}) {
    const endpoint = options.streaming
      ? `${this.baseUrl}/stream-query`
      : `${this.baseUrl}/api/query`;

    // Create request payload
    const payload = {
      query: queryText,
      uuid: this.getUuid(),
      ...options.extraData,
    };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        // Try fallback endpoint if main fails
        if (options.allowFallback && !options.isFallback) {
          console.warn(`Primary endpoint ${endpoint} failed, trying fallback`);
          return this.sendQuery(queryText, {
            ...options,
            streaming: !options.streaming,
            isFallback: true,
          });
        }

        const errorData = await response.json();
        throw new Error(
          `API Error (${response.status}): ${JSON.stringify(errorData)}`
        );
      }

      if (options.streaming) {
        // Return the response directly for streaming to handle
        return response;
      } else {
        // Parse JSON for non-streaming responses
        return await response.json();
      }
    } catch (error) {
      console.error("API request failed:", error);

      // Try fallback if enabled
      if (options.allowFallback && !options.isFallback) {
        console.warn("Error occurred, trying fallback endpoint");
        return this.sendQuery(queryText, {
          ...options,
          streaming: !options.streaming,
          isFallback: true,
        });
      }

      throw error;
    }
  }
}

// Create singleton instance
const apiAdapter = new ApiAdapter();
export default apiAdapter;
