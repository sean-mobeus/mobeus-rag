export default class StreamedAudioPlayer {
  constructor() {
    this.audioElement = new Audio();
    this.mediaSource = new MediaSource();
    this.sourceBuffer = null;
    this.mimeCodec = "audio/webm; codecs=opus";
    this.audioElement.src = URL.createObjectURL(this.mediaSource);
  }

  get element() {
    return this.audioElement;
  }

  async playStream(url) {
    return new Promise((resolve, reject) => {
      this.mediaSource.addEventListener("sourceopen", async () => {
        try {
          this.sourceBuffer = this.mediaSource.addSourceBuffer(this.mimeCodec);
          this.sourceBuffer.mode = "sequence";

          const res = await fetch(url);
          const reader = res.body.getReader();

          let hasAppended = false;

          const process = async () => {
            while (true) {
              const { value, done } = await reader.read();
              if (done) break;

              if (
                this.sourceBuffer &&
                value &&
                this.mediaSource.readyState === "open"
              ) {
                await this.appendBufferAsync(value);

                // 👇 Play after first buffer is safely added
                if (!hasAppended) {
                  this.audioElement.play().catch(reject);
                  hasAppended = true;
                }
              }
            }

            if (this.mediaSource.readyState === "open") {
              this.mediaSource.endOfStream();
            }

            resolve();
          };

          process().catch(reject);
        } catch (err) {
          reject(err);
        }
      });
    });
  }

  appendBufferAsync(chunk) {
    return new Promise((resolve) => {
      this.sourceBuffer.addEventListener("updateend", () => resolve(), {
        once: true,
      });
      this.sourceBuffer.appendBuffer(chunk);
    });
  }

  stop() {
    this.audioElement.pause();
    this.audioElement.currentTime = 0;
  }
}
