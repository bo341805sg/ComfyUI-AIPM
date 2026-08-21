import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prompt_assistant_nodes", ROOT / "nodes.py")
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)


class PromptAssistantTests(unittest.TestCase):
    def test_only_image_and_video_nodes_are_registered(self):
        self.assertEqual(
            set(nodes.NODE_CLASS_MAPPINGS),
            {"AIPMImagePrompt", "AIPMVideoPrompt"},
        )
        self.assertEqual(
            set(nodes.NODE_DISPLAY_NAME_MAPPINGS),
            {"AIPMImagePrompt", "AIPMVideoPrompt"},
        )

    def test_image_node_defaults_to_krea_2(self):
        target = nodes.AIPMImagePrompt.INPUT_TYPES()["required"]["目标生图模型"]
        self.assertEqual(target[1]["default"], "Krea 2 / Krea 2 Turbo 系列")

    def test_image_reference_purpose_defaults_to_multi_reference_editing(self):
        purpose = nodes.AIPMImagePrompt.INPUT_TYPES()["required"]["参考图用途"]
        self.assertEqual(purpose[0], ["多参考改图", "仅分析参考"])
        self.assertEqual(purpose[1]["default"], "多参考改图")

    def test_both_nodes_expose_editable_model_name_with_huihui_default(self):
        expected = "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf"
        for node in (nodes.AIPMImagePrompt, nodes.AIPMVideoPromptCore):
            required = node.INPUT_TYPES()["required"]
            self.assertIn("模型名称", required)
            self.assertNotIn("服务模型", required)
            self.assertEqual(required["模型名称"][0], "STRING")
            self.assertEqual(required["模型名称"][1]["default"], expected)

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
        self.assertIn("grid-template-columns:minmax(0,1fr) minmax(0,1fr)", ui)
        self.assertIn("box-sizing:border-box;min-width:0;width:100%", ui)
        for node in (nodes.AIPMImagePrompt, nodes.AIPMVideoPromptCore):
            self.assertNotIn("独立执行令牌", node.INPUT_TYPES().get("optional", {}))

    def test_aipm_result_cache_uses_node_callback_and_serialization_sync(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("const acceptResult = (output)", ui)
        self.assertIn("node.onExecuted = nodeExecuted", ui)
        self.assertIn("node.onSerialize = serialize", ui)
        self.assertIn("previousResult.value = String(this.properties.aipm_previous_result)", ui)

    def test_video_result_is_immediately_written_to_linked_cinetimeline(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertIn("function writeResultToLinkedCineTimelines(node, rawTimelineJson)", ui)
        self.assertIn('output?.name === "完整结果 JSON"', ui)
        self.assertIn('targetInput?.name !== "timeline_json"', ui)
        self.assertIn("timelineWidget.value = raw", ui)
        self.assertIn("target.cineTimelineEditor?.reloadState?.()", ui)
        self.assertIn("writeResultToLinkedCineTimelines(node, raw)", ui)

    def test_generate_buttons_keep_fixed_labels_and_width_while_running(self):
        ui = (ROOT / "web" / "aipm_ui.js").read_text(encoding="utf-8")
        self.assertNotIn('button.textContent = revise ? "生成 / 重新创作" : "正在生成……"', ui)
        self.assertIn("overflow:hidden;text-overflow:ellipsis;white-space:nowrap", ui)
        self.assertIn("function syncGeneratePanelWidth(node)", ui)
        self.assertIn("panel.widget.computedWidth = width", ui)
        self.assertIn("requestAnimationFrame(() => syncGeneratePanelWidth(this))", ui)

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
        self.assertIn("FLUX.1 / FLUX.2 系列", choices)
        self.assertIn("Krea 2 / Krea 2 Turbo 系列", choices)
        self.assertLessEqual(len(choices), 20)
        self.assertTrue(set(choices).issubset(nodes.PROMPT_SKILL_BY_PROFILE))

    def test_each_profile_loads_a_nonempty_specialized_skill(self):
        loaded = {}
        for profile in nodes.IMAGE_MODEL_PROFILES:
            skill_id, instructions = nodes.load_prompt_skill(profile)
            loaded[profile] = skill_id
            self.assertTrue(instructions.startswith("# "))
            self.assertNotIn("[TODO", instructions)
        self.assertEqual(loaded["Pony Diffusion / Pony 系模型"], "aipm-pony-booru")
        self.assertEqual(loaded["Krea 2 / Krea 2 Turbo 系列"], "aipm-krea2-director")
        self.assertEqual(loaded["Qwen Image 系列"], "aipm-chinese-multimodal")
        self.assertTrue(nodes.NATIVE_QUALITY_ANCHORS["Pony Diffusion / Pony 系模型"].startswith("score_9"))
        self.assertIn("masterpiece", nodes.NATIVE_QUALITY_ANCHORS["Illustrious / NoobAI 系模型"])

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

    def test_official_prompt_family_rules_are_preserved(self):
        _, flux = nodes.load_prompt_skill("FLUX.1 / FLUX.2 系列")
        _, qwen = nodes.load_prompt_skill("Qwen Image 系列")
        _, krea = nodes.load_prompt_skill("Krea 2 / Krea 2 Turbo 系列")
        _, noobai = nodes.load_prompt_skill("Illustrious / NoobAI 系模型")
        self.assertIn("清晰自然语言", flux)
        self.assertIn("英文双引号", flux)
        self.assertIn("年龄段、脸型与骨相", qwen)
        self.assertIn("内容、主体和构图", krea)
        self.assertIn("NoobAI XL 1.1 官方模型卡", noobai)
        self.assertNotIn("Stable Diffusion 1.x", nodes.NATIVE_QUALITY_ANCHORS)
        self.assertNotIn("Stable Diffusion XL 基础模型", nodes.NATIVE_QUALITY_ANCHORS)

    def test_extracts_fenced_json(self):
        value = nodes.OpenAICompatibleClient.parse_object('```json\n{"positive_prompt":"中文"}\n```')
        self.assertEqual(value["positive_prompt"], "中文")

    def test_professional_contract_is_required_by_schema(self):
        schema = nodes.AIPMImagePrompt.response_format()["json_schema"]["schema"]
        self.assertIn("quality_features", schema["required"])
        self.assertIn("emphasis_features", schema["required"])
        self.assertGreaterEqual(schema["properties"]["quality_features"]["minItems"], 4)

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
        self.assertIn("MiniMax H3（自动判断模式）", inputs["required"]["目标视频模型"][0])
        self.assertEqual(inputs["required"]["视频时长"][0], "INT")
        self.assertEqual(inputs["required"]["视频时长"][1]["min"], 4)
        self.assertEqual(inputs["required"]["视频时长"][1]["max"], 15)
        self.assertEqual(inputs["required"]["分段数量"][0], "INT")
        self.assertEqual(inputs["required"]["分段数量"][1]["default"], 1)
        self.assertIn("image1", inputs["optional"])
        self.assertIn("image4", inputs["optional"])
        self.assertIn("video1", inputs["optional"])
        self.assertIn("audio1", inputs["optional"])

    def test_video_mode_resolution(self):
        resolve = nodes.AIPMVideoPromptCore._resolve_mode
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断（推荐）", 0, False, False), "text_to_video")
        self.assertEqual(resolve("MiniMax H3（自动判断模式）", "自动判断（推荐）", 1, False, False), "h3_ref2va")
        self.assertEqual(resolve("MiniMax H3 FL2VA（首尾帧）", "自动判断（推荐）", 2, False, False), "h3_fl2va")

    def test_timeline_plan_schema_requires_exact_segment_count(self):
        schema = nodes.AIPMVideoPromptCore.timeline_plan_format(3)["json_schema"]["schema"]
        segments = schema["properties"]["segments"]
        self.assertEqual(segments["minItems"], 3)
        self.assertEqual(segments["maxItems"], 3)
        self.assertIn("dialogue_lines", segments["items"]["required"])

    def test_dialogue_speaker_ids_are_bound_locally(self):
        prompt = "母亲说道：<d>[Chinese] 到了给妈打电话。</d> 女儿回答：<d>[Chinese] 知道了，妈。</d>"
        bound = nodes.AIPMVideoPromptCore.bind_dialogue_speaker_ids(
            prompt, ["母亲：到了给妈打电话。", "女儿：知道了，妈。"],
        )
        self.assertIn("(S1) <d>[Chinese] 到了给妈打电话。</d>", bound)
        self.assertIn("(S2) <d>[Chinese] 知道了，妈。</d>", bound)

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
            return (f"integrated_multimodal_description: [Shot 1] 第{index}段使用中文描述人物动作、镜头、表演、声音与结束状态，内容足够完整清晰。\n\noverall_soundscape: 环境声。\n\nnon_diegetic_music: N/A", {"usage": {"total_tokens": 7}})
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
                "MiniMax H3（自动判断模式）", "自动判断（推荐）", 8, "16:9", "中文（推荐）", 1,
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


if __name__ == "__main__":
    unittest.main()
