// SimplifiedAudioPlayer.jsx - Uses a simpler and more compatible approach
export default class SimplifiedAudioPlayer {
  constructor() {
    this.audioElement = new Audio();
    this.audioElement.preload = "auto";
    this.isPlaying = false;
    this.buffer = [];
    this.totalSize = 0;
    this.abortController = null;
    this.fullAudioBlob = null;
    this.onFirstChunkCallback = null;
  }

  get element() {
    return this.audioElement;
  }

  setOnFirstChunkCallback(callback) {
    this.onFirstChunkCallback = callback;
  }

  async playStream(url) {
    try {
      this.stop();
      this.buffer = [];
      this.totalSize = 0;
      this.isPlaying = true;
      this.abortController = new AbortController();

      console.log("Starting audio stream fetch:", url);

      const response = await fetch(url, {
        signal: this.abortController.signal,
        headers: {
          Accept: "audio/ogg, audio/mpeg, audio/*", // Accept any audio format
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      console.log(
        "Stream response received, content-type:",
        response.headers.get("content-type")
      );
      const contentType = response.headers.get("content-type") || "audio/ogg";

      // Get a reader to read the stream
      const reader = response.body.getReader();
      let firstChunkProcessed = false;

      // Read all chunks from the stream
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          console.log("Stream complete, total size:", this.totalSize);
          break;
        }

        if (value && value.length > 0) {
          this.buffer.push(value);
          this.totalSize += value.length;

          // If this is the first chunk with data
          if (!firstChunkProcessed && this.onFirstChunkCallback) {
            firstChunkProcessed = true;
            this.onFirstChunkCallback();
          }

          // Start playback as soon as we have enough data
          // We'll use a 3-chunk minimum to ensure smooth playback
          if (this.buffer.length === 3) {
            this.playAudio(contentType);
          }
        }
      }

      // Play the complete audio if we haven't started yet
      if (this.buffer.length > 0 && !this.audioElement.src) {
        this.playAudio(contentType);
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Error in streaming audio:", err);
        throw err;
      }
    }
  }

  playAudio(contentType) {
    try {
      // Concatenate all chunks into a single Uint8Array
      const totalLength = this.buffer.reduce((acc, val) => acc + val.length, 0);
      const completeBuffer = new Uint8Array(totalLength);

      let offset = 0;
      for (const chunk of this.buffer) {
        completeBuffer.set(chunk, offset);
        offset += chunk.length;
      }

      // Create a blob from all the chunks
      this.fullAudioBlob = new Blob([completeBuffer], { type: contentType });
      const audioUrl = URL.createObjectURL(this.fullAudioBlob);

      // Clean up any previous audio
      if (this.audioElement.src) {
        URL.revokeObjectURL(this.audioElement.src);
      }

      console.log(`Playing audio (${(totalLength / 1024).toFixed(2)} KB)`);

      // Set the source and play
      this.audioElement.src = audioUrl;
      this.audioElement.play().catch((error) => {
        console.error("Error playing audio:", error);

        // If it fails with opus/ogg, try with mp3 as fallback
        if (contentType.includes("ogg") || contentType.includes("opus")) {
          console.log("Trying fallback format...");
          this.fullAudioBlob = new Blob([completeBuffer], {
            type: "audio/mpeg",
          });
          const fallbackUrl = URL.createObjectURL(this.fullAudioBlob);

          if (this.audioElement.src) {
            URL.revokeObjectURL(this.audioElement.src);
          }

          this.audioElement.src = fallbackUrl;
          this.audioElement.play().catch((secondError) => {
            console.error("Fallback playback also failed:", secondError);
          });
        }
      });
    } catch (error) {
      console.error("Error creating audio blob:", error);
    }
  }

  stop() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    if (this.audioElement) {
      this.audioElement.pause();
      if (this.audioElement.src) {
        URL.revokeObjectURL(this.audioElement.src);
        this.audioElement.src = "";
      }
    }

    if (this.fullAudioBlob) {
      this.fullAudioBlob = null;
    }

    this.isPlaying = false;
    this.buffer = [];
    this.totalSize = 0;
  }
}
