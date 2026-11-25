---
name: narrated-tutorials
description: Create narrated tutorial or explainer videos from steps, screenshots or supplied recordings, with Chinese and English voice auditions, single/bilingual audio-timed captions, and numbered screenshot annotations. Supports preset speech, local Qwen Mandarin voice design, optional offline Kokoro English, and authorized reference-voice synthesis through local VoiceStudio.
---

# 中英文配音教程视频

把用户的步骤或素材整理成分镜，生成配音、MP4、字幕和制作记录。共享的是制作流程、脚本和声线配置；不捆绑个人录音、凭证或模型。

## 工作方式

1. 明确语言、受众和材料来源。已有截图做图文教程，已有录屏可剪入视频；需要实机录制时用当前环境实际提供的录屏工具，不能把静态截图称为实机操作。不会因生成了教程就声称安装操作已经完成。
2. 新项目未指定声线时，按 [references/voice-selection.md](references/voice-selection.md) 主动在对话中展示 2–3 段可播放短音频，等用户选声后再批量合成；不能只给声线名称或网页链接。用 `listen` 导出内置试听，无需联网或下载模型。用户明确指定或要求沿用上次时直接继续；已有偏好用于排列候选。`assets/voices.json` 提供 10 种：中文女声、中文男声各 2 种，英文女声、英文男声各 3 种（含离线 Heart）。其中三种中文青年音是本地 Qwen 声音设计预设，读 [references/qwen-design.md](references/qwen-design.md) 准备模型与本机配置。它们按标准普通话、大气清朗、吐字清晰的目标设计，当前标签表示设计目标，效果需要试听确认；固定描述和随机种子不保证跨文本声纹完全不变。风格标签是选择提示，不保证每个人都觉得自然。
3. 按 [references/usage.md](references/usage.md) 准备独立 Python 环境并运行 `doctor`。FFmpeg、字体、Python 解释器都在使用者的电脑上解析，不写死作者路径。
4. 在线预设使用 edge-tts，会把旁白文字发给 Microsoft。按用户当前授权范围选择在线或离线路径；仅在已授权时传 `--allow-online`。不能因为离线引擎失败就悄悄改走在线、付费服务或换声线。
5. 使用自己的声音时读 [references/voicestudio.md](references/voicestudio.md)。需要本人录音或声音所有者明确授权、干净短音频及准确转录。缺少音频时仍完成可独立开发的部分，说明尚未实测本人声线；不能拿网上人物音频代替。第一版本地适配器只连接 loopback 地址，拒绝重定向；不自动安装 VoiceStudio、不接受模型条款、不下载大模型。
6. 默认用清晰图解解释原理，用实际截图或已有录屏讲软件操作；标出关键位置，涉及鼠标操作时安排指针移动、停留和点击光圈，避免遮住按钮文字。读 [references/visual-style.md](references/visual-style.md) 配置图解、截图标注和指针。使用者指定其他风格时可以调整；只有文字素材时先做明确标注的示意，不能编造软件截图。
7. 按 `assets/example-project.json` 写分镜清单。旁白使用完整自然句子；读者要看的代码与实际读音可以不同，避免逐字符读文件路径。截图上的编号坐标必须来自实际图片，不编造界面。选定一小段试听后再批量生成。字幕与画面时长以音轨为准。
8. 默认生成直接显示在画面上的单语字幕；用户需要双语时先按语义逐句翻译并校对术语，准备一一配对的 captions，再运行 render。读 [references/subtitles.md](references/subtitles.md)。字幕按完整语句的实际 PCM 起止计时，不按字数分摊；双语共用同一时间码。已有音频必须有准确时间码，缺少时先取得对齐字幕，不交付估时字幕冒充同步成片。
9. 检查画面、声音、字幕和指针共用最终时间轴；换声线后重新测时长。源图重点不要被字幕挡住。抽查开头、切段和结尾，并检查最终解码结果。
10. 返回可播放视频和必要文件，注明 AI 合成旁白。默认本地交付；上传到文档或发布按用户指定目标操作。分享 Skill 时只打包 Skill 文件，不打包输出缓存、原始录音或凭证。

## 快速调用

从当前 Skill 目录运行；`python` 指安装了依赖的独立环境解释器：

```sh
python scripts/studio.py listen --language zh --output ./auditions
python scripts/studio.py doctor
python scripts/studio.py voices
python scripts/studio.py audition --language zh --output ./auditions --allow-online
python scripts/studio.py render ./project.json --output ./result --allow-online
```

`--allow-online` 只适用于已授权的在线生成。离线 Kokoro、Qwen、VoiceStudio 和导入音频不需要这个标志。完整配置、离线模型路径和输出说明在 [usage.md](references/usage.md)；接口版本依据与克隆限制在 [voicestudio.md](references/voicestudio.md)。

公开可调用的声音不等于无条件可商用或可再分发。商业交付、打包引擎/模型时先核对该服务及具体模型的当前条件，见 [sources.md](references/sources.md)。

## 工具和共享调整

完整工具及实际验证范围见 [references/toolchain.md](references/toolchain.md)。VoiceStudio 是可选的本地克隆后端：代码接口已实现，协议测试通过，真实声音克隆仍需运行中的应用/模型及本人或授权录音验证。不能把已验证的 Qwen 声音设计称为 VoiceStudio 克隆。

别人可以修改旁白、语言、声线、素材、主题颜色、帧率、编号、高亮框、指针轨迹和节奏。`assets/style-default.json` 提供可覆盖默认值；每个项目的 `style` 覆盖它。分享包保留说明和可编辑配置，不含个人资料、参考录音、模型和 `local-engines.json` 本机路径。
