# 这次借鉴了什么

以下是设计思路的来源，核对于 2026-11-26。本次代码独立实现，没有把第三方 Skill 作为指令覆盖用户要求，也没有复制其动画风格或验收脚本。

| 来源 | 值得学习 | 本 Skill 的落地 |
|---|---|---|
| [Remotion 官方 Skill](https://github.com/remotion-dev/skills/blob/main/skills/remotion-best-practices/SKILL.md) | 先打开预览、复用组件，字幕与渲染分模块按需读取 | storyboard 静态分镜、preview 指定分镜样片、3 个可覆盖模板，header/steps/flow/footer 组件与分主题参考文档 |
| [Anything2Explainer QC 规则](https://github.com/Vincentwei1021/anything2explainer/blob/main/reference/agent-qc-rules.md) | 用实际成片抽帧和总览逐镜核对，关注可读性、遮挡、时间和内容 | review.html/json、实际关键帧、重要区域几何检查、最终音轨起点检查及独立人工检查项 |
| [Playwright 官方 locators](https://playwright.dev/docs/locators) 与 [截图](https://playwright.dev/docs/screenshots) | 用真实页面和可靠目标定位采集素材 | 可选独立 Chromium、严格定位、实际动作与连续截图、结果截图与操作日志 |

当前没有引入 Remotion、React、Remotion Studio 或其完整动画运行时，仍由 Pillow + FFmpeg 合成。不会把借鉴预览思想写成“已接入 Remotion”。需要复杂镜头动画或拖动式编辑器时，可以再评估独立渲染后端；本轮没有为了这些尚未提出的功能新增整套依赖。

Anything2Explainer 为其影片设定的具体配色、运动次数和逐帧阈值不适合作为所有安装教程的固定标准。本项目使用自己的 1080p 字幕区域、50 ms 音轨起点容差和人工核对项，保留清晰、平稳的教程风格。
