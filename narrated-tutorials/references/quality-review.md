# 每次交付都能复查

preview/render 成功后自动生成验收页，也可重新检查现有结果：

```sh
python scripts/studio.py review result
```

打开 result/review.html，可播放视频、查看每镜时间与旁白、核对双语字幕，并点击实际导出关键帧跳到对应位置。contact-sheet.png 是全片总览；review-frames 保存实际 MP4 抽帧，含分镜首尾和句内代表画面，避免只检查未合成的源图。

验收页和视频保持在同一目录。可直接本地打开；通过 HTTP 预览时，服务器需要支持视频的 Range 分段请求，否则浏览器可能无法拖动或按关键帧跳转。

自动检查记录在 review.json：

- 视频散列、1920×1080 画面、音轨、计划时长及完整解码。
- 字幕非空、顺序和范围、每镜覆盖、双语译文及导出文件。
- 对按句测时的配音，从最终 AAC 解码后核对语句附近的能量起点，容许差为 50 ms；这是能量检查，不是识别每个字。
- 指针坐标与时间范围、编号与已标记重要区域的重叠、重要区域与字幕带重叠，以及采集动作晚于计划的告警。

automatic_status 为 error / needs_attention / automatic_checks_passed。修复 error 后再交付；warning 需要看画面/听声音决定如何改。manual_status 初始始终为 pending，自动检查不能证明术语发音、内容事实、指针含义和声音自然度都正确。

人工检查页可勾选并写明“第几镜、几秒、哪里有问题”，点击下载检查反馈，得到绑定视频 SHA256 的 review-feedback.json。网页不自动把反馈发给助手，也不回写 review.json。视频修改后应重新核对；旧视频的反馈不能冒充新视频的验收。

## 标记不能被挡住的区域

截图场景用原图像素；视频场景用最终 1920×1080 画面坐标：

```json
"protected_regions": [
  {"label":"保存按钮","space":"image","x":400,"y":250,"width":120,"height":50}
]
```

space 默认 image；写 frame 时直接对应最终画面。几何检查会将原图坐标按实际截图缩放位置转换。画面字幕区目前从 y=898 开始。Playwright capture 默认把实际操作目标框转成 frame 区域，可通过每步 protect_targets:false 关闭。

没有标记的按钮、图片里的小字、颜色对比度与语义仍需看图确认；本版本不含 OCR、自动事实核查、语音识别或真人听感评价。不要把“未发现几何重叠”写成“全片保证无遮挡、绝无延迟”。
