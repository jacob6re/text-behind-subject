# text-behind-subject

让红色大字从人物头顶后方出现，再将局部笔画横向延展或向下拉长。逐帧人物遮罩让文字始终位于人物后面，保留原片动作和原声。

## 安装

```bash
npx -y skills add jacob6re/text-behind-subject -g --all
```

## 使用

在支持 Agent Skills 的客户端中提供视频、文字和希望出现的位置，例如：

> 使用 $text-behind-subject，处理我的视频 input.mp4。文字分三行：TEXT / BEHIND / SUBJECT，从头顶后方出现后拉伸，全程位于人物背后，保留原声。

默认文字红色为 `#B80609`。输出 MP4 和可编辑的 HyperFrames 工程。

## 环境

- FFmpeg / ffprobe
- Python 3 + Pillow
- Node.js 22+ 与 HyperFrames
- 自动逐帧人物抠像：macOS 12+、Swift、Apple Vision
- 其他平台可以提供与视频逐帧对应的灰度 PNG 遮罩

附带 Anton 粗窄字体，适用于拉丁字母。中文需要另行提供覆盖相应字符的字体。

## 效果与边界

- 先出现正常字形，再直接增长 SVG 实心笔画，保留两端形状；避免放大窄纹理或百分比裁切插值造成中途透明。
- 向下拉伸按字母或汉字从左到右依次启动，默认约 0.2 秒间隔。
- 原片、文字、逐帧遮罩人物分别处于三个图层。
- 自动遮罩适合单人镜头，多人时包含所有人物；不提供指定人物的身份跟踪。
- 发丝、快速动作和遮挡需要检查并可能修整遮罩。
- 默认保留视频规格与完整时长；只有指定参数时截取或降低规格。

## 文件

- `skills/text-behind-subject/SKILL.md`：工作流程与验收方法
- `skills/text-behind-subject/scripts/build.py`：生成文字切片、遮罩图集与动画工程
- `skills/text-behind-subject/scripts/video_masks.swift`：Apple Vision 逐帧人物分割
- `skills/text-behind-subject/assets/`：本地动画库与字体

第三方素材授权见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
