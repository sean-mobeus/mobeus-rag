// StreamedAudioPlayerV2.jsx
export default class StreamedAudioPlayerV2 {
  constructor() {
    this.audioElement = new Audio();
    this.currentUrl = null;
    this.playing = false;
    this.abortController = null;
    this.queuedChunks = [];
    this.processingChunk = false;
    this.chunkInterval = null;
    this.latencyOptimized = true; // Set to true for lowest latency
  }

  get element() {
    return this.audioElement;
  }

  async playStream(url) {
    this.stop();
    this.abortController = new AbortController();
    this.playing = true;
    this.queuedChunks = [];

    try {
      // Fetch the streaming audio
      console.log("Fetching from URL:", url);
      const response = await fetch(url, {
        signal: this.abortController.signal,
        headers: {
          Accept: "audio/ogg, audio/webm", // Accept both formats for compatibility
        },
      });

      if (!response.ok) {
        throw new Error(
          `Server responded with ${response.status}: ${response.statusText} for URL: ${url}`
        );
      }

      console.log(
        "Stream response received, content-type:",
        response.headers.get("content-type")
      );

      // Set up audio element event handlers
      this.setupAudioEvents();

      // Get reader from response body
      const reader = response.body.getReader();

      // Start processing chunks as they arrive
      let firstChunk = true;
      let accumulatedChunks = [];

      // Process incoming chunks
      while (this.playing) {
        const { done, value } = await reader.read();

        if (done) {
          console.log("Stream complete");
          break;
        }

        if (!value || value.length === 0) continue;

        if (firstChunk && this.latencyOptimized) {
          // Play the very first chunk immediately for lowest latency
          this.playChunk([value]);
          firstChunk = false;
        } else {
          // Queue additional chunks
          accumulatedChunks.push(value);

          // Process accumulated chunks in larger batches for stability
          if (accumulatedChunks.length >= 2 || !this.latencyOptimized) {
            this.queuedChunks.push(accumulatedChunks);
            accumulatedChunks = [];

            // Start processing queue if not already processing
            if (!this.processingChunk) {
              this.processNextChunk();
            }
          }
        }
      }

      // Process any remaining chunks
      if (accumulatedChunks.length > 0) {
        this.queuedChunks.push(accumulatedChunks);
        if (!this.processingChunk) {
          this.processNextChunk();
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Error in audio streaming:", err);
      }
      this.playing = false;
      throw err; // Re-throw so we can handle it in the wrapper
    }
  }

  setupAudioEvents() {
    // Clear previous event listeners
    this.audioElement.onended = null;
    this.audioElement.onerror = null;

    // Process the next chunk when current audio ends
    this.audioElement.onended = () => {
      if (this.playing && this.queuedChunks.length > 0) {
        this.processNextChunk();
      }
    };

    this.audioElement.onerror = (err) => {
      console.error("Audio playback error:", err);
      this.processNextChunk(); // Try the next chunk on error
    };
  }

  processNextChunk() {
    if (!this.playing || this.queuedChunks.length === 0) {
      this.processingChunk = false;
      return;
    }

    this.processingChunk = true;
    const nextChunks = this.queuedChunks.shift();
    this.playChunk(nextChunks);
  }

  playChunk(chunks) {
    try {
      // Determine MIME type based on server response
      // Default to 'audio/ogg' which is what OpenAI actually sends
      const mimeType = "audio/ogg; codecs=opus";

      // Create blob and URL with the correct MIME type
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);

      // Revoke previous URL to prevent memory leaks
      if (this.currentUrl) {
        URL.revokeObjectURL(this.currentUrl);
      }

      this.currentUrl = url;
      this.audioElement.src = url;

      // Play the chunk
      console.log("Playing chunk, blob size:", blob.size);
      this.audioElement
        .play()
        .then(() => {
          // Set up a timer to process next chunk before this one ends
          // to minimize gaps between audio segments
          if (this.chunkInterval) {
            clearTimeout(this.chunkInterval);
          }

          // Process next chunk when we're near the end of current audio
          // This helps prevent gaps between audio segments
          const duration = this.audioElement.duration;
          if (!isNaN(duration) && duration > 0.1) {
            const timeToNextChunk = Math.max((duration - 0.1) * 1000, 10);
            this.chunkInterval = setTimeout(() => {
              if (this.queuedChunks.length > 0) {
                this.processNextChunk();
              } else {
                this.processingChunk = false;
              }
            }, timeToNextChunk);
          } else {
            // If we can't determine duration, process next chunk immediately
            if (this.queuedChunks.length > 0) {
              this.processNextChunk();
            } else {
              this.processingChunk = false;
            }
          }
        })
        .catch((err) => {
          console.error("Error playing audio chunk:", err);
          this.processingChunk = false;
        });
    } catch (err) {
      console.error("Error creating audio blob:", err);
      this.processingChunk = false;
    }
  }

  stop() {
    this.playing = false;

    if (this.chunkInterval) {
      clearTimeout(this.chunkInterval);
      this.chunkInterval = null;
    }

    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.onended = null;
      this.audioElement.onerror = null;

      if (this.currentUrl) {
        URL.revokeObjectURL(this.currentUrl);
        this.currentUrl = null;
      }

      this.audioElement.src = "";
    }

    this.queuedChunks = [];
    this.processingChunk = false;
  }
}
