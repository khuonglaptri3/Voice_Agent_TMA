class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.inputBuffer = [];
    this.sourcePosition = 0;
    this.pendingSamples = [];
  }

  resampleToTarget(samples) {
    const ratio = sampleRate / this.targetSampleRate;
    for (let i = 0; i < samples.length; i += 1) {
      this.inputBuffer.push(samples[i]);
    }

    const resampled = [];
    while (this.sourcePosition + 1 < this.inputBuffer.length) {
      const lower = Math.floor(this.sourcePosition);
      const upper = lower + 1;
      const fraction = this.sourcePosition - lower;
      const lowSample = this.inputBuffer[lower];
      const highSample = this.inputBuffer[upper];
      resampled.push(lowSample + (highSample - lowSample) * fraction);
      this.sourcePosition += ratio;
    }

    const consumedSamples = Math.min(
      Math.floor(this.sourcePosition),
      this.inputBuffer.length - 1,
    );
    if (consumedSamples > 0) {
      this.inputBuffer.splice(0, consumedSamples);
      this.sourcePosition -= consumedSamples;
    }

    return resampled;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input.length) return true;

    const resampled = this.resampleToTarget(input[0]);
    for (const sample of resampled) {
      this.pendingSamples.push(sample);
    }

    while (this.pendingSamples.length >= 512) {
      const frameSamples = this.pendingSamples.splice(0, 512);
      const frame = new Int16Array(512);
      for (let i = 0; i < frameSamples.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, frameSamples[i]));
        frame[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      this.port.postMessage(frame.buffer, [frame.buffer]);
    }

    return true;
  }
}

registerProcessor("audio-capture-processor", AudioCaptureProcessor);