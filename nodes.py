from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image


CATEGORY = "AI 提示词大师"


def requires_planned_dialogue(idea: str) -> bool:
    """Conservative lexical guard, not a full natural-language intent parser.

    Remove local negative speech phrases, not entire sentences: a request may
    forbid narration while still requiring a character's line.
    """
    speech = r"(?:台词|对白|旁白|独白|对话|开口|说一句|说话)"
    text = re.sub(
        rf"(?:不要|不需要|无需|禁止|没有|无|不)(?:任何|添加|加入|生成|安排|出现|进行|让角色|角色|人物|人声|的|\s)*{speech}",
        "", idea,
    )
    text = re.sub(
        r"\b(?:no|without|avoid|do not add|don't add)\s+(?:any\s+)?(?:dialogue|voice[ -]?over|speech|speaking)\b",
        "", text, flags=re.IGNORECASE,
    )
    return bool(re.search(
        speech + r"|dialogue|voice[ -]?over|\bspeak\b|\bsays?\b|(?:说|问|答)[：:“\"]",
        text, re.IGNORECASE,
    ))


def explicitly_allows_repeated_segments(idea: str) -> bool:
    # A mere mention of repetition (especially a prohibition) is not consent.
    text = re.sub(r"(?:不要|禁止|避免|不允许|无需)(?:完全|再次|再|任何|\s)*(?:重复|循环)[^，。；\n]*", "", idea)
    text = re.sub(r"\b(?:do not|don't|never|avoid)\s+(?:repeat|loop)[^,.;\n]*", "", text, flags=re.IGNORECASE)
    return bool(re.search(
        r"(?:明确要求|要求|需要|请)(?:两段|每段|都|完全|再次|\s)*(?:重复|循环)"
        r"|(?:重复演示|循环演示|循环播放)|\b(?:please repeat|repeat the same|loop the same)\b",
        text, re.IGNORECASE,
    ))


def normalize_plan_mode(plan: dict[str, Any], mode: str) -> None:
    """Frame placements are executable only in keyframe mode.

    Preserve reference identities and descriptions; discard only inapplicable
    frame-routing fields so multimodal portraits cannot become timed guides.
    """
    if mode == "h3_ref2va":
        for segment in plan.get("segments", []):
            if isinstance(segment, dict):
                segment["keyframe_bindings"] = []
                segment["keyframe_transitions"] = []

# This menu represents prompt dialects, not product versions. Models sharing
# the same prompting rules intentionally live in one family.
IMAGE_MODEL_PROFILES = [
    "自动判断 / 通用（推荐）",
    "中文自然语言（闭源模型通用）",
    "Stable Diffusion 1.x",
    "Stable Diffusion XL 基础模型",
    "Pony Diffusion / Pony 系模型",
    "Illustrious / NoobAI 系模型",
    "FLUX.1 文生图",
    "FLUX.2 文生图",
    "FLUX.2 多参考编辑",
    "Krea 2 / Krea 2 Turbo 文生图",
    "Krea 2 风格参考",
    "Krea 2 身份编辑",
    "Qwen Image 文生图",
    "Qwen Image 单图编辑",
    "Qwen Image 多图编辑",
    "Z-Image 系列",
    "Stable Diffusion 3 / 3.5",
    "HiDream Image 系列",
    "HunyuanImage 系列",
    "Kolors 系列",
    "Anima 系列",
    "Chroma 系列",
    "PixArt Sigma 系列",
    "Stable Cascade",
]

IMAGE_PROMPT_DIALECTS = {
    "自动判断 / 通用（推荐）": "根据目标描述选择兼容性最好的结构化自然语言，不使用未知参数。",
    "中文自然语言（闭源模型通用）": "使用完整、清晰的中文自然语言和段落式指令；不写权重括号、质量标签或采样参数。",
    "Stable Diffusion 1.x": "使用简洁英文逗号标签，核心主体和风格词前置；仅在推理前端支持时使用少量 (term:1.2) 权重，质量前缀服从 checkpoint 模型卡。",
    "Stable Diffusion XL 基础模型": "使用较完整的英文短语与逗号标签混合结构，明确主体、构图、光线和材质；基础模型不强制 masterpiece 前缀。",
    "Pony Diffusion / Pony 系模型": "使用 Pony 的 score_9、score_8_up 等质量标签及 booru 风格标签，人物数量、评级与构图标签前置。",
    "Illustrious / NoobAI 系模型": "使用 Danbooru/booru 标签语法，角色、作品、人数、构图、服装与动作标签清晰分组，不套用 Pony score 标签。",
    "FLUX.1 / FLUX.2 系列": "使用详细自然语言描述，强调空间关系、镜头、光线、材质和文字内容；不堆砌 SD 质量标签，通常不依赖负面提示词。",
    "FLUX.1 文生图": "使用英文自然语言描述主体、空间关系、镜头、光线、材质和准确文字；不使用 SD 权重语法。",
    "FLUX.2 文生图": "使用英文自然语言和明确视觉层级；区分用户原始意图与可选提示扩写，不虚构关键对象。",
    "FLUX.2 多参考编辑": "逐张说明参考图职责、目标位置和不可改变项；明确编辑动作，防止身份、服装、风格和背景跨图污染。",
    "Krea 2 / Krea 2 Turbo 系列": "使用清晰的摄影导演式自然语言，优先描述主体、场景关系、镜头与构图、真实光线、色彩和材质；避免 SD 式质量词堆叠，Turbo 版本保持提示精炼。",
    "Krea 2 / Krea 2 Turbo 文生图": "使用忠实、连贯的英文自然语言；Turbo 删除重复描述但不删主体、动作和空间约束。",
    "Krea 2 风格参考": "文字固定内容和构图，参考图仅承担色板、媒介、纹理与审美；明确禁止继承参考图主体。",
    "Krea 2 身份编辑": "身份参考优先；明确保留脸部辨识特征和未修改内容，并把风格压力限制在身份之外。",
    "Qwen Image 系列": "优先使用清晰中文自然语言，精确描述主体关系、构图和需要渲染的文字；参考图使用 <Picture N>。",
    "Qwen Image 文生图": "使用清晰中文自然语言，精确描述主体关系、构图与可见文字，不混入编辑指令。",
    "Qwen Image 单图编辑": "使用直接、具体的局部编辑指令，明确修改项与保留项，避免重新描述整张图导致漂移。",
    "Qwen Image 多图编辑": "逐图指定元素来源、目标位置和保留项；不合并不同人物身份，不把参考图背景带入成图。",
    "Z-Image 系列": "使用简洁但完整的中文或英文自然语言，主体动作与画面结构前置，避免冗余质量词和过长否定列表。",
    "Stable Diffusion 3 / 3.5": "使用自然语言与关键词混合提示，明确对象关系、构图、光线和文字；避免 SD1.x 式碎片化标签堆叠。",
    "HiDream Image 系列": "使用完整自然语言，明确多主体关系、空间层次、风格和光照；不要附加服务商参数。",
    "HunyuanImage 系列": "优先中文自然语言，准确描述主体、场景、文字与文化元素，保持结构明确。",
    "Kolors 系列": "优先中文自然语言，突出人物五官、服饰、构图、光影和审美风格。",
    "Anima 系列": "使用 Anima 原生 Danbooru 标签、自然语言或二者混合；严格构图优先用标签加英文空间契约，不套用 SDXL/Illustrious/Pony 的通用模板。",
    "Chroma 系列": "使用类似 FLUX 的详细自然语言，明确画面叙事、空间关系、材质与光线，减少标签堆叠。",
    "PixArt Sigma 系列": "使用清晰英文自然语言或短语，主体、场景、风格、构图和光照按顺序表达。",
    "Stable Cascade": "使用简洁英文自然语言与视觉关键词，避免复杂权重语法和过长负面提示。",
}

# Native/recommended output language in automatic mode. This is deliberately
# separate from UI localization: users can describe ideas in Chinese while the
# generated prompt follows the target model's strongest prompt language.
IMAGE_PROMPT_LANGUAGES = {
    "中文自然语言（闭源模型通用）": "zh-CN",
    "Qwen Image 系列": "zh-CN",
    "Qwen Image 文生图": "zh-CN",
    "Qwen Image 单图编辑": "zh-CN",
    "Qwen Image 多图编辑": "zh-CN",
    "Z-Image 系列": "zh-CN",
    "HunyuanImage 系列": "zh-CN",
    "Kolors 系列": "zh-CN",
    "Stable Diffusion 1.x": "en",
    "Stable Diffusion XL 基础模型": "en",
    "Pony Diffusion / Pony 系模型": "en-tags",
    "Illustrious / NoobAI 系模型": "en-tags",
    "FLUX.1 / FLUX.2 系列": "en",
    "FLUX.1 文生图": "en",
    "FLUX.2 文生图": "en",
    "FLUX.2 多参考编辑": "en",
    "Krea 2 / Krea 2 Turbo 系列": "en",
    "Krea 2 / Krea 2 Turbo 文生图": "en",
    "Krea 2 风格参考": "en",
    "Krea 2 身份编辑": "en",
    "Stable Diffusion 3 / 3.5": "en",
    "HiDream Image 系列": "en",
    "Anima 系列": "en-tags",
    "Chroma 系列": "en",
    "PixArt Sigma 系列": "en",
    "Stable Cascade": "en",
}

PROMPT_SKILL_BY_PROFILE = {
    "自动判断 / 通用（推荐）": "aipm-general-natural",
    "中文自然语言（闭源模型通用）": "aipm-general-natural",
    "Stable Diffusion 1.x": "aipm-sd-weighted",
    "Stable Diffusion XL 基础模型": "aipm-sd-weighted",
    "Pony Diffusion / Pony 系模型": "aipm-pony-booru",
    "Illustrious / NoobAI 系模型": "aipm-illustrious-booru",
    "Anima 系列": "aipm-anima",
    "FLUX.1 / FLUX.2 系列": "aipm-flux-natural",
    "FLUX.1 文生图": "aipm-flux-natural",
    "FLUX.2 文生图": "aipm-flux2-natural",
    "FLUX.2 多参考编辑": "aipm-flux2-edit",
    "HiDream Image 系列": "aipm-flux-natural",
    "Chroma 系列": "aipm-flux-natural",
    "PixArt Sigma 系列": "aipm-flux-natural",
    "Stable Cascade": "aipm-flux-natural",
    "Krea 2 / Krea 2 Turbo 系列": "aipm-krea2-director",
    "Krea 2 / Krea 2 Turbo 文生图": "aipm-krea2-director",
    "Krea 2 风格参考": "aipm-krea2-style-reference",
    "Krea 2 身份编辑": "aipm-krea2-identity-edit",
    "Qwen Image 系列": "aipm-chinese-multimodal",
    "Qwen Image 文生图": "aipm-qwen-image-generate",
    "Qwen Image 单图编辑": "aipm-qwen-image-edit",
    "Qwen Image 多图编辑": "aipm-qwen-image-edit",
    "Z-Image 系列": "aipm-chinese-multimodal",
    "HunyuanImage 系列": "aipm-chinese-multimodal",
    "Kolors 系列": "aipm-chinese-multimodal",
    "Stable Diffusion 3 / 3.5": "aipm-sd3-modern",
}

VIDEO_MODEL_PROFILES = [
    "MiniMax H3",
]

VIDEO_PROMPT_DIALECTS = {
    "MiniMax H3": "根据生成模式编写关键帧或多模态提示词；使用可观察的时序动作、表演、镜头和声音描述。",
    "MiniMax H3（自动判断模式）": "根据参考输入自动选择纯文生视频、Ref2VA 多参考或 FL2VA 首尾帧表达；使用可观察的时序动作、表演、镜头和声音描述。",
    "MiniMax H3 Ref2VA（多参考）": "使用 <Picture N>、<Video N>、<Audio N> 明确多模态参考职责，描述继承什么并排除无关姿态或背景。",
    "MiniMax H3 FL2VA（首尾帧）": "把首帧和尾帧视为状态契约，描述从起始状态到结束状态的物理可行路径，不增加多参考语法。",
    "Wan 系列": "使用清晰自然语言，按主体、动作时序、镜头、光线和风格组织，避免无效质量标签堆叠。",
    "LTX-Video 系列": "使用直接、紧凑、按时间展开的自然语言，优先动作、镜头和声音同步。",
    "HunyuanVideo 系列": "使用完整自然语言明确主体运动、场景运动、镜头运动、光线和时序连续性。",
    "中文自然语言视频模型（通用）": "使用简体中文导演式自然语言，显式写出开场、动作阶段、镜头响应、结束状态和声音。",
}

VIDEO_PROMPT_SKILL_BY_PROFILE = {
    "MiniMax H3": "aipm-minimax-h3-video",
    "MiniMax H3（自动判断模式）": "aipm-minimax-h3-video",
    "MiniMax H3 Ref2VA（多参考）": "aipm-minimax-h3-video",
    "MiniMax H3 FL2VA（首尾帧）": "aipm-minimax-h3-video",
    "Wan 系列": "aipm-wan-video",
    "LTX-Video 系列": "aipm-ltx-video",
    "HunyuanVideo 系列": "aipm-hunyuan-video",
    "中文自然语言视频模型（通用）": "aipm-video-general",
}
REFINEMENT_MODEL_PROFILES = [
    "自动判断 / 通用（推荐）",
    *[value for value in IMAGE_MODEL_PROFILES if value != "自动判断 / 通用（推荐）"],
    "MiniMax H3", "Wan 系列", "LTX-Video 系列", "HunyuanVideo 系列",
    "中文自然语言视频模型（通用）",
]
NATIVE_QUALITY_ANCHORS = {
    "Pony Diffusion / Pony 系模型": "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up",
    "Illustrious / NoobAI 系模型": "masterpiece, best quality, highres",
    "Anima 系列": "masterpiece, best quality, highres, safe",
}
SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def load_h3_planning_review() -> str:
    """Planner-only guidance, never an additional model-output schema."""
    path = SKILLS_DIR / "aipm-minimax-h3-video" / "references" / "planning-review.md"
    if not path.is_file():
        raise PromptAssistantError(f"MiniMax H3 规划检查规则不存在：{path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PromptAssistantError("MiniMax H3 规划检查规则为空")
    return text


def load_prompt_skill(model_profile: str, mode: str | None = None) -> tuple[str, str]:
    skill_id = (
        "aipm-prompt-refinement" if str(model_profile) == "__refinement__" else
        VIDEO_PROMPT_SKILL_BY_PROFILE.get(str(model_profile))
        or PROMPT_SKILL_BY_PROFILE.get(str(model_profile), "aipm-general-natural")
    )
    skill_path = SKILLS_DIR / skill_id / "SKILL.md"
    if not skill_path.is_file():
        raise PromptAssistantError(f"目标提示词技能不存在：{skill_path}")
    text = skill_path.read_text(encoding="utf-8").strip()
    # Runtime models need the instruction body, not Codex discovery metadata.
    text = re.sub(r"^---\s*.*?\s*---\s*", "", text, count=1, flags=re.DOTALL)
    if not text:
        raise PromptAssistantError(f"目标提示词技能为空：{skill_id}")
    if skill_id == "aipm-minimax-h3-video" and mode:
        reference_name = "official-ref2va.md" if mode == "h3_ref2va" else "official-base.md"
        reference_path = skill_path.parent / "references" / reference_name
        if not reference_path.is_file():
            raise PromptAssistantError(f"MiniMax H3 模式规则不存在：{reference_path}")
        reference_text = reference_path.read_text(encoding="utf-8").strip()
        if not reference_text:
            raise PromptAssistantError(f"MiniMax H3 模式规则为空：{reference_name}")
        text = f"{text}\n\n{reference_text}"
    contract_path = SKILLS_DIR / "runtime-contract.md"
    contract = contract_path.read_text(encoding="utf-8").strip()
    if not contract:
        raise PromptAssistantError("AIPM运行边界规则为空")
    return skill_id, f"{contract}\n\n{text}"


def resolve_prompt_language(model_profile: str, requested: str) -> str:
    if requested == "中文":
        return "zh-CN"
    if requested == "English":
        return "en"
    return IMAGE_PROMPT_LANGUAGES.get(model_profile, "zh-CN")


class PromptAssistantError(RuntimeError):
    pass


class OpenAICompatibleClient:
    @staticmethod
    def endpoint(service_url: str) -> str:
        base = str(service_url or "").strip().rstrip("/")
        if not base:
            raise PromptAssistantError("远程 AI 服务地址不能为空")
        return base if base.endswith("/chat/completions") else base + "/chat/completions"

    @classmethod
    def request(cls, service_url: str, payload: dict[str, Any], timeout: float = 300.0) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "User-Agent": "ComfyUI-AIPM/0.1"}
        api_key = (
            os.getenv("AIPM_API_KEY", "").strip()
            or os.getenv("PROMPT_ASSISTANT_API_KEY", "").strip()
        )
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        request = urllib.request.Request(
            cls.endpoint(service_url),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise PromptAssistantError(f"远程服务 HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PromptAssistantError(f"远程服务连接失败：{exc}") from exc
        if not isinstance(result, dict):
            raise PromptAssistantError("远程服务返回的根对象不是 JSON")
        return result

    @staticmethod
    def content(response: dict[str, Any]) -> str:
        try:
            value = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PromptAssistantError("远程服务没有返回 assistant content") from exc
        if isinstance(value, list):
            value = "".join(str(item.get("text", "")) for item in value if isinstance(item, dict))
        return str(value or "").strip()

    @staticmethod
    def parse_object(content: str) -> dict[str, Any]:
        text = str(content or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise PromptAssistantError("远程 AI 没有返回可解析的 JSON 对象")
            try:
                result = json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                raise PromptAssistantError(f"远程 AI 返回了无效 JSON：{exc.msg}") from exc
        if not isinstance(result, dict):
            raise PromptAssistantError("远程 AI 返回的 JSON 根节点必须是对象")
        return result

    @classmethod
    def request_object(cls, service_url: str, payload: dict[str, Any], stage: str, attempts: int = 3,
                       validator=None):
        current = copy.deepcopy(payload)
        last_text = ""
        last_connection_error = None
        for attempt in range(attempts):
            try:
                response = cls.request(service_url, current)
            except PromptAssistantError as exc:
                # llama.cpp can briefly reset a LAN connection while under
                # memory/load pressure. Retry only transport failures; HTTP
                # and payload errors should remain immediately actionable.
                if not str(exc).startswith("远程服务连接失败："):
                    raise
                last_connection_error = exc
                if attempt + 1 >= attempts:
                    break
                time.sleep(1.5 * (attempt + 1))
                continue
            last_text = cls.content(response)
            validation_error = None
            try:
                parsed = cls.parse_object(last_text)
                if validator is not None:
                    validator(parsed)
                return parsed, response
            except PromptAssistantError as exc:
                validation_error = str(exc)
                if attempt + 1 >= attempts:
                    break
                finish_reason = ""
                try:
                    finish_reason = str(response["choices"][0].get("finish_reason") or "")
                except (KeyError, IndexError, TypeError, AttributeError):
                    pass
                # A structured response that stops at the token ceiling is
                # incomplete JSON. Increase only the output allowance on the
                # retry instead of repeating the same doomed request.
                if finish_reason in {"length", "max_tokens"} or not last_text.rstrip().endswith("}"):
                    current["max_tokens"] = min(max(int(current.get("max_tokens") or 0) * 2, 3200), 6000)
                current.setdefault("messages", []).append({
                    "role": "system",
                    "content": (
                        f"上一次输出未通过验收：{validation_error}。"
                        "请压缩重复描述并修正该问题，只重新输出一个完整闭合的 JSON 对象，"
                        "不要解释、思考过程或代码围栏。"
                    ),
                })
                current["temperature"] = 0.1
                current["cache_prompt"] = False
        if last_connection_error is not None and not last_text:
            raise PromptAssistantError(
                f"{stage}连接远程服务连续失败 {attempts} 次：{last_connection_error}"
            ) from last_connection_error
        excerpt = re.sub(r"\s+", " ", last_text)[:240] or "<empty>"
        raise PromptAssistantError(
            f"{stage} 连续 {attempts} 次未返回有效 JSON（最后响应 {len(last_text)} 字符，可能被截断）；最后响应：{excerpt}"
        )

    @classmethod
    def request_text(cls, service_url: str, payload: dict[str, Any], stage: str,
                     attempts: int = 2, validator=None) -> tuple[str, dict[str, Any]]:
        last_error: Exception | None = None
        current = copy.deepcopy(payload)
        for attempt in range(attempts):
            try:
                response = cls.request(service_url, current)
                content = cls.content(response)
                if not content:
                    raise PromptAssistantError("远程服务返回空文本")
                if validator is not None:
                    validator(content)
                return content, response
            except PromptAssistantError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                current.setdefault("messages", []).append({
                    "role": "system",
                    "content": f"上一次输出未通过验收：{exc}。请只重新输出修正后的提示词纯文本，不要JSON、解释或代码围栏。",
                })
                current["temperature"] = 0.1
                current["cache_prompt"] = False
        raise PromptAssistantError(f"{stage}连续 {attempts} 次失败：{last_error}") from last_error


def encode_image_batch(images: Any, limit: int = 9) -> list[dict[str, str]]:
    if images is None:
        return []
    tensor = images.detach().cpu() if hasattr(images, "detach") else images
    encoded: list[dict[str, str]] = []
    for index in range(min(int(tensor.shape[0]), limit)):
        array = tensor[index].numpy() if hasattr(tensor[index], "numpy") else tensor[index]
        array = (array.clip(0, 1) * 255).astype("uint8")
        image = Image.fromarray(array, mode="RGB")
        image.thumbnail((640, 640))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=84, optimize=True)
        content = buffer.getvalue()
        encoded.append({
            "sha256": hashlib.sha256(content).hexdigest(),
            "data_url": "data:image/jpeg;base64," + base64.b64encode(content).decode("ascii"),
        })
    return encoded


def parse_reference_asset_manifest(source: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(str(source or "[]"))
    except json.JSONDecodeError as exc:
        raise PromptAssistantError(f"参考素材清单JSON无效：{exc.msg}") from exc
    if not isinstance(value, list):
        raise PromptAssistantError("参考素材清单JSON必须是数组")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PromptAssistantError(f"参考素材清单第 {index + 1} 项必须是对象")
        asset_id = str(item.get("asset_id") or "").strip()
        media_type = str(item.get("media_type") or "").strip().lower()
        if not asset_id or media_type not in {"image", "video", "audio"}:
            raise PromptAssistantError(f"参考素材清单第 {index + 1} 项缺少有效asset_id或media_type")
        result.append(copy.deepcopy(item))
    return result


class ReferenceAnalysisPipeline:
    """Shared staged media-analysis layer for every AIPM prompt node."""

    _image_cache: dict[str, str] = {}
    _cache_limit = 128

    @classmethod
    def analyze_images(
        cls, service_url: str, service_model: str, images: list[dict[str, str]],
        role_hint: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        profiles: list[dict[str, Any]] = []
        cache_hits = 0
        for index, image in enumerate(images):
            # Analysis is conditioned on the service, task and reference slot,
            # not just pixels. Reordered references must not reuse old roles.
            cache_key = hashlib.sha256(json.dumps(
                ["image-analysis-v2", service_url, service_model, image["sha256"],
                 index + 1, role_hint], ensure_ascii=False,
            ).encode("utf-8")).hexdigest()
            analysis = cls._image_cache.get(cache_key)
            if analysis:
                cache_hits += 1
            else:
                instruction = {
                    "task": "分析一张用于 AI 生图提示词的视觉参考图",
                    "picture_id": f"<Picture {index + 1}>",
                    "role_hint": role_hint,
                    "rules": [
                        "只输出精炼中文视觉档案，不写剧情，不使用 markdown",
                        "描述主体类别、年龄段、五官、肤色、发型、体型、服装、姿态、材质、色彩、场景、构图、光线和显著识别特征",
                        "区分可继承事实与仅属于原图的姿态、背景或构图",
                        "看不清的内容标记未知，禁止臆造",
                    ],
                }
                payload = {
                    "model": service_model,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": json.dumps(instruction, ensure_ascii=False)},
                        {"type": "image_url", "image_url": {"url": image["data_url"]}},
                    ]}],
                    "temperature": 0.15, "max_tokens": 450, "cache_prompt": False,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
                last_error: Exception | None = None
                for _ in range(2):
                    try:
                        response = OpenAICompatibleClient.request(service_url, payload, timeout=180.0)
                        analysis = OpenAICompatibleClient.content(response)
                        if analysis:
                            break
                    except (PromptAssistantError, RuntimeError) as exc:
                        last_error = exc
                if not analysis:
                    raise PromptAssistantError(
                        f"参考图片 {index + 1} 分析失败：{last_error or '远程服务返回空内容'}"
                    )
                if len(cls._image_cache) >= cls._cache_limit:
                    cls._image_cache.pop(next(iter(cls._image_cache)))
                cls._image_cache[cache_key] = analysis
            profiles.append({
                "picture_id": f"<Picture {index + 1}>",
                "image_sha256": image["sha256"],
                "visual_profile": analysis,
            })
        return profiles, cache_hits


def reconcile_append_editor(package, timeline):
    """Use the connected editor's current order/content, never resurrect deleted shots."""
    if not isinstance(timeline, dict) or not isinstance(timeline.get("shots"), list):
        raise PromptAssistantError("续写时间轴快照无效")
    shots = timeline["shots"]
    if not shots:
        raise PromptAssistantError("当前时间轴没有分段，请先生成初始剧情")
    cached = {str(s.get("segment_id")): s for s in package.get("segments", [])}
    result = copy.deepcopy(package)
    segments, seen = [], set()
    fps = float(timeline.get("fps") or 24)
    if fps <= 0:
        raise PromptAssistantError("时间轴帧率无效")
    for shot in shots:
        sid = str(shot.get("shot_id") or "")
        if not sid or sid in seen:
            raise PromptAssistantError("时间轴分段编号为空或重复")
        seen.add(sid)
        segment = copy.deepcopy(cached.get(sid, {}))
        metadata = shot.get("metadata") or {}
        duration = (float(shot["end_frame"]) - float(shot["start_frame"])) / fps
        if duration <= 0:
            raise PromptAssistantError("时间轴分段时长无效")
        segment.update(segment_id=sid, index=len(segments)+1, duration=duration,
                       title=shot.get("title") or segment.get("title") or sid,
                       transition=shot.get("transition", "cut"))
        if "local_prompt" in shot:
            for key in ("timeline_local_prompt", "source_prompt", "prompt", "compiled_prompt"):
                segment[key] = str(shot["local_prompt"] or "")
        for source, target in (("start_state", "opening_state"), ("end_state", "ending_state"),
                               ("handoff", "continuity_from_previous"), ("dialogue_lines", "dialogue_lines")):
            if source in metadata: segment[target] = copy.deepcopy(metadata[source])
        segments.append(segment)
    result.update(segments=segments, segment_count=len(segments),
                  total_duration=sum(s["duration"] for s in segments),
                  generation_status="complete", aipm_operation="rewrite")
    for key in ("append_base_count", "append_requested_count", "resume_from_segment", "failed_segment_id", "interruption_error"):
        result.pop(key, None)
    return result


def reuse_append_global_images(profiles, base_package, mode):
    """Reuse proven global asset identities; retain distinct temporal roles.

    image_sha256 identifies the analyzed image, unlike loader slots or filenames.
    Unknown/ambiguous identities fail closed to a fresh, collision-free ordinal.
    """
    old = [p for p in base_package.get("reference_profiles", []) if isinstance(p, dict)]
    global_ids = set(base_package.get("global", {}).get("reference_ids", []))
    occupied = {str(p.get("picture_id") or "") for p in old}
    matches = {}
    for p in old:
        digest = str(p.get("image_sha256") or "").strip().lower()
        pid = str(p.get("picture_id") or "")
        if digest and pid in global_ids:
            matches.setdefault(digest, set()).add(pid)
    next_id = 1
    for p in profiles:
        digest = str(p.get("image_sha256") or "").strip().lower()
        candidates = matches.get(digest, set()) if mode == "h3_ref2va" else set()
        if len(candidates) == 1:
            p["picture_id"] = next(iter(candidates))
        else:
            while f"<Picture {next_id}>" in occupied:
                next_id += 1
            p["picture_id"] = f"<Picture {next_id}>"
            occupied.add(p["picture_id"])
            next_id += 1
    return profiles


class AIPMImagePrompt:
    CATEGORY = CATEGORY
    FUNCTION = "generate"
    OUTPUT_NODE = True
    RETURN_TYPES = ("AIPM_IMAGE_PROMPT", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("提示词数据", "正向提示词", "负向提示词", "完整结果 JSON")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "画面描述与创作要求": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "远程服务地址": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "模型名称": ("STRING", {"default": "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf"}),
                "目标生图模型": (IMAGE_MODEL_PROFILES, {"default": "Krea 2 / Krea 2 Turbo 文生图"}),
                "画面比例": (["自动", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],),
                "提示词语言": (["自动适配（推荐）", "中文", "English"],),
                "参考图用途": (["多参考改图", "仅分析参考"], {"default": "多参考改图"}),
            },
            "optional": {
                "参考图片": ("IMAGE",),
                "参考图片2": ("IMAGE",),
                "参考图片3": ("IMAGE",),
                "修改意见": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
            },
        }


class AIPMVideoPrompt:
    CATEGORY = CATEGORY
    FUNCTION = "generate"
    OUTPUT_NODE = True
    RETURN_TYPES = ("CINE_TIMELINE", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("提示词数据", "视频提示词", "负向提示词", "声音提示词", "完整结果 JSON")

    @staticmethod
    def _authoring_data(value: dict[str, Any]) -> dict[str, Any]:
        """Return AIPM authoring metadata from the canonical timeline document."""
        if not isinstance(value, dict):
            return {}
        if value.get("schema") not in {"cine_timeline", "cine_keyframe_timeline"}:
            return value
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        authoring = metadata.get("aipm")
        return authoring if isinstance(authoring, dict) else {}

    @staticmethod
    def _canonical_timeline(package: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Build the one canonical document used by AIPM and CineTimeline."""
        timeline, _timeline_json, _report, _first_prompt = (
            AIPMCineTimelineAdapter().convert(package, 24, "cut")["result"]
        )
        metadata = timeline.setdefault("metadata", {})
        metadata["aipm"] = copy.deepcopy(package)
        timeline_json = json.dumps(timeline, ensure_ascii=False, indent=2)
        return timeline, timeline_json

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "视频内容与导演要求": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "远程服务地址": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "模型名称": ("STRING", {"default": "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf"}),
                "目标视频模型": (VIDEO_MODEL_PROFILES,),
                "生成模式": (["多模态", "关键帧"], {"default": "多模态"}),
                "视频时长": ("INT", {"default": 15, "min": 4, "max": 30, "step": 1, "display": "number"}),
                "构图比例": (["自动", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"], {
                    "tooltip": "仅用于指导 AI 编写构图提示词；实际生成尺寸由工作流的宽度、高度节点控制。"
                }),
                "提示词语言": (["中文（推荐）", "English"],),
                "分段数量": ("INT", {"default": 1, "min": 1, "max": 12, "step": 1, "display": "number"}),
            },
            "optional": {
                **{f"image{index}": ("IMAGE",) for index in range(1, 10)},
                **{f"video{index}": ("VIDEO",) for index in range(1, 4)},
                **{f"audio{index}": ("AUDIO",) for index in range(1, 4)},
                "修改意见": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "上次结果JSON": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "参考素材清单JSON": ("STRING", {"default": "[]", "multiline": True, "dynamicPrompts": False}),
            },
        }

    @staticmethod
    def response_format() -> dict[str, Any]:
        string_array = {"type": "array", "items": {"type": "string"}}
        return {"type": "json_schema", "json_schema": {"name": "video_prompt_result", "strict": True, "schema": {
            "type": "object", "properties": {
                "video_prompt": {"type": "string"}, "negative_prompt": {"type": "string"},
                "audio_prompt": {"type": "string"}, "start_state": {"type": "string"},
                "motion_phases": string_array, "end_state": {"type": "string"},
                "camera_plan": {"type": "string"}, "performance_plan": {"type": "string"},
                "visual_design": {"type": "string"},
                "reference_usage": string_array, "continuity_guards": string_array,
            }, "required": ["video_prompt", "negative_prompt", "audio_prompt", "start_state",
                "motion_phases", "end_state", "camera_plan", "performance_plan",
                "visual_design", "reference_usage", "continuity_guards"],
        }}}

    @staticmethod
    def _resolve_mode(profile: str, requested: str, image_count: int, has_video: bool, has_audio: bool) -> str:
        # The user-facing mode is authoritative.  Legacy labels remain
        # readable so existing workflows migrate without changing meaning.
        if requested in {"多模态", "多参考 Ref2VA"}:
            return "h3_ref2va"
        if requested == "关键帧":
            return "h3_keyframe"
        if requested == "首帧 I2VA":
            return "h3_i2va"
        if requested == "尾帧 L2VA":
            return "h3_l2va"
        if requested == "文生视频":
            return "text_to_video"
        if requested in {"自动判断", "自动判断（推荐）"}:
            # Removed from the UI because image count alone cannot reliably
            # distinguish storyboard keyframes from multimodal references.
            # Treat persisted/API legacy values as the new deterministic default.
            return "h3_ref2va"
        if requested in {"首尾帧", "首尾帧 FL2VA"}:
            return "h3_keyframe"
        if "Ref2VA" in profile:
            return "h3_ref2va"
        if "FL2VA" in profile:
            return "h3_fl2va"
        if profile.startswith("MiniMax H3") and (image_count or has_video or has_audio):
            return "h3_ref2va"
        return "text_to_video"

    @staticmethod
    def validate_generated_language(generated: dict[str, Any], requested_language: str) -> None:
        prompt = str(generated.get("video_prompt") or "")
        if not prompt.strip():
            raise PromptAssistantError("video_prompt 为空")
        if requested_language != "English":
            chinese_count = len(re.findall(r"[\u3400-\u9fff]", prompt))
            if chinese_count < 30:
                raise PromptAssistantError(
                    "用户选择中文，但 video_prompt 的描述正文不是中文；仅官方字段名、控制标签、任务类型和关系枚举可以保留英文"
                )

    @staticmethod
    def timeline_plan_format(segment_count: int) -> dict[str, Any]:
        string_array = {"type": "array", "items": {"type": "string"}}
        keyframe_binding = {
            "type": "object",
            "properties": {
                "reference_id": {"type": "string"},
                "local_frame": {"type": "integer"},
                "placement_reason": {"type": "string"},
            },
            "required": ["reference_id", "local_frame", "placement_reason"],
        }
        segment = {
            "type": "object",
            "properties": {
                "segment_id": {"type": "string"}, "title": {"type": "string"},
                "duration": {"type": "integer"}, "brief": {"type": "string"},
                "negative_prompt": {"type": "string"}, "reference_ids": string_array,
                "dialogue_lines": string_array,
                "opening_state": {"type": "string"}, "ending_state": {"type": "string"},
                "continuity_from_previous": {"type": "string"},
                "transition": {"type": "string", "enum": ["cut", "motion_context"]},
                "keyframe_bindings": {"type": "array", "items": keyframe_binding},
                "keyframe_transitions": string_array,
            },
            "required": ["segment_id", "title", "duration", "brief", "negative_prompt",
                         "reference_ids", "dialogue_lines", "opening_state", "ending_state",
                         "continuity_from_previous", "transition", "keyframe_bindings",
                         "keyframe_transitions"],
        }
        schema = {
            "type": "object",
            "properties": {
                "global_prompt": {"type": "string"},
                "global_negative_prompt": {"type": "string"},
                "global_reference_ids": string_array,
                "global_reference_bindings": string_array,
                "segments": {"type": "array", "items": segment,
                             "minItems": segment_count, "maxItems": segment_count},
            },
            "required": ["global_prompt", "global_negative_prompt", "global_reference_ids",
                         "global_reference_bindings", "segments"],
        }
        return {"type": "json_schema", "json_schema": {
            "name": "aipm_timeline_plan", "strict": True, "schema": schema,
        }}

    @staticmethod
    def validate_prompt_text(prompt: str, requested_language: str) -> None:
        text = str(prompt or "").strip()
        if not text:
            raise PromptAssistantError("提示词为空")
        if requested_language != "English" and len(re.findall(r"[\u3400-\u9fff]", text)) < 30:
            raise PromptAssistantError("中文模式下描述正文必须使用中文，只有H3官方语法保留英文")

    @staticmethod
    def validate_h3_structure(prompt: str, mode: str, duration_seconds: int) -> None:
        """Reject structurally invalid H3 prompts before they enter CineTimeline."""
        text = str(prompt or "").strip()
        base_fields = [
            "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music",
        ]
        ref_fields = [
            "subject_definitions", "summary", "retention_analysis", "detailed_description",
            "overall_soundscape", "non_diegetic_music",
        ]
        expected = ref_fields if mode == "h3_ref2va" else base_fields
        found = re.findall(
            r"(?m)^(subject_definitions|summary|retention_analysis|detailed_description|"
            r"integrated_multimodal_description|overall_soundscape|non_diegetic_music)\s*:", text,
        )
        if found != expected:
            raise PromptAssistantError(
                f"MiniMax H3 {mode} 字段结构错误：应为 {' -> '.join(expected)}，实际为 {' -> '.join(found) or '无'}"
            )
        if "【" in text or "】" in text:
            raise PromptAssistantError("MiniMax H3 机器提示词不能包含中文方括号编辑标签")
        for minutes, seconds, millis in re.findall(r"At\s+(\d{2}):(\d{2})\.(\d{3})", text):
            timestamp = int(minutes) * 60 + int(seconds) + int(millis) / 1000
            if timestamp < 0 or timestamp > duration_seconds:
                raise PromptAssistantError(
                    f"镜头时间 {minutes}:{seconds}.{millis} 必须位于 0 至 {duration_seconds} 秒的闭区间内"
                )

    @staticmethod
    def bind_dialogue_speaker_ids(prompt: str, dialogue_lines: list[str]) -> str:
        """Deterministically bind one stable speaker ID to each H3 vocal event."""
        roles = [
            re.split(r"[：:]", str(line), maxsplit=1)[0].strip()
            for line in dialogue_lines if str(line).strip()
        ]
        if not roles:
            return prompt
        role_ids: dict[str, int] = {}
        for role in roles:
            if role not in role_ids:
                role_ids[role] = len(role_ids) + 1
        dialogue_pattern = re.compile(r"<d>\s*\[[^\]]+\]\s*.+?</d>", re.DOTALL)
        matches = list(dialogue_pattern.finditer(prompt))
        if not matches:
            return prompt

        output: list[str] = []
        cursor = 0
        for dialogue_index, match in enumerate(matches):
            role = roles[min(dialogue_index, len(roles) - 1)]
            speaker = f"(S{role_ids[role]})"
            between = prompt[cursor:match.start()]

            # A speaker ID belongs to the current vocal clause, not necessarily
            # immediately next to <d>.  Keep its first occurrence and remove only
            # duplicate occurrences of the same ID in that clause.  Strong sentence
            # boundaries keep IDs from an earlier vocal event out of consideration.
            boundary = max(
                between.rfind(marker)
                for marker in ("。", "！", "？", "\n", "<scenetrans>", "<cutoff>")
            )
            head, clause = between[:boundary + 1], between[boundary + 1:]
            occurrences = list(re.finditer(re.escape(speaker), clause))
            if occurrences:
                first_seen = False

                def deduplicate(current: re.Match[str]) -> str:
                    nonlocal first_seen
                    if not first_seen:
                        first_seen = True
                        return current.group(0)
                    return ""

                clause = re.sub(re.escape(speaker), deduplicate, clause)
            else:
                clause = f"{clause}{speaker} "

            output.extend((head, clause, match.group(0)))
            cursor = match.end()

        output.append(prompt[cursor:])
        return "".join(output)

    @staticmethod
    def compile_h3_prompt(local_prompt: str, global_prompt: str, negative_prompt: str) -> str:
        """Compile a timeline-local H3 prompt into a standalone executable prompt."""
        text = str(local_prompt or "").strip()
        common = str(global_prompt or "").strip()
        negative = str(negative_prompt or "").strip()
        if not text:
            return text
        field_pattern = re.compile(
            r"(?m)^(integrated_multimodal_description|overall_soundscape|non_diegetic_music|"
            r"subject_definitions|summary|retention_analysis|detailed_description)\s*:\s*"
        )
        matches = list(field_pattern.finditer(text))
        if not matches:
            return "\n\n".join(value for value in (common, text) if value)
        preamble = text[:matches[0].start()].strip()
        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections.append((match.group(1), text[match.end():end].strip()))
        target = (
            "detailed_description"
            if any(name == "detailed_description" for name, _ in sections)
            else "integrated_multimodal_description"
        )
        compiled_sections = []
        for name, value in sections:
            if name == target:
                additions = [common, value]
                if negative:
                    additions.append("视觉限制：避免出现" + negative)
                value = "\n".join(part for part in additions if part)
            compiled_sections.append(f"{name}: {value}")
        return "\n\n".join(part for part in (preamble, *compiled_sections) if part)

    def generate_timeline_package(
        self, *, service_url: str, service_model: str, profile: str, mode: str,
        idea: str, duration_seconds: int, segment_count: int, aspect_ratio: str,
        requested_language: str, skill_id: str, skill: str,
        reference_profiles: list[dict[str, Any]], cache_hits: int,
        has_video: bool | int, has_audio: bool | int, previous: dict[str, Any] | None,
        modification: str, video_assets: list[dict[str, Any]] | None = None,
        audio_assets: list[dict[str, Any]] | None = None,
        operation: str = "rewrite", base_package: dict[str, Any] | None = None,
        target_segment_id: str = "",
    ):
        base_package = copy.deepcopy(base_package) if isinstance(base_package, dict) else None
        base_segments = copy.deepcopy(base_package.get("segments") or []) if base_package else []
        append_offset = max([len(base_segments)] + [int(m.group(1)) for s in base_segments
                            if (m := re.fullmatch(r"SEGMENT_(\d+)", str(s.get("segment_id") or "")))]) if operation == "append" else 0
        target_index = next((
            index for index, item in enumerate(base_segments)
            if str(item.get("segment_id") or "") == str(target_segment_id or "")
        ), -1)
        if operation == "revise_segment" and target_index < 0:
            raise PromptAssistantError("修改目标分段不在AIPM缓存中")
        dialogue_requested = requires_planned_dialogue(idea)
        repeated_segments_allowed = explicitly_allows_repeated_segments(idea)
        reference_ids = [item["picture_id"] for item in reference_profiles]
        image_reference_ids = list(reference_ids)
        video_count = int(has_video or 0)
        audio_count = int(has_audio or 0)
        reference_ids.extend(f"<Video {index}>" for index in range(1, video_count + 1))
        reference_ids.extend(f"<Audio {index}>" for index in range(1, audio_count + 1))
        resume_key = hashlib.sha256(json.dumps({
            "service_model": service_model, "profile": profile, "mode": mode,
            "idea": idea, "duration_seconds": duration_seconds,
            "segment_count": segment_count, "aspect_ratio": aspect_ratio,
            "requested_language": requested_language,
            "reference_ids": reference_ids,
        }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        resumable = bool(
            isinstance(previous, dict)
            and previous.get("generation_status") == "interrupted"
            and previous.get("resume_key") == resume_key
            and isinstance(previous.get("timeline_plan"), dict)
        )
        plan_context = {
            "task": "规划全局与分段提示词", "idea": idea, "segment_count": segment_count,
            "default_segment_duration": duration_seconds, "target_model": profile,
            "mode": mode, "aspect_ratio": aspect_ratio, "language": requested_language,
            "timeline_fps": 24,
            "planning_review": load_h3_planning_review(),
            "reference_profiles": reference_profiles, "available_reference_ids": reference_ids,
            "previous_result": previous, "modification_request": modification if previous else "",
            "timeline_operation": operation,
            "existing_segments": [{
                "segment_id": item.get("segment_id"), "title": item.get("title"),
                "prompt": item.get("timeline_local_prompt") or item.get("source_prompt") or item.get("prompt"),
                "opening_state": item.get("opening_state"), "ending_state": item.get("ending_state"),
                "transition": item.get("transition", "cut"),
            } for item in base_segments],
            "target_segment": base_segments[target_index] if target_index >= 0 else None,
            "promotion_rules": [
                "只有在全部分段都使用且属性保持一致的人物、服装、场景或参考才提升到全局",
                "人物身份可全局但换装可留在分段；参考绑定必须写明继承属性和排除属性",
                "若没有共同人物服装场景，全局只保留画面风格、画质、色彩、摄影语言、声音规范和公共负向约束",
                "每个分段只列本段额外需要的参考；不得把未使用参考塞入全局",
                f"必须准确输出 {segment_count} 个分段，每段默认 {duration_seconds} 秒",
                "默认每段推进不同剧情，禁止把完整要求复制到每段；用户明确要求重复演示或循环时保留重复，其他情况下brief、opening_state、ending_state不得三项全同",
                "多模态模式keyframe_bindings和keyframe_transitions必须为空；人物/道具参考不等于指定帧位",
                "若创作要求提出需要台词、对白、旁白或角色说话，但没有给出逐字文本，必须结合人物关系、情境、目标和时长主动创作简洁可表演的台词，并在对应分段计划中明确台词内容与说话者；若用户给出逐字台词，则必须原样保留",
                "每个分段的dialogue_lines必须列出本段实际发声内容，格式为‘角色：逐字台词’；没有任何发声时返回空数组，禁止用‘包含对白’‘角色说话’等占位描述",
                "transition表示进入本段的边界：全新时间轴第一段必须为cut；续写的第一段必须根据现有最后一段决定cut或motion_context；只有动作、机位运动、构图尺度和声音相位都应从上一段无缝延续时才用motion_context",
                "切换景别（尤其近景/特写后回到中景或远景）、机位、视角、场景、时间或叙事焦点时必须用cut，避免把上一段的近景构图永久继承到后续分段",
                "续写只规划新增分段，不重写existing_segments；修改指定分段时只规划target_segment，并同时兼顾相邻分段边界",
                "规划内容精炼，禁止在规划JSON里撰写完整H3提示词",
            ],
        }
        if mode == "h3_keyframe":
            frame_count = max(1, round(duration_seconds * 24))
            plan_context["keyframe_rules"] = [
                "逐张比较reference_profiles中的画面内容、动作阶段、构图与因果关系，再决定中间关键帧位置",
                f"每个分段固定按24fps计算，共{frame_count}帧，合法局部帧为0到{frame_count - 1}",
                "每个分段的keyframe_bindings必须包含全部图片，顺序必须与available_reference_ids中的Picture顺序一致",
                "只有一张图片时固定local_frame=0；两张图片时固定为0和末帧",
                "三张及以上时第一张固定0、最后一张固定末帧；中间图片根据动作与叙事所需时长选择严格递增的帧，不得机械均分",
                "keyframe_transitions必须逐区间说明从当前图片到下一图片之间的可见动作、表演、镜头与画面演化，并明确对应起止帧",
            ]
        plan_payload = {
            "model": service_model,
            "messages": [
                {"role": "system", "content": "你是影视时间线规划师。只输出小型规划JSON，不写完整提示词。"},
                {"role": "user", "content": [{"type": "text", "text": json.dumps(plan_context, ensure_ascii=False)}]},
            ],
            "temperature": 0.2, "max_tokens": min(2400, 700 + segment_count * 260),
            "cache_prompt": False, "response_format": self.timeline_plan_format(segment_count),
            "chat_template_kwargs": {"enable_thinking": False},
        }
        def validate_plan(candidate: dict[str, Any]) -> None:
            planned_segments = candidate.get("segments") if isinstance(candidate, dict) else None
            if not isinstance(planned_segments, list) or len(planned_segments) != segment_count:
                raise PromptAssistantError(f"时间线规划必须返回 {segment_count} 个分段")
            if dialogue_requested and not any(
                str(line).strip()
                for segment in planned_segments
                for line in (segment.get("dialogue_lines") or [])
            ):
                raise PromptAssistantError("创作要求需要台词，但时间线规划没有产出任何实际台词正文")
            normalize_plan_mode(candidate, mode)
            if segment_count > 1 and not repeated_segments_allowed:
                signatures = [
                    tuple(re.sub(r"\s+", "", str(segment.get(field) or "")) for field in (
                        "brief", "opening_state", "ending_state",
                    ))
                    for segment in planned_segments
                ]
                if len(set(signatures)) != len(signatures):
                    raise PromptAssistantError("多段时间线包含重复剧情阶段")
            if mode == "h3_keyframe" and image_reference_ids:
                expected_ids = list(image_reference_ids)
                last_frame = max(0, round(duration_seconds * 24) - 1)
                for segment in planned_segments:
                    bindings = segment.get("keyframe_bindings")
                    if not isinstance(bindings, list):
                        raise PromptAssistantError("关键帧规划缺少keyframe_bindings")
                    ids = [str(item.get("reference_id") or "") for item in bindings if isinstance(item, dict)]
                    frames = [int(item.get("local_frame", -1)) for item in bindings if isinstance(item, dict)]
                    if ids != expected_ids or len(frames) != len(expected_ids):
                        raise PromptAssistantError("关键帧规划必须按图片输入顺序绑定全部参考图")
                    if not frames or frames[0] != 0:
                        raise PromptAssistantError("第一张关键帧图片必须位于局部第0帧")
                    if len(frames) >= 2 and frames[-1] != last_frame:
                        raise PromptAssistantError("最后一张关键帧图片必须位于片段末帧")
                    if frames != sorted(set(frames)) or any(frame < 0 or frame > last_frame for frame in frames):
                        raise PromptAssistantError("关键帧帧位必须合法且严格递增")
                    transitions = segment.get("keyframe_transitions")
                    if len(frames) >= 2 and (not isinstance(transitions, list) or len(transitions) != len(frames) - 1):
                        raise PromptAssistantError("每两个关键帧之间都必须有一条画面演化描述")

        try:
            if resumable:
                plan = copy.deepcopy(previous["timeline_plan"])
                validate_plan(plan)
                plan_response = {"usage": {}, "aipm_resume": True}
            else:
                plan, plan_response = OpenAICompatibleClient.request_object(
                    service_url, plan_payload, "时间线规划", attempts=3, validator=validate_plan,
                )
        except PromptAssistantError:
            # Small local fallback: some llama.cpp JSON-schema backends truncate
            # even a one-segment planning object. Planning is only routing data;
            # the professional segment prompt is still authored by the remote
            # model in the next stage, so do not abort the whole workflow here.
            plan = {
                "global_prompt": "电影级写实质感、稳定主体身份与空间连续性、自然光影、清晰细节",
                "global_negative_prompt": "低清晰度、闪烁、重影、身份漂移、畸形肢体、文字、水印",
                "global_reference_ids": reference_ids if segment_count == 1 else [],
                "global_reference_bindings": [],
                "segments": [{
                    "segment_id": (
                        str(target_segment_id) if operation == "revise_segment"
                        else f"SEGMENT_{append_offset + index + 1:03d}"
                    ),
                    "title": f"分段 {index + 1}",
                    "duration": duration_seconds,
                    "brief": f"第 {index + 1}/{segment_count} 段：只表现完整创作要求中按时间顺序对应本阶段的剧情，不提前或重复其他阶段。原始要求：{idea}",
                    "negative_prompt": "",
                    "reference_ids": reference_ids,
                    "dialogue_lines": [],
                    "opening_state": f"第 {index + 1} 段起始状态；承接此前阶段且不得回到已完成动作",
                    "ending_state": f"第 {index + 1} 段结束状态；必须推进到下一剧情阶段",
                    "continuity_from_previous": "" if index == 0 else "承接上一分段结束状态",
                    "transition": (
                        str(base_segments[target_index].get("transition") or "cut")
                        if operation == "revise_segment" else "cut"
                    ),
                    "keyframe_bindings": [{
                        "reference_id": reference_id,
                        "local_frame": (
                            0 if len(image_reference_ids) <= 1 else
                            round(image_index * (max(1, round(duration_seconds * 24)) - 1) / (len(image_reference_ids) - 1))
                        ),
                        "placement_reason": "远程规划不可用时的安全边界/均分回退",
                    } for image_index, reference_id in enumerate(image_reference_ids)] if mode == "h3_keyframe" else [],
                    "keyframe_transitions": [
                        f"从{image_reference_ids[image_index]}演化到{image_reference_ids[image_index + 1]}"
                        for image_index in range(max(0, len(image_reference_ids) - 1))
                    ] if mode == "h3_keyframe" else [],
                } for index in range(segment_count)],
            }
            plan_response = {"usage": {}, "aipm_fallback": "local_timeline_plan"}
        normalize_plan_mode(plan, mode)
        segments_plan = plan.get("segments") if isinstance(plan.get("segments"), list) else []
        if len(segments_plan) != segment_count:
            raise PromptAssistantError(f"时间线规划应返回 {segment_count} 段，实际返回 {len(segments_plan)} 段")

        global_prompt = str(plan.get("global_prompt") or "").strip()
        global_negative = str(plan.get("global_negative_prompt") or "").strip()
        global_reference_ids = [str(value) for value in plan.get("global_reference_ids", []) if str(value) in reference_ids]
        if base_package and operation in {"append", "revise_segment"}:
            base_global = base_package.get("global") if isinstance(base_package.get("global"), dict) else {}
            global_prompt = str(base_global.get("prompt") or global_prompt)
            global_negative = str(base_global.get("negative_prompt") or global_negative)
            global_reference_ids = [
                str(value) for value in base_global.get("reference_ids", []) if str(value)
            ]
        # Only multimodal mode has true timeline-global references.  In the
        # three image-sequenced modes, every connected image is attached to
        # every concrete segment in connector order; the adapter decides
        # whether those ordered images are ordinary, boundary, or keyframes.
        if mode != "h3_ref2va":
            global_reference_ids = []
        elif segments_plan:
            # The planner may leave a reference on every segment instead of
            # promoting it.  Timeline-wide intersection is authoritative:
            # references used by every segment belong to the global scope.
            per_segment_reference_sets = [
                {str(value) for value in segment.get("reference_ids", []) if str(value) in reference_ids}
                for segment in segments_plan
            ]
            shared_reference_ids = set.intersection(*per_segment_reference_sets) if per_segment_reference_sets else set()
            global_reference_ids = list(dict.fromkeys(
                global_reference_ids + [value for value in reference_ids if value in shared_reference_ids]
            ))
            plan["global_reference_ids"] = list(global_reference_ids)
            for segment in segments_plan:
                segment["reference_ids"] = [
                    str(value) for value in segment.get("reference_ids", [])
                    if str(value) in reference_ids and str(value) not in global_reference_ids
                ]
        segment_results = copy.deepcopy(previous.get("segments") or []) if resumable else []
        if len(segment_results) > segment_count:
            segment_results = []
            resumable = False
        usage_records = copy.deepcopy(previous.get("usage", {}).get("stages") or []) if resumable else []
        usage_records.append(plan_response.get("usage") or {})
        previous_end = str(segment_results[-1].get("ending_state") or "") if segment_results else ""
        start_index = len(segment_results)
        interrupted_error = ""
        failed_segment_id = ""
        for index, segment_plan in enumerate(segments_plan[start_index:], start=start_index):
            segment_id = (
                str(target_segment_id) if operation == "revise_segment"
                else f"SEGMENT_{append_offset + index + 1:03d}"
            )
            segment_refs = (
                list(image_reference_ids)
                if mode != "h3_ref2va" and image_reference_ids
                else [str(value) for value in segment_plan.get("reference_ids", []) if str(value) in reference_ids]
            )
            active_refs = list(dict.fromkeys(global_reference_ids + segment_refs))
            prompt_context = {
                "task": "只生成当前分段可直接执行的MiniMax H3提示词纯文本",
                "professional_skill": skill, "target_model": profile, "mode": mode,
                "language": requested_language, "aspect_ratio": aspect_ratio,
                "original_idea": idea,
                "segment_id": segment_id, "duration_seconds": duration_seconds,
                "global_prompt_is_upstream": True, "global_reference_ids": global_reference_ids,
                "segment_plan": segment_plan, "active_reference_ids": active_refs,
                "reference_profiles": [item for item in reference_profiles if item["picture_id"] in active_refs],
                "previous_segment_end": previous_end,
                "rules": [
                    "输出纯文本，不输出JSON、Markdown或解释",
                    "只写当前分段的局部H3提示词，不重复global_prompt中的公共风格、人物、服装、场景或声音规范；全局内容将由本地编译器合并",
                    "只使用active_reference_ids中的参考，并保持官方Subject/Picture/Video/Audio语法",
                    f"本段严格为{duration_seconds}秒，结尾状态必须落定",
                    "中文模式下只有官方字段、标签和枚举为英文，所有描述正文使用中文",
                    "若segment_plan或创作要求需要台词、对白、旁白或角色说话，必须写出实际可朗读的台词正文，不能只写‘角色说话’或仅描述音色；未指定原文时主动根据剧情创作，已指定原文时逐字保留",
                    "segment_plan.dialogue_lines中的每一条都是必须执行的逐字台词：在对应动作时刻将角色名映射为稳定(SN)，并逐句写入<d>[语言] 实际台词</d>，不得遗漏、概括或移到overall_soundscape",
                    "为实际发声者按首次开口顺序绑定稳定(S1)、(S2)编号，并使用<d>[语言] 实际台词</d>；不说话的角色不得虚构声纹编号",
                ],
            }
            if mode == "h3_keyframe" and image_reference_ids:
                prompt_context["rules"].extend([
                    "严格采用segment_plan.keyframe_bindings中的24fps局部帧位，不得改写关键帧位置",
                    "在detailed_description/integrated_multimodal_description正文中明确写出每个关键帧的帧号",
                    "按segment_plan.keyframe_transitions逐区间描述相邻图片之间连续、物理可行的画面变化过程，不能只罗列静态图片",
                    "关键帧图片由Add Guide按帧注入，不是Ref2VA参考；提示词禁止输出<Picture N>或<Subject N>媒体标签，改用‘第N张关键帧图像’和具体帧号描述",
                ])
            text_payload = {
                "model": service_model,
                "messages": [
                    {"role": "system", "content": "你是MiniMax H3提示词导演。只返回当前分段的完整提示词纯文本。"},
                    {"role": "user", "content": [{"type": "text", "text": json.dumps(prompt_context, ensure_ascii=False)}]},
                ],
                "temperature": 0.25, "max_tokens": 3200, "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            planned_dialogue = [
                str(value).strip() for value in segment_plan.get("dialogue_lines", [])
                if str(value).strip()
            ]
            expected_speakers = {
                re.split(r"[：:]", line, maxsplit=1)[0].strip()
                for line in planned_dialogue
            }

            def validate_segment_text(text: str) -> None:
                self.validate_prompt_text(text, requested_language)
                self.validate_h3_structure(text, mode, duration_seconds)
                if planned_dialogue and not re.search(
                    r"<d>\s*\[[^\]]+\]\s*.+?</d>", text, re.DOTALL,
                ):
                    raise PromptAssistantError(
                        "当前分段规划包含台词，但生成结果缺少H3 <d>[语言]…</d>台词正文"
                    )
                if mode == "h3_keyframe" and image_reference_ids:
                    if re.search(r"<(?:Picture|Subject)\s+\d+>", text, re.IGNORECASE):
                        raise PromptAssistantError("关键帧模式使用Add Guide注入图片，提示词不能包含Ref2VA Picture/Subject标签")
                    missing_frames = [
                        int(item.get("local_frame", -1))
                        for item in segment_plan.get("keyframe_bindings", [])
                        if not re.search(
                            rf"(?:第\s*{int(item.get('local_frame', -1))}\s*帧|frame\s*{int(item.get('local_frame', -1))}\b)",
                            text, re.IGNORECASE,
                        )
                    ]
                    if missing_frames:
                        raise PromptAssistantError(f"关键帧提示词没有明确描述帧位：{missing_frames}")
            try:
                segment_prompt, segment_response = OpenAICompatibleClient.request_text(
                    service_url, text_payload, f"{segment_id} 提示词生成", attempts=2,
                    validator=validate_segment_text,
                )
                source_prompt = segment_prompt
                timeline_local_prompt = self.bind_dialogue_speaker_ids(source_prompt, planned_dialogue)
                compiled_prompt = self.compile_h3_prompt(
                    timeline_local_prompt, global_prompt, global_negative,
                )
                speaker_ids = set(re.findall(r"\(S\d+\)", timeline_local_prompt))
                if planned_dialogue and len(speaker_ids) < len(expected_speakers):
                    raise PromptAssistantError(
                        f"当前分段有 {len(expected_speakers)} 个发声角色，但本地只绑定了 "
                        f"{len(speaker_ids)} 个H3 (SN)声纹编号"
                    )
            except PromptAssistantError as exc:
                interrupted_error = str(exc)
                failed_segment_id = segment_id
                break
            usage_records.append(segment_response.get("usage") or {})
            opening_state = str(segment_plan.get("opening_state") or "").strip()
            ending_state = str(segment_plan.get("ending_state") or "").strip()
            segment_results.append({
                "segment_id": segment_id, "index": index + 1,
                "title": str(segment_plan.get("title") or segment_id),
                "start": index * duration_seconds, "end": (index + 1) * duration_seconds,
                "duration": duration_seconds, "dramatic_purpose": str(segment_plan.get("brief") or ""),
                "dialogue_lines": planned_dialogue,
                "prompt": source_prompt, "source_prompt": source_prompt,
                "timeline_local_prompt": timeline_local_prompt,
                "compiled_prompt": compiled_prompt,
                "negative_prompt": str(segment_plan.get("negative_prompt") or "").strip(),
                "reference_ids": segment_refs, "effective_reference_ids": active_refs,
                "keyframe_bindings": copy.deepcopy(segment_plan.get("keyframe_bindings") or []),
                "keyframe_transitions": copy.deepcopy(segment_plan.get("keyframe_transitions") or []),
                "opening_state": opening_state, "ending_state": ending_state,
                "continuity_from_previous": str(segment_plan.get("continuity_from_previous") or "").strip(),
                "transition": (
                    str(base_segments[target_index].get("transition") or "cut")
                    if operation == "revise_segment" else
                    "cut" if index == 0 and operation == "rewrite" else
                    "motion_context" if str(segment_plan.get("transition") or "cut") == "motion_context" else "cut"
                ),
            })
            previous_end = ending_state

        complete = len(segment_results) == segment_count and not interrupted_error
        first = segment_results[0] if segment_results else None
        effective_negative = "，".join(value for value in [
            global_negative, first["negative_prompt"] if first else "",
        ] if value)
        package = {
            "schema": "aipm_video_timeline", "version": "2.0", "prompt_skill_id": skill_id,
            "revision": (int(previous.get("revision") or 1) if resumable
                         else int(previous.get("revision") or 1) + 1 if previous else 1),
            "modification_request": modification if previous else "", "target_model": profile,
            "generation_mode": mode, "segment_count": segment_count,
            "default_segment_duration": duration_seconds, "total_duration": duration_seconds * segment_count,
            "aspect_ratio": aspect_ratio, "prompt_language": "en" if requested_language == "English" else "zh-CN",
            "global": {
                "prompt": global_prompt, "negative_prompt": global_negative,
                "reference_ids": global_reference_ids,
                "reference_bindings": plan.get("global_reference_bindings") or [],
            },
            "generation_status": "complete" if complete else "interrupted",
            "resume_key": resume_key,
            "resume_from_segment": None if complete else len(segment_results) + 1,
            "failed_segment_id": failed_segment_id,
            "interruption_error": interrupted_error,
            "timeline_plan": copy.deepcopy(plan),
            "segments": segment_results,
            "video_prompt": first["compiled_prompt"] if first else "",
            "negative_prompt": effective_negative,
            "audio_prompt": "声音设计已包含在各分段H3提示词的 overall_soundscape 与 non_diegetic_music 中。",
            "reference_count": len(reference_ids), "reference_profiles": reference_profiles,
            "media_assets": {
                "videos": copy.deepcopy(video_assets or []),
                "audios": copy.deepcopy(audio_assets or []),
            },
            "reference_analysis_cache_hits": cache_hits,
            "processing_strategy": "reference-analysis -> compact-global-segment-plan -> resumable-per-segment-text -> local-package",
            "usage": {"stages": usage_records},
        }
        if operation == "append" and base_package:
            append_profiles = copy.deepcopy(package.get("reference_profiles") or [])
            append_media = copy.deepcopy(package.get("media_assets") or {})
            appended = copy.deepcopy(package["segments"])
            append_complete = package["generation_status"] == "complete"
            append_failure = package.get("interruption_error", "")
            append_failed_id = package.get("failed_segment_id", "")
            package = copy.deepcopy(base_package)
            package["revision"] = int(base_package.get("revision") or 1) + 1
            package["segments"] = base_segments + appended
            package["segment_count"] = len(base_segments) + segment_count
            package["total_duration"] = sum(float(item.get("duration") or duration_seconds) for item in package["segments"])
            package["generation_status"] = "complete" if append_complete else "interrupted"
            package["resume_from_segment"] = None if append_complete else len(base_segments) + len(appended) + 1
            package["failed_segment_id"] = "" if append_complete else append_failed_id
            package["interruption_error"] = "" if append_complete else append_failure
            package["resume_key"] = resume_key
            package["aipm_operation"] = "append"
            package["append_base_count"] = len(base_segments)
            package["append_requested_count"] = segment_count
            package["timeline_plan"] = copy.deepcopy(plan)
            package["usage"] = {"stages": usage_records}
            known_profile_ids = {
                str(item.get("picture_id") or "")
                for item in package.get("reference_profiles", []) if isinstance(item, dict)
            }
            package.setdefault("reference_profiles", []).extend(
                item for item in append_profiles
                if str(item.get("picture_id") or "") not in known_profile_ids
            )
            package["reference_count"] = len(package.get("reference_profiles") or [])
            package.setdefault("media_assets", {"videos": [], "audios": []})
            for key in ("videos", "audios"):
                existing_ids = {
                    str(item.get("asset_id") or "")
                    for item in package["media_assets"].get(key, []) if isinstance(item, dict)
                }
                package["media_assets"].setdefault(key, []).extend(
                    item for item in append_media.get(key, [])
                    if str(item.get("asset_id") or "") not in existing_ids
                )
        elif operation == "revise_segment" and base_package:
            if not package["segments"]:
                package = copy.deepcopy(base_package)
                package["generation_status"] = "interrupted"
                package["resume_from_segment"] = target_index + 1
                package["failed_segment_id"] = str(target_segment_id)
                package["interruption_error"] = interrupted_error or "指定分段修改未完成"
                package["aipm_operation"] = "revise_segment"
                package["revision_target_segment_id"] = str(target_segment_id)
                cine_timeline, cine_timeline_json = self._canonical_timeline(package)
                return {"ui": {"text": [package.get("video_prompt", ""), package.get("negative_prompt", ""), cine_timeline_json]},
                        "result": (cine_timeline, package.get("video_prompt", ""), package.get("negative_prompt", ""),
                                   package.get("audio_prompt", ""), cine_timeline_json)}
            revised = copy.deepcopy(package["segments"][0])
            original = copy.deepcopy(base_segments[target_index])
            revised["segment_id"] = original.get("segment_id")
            revised["index"] = original.get("index", target_index + 1)
            revised["start"] = original.get("start", 0)
            revised["end"] = original.get("end", revised.get("duration", duration_seconds))
            revised["duration"] = original.get("duration", duration_seconds)
            revised["transition"] = original.get("transition", "cut")
            package = copy.deepcopy(base_package)
            package["revision"] = int(base_package.get("revision") or 1) + 1
            package["segments"][target_index] = revised
            package["generation_status"] = "complete"
            package["resume_from_segment"] = None
            package["failed_segment_id"] = ""
            package["interruption_error"] = ""
            package["aipm_operation"] = "revise_segment"
            package["revision_target_segment_id"] = str(target_segment_id)
            package["usage"] = {"stages": usage_records}
        cine_timeline, cine_timeline_json = self._canonical_timeline(package)
        return {"ui": {"text": [package["video_prompt"], package["negative_prompt"], cine_timeline_json]},
                "result": (
                    cine_timeline, package["video_prompt"], package["negative_prompt"],
                    package["audio_prompt"], cine_timeline_json,
                )}

    def generate(self, 视频内容与导演要求, 远程服务地址, 模型名称, 目标视频模型, 生成模式,
                 视频时长, 构图比例, 提示词语言, 分段数量, image1=None, image2=None,
                 image3=None, image4=None, image5=None, image6=None, image7=None, image8=None, image9=None,
                 video1=None, video2=None, video3=None, audio1=None, audio2=None, audio3=None,
                 修改意见="", 上次结果JSON="", 参考素材清单JSON="[]"):
        idea = str(视频内容与导演要求 or "").strip()
        if not idea:
            raise PromptAssistantError("请先填写视频内容与导演要求")
        try:
            duration_seconds = int(视频时长)
        except (TypeError, ValueError):
            # Development-time migration for workflows saved with the former
            # values such as "5秒". New workflows always submit an INT.
            match = re.search(r"\d+", str(视频时长 or ""))
            duration_seconds = int(match.group()) if match else 5
        duration_seconds = max(4, min(30, duration_seconds))
        duration_label = f"{duration_seconds}秒"
        try:
            segment_count = max(1, min(12, int(分段数量)))
        except (TypeError, ValueError):
            segment_count = 1
        modification = str(修改意见 or "").strip()
        previous_json = str(上次结果JSON or "").strip()
        operation = "rewrite"
        target_segment_id = ""
        base_package = None
        run_marker = "__AIPM_RUN_V1__"
        run_marker_v2 = "__AIPM_RUN_V2__"
        independent_execution = modification.startswith(run_marker)
        if modification.startswith(run_marker_v2):
            independent_execution = True
            try:
                run_payload = json.loads(modification[len(run_marker_v2):])
                operation = str(run_payload.get("operation") or "rewrite")
                target_segment_id = str(run_payload.get("target_segment_id") or "")
                previous_json = str(run_payload.get("previous_result") or previous_json or "")
                if operation == "append" and run_payload.get("editor_timeline") is not None:
                    stored = self._authoring_data(json.loads(previous_json))
                    previous_json = json.dumps(reconcile_append_editor(stored, run_payload["editor_timeline"]), ensure_ascii=False)
                modification = str(run_payload.get("instruction") or "").strip()
            except (json.JSONDecodeError, AttributeError) as exc:
                raise PromptAssistantError("AIPM时间轴操作请求无效") from exc
        if independent_execution:
            if operation not in {"append", "revise_segment"}:
                modification = ""
        marker = "__AIPM_REVISION_V1__"
        if modification.startswith(marker):
            independent_execution = True
            try:
                revision_payload = json.loads(modification[len(marker):])
                modification = str(revision_payload.get("instruction") or "").strip()
                previous_json = str(revision_payload.get("previous_result") or "").strip()
            except (json.JSONDecodeError, AttributeError) as exc:
                raise PromptAssistantError("修改请求数据无效，请重新生成后再优化") from exc
        # Some workflows were saved before `参考图用途` was inserted ahead of
        # the hidden cache widgets. ComfyUI then restores the cached result into
        # `修改意见`. Treat a complete saved result as cache data, never as a
        # revision instruction, so Ctrl+Enter remains offline and deterministic.
        if modification and not independent_execution:
            try:
                shifted_cache = json.loads(modification)
            except json.JSONDecodeError:
                shifted_cache = None
            shifted_authoring = self._authoring_data(shifted_cache) if isinstance(shifted_cache, dict) else {}
            if (isinstance(shifted_authoring, dict)
                    and shifted_authoring.get("video_prompt")
                    and shifted_cache.get("schema") in {"aipm_video_prompt", "cine_timeline", "cine_keyframe_timeline"}):
                if not previous_json:
                    previous_json = modification
                modification = ""
        # The node's own generate button stores its result in this hidden
        # widget. A later full-workflow queue must reuse it instead of calling
        # the remote model again.
        if previous_json and not modification and not independent_execution:
            try:
                stored = json.loads(previous_json)
            except json.JSONDecodeError as exc:
                raise PromptAssistantError("已保存的视频提示词结果无效，请清空后重新生成") from exc
            authoring = self._authoring_data(stored)
            if isinstance(authoring, dict) and authoring.get("generation_status") == "interrupted":
                resume_from = int(authoring.get("resume_from_segment") or 1)
                raise PromptAssistantError(
                    f"AIPM多段提示词尚未完成，当前应从第 {resume_from} 段继续；"
                    "请点击节点上的“生成 / 继续生成”，不要运行主工作流。"
                )
            if (not isinstance(stored, dict)
                    or stored.get("schema") not in {"cine_timeline", "cine_keyframe_timeline"}
                    or not authoring.get("video_prompt")):
                raise PromptAssistantError("已保存的视频提示词结果无效，请清空后重新生成")
            raw = json.dumps(stored, ensure_ascii=False, indent=2)
            return {
                "ui": {"text": [str(authoring.get("video_prompt") or ""), str(authoring.get("negative_prompt") or ""), raw]},
                "result": (
                    stored, str(authoring.get("video_prompt") or ""),
                    str(authoring.get("negative_prompt") or ""), str(authoring.get("audio_prompt") or ""),
                    raw,
                ),
            }
        if not independent_execution:
            raise PromptAssistantError("AIPM不会随主工作流调用远程AI。请先点击节点上的“生成 / 重新创作”按钮生成并缓存提示词。")
        previous = None
        if previous_json and (modification or independent_execution):
            try:
                candidate = json.loads(previous_json)
            except json.JSONDecodeError as exc:
                raise PromptAssistantError("没有可用于修改的上次有效结果") from exc
            candidate = self._authoring_data(candidate)
            if operation in {"append", "revise_segment"}:
                if not isinstance(candidate, dict) or not isinstance(candidate.get("segments"), list):
                    raise PromptAssistantError("续写或分段修改需要有效的AIPM时间轴缓存")
                base_package = candidate
                if (operation == "append"
                        and candidate.get("generation_status") == "interrupted"
                        and candidate.get("aipm_operation") == "append"):
                    base_count = max(0, int(candidate.get("append_base_count") or 0))
                    requested_count = max(1, int(candidate.get("append_requested_count") or segment_count))
                    base_package = copy.deepcopy(candidate)
                    base_package["segments"] = copy.deepcopy(candidate["segments"][:base_count])
                    base_package["segment_count"] = base_count
                    previous = copy.deepcopy(candidate)
                    previous["segments"] = copy.deepcopy(candidate["segments"][base_count:])
                    previous["segment_count"] = requested_count
                    segment_count = requested_count
            if modification:
                if not isinstance(candidate, dict) or not candidate.get("video_prompt"):
                    raise PromptAssistantError("没有可用于修改的上次有效结果")
                previous = candidate if operation == "rewrite" else None
            elif isinstance(candidate, dict) and candidate.get("generation_status") == "interrupted":
                previous = candidate

        asset_manifest = parse_reference_asset_manifest(参考素材清单JSON)
        image_assets = [item for item in asset_manifest if item.get("media_type") == "image"]
        video_assets = [item for item in asset_manifest if item.get("media_type") == "video"]
        audio_assets = [item for item in asset_manifest if item.get("media_type") == "audio"]
        encoded_images = []
        image_references = (image1, image2, image3, image4, image5, image6, image7, image8, image9)
        video_references = (video1, video2, video3)
        audio_references = (audio1, audio2, audio3)
        for reference in image_references:
            remaining = 9 - len(encoded_images)
            encoded_images.extend(encode_image_batch(reference, limit=remaining))
            if len(encoded_images) >= 9:
                break
        if len(image_assets) < len(encoded_images):
            raise PromptAssistantError("参考图片没有稳定的本地素材地址；请直接连接Load Image文件加载节点")
        connected_video_count = sum(reference is not None for reference in video_references)
        connected_audio_count = sum(reference is not None for reference in audio_references)
        if connected_video_count and len(video_assets) < connected_video_count:
            raise PromptAssistantError("参考视频没有稳定的本地素材地址；请直接连接Load Video文件加载节点")
        if connected_audio_count and len(audio_assets) < connected_audio_count:
            raise PromptAssistantError("参考声音没有稳定的本地素材地址；请直接连接Load Audio文件加载节点")
        reference_profiles, cache_hits = ReferenceAnalysisPipeline.analyze_images(
            str(远程服务地址), str(模型名称 or "").strip(), encoded_images, idea,
        ) if encoded_images else ([], 0)
        if base_package and not reference_profiles:
            cached_profiles = base_package.get("reference_profiles")
            if isinstance(cached_profiles, list):
                reference_profiles = copy.deepcopy(cached_profiles)
                cache_hits = len(reference_profiles)
        for index, profile_item in enumerate(reference_profiles):
            if index < len(image_assets):
                profile_item.update(image_assets[index])
        # AIPM currently targets one H3 family; the separate generation-mode
        # widget owns the keyframe vs multimodal distinction.  Normalize old
        # persisted profile labels without changing their chosen mode.
        profile = "MiniMax H3"
        mode = self._resolve_mode(profile, str(生成模式), len(reference_profiles), bool(connected_video_count), bool(connected_audio_count))
        if operation == "append" and base_package:
            reuse_append_global_images(reference_profiles, base_package, mode)
        if mode != "h3_ref2va" and (connected_video_count or connected_audio_count):
            raise PromptAssistantError("只有多模态模式接受视频或声音参考；其他模式仅按顺序绑定参考图片")
        if mode == "h3_fl2va" and len(reference_profiles) > 2:
            raise PromptAssistantError("MiniMax H3 FL2VA 最多接收两张图片：首帧与尾帧")
        if mode == "h3_fl2va" and len(reference_profiles) != 2:
            raise PromptAssistantError("首尾帧模式必须正好连接两张图片，并按输入顺序作为首帧、尾帧")
        if mode in {"h3_i2va", "h3_l2va"} and len(reference_profiles) != 1:
            label = "I2VA 首帧" if mode == "h3_i2va" else "L2VA 尾帧"
            raise PromptAssistantError(f"MiniMax H3 {label} 模式必须正好连接一张图片")
        if mode == "h3_ref2va" and connected_audio_count and not reference_profiles and not connected_video_count:
            raise PromptAssistantError("MiniMax H3 Ref2VA 不能只输入声音，至少还需要图片或视频参考")
        skill_id, skill = load_prompt_skill(profile, mode)
        effective_count = 1 if operation == "revise_segment" else segment_count
        effective_duration = duration_seconds
        if operation == "revise_segment" and base_package:
            target = next((item for item in base_package.get("segments", [])
                           if str(item.get("segment_id") or "") == target_segment_id), None)
            if not target:
                raise PromptAssistantError("请选择有效的修改目标分段")
            effective_duration = max(4, min(30, int(round(float(target.get("duration") or duration_seconds)))))
        return self.generate_timeline_package(
            service_url=str(远程服务地址), service_model=str(模型名称 or "").strip(),
            profile=profile, mode=mode, idea=idea, duration_seconds=effective_duration,
            segment_count=effective_count, aspect_ratio=str(构图比例),
            requested_language=str(提示词语言), skill_id=skill_id, skill=skill,
            reference_profiles=reference_profiles, cache_hits=cache_hits,
            has_video=connected_video_count, has_audio=connected_audio_count,
            previous=previous, modification=modification,
            video_assets=video_assets, audio_assets=audio_assets,
            operation=operation, base_package=base_package,
            target_segment_id=target_segment_id,
        )

        # Legacy monolithic synthesis retained temporarily below for source
        # comparison during the v2 rollout. The v2 timeline pipeline returns
        # above and locally assembles the final package.
        context = {
            "task": "按修改意见优化上次视频提示词" if previous else "生成可直接用于目标视频模型的专业提示词",
            "idea": idea, "target_video_model": profile, "resolved_mode": mode,
            "duration_seconds": duration_seconds, "duration": duration_label,
            "timeline_end": f"00:{duration_seconds:02d}.000",
            "aspect_ratio": 构图比例, "language": 提示词语言,
            "prompt_dialect": VIDEO_PROMPT_DIALECTS.get(profile, VIDEO_PROMPT_DIALECTS["中文自然语言视频模型（通用）"]),
            "professional_skill_id": skill_id, "professional_skill": skill,
            "reference_image_count": len(reference_profiles), "reference_visual_profiles": reference_profiles,
            "has_video_reference": video1 is not None, "has_audio_reference": audio1 is not None,
            "reference_tags": {
                "images": [f"<Picture {i + 1}>" for i in range(len(reference_profiles))],
                "video": ["<Video 1>"] if video1 is not None else [],
                "audio": ["<Audio 1>"] if audio1 is not None else [],
            },
            "previous_result": previous, "modification_request": modification if previous else "",
            "hard_rules": [
                "MiniMax H3 的官方 Context-IR 字段名、控制标记、任务类型和保留关系枚举保持英文；字段正文严格使用用户选择的提示词语言；对白、歌词和画面内文字保持原文",
                f"目标视频的精确总时长是 {duration_seconds} 秒；所有镜头时间必须位于 0.000 至 {duration_seconds}.000 秒内，最终动作和声音必须在 {duration_seconds}.000 秒落定；不得自行改成 5 秒或其他时长",
                "按开场状态、触发、动作阶段、表演反应、镜头响应、结束落点的因果顺序设计",
                "人物镜头必须写可见的眼神、呼吸、姿态、细微表情或反应，不用抽象情绪词代替表演",
                "声音提示词区分对白、环境声、拟音和音乐；没有音乐时明确写无非剧情音乐",
                "每个参考只继承被指定或可见且有用的事实，禁止复制无关背景、姿势和构图",
                "不得输出采样器、步数、CFG 或服务商私有参数",
                "video_prompt 必须匹配 professional_skill 为当前模式规定的官方 Base 三字段或 Ref2VA 六段格式，禁止九段中文方括号标签",
                "只输出 schema 要求的 JSON 对象",
            ],
        }
        payload = {
            "model": str(模型名称 or "").strip(),
            "messages": [
                {"role": "system", "content": (
                    "你是专业影视导演和视频生成提示词设计师。完整执行 professional_skill，把简单描述转化为可拍摄、可生成、时序清楚的提示词。"
                    "若用户选择中文，只有 MiniMax H3 官方字段名、控制标签、任务类型和保留关系枚举使用英文，所有描述正文必须使用中文。"
                    "只输出合法 JSON。"
                )},
                {"role": "user", "content": [{"type": "text", "text": json.dumps(context, ensure_ascii=False)}]},
            ],
            "temperature": 0.25, "max_tokens": 4200, "cache_prompt": False,
            "response_format": self.response_format(),
            "chat_template_kwargs": {"enable_thinking": False},
        }
        generated, response = OpenAICompatibleClient.request_object(
            远程服务地址, payload, "视频提示词生成",
            validator=lambda result: self.validate_generated_language(result, str(提示词语言)),
        )
        package = {
            "schema": "aipm_video_prompt", "version": "1.0", "prompt_skill_id": skill_id,
            "revision": int(previous.get("revision") or 1) + 1 if previous else 1,
            "modification_request": modification if previous else "", "target_model": profile,
            "generation_mode": mode, "duration": duration_seconds,
            "duration_label": duration_label, "aspect_ratio": 构图比例,
            "prompt_language": "en" if 提示词语言 == "English" else "zh-CN",
            "reference_count": len(reference_profiles) + int(video1 is not None) + int(audio1 is not None),
            "reference_profiles": reference_profiles, "reference_analysis_cache_hits": cache_hits,
            "processing_strategy": "per-image-analysis-then-text-synthesis",
        }
        for field in ("negative_prompt", "audio_prompt", "start_state", "end_state", "camera_plan", "performance_plan", "visual_design"):
            package[field] = str(generated.get(field) or "").strip()
        for field in ("motion_phases", "reference_usage", "continuity_guards"):
            package[field] = generated.get(field) if isinstance(generated.get(field), list) else []
        package["video_prompt"] = str(generated.get("video_prompt") or "").strip()
        if not package["video_prompt"]:
            raise PromptAssistantError("远程服务没有返回 MiniMax H3 视频提示词")
        package["usage"] = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        cine_timeline, cine_timeline_json = self._canonical_timeline(package)
        return {"ui": {"text": [package["video_prompt"], package["negative_prompt"], cine_timeline_json]},
                "result": (
                    cine_timeline, package["video_prompt"], package["negative_prompt"],
                    package["audio_prompt"], cine_timeline_json,
                )}


# Keep the completed video implementation before defining the image node below.
AIPMVideoPromptCore = AIPMVideoPrompt


def resolve_refinement_profile(prompt_type: str, target_model: str) -> str:
    if str(target_model) in PROMPT_SKILL_BY_PROFILE or str(target_model) in VIDEO_PROMPT_SKILL_BY_PROFILE:
        return str(target_model)
    value = str(target_model or "").lower()
    if str(prompt_type) == "生视频提示词" or any(key in value for key in ("h3", "video", "wan", "ltx", "hunyuanvideo")):
        if "h3" in value or "minimax" in value: return "MiniMax H3"
        if "wan" in value: return "Wan 系列"
        if "ltx" in value: return "LTX-Video 系列"
        if "hunyuan" in value: return "HunyuanVideo 系列"
        return "中文自然语言视频模型（通用）"
    routes = (
        (("krea",), "Krea 2 / Krea 2 Turbo 系列"), (("flux",), "FLUX.1 / FLUX.2 系列"),
        (("pony",), "Pony Diffusion / Pony 系模型"), (("illustrious", "noobai"), "Illustrious / NoobAI 系模型"),
        (("sdxl", "stable diffusion xl"), "Stable Diffusion XL 基础模型"),
        (("sd3", "stable diffusion 3"), "Stable Diffusion 3 / 3.5"),
        (("sd1", "stable diffusion 1"), "Stable Diffusion 1.x"),
        (("qwen image", "qwen-image"), "Qwen Image 系列"), (("z-image", "zimage"), "Z-Image 系列"),
        (("hunyuanimage", "hunyuan image"), "HunyuanImage 系列"), (("kolors",), "Kolors 系列"),
    )
    for keys, profile in routes:
        if any(key in value for key in keys): return profile
    return "自动判断 / 通用（推荐）"


class AIPMPromptRefinement:
    CATEGORY = CATEGORY
    FUNCTION = "refine"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("细化后提示词", "细化后负向提示词", "问题诊断", "修改摘要", "完整结果 JSON")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原始提示词": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
            "遇到的问题与修改目标": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
            "提示词类型": (["自动判断", "生图提示词", "生视频提示词"], {"default": "自动判断"}),
            "目标模型": (REFINEMENT_MODEL_PROFILES, {"default": "自动判断 / 通用（推荐）"}),
            "必须保留的内容": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "远程服务地址": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
            "模型名称": ("STRING", {"default": "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf"}),
            "输出语言": (["跟随原提示词（推荐）", "中文", "English"],),
        }, "optional": {
            "上次结果JSON": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
        }}

    @staticmethod
    def response_format() -> dict[str, Any]:
        fields = {
            "refined_prompt": {"type": "string"}, "negative_prompt": {"type": "string"},
            "diagnosis": {"type": "array", "items": {"type": "string"}},
            "modification_summary": {"type": "array", "items": {"type": "string"}},
            "preserved_elements": {"type": "array", "items": {"type": "string"}},
            "workflow_recommendations": {"type": "array", "items": {"type": "string"}},
        }
        return {"type": "json_schema", "json_schema": {"name": "prompt_refinement_result", "strict": True,
            "schema": {"type": "object", "properties": fields, "required": list(fields)}}}

    @staticmethod
    def _cached_result(raw: str):
        try: value = json.loads(str(raw or ""))
        except json.JSONDecodeError as exc: raise PromptAssistantError("已保存的细化结果无效，请清空后重新执行") from exc
        if not isinstance(value, dict) or value.get("schema") != "aipm_prompt_refinement" or not value.get("refined_prompt"):
            raise PromptAssistantError("已保存的细化结果无效，请清空后重新执行")
        text = json.dumps(value, ensure_ascii=False, indent=2)
        return {"ui": {"text": [value["refined_prompt"], value.get("negative_prompt", ""), text]}, "result": (
            value["refined_prompt"], value.get("negative_prompt", ""), value.get("diagnosis_text", ""),
            value.get("modification_summary_text", ""), text)}

    def refine(self, 原始提示词, 遇到的问题与修改目标, 提示词类型, 目标模型, 必须保留的内容,
               远程服务地址, 模型名称, 输出语言, 上次结果JSON=""):
        original, issue, cached = map(lambda value: str(value or "").strip(), (原始提示词, 遇到的问题与修改目标, 上次结果JSON))
        marker, revision_marker = "__AIPM_RUN_V1__", "__AIPM_REVISION_V1__"
        independent, previous = issue.startswith(marker) or issue.startswith(revision_marker), None
        if issue.startswith(marker): issue = issue[len(marker):].strip()
        elif issue.startswith(revision_marker):
            try:
                payload = json.loads(issue[len(revision_marker):]); issue = str(payload.get("instruction") or "").strip()
                cached = str(payload.get("previous_result") or cached).strip(); previous = json.loads(cached) if cached else None
            except (json.JSONDecodeError, AttributeError) as exc: raise PromptAssistantError("继续细化请求无效，请重新执行") from exc
        if not original: raise PromptAssistantError("请先填写原始提示词")
        if not issue: raise PromptAssistantError("请填写遇到的问题与修改目标")
        if not independent:
            if cached: return self._cached_result(cached)
            raise PromptAssistantError("AIPM不会随主工作流调用远程AI。请点击节点上的“分析并细化”按钮。")
        profile = resolve_refinement_profile(提示词类型, 目标模型)
        base_skill_id, base_skill = load_prompt_skill(profile)
        refinement_skill_id, refinement_skill = load_prompt_skill("__refinement__")
        language_rule = {"中文": "可执行提示词与诊断使用简体中文，固定标签保持原样。", "English": "Write executable prompts in English."}.get(str(输出语言), "保持原提示词的主要语言和固定语法。")
        context = {"task": "诊断并最小幅度细化已有提示词", "original_prompt": original,
            "observed_problem_and_goal": issue, "prompt_type": 提示词类型, "target_model": 目标模型,
            "resolved_profile": profile, "must_preserve": str(必须保留的内容 or "").strip(),
            "previous_refinement": previous, "language_rule": language_rule,
            "base_prompt_skill_id": base_skill_id, "base_prompt_skill": base_skill,
            "refinement_skill_id": refinement_skill_id, "refinement_skill": refinement_skill}
        payload = {"model": str(模型名称 or "").strip(), "messages": [
            {"role": "system", "content": "你是AI生成提示词诊断与细化专家。只做解决已报告问题所需的最小修改，保留无关内容。无法靠提示词解决的问题必须写入诊断和工作流建议。只输出schema JSON。"},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            "temperature": 0.2, "max_tokens": 1800, "cache_prompt": False,
            "response_format": self.response_format(), "chat_template_kwargs": {"enable_thinking": False}}
        def validate(value):
            if not str(value.get("refined_prompt") or "").strip(): raise PromptAssistantError("refined_prompt 不能为空")
        generated, response = OpenAICompatibleClient.request_object(远程服务地址, payload, "提示词诊断与细化", validator=validate)
        diagnosis = [str(x).strip() for x in generated.get("diagnosis", []) if str(x).strip()]
        summary = [str(x).strip() for x in generated.get("modification_summary", []) if str(x).strip()]
        package = {"schema": "aipm_prompt_refinement", "version": "1.0", "prompt_type": 提示词类型,
            "target_model": 目标模型, "resolved_profile": profile, "base_prompt_skill_id": base_skill_id,
            "refinement_skill_id": refinement_skill_id, "original_prompt": original, "problem_and_goal": issue,
            "refined_prompt": str(generated.get("refined_prompt") or "").strip(),
            "negative_prompt": str(generated.get("negative_prompt") or "").strip(),
            "diagnosis": diagnosis, "diagnosis_text": "\n".join(diagnosis), "modification_summary": summary,
            "modification_summary_text": "\n".join(summary), "preserved_elements": generated.get("preserved_elements", []),
            "workflow_recommendations": generated.get("workflow_recommendations", []),
            "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {}}
        raw = json.dumps(package, ensure_ascii=False, indent=2)
        return {"ui": {"text": [package["refined_prompt"], package["negative_prompt"], raw]}, "result": (
            package["refined_prompt"], package["negative_prompt"], package["diagnosis_text"], package["modification_summary_text"], raw)}


class AIPMImagePrompt:
    CATEGORY = CATEGORY
    FUNCTION = "generate"
    OUTPUT_NODE = True
    RETURN_TYPES = ("AIPM_IMAGE_PROMPT", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("提示词数据", "正向提示词", "负向提示词", "完整结果 JSON")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "画面描述与创作要求": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "远程服务地址": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "模型名称": ("STRING", {"default": "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf"}),
                "目标生图模型": (IMAGE_MODEL_PROFILES, {"default": "Krea 2 / Krea 2 Turbo 文生图"}),
                "画面比例": (["自动", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],),
                "提示词语言": (["自动适配（推荐）", "中文", "English"],),
                "参考图用途": (["多参考改图", "仅分析参考"], {"default": "多参考改图"}),
            },
            "optional": {
                **{f"image{index}": ("IMAGE",) for index in range(1, 10)},
                "修改意见": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "上次结果JSON": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False}),
                "参考素材清单JSON": ("STRING", {"default": "[]", "multiline": True, "dynamicPrompts": False}),
            },
        }

    @staticmethod
    def response_format() -> dict[str, Any]:
        return {"type": "json_schema", "json_schema": {"name": "image_prompt_result", "strict": True, "schema": {
            "type": "object", "properties": {
                "positive_prompt": {"type": "string"}, "negative_prompt": {"type": "string"},
                "composition_notes": {"type": "string"},
                "reference_usage": {"type": "array", "items": {"type": "string"}},
                "quality_features": {"type": "array", "items": {"type": "string"}},
                "emphasis_features": {"type": "array", "items": {"type": "string"}},
            }, "required": ["positive_prompt", "negative_prompt", "composition_notes", "reference_usage", "quality_features", "emphasis_features"],
        }}}

    @staticmethod
    def compile_reference_binding_prompt(
        reference_profiles: list[dict[str, Any]],
        reference_usage: list[str],
        prompt_language: str,
    ) -> str:
        """Preserve ordered sampler-image semantics in the executable prompt."""
        if not reference_profiles:
            return ""
        usage_values = [str(value).strip() for value in reference_usage if str(value).strip()]
        bindings: list[str] = []
        for index, _profile in enumerate(reference_profiles, start=1):
            picture_token = f"<Picture {index}>"
            image_token = f"image{index}"
            matched = next((value for value in usage_values if picture_token in value), "")
            # Do not leak legacy Chinese reference definitions into an
            # English-native model prompt. Fresh responses are validated too,
            # while this remains a safeguard for cached/older packages.
            if prompt_language != "zh-CN" and re.search(r"[\u3400-\u9fff]", matched):
                matched = ""
            if prompt_language == "zh-CN":
                replacement = f"{image_token}（参考图{index}）"
                detail = matched.replace(picture_token, replacement) if matched else (
                    f"{replacement}必须作为第{index}个已连接参考图，继承用户为它指定的主体、服装、姿态或场景属性"
                )
            else:
                replacement = f"{image_token} (reference image {index})"
                detail = matched.replace(picture_token, replacement) if matched else (
                    f"{replacement} is the {index}th connected reference and must preserve its user-assigned subject, clothing, pose, or scene role"
                )
            bindings.append(detail.rstrip("。.;；"))
        if prompt_language == "zh-CN":
            return "参考图绑定（必须与采样器参考输入顺序一致）：" + "；".join(bindings) + "。"
        return "Reference bindings (must match sampler reference-input order): " + "; ".join(bindings) + "."

    @staticmethod
    def validate_generated_language(candidate: dict[str, Any], prompt_language: str) -> None:
        """Enforce the executable language contract before local assembly."""
        if prompt_language not in {"en", "en-tags"}:
            return
        executable_values = [
            str(candidate.get("positive_prompt") or ""),
            str(candidate.get("negative_prompt") or ""),
        ]
        reference_usage = candidate.get("reference_usage")
        if isinstance(reference_usage, list):
            executable_values.extend(str(value or "") for value in reference_usage)
        if any(re.search(r"[\u3400-\u9fff]", value) for value in executable_values):
            raise PromptAssistantError(
                "当前目标模型要求英文可执行提示词；positive_prompt、negative_prompt 和 reference_usage 不得包含中文"
            )

    @staticmethod
    def validate_reference_usage(candidate: dict[str, Any], reference_count: int, reference_mode: str) -> None:
        """Require an explicit one-to-one role for every executable reference input."""
        if reference_count <= 0 or reference_mode != "多参考改图":
            return
        usage = candidate.get("reference_usage")
        if not isinstance(usage, list):
            raise PromptAssistantError("多参考改图必须返回 reference_usage 数组")
        joined = "\n".join(str(value or "") for value in usage)
        missing = [f"<Picture {index}>" for index in range(1, reference_count + 1)
                   if f"<Picture {index}>" not in joined]
        if missing:
            raise PromptAssistantError(f"多参考职责缺失：{', '.join(missing)}")

    @staticmethod
    def validate_anima_prompt(candidate: dict[str, Any], idea: str, model_profile: str) -> None:
        """Enforce Anima-specific framing contracts that a prose skill alone may miss."""
        if model_profile != "Anima 系列":
            return
        positive = str(candidate.get("positive_prompt") or "").lower()
        negative = str(candidate.get("negative_prompt") or "").lower()
        weights = re.findall(r"\([^()]+:\s*1(?:\.\d+)?\)", positive)
        if len(weights) > 3:
            raise PromptAssistantError("Anima 正向提示词最多只能加权 3 个决定性概念，避免局部细节抢占构图")
        full_body_requested = bool(re.search(
            r"全身(?:图|像)?|完整人物|从头到脚|脚(?:部)?(?:要|需|必须)?看到|"
            r"\bfull[ -]?body\b|\bhead[ -]?to[ -]?toe\b|\bfull[ -]?length\b",
            str(idea or ""), re.IGNORECASE,
        ))
        if not full_body_requested:
            return
        required_groups = {
            "全身主景别": ["full body"],
            "头脚完整性": ["head-to-toe", "head to toe", "entire figure", "complete body", "full-length", "full length"],
            "双脚可见": ["both feet visible", "feet fully visible"],
            "远景距离": ["long shot", "wide shot", "full-length", "full length"],
            "画内边界": ["clear space", "inside the frame", "fully in frame", "without any crop", "without cropping", "no part of the body outside"],
        }
        missing = [name for name, choices in required_groups.items()
                   if not any(choice in positive for choice in choices)]
        conflicts = [term for term in ("upper body", "cowboy shot", "medium shot", "close-up", "close up")
                     if term in positive]
        negative_groups = {
            "裁切": ["cropped", "accidental crop"],
            "脚部出框": ["cropped feet", "feet out of frame"],
            "竞争景别": ["upper body", "close-up", "close up"],
        }
        missing_negative = [name for name, choices in negative_groups.items()
                            if not any(choice in negative for choice in choices)]
        if missing or conflicts or missing_negative:
            details = []
            if missing: details.append("正向缺少" + "、".join(missing))
            if conflicts: details.append("正向包含冲突景别：" + ", ".join(conflicts))
            if missing_negative: details.append("负向缺少" + "、".join(missing_negative))
            raise PromptAssistantError("Anima 全身构图契约不完整：" + "；".join(details))

    @classmethod
    def validate_generated_result(cls, candidate: dict[str, Any], prompt_language: str,
                                  reference_count: int, reference_mode: str,
                                  idea: str = "", model_profile: str = "") -> None:
        cls.validate_generated_language(candidate, prompt_language)
        cls.validate_reference_usage(candidate, reference_count, reference_mode)
        cls.validate_anima_prompt(candidate, idea, model_profile)

    def generate(self, 画面描述与创作要求, 远程服务地址, 模型名称, 目标生图模型, 画面比例,
                 提示词语言, image1=None,
                 修改意见="", 上次结果JSON="", 参考素材清单JSON="[]",
                 image2=None, image3=None, image4=None, image5=None, image6=None,
                 image7=None, image8=None, image9=None, 参考图用途="多参考改图"):
        idea = str(画面描述与创作要求 or "").strip()
        if not idea:
            raise PromptAssistantError("请先填写画面描述与创作要求")
        previous = None
        modification = str(修改意见 or "").strip()
        previous_json = str(上次结果JSON or "").strip()
        run_marker = "__AIPM_RUN_V1__"
        independent_execution = modification.startswith(run_marker)
        if independent_execution:
            modification = ""
        revision_marker = "__AIPM_REVISION_V1__"
        if modification.startswith(revision_marker):
            independent_execution = True
            try:
                revision_payload = json.loads(modification[len(revision_marker):])
                modification = str(revision_payload.get("instruction") or "").strip()
                previous_json = str(revision_payload.get("previous_result") or "").strip()
            except (json.JSONDecodeError, AttributeError) as exc:
                raise PromptAssistantError("修改请求数据无效，请重新生成后再优化") from exc
        # Migrate the legacy widget ordering where the serialized cached result
        # was restored into `修改意见` after `参考图用途` was added. A full AIPM
        # result is cache data, not user-authored revision text.
        if modification and not independent_execution:
            try:
                shifted_cache = json.loads(modification)
            except json.JSONDecodeError:
                shifted_cache = None
            if (isinstance(shifted_cache, dict)
                    and shifted_cache.get("schema") == "aipm_image_prompt"
                    and shifted_cache.get("positive_prompt")):
                if not previous_json:
                    previous_json = modification
                modification = ""
        if previous_json and not modification and not independent_execution:
            try:
                stored = json.loads(previous_json)
            except json.JSONDecodeError as exc:
                raise PromptAssistantError("已保存的生图提示词结果无效，请清空后重新生成") from exc
            if (not isinstance(stored, dict)
                    or stored.get("schema") != "aipm_image_prompt"
                    or not stored.get("positive_prompt")):
                raise PromptAssistantError("已保存的生图提示词结果无效，请清空后重新生成")
            raw = json.dumps(stored, ensure_ascii=False, indent=2)
            return {
                "ui": {"text": [str(stored.get("positive_prompt") or ""), str(stored.get("negative_prompt") or ""), raw]},
                "result": (
                    stored, str(stored.get("positive_prompt") or ""),
                    str(stored.get("negative_prompt") or ""), raw,
                ),
            }
        if not independent_execution:
            raise PromptAssistantError("AIPM不会随主工作流调用远程AI。请先点击节点上的“生成 / 重新创作”按钮生成并缓存提示词。")
        if modification and previous_json:
            try:
                candidate = json.loads(previous_json)
            except json.JSONDecodeError as exc:
                raise PromptAssistantError("没有可用于修改的上次有效结果，请先生成一次提示词") from exc
            if not isinstance(candidate, dict) or not candidate.get("positive_prompt"):
                raise PromptAssistantError("没有可用于修改的上次有效结果，请先生成一次提示词")
            previous = {
                "positive_prompt": str(candidate.get("positive_prompt") or ""),
                "negative_prompt": str(candidate.get("negative_prompt") or ""),
                "composition_notes": str(candidate.get("composition_notes") or ""),
                "reference_usage": candidate.get("reference_usage") if isinstance(candidate.get("reference_usage"), list) else [],
                "revision": int(candidate.get("revision") or 1),
            }
        asset_manifest = parse_reference_asset_manifest(参考素材清单JSON)
        image_assets = [item for item in asset_manifest if item.get("media_type") == "image"]
        # Each port may itself carry an IMAGE batch; the global cap remains
        # nine references to bound remote analysis cost and context.
        encoded_images = []
        for reference in (image1, image2, image3, image4, image5, image6, image7, image8, image9):
            remaining = 9 - len(encoded_images)
            if remaining <= 0:
                break
            encoded_images.extend(encode_image_batch(reference, limit=remaining))
        if len(image_assets) < len(encoded_images):
            raise PromptAssistantError("参考图片没有稳定的本地素材地址；请直接连接Load Image文件加载节点")
        reference_profiles, cache_hits = ReferenceAnalysisPipeline.analyze_images(
            str(远程服务地址), str(模型名称 or "").strip(), encoded_images,
            idea,
        ) if encoded_images else ([], 0)
        for index, profile_item in enumerate(reference_profiles):
            if index < len(image_assets):
                profile_item.update(image_assets[index])
        reference_mode = str(参考图用途 or "多参考改图")
        model_profile = str(目标生图模型 or "自动判断 / 通用（推荐）")
        prompt_skill_id, prompt_skill = load_prompt_skill(model_profile)
        native_quality_anchor = NATIVE_QUALITY_ANCHORS.get(model_profile, "")
        numeric_weight_skills = {"aipm-sd-weighted", "aipm-pony-booru", "aipm-illustrious-booru"}
        emphasis_policy = (
            "优先用清楚语序表达重点；仅当前工作流支持且确有必要时使用少量温和权重，不强制加权。"
            if prompt_skill_id in numeric_weight_skills else
            "禁止数字权重；用清楚主句突出任务重点，不强加对焦或光线设计。"
        )
        resolved_language = resolve_prompt_language(model_profile, str(提示词语言))
        if resolved_language == "zh-CN":
            language_rule = (
                "positive_prompt、negative_prompt、reference_usage 的每一项以及 composition_notes "
                "全部使用简体中文；模型要求的固定英文标记、质量标签和 imageN/<Picture N> 引用标记保持原样。"
            )
        elif resolved_language == "en-tags":
            language_rule = (
                "positive_prompt 与 negative_prompt 使用目标模型原生英文标签语法；"
                "reference_usage 的每一项使用英文自然语言并保留 <Picture N> 标记；"
                "只有 composition_notes 可以使用简体中文。"
            )
        else:
            language_rule = (
                "positive_prompt、negative_prompt 以及 reference_usage 的每一项都必须使用完整准确的英文；"
                "composition_notes 可以使用简体中文。"
            )
        context = {
            "task": "在上次结果基础上按修改意见定向优化提示词" if previous else "为指定生图模型编写可直接执行的专业提示词",
            "idea": idea,
            "target_image_model": model_profile, "aspect_ratio": 画面比例,
            "prompt_dialect": IMAGE_PROMPT_DIALECTS.get(model_profile, IMAGE_PROMPT_DIALECTS["自动判断 / 通用（推荐）"]),
            "professional_skill_id": prompt_skill_id,
            "professional_skill": prompt_skill,
            "mandatory_professional_contract": {
                "native_quality_anchor": (
                    f"positive_prompt 必须以此模型原生质量锚点开头，保持原样：{native_quality_anchor}"
                    if native_quality_anchor else
                    "此模型不强制固定质量口令；仅当专业技能或目标 checkpoint 模型卡明确要求时使用质量标签，禁止无依据堆叠 score、masterpiece 或 8K。"
                ),
                "emphasis": emphasis_policy,
                "quality": "只补充任务相关、可见的画质特征，不凑数量，不改变已有参考内容；极简画面可以不补充。",
                "coverage": "按任务需要选择主体、动作、构图、光色和材质；无关项省略，不为覆盖清单制造内容。",
                "audit": "quality_features 和 emphasis_features 必须逐项列出已实际写进 positive_prompt 的短语；不得列出正文中不存在的项目。",
            },
            "modification_request": modification if previous else "",
            "previous_result": previous,
            "reference_roles": idea,
            "reference_purpose": reference_mode if reference_profiles else "无参考图",
            "reference_image_count": len(reference_profiles),
            "reference_visual_profiles": reference_profiles,
            "language_request": 提示词语言, "resolved_prompt_language": resolved_language, "rules": [
                language_rule,
                "组织主体身份、五官、服装、姿态、构图、镜头、光线、材质、色彩和环境",
                "有参考图时逐图分析可见事实，使用 <Picture 1>、<Picture 2> 等从一开始编号的标记",
                "不臆造看不清的身份事实，不把分析过程写进正向提示词",
                "针对目标生图模型优化表达，但不添加该模型不支持的参数语法",
                "修改模式下只改变修改意见明确涉及的内容，其余人物、场景、构图和参考关系保持稳定",
                "依据professional_skill补足影响执行的视觉细节；简单任务不为扩写而新增对象、材质或镜头。保持用户主体、数量、动作和风格不变",
                "遵守本次任务与输出结构；quality_features、emphasis_features只列正文已使用的相关短语，可为空，禁止为凑数扩写",
            ],
        }
        # The synthesis request is deliberately text-only. Each image has
        # already been analyzed independently above, preventing visual-token
        # pressure from growing with the number of references.
        content: list[dict[str, Any]] = [{
            "type": "text", "text": json.dumps(context, ensure_ascii=False)
        }]
        payload = {
            "model": str(模型名称 or "").strip(),
            "messages": [
                {"role": "system", "content": "你是专业的 AI 生图提示词导演。必须完整执行用户消息中的 professional_skill，而不是简单改写画面描述。严格依据描述、参考图和修改意见，只输出 schema 要求的 JSON。修改任务不是重新创作，必须保留未被要求改变的内容。"},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3, "max_tokens": 1200, "cache_prompt": False,
            "response_format": self.response_format(),
            "chat_template_kwargs": {"enable_thinking": False},
        }
        result, response = OpenAICompatibleClient.request_object(
            远程服务地址,
            payload,
            "生图提示词生成",
            validator=lambda candidate: self.validate_generated_result(
                candidate, resolved_language, len(reference_profiles), reference_mode,
                idea, model_profile,
            ),
        )
        reference_usage = result.get("reference_usage") if isinstance(result.get("reference_usage"), list) else []
        reference_binding_prompt = (
            self.compile_reference_binding_prompt(reference_profiles, reference_usage, resolved_language)
            if reference_profiles and reference_mode == "多参考改图" else ""
        )
        positive_body = str(result.get("positive_prompt") or "").strip()
        positive_prompt = "\n".join(
            value for value in (reference_binding_prompt, positive_body) if value
        )
        package = {
            "schema": "aipm_image_prompt", "version": "1.0",
            "prompt_skill_id": prompt_skill_id,
            "native_quality_anchor": native_quality_anchor,
            "revision": (previous["revision"] + 1) if previous else 1,
            "modification_request": modification if previous else "",
            "target_model": str(目标生图模型 or ""), "aspect_ratio": 画面比例,
            "language_request": 提示词语言, "prompt_language": resolved_language,
            "reference_count": len(reference_profiles),
            "reference_mode": reference_mode if reference_profiles else "无参考图",
            "reference_profiles": reference_profiles,
            "reference_binding_prompt": reference_binding_prompt,
            "reference_binding_order": [
                {
                    "image_token": f"image{index + 1}",
                    "picture_token": str(profile.get("picture_id") or f"<Picture {index + 1}>"),
                    "asset_id": str(profile.get("asset_id") or ""),
                }
                for index, profile in enumerate(reference_profiles)
            ],
            "reference_analysis_cache_hits": cache_hits,
            "processing_strategy": "per-image-analysis-then-text-synthesis",
            "positive_prompt": positive_prompt,
            "negative_prompt": str(result.get("negative_prompt") or "").strip(),
            "composition_notes": str(result.get("composition_notes") or "").strip(),
            "reference_usage": reference_usage,
            "quality_features": result.get("quality_features") if isinstance(result.get("quality_features"), list) else [],
            "emphasis_features": result.get("emphasis_features") if isinstance(result.get("emphasis_features"), list) else [],
            "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
        }
        raw = json.dumps(package, ensure_ascii=False, indent=2)
        result = (package, package["positive_prompt"], package["negative_prompt"], raw)
        # OUTPUT_NODE alone makes the node independently queueable, but ComfyUI
        # only records/emits display output when a UI payload is returned. The
        # frontend generate button relies on that event to leave its running
        # state and present the generated prompts.
        return {
            "ui": {
                "text": [package["positive_prompt"], package["negative_prompt"], raw],
            },
            "result": result,
        }


class AIPMCineTimelineAdapter:
    """Convert an AIPM video package into CineTimeline's neutral timeline contract."""

    CATEGORY = CATEGORY
    FUNCTION = "convert"
    OUTPUT_NODE = True
    RETURN_TYPES = ("CINE_TIMELINE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("CineTimeline数据", "时间线JSON", "适配报告", "首段编译提示词")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词数据": ("AIPM_VIDEO_PROMPT",),
                "帧率": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "默认转场": (["cut", "motion_context", "tail_continuity", "dissolve", "fade", "match_cut"],),
            }
        }

    @staticmethod
    def _reference_record(reference_id: str, image_index: int, start: int, end: int,
                          scope: str, shot_id: str = "", suffix: str = "",
                          asset: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_id = re.sub(r"[^A-Za-z0-9_]+", "_", reference_id.strip("<> ")).strip("_")
        asset = asset if isinstance(asset, dict) else {}
        return {
            "reference_id": (clean_id or f"REFERENCE_{image_index + 1}") + suffix,
            "type": "character", "media_type": "image", "media_order": image_index + 1,
            "scope": scope, "shot_id": shot_id,
            "target_id": f"<Subject {image_index + 1}>",
            "asset_id": str(asset.get("asset_id") or ""),
            "filename": str(asset.get("filename") or ""),
            "subfolder": str(asset.get("subfolder") or ""),
            "storage_type": str(asset.get("storage_type") or "input"),
            "image_index": image_index, "start_frame": start, "end_frame": end,
            "strength": 1.0, "adapter": "auto", "priority": 1000 - image_index,
            "metadata": {
                "source": "AIPM", "provider_token": reference_id,
                "sha256": str(asset.get("sha256") or asset.get("image_sha256") or ""),
                "width": asset.get("width"), "height": asset.get("height"),
            },
        }

    def convert(self, 提示词数据: dict[str, Any], 帧率: int, 默认转场: str):
        package = copy.deepcopy(提示词数据)
        if not isinstance(package, dict) or package.get("schema") not in {
            "aipm_video_timeline", "aipm_video_prompt",
        }:
            raise PromptAssistantError("输入不是有效的AIPM视频提示词数据")
        source_segments = package.get("segments")
        if not isinstance(source_segments, list) or not source_segments:
            source_segments = [{
                "segment_id": "SEGMENT_001", "duration": package.get("default_segment_duration", 5),
                "prompt": package.get("video_prompt", ""),
                "timeline_local_prompt": package.get("video_prompt", ""),
                "compiled_prompt": package.get("video_prompt", ""),
                "negative_prompt": package.get("negative_prompt", ""),
                "reference_ids": [], "effective_reference_ids": [],
                "opening_state": "", "ending_state": "", "continuity_from_previous": "",
            }]
        fps = max(1, int(帧率))
        global_data = package.get("global") if isinstance(package.get("global"), dict) else {}
        global_prompt = str(global_data.get("prompt") or "")
        global_negative = str(global_data.get("negative_prompt") or package.get("negative_prompt") or "")
        shots: list[dict[str, Any]] = []
        cursor = 0
        frame_ranges: list[tuple[int, int]] = []
        for index, segment in enumerate(source_segments):
            duration = max(0.1, float(segment.get("duration") or package.get("default_segment_duration") or 5))
            frames = max(1, round(duration * fps))
            start, end = cursor, cursor + frames
            cursor = end
            frame_ranges.append((start, end))
            shot_id = str(segment.get("segment_id") or f"SEGMENT_{index + 1:03d}")
            local_prompt = str(
                segment.get("timeline_local_prompt") or segment.get("source_prompt")
                or segment.get("prompt") or segment.get("compiled_prompt") or ""
            )
            shots.append({
                "shot_id": shot_id, "start_frame": start, "end_frame": end,
                "title": str(segment.get("title") or ""),
                "local_prompt": local_prompt,
                "camera": "", "transition": "cut" if index == 0 else (
                    str(segment.get("transition") or 默认转场)
                    if str(segment.get("transition") or 默认转场) in {"cut", "motion_context"}
                    else str(默认转场)
                ),
                "metadata": {
                    "duration_seconds": frames / fps,
                    "start_state": str(segment.get("opening_state") or ""),
                    "end_state": str(segment.get("ending_state") or ""),
                    "handoff": str(segment.get("continuity_from_previous") or ""),
                    "dialogue_lines": segment.get("dialogue_lines") or [],
                    "aipm_source_prompt": str(segment.get("source_prompt") or segment.get("prompt") or ""),
                    "aipm_compiled_prompt": str(segment.get("compiled_prompt") or ""),
                    "continue_from_previous": False,
                    "continuity_handle_frames": 1,
                },
            })

        global_ids = [str(value) for value in global_data.get("reference_ids", [])]
        mode = str(package.get("generation_mode") or ("h3_ref2va" if global_ids else "text_to_video"))
        if mode != "h3_ref2va":
            global_ids = []
        profiles = package.get("reference_profiles") if isinstance(package.get("reference_profiles"), list) else []
        picture_index = {
            str(item.get("picture_id")): (index, item) for index, item in enumerate(profiles)
            if isinstance(item, dict) and item.get("picture_id")
        }
        references: list[dict[str, Any]] = []
        for reference_id, (image_index, asset) in picture_index.items():
            if reference_id in global_ids:
                references.append(self._reference_record(
                    reference_id, image_index, 0, cursor, "global", asset=asset,
                ))
                continue
            used = [
                index for index, segment in enumerate(source_segments)
                if reference_id in [str(value) for value in segment.get("effective_reference_ids", [])]
            ]
            for index in used:
                start, end = frame_ranges[index]
                shot_id = shots[index]["shot_id"]
                record = self._reference_record(
                    reference_id, image_index, start, end, "shot", shot_id,
                    f"_{shot_id}", asset,
                )
                if mode == "h3_fl2va":
                    record["type"] = "first_frame" if image_index == 0 else "last_frame"
                elif mode == "h3_keyframe":
                    planned = next((
                        item for item in source_segments[index].get("keyframe_bindings", [])
                        if isinstance(item, dict) and str(item.get("reference_id") or "") == reference_id
                    ), None)
                    last_index = max(1, len(profiles) - 1)
                    fallback_local = round(image_index * max(0, end - start - 1) / last_index)
                    local_frame = int(planned.get("local_frame", fallback_local)) if planned else fallback_local
                    local_frame = max(0, min(max(0, end - start - 1), local_frame))
                    frame = start + local_frame
                    record["keyframe_frame"] = frame
                    record["keyframe_local_frame"] = local_frame
                    record["keyframe_placement_reason"] = str((planned or {}).get("placement_reason") or "")
                    record["keyframe_role"] = (
                        "first" if image_index == 0 else
                        "last" if image_index == len(profiles) - 1 else "guide"
                    )
                    record["type"] = (
                        "first_frame" if image_index == 0 else
                        "last_frame" if image_index == len(profiles) - 1 else "guide"
                    )
                references.append(record)

        media_assets = package.get("media_assets") if isinstance(package.get("media_assets"), dict) else {}
        for media_type, key, token_name in (
            ("video", "videos", "Video"), ("audio", "audios", "Audio"),
        ):
            asset_values = media_assets.get(key) if isinstance(media_assets.get(key), list) else []
            for media_index, asset in enumerate(asset_values):
                if not isinstance(asset, dict) or not str(asset.get("asset_id") or "").strip():
                    continue
                token = f"<{token_name} {media_index + 1}>"
                used = []
                for index, segment in enumerate(source_segments):
                    ids = [str(value) for value in segment.get("effective_reference_ids", [])]
                    prompt_text = "\n".join(str(segment.get(field) or "") for field in (
                        "source_prompt", "timeline_local_prompt", "compiled_prompt",
                    ))
                    if token in ids or token in prompt_text:
                        used.append(index)
                scopes = [("global", "", 0, cursor)] if token in global_ids or len(used) == len(source_segments) else [
                    ("shot", shots[index]["shot_id"], frame_ranges[index][0], frame_ranges[index][1])
                    for index in used
                ]
                for scope, shot_id, start, end in scopes:
                    references.append({
                        "reference_id": f"{token_name.upper()}_{media_index + 1}"
                        + (f"_{shot_id}" if shot_id else ""),
                        "type": media_type, "media_type": media_type,
                        "media_order": media_index + 1, "scope": scope, "shot_id": shot_id,
                        "target_id": token, "asset_id": str(asset.get("asset_id") or ""),
                        "filename": str(asset.get("filename") or ""),
                        "subfolder": str(asset.get("subfolder") or ""),
                        "storage_type": str(asset.get("storage_type") or "input"),
                        "start_frame": start, "end_frame": end, "strength": 1.0,
                        "adapter": "auto", "priority": 900 - media_index,
                        "metadata": {
                            "source": "AIPM", "provider_token": token,
                            "sha256": str(asset.get("sha256") or ""),
                            "duration": asset.get("duration"),
                        },
                    })

        timeline = {
            "schema": "cine_keyframe_timeline" if mode == "h3_keyframe" else "cine_timeline",
            "version": "1.0", "fps": fps,
            "total_frames": cursor, "global_prompt": global_prompt,
            "negative_prompt": global_negative, "shots": shots, "references": references,
            "audio": [], "subtitles": [], "background_music": [],
            "metadata": {
                "source": "AIPM", "aipm_schema": package.get("schema"),
                "aipm_revision": package.get("revision"),
                "mode": "keyframe" if mode == "h3_keyframe" else "multimodal" if mode == "h3_ref2va" else mode,
                "adapter": "AIPMCineTimelineAdapter", "adapter_version": "1.0",
                "conditioning_mode": "text_to_video" if mode == "h3_keyframe" and not profiles else mode,
            },
        }
        report = {
            "status": "adapted", "segments": len(shots), "references": len(references),
            "fps": fps, "total_frames": cursor,
            "prompt_layers": ["source_prompt", "timeline_local_prompt", "compiled_prompt"],
        }
        timeline_json = json.dumps(timeline, ensure_ascii=False, indent=2)
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        first_compiled = str(source_segments[0].get("compiled_prompt") or package.get("video_prompt") or "")
        return {
            "ui": {"text": [timeline_json, report_json, first_compiled]},
            "result": (timeline, timeline_json, report_json, first_compiled),
        }


NODE_CLASS_MAPPINGS = {
    "AIPMImagePrompt": AIPMImagePrompt,
    "AIPMVideoPrompt": AIPMVideoPromptCore,
    "AIPMPromptRefinement": AIPMPromptRefinement,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AIPMImagePrompt": "AI 提示词大师 · 生图",
    "AIPMVideoPrompt": "AI 提示词大师 · 生视频",
    "AIPMPromptRefinement": "AI 提示词大师 · 提示词细化",
}
