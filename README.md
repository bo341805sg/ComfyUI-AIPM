# ComfyUI-AIPM

`AIPM` 是“AI 提示词大师”（AI Prompt Master）的缩写。插件注册三个可独立执行的 ComfyUI 节点：

- `AI 提示词大师 · 生图`
- `AI 提示词大师 · 生视频`
- `AI 提示词大师 · 提示词细化`

节点按钮会调用 OpenAI 兼容的多模态服务；主工作流运行时只复用已缓存结果，不会再次提交远程生成。

## 主要能力

- Krea 2 文生图、风格参考、身份编辑。
- FLUX.1 文生图、FLUX.2 文生图与多参考编辑。
- Qwen Image 文生图、单图编辑与多图编辑。
- SD/SDXL、SD3、Pony、Illustrious/NoobAI 等模型方言。
- 最多三张生图参考图的逐图分析、`image1/image2/image3` 有序绑定和完整职责校验。
- MiniMax H3 T2VA、I2VA、L2VA、FL2VA、Ref2VA，以及 Wan、LTX-Video、HunyuanVideo 专用技能。
- 多分段视频提示词、台词/说话人、声音、摄影、表演、连续性与 CineTimeline JSON 输出。
- 多段生成按段保存检查点；单段连续失败 2 次后中断，再次点击从失败段继续，完整完成后再次生成才从头开始。
- 基于上次结果的最小必要提示词修复。

## 远程服务

服务需兼容 `POST /v1/chat/completions`。需要鉴权时设置环境变量 `AIPM_API_KEY`；密钥不会写入工作流。

## 安装

将目录放入 `ComfyUI/custom_nodes/ComfyUI-AIPM`，安装依赖后重启 ComfyUI。

## 测试

```bash
python -m unittest discover -s tests -v
```

当前回归测试：52 项。

## License

MIT
