# ComfyUI-AIPM

`AIPM` 是“AI 提示词大师”（AI Prompt Master）的缩写。插件正式版只注册两个可独立
执行的 ComfyUI 节点：

- `AI 提示词大师 · 生图`
- `AI 提示词大师 · 生视频`

它们调用 OpenAI 兼容的多模态服务生成专业提示词。用户点击节点内按钮时只执行当前
AIPM 节点；主生成工作流执行时复用最近一次结果，不会再次调用远程服务。

## 生图节点

- 支持 Krea 2、FLUX、SDXL、SD 1.x、SD3、Illustrious、Pony 等提示词体系。
- 根据目标模型自动选择中文自然语言、英文自然语言或标签/权重格式。
- 支持最多三张参考图逐图分析。
- `仅分析参考` 输出纯提示词；`多参考改图` 保留 `image1/image2/image3` 绑定关系。
- 支持基于上次结果和修改意见继续优化。

## 生视频节点

- 支持 MiniMax H3 以及通用自然语言视频提示词。
- 支持文生视频、多参考 Ref2VA、首尾帧 FL2VA 自动判断。
- 支持图片、视频和音频参考。
- 支持全局提示词、多个分段提示词、全局/分段参考的本地 JSON 组装。
- 支持 H3 台词、说话人音色绑定、场景声、摄影、表演和连续性规则。
- 输出的第一个结果就是标准 CineTimeline 文档，可直接连接
  `CineTimeline Plan.timeline_json`。

内部的 CineTimeline 转换器只用于本地组装标准 JSON，不作为第三个 ComfyUI 节点注册。

## 远程服务

服务必须兼容：

```text
POST /v1/chat/completions
```

节点内可动态修改服务地址与模型名称。需要鉴权时，通过环境变量设置：

```text
AIPM_API_KEY
```

密钥不会写入工作流或插件文件。

默认模型名称为：

```text
Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf
```

## 安装

将插件目录放入：

```text
ComfyUI/custom_nodes/ComfyUI-AIPM
```

重启 ComfyUI 后，在节点菜单中搜索“AI 提示词大师”。

## 已验收范围

- 生图与生视频节点独立执行。
- 主工作流缓存复用，不重复请求远程模型。
- 中文/英文及各提示词体系的输出约束。
- 多图逐张分析和多参考绑定。
- MiniMax H3 多分段、台词、说话人、场景音效与参考关系。
- AIPM 标准 JSON 直接写入 CineTimeline。
- 42 项单元测试通过。

## 测试

```bash
python -m pytest -q
```

## License

MIT
