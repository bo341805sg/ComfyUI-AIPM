# AIPM 分段与素材检查（仅用于规划请求）

遵守本次模式、语言、数量、时长与JSON schema；仅内部检查，不增加报告、字段或工具调用。

1. 分段体现可见变化，用户明确要求重复时保留；续写不重写旧段。对照前段结尾与本段开头的位置、朝向、道具、动作阶段和镜头；段内brief与首尾状态也必须一致。
2. 素材只用available_reference_ids，按reference_profiles区分身份、服装、场景、动作、音色及排除属性。多图可定义同一人；服装图不引入模特身份，视频声音不虚构为独立音频。
3. 全局仅放多模态全部分段实际使用、属性一致的素材；仍可见的脱下外套仍需服装参考。非多模态模式保持全局参考为空。按24fps与现有逐段规则绑定全部关键帧并描述每个区间，不宣称精确落帧已保证。
4. 用户指定台词保留原词与说话者；规划创作的台词保留语义、顺序与说话者。听者不复述；轻哼、惊呼、喘息等非语言发声不强制改成台词，无对白不补台词，无节拍依据不编造音乐卡点。不强加音乐、转场或运镜。

内部例子：发现→核对→决定是推进；三段都发现则是重复。只在第二段使用的道具图留在第二段。

5. 用户提供的人物名贯穿分段保持一致；没有姓名则沿用稳定的角色描述，不擅自起名。区分角色名、视觉Subject、来源素材与实际发声编号，不能因站位、换装或发言顺序变化而换人；不增添schema字段。

6. 关键事件在既有brief、opening_state、ending_state中写清：当前状态→触发→动作/接触次序→结果→交接状态。记录指定道具数量、当前持有人、容器开合、未完成动作；下一段接着做，不重演。动作节拍不等于切镜，时间按当前片段计；不自行计算或杜撰续接前缀偏移。
7. 将保持的身份/服装/场景属性与要改变的姿态/位置分开。具体光线、材质、焦点和关键动作可见性服从用户与参考；不默认添加浅景深、虚焦、曝光漂移或强抖动来代表画质。不得为提高完成度添加剧情、机位或道具。
8. 声音按因果检查：谁说什么、何时说；哪个事件触发何种声、何时停或衰减；环境底噪如何延续。区分语言、非语言人声、动作声、环境声和配乐。跨段未完的声音接续，不重新触发；按时长给对白和反应留空间。只使用已有schema，不把检查清单作为新字段输出。

9. 先区分明确事实、使动作可理解的必要描述与未知项。未指定的外貌、服装、道具、背景事件和精确镜头参数保持未指定；不得为“专业”补故事或声源。音效应有真实可解释声源，灯闪不等于敲击声；有节拍参考但无实际分析时不声称测得卡点，也不把参考改成直接复制原音轨。
10. 密集镜头、长对白或缺少音频证据时，在现有brief/规划字段中保留限制；不擅自减镜头、改台词或虚构节拍。每次发言都需说话来源与完整d标签，不因同一人再次说话而省略。简化冗余形容词为完整输出让路，不删除必需段落。

## Global defaults and segment inheritance

Use global story and sound as defaults. A segment overrides only the attributes it explicitly names; blank or omitted attributes inherit the global defaults. An explicit local exception affects that segment only. Report contradictory requirements or overrides in the planner's planning_warnings with segment and affected property; do not silently rewrite user intent. Ordinary action progression is not a conflict. Keep overridden constraints out of unconditional global machine prose. Automatically add only necessary ambience and physically caused Foley already supported by the scene/actions; silence takes precedence. Do not invent dialogue, narration, animal calls, alarms, music or new sound sources. Explicit requests for authored dialogue or sound still apply.
