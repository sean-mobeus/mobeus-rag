// MP3StreamPlayer.jsx - Refined version
export default class MP3StreamPlayer {
  constructor() {
    this.audioElement = new Audio();
    this.audioElement.preload = "auto";

    // Add a small amount of initial buffering to prevent garbled audio at start
    this.audioElement.addEventListener(
      "canplaythrough",
      this.handleCanPlayThrough.bind(this)
    );
    this.audioElement.addEventListener(
      "loadedmetadata",
      this.handleLoadedMetadata.bind(this)
    );
    this.audioElement.addEventListener("error", this.handleError.bind(this));

    this.onFirstChunkCallback = null;
    this.firstChunkReceived = false;
    this.isPlaying = false;
    this.initialBufferingComplete = false;
    this.bufferingStartTime = null;
  }

  get element() {
    return this.audioElement;
  }

  setOnFirstChunkCallback(callback) {
    this.onFirstChunkCallback = callback;
  }

  handleLoadedMetadata() {
    console.log("Metadata loaded");

    // Trigger first chunk callback if not already done
    if (!this.firstChunkReceived && this.onFirstChunkCallback) {
      this.firstChunkReceived = true;
      this.onFirstChunkCallback();
    }

    // Start the initial buffering timer
    this.bufferingStartTime = Date.now();
  }

  handleCanPlayThrough() {
    if (!this.initialBufferingComplete) {
      const bufferingTime =
        Date.now() - (this.bufferingStartTime || Date.now());
      console.log(`Initial buffering complete after ${bufferingTime}ms`);
      this.initialBufferingComplete = true;

      // Start playback after initial buffering
      this.startPlayback();
    }
  }

  handleError(event) {
    // Only log real errors, not cleanup errors
    if (this.audioElement.error && this.audioElement.error.code !== 4) {
      console.error("Audio error:", this.audioElement.error);
    }
  }

  startPlayback() {
    if (!this.isPlaying) {
      console.log("Starting playback");
      this.isPlaying = true;

      // Play with a slight delay to ensure buffering
      setTimeout(() => {
        this.audioElement.play().catch((err) => {
          // Only log real errors, not user-initiated pauses
          if (err.name !== "AbortError" && err.name !== "NotAllowedError") {
            console.error("Error starting playback:", err);
          }
        });
      }, 100);
    }
  }

  async playStream(url) {
    try {
      // Reset state
      this.stop();
      this.firstChunkReceived = false;
      this.isPlaying = false;
      this.initialBufferingComplete = false;

      console.log("Starting audio stream fetch:", url);

      // Set source to streaming endpoint
      this.audioElement.src = url;

      // This tells the browser to start loading immediately
      this.audioElement.load();

      // For calculating buffering
      const checkBuffering = setInterval(() => {
        if (
          !this.audioElement ||
          !this.audioElement.buffered ||
          !this.audioElement.buffered.length
        )
          return;

        const bufferedEnd = this.audioElement.buffered.end(
          this.audioElement.buffered.length - 1
        );
        const bufferedSeconds = bufferedEnd.toFixed(2);

        // Since we're streaming, we can report the actual seconds buffered
        // instead of a percentage (which doesn't make sense with infinite duration)
        console.log(`Audio buffered: ${bufferedSeconds} seconds`);

        // If we have a good buffer and haven't started playing, start now
        if (
          bufferedSeconds > 0.5 &&
          !this.isPlaying &&
          !this.initialBufferingComplete
        ) {
          this.startPlayback();
        }
      }, 1000);

      return new Promise((resolve, reject) => {
        // Clean up the interval when done
        const cleanup = () => {
          clearInterval(checkBuffering);
        };

        this.audioElement.onended = () => {
          cleanup();
          resolve();
        };

        this.audioElement.onerror = (e) => {
          // Only reject for real errors
          if (this.audioElement.error && this.audioElement.error.code !== 4) {
            cleanup();
            reject(this.audioElement.error);
          }
        };
      });
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Error in streaming audio:", err);
      }
      return Promise.reject(err);
    }
  }

  pause() {
    if (this.audioElement) {
      this.audioElement.pause();
      this.isPlaying = false;
    }
  }

  resume() {
    if (this.audioElement && !this.isPlaying) {
      this.audioElement.play().catch((err) => {
        console.error("Error resuming playback:", err);
      });
      this.isPlaying = true;
    }
  }

  stop() {
    this.isPlaying = false;

    if (this.audioElement) {
      this.audioElement.pause();

      // Clear the src attribute
      if (this.audioElement.src) {
        this.audioElement.removeAttribute("src");
        this.audioElement.load(); // This resets the Audio element's state
      }
    }
  }
}
