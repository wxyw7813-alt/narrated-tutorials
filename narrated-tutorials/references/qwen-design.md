# 本地普通话青年声线

用于替换不合口味的跨语言中文声线，提供一种女声、三种男声的声音设计预设。知晴、承岳、明朗、修远是本 Skill 的风格名称，不是真人身份，不涉及真人录音或声音克隆。

目标：青年音、大气从容、音色清朗、普通话发音准确、吐字清楚。每种预设使用独立描述和固定随机种子；听感、年龄感和口音需要试听确认，不能由这些标签或生成成功推断已经达标。VoiceDesign 重新生成不同文字时，音色可能变化；它不是保持同一声纹的克隆功能。

## 本地运行

当前实现使用 Apple Silicon 上的 MLX-Audio 0.6.7 和 Qwen3-TTS VoiceDesign 1.7B 4-bit。本次固定模型：

- 仓库：`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit`
- 修订：`5c390979e4b93af5f2932f90742ca99c7dd04687`
- 文件总大小约 2.3 GB；实际运行还需要内存，当前未验证 Intel Mac 或 Windows。

只在用户授权准备本地模型时安装和下载，不在生成失败时自动增加下载或调用付费服务。模型可以通过 Hugging Face 的 `snapshot_download` 或官方 HTTPS 文件链接取得；固定修订并核对 SHA-256。

```sh
python3.12 -m venv /path/to/qwen-venv
/path/to/qwen-venv/bin/python -m pip install -r scripts/requirements-qwen.txt
```

在 Skill 根目录创建仅供本机使用的 `local-engines.json`，或在项目 voice 中提供 python/model 两项。配置路径不能随共享包分发：

```json
{
  "qwen-design": {
    "python": "/path/to/qwen-venv/bin/python",
    "model": "/path/to/downloaded-qwen-voice-design-model"
  }
}
```

运行 `studio.py audition --language zh --output DIR --allow-online` 可生成中文试听。晓晓使用在线服务，四种设计声线使用本地模型。只试听本地预设可用 `--preset ID`，不需要 `--allow-online`。

合成脚本禁用 Hugging Face 隐式联网，仅从已存在的本地模型加载，不上传文本或音频。内部最多生成约 160 秒，达到生成上限即拒绝输出；长讲稿应按自然段拆成分镜。输出字幕采用完整语句实际音轨测时，按句同步；逐字卡拉 OK 对齐仍需额外工具。

## 来源

[Qwen3-TTS 官方项目](https://github.com/QwenLM/Qwen3-TTS) · [MLX 模型卡](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit) · [MLX-Audio](https://github.com/Neywa-Labs/mlx-audio)

上游模型卡标注 Apache-2.0；实际分发模型或商业部署仍需核对所用修订、依赖及具体条件。Skill 分享包包含脚本和描述，不包含权重、本机配置或运行环境。
