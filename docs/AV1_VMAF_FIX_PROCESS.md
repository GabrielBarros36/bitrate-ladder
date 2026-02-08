# AV1 VMAF Debugging and Fix Log

## Context: the reported issue
The investigation started when you reported that AV1 results looked wrong, with very low minimum VMAF values (sometimes near `0`) despite high bitrates. You shared a concrete example:

- Point: `p089`
- Codec: `av1`
- Resolution: `1920x1080`
- Bitrate: `7500 kbps`
- Observed: `vmaf_mean ~66.97`, `vmaf_min ~1.74`, `vmaf_p95 = 100.0`

That pattern (very high `p95` but very low mean/min) suggested potential frame matching or timing misalignment, not purely poor compression.

---

## Goal
Determine whether AV1 quality was truly bad or whether the VMAF pipeline was comparing the wrong frames, then implement a robust fix.

---

## Step-by-step timeline

### 1) Build a minimal repro config
Why: reduce variables and isolate AV1 vs H.264 under identical settings.

Command used:
```bash
cat > /tmp/debug_av1_config.json <<'JSON'
{
  "input": {
    "source_path": "./9910331-uhd_3840_2160_30fps.mp4"
  },
  "ladder": {
    "points": [
      {"bitrate_kbps": 7500, "width": 1920, "height": 1080, "codec": "h264"},
      {"bitrate_kbps": 7500, "width": 1920, "height": 1080, "codec": "av1"}
    ]
  },
  "vmaf": {
    "evaluation_resolution": "1920x1080"
  },
  "runtime": {
    "threads": 4,
    "work_dir": "./out/debug_work",
    "keep_temp": true
  },
  "output": {
    "report_path": "./out/debug_av1_report.json"
  }
}
JSON
```

Created file:
- `/tmp/debug_av1_config.json`

---

### 2) First run failed because of path resolution
Why: the config file was in `/tmp`, so relative `source_path` resolved from `/tmp`, not the repo.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" uv run python -m bitrate_ladder --config /tmp/debug_av1_config.json
```

Observed error:
- `Input source_path does not exist: /private/tmp/9910331-uhd_3840_2160_30fps.mp4`

Fix commands:
```bash
python3 - <<'PY'
from pathlib import Path
print((Path.cwd()/'9910331-uhd_3840_2160_30fps.mp4').resolve())
PY
```
```bash
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/debug_av1_config.json')
cfg=json.loads(p.read_text())
cfg['input']['source_path']=str((Path('/Users/gabrielromaninidebarros/Development/bitrate-ladder')/'9910331-uhd_3840_2160_30fps.mp4').resolve())
p.write_text(json.dumps(cfg,indent=2))
print('updated')
PY
```

---

### 3) Reproduce the bad AV1 score in isolation
Why: confirm the bug is real and reproducible.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" uv run python -m bitrate_ladder --config /tmp/debug_av1_config.json
```

Result summary:
- H.264 @ 7500: `vmaf_mean 98.8569`, `vmaf_min 92.0878`
- AV1 @ 7500: `vmaf_mean 66.9683`, `vmaf_min 1.7445`

Commands used to inspect:
```bash
python3 - <<'PY'
import json
from pathlib import Path
r=Path('/private/tmp/out/debug_av1_report.json')
report=json.loads(r.read_text())
for p in report['points']:
    print(p['id'],p['codec'],p['bitrate_kbps'],p['vmaf_mean'],p['vmaf_min'],p['vmaf_max'],p['vmaf_p95'],p['frame_count'])
    print('log',p.get('vmaf_log_path'))
PY
```

Files produced:
- `/private/tmp/out/debug_av1_report.json`
- `/private/tmp/out/debug_work/vmaf/p001.json`
- `/private/tmp/out/debug_work/vmaf/p002.json`
- `/private/tmp/out/debug_work/encodes/p001.mp4`
- `/private/tmp/out/debug_work/encodes/p002.mkv`

---

### 4) Inspect frame-level AV1 behavior
Why: determine whether low mean came from a few outliers or systematic mismatch.

Commands:
```bash
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/private/tmp/out/debug_work/vmaf/p002.json')
obj=json.loads(p.read_text())
vals=[fr['metrics']['vmaf'] for fr in obj['frames']]
print('count',len(vals))
print('min',min(vals),'max',max(vals))
for t in [5,10,20,40,60,80,90]:
    c=sum(1 for v in vals if v<t)
    print(f'<{t}:',c)
low=[(i,v) for i,v in enumerate(vals) if v<20]
print('first low',low[:30])
PY
```
```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('/private/tmp/out/debug_work/vmaf/p002.json').read_text())
vals=[fr['metrics']['vmaf'] for fr in obj['frames']]
for i in range(20,45):
    print(i,round(vals[i],3))
PY
```
```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('/private/tmp/out/debug_work/vmaf/p001.json').read_text())
vals=[fr['metrics']['vmaf'] for fr in obj['frames']]
for i in range(20,45):
    print(i,round(vals[i],3))
PY
```

Observation:
- AV1 had many sharp dips and near-alternating high/low behavior over short spans.
- H.264 did not show this behavior.

Interpretation:
- Strong signal for temporal misalignment (frame pairing issue), not purely coding quality.

---

### 5) Check stream timebases/frame-rate metadata
Why: mismatched timebases are a common cause of bad frame pairing.

Commands:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,r_frame_rate,nb_frames,time_base,duration -of json /private/tmp/out/debug_work/encodes/p002.mkv
```
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,r_frame_rate,time_base,duration -of json /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4
```

Observation:
- Source time base: `1/30000`
- AV1 encode (mkv) time base: `1/1000`

This increased confidence in timestamp/timeline mismatch.

---

### 6) Run manual VMAF experiments to isolate cause

#### 6.1) Add `settb=AVTB` only
Why: test whether common timebase alone fixes pairing.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -i /private/tmp/out/debug_work/encodes/p002.mkv -lavfi "[0:v]scale=1920:1080:flags=bicubic,settb=AVTB,setpts=PTS-STARTPTS[ref];[1:v]scale=1920:1080:flags=bicubic,settb=AVTB,setpts=PTS-STARTPTS[dist];[dist][ref]libvmaf=log_fmt=json:log_path=/tmp/manual_vmaf_av1_settb.json:n_threads=4" -f null -
```

Result: still ~`66.97` (not fixed).

Created file:
- `/tmp/manual_vmaf_av1_settb.json`

#### 6.2) Remux AV1 MKV to MP4
Why: test whether container/tbn specifics were the problem.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /private/tmp/out/debug_work/encodes/p002.mkv -c copy /tmp/p002_copy.mp4 && PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffprobe -v error -select_streams v:0 -show_entries stream=time_base,r_frame_rate,avg_frame_rate -of json /tmp/p002_copy.mp4
```

Then VMAF rerun against `/tmp/p002_copy.mp4` still gave ~`66.97`.

Created file:
- `/tmp/p002_copy.mp4`
- `/tmp/manual_vmaf_av1_mp4.json`

#### 6.3) Try different AV1 encoder modes (quality hypothesis)
Why: rule out “AV1 encode is truly bad at this setting” as primary cause.

Commands:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -an -vf scale=1920:1080:flags=lanczos -c:v libaom-av1 -b:v 7500k -maxrate 7500k -bufsize 15000k -cpu-used 6 -crf 20 -row-mt 1 /tmp/p002_crf20.mkv
```
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -an -vf scale=1920:1080:flags=lanczos -c:v libsvtav1 -preset 8 -b:v 7500k /tmp/p002_svt.mkv
```
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -an -vf scale=1920:1080:flags=lanczos -c:v libaom-av1 -b:v 7500k -maxrate 7500k -bufsize 15000k -cpu-used 6 -row-mt 1 -lag-in-frames 0 -auto-alt-ref 0 /tmp/p002_noalt.mkv
```

VMAF checks for these remained around ~`66`.

Created files:
- `/tmp/p002_crf20.mkv`
- `/tmp/p002_svt.mkv`
- `/tmp/p002_noalt.mkv`
- `/tmp/manual_vmaf_av1_crf20.json`
- `/tmp/manual_vmaf_av1_svt.json`
- `/tmp/manual_vmaf_av1_noalt.json`

Conclusion at this stage:
- Multiple AV1 encoder variants all giving the same suspicious pattern strongly suggested metric pipeline misalignment, not encoder weakness.

#### 6.4) PSNR diagnostic
Why: confirm timestamp mismatch at filter level.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -i /private/tmp/out/debug_work/encodes/p002.mkv -lavfi "[0:v]scale=1920:1080:flags=bicubic[ref];[1:v]scale=1920:1080:flags=bicubic,setpts=PTS-STARTPTS[dist];[dist][ref]psnr" -f null -
```

Critical clue in output:
- `not matching timebases found between first input: 1/1000 and second input 1/30000, results may be incorrect!`

This directly confirmed timeline mismatch risk.

#### 6.5) Additional AV1 speed/quality check (`cpu-used 2`) and cleanup
Why: test if a slower libaom mode changed behavior; it did not complete in reasonable time and was not needed after the timeline diagnosis.

Command started:
```bash
PATH=\"/opt/homebrew/opt/ffmpeg-full/bin:$PATH\" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -an -vf scale=1920:1080:flags=lanczos -c:v libaom-av1 -b:v 7500k -maxrate 7500k -bufsize 15000k -cpu-used 2 -row-mt 1 /tmp/p002_cu2.mkv
```

Because the run became impractically long, I terminated it:
```bash
pgrep -f 'ffmpeg.*p002_cu2.mkv'
kill -9 <pid>
```

Created (partial/incomplete) file:
- `/tmp/p002_cu2.mkv`

---

### 7) Decisive experiment: force shared CFR timeline
Why: make frame matching deterministic across codecs/containers.

Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" ffmpeg -hide_banner -y -i /Users/gabrielromaninidebarros/Development/bitrate-ladder/9910331-uhd_3840_2160_30fps.mp4 -i /private/tmp/out/debug_work/encodes/p002.mkv -lavfi "[0:v]fps=30000/1001,scale=1920:1080:flags=bicubic,settb=AVTB,setpts=N/FRAME_RATE/TB[ref];[1:v]fps=30000/1001,scale=1920:1080:flags=bicubic,settb=AVTB,setpts=N/FRAME_RATE/TB[dist];[dist][ref]libvmaf=log_fmt=json:log_path=/tmp/manual_vmaf_av1_fps.json:n_threads=4" -f null -
```

Result:
- `VMAF score: 99.795892`

This immediately validated the root cause: frame timeline normalization was missing.

Created file:
- `/tmp/manual_vmaf_av1_fps.json`

---

## Code fix implemented

### Files changed
- `src/bitrate_ladder/vmaf.py`
- `src/bitrate_ladder/cli.py`

### What changed and why

#### `src/bitrate_ladder/vmaf.py`
1. Added `probe_video_fps(video_path, ffprobe_bin='ffprobe')`:
- Uses `ffprobe` to read source video frame rate.
- Why: choose one canonical FPS timeline for both streams during VMAF.

2. Updated `compute_vmaf_metrics(...)` signature:
- Added `evaluation_fps` parameter.

3. Rebuilt VMAF filter graph to normalize both streams before `libvmaf`:
- `fps=<evaluation_fps>`
- `scale=<evaluation_resolution>`
- `settb=AVTB`
- `setpts=N/FRAME_RATE/TB`

Why: enforce identical CFR timeline and monotonic PTS semantics so frame pairing is stable.

#### `src/bitrate_ladder/cli.py`
1. Imported and called `probe_video_fps` once at run start.
2. Passed `evaluation_fps` into `compute_vmaf_metrics` for each point.
3. Added runtime metadata field:
- `runtime.evaluation_fps`

Why: traceability and reproducibility in reports.

---

## Validation after code fix

### 1) Automated tests
Command:
```bash
uv run --with pytest pytest
```

Result:
- `12 passed, 1 skipped`

### 2) Re-run focused AV1/H.264 debug pipeline
Command:
```bash
PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH" uv run python -m bitrate_ladder --config /tmp/debug_av1_config.json
```

Post-fix report check command:
```bash
python3 - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('/private/tmp/out/debug_av1_report.json').read_text())
for p in r['points']:
    print(p['id'],p['codec'],round(p['vmaf_mean'],3),round(p['vmaf_min'],3),round(p['vmaf_p95'],3))
print('selected',r['selected_ladder'])
print('fps',r['runtime'].get('evaluation_fps'))
PY
```

Post-fix result:
- H.264: `vmaf_mean 98.857`, `vmaf_min 92.088`
- AV1: `vmaf_mean 99.796`, `vmaf_min 95.720`
- Selected point switched to AV1 in this 2-point test.

---

## Commit created
Command:
```bash
git add src/bitrate_ladder/cli.py src/bitrate_ladder/vmaf.py && git commit -m "fix: normalize fps timeline for vmaf frame matching"
```

Commit:
- `f47fbc4`

---

## Key takeaways for your blog post
- The initial symptom (`mean ~67`, `p95=100`, `min near 0`) was a strong anti-pattern for timestamp mismatch.
- Narrowing scope to a 2-point repro dramatically accelerated root-cause isolation.
- Checking frame-level metric behavior and stream timebase metadata was essential.
- PSNR warning about mismatched timebases was the strongest direct clue.
- The decisive fix was not encoder tuning; it was deterministic timeline normalization before VMAF.
- Cross-codec quality comparisons require strict frame alignment, not just same bitrate/resolution.
