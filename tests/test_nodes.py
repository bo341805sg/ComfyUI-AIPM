import importlib.util
import inspect
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prompt_assistant_nodes", ROOT / "nodes.py")
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)


class PromptAssistantTests(unittest.TestCase):
    def test_reference_cache_separates_request_context(self):
        from unittest.mock import patch
        nodes.ReferenceAnalysisPipeline._image_cache.clear()
        images = [{"sha256": "a", "data_url": "unused"}, {"sha256": "b", "data_url": "unused"}]
        def respond(url, payload, **kwargs):
            instruction = json.loads(payload["messages"][0]["content"][0]["text"])
            return {"choices": [{"message": {"content": json.dumps([url, payload["model"], instruction])}}]}
        analyze = nodes.ReferenceAnalysisPipeline.analyze_images
        try:
            with patch.object(nodes.OpenAICompatibleClient, "request", side_effect=respond) as request:
                first, hits = analyze("http://one/v1", "model", images, "identity")
                self.assertEqual(hits, 0)
                repeated, hits = analyze("http://one/v1", "model", images, "identity")
                self.assertEqual(hits, 2)
                self.assertEqual(first, repeated)
                for url, model, refs, hint in [
                    ("http://one/v1", "model", images, "clothing only"),
                    ("http://two/v1", "model", images, "identity"),
                    ("http://one/v1", "other-model", images, "identity"),
                    ("http://one/v1", "model", list(reversed(images)), "identity"),
                ]:
                    with self.subTest(url=url, model=model, hint=hint, order=refs):
                        changed, hits = analyze(url, model, refs, hint)
                        self.assertEqual(hits, 0)
                        self.assertNotEqual(changed, first)
                self.assertEqual(request.call_count, 10)
        finally:
            nodes.ReferenceAnalysisPipeline._image_cache.clear()

    def test_all_runtime_skill_routes_share_contract_once(self):
        profiles = list(nodes.PROMPT_SKILL_BY_PROFILE) + list(nodes.VIDEO_PROMPT_SKILL_BY_PROFILE) + ["__refinement__"]
        for profile in profiles:
            with self.subTest(profile=profile):
                _, text = nodes.load_prompt_skill(profile)
                self.assertEqual(text.count("# AIPM runtime scope"), 1)
                self.assertNotIn("\nname: aipm-", text)
        _, h3 = nodes.load_prompt_skill("MiniMax H3", "h3_ref2va")
        self.assertIn("without a JSON wrapper", h3)
        self.assertIn("subject_definitions:", h3)
        self.assertNotIn("otherwise move the camera", h3)

    def test_dialogue_requirement_negation_and_mixed_intent(self):
        for idea in ["无对白", "不要添加台词", "不需要任何对白", "角色不说话", "没有旁白", "without dialogue", "no voice-over", "风景静默"]:
            self.assertFalse(nodes.requires_planned_dialogue(idea), idea)
        for idea in ["需要对白", "不要旁白，林说一句你好", "无对白，但需要旁白", "林说：你好", "no voice-over, Alice says hello"]:
            self.assertTrue(nodes.requires_planned_dialogue(idea), idea)

    def test_explicit_repeat_does_not_disable_accidental_duplicate_guard(self):
        for idea in ["重复演示", "明确要求两段重复同一动作", "请重复", "please repeat the same action"]:
            self.assertTrue(nodes.explicitly_allows_repeated_segments(idea), idea)
        for idea in ["三段推进剧情", "不要重复演示", "避免重复剧情", "do not repeat the same action"]:
            self.assertFalse(nodes.explicitly_allows_repeated_segments(idea), idea)

    def test_multimodal_frame_normalization_preserves_keyframe_mode(self):
        import copy
        original = {"segments": [{"reference_ids": ["<Picture 1>"], "brief": "穿绿色外套", "keyframe_bindings": [{"reference_id": "<Picture 1>", "local_frame": 120}], "keyframe_transitions": ["变化"]}]}
        plan = copy.deepcopy(original)
        nodes.normalize_plan_mode(plan, "h3_keyframe")
        self.assertEqual(plan, original)
        nodes.normalize_plan_mode(plan, "h3_ref2va")
        self.assertEqual(plan["segments"][0]["keyframe_bindings"], [])
        self.assertEqual(plan["segments"][0]["reference_ids"], ["<Picture 1>"])
        self.assertEqual(plan["segments"][0]["brief"], "穿绿色外套")

    def test_real_planner_validator_silence_duplicates_and_mode_routing(self):
        from unittest.mock import patch
        import copy
        class Captured(BaseException):
            pass
        def capture(idea):
            holder = {}
            def intercepted(cls, *args, **kwargs):
                holder["validate"] = kwargs["validator"]
                raise Captured()
            with patch.object(nodes.OpenAICompatibleClient, "request_object", classmethod(intercepted)):
                with self.assertRaises(Captured):
                    nodes.AIPMVideoPromptCore().generate_timeline_package(
                        service_url="http://unused/v1", service_model="test", profile="MiniMax H3", mode="h3_ref2va", idea=idea,
                        duration_seconds=15, segment_count=2, aspect_ratio="16:9", requested_language="中文",
                        skill_id="aipm-minimax-h3-video", skill="test", reference_profiles=[], cache_hits=0,
                        has_video=False, has_audio=False, previous=None, modification="")
            return holder["validate"]
        segment = dict(brief="动作", opening_state="开始", ending_state="结束", dialogue_lines=[], keyframe_bindings=[{"local_frame": 0}], keyframe_transitions=[])
        duplicate = {"segments": [copy.deepcopy(segment), copy.deepcopy(segment)]}
        capture("无对白，明确要求重复演示")(duplicate)
        self.assertEqual(duplicate["segments"][0]["keyframe_bindings"], [])
        with self.assertRaisesRegex(nodes.PromptAssistantError, "重复剧情"):
            capture("无对白，剧情不要重复")(copy.deepcopy(duplicate))
        with self.assertRaisesRegex(nodes.PromptAssistantError, "实际台词"):
            capture("请安排对白，重复演示")(copy.deepcopy(duplicate))

    def test_h3_planning_review_is_loaded_into_planning_context(self):
        review = nodes.load_h3_planning_review()
        self.assertIn("24fps", review)
        self.assertIn("非多模态模式保持全局参考为空", review)
        self.assertIn("用户明确要求重复", review)
        self.assertIn("续写不重写旧段", review)
        self.assertIn('"planning_review": load_h3_planning_review()', (ROOT / "nodes.py").read_text(encoding="utf-8"))

    def test_h3_review_not_injected_into_image_or_base_reference(self):
        _, image = nodes.load_prompt_skill("Anima 系列")
        _, base = nodes.load_prompt_skill("MiniMax H3 FL2VA（首尾帧）", "h3_fl2va")
        _, ref = nodes.load_prompt_skill("MiniMax H3 Ref2VA（多参考）", "h3_ref2va")
        self.assertNotIn("Two-speaker example fragment", image)
        self.assertNotIn("Two-speaker example fragment", base)
        self.assertIn("reference generation", nodes._h3_contract.selected_example(ROOT / "skills" / "aipm-minimax-h3-video", "h3_ref2va", "人物对白")[1])
        self.assertNotIn("AIPM 分段与素材检查（仅用于规划请求）", ref)

    def test_h3_planning_review_missing_or_empty_fails_explicitly(self):
        from unittest.mock import patch
        with patch.object(pathlib.Path, "is_file", return_value=False):
            with self.assertRaises(nodes.PromptAssistantError):
                nodes.load_h3_planning_review()
        with patch.object(pathlib.Path, "read_text", return_value=" "):
            with self.assertRaises(nodes.PromptAssistantError):
                nodes.load_h3_planning_review()

    def test_only_image_and_video_nodes_are_registered(self):
        self.assertEqual(
            set(nodes.NODE_CLASS_MAPPINGS),
            {"AIPMImagePrompt", "AIPMVideoPrompt", "AIPMPromptRefinement"},
        )
        self.assertEqual(
            set(nodes.NODE_DISPLAY_NAME_MAPPINGS),
            {"AIPMImagePrompt", "AIPMVideoPrompt", "AIPMPromptRefinement"},
        )

    def test_image_node_defaults_to_krea_2(self):
        target = nodes.AIPMImagePrompt.INPUT_TYPES()["required"]["目标生图模型"]
        self.assertEqual(target[1]["default"], "Krea 2 / Krea 2 Turbo 文生图")

    def test_image_reference_purpose_defaults_to_multi_reference_editing(self):
        purpose = nodes.AIPMImagePrompt.INPUT_TYPES()["required"]["参考图用途"]
        self.assertEqual(purpose[0], ["多参考改图", "仅分析参考"])
        self.assertEqual(purpose[1]["default"], "多参考改图")

    def test_connection_fields_are_global(self):
        for node in (nodes.AIPMImagePrompt, nodes.AIPMVideoPrompt, nodes.AIPMPromptRefinement):
            required = node.INPUT_TYPES()["required"]
            self.assertNotIn("模型名称", required)
            self.assertNotIn("远程服务地址", required)
            self.assertNotIn("服务模型", required)

    def test_description_editor_uses_native_multiline_widget(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertNotIn("installResizableIdeaEditor", ui)
        for node in (nodes.AIPMImagePrompt, nodes.AIPMVideoPromptCore):
            required = node.INPUT_TYPES()["required"]
            field = "画面描述与创作要求" if node is nodes.AIPMImagePrompt else "视频内容与导演要求"
            self.assertTrue(required[field][1]["multiline"])

    def test_aipm_nodes_enforce_minimum_width_and_keep_revision_at_two_lines(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("function configureStableNodeLayout(node)", ui)
        self.assertIn("const AIPM_MIN_WIDTH = 480", ui)
        self.assertIn("Math.max(AIPM_MIN_WIDTH", ui)
        self.assertIn("delete node.properties.aipm_locked_width", ui)
        self.assertIn('modification.computeSize = (width) => [width, 54]', ui)
        self.assertIn('element.style.resize = "none"', ui)
        self.assertIn("configureStableNodeLayout(this)", ui)
        self.assertIn('node.addWidget("button"', ui)
        self.assertIn('node.addWidget(\n      "combo", "时间轴处理方式"', ui)
        self.assertIn('node.widgets.splice(modificationIndex, 0, ...controls)', ui)
        self.assertIn("immediately above, the modification request", ui)
        self.assertIn("delete widget.last_y", ui)
        self.assertIn('node.addDOMWidget?.("aipm_image_actions"', ui)
        for node in (nodes.AIPMImagePrompt, nodes.AIPMVideoPromptCore):
            self.assertNotIn("独立执行令牌", node.INPUT_TYPES().get("optional", {}))

    def test_aipm_result_cache_uses_node_callback_and_serialization_sync(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("const acceptResult = (output)", ui)
        self.assertIn("node.onExecuted = nodeExecuted", ui)
        self.assertIn("node.onSerialize = serialize", ui)
        self.assertIn('previousResult.value = String(this.properties.aipm_previous_result || "")', ui)
        self.assertIn('if (!requestState.running || !Array.isArray(output?.text)) return;', ui)

    def test_frontend_only_native_controls_never_enter_positional_widget_values(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("const keepRuntimeOnly = (widget)", ui)
        self.assertIn("widget.serialize = false", ui)
        self.assertIn("widget.options.serialize = false", ui)
        for name in ("operationSelect", "targetSelect", "button", "reviseButton", "cacheButton", "clearButton", "status"):
            self.assertIn(f"keepRuntimeOnly(node.addWidget", ui)
        self.assertIn("removeOldPanel(this);\n      const result = originalConfigure", ui)
        self.assertIn("configureStableNodeLayout(this);\n      installGeneratePanel(this);", ui)
        self.assertIn('["重写时间轴", "续写时间轴"].includes', ui)
        self.assertIn("modificationInput.value = shiftedInstruction", ui)

    def test_video_result_is_immediately_written_to_linked_cinetimeline(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn('function writeResultToLinkedCineTimelines(node, rawTimelineJson, strategy = "rewrite"', ui)
        self.assertIn('output?.name === "完整结果 JSON"', ui)
        self.assertIn('targetInput?.name !== "timeline_json"', ui)
        self.assertIn("timelineWidget.value = raw", ui)
        self.assertIn("target.cineTimelineEditor?.reloadState?.()", ui)
        self.assertIn("writeResultToLinkedCineTimelines(", ui)
        self.assertIn('if (index === 0 || shot.metadata.new_scene === true) shot.transition = "cut"', ui)
        self.assertIn('else if (!["cut", "motion_context"].includes(shot.transition))', ui)
        self.assertIn('const resultOperation = String(authoring?.aipm_operation || "")', ui)
        self.assertIn('next = { ...parsed, ...current, total_frames: totalFrames,', ui)
        self.assertIn('shots: [...existing, ...additions]', ui)
        self.assertIn('if (!additions.length) continue;', ui)
        self.assertIn('Number(shot.start_frame) < existingEnd', ui)
        self.assertNotIn('current?.metadata?.render_target_shot_id', ui)

    def test_generate_buttons_keep_fixed_labels_and_width_while_running(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertNotIn('button.textContent = revise ? "生成 / 重新创作" : "正在生成……"', ui)
        self.assertIn('button.name = isRefinement', ui)
        self.assertIn('button.callback = () => run(false)', ui)
        self.assertIn('document.createElement("button")', ui)
        self.assertIn("当前AIPM请求仍在执行，请等待完成", ui)
        self.assertIn("const activeGraph = node.graph || app.graph || app.rootGraph", ui)
        self.assertIn("const prompt = await app.graphToPrompt(activeGraph)", ui)
        self.assertIn("const keep = new Set()", ui)
        self.assertIn("String(value?.class_type || \"\") === comfyClass", ui)
        self.assertIn("String(id).endsWith(`:${node.id}`)", ui)
        self.assertIn("prompt.output = Object.fromEntries", ui)
        self.assertIn("node.constructor.nodeData.output_node = true", ui)
        self.assertNotIn("partialExecutionTargets: executionTargets", ui)
        self.assertNotIn("app.queuePrompt(0, 1, executionTargets)", ui)
        self.assertIn('api.addEventListener("execution_success", completedWithoutNodeResult)', ui)
        self.assertIn("reviseButton.disabled = false", ui)
        self.assertIn("node.mode = 0", ui)

    def test_legacy_cache_busting_entries_do_not_register_duplicate_extensions(self):
        web = ROOT / "web"
        legacy_entries = sorted(web.glob("aipm_ui_v*.js"))
        for entry in legacy_entries:
            source = entry.read_text(encoding="utf-8")
            if entry.name in {"aipm_ui_v53.js", "aipm_ui_v54.js", "aipm_ui_v55.js", "aipm_ui_v56.js", "aipm_ui_v57.js", "aipm_ui_v58.js", "aipm_ui_v59.js", "aipm_ui_v60.js", "aipm_ui_v61.js", "aipm_ui_v62.js", "aipm_ui_v63.js", "aipm_ui_v64.js", "aipm_ui_v65.js", "aipm_ui_v66.js"}:
                expected = entry.stem.rsplit("v", 1)[-1]
                self.assertIn(f'import "./aipm_ui.js?v={expected}"', source)
                continue
            self.assertNotIn('import "./aipm_ui.js?', source, entry.name)
            self.assertNotIn("app.registerExtension", source, entry.name)
        ui = (web / "aipm_ui.js").read_text(encoding="utf-8")
        import re
        version = re.search(r"const VERSION = (\d+);", ui).group(1)
        self.assertIn(f"globalThis.__COMFYUI_AIPM_UI_VERSION__ < {version}", ui)
        self.assertIn(f"globalThis.__COMFYUI_AIPM_UI_VERSION__ = {version}", ui)
        self.assertIn('"CineTimelinePlan", "CineTimelineKeyframePlan"', ui)
        self.assertIn("const link = activeGraph.links?.[linkId]", ui)
        self.assertIn("writeTextToLinkedPreviews(node, output)", ui)
        self.assertIn('"视频提示词预览"', ui)

    def test_all_prompt_nodes_have_offline_cached_output_button(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn('node.addWidget("button", "输出缓存"', ui)
        self.assertIn("async function outputCachedResult()", ui)
        self.assertIn('null, outputCachedResult, { serialize: false }', ui)
        self.assertIn('null, clearCachedResult, { serialize: false }', ui)
        self.assertIn('node.addDOMWidget?.("aipm_image_actions"', ui)
        self.assertIn('setStatus("正在从本地缓存重新输出，不调用远程服务……")', ui)
        self.assertIn('currentAction === "cache"', ui)
        self.assertIn('"AIPMImagePrompt", "AIPMVideoPrompt", "AIPMPromptRefinement"', ui)

    def test_video_node_reuses_original_outputs_for_cinetimeline(self):
        node = nodes.AIPMVideoPromptCore
        self.assertEqual(node.RETURN_TYPES, ("CINE_TIMELINE", "STRING", "STRING", "STRING", "STRING"))
        self.assertEqual(node.RETURN_NAMES[0], "提示词数据")
        self.assertEqual(node.RETURN_NAMES[-1], "完整结果 JSON")

    def test_image_prompt_is_independently_executable_output_node(self):
        self.assertTrue(nodes.AIPMImagePrompt.OUTPUT_NODE)
        optional = nodes.AIPMImagePrompt.INPUT_TYPES()["optional"]
        self.assertIn("image1", optional)
        self.assertIn("image2", optional)
        self.assertIn("image3", optional)
        self.assertEqual([name for name in optional if name.startswith("image")], [f"image{i}" for i in range(1, 10)])
        for name in (f"image{i}" for i in range(1, 10)):
            self.assertIn(name, inspect.signature(nodes.AIPMImagePrompt.generate).parameters)
        self.assertNotIn("参考图片", optional)
        self.assertNotIn("重新生成标记", optional)
        self.assertNotIn("修改模式", optional)
        self.assertNotIn("启用图像分析", nodes.AIPMImagePrompt.INPUT_TYPES()["required"])

    def test_image_prompt_collects_three_reference_ports_in_order(self):
        node = nodes.AIPMImagePrompt()
        original_encode = nodes.encode_image_batch
        original_analyze = nodes.ReferenceAnalysisPipeline.analyze_images
        original_request = nodes.OpenAICompatibleClient.request_object
        encoded_calls = []

        def fake_encode(value, limit=9):
            if value is None:
                return []
            encoded_calls.append((value, limit))
            return [{"sha256": str(value), "data_url": "data:image/jpeg;base64,AA=="}]

        nodes.encode_image_batch = fake_encode
        nodes.ReferenceAnalysisPipeline.analyze_images = classmethod(
            lambda cls, url, model, images, reference_roles="": (
                [{"picture_id": f"<Picture {i + 1}>", "visual_profile": item["sha256"]}
                 for i, item in enumerate(images)],
                0,
            )
        )
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, url, payload, stage, **kwargs: ({
                "positive_prompt": "three refs", "negative_prompt": "",
                "composition_notes": "", "reference_usage": [],
                "quality_features": ["a", "b", "c", "d"],
                "emphasis_features": ["subject"],
            }, {"usage": {}})
        )
        manifest = json.dumps([
            {"media_type": "image", "asset_id": "one.png"},
            {"media_type": "image", "asset_id": "two.png"},
            {"media_type": "image", "asset_id": "three.png"},
        ])
        try:
            response = node.generate(
                "三图参考", "http://host/v1", "model.gguf", "通用生图模型",
                "1:1", "中文", "one", image2="two", image3="three",
                修改意见="__AIPM_RUN_V1__test", 参考素材清单JSON=manifest,
            )
            analysis_only = node.generate(
                "三图参考", "http://host/v1", "model.gguf", "通用生图模型",
                "1:1", "中文", "one", image2="two", image3="three",
                修改意见="__AIPM_RUN_V1__test", 参考素材清单JSON=manifest,
                参考图用途="仅分析参考",
            )
        finally:
            nodes.encode_image_batch = original_encode
            nodes.ReferenceAnalysisPipeline.analyze_images = original_analyze
            nodes.OpenAICompatibleClient.request_object = original_request
        package = response["result"][0]
        self.assertEqual([item[0] for item in encoded_calls[:3]], ["one", "two", "three"])
        self.assertEqual(package["reference_count"], 3)
        self.assertEqual(package["reference_profiles"][2]["picture_id"], "<Picture 3>")
        self.assertIn("image1（参考图1）", package["positive_prompt"])
        self.assertIn("image2（参考图2）", package["positive_prompt"])
        self.assertIn("image3（参考图3）", package["positive_prompt"])
        self.assertEqual(
            [item["asset_id"] for item in package["reference_binding_order"]],
            ["one.png", "two.png", "three.png"],
        )
        self.assertEqual(analysis_only["result"][0]["reference_mode"], "仅分析参考")
        self.assertEqual(analysis_only["result"][0]["reference_binding_prompt"], "")
        self.assertEqual(analysis_only["result"][1], "three refs")

    def test_endpoint_accepts_v1_base(self):
        self.assertEqual(nodes.OpenAICompatibleClient.endpoint("http://host:8080/v1"), "http://host:8080/v1/chat/completions")

    def test_market_model_profiles_are_ranked_combo(self):
        choices = nodes.AIPMImagePrompt.INPUT_TYPES()["required"]["目标生图模型"][0]
        self.assertEqual(choices[0], "自动判断 / 通用（推荐）")
        self.assertIn("中文自然语言（闭源模型通用）", choices)
        self.assertIn("Stable Diffusion 1.x", choices)
        self.assertIn("Pony Diffusion / Pony 系模型", choices)
        self.assertIn("FLUX.2 多参考编辑", choices)
        self.assertIn("Krea 2 身份编辑", choices)
        self.assertIn("Qwen Image 多图编辑", choices)
        self.assertLessEqual(len(choices), 25)
        self.assertTrue(set(choices).issubset(nodes.PROMPT_SKILL_BY_PROFILE))

    def test_each_profile_loads_a_nonempty_specialized_skill(self):
        loaded = {}
        for profile in nodes.IMAGE_MODEL_PROFILES:
            skill_id, instructions = nodes.load_prompt_skill(profile)
            loaded[profile] = skill_id
            self.assertTrue(instructions.startswith("# "))
            self.assertNotIn("[TODO", instructions)
        self.assertEqual(loaded["Pony Diffusion / Pony 系模型"], "aipm-pony-booru")
        self.assertEqual(loaded["Krea 2 / Krea 2 Turbo 文生图"], "aipm-krea2-director")
        self.assertEqual(loaded["Krea 2 身份编辑"], "aipm-krea2-identity-edit")
        self.assertEqual(loaded["FLUX.2 多参考编辑"], "aipm-flux2-edit")
        self.assertEqual(loaded["Qwen Image 多图编辑"], "aipm-qwen-image-edit")
        self.assertEqual(loaded["Anima 系列"], "aipm-anima")
        self.assertTrue(nodes.NATIVE_QUALITY_ANCHORS["Pony Diffusion / Pony 系模型"].startswith("score_9"))
        self.assertIn("masterpiece", nodes.NATIVE_QUALITY_ANCHORS["Illustrious / NoobAI 系模型"])

    def test_release_matrix_covers_every_active_specialized_skill(self):
        matrix = json.loads((ROOT / "tests" / "skill_release_matrix.json").read_text(encoding="utf-8"))
        covered = {item["skill"] for item in matrix["scenarios"]}
        active = {
            nodes.load_prompt_skill(profile)[0]
            for profile in [*nodes.IMAGE_MODEL_PROFILES, *nodes.VIDEO_MODEL_PROFILES]
        }
        exempt_fallbacks = {
            "aipm-general-natural", "aipm-sd-weighted", "aipm-pony-booru",
            "aipm-sd3-modern", "aipm-chinese-multimodal", "aipm-video-general",
        }
        self.assertFalse((active - exempt_fallbacks) - covered)
        self.assertEqual(matrix["release_gate"]["compare"], ["without_skill", "with_skill"])
        self.assertGreaterEqual(len(matrix["scenarios"]), 15)

    def test_automatic_language_follows_model_prompt_dialect(self):
        self.assertEqual(nodes.resolve_prompt_language("Qwen Image 系列", "自动适配（推荐）"), "zh-CN")
        self.assertEqual(nodes.resolve_prompt_language("Krea 2 / Krea 2 Turbo 系列", "自动适配（推荐）"), "en")
        self.assertEqual(nodes.resolve_prompt_language("Pony Diffusion / Pony 系模型", "自动适配（推荐）"), "en-tags")
        self.assertEqual(nodes.resolve_prompt_language("FLUX.1 / FLUX.2 系列", "中文"), "zh-CN")

    def test_krea_rejects_chinese_reference_definitions(self):
        with self.assertRaises(nodes.PromptAssistantError):
            nodes.AIPMImagePrompt.validate_generated_language({
                "positive_prompt": "A cinematic portrait",
                "negative_prompt": "blur",
                "reference_usage": ["<Picture 1> 用于人物身份和服装"],
            }, "en")

    def test_english_tag_models_reject_chinese_reference_definitions(self):
        with self.assertRaises(nodes.PromptAssistantError):
            nodes.AIPMImagePrompt.validate_generated_language({
                "positive_prompt": "score_9, 1girl, portrait",
                "negative_prompt": "lowres",
                "reference_usage": ["<Picture 1> 用作服装参考"],
            }, "en-tags")

    def test_english_binding_does_not_reuse_legacy_chinese_definition(self):
        binding = nodes.AIPMImagePrompt.compile_reference_binding_prompt(
            [{"picture_id": "<Picture 1>"}],
            ["<Picture 1> 用于人物身份和服装"],
            "en",
        )
        self.assertIn("image1 (reference image 1)", binding)
        self.assertNotRegex(binding, r"[\u3400-\u9fff]")

    def test_multi_reference_result_requires_every_picture_role(self):
        candidate = {
            "positive_prompt": "Two distinct people in a studio",
            "negative_prompt": "",
            "reference_usage": ["<Picture 1> defines the woman on the left"],
        }
        with self.assertRaisesRegex(nodes.PromptAssistantError, "<Picture 2>"):
            nodes.AIPMImagePrompt.validate_generated_result(candidate, "en", 2, "多参考改图")
        candidate["reference_usage"].append("<Picture 2> defines the man on the right")
        nodes.AIPMImagePrompt.validate_generated_result(candidate, "en", 2, "多参考改图")

    def test_anima_full_body_requires_complete_non_competing_framing_contract(self):
        weak = {
            "positive_prompt": "masterpiece, best quality, 1girl, standing, full body, portrait",
            "negative_prompt": "cropped",
            "reference_usage": [],
        }
        with self.assertRaisesRegex(nodes.PromptAssistantError, "Anima 全身构图契约不完整"):
            nodes.AIPMImagePrompt.validate_generated_result(
                weak, "en-tags", 0, "无参考图", "纯色背景全身图", "Anima 系列",
            )
        strong = {
            "positive_prompt": (
                "masterpiece, best quality, highres, safe, 1girl, solo, (full body:1.2), "
                "head-to-toe, entire figure visible, both feet visible, long shot, standing on the ground. "
                "A full-length character illustration with clear space above her head and below both feet; "
                "her complete body remains inside the frame without any crop."
            ),
            "negative_prompt": (
                "cropped, accidental crop, cropped feet, feet out of frame, lower body out of frame, "
                "upper body, close-up"
            ),
            "reference_usage": [],
        }
        nodes.AIPMImagePrompt.validate_generated_result(
            strong, "en-tags", 0, "无参考图", "纯色背景全身图", "Anima 系列",
        )

    def test_anima_rejects_more_than_three_weighted_concepts(self):
        candidate = {
            "positive_prompt": "1girl, (full body:1.2), (red dress:1.1), (blue eyes:1.1), (smile:1.1)",
            "negative_prompt": "cropped",
            "reference_usage": [],
        }
        with self.assertRaisesRegex(nodes.PromptAssistantError, "最多只能加权 3 个"):
            nodes.AIPMImagePrompt.validate_generated_result(
                candidate, "en-tags", 0, "无参考图", "一个女孩", "Anima 系列",
            )

    def test_official_prompt_family_rules_are_preserved(self):
        _, flux = nodes.load_prompt_skill("FLUX.1 / FLUX.2 系列")
        _, qwen = nodes.load_prompt_skill("Qwen Image 系列")
        _, krea = nodes.load_prompt_skill("Krea 2 / Krea 2 Turbo 系列")
        _, noobai = nodes.load_prompt_skill("Illustrious / NoobAI 系模型")
        _, anima = nodes.load_prompt_skill("Anima 系列")
        self.assertIn("清晰自然语言", flux)
        self.assertIn("英文双引号", flux)
        self.assertIn("景别可见且参考支持", qwen)
        self.assertIn("内容、主体和构图", krea)
        self.assertIn("NoobAI XL 1.1 官方模型卡", noobai)
        self.assertIn("Anima 是独立的动漫/插画模型家族", anima)
        self.assertIn("both feet visible", anima)
        self.assertNotIn("Stable Diffusion 1.x", nodes.NATIVE_QUALITY_ANCHORS)
        self.assertNotIn("Stable Diffusion XL 基础模型", nodes.NATIVE_QUALITY_ANCHORS)

    def test_h3_skill_loads_only_the_selected_official_mode_contract(self):
        _, base = nodes.load_prompt_skill("MiniMax H3 FL2VA（首尾帧）", "h3_fl2va")
        _, ref = nodes.load_prompt_skill("MiniMax H3 Ref2VA（多参考）", "h3_ref2va")
        self.assertIn("# Official Base-mode contract", base)
        self.assertNotIn("# Official Ref2VA contract", base)
        self.assertIn("# Official Ref2VA contract", ref)
        self.assertNotIn("# Official Base-mode contract", ref)

    def test_h3_structure_validation_enforces_mode_order_and_timestamps(self):
        base = (
            "integrated_multimodal_description: [Shot 1] 角色听见响声后停步，缓慢回头并在结尾站稳，"
            "镜头小幅推近，呼吸与衣料摩擦同步。\n\n"
            "overall_soundscape: 雨声、脚步声和短促吸气。\n\n"
            "non_diegetic_music: N/A"
        )
        nodes.AIPMVideoPromptCore.validate_h3_structure(base, "text_to_video", 8)
        with self.assertRaises(nodes.PromptAssistantError):
            nodes.AIPMVideoPromptCore.validate_h3_structure(base, "h3_ref2va", 8)
        boundary_time = base.replace("[Shot 1]", "[Shot 1] [Shot 2] At 00:08.000,")
        nodes.AIPMVideoPromptCore.validate_h3_structure(boundary_time, "text_to_video", 8)
        invalid_time = base.replace("[Shot 1]", "[Shot 1] [Shot 2] At 00:08.001,")
        with self.assertRaises(nodes.PromptAssistantError):
            nodes.AIPMVideoPromptCore.validate_h3_structure(invalid_time, "text_to_video", 8)

    def test_extracts_fenced_json(self):
        value = nodes.OpenAICompatibleClient.parse_object('```json\n{"positive_prompt":"中文"}\n```')
        self.assertEqual(value["positive_prompt"], "中文")

    def test_professional_contract_is_required_by_schema(self):
        schema = nodes.AIPMImagePrompt.response_format()["json_schema"]["schema"]
        self.assertIn("quality_features", schema["required"])
        self.assertIn("emphasis_features", schema["required"])
        self.assertEqual(schema["properties"]["quality_features"].get("minItems", 0), 0)
        self.assertEqual(schema["properties"]["emphasis_features"].get("minItems", 0), 0)

    def test_transient_connection_error_is_retried(self):
        calls = []
        original_request = nodes.OpenAICompatibleClient.request
        original_sleep = nodes.time.sleep

        def flaky_request(cls, url, payload, timeout=300.0):
            calls.append(url)
            if len(calls) == 1:
                raise nodes.PromptAssistantError("远程服务连接失败：reset")
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        nodes.OpenAICompatibleClient.request = classmethod(flaky_request)
        nodes.time.sleep = lambda seconds: None
        try:
            result, _ = nodes.OpenAICompatibleClient.request_object(
                "http://host/v1", {"messages": []}, "测试", attempts=2
            )
        finally:
            nodes.OpenAICompatibleClient.request = original_request
            nodes.time.sleep = original_sleep
        self.assertTrue(result["ok"])
        self.assertEqual(len(calls), 2)

    def test_reference_images_are_analyzed_individually_and_cached(self):
        nodes.ReferenceAnalysisPipeline._image_cache.clear()
        calls = []
        original = nodes.OpenAICompatibleClient.request
        nodes.OpenAICompatibleClient.request = classmethod(
            lambda cls, url, payload, timeout=300.0: (
                calls.append(payload) or {"choices": [{"message": {"content": "视觉档案"}}]}
            )
        )
        images = [
            {"sha256": "a", "data_url": "data:image/jpeg;base64,AA=="},
            {"sha256": "b", "data_url": "data:image/jpeg;base64,AA=="},
        ]
        try:
            profiles, hits = nodes.ReferenceAnalysisPipeline.analyze_images("http://host/v1", "model", images)
            cached_profiles, cached_hits = nodes.ReferenceAnalysisPipeline.analyze_images("http://host/v1", "model", images)
        finally:
            nodes.OpenAICompatibleClient.request = original
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(hits, 0)
        self.assertEqual(cached_hits, 2)
        self.assertEqual(cached_profiles[1]["picture_id"], "<Picture 2>")

    def test_node_returns_independent_package(self):
        node = nodes.AIPMImagePrompt()
        original = nodes.OpenAICompatibleClient.request_object
        nodes.OpenAICompatibleClient.request_object = classmethod(lambda cls, url, payload, stage, **kwargs: ({
            "positive_prompt": "电影感人物肖像", "negative_prompt": "模糊",
            "composition_notes": "半身构图", "reference_usage": [],
        }, {"usage": {"total_tokens": 10}}))
        try:
            response = node.generate(
                "一个人物肖像", "http://host/v1", "model.gguf", "通用生图模型",
                "1:1", "中文", None, 修改意见="__AIPM_RUN_V1__test",
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original
        package, positive, negative, raw = response["result"]
        self.assertEqual(package["schema"], "aipm_image_prompt")
        self.assertEqual(positive, "电影感人物肖像")
        self.assertEqual(negative, "模糊")
        self.assertEqual(json.loads(raw)["usage"]["total_tokens"], 10)
        self.assertEqual(response["ui"]["text"][0], positive)
        self.assertEqual(package["prompt_skill_id"], "aipm-general-natural")

    def test_revision_uses_previous_result_and_increments_version(self):
        node = nodes.AIPMImagePrompt()
        captured = []
        original = nodes.OpenAICompatibleClient.request_object

        def revised(cls, url, payload, stage, **kwargs):
            captured.append(payload)
            return ({
                "positive_prompt": "短发女侦探，冷峻近景",
                "negative_prompt": "模糊",
                "composition_notes": "胸像",
                "reference_usage": [],
            }, {"usage": {}})

        nodes.OpenAICompatibleClient.request_object = classmethod(revised)
        previous = json.dumps({
            "positive_prompt": "长发女侦探",
            "negative_prompt": "模糊",
            "composition_notes": "中景",
            "reference_usage": [],
            "revision": 1,
        }, ensure_ascii=False)
        revision_request = "__AIPM_REVISION_V1__" + json.dumps({
            "instruction": "改成短发和胸像", "previous_result": previous,
        }, ensure_ascii=False)
        try:
            response = node.generate(
                "雨夜女侦探", "http://host/v1", "model.gguf", "通用生图模型",
                "1:1", "中文", None,
                revision_request, previous,
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original
        package = response["result"][0]
        request_context = json.loads(captured[0]["messages"][1]["content"][0]["text"])
        self.assertEqual(package["revision"], 2)
        self.assertEqual(package["modification_request"], "改成短发和胸像")
        self.assertEqual(request_context["previous_result"]["positive_prompt"], "长发女侦探")

    def test_video_node_exposes_minimax_h3_and_media_inputs(self):
        inputs = nodes.AIPMVideoPromptCore.INPUT_TYPES()
        self.assertEqual(inputs["required"]["目标视频模型"][0], ["MiniMax H3"])
        self.assertEqual(inputs["required"]["视频时长"][0], "INT")
        self.assertEqual(inputs["required"]["视频时长"][1]["default"], 15)
        self.assertEqual(inputs["required"]["视频时长"][1]["min"], 4)
        self.assertEqual(inputs["required"]["视频时长"][1]["max"], 30)
        self.assertEqual(inputs["required"]["分段数量"][0], "INT")
        self.assertEqual(inputs["required"]["分段数量"][1]["default"], 1)
        self.assertIn("image1", inputs["optional"])
        self.assertIn("image4", inputs["optional"])
        self.assertIn("video1", inputs["optional"])
        self.assertIn("audio1", inputs["optional"])
        self.assertEqual([name for name in inputs["optional"] if name.startswith("image")], [f"image{i}" for i in range(1, 10)])
        self.assertEqual([name for name in inputs["optional"] if name.startswith("video")], [f"video{i}" for i in range(1, 4)])
        self.assertEqual([name for name in inputs["optional"] if name.startswith("audio")], [f"audio{i}" for i in range(1, 4)])
        signature = inspect.signature(nodes.AIPMVideoPromptCore.generate).parameters
        for name in [*(f"image{i}" for i in range(1, 10)), *(f"video{i}" for i in range(1, 4)), *(f"audio{i}" for i in range(1, 4))]:
            self.assertIn(name, signature)

    def test_reference_ports_use_one_dynamic_trailing_placeholder(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("function syncDynamicReferenceInputs(node)", ui)
        self.assertIn('return { image: 9, video: 3, audio: 3 }', ui)
        self.assertIn("input.link != null", ui)
        self.assertIn("number !== availableNumber", ui)
        self.assertIn("node.removeInput?.(slot)", ui)
        self.assertIn("node.addInput?.(`${prefix}${availableNumber}`, type)", ui)
        self.assertIn("nodeType.prototype.onConnectionsChange", ui)

    def test_image_node_does_not_install_video_preview_widget(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("const videoPromptPreview = isVideo &&", ui)
        self.assertIn("if (videoPromptPreview) nativeWidgets.push(videoPromptPreview)", ui)
        self.assertIn('panelRoot.className = "aipm-image-actions-v76"', ui)
        self.assertIn('gridAutoRows: "20px"', ui)
        self.assertIn('alignContent: "start"', ui)
        self.assertIn("const resizeContentInput = (nextHeight) =>", ui)
        self.assertIn("contentInput._aipmAdaptiveHeight = adaptiveHeight", ui)
        self.assertIn("resizeContentInput(Number(nextSize[1]))", ui)
        self.assertIn("node._aipmFitContentInput = () =>", ui)
        self.assertIn("72 + Number(nextHeight) - (minimumHeight || Number(nextHeight)) - 8", ui)
        self.assertIn("panelWidget.computeSize = (width) => [width, 86]", ui)
        self.assertIn("contentInput._aipmAdaptiveHeight = 72", ui)
        self.assertIn("this.bodyHeight - start - occupied - 8", ui)
        self.assertIn('"正向提示词": textValues[0]', ui)
        self.assertIn('String(targetInput?.type || "").toUpperCase() !== "STRING"', ui)
        self.assertIn("targetWidget.value = String(value)", ui)
        self.assertIn('height: "20px", minHeight: "20px"', ui)
        self.assertIn("getMinHeight: () => 86", ui)
        self.assertIn('["自动判断 / 通用（推荐）", "Krea 2 / Krea 2 Turbo 系列"]', ui)
        self.assertIn('widget.value = "Krea 2 / Krea 2 Turbo 文生图"', ui)
        self.assertIn('node.addDOMWidget?.("aipm_image_actions"', ui)
        self.assertIn('["生成 / 重新创作", () => run(false)]', ui)

    def test_video_mode_resolution(self):
        resolve = nodes.AIPMVideoPromptCore._resolve_mode
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断", 0, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断", 1, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断", 2, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断", 3, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断", 1, True, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "关键帧", 3, False, False), "h3_keyframe")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "多模态", 1, True, True), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断（推荐）", 0, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断（推荐）", 1, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3 FL2VA（首尾帧）", "自动判断（推荐）", 2, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "首帧 I2VA", 1, False, False), "h3_i2va")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "尾帧 L2VA", 1, False, False), "h3_l2va")

    def test_specialized_video_profiles_do_not_use_generic_fallback(self):
        self.assertEqual(nodes.load_prompt_skill("Wan 系列")[0], "aipm-wan-video")
        self.assertEqual(nodes.load_prompt_skill("LTX-Video 系列")[0], "aipm-ltx-video")
        self.assertEqual(nodes.load_prompt_skill("HunyuanVideo 系列")[0], "aipm-hunyuan-video")
        modes = nodes.AIPMVideoPromptCore.INPUT_TYPES()["required"]["生成模式"][0]
        self.assertEqual(modes, ["多模态", "关键帧"])
        self.assertEqual(nodes.AIPMVideoPromptCore.INPUT_TYPES()["required"]["生成模式"][1]["default"], "多模态")

    def test_timeline_plan_schema_requires_exact_segment_count(self):
        schema = nodes.AIPMVideoPromptCore.timeline_plan_format(3)["json_schema"]["schema"]
        segments = schema["properties"]["segments"]
        self.assertEqual(segments["minItems"], 3)
        self.assertEqual(segments["maxItems"], 3)
        self.assertIn("dialogue_lines", segments["items"]["required"])
        self.assertIn("transition", segments["items"]["required"])
        self.assertEqual(segments["items"]["properties"]["transition"]["enum"], ["cut", "motion_context"])

    def test_dialogue_speaker_ids_are_bound_locally(self):
        prompt = "母亲说道：<d>[Chinese] 到了给妈打电话。</d> 女儿回答：<d>[Chinese] 知道了，妈。</d>"
        bound = nodes.AIPMVideoPromptCore.bind_dialogue_speaker_ids(
            prompt, ["母亲：到了给妈打电话。", "女儿：知道了，妈。"],
        )
        self.assertIn("(S1) <d>[Chinese] 到了给妈打电话。</d>", bound)
        self.assertIn("(S2) <d>[Chinese] 知道了，妈。</d>", bound)

    def test_dialogue_speaker_binding_does_not_duplicate_existing_clause_id(self):
        prompt = "母亲 (S1) 以温和的声音说道：<d>[Chinese] 到了给妈打电话。</d>"
        bound = nodes.AIPMVideoPromptCore.bind_dialogue_speaker_ids(
            prompt, ["母亲：到了给妈打电话。"],
        )
        self.assertEqual(bound.count("(S1)"), 1)
        self.assertEqual(
            nodes.AIPMVideoPromptCore.bind_dialogue_speaker_ids(
                bound, ["母亲：到了给妈打电话。"],
            ),
            bound,
        )

    def test_dialogue_speaker_binding_removes_duplicate_same_id_in_clause(self):
        prompt = "母亲 (S1) 低声说道：(S1) <d>[Chinese] 到了给妈打电话。</d>"
        bound = nodes.AIPMVideoPromptCore.bind_dialogue_speaker_ids(
            prompt, ["母亲：到了给妈打电话。"],
        )
        self.assertEqual(bound.count("(S1)"), 1)

    def test_h3_compiler_keeps_local_source_separate(self):
        local = "integrated_multimodal_description: 当前分段动作\n\noverall_soundscape: 雨声\n\nnon_diegetic_music: N/A"
        compiled = nodes.AIPMVideoPromptCore.compile_h3_prompt(local, "统一电影风格", "身份漂移")
        self.assertNotIn("统一电影风格", local)
        self.assertIn("统一电影风格", compiled)
        self.assertIn("视觉限制：避免出现身份漂移", compiled)

    def test_cinetimeline_adapter_preserves_prompt_layers(self):
        package = {
            "schema": "aipm_video_timeline", "revision": 2,
            "global": {"prompt": "统一电影风格", "negative_prompt": "身份漂移", "reference_ids": []},
            "segments": [{
                "segment_id": "SEGMENT_001", "duration": 5,
                "source_prompt": "远端原始", "timeline_local_prompt": "时间线局部",
                "compiled_prompt": "独立执行成品", "dialogue_lines": [],
                "reference_ids": [], "effective_reference_ids": [],
                "opening_state": "门外", "ending_state": "门内",
                "continuity_from_previous": "",
            }],
            "reference_profiles": [], "video_prompt": "独立执行成品",
        }
        response = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")
        timeline = response["result"][0]
        self.assertEqual(timeline["global_prompt"], "统一电影风格")
        self.assertEqual(timeline["shots"][0]["local_prompt"], "时间线局部")
        self.assertEqual(timeline["shots"][0]["metadata"]["aipm_source_prompt"], "远端原始")
        self.assertEqual(response["result"][3], "独立执行成品")

    def test_cinetimeline_adapter_preserves_remote_segment_transition(self):
        package = {
            "schema": "aipm_video_timeline", "revision": 1,
            "global": {"prompt": "电影风格", "negative_prompt": "", "reference_ids": []},
            "segments": [
                {"segment_id": "SEGMENT_001", "duration": 5, "timeline_local_prompt": "建立场景",
                 "transition": "cut", "reference_ids": [], "effective_reference_ids": []},
                {"segment_id": "SEGMENT_002", "duration": 5, "timeline_local_prompt": "近景连续动作",
                 "transition": "motion_context", "reference_ids": [], "effective_reference_ids": []},
                {"segment_id": "SEGMENT_003", "duration": 5, "timeline_local_prompt": "切回远景",
                 "transition": "cut", "reference_ids": [], "effective_reference_ids": []},
            ],
            "reference_profiles": [], "video_prompt": "建立场景",
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "motion_context")["result"][0]
        self.assertEqual([shot["transition"] for shot in timeline["shots"]],
                         ["cut", "motion_context", "cut"])

    def test_cinetimeline_adapter_preserves_reloadable_reference_assets(self):
        package = {
            "schema": "aipm_video_timeline", "revision": 1,
            "global": {"prompt": "电影风格", "negative_prompt": "", "reference_ids": ["<Picture 1>"]},
            "segments": [{
                "segment_id": "SEGMENT_001", "duration": 5,
                "timeline_local_prompt": "<Picture 1>缓慢回头", "compiled_prompt": "成品",
                "reference_ids": ["<Picture 1>"], "effective_reference_ids": ["<Picture 1>"],
            }],
            "reference_profiles": [{
                "picture_id": "<Picture 1>", "asset_id": "aipm_assets/aipm_test.png",
                "filename": "aipm_test.png", "subfolder": "aipm_assets",
                "storage_type": "input", "sha256": "abc", "width": 640, "height": 480,
            }],
            "video_prompt": "成品",
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"][0]
        reference = timeline["references"][0]
        self.assertEqual(reference["asset_id"], "aipm_assets/aipm_test.png")
        self.assertEqual(reference["scope"], "global")
        self.assertEqual(reference["metadata"]["sha256"], "abc")

    def test_keyframe_adapter_has_no_global_references_and_repeats_order_per_segment(self):
        profiles = [
            {"picture_id": f"<Picture {index}>", "asset_id": f"frame{index}.png"}
            for index in range(1, 4)
        ]
        package = {
            "schema": "aipm_video_timeline", "revision": 1,
            "generation_mode": "h3_keyframe",
            "global": {"prompt": "电影风格", "negative_prompt": "", "reference_ids": []},
            "segments": [{
                "segment_id": f"SEGMENT_{index:03d}", "duration": 5,
                "timeline_local_prompt": "动作", "compiled_prompt": "成品",
                "reference_ids": [item["picture_id"] for item in profiles],
                "effective_reference_ids": [item["picture_id"] for item in profiles],
            } for index in range(1, 3)],
            "reference_profiles": profiles, "video_prompt": "成品",
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"][0]
        self.assertEqual(timeline["schema"], "cine_keyframe_timeline")
        self.assertFalse(any(ref["scope"] == "global" for ref in timeline["references"]))
        self.assertEqual(len(timeline["references"]), 6)
        first_segment = [ref for ref in timeline["references"] if ref["shot_id"] == "SEGMENT_001"]
        self.assertEqual([ref["asset_id"] for ref in first_segment], ["frame1.png", "frame2.png", "frame3.png"])
        self.assertEqual([ref["keyframe_role"] for ref in first_segment], ["first", "guide", "last"])
        self.assertEqual([ref["keyframe_frame"] for ref in first_segment], [0, 60, 119])

    def test_keyframe_adapter_uses_remote_planned_middle_frame(self):
        profiles = [
            {"picture_id": f"<Picture {index}>", "asset_id": f"frame{index}.png"}
            for index in range(1, 4)
        ]
        bindings = [
            {"reference_id": "<Picture 1>", "local_frame": 0, "placement_reason": "首帧"},
            {"reference_id": "<Picture 2>", "local_frame": 83, "placement_reason": "动作落点"},
            {"reference_id": "<Picture 3>", "local_frame": 119, "placement_reason": "尾帧"},
        ]
        package = {
            "schema": "aipm_video_timeline", "generation_mode": "h3_keyframe",
            "global": {"prompt": "", "negative_prompt": "", "reference_ids": []},
            "segments": [{
                "segment_id": "SEGMENT_001", "duration": 5, "timeline_local_prompt": "动作",
                "reference_ids": [item["picture_id"] for item in profiles],
                "effective_reference_ids": [item["picture_id"] for item in profiles],
                "keyframe_bindings": bindings,
            }],
            "reference_profiles": profiles, "video_prompt": "动作",
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"][0]
        self.assertEqual([ref["keyframe_frame"] for ref in timeline["references"]], [0, 83, 119])
        self.assertEqual(timeline["references"][1]["keyframe_placement_reason"], "动作落点")

    def test_keyframe_adapter_without_images_is_text_to_video_conditioning(self):
        package = {
            "schema": "aipm_video_timeline", "generation_mode": "h3_keyframe",
            "global": {"prompt": "电影风格", "negative_prompt": "", "reference_ids": []},
            "segments": [{
                "segment_id": "SEGMENT_001", "duration": 5,
                "timeline_local_prompt": "人物从门口走到窗边", "effective_reference_ids": [],
            }],
            "reference_profiles": [], "video_prompt": "人物从门口走到窗边",
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"][0]
        self.assertEqual(timeline["schema"], "cine_keyframe_timeline")
        self.assertEqual(timeline["references"], [])
        self.assertEqual(timeline["metadata"]["conditioning_mode"], "text_to_video")

    def test_keyframe_timeline_cache_unwraps_authoring_package(self):
        authoring = {"schema": "aipm_video_timeline", "video_prompt": "成品提示词"}
        cached = {"schema": "cine_keyframe_timeline", "metadata": {"aipm": authoring}}
        self.assertIs(nodes.AIPMVideoPromptCore._authoring_data(cached), authoring)

    def test_cinetimeline_adapter_maps_video_and_audio_assets(self):
        package = {
            "schema": "aipm_video_timeline", "revision": 1,
            "global": {"prompt": "电影风格", "negative_prompt": "", "reference_ids": []},
            "segments": [{
                "segment_id": "SEGMENT_001", "duration": 5,
                "timeline_local_prompt": "使用<Video 1>的运动和<Audio 1>的声音",
                "compiled_prompt": "成品", "effective_reference_ids": ["<Video 1>", "<Audio 1>"],
            }],
            "reference_profiles": [], "video_prompt": "成品",
            "media_assets": {
                "videos": [{"asset_id": "aipm_assets/video.mp4", "filename": "video.mp4"}],
                "audios": [{"asset_id": "aipm_assets/audio.wav", "filename": "audio.wav"}],
            },
        }
        timeline = nodes.AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"][0]
        by_type = {item["media_type"]: item for item in timeline["references"]}
        self.assertEqual(by_type["video"]["asset_id"], "aipm_assets/video.mp4")
        self.assertEqual(by_type["audio"]["asset_id"], "aipm_assets/audio.wav")
        self.assertEqual(by_type["video"]["scope"], "global")

    def test_multi_segment_package_is_assembled_locally(self):
        node = nodes.AIPMVideoPromptCore()
        original_object = nodes.OpenAICompatibleClient.request_object
        original_text = nodes.OpenAICompatibleClient.request_text
        plan = {
            "global_prompt": "统一写实电影风格", "global_negative_prompt": "身份漂移",
            "global_reference_ids": ["<Picture 1>"],
            "global_reference_bindings": ["<Picture 1> 全局继承人物身份"],
            "segments": [
                {"segment_id": "x", "title": "第一段", "duration": 6, "brief": "进入房间",
                 "negative_prompt": "跳切", "reference_ids": [], "opening_state": "门外",
                 "ending_state": "门内", "continuity_from_previous": ""},
                {"segment_id": "y", "title": "第二段", "duration": 6, "brief": "发现线索",
                 "negative_prompt": "道具漂移", "reference_ids": [], "opening_state": "门内",
                 "ending_state": "拿起信封", "continuity_from_previous": "承接门内状态"},
            ],
        }
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, *args, **kwargs: (plan, {"usage": {"total_tokens": 5}})
        )
        calls = []
        def fake_text(cls, *args, **kwargs):
            calls.append(args[2])
            index = len(calls)
            return (f"subject_definitions:\n<Subject 1> 是 <Picture 1> 中的人物。\nsummary:\nreference generation. 当前分段。\nretention_analysis:\n<Subject 1> 的身份为 fully_preserved。\ndetailed_description: [Shot 1] 第{index}段使用中文描述人物动作、镜头、表演、声音与结束状态，内容足够完整清晰。\n\noverall_soundscape: 环境声。\n\nnon_diegetic_music: N/A", {"usage": {"total_tokens": 7}})
        nodes.OpenAICompatibleClient.request_text = classmethod(fake_text)
        try:
            result = node.generate_timeline_package(
                service_url="http://host/v1", service_model="model", profile="MiniMax H3 Ref2VA（多参考）",
                mode="h3_ref2va", idea="两段剧情", duration_seconds=6, segment_count=2,
                aspect_ratio="16:9", requested_language="中文（推荐）", skill_id="aipm-minimax-h3-video",
                skill="skill", reference_profiles=[{"picture_id": "<Picture 1>", "visual_profile": "人物"}],
                cache_hits=0, has_video=False, has_audio=False, previous=None, modification="",
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original_object
            nodes.OpenAICompatibleClient.request_text = original_text
        timeline = json.loads(result["ui"]["text"][2])
        package = timeline["metadata"]["aipm"]
        self.assertEqual(package["segment_count"], 2)
        self.assertEqual(package["total_duration"], 12)
        self.assertEqual(len(package["segments"]), 2)
        self.assertEqual(package["global"]["reference_ids"], ["<Picture 1>"])
        self.assertEqual(len(calls), 2)

    def test_multimodal_reference_used_by_every_segment_is_promoted_global(self):
        node = nodes.AIPMVideoPromptCore()
        original_object = nodes.OpenAICompatibleClient.request_object
        original_text = nodes.OpenAICompatibleClient.request_text
        plan = {
            "global_prompt": "统一风格", "global_negative_prompt": "",
            "global_reference_ids": [], "global_reference_bindings": [],
            "segments": [
                {"segment_id": "a", "title": "起", "duration": 15, "brief": "人物进门",
                 "negative_prompt": "", "reference_ids": ["<Picture 1>"], "dialogue_lines": [],
                 "opening_state": "门外", "ending_state": "门内", "continuity_from_previous": ""},
                {"segment_id": "b", "title": "承", "duration": 15, "brief": "人物查看桌面",
                 "negative_prompt": "", "reference_ids": ["<Picture 1>"], "dialogue_lines": [],
                 "opening_state": "门内", "ending_state": "桌旁", "continuity_from_previous": "承接"},
            ],
        }
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, *args, **kwargs: (plan, {"usage": {}})
        )
        nodes.OpenAICompatibleClient.request_text = classmethod(
            lambda cls, *args, **kwargs: (
                "subject_definitions:\n<Subject 1> 是 <Picture 1> 中的人物。\nsummary:\nreference generation. 当前阶段。\nretention_analysis:\n<Subject 1> 的身份为 fully_preserved。\ndetailed_description: [Shot 1] 人物完成当前阶段动作并稳定落定，镜头清晰连续。\n\n"
                "overall_soundscape: 环境声。\n\nnon_diegetic_music: N/A", {"usage": {}}
            )
        )
        try:
            result = node.generate_timeline_package(
                service_url="http://host/v1", service_model="model", profile="MiniMax H3",
                mode="h3_ref2va", idea="两段剧情", duration_seconds=15, segment_count=2,
                aspect_ratio="16:9", requested_language="中文（推荐）",
                skill_id="aipm-minimax-h3-video", skill="skill",
                reference_profiles=[{"picture_id": "<Picture 1>", "visual_profile": "人物"}],
                cache_hits=0, has_video=False, has_audio=False, previous=None, modification="",
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original_object
            nodes.OpenAICompatibleClient.request_text = original_text
        package = json.loads(result["ui"]["text"][2])["metadata"]["aipm"]
        self.assertEqual(package["global"]["reference_ids"], ["<Picture 1>"])
        self.assertEqual([item["reference_ids"] for item in package["segments"]], [[], []])
        self.assertEqual([item["effective_reference_ids"] for item in package["segments"]],
                         [["<Picture 1>"], ["<Picture 1>"]])

    def test_multi_segment_failure_returns_checkpoint_and_resumes_at_failed_segment(self):
        node = nodes.AIPMVideoPromptCore()
        original_object = nodes.OpenAICompatibleClient.request_object
        original_text = nodes.OpenAICompatibleClient.request_text
        plan = {
            "global_prompt": "统一风格", "global_negative_prompt": "闪烁",
            "global_reference_ids": [], "global_reference_bindings": [],
            "segments": [{
                "segment_id": f"SEGMENT_{index:03d}", "title": f"第{index}段",
                "duration": 6, "brief": f"动作{index}", "negative_prompt": "",
                "reference_ids": [], "dialogue_lines": [],
                "opening_state": f"开场{index}", "ending_state": f"结尾{index}",
                "continuity_from_previous": "" if index == 1 else "承接上一段",
            } for index in range(1, 4)],
        }
        valid = (
            "integrated_multimodal_description: [Shot 1] 人物在清晰稳定的环境中完成当前分段动作，"
            "镜头保持连续并跟随主体，动作、呼吸、衣料和视线变化完整，最终在明确构图中稳定落定。\n\n"
            "overall_soundscape: 连续环境声、脚步声和衣料摩擦准确同步。\n\n"
            "non_diegetic_music: N/A"
        )
        calls = []
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, *args, **kwargs: (plan, {"usage": {"total_tokens": 5}})
        )

        def first_pass(cls, *args, **kwargs):
            calls.append((args[2], kwargs.get("attempts")))
            if len(calls) == 2:
                raise nodes.PromptAssistantError("SEGMENT_002 提示词生成连续 2 次失败：测试错误")
            return valid, {"usage": {"total_tokens": 7}}

        nodes.OpenAICompatibleClient.request_text = classmethod(first_pass)
        try:
            interrupted = node.generate_timeline_package(
                service_url="http://host/v1", service_model="model", profile="MiniMax H3（自动判断模式）",
                mode="text_to_video", idea="三段连续动作", duration_seconds=6, segment_count=3,
                aspect_ratio="16:9", requested_language="中文（推荐）", skill_id="aipm-minimax-h3-video",
                skill="skill", reference_profiles=[], cache_hits=0, has_video=False, has_audio=False,
                previous=None, modification="",
            )
            checkpoint = json.loads(interrupted["ui"]["text"][2])["metadata"]["aipm"]
            self.assertEqual(checkpoint["generation_status"], "interrupted")
            self.assertEqual(checkpoint["resume_from_segment"], 2)
            self.assertEqual([item["segment_id"] for item in checkpoint["segments"]], ["SEGMENT_001"])
            self.assertEqual(calls[1][1], 2)

            resumed_calls = []
            nodes.OpenAICompatibleClient.request_object = classmethod(
                lambda cls, *args, **kwargs: (_ for _ in ()).throw(AssertionError("恢复时不应重新规划"))
            )
            nodes.OpenAICompatibleClient.request_text = classmethod(
                lambda cls, *args, **kwargs: (resumed_calls.append(args[2]) or valid, {"usage": {"total_tokens": 7}})
            )
            completed = node.generate_timeline_package(
                service_url="http://host/v1", service_model="model", profile="MiniMax H3（自动判断模式）",
                mode="text_to_video", idea="三段连续动作", duration_seconds=6, segment_count=3,
                aspect_ratio="16:9", requested_language="中文（推荐）", skill_id="aipm-minimax-h3-video",
                skill="skill", reference_profiles=[], cache_hits=0, has_video=False, has_audio=False,
                previous=checkpoint, modification="",
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original_object
            nodes.OpenAICompatibleClient.request_text = original_text
        final_package = json.loads(completed["ui"]["text"][2])["metadata"]["aipm"]
        self.assertEqual(final_package["generation_status"], "complete")
        self.assertEqual([item["segment_id"] for item in final_package["segments"]],
                         ["SEGMENT_001", "SEGMENT_002", "SEGMENT_003"])
        self.assertEqual(resumed_calls, ["SEGMENT_002 提示词生成", "SEGMENT_003 提示词生成"])

    def test_video_node_returns_structured_package(self):
        node = nodes.AIPMVideoPromptCore()
        original_object = nodes.OpenAICompatibleClient.request_object
        original_text = nodes.OpenAICompatibleClient.request_text
        nodes.OpenAICompatibleClient.request_object = classmethod(lambda cls, url, payload, stage, **kwargs: ({
            "global_prompt": "统一冷蓝电影风格", "global_negative_prompt": "身份漂移",
            "global_reference_ids": [], "global_reference_bindings": [],
            "segments": [{
                "segment_id": "SEGMENT_001", "title": "回望", "duration": 8,
                "brief": "侦探听声回望", "negative_prompt": "动作跳变", "reference_ids": [],
                "opening_state": "侦探背对镜头行走", "ending_state": "侦探面向镜头静止",
                "continuity_from_previous": "",
            }],
        }, {"usage": {"total_tokens": 8}}))
        nodes.OpenAICompatibleClient.request_text = classmethod(
            lambda cls, url, payload, stage, **kwargs: (
                "integrated_multimodal_description: [Shot 1] 雨夜里侦探停步回望，镜头缓慢推近，呼吸短暂停顿，最终稳定站定。\n\noverall_soundscape: 持续雨声与脚步声。\n\nnon_diegetic_music: N/A",
                {"usage": {"total_tokens": 12}},
            )
        )
        try:
            response = node.generate(
                "雨夜侦探听见身后脚步并回头", "http://host/v1", "model.gguf",
                "MiniMax H3（自动判断模式）", "文生视频", 8, "16:9", "中文（推荐）", 1,
                修改意见="__AIPM_RUN_V1__test",
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original_object
            nodes.OpenAICompatibleClient.request_text = original_text
        timeline = json.loads(response["ui"]["text"][2])
        package = timeline["metadata"]["aipm"]
        self.assertEqual(package["schema"], "aipm_video_timeline")
        self.assertEqual(package["generation_mode"], "text_to_video")
        self.assertEqual(package["default_segment_duration"], 8)
        self.assertEqual(package["segment_count"], 1)
        self.assertEqual(len(package["segments"]), 1)
        self.assertEqual(package["prompt_skill_id"], "aipm-minimax-h3-video")
        self.assertEqual(response["result"][0]["schema"], "cine_timeline")
        self.assertEqual(json.loads(response["result"][4])["schema"], "cine_timeline")
        self.assertIn("雨夜", response["result"][1])
        self.assertNotIn("【参考关系】", response["result"][1])

    def test_video_chinese_language_validation_rejects_english_body(self):
        with self.assertRaises(nodes.PromptAssistantError):
            nodes.AIPMVideoPromptCore.validate_generated_language(
                {"video_prompt": "subject_definitions: The entire descriptive body is written only in English."},
                "中文（推荐）",
            )
        nodes.AIPMVideoPromptCore.validate_generated_language(
            {"video_prompt": "detailed_description: 这是使用中文撰写的完整镜头描述，包含人物动作、表演反应、镜头运动、环境声音以及清楚明确的结束状态。"},
            "中文（推荐）",
        )

    def test_video_full_workflow_reuses_hidden_generated_result(self):
        node = nodes.AIPMVideoPromptCore()
        authoring = {
            "schema": "aipm_video_prompt", "version": "1.0",
            "video_prompt": "已生成的固定视频提示词", "negative_prompt": "固定负向约束",
            "audio_prompt": "固定声音", "revision": 1,
        }
        stored, _stored_json = node._canonical_timeline(authoring)
        original = nodes.OpenAICompatibleClient.request_object
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应再次调用远程服务"))
        )
        try:
            response = node.generate(
                "原始描述", "http://host/v1", "model.gguf",
                "MiniMax H3（自动判断模式）", "自动判断（推荐）", 5, "16:9", "中文（推荐）", 1,
                上次结果JSON=json.dumps(stored, ensure_ascii=False),
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original
        self.assertEqual(response["result"][1], "已生成的固定视频提示词")
        self.assertEqual(response["result"][2], "固定负向约束")
        self.assertEqual(len(response["result"]), 5)
        self.assertEqual(response["result"][0]["schema"], "cine_timeline")
        self.assertEqual(json.loads(response["result"][4])["schema"], "cine_timeline")
        self.assertEqual(response["result"][0], json.loads(response["result"][4]))
        self.assertEqual(response["result"][4], response["ui"]["text"][2])

    def test_main_workflow_never_calls_remote_without_cached_result(self):
        image = nodes.AIPMImagePrompt()
        video = nodes.AIPMVideoPromptCore()
        with self.assertRaisesRegex(nodes.PromptAssistantError, "不会随主工作流"):
            image.generate("画面", "http://host/v1", "model.gguf", "通用生图模型", "1:1", "中文")
        with self.assertRaisesRegex(nodes.PromptAssistantError, "不会随主工作流"):
            video.generate(
                "镜头", "http://host/v1", "model.gguf", "MiniMax H3（自动判断模式）",
                "自动判断（推荐）", 5, "16:9", "中文（推荐）", 1,
            )

    def test_image_full_workflow_reuses_hidden_generated_result(self):
        node = nodes.AIPMImagePrompt()
        stored = {
            "schema": "aipm_image_prompt", "version": "1.0",
            "positive_prompt": "固定正向提示词", "negative_prompt": "固定负向提示词",
        }
        response = node.generate(
            "画面", "http://host/v1", "model.gguf", "通用生图模型", "1:1", "中文",
            上次结果JSON=json.dumps(stored, ensure_ascii=False),
        )
        self.assertEqual(response["result"][1], "固定正向提示词")
        self.assertEqual(response["result"][2], "固定负向提示词")

    def test_image_main_workflow_migrates_cache_shifted_into_modification(self):
        node = nodes.AIPMImagePrompt()
        stored = {
            "schema": "aipm_image_prompt", "version": "1.0",
            "positive_prompt": "重启后固定正向提示词", "negative_prompt": "固定负向提示词",
        }
        original = nodes.OpenAICompatibleClient.request_object
        nodes.OpenAICompatibleClient.request_object = classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(AssertionError("主工作流不应调用远程服务"))
        )
        try:
            response = node.generate(
                "画面", "http://host/v1", "model.gguf", "通用生图模型", "1:1", "中文",
                修改意见=json.dumps(stored, ensure_ascii=False),
            )
        finally:
            nodes.OpenAICompatibleClient.request_object = original
        self.assertEqual(response["result"][1], "重启后固定正向提示词")

    def test_frontend_migrates_shifted_cache_out_of_revision_widget(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("function migrateShiftedCachedResult(node)", ui)
        self.assertIn('modification.value = ""', ui)

    def test_refinement_node_contract_and_skill(self):
        inputs = nodes.AIPMPromptRefinement.INPUT_TYPES()
        self.assertIn("原始提示词", inputs["required"])
        self.assertIn("遇到的问题与修改目标", inputs["required"])
        target = inputs["required"]["目标模型"]
        self.assertIsInstance(target[0], list)
        self.assertIn("Krea 2 / Krea 2 Turbo 文生图", target[0])
        self.assertIn("MiniMax H3", target[0])
        self.assertEqual(target[1]["default"], "自动判断 / 通用（推荐）")
        self.assertEqual(nodes.AIPMPromptRefinement.RETURN_NAMES[-1], "完整结果 JSON")
        skill_id, skill = nodes.load_prompt_skill("__refinement__")
        self.assertEqual(skill_id, "aipm-prompt-refinement")
        self.assertIn("smallest sufficient repair", skill)

    def test_refinement_main_workflow_reuses_cache(self):
        stored = {"schema": "aipm_prompt_refinement", "refined_prompt": "修复后的提示词",
                  "negative_prompt": "穿模", "diagnosis_text": "接触关系不清", "modification_summary_text": "补充遮挡"}
        result = nodes.AIPMPromptRefinement().refine(
            "原提示词", "人物手穿过杯子", "生图提示词", "Krea2", "保留人物",
            "http://host/v1", "model.gguf", "中文", json.dumps(stored, ensure_ascii=False))
        self.assertEqual(result["result"][0], "修复后的提示词")

    def test_refinement_profile_resolution(self):
        self.assertEqual(nodes.resolve_refinement_profile("生图提示词", "Krea2"), "Krea 2 / Krea 2 Turbo 系列")
        self.assertEqual(nodes.resolve_refinement_profile("生视频提示词", "MiniMax H3"), "MiniMax H3")


if __name__ == "__main__":
    unittest.main()
