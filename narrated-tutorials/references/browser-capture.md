# 用 Playwright 采集真实网页素材

用在“打开网页、点击、填写、选择，再讲解结果”的教程。脚本在独立 Chromium 中执行声明的动作，按单调时钟连续截取实际网页画面，再用 FFmpeg 组成片段。不是静态截图假装点击，也不是桌面安装器录屏。当前为单标签页，不能接管用户现有登录态。

## 可选依赖

其他功能不需要 Node 或 Playwright。需要此功能时，从 Skill 目录运行：

```sh
npm ci --prefix scripts --ignore-scripts
python scripts/studio.py doctor --capture
```

Node 20+。若缺 Chromium，按输出准备浏览器；首次下载可能较大，已有匹配缓存可直接复用：

```sh
cd scripts
npx playwright install chromium
```

不把 node_modules、浏览器缓存或模型塞进共享 Skill。Python 依赖仍按 usage.md 安装。

## 先跑可验证的小例子

在一个终端从 Skill 目录提供演示页面：

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory assets
```

另一个终端执行（示例选用承岳，需已配置本地 Qwen；也可改为自己的音频和准确字幕）：

```sh
python scripts/studio.py capture assets/browser-plan.example.json --output capture-result
python scripts/studio.py preview capture-result/project.json --scene 1 --output sample
python scripts/studio.py render capture-result/project.json --output result
```

这个演示实际点击“打开设置”、选择 Python 3.11、点击“保存设置”，并等待确认文字出现；页面明确标注为本地演示，不会安装或修改系统 Python。演示素材只证明网页采集流程，不代表 Cursor/PyCharm 安装已完成。

## 改成自己的网页教程

复制 browser-plan.example.json。根字段 url、voice、steps 必填；subtitles/template/style 与渲染项目相同。每步有 title、narration、captions 和 actions。先测实际配音，再把动作绑定到字幕时刻；网页操作耗时长时保留完整录制长度，避免被短配音截断。

```json
{
  "type":"click",
  "target":{"role":"button","name":"保存设置"},
  "caption":1,"edge":"start","offset":0.4
}
```

caption 从 1 开始，edge 可为 start/end，offset 为秒；也可单独使用 at_seconds，不能混用。每句 start/end 来自实际配音，双语用同一码；动作涉及页面等待，不能保证每次网页响应同样快，迟于计划超过 0.25 秒会提示复核。必要时拆分旁白、调整偏移并重采集。

目标只选一种：role+name、label、placeholder、test_id、text 或 css，优先用实际可见名称和 label。匹配多个目标会失败，不能静默点击第一个。支持 click/fill/press/select/check/uncheck/hover/scroll/navigate/expect_text，不接受项目里的任意 JavaScript。fill 可用 value_env 从环境变量读取；发布前仍需检查截图和画面是否出现个人信息。

capture_fps 默认 10，可设 5–20；viewport 默认 1280×720。最终输出默认 20 fps，插帧不会把采集变成真正 60 fps。低速网页操作适合此方式，高帧率动画/桌面程序宜用已有录屏。指针和点击光圈是随真实目标移动的教学覆盖层，不是操作系统鼠标。

默认只访问本机网页。用户已要求录制的外部 HTTP(S) 网站可加 --allow-external；这会允许该独立浏览器访问网站所需外部资源，不意味着获得提交、付款或修改无关内容的授权。需要登录、多窗口或桌面弹窗时应改用宿主已有工具，或导入用户提供的录屏，不声称此命令覆盖这些情况。

## 输出与失败处理

- project.json：可直接送入 preview/render，保留音频、时间码、动作片段长度和重要目标框。
- step-001.png 等：每步结果截图；clips/ 是真实画面片段，narration/ 是配音。
- capture-log.json：每次动作、实际时间、目标框、帧时间及失败原因；capture-provenance.json 保存方法和媒体散列。
- frames/ 与 work/：原始画面和准备作业，默认项目私有；不随 Skill 公开。

出错时不生成成功的 project.json；--overwrite 重采集会先撤下旧成功清单，避免失败后误渲染旧成果。处理问题后再显式重跑，不自动重复外部业务操作。日志不记录 fill 的内容，但网页截图本身可能显示输入结果。
