# 运行与分享

## 环境

Python 3.11+，FFmpeg（包含 ffprobe、libx264、AAC、mov_text），支持中文的字体。macOS 自动使用 PingFang；其他电脑可传 `--font /path/to/font.ttc`。安装依赖到独立环境，不更改系统 Python：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/studio.py doctor
```

macOS 若没有 FFmpeg，可通过已经安装的 Homebrew 执行 `brew install ffmpeg`，或使用 FFmpeg 官方链接的发行包。先检查实际环境，无需为了本 Skill 重装已有工具。

## 选声线

`voices` 显示声线 ID、性别和设置。目录包含中文女声 2 种，其余三组各 3 种，共 11 种；知晴、明朗、修远是本地 Qwen 设计的青年普通话预设，按 [qwen-design.md](qwen-design.md) 准备运行环境。音色是否符合要求以试听为准。`audition --language zh|en|all --output DIR --allow-online` 生成可在浏览器打开的 `index.html` 及 MP3；可用 `--preset ID --text '试听内容'` 只生成一条。

在线声线通过 edge-tts 调用 Microsoft Edge 在线语音，不是本地开源模型，也不承诺持续可用或生产服务保障。报错时保留已有结果，处理服务/网络问题后再试，不能静默换成机械系统音。

英文 `en-heart-local` 是可选离线配置：单独准备 Python 环境中的 `kokoro-onnx`、`soundfile`、`numpy`、`onnxruntime`，以及自行取得并核对来源/条件的模型和声线文件。不会自动下载。将 voice 配为：

```json
{
  "preset": "en-heart-local",
  "python": "/path/to/kokoro-venv/bin/python",
  "model": "/path/to/kokoro-v1.0.onnx",
  "voices": "/path/to/voices-v1.0.bin"
}
```

## 分镜 JSON

复制 `assets/example-project.json` 到自己的项目目录。路径均相对分镜 JSON 所在目录，也可以使用绝对路径。`voice` 指定全片声线。每个 scene：

| 字段 | 作用 |
|---|---|
| `title`、`narration` | 必填，画面标题和要读出的完整旁白 |
| `points` | 无截图时显示的步骤列表，过长会提示拆分 |
| `image` | 截图或流程图路径；按比例放入画面 |
| `highlights` | 截图重点框，如 `[{"x":100,"y":80,"width":240,"height":60}]` |
| `pointer` | 移动指针与点击轨迹，见 [visual-style.md](visual-style.md) |
| `callouts` | 截图编号，如 `[{"number":1,"x":320,"y":210}]`，坐标使用原图像素 |
| `footer`、`kind` | 画面说明和类型，可标明历史截图/操作示意 |
| `video`、`video_start` | 已有录屏及起始秒数；取代卡片画面，源音轨被新旁白替换 |
| `audio` | 已有该场景旁白音频，跳过 TTS；需和 narration 内容匹配 |
| `captions` | 原文与译文配对；已有音频还需要 start/end 秒数，见 [subtitles.md](subtitles.md) |
| `audio_origin` | 导入音频来源：`synthetic`、`human-recording` 或默认 `provided-unknown` |

同一场景不能同时使用 video 与 image/callouts。截图中的指针动画属于后期引导，已有录屏中的真实指针可以直接保留；视频场景也可使用 frame 坐标加指针覆盖。录屏按旁白时长截取，素材不够长时定格最后一帧；需要动作逐步同步时，应细分场景和指定 `video_start`。本版本不会自动理解屏幕动作或启动桌面录屏。分镜配置里安排的后期指针不会操作用户的实际桌面。

```sh
.venv/bin/python scripts/studio.py render project.json --output result --allow-online
```

已有输出默认不覆盖；明确需要替换时加 `--overwrite`。失败后保留工作缓存，成功音轨以文本、声线设置、参考音频/模型内容散列缓存；重新运行不会无故重做。VoiceStudio 生成超时不自动重试，避免重复占用引擎，先在应用中确认上一请求结束。

## 输出和字幕

- `video.mp4`：1920×1080、默认 20 fps（可通过 style.fps 调整）、H.264/AAC，包含可选择的 mov_text 字幕轨。
- `subtitles.srt`：当前模式的字幕；新流程默认直接显示到画面中，也保留可选择字幕轨。单语或双语可配置，见 [subtitles.md](subtitles.md)。
- `subtitles.source/target/bilingual.srt` 和 `.vtt`：原文、译文、双语文件（单语只生成原文）。
- `caption-timeline.json`：每句最终时间码。
- `chapters.txt`：章节开始时间。
- `provenance.json`：声线设置、音轨时长、字幕时间来源、文件散列、素材说明。
- `preview.html`：本地播放器。
- `work/`：中间图片、音轨和视频片段，属于项目私有材料，不随 Skill 分发。

新字幕流程默认按完整语句合成并测量实际 PCM 声音起止；不再按整段时长或字数估算。中间分镜采用 PCM 音轨，全部拼接后只编码一次 AAC，避免逐段编码补齐带来的累积偏差。这是按句同步，不是逐字卡拉 OK 对齐。生成结果应人工检查漏字、术语发音和内容准确性；音频文件通过解码测试不能代替试听。

## 给别人使用

分享 `narrated-tutorials` 整个文件夹或它的 ZIP。对方解压到其 Codex 的 `~/.codex/skills/narrated-tutorials/`，在新对话里使用 `$narrated-tutorials`。其他支持 SKILL.md 的代理可放入其文档规定的 Skill 目录；未逐一验证所有代理兼容性。

对方仍需安装运行依赖。Skill 是供代理遵循的工作说明和工具，不是安装后自动拥有全部模型的独立视频软件。参考录音、本人授权记录和 API key 及 local-engines.json 本机配置都留在各自电脑，不发给他人；API key 只从环境变量读取。
