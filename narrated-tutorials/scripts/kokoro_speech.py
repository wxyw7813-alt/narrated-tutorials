"""Optional offline helper. Models must already exist; never downloads weights."""
import argparse
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    for key in ('model', 'voices', 'text-file', 'output'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--voice', default='af_heart')
    p.add_argument('--speed', type=float, default=.98)
    a = p.parse_args()
    import numpy as np
    import soundfile as sf
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    ort.disable_telemetry_events()
    opt = ort.SessionOptions()
    opt.intra_op_num_threads = 2
    opt.inter_op_num_threads = 1
    session = ort.InferenceSession(a.model, sess_options=opt, providers=['CPUExecutionProvider'])
    model = Kokoro.from_session(session, a.voices)
    samples, rate = model.create(Path(a.text_file).read_text(encoding='utf-8'),
                                 voice=a.voice, speed=a.speed, lang='en-us')
    samples = np.asarray(samples, dtype=np.float32)
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError('Kokoro returned empty or invalid audio')
    peak = float(np.max(np.abs(samples)))
    if peak > .97:
        samples *= .97 / peak
    sf.write(a.output, samples, rate, subtype='PCM_16')

if __name__ == '__main__':
    main()
