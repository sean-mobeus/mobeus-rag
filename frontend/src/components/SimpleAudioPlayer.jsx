// SimpleAudioPlayer.jsx - A simplified, robust player
export default class SimpleAudioPlayer {
  constructor() {
    this.audioElement = new Audio();
    this.firstChunkCallback = null;
    this.firstChunkReceived = false;
  }

  get element() {
    return this.audioElement;
  }

  setOnFirstChunkCallback(callback) {
    this.firstChunkCallback = callback;
  }

  async playStream(url) {
    try {
      // Reset state
      this.stop();
      this.firstChunkReceived = false;

      // Set up listeners first before setting the source
      this.setupListeners();

      console.log("Starting audio stream fetch:", url);

      // Set source to streaming endpoint
      this.audioElement.src = url;

      // Start loading
      this.audioElement.load();

      // Return a promise that resolves when playback ends
      return new Promise((resolve, reject) => {
        this.audioElement.onended = resolve;
        this.audioElement.onerror = (e) => {
          // Ignore empty src errors which happen during cleanup
          if (this.audioElement.error && this.audioElement.error.code !== 4) {
            reject(this.audioElement.error);
          }
        };
      });
    } catch (err) {
      console.error("Error in streaming audio:", err);
      return Promise.reject(err);
    }
  }

  setupListeners() {
    // Handle first data arrival (first chunk received)
    const handleDataArrival = () => {
      if (!this.firstChunkReceived && this.firstChunkCallback) {
        this.firstChunkReceived = true;
        this.firstChunkCallback();
      }
    };

    // Track loading progress
    this.audioElement.addEventListener("loadedmetadata", handleDataArrival);
    this.audioElement.addEventListener("loadeddata", () =>
      console.log("Audio data loaded")
    );

    // Start playback when we can
    this.audioElement.addEventListener("canplay", () => {
      console.log("Audio can be played");
      this.audioElement.play().catch((err) => {
        // Ignore user-initiated interruptions
        if (err.name !== "AbortError" && err.name !== "NotAllowedError") {
          console.error("Error starting playback:", err);
        }
      });
    });

    // Monitor buffering
    this.audioElement.addEventListener("progress", () => {
      if (this.audioElement.buffered && this.audioElement.buffered.length) {
        const bufferedEnd = this.audioElement.buffered.end(
          this.audioElement.buffered.length - 1
        );
        console.log(`Buffered: ${bufferedEnd.toFixed(2)} seconds`);
      }
    });

    // Handle playback issues
    this.audioElement.addEventListener("waiting", () =>
      console.log("Waiting for more data...")
    );
    this.audioElement.addEventListener("playing", () =>
      console.log("Playback started/resumed")
    );
    this.audioElement.addEventListener("pause", () =>
      console.log("Playback paused")
    );
  }

  pause() {
    if (this.audioElement) {
      this.audioElement.pause();
    }
  }

  resume() {
    if (this.audioElement) {
      this.audioElement.play().catch((err) => {
        console.error("Error resuming playback:", err);
      });
    }
  }

  stop() {
    if (this.audioElement) {
      this.audioElement.pause();

      // Clear event listeners to prevent memory leaks
      this.audioElement.onended = null;
      this.audioElement.onerror = null;

      // Clear the source
      this.audioElement.src = "";

      // Reset the audio element
      try {
        this.audioElement.load();
      } catch (e) {
        // Ignore load errors during cleanup
      }
    }
  }
}
