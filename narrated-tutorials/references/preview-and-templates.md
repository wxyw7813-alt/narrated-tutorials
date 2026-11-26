# 先看分镜，再做样片

从 Skill 目录运行。storyboard 不合成新旁白，可先检查标题、截图和布局；preview 只渲染选中的完整分镜，包含真实配音、字幕和指针。它们不是可拖动编辑的 Remotion Studio。

```sh
python scripts/studio.py templates
python scripts/studio.py storyboard project.json --output board
python scripts/studio.py preview project.json --scene 2 --output sample
python scripts/studio.py preview project.json --scene 1 --scene 3 --output sample-1-3
python scripts/studio.py render project.json --output result
```

打开 board/index.html 看静态分镜，sample/review.html 看有声样片及验收记录。静态分镜不显示最终字幕覆盖和动态指针；这些要在样片中核对。在线声线需用户已授权并加 --allow-online。preview 默认选择第 1 镜；分镜编号从 1 开始，不能重复。样片在 provenance/review 中标记为 scene-preview，不能当作全片交付。

项目根字段 template 可选 software-guide（软件操作）、concept-explainer（原理流程）、minimal（简洁交付）。配置合并顺序为 assets/style-default.json → assets/templates.json 对应模板 → 项目 style。默认模板保持原有蓝色风格。换模板不会换声音、修改内容或下载新引擎。

标题、编号步骤、页脚和流程框由 scripts/components.py 复用。流程卡片示例：

```json
{
  "title": "从目标到结果",
  "narration": "先看清目标，再按步骤操作，最后检查结果。",
  "kind": "代码绘制的流程示意",
  "flow": ["看清目标", "按步骤操作", "检查结果"]
}
```

flow 接受 2–4 个短标签，不能与 image/video/points 混用。长标签会要求缩短或拆图。它是关系示意，不能冒充软件截图。完整可编辑例子见 assets/concept-project.example.json。

首次采用新风格时，先检查一镜能减少整片返工；用户已经选定素材、声音和风格时可直接制作。这里没有固定几轮确认的要求。
