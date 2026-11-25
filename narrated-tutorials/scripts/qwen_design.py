"""Optional Apple Silicon local voice design. Uses existing local model files only."""
import argparse
import json
import os
from pathlib import Path

# Model loading must not make an implicit download or telemetry request.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--jobs', required=True, help='JSON list of local synthesis jobs')
    a = p.parse_args()
    jobs = json.loads(Path(a.jobs).read_text(encoding='utf-8'))
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    model = None
    current = None
    for job in jobs:
        path = Path(job['model']).expanduser().resolve()
        if not path.is_dir() or not (path/'model.safetensors').is_file() or not (path/'speech_tokenizer/model.safetensors').is_file():
            raise ValueError('Prepare the local Qwen VoiceDesign model and speech tokenizer first.')
        if current != path:
            model = load_model(str(path))
            current = path
        mx.random.seed(int(job.get('seed', 42)))
        text = job['text'].strip()
        # Bound generation; hitting the cap is a failed take, not accepted truncation.
        cap = min(2000, max(384, len(text)*10))
        print('Generating', job.get('id','voice'), flush=True)
        chunks = list(model.generate_voice_design(text=text, instruct=job['instruct'],
                      language='Chinese', temperature=float(job.get('temperature',.7)),
                      max_tokens=cap, verbose=False))
        if not chunks:
            raise ValueError('Voice design returned no audio')
        audio = np.concatenate([np.asarray(c.audio).reshape(-1) for c in chunks]).astype(np.float32)
        rate = int(chunks[0].sample_rate)
        if not len(audio) or not np.isfinite(audio).all() or np.max(np.abs(audio)) < .0001:
            raise ValueError('Invalid or silent voice-design output')
        if len(audio)/rate >= cap/12.5-.4:
            raise ValueError('Generation reached token cap; split the narration into shorter scenes')
        peak = float(np.max(np.abs(audio)))
        if peak > .97:
            audio *= .97/peak
        dest = Path(job['output']); dest.parent.mkdir(parents=True,exist_ok=True)
        sf.write(dest, audio, rate, subtype='PCM_16')
        print(json.dumps({'id':job.get('id'),'seconds':len(audio)/rate,'output':str(dest)},ensure_ascii=False),flush=True)
        mx.clear_cache()

if __name__ == '__main__':
    main()
