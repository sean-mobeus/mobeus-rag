// OptimizedAudioPlayer.jsx - Faster playback with less buffering
export default class OptimizedAudioPlayer {
  constructor() {
    this.audioElement = new Audio();

    // Critical: Set to true to start playing as soon as possible
    this.audioElement.autoplay = true;

    // Reduce initial buffering requirements
    this.audioElement.preload = "auto";

    // Set minimal buffering (play as soon as possible)
    // These properties may not be supported in all browsers, but when they are, they help
    if ("fastSeek" in this.audioElement) {
      this.audioElement.preservesPitch = false;
    }

    // Set up event tracking
    this.setupEventListeners();

    this.onFirstChunkCallback = null;
    this.firstAudioEvent = false;
    this.startTime = null;
    this.loadStartTime = null;
  }

  setupEventListeners() {
    // Track load timing
    this.audioElement.addEventListener("loadstart", () => {
      this.loadStartTime = Date.now();
      console.log("Audio: Load started");
    });

    // All of these can indicate first audio data has arrived
    const firstDataEvents = ["loadedmetadata", "canplay", "canplaythrough"];

    firstDataEvents.forEach((event) => {
      this.audioElement.addEventListener(
        event,
        () => {
          if (!this.firstAudioEvent && this.onFirstChunkCallback) {
            this.firstAudioEvent = true;
            const now = Date.now();
            const loadTime = now - (this.loadStartTime || now);
            console.log(
              `Audio: First data received (${event}) after ${loadTime}ms`
            );
            this.onFirstChunkCallback(loadTime);
          }
        },
        { once: true }
      ); // Only trigger once
    });

    // Log playback start
    this.audioElement.addEventListener(
      "playing",
      () => {
        const now = Date.now();
        const startupTime = now - (this.startTime || now);
        console.log(`Audio: Playback started after ${startupTime}ms`);
      },
      { once: true }
    );

    // Log errors
    this.audioElement.addEventListener("error", (e) => {
      if (this.audioElement.error && this.audioElement.error.code !== 4) {
        console.error("Audio error:", this.audioElement.error);
      }
    });
  }

  get element() {
    return this.audioElement;
  }

  setOnFirstChunkCallback(callback) {
    this.onFirstChunkCallback = callback;
  }

  async playStream(url) {
    try {
      // Reset state
      this.stop();
      this.startTime = Date.now();
      this.firstAudioEvent = false;

      console.log("Streaming audio from:", url);

      // Set the audio source directly (browser handles streaming)
      this.audioElement.src = url;

      // Start loading audio immediately
      this.audioElement.load();

      // Automatic playback happens based on the autoplay setting

      // Return a promise that resolves when audio finishes
      return new Promise((resolve, reject) => {
        this.audioElement.onended = resolve;
        this.audioElement.onerror = (e) => {
          if (this.audioElement.error && this.audioElement.error.code !== 4) {
            reject(this.audioElement.error);
          } else {
            // Don't reject for cleanup errors
            resolve();
          }
        };
      });
    } catch (err) {
      console.error("Error starting audio stream:", err);
      throw err;
    }
  }

  pause() {
    if (this.audioElement) {
      this.audioElement.pause();
    }
  }

  resume() {
    if (this.audioElement) {
      this.audioElement.play().catch((err) => {
        // Ignore user interaction errors
        if (err.name !== "AbortError" && err.name !== "NotAllowedError") {
          console.error("Error resuming playback:", err);
        }
      });
    }
  }

  stop() {
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.removeAttribute("src");
      this.audioElement.load(); // Reset the audio element
    }
  }
}
