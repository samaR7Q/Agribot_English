// Mic capture: downsample to 16 kHz mono 16-bit PCM and post ~100 ms chunks.
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;
    this.acc = 0;
    this.accN = 0;
    this.out = new Int16Array(1600);
    this.outN = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i];
      this.accN++;
      this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const s = Math.max(-1, Math.min(1, this.acc / this.accN));
        this.acc = 0;
        this.accN = 0;
        this.out[this.outN++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.outN === this.out.length) {
          this.port.postMessage(this.out.slice(0).buffer, []);
          this.outN = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
