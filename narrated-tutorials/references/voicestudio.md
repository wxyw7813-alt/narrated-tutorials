# 使用自己的声音

VoiceStudio 负责从参考录音生成新旁白，本 Skill 负责分镜、素材、字幕、合成和交付。通过独立本地 HTTP 服务连接，不复制或打包 VoiceStudio 引擎代码。

## 使用条件

需要声音所有者明确许可。用户说“用我自己的录音”可以作为其授权表述；只有一段来历不明的录音，不能当作已获授权。不需要人为增加重复确认，但应记录本次授权范围。共享 Skill 时不附带参考音频或个人授权材料。

准备 5–15 秒单人、清楚、无背景音乐的录音是较好的起点。第一版脚本接受 3–20 秒并要求准确转录，便于当前 OmniVoice 接口保持录音与文字对应。不同模型的效果和语言能力仍有差异，不保证跨语言克隆口音不变。

本 Skill 不会替用户安装应用、接受模型协议或下载数 GB 权重。已安装 VoiceStudio 后，在应用的 Model Catalogue 中选择支持克隆的引擎，完成模型设置并先生成一小段。Apple Silicon 可用的引擎与 Intel Mac 不同，先按实际设备查官方说明；不要把“macOS 支持”当作所有 Mac 都能跑全部模型。

## 接口与配置

截至 2026-11-20，核对上游提交 `7aae31d0b70da247c0c9cab4c4aced7e056c3022` 的 `/generate` 定义：multipart 字段包括 `text`、`language`、`ref_audio`、`ref_text`、`engine`、`speed`、`stream=false`；非流式返回 WAV。`GET /engines` 用于查看引擎。

```sh
python scripts/studio.py vs-check
```

如果应用使用其他本地端口，传 `--url http://127.0.0.1:PORT`。voice 中使用同一 URL。身份验证如已启用，从 `OMNIVOICE_API_KEY` 环境变量读取，不写进 JSON。

```json
{
  "provider": "voicestudio",
  "url": "http://127.0.0.1:3900",
  "engine": "omnivoice",
  "language": "Chinese",
  "reference_audio": "./private/my-reference.wav",
  "reference_text": "这里填写参考录音中实际说出的全部文字。",
  "authorization": "本人录音，允许用于本次教程的合成旁白。",
  "speed": 1.0
}
```

把这段对象放入项目 JSON 的 voice。`engine` 改成 `vs-check` 返回且已完成配置的实际克隆引擎 ID。`language` 使用对应引擎支持的语言，英文可用 `English`，也可用 `Auto`。不把参考音频的转录改成目标语言；跨语言时仅修改新旁白和目标语言。

脚本仅访问本机 loopback，不经 HTTP 代理，不跟随重定向。它会发送参考音频到本机 VoiceStudio，并在客户端清理临时标准化参考文件；VoiceStudio 自己可能保留历史和提示缓存，应在其应用中管理。若要连接远程服务器，需要另行设计明确的发送授权、HTTPS 与凭证管理。

第一版本地适配器已做协议测试，协议测试不代表真实模型完成声音克隆。只有在真实 VoiceStudio、实际模型、本人/授权参考音频上试听通过后，才能报告该配置的克隆效果。没有音频/服务时，可先用 `scene.audio` 导入应用里已经生成的新旁白，完整验证后续视频流程。

## 版本变化

上游更新后如返回非 WAV 或报缺字段，停止并核对其当前源码/API，不尝试猜字段或悄悄切云端。生成结果报告 dropped chunks 时，脚本直接拒绝该音轨，避免视频缺句。
