class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.pendingSamples = [];
  }

  resampleToTarget(samples) {
    const actualRate = sampleRate;
    const ratio = actualRate / this.targetSampleRate;
    const targetLength = Math.ceil(samples.length / ratio);
    const resampled = new Float32Array(targetLength);

    for (let i = 0; i < targetLength; i += 1) {
      const sourceIndex = i * ratio;
      const lower = Math.floor(sourceIndex);
      const upper = Math.min(samples.length - 1, lower + 1);
      const t = sourceIndex - lower;
      const lo = samples[lower] || 0;
      const hi = samples[upper] || 0;
      resampled[i] = lo + (hi - lo) * t;
    }

    return resampled;
  }

  process(inputs, _outputs, _parameters) {
    const input = inputs[0];

    if (!input || !input.length) {
      return true;
    }

    const channel = input[0];
    const resampled = this.resampleToTarget(channel);

    for (let i = 0; i < resampled.length; i += 1) {
      this.pendingSamples.push(resampled[i]);

      if (this.pendingSamples.length >= 512) {
        const frame = new Int16Array(512);

        for (let j = 0; j < 512; j += 1) {
          const sample = Math.max(-1, Math.min(1, this.pendingSamples.shift()));
          frame[j] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
        }

        this.port.postMessage(frame.buffer, [frame.buffer]);
      }
    }

    return true;
  }
}

registerProcessor("audio-capture-processor", AudioCaptureProcessor);
