# 这套 Skill 使用的工具

不需要每次都使用全部工具。先按声音、素材和交付需求选对应的路径。

| 工具 | 一句话作用 | 当前使用情况 |
|---|---|---|
| Codex + SKILL.md | 把需求整理成步骤、分镜和可重复的制作流程 | 已使用；不是独立视频编辑软件 |
| Python 3.11+ / JSON | 调用工具、保存分镜和风格参数 | 核心运行部分；不写死作者电脑路径 |
| Pillow | 排版卡片与截图，画编号、高亮框、指针和点击光圈素材 | 已实现并实测 |
| FFmpeg | 合成画面、动画指针、配音、音量、单语/双语画面字幕和可选字幕轨，导出 MP4 | 已实现并实测；overlay 叠加指针，split 复用点击光圈 |
| ffprobe + FFmpeg 解码 | 检查时长、分辨率、音轨、字幕及文件能否完整播放 | 已使用；不代替人工听感检查 |
| edge-tts / Microsoft 在线语音 | 晓晓等在线预设配音 | 已生成试听；旁白文本会发给该服务 |
| Qwen3-TTS + MLX-Audio / MLX | 在 Apple Silicon 本机按描述生成中文青年声线 | 四种声线已生成实测试听；不是声音克隆 |
| Kokoro-ONNX / ONNX Runtime | 在本机生成英文 Heart 女声 | 已实测；需要单独准备模型和 voice 文件 |
| VoiceStudio 本地 HTTP 接口 | 用本人或授权参考录音生成新旁白 | 适配代码和协议测试完成；未在真实 VoiceStudio 模型上完成本人声音克隆实测 |
| Excalidraw 文件格式 / SVG | 保存可编辑的流程图，方便别人改图 | 已生成源文件；本次图由代码绘制，未在 Excalidraw 网页手绘 |
| 用户截图、历史文档截图、已有录屏或宿主截图工具 | 提供真实界面素材 | 当前示范使用原文历史截图；Skill 不自带通用桌面录屏器 |
| Python unittest | 检查接口、缓存、时序和视频中实际指针位置 | 开发验证工具，使用者不必每次重跑 |

声音引擎是可替换的。选在线预设无需本地声音模型；选 Heart 或 Qwen 需要各自本地环境；只有需要本人声音时才需要 VoiceStudio。声线、语言、旁白、素材、主题和指针轨迹可以独立修改。

## 开发中额外使用过什么

- Hugging Face Hub / HTTPS：下载公开模型、固定修订并核对散列，不是每次生成视频都必须联网。
- Qwen 官方免费演示 / gradio_client：本地模型下载阶段测试过三段设计样音，第四段遇到免费额度限制。最终分享目录中的四段当前中文设计样音已改用本地模型生成；演示站不属于 Skill 的运行依赖。
- skill-creator 的初始化和校验脚本：生成 Skill 目录、检查 frontmatter 与文件结构，不负责视频合成。
- 原安装教程的 Word 附件另用过 python-docx 与 LibreOffice 渲染；它们不属于这套视频 Skill 的必要依赖。

## VoiceStudio 到底完成到哪里

已实现：本地地址校验、引擎检查、参考音频与准确转录上传、接收生成 WAV、漏句错误拦截、音轨缓存，以及继续合成视频。测试使用本机假服务和纯音，证明协议处理及失败路径正常。

尚未完成：在运行中的真实 VoiceStudio、已配置的克隆模型、本人或授权参考录音上试听并验证克隆效果。缺少这些条件时不能宣称“本人声音克隆已经做好”。可先按 [voicestudio.md](voicestudio.md) 配置，或把应用里生成的旁白通过 scene.audio 导入。

相关来源：[FFmpeg 叠加滤镜](https://ffmpeg.org/ffmpeg-filters.html#overlay)、[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[MLX-Audio](https://github.com/Neywa-Labs/mlx-audio)、[VoiceStudio](https://github.com/debpalash/VoiceStudio)。

字幕由 captions.py 配合 Python wave/array 读取 PCM 数据测时，Pillow 排版原文与译文，FFmpeg 按同一时间轴叠加。Codex 在制作分镜时准备和校对双语译文；运行脚本不偷偷调用翻译服务。此版本不包含现有录音的自动转录/强制对齐模型。

内置试听：Skill 附带 11 段通用 AI 合成 MP3。`listen` 用 Python 标准库校验并导出它们，让用户在配置引擎前先试听。不是模型权重、私人录音或实时生成的当前项目配音。
