# 引擎来源与使用范围

核对日期：2026-11-20。下面链接是当前核对依据，服务和模型条款可能更新；不把本文件当成永久商用许可。

| 组件 | 用途 | 需要区分 |
|---|---|---|
| [edge-tts](https://github.com/rany2/edge-tts) | 在线中英文预设语音 | Python 客户端开源不等于微软声线/服务开放授权；无密钥入口不等于生产 SLA |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 可选本地英文语音 | 运行库、模型文件、voice 文件需各自核对来源及条件 |
| [VoiceStudio](https://github.com/debpalash/VoiceStudio) | 本地克隆与音频工作站 | 应用采用 AGPL-3.0；模型、tokenizer、录音及输出还有各自条件 |
| [VoiceStudio 许可说明](https://github.com/debpalash/VoiceStudio/blob/main/LICENSE-NOTICE.md) | 查看应用与模型区别 | 当前说明提到默认 OmniVoice 权重为 CC-BY-NC，另有 tokenizer 条款；不能由应用可商用推断默认模型可商用 |
| [引擎与参考音频说明](https://github.com/debpalash/VoiceStudio/blob/main/docs/engines/README.md) | 选择硬件和克隆引擎 | 支持平台、参考片段长度、语言能力随引擎不同 |
| [生成接口源码](https://github.com/debpalash/VoiceStudio/blob/7aae31d0b70da247c0c9cab4c4aced7e056c3022/backend/api/routers/generation.py) | 本地适配依据 | 协议实现独立编写；分享包不包含上游引擎代码或权重 |
| [FFmpeg](https://ffmpeg.org/) | 本地视频合成 | 自行安装的构建及编码器另有许可证，不随本 Skill 打包 |

如果将来要出售、托管或嵌入产品，重新审阅实际使用的引擎和资产范围；仅调用本地 API 不构成对整个部署许可条件的结论。


新增本地中文青年候选使用 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 和 [MLX 模型](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit)。固定修订模型卡标注 Apache-2.0；设计目标与音色听感需要区分，这些声音不是任何真人的录音或克隆。
