/**
 * AudioVisualizer for rendering audio waveforms and frequency data
 */
class AudioVisualizer {
  /**
   * Create a new AudioVisualizer instance
   * @param {HTMLCanvasElement} canvas - Canvas element to draw on
   */
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.animationFrame = null;
    this.dataCache = new WeakMap();

    // Visualization settings
    this.barCount = 64;
    this.barWidth = 2;
    this.barSpacing = 2;
    this.barColor = "#0099ff";
    this.backgroundColor = "transparent";

    // Ensure canvas is properly sized
    this.resize();

    // Listen for resize events
    window.addEventListener("resize", this.resize.bind(this));
  }

  /**
   * Resize the canvas to match its display size
   */
  resize() {
    if (!this.canvas) return;

    const rect = this.canvas.getBoundingClientRect();

    if (rect.width > 0 && rect.height > 0) {
      this.canvas.width = rect.width;
      this.canvas.height = rect.height;
    }
  }

  /**
   * Start visualization with an analyzer node
   * @param {AnalyserNode} analyzer - Web Audio API analyzer node
   * @param {Object} options - Visualization options
   */
  start(analyzer, options = {}) {
    this.stop();

    if (!analyzer) {
      console.error("No analyzer node provided");
      return;
    }

    // Apply options
    if (options.barCount) this.barCount = options.barCount;
    if (options.barWidth) this.barWidth = options.barWidth;
    if (options.barSpacing) this.barSpacing = options.barSpacing;
    if (options.barColor) this.barColor = options.barColor;
    if (options.backgroundColor) this.backgroundColor = options.backgroundColor;

    // Start animation loop
    const drawLoop = () => {
      if (!this.canvas || !this.ctx || !analyzer) return;

      // Clear canvas
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

      // Fill background if set
      if (this.backgroundColor !== "transparent") {
        this.ctx.fillStyle = this.backgroundColor;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
      }

      // Get frequency data
      const bufferLength = analyzer.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyzer.getByteFrequencyData(dataArray);

      // Calculate bar dimensions
      const totalWidth =
        (this.barWidth + this.barSpacing) * this.barCount - this.barSpacing;
      const startX = (this.canvas.width - totalWidth) / 2;

      // Draw bars
      this.ctx.fillStyle = this.barColor;

      for (let i = 0; i < this.barCount; i++) {
        // Map dataArray indices to bars
        const dataIndex = Math.floor(i * (bufferLength / this.barCount));

        // Normalize value (0-255 -> 0-1)
        const value = dataArray[dataIndex] / 255;

        // Calculate bar height (min 1px for visibility)
        const barHeight = Math.max(1, value * this.canvas.height);

        // Draw bar
        const x = startX + i * (this.barWidth + this.barSpacing);
        const y = this.canvas.height - barHeight;

        this.ctx.fillRect(x, y, this.barWidth, barHeight);
      }

      // Continue animation
      this.animationFrame = requestAnimationFrame(drawLoop);
    };

    // Start the loop
    this.animationFrame = requestAnimationFrame(drawLoop);
  }

  /**
   * Draw a single frame of audio data
   * @param {Float32Array|Uint8Array} data - Audio data to visualize
   */
  drawFrame(data) {
    if (!this.canvas || !this.ctx || !data) return;

    // Clear canvas
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Fill background if set
    if (this.backgroundColor !== "transparent") {
      this.ctx.fillStyle = this.backgroundColor;
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    // Calculate bar dimensions
    const totalWidth =
      (this.barWidth + this.barSpacing) * this.barCount - this.barSpacing;
    const startX = (this.canvas.width - totalWidth) / 2;

    // Convert data to normalized array
    const normalizedData = this.normalizeArray(data, this.barCount);

    // Draw bars
    this.ctx.fillStyle = this.barColor;

    for (let i = 0; i < this.barCount; i++) {
      // Get normalized value (0-1)
      const value = normalizedData[i];

      // Calculate bar height (min 1px for visibility)
      const barHeight = Math.max(1, value * this.canvas.height);

      // Draw bar
      const x = startX + i * (this.barWidth + this.barSpacing);
      const y = this.canvas.height - barHeight;

      this.ctx.fillRect(x, y, this.barWidth, barHeight);
    }
  }

  /**
   * Stop the visualization animation
   */
  stop() {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  }

  /**
   * Normalize an array to a specific length
   * @param {Float32Array|Uint8Array} data - Input array
   * @param {number} targetLength - Desired output length
   * @returns {Float32Array} - Normalized array
   */
  normalizeArray(data, targetLength) {
    // Check if we have this in cache
    const cache = this.dataCache.get(data);
    if (cache && cache[targetLength]) {
      return cache[targetLength];
    }

    const result = new Float32Array(targetLength);
    const inputLength = data.length;

    if (targetLength <= inputLength) {
      // Downsampling
      const step = inputLength / targetLength;

      for (let i = 0; i < targetLength; i++) {
        const inputIndex = Math.floor(i * step);

        // Use peak value in this segment
        let maxValue = 0;
        const nextInputIndex = Math.min(
          inputLength - 1,
          Math.floor((i + 1) * step)
        );

        for (let j = inputIndex; j <= nextInputIndex; j++) {
          const value =
            data instanceof Uint8Array ? data[j] / 255 : Math.abs(data[j]);
          maxValue = Math.max(maxValue, value);
        }

        result[i] = maxValue;
      }
    } else {
      // Upsampling (linear interpolation)
      const step = (inputLength - 1) / (targetLength - 1);

      for (let i = 0; i < targetLength; i++) {
        const inputIndex = i * step;
        const lowerIndex = Math.floor(inputIndex);
        const upperIndex = Math.ceil(inputIndex);

        if (lowerIndex === upperIndex) {
          // Exact index
          result[i] =
            data instanceof Uint8Array
              ? data[lowerIndex] / 255
              : Math.abs(data[lowerIndex]);
        } else {
          // Interpolate
          const weight = inputIndex - lowerIndex;
          const lowerValue =
            data instanceof Uint8Array
              ? data[lowerIndex] / 255
              : Math.abs(data[lowerIndex]);
          const upperValue =
            data instanceof Uint8Array
              ? data[upperIndex] / 255
              : Math.abs(data[upperIndex]);

          result[i] = lowerValue * (1 - weight) + upperValue * weight;
        }
      }
    }

    // Store in cache
    if (!this.dataCache.has(data)) {
      this.dataCache.set(data, {});
    }
    this.dataCache.get(data)[targetLength] = result;

    return result;
  }

  /**
   * Destroy the visualizer and clean up resources
   */
  destroy() {
    this.stop();

    if (this.canvas) {
      this.ctx = null;
      this.canvas = null;
    }

    this.dataCache = new WeakMap();
    window.removeEventListener("resize", this.resize);
  }
}

export default AudioVisualizer;
