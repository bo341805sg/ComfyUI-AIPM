import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

if (!globalThis.__COMFYUI_AIPM_UI_VERSION__ || globalThis.__COMFYUI_AIPM_UI_VERSION__ < 85) {
  globalThis.__COMFYUI_AIPM_UI_VERSION__ = 85;

const VERSION = 85;
const AIPM_MIN_WIDTH = 480;
const REVISION_MARKER = "__AIPM_REVISION_V1__";
const RUN_MARKER = "__AIPM_RUN_V1__";

function removeOldPanel(node) {
  const oldPanel = node._aipmGeneratePanel;
  if (!oldPanel) return;
  oldPanel.cleanup?.();
  oldPanel.root?.remove?.();
  for (const nativeWidget of oldPanel.nativeWidgets || []) {
    const nativeIndex = node.widgets?.indexOf(nativeWidget) ?? -1;
    if (nativeIndex >= 0) node.widgets.splice(nativeIndex, 1);
  }
  const index = node.widgets?.indexOf(oldPanel.widget) ?? -1;
  if (index >= 0) node.widgets.splice(index, 1);
  delete node._aipmGeneratePanel;
}

function hideInternalWidget(widget) {
  if (!widget) return;
  // ComfyUI treats converted-widget as a non-rendered internal value. Using a
  // custom type still lets newer Vue widgets render their original text box.
  widget.type = "converted-widget";
  widget.computeSize = () => [0, -4];
  widget.options ||= {};
  widget.options.hidden = true;
  const element = widget.element || widget.inputEl;
  if (element?.style) {
    element.style.display = "none";
    element.style.width = "0";
    element.style.height = "0";
    element.style.minHeight = "0";
    element.style.margin = "0";
    element.style.padding = "0";
  }
}

function writeTextToLinkedPreviews(node, output) {
  const graph = node?.graph || app.graph || app.rootGraph;
  if (!graph) return 0;
  const textValues = output?.text || [];
  const valuesByName = {
    "视频提示词": textValues[0],
    "正向提示词": textValues[0],
    "负向提示词": textValues[1],
    "完整结果 JSON": textValues[2],
  };
  let updated = 0;
  for (const source of node.outputs || []) {
    const value = valuesByName[source?.name];
    if (value == null) continue;
    for (const linkId of source?.links || []) {
      const link = graph.links?.[linkId] || graph.links?.get?.(linkId);
      const target = link ? graph.getNodeById?.(link.target_id) : null;
      const type = String(target?.type || target?.comfyClass || "").toLowerCase();
      if (!target) continue;
      // Timeline documents are imported only by the complete-result handler.
      // A generic preview refresh must not write a partial package into them.
      if (type.startsWith("cinetimeline")) continue;
      if (type.includes("showtext") || type.includes("displaytext") || type.includes("previewtext")) {
        target.onExecuted?.({ text: [String(value)] });
      } else {
        const targetInput = target.inputs?.[link.target_slot];
        if (String(targetInput?.type || "").toUpperCase() !== "STRING") continue;
        const widgetName = targetInput?.widget?.name || targetInput?.name;
        const targetWidget = target.widgets?.find((widget) => widget.name === widgetName);
        if (!targetWidget) continue;
        targetWidget.value = String(value);
        targetWidget.callback?.(targetWidget.value, app.canvas, target, app.canvas?.graph_mouse, {});
      }
      target.setDirtyCanvas?.(true, true);
      updated += 1;
    }
  }
  return updated;
}

function linkedAppendTimeline(node) {
  const graph = node.graph || app.graph;
  const output = (node.outputs || []).find(o => o.name === "完整结果 JSON");
  const targets = new Set();
  for (const id of output?.links || []) {
    const link = graph?.links?.[id] || graph?.links?.get?.(id);
    const target = link && graph.getNodeById?.(link.target_id);
    if (target && ["CineTimelinePlan", "CineTimelineKeyframePlan", "CineTimelineStudio", "CineTimelineEditor"].includes(target.comfyClass || target.type)
        && target.inputs?.[link.target_slot]?.name === "timeline_json") targets.add(target);
  }
  if (!targets.size) return null;
  if (targets.size !== 1) throw new Error("续写连接了多个时间轴，请只保留一个目标。");
  const target = [...targets][0];
  const widget = target.widgets?.find(w => w.name === "timeline_state");
  const timeline = JSON.parse(String(widget?.value || "{}"));
  if (!Array.isArray(timeline.shots) || !timeline.shots.length) throw new Error("当前时间轴没有可续写分段。");
  return timeline;
}

function writeResultToLinkedCineTimelines(node, rawTimelineJson, strategy = "rewrite", targetSegmentId = "") {
  const graph = node?.graph || app.graph;
  let raw = String(rawTimelineJson || "").trim();
  if (!raw || String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return 0;
  let parsed;
  try {
    parsed = JSON.parse(raw);
    if (!["cine_timeline", "cine_keyframe_timeline"].includes(parsed?.schema) || !Array.isArray(parsed?.shots)) return 0;
  } catch {
    return 0;
  }
  parsed.shots.forEach((shot, index) => {
    shot.metadata = shot.metadata && typeof shot.metadata === "object" ? shot.metadata : {};
    if (index === 0 || shot.metadata.new_scene === true) shot.transition = "cut";
    else if (!["cut", "motion_context"].includes(shot.transition)) shot.transition = "motion_context";
  });
  raw = JSON.stringify(parsed);
  const jsonOutput = (node.outputs || []).find((output) => output?.name === "完整结果 JSON");
  let updated = 0;
  for (const linkId of jsonOutput?.links || []) {
    const link = graph?.links?.[linkId] || graph?.links?.get?.(linkId);
    const target = link ? graph?.getNodeById?.(link.target_id) : null;
    if (!target || ![
      "CineTimelinePlan", "CineTimelineKeyframePlan", "CineTimelineStudio", "CineTimelineEditor",
    ].includes(String(target.comfyClass || target.type || ""))) continue;
    const targetIsKeyframe = String(target.comfyClass || target.type || "") === "CineTimelineKeyframePlan";
    if (targetIsKeyframe !== (parsed.schema === "cine_keyframe_timeline")) continue;
    const targetInput = target.inputs?.[link.target_slot];
    if (targetInput?.name !== "timeline_json") continue;
    const timelineWidget = target.widgets?.find((widget) => widget.name === "timeline_state");
    if (!timelineWidget) continue;
    let current;
    try {
      current = JSON.parse(String(timelineWidget.value || "{}"));
    } catch {}
    let next = parsed;
    raw = JSON.stringify(parsed);
    if (strategy === "append" || strategy === "revise_segment") {
      const incoming = parsed.shots || [];
      const existing = Array.isArray(current?.shots) ? current.shots : [];
      if (strategy === "append") {
        const known = new Set(existing.map((shot) => String(shot?.shot_id || "")));
        const additions = incoming.filter((shot) => !known.has(String(shot?.shot_id || "")));
        if (!additions.length) continue;
        const existingEnd = Math.max(0, ...existing.map((shot) => Number(shot.end_frame) || 0));
        if (additions.some((shot) => Number(shot.start_frame) < existingEnd)) {
          throw new Error("续写分段与当前时间轴重叠，请按当前时间轴重新续写；现有内容未覆盖。");
        }
        // Append must preserve the editor's complete existing document.
        const totalFrames = Math.max(existingEnd, ...additions.map((shot) => Number(shot.end_frame) || 0));
        const oldRefs = Array.isArray(current?.references) ? current.references : [];
        const knownRefs = new Set(oldRefs.map((ref) => String(ref.reference_id || "")));
        const addedIds = new Set(additions.map((shot) => String(shot.shot_id || "")));
        const newRefs = (parsed.references || []).filter((ref) =>
          !knownRefs.has(String(ref.reference_id || "")) &&
          (ref.scope === "global" || addedIds.has(String(ref.shot_id || ""))));
        next = { ...parsed, ...current, total_frames: totalFrames,
          shots: [...existing, ...additions],
          references: [...oldRefs.map((ref) => ref.scope === "global"
            ? { ...ref, end_frame: totalFrames } : ref), ...newRefs],
        };
        if (Array.isArray(current?.background_music) && current.background_music.length) {
          next.background_music = current.background_music;
        }
      } else {
        const replacement = incoming.find((shot) => String(shot?.shot_id || "") === String(targetSegmentId));
        if (!replacement) continue;
        next = { ...current, shots: existing.map((shot) => {
          if (String(shot?.shot_id || "") !== String(targetSegmentId)) return shot;
          const oldRender = shot?.metadata?.render;
          const merged = { ...replacement, metadata: { ...(replacement.metadata || {}) } };
          if (oldRender) merged.metadata.render = { ...oldRender, status: "redo", active_version: "" };
          return merged;
        }) };
      }
      next.metadata = { ...(next.metadata || {}), aipm: parsed?.metadata?.aipm };
      raw = JSON.stringify(next);
    }
    timelineWidget.value = raw;
    timelineWidget.callback?.(raw);
    target.cineTimelineEditor?.reloadState?.();
    target.setDirtyCanvas?.(true, true);
    updated += 1;
  }
  if (updated) graph?.change?.();
  return updated;
}

function migrateVideoDurationWidget(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return;
  const widget = node.widgets?.find((item) => item.name === "视频时长");
  if (!widget) return;
  const matched = String(widget.value ?? "").match(/\d+/);
  const seconds = Math.max(4, Math.min(30, matched ? Number(matched[0]) : Number(widget.value) || 15));
  widget.value = seconds;
  widget.type = "number";
  widget.options = {
    ...(widget.options || {}), min: 4, max: 30, step: 1, precision: 0,
  };
  const input = node.inputs?.find((item) => item.name === "视频时长");
  if (input) input.type = "INT";
  const segmentWidget = node.widgets?.find((item) => item.name === "分段数量");
  if (segmentWidget) {
    segmentWidget.value = Math.max(1, Math.min(12, Number(segmentWidget.value) || 1));
    segmentWidget.type = "number";
    segmentWidget.options = {
      ...(segmentWidget.options || {}), min: 1, max: 12, step: 1, precision: 0,
    };
  }
  const segmentInput = node.inputs?.find((item) => item.name === "分段数量");
  if (segmentInput) segmentInput.type = "INT";
}

function detachInternalWidget(node, widget) {
  const index = node.widgets?.indexOf(widget) ?? -1;
  if (index >= 0) node.widgets.splice(index, 1);
}

function syncGeneratePanelWidth(node) {
  const panel = node._aipmGeneratePanel;
  if (!panel?.root) return;
  const width = Math.max(1, (Number(node.size?.[0]) || AIPM_MIN_WIDTH) - 20);
  panel.widget.computedWidth = width;
  panel.root.style.width = `${width}px`;
  panel.root.style.maxWidth = `${width}px`;
  const host = panel.root.parentElement;
  if (host?.style) {
    host.style.width = `${width}px`;
    host.style.maxWidth = `${width}px`;
  }
}

function configureStableNodeLayout(node) {
  if (node._aipmStableLayoutVersion === VERSION) return;
  node._aipmStableLayoutVersion = VERSION;
  node.properties ||= {};
  // LiteGraph disables every native widget when the node itself is bypassed
  // or muted. AIPM is safe in ALWAYS mode: ordinary workflow execution only
  // emits its saved local cache; remote calls require an explicit button marker.
  node.mode = 0;
  delete node.properties.aipm_locked_width;

  const contentInput = node.widgets?.find((widget) =>
    widget.name === "画面描述与创作要求" || widget.name === "视频内容与导演要求"
  );
  let resizeBaselineHeight = Math.max(1, Number(node.size?.[1]) || 300);
  let contentBaselineHeight = 110;
  if (contentInput) {
    const measured = Number(contentInput.computeSize?.(Number(node.size?.[0]) || AIPM_MIN_WIDTH)?.[1]);
    if (Number.isFinite(measured) && measured > 0) contentBaselineHeight = measured;
    contentInput._aipmAdaptiveHeight = Math.max(72, contentBaselineHeight);
    contentInput.computeSize = (width) => [width, contentInput._aipmAdaptiveHeight];
  }
  const originalComputeSize = node.computeSize;
  if (contentInput && originalComputeSize) {
    node.computeSize = function () {
      const currentHeight = contentInput._aipmAdaptiveHeight;
      contentInput._aipmAdaptiveHeight = 72;
      try {
        return originalComputeSize.apply(this, arguments);
      } finally {
        contentInput._aipmAdaptiveHeight = currentHeight;
      }
    };
  }

  const resizeContentInput = (nextHeight) => {
    if (!contentInput || !Number.isFinite(Number(nextHeight))) return;
    // Recompute the budget, never accumulate an automatic resize delta.
    const minimumHeight = Number(node.computeSize?.([Number(node.size?.[0]) || AIPM_MIN_WIDTH, 0])?.[1]);
    const adaptiveHeight = Math.max(72, 72 + Number(nextHeight) - (minimumHeight || Number(nextHeight)) - 8);
    contentInput._aipmAdaptiveHeight = adaptiveHeight;
    const element = contentInput.element || contentInput.inputEl;
    if (element?.style) {
      const editorHeight = Math.max(62, adaptiveHeight - 10);
      element.style.height = `${editorHeight}px`;
      element.style.minHeight = `${editorHeight}px`;
      element.style.maxHeight = `${editorHeight}px`;
      element.style.resize = "none";
    }
  };
  resizeContentInput(resizeBaselineHeight);
  node._aipmFitContentInput = () => {
    if (!contentInput || !node.size) return;
    resizeContentInput(Number(node.size[1]));
  };

  // Canvas arrange uses measured slot geometry, not computeSize. Fit against
  // that exact budget before its overflow check can grow the node again.
  const originalArrangeWidgets = node._arrangeWidgets;
  if (contentInput && originalArrangeWidgets) {
    node._arrangeWidgets = function (slotBottom) {
      const start = this.widgets_start_y ?? ((this.widgets_up ? 0 : slotBottom) + 2);
      const widgets = this.getLayoutWidgets();
      let occupied = 4; // content widget margin
      for (const widget of widgets) {
        if (widget === contentInput) continue;
        occupied += widget.computeSize
          ? Number(widget.computeSize(this.size?.[0])?.[1] || 0) + 4
          : widget.computeLayoutSize
            ? Number(widget.computeLayoutSize(this).minHeight || 0)
            : 24;
      }
      contentInput._aipmAdaptiveHeight = Math.max(72, this.bodyHeight - start - occupied - 8);
      const element = contentInput.element || contentInput.inputEl;
      if (element?.style) {
        const height = `${Math.max(62, contentInput._aipmAdaptiveHeight - 10)}px`;
        element.style.height = element.style.minHeight = element.style.maxHeight = height;
      }
      return originalArrangeWidgets.apply(this, arguments);
    };
  }

  const modification = node.widgets?.find((widget) =>
    widget.name === "修改意见" || widget.name === "遇到的问题与修改目标"
  );
  if (modification) {
    modification.computeSize = (width) => [width, 54];
    modification.options ||= {};
    modification.options.minHeight = 54;
    modification.options.maxHeight = 54;
    const element = modification.element || modification.inputEl;
    if (element?.style) {
      element.style.height = "44px";
      element.style.minHeight = "44px";
      element.style.maxHeight = "44px";
      element.style.resize = "none";
    }
  }

  if (String(node?.comfyClass || node?.type || "") === "AIPMPromptRefinement") {
    const originalPrompt = node.widgets?.find((widget) => widget.name === "原始提示词");
    const mustPreserve = node.widgets?.find((widget) => widget.name === "必须保留的内容");
    if (originalPrompt) originalPrompt.computeSize = (width) => [width, 150];
    if (mustPreserve) mustPreserve.computeSize = (width) => [width, 54];
  }

  const originalResize = node.onResize;
  node.onResize = function (size) {
    const nextSize = Array.isArray(size) ? size : this.size;
    if (nextSize) nextSize[0] = Math.max(AIPM_MIN_WIDTH, Number(nextSize[0]) || AIPM_MIN_WIDTH);
    if (nextSize) resizeContentInput(Number(nextSize[1]));
    const result = originalResize?.apply(this, arguments);
    if (this.size) this.size[0] = Math.max(AIPM_MIN_WIDTH, Number(this.size[0]) || AIPM_MIN_WIDTH);
    requestAnimationFrame(() => syncGeneratePanelWidth(this));
    return result;
  };
  if (node.size) node.size[0] = Math.max(AIPM_MIN_WIDTH, Number(node.size[0]) || AIPM_MIN_WIDTH);
}

function collectReferenceAssetManifest(node) {
  const definitions = (node.inputs || [])
    .filter((input) => /^(image\d+|video\d+|audio\d+|参考图片\d*|参考图片|参考视频|参考声音)$/.test(String(input.name || "")))
    .map((input) => ({
      input,
      mediaType: /^(video|参考视频)/.test(String(input.name)) ? "video"
        : /^(audio|参考声音)/.test(String(input.name)) ? "audio" : "image",
    }));
  const manifest = [];
  const counters = { image: 0, video: 0, audio: 0 };
  for (const { input, mediaType } of definitions) {
    if (input.link == null) continue;
    let link = app.graph?.links?.[input.link];
    let source = link ? app.graph?.getNodeById?.(link.origin_id) : null;
    for (let depth = 0; source && depth < 8; depth += 1) {
      const sourceType = String(source.comfyClass || source.type || "").toLowerCase();
      if (!sourceType.includes("reroute")) break;
      const upstream = source.inputs?.find((item) => item.link != null);
      link = upstream ? app.graph?.links?.[upstream.link] : null;
      source = link ? app.graph?.getNodeById?.(link.origin_id) : null;
    }
    if (!source) continue;
    const sourceType = String(source.comfyClass || source.type || "").toLowerCase();
    const expectedLoader = mediaType === "image" ? "loadimage"
      : mediaType === "video" ? "loadvideo" : "loadaudio";
    if (!sourceType.replaceAll("_", "").includes(expectedLoader)) continue;
    const candidateNames = mediaType === "image" ? ["image"]
      : mediaType === "video" ? ["file", "video"] : ["audio", "file"];
    const sourceWidget = source.widgets?.find((widget) =>
      candidateNames.includes(String(widget.name || "").toLowerCase())
    );
    const assetId = String(sourceWidget?.value || "").trim();
    if (!assetId) continue;
    const index = counters[mediaType]++;
    manifest.push({
      asset_id: assetId,
      media_type: mediaType,
      input_name: input.name,
      [`${mediaType}_index`]: index,
      storage_type: "input",
      source_node_type: String(source.comfyClass || source.type || ""),
    });
  }
  return manifest;
}

function migrateReferenceInputNames(node) {
  const nodeType = String(node?.comfyClass || node?.type || "");
  const mapping = nodeType === "AIPMImagePrompt" ? {
    "参考图片": "image1", "参考图片1": "image1",
    "参考图片2": "image2", "参考图片3": "image3",
  } : nodeType === "AIPMVideoPrompt" ? {
    "参考图片1": "image1", "参考图片2": "image2",
    "参考图片3": "image3", "参考图片4": "image4",
    "参考视频": "video1", "参考声音": "audio1",
  } : {};
  for (const input of node?.inputs || []) {
    const replacement = mapping[String(input.name || "")];
    if (replacement) {
      input.name = replacement;
      input.label = replacement;
    }
  }
}

function dynamicReferenceLimits(node) {
  const nodeType = String(node?.comfyClass || node?.type || "");
  if (nodeType === "AIPMImagePrompt") return { image: 9 };
  if (nodeType === "AIPMVideoPrompt") return { image: 9, video: 3, audio: 3 };
  return {};
}

function syncDynamicReferenceInputs(node) {
  if (node._aipmSyncingReferenceInputs) return;
  const limits = dynamicReferenceLimits(node);
  if (!Object.keys(limits).length) return;
  node._aipmSyncingReferenceInputs = true;
  try {
    for (const [prefix, limit] of Object.entries(limits)) {
      const pattern = new RegExp(`^${prefix}(\\d+)$`);
      const matching = (node.inputs || []).map((input, slot) => {
        const match = pattern.exec(String(input.name || ""));
        return match ? { input, slot, number: Number(match[1]) } : null;
      }).filter(Boolean);
      const connectedNumbers = new Set(
        matching.filter(({ input }) => input.link != null).map(({ number }) => number),
      );
      const availableNumber = Array.from({ length: limit }, (_, index) => index + 1)
        .find((number) => !connectedNumbers.has(number));
      // Keep every connected port and exactly one empty port. Removing from
      // the end lets LiteGraph update target_slot indexes without invalidating
      // earlier entries.
      const removeSlots = matching
        .filter(({ input, number }) => input.link == null && number !== availableNumber)
        .map(({ slot }) => slot)
        .sort((a, b) => b - a);
      for (const slot of removeSlots) node.removeInput?.(slot);
      if (availableNumber != null && !(node.inputs || []).some((input) => input.name === `${prefix}${availableNumber}`)) {
        const type = prefix === "image" ? "IMAGE" : prefix === "video" ? "VIDEO" : "AUDIO";
        node.addInput?.(`${prefix}${availableNumber}`, type);
      }
    }
    node.setDirtyCanvas?.(true, true);
  } finally {
    node._aipmSyncingReferenceInputs = false;
  }
}

function migrateModelNameWidget(node) {
  const oldDefault = "Qwen3.8-27B-Uncensored-Q5_K_M.gguf";
  const newDefault = "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf";
  for (const input of node?.inputs || []) {
    if (input.name === "服务模型") {
      input.name = "模型名称";
      input.label = "模型名称";
      if (input.widget?.name === "服务模型") input.widget.name = "模型名称";
    }
  }
  for (const widget of node?.widgets || []) {
    if (widget.name !== "服务模型" && widget.name !== "模型名称") continue;
    widget.name = "模型名称";
    if (!String(widget.value || "").trim() || widget.value === oldDefault) widget.value = newDefault;
  }
}

function migrateImageModelDefault(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMImagePrompt") return;
  const widget = node.widgets?.find((item) => item.name === "目标生图模型");
  if (["自动判断 / 通用（推荐）", "Krea 2 / Krea 2 Turbo 系列"].includes(String(widget?.value || ""))) {
    widget.value = "Krea 2 / Krea 2 Turbo 文生图";
  }
}

function migrateVideoTargetModel(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return;
  const widget = node.widgets?.find((item) => item.name === "目标视频模型");
  if (widget) widget.value = "MiniMax H3";
}

function migrateImageReferencePurpose(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMImagePrompt") return;
  const widget = node.widgets?.find((item) => item.name === "参考图用途");
  if (widget && !["多参考改图", "仅分析参考"].includes(String(widget.value || ""))) {
    widget.value = "多参考改图";
  }
}

function migrateVideoGenerationMode(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return;
  const widget = node.widgets?.find((item) => item.name === "生成模式");
  if (!widget) return;
  const migration = {
    "自动判断": "多模态",
    "自动判断（推荐）": "多模态",
    "文生视频": "关键帧",
    "多参考 Ref2VA": "多模态",
    "首帧 I2VA": "关键帧",
    "尾帧 L2VA": "关键帧",
    "首尾帧": "关键帧",
    "首尾帧 FL2VA": "关键帧",
  };
  widget.value = migration[String(widget.value || "")] || widget.value || "多模态";
}

function migrateShiftedCachedResult(node) {
  const modification = node.widgets?.find((item) => item.name === "修改意见");
  const raw = String(modification?.value || "").trim();
  if (!raw) return;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return;
  }
  const nodeType = String(node?.comfyClass || node?.type || "");
  const isImageCache = nodeType === "AIPMImagePrompt"
    && parsed?.schema === "aipm_image_prompt" && parsed?.positive_prompt;
  const isVideoCache = nodeType === "AIPMVideoPrompt"
    && ["aipm_video_prompt", "cine_timeline", "cine_keyframe_timeline"].includes(parsed?.schema);
  if (!isImageCache && !isVideoCache) return;
  const previousResult = node.widgets?.find((item) => item.name === "上次结果JSON");
  node.properties ||= {};
  if (!String(node.properties.aipm_previous_result || "").trim()) {
    node.properties.aipm_previous_result = raw;
  }
  if (previousResult && !String(previousResult.value || "").trim()) {
    previousResult.value = String(node.properties.aipm_previous_result || raw);
  }
  modification.value = "";
}

function installGeneratePanel(node) {
  if (node._aipmGeneratePanel?.version === VERSION) return;
  removeOldPanel(node);
  const requestState = node._aipmRequestState ||= { running: false, activePromptId: "", pendingQueueEvents: [], currentAction: "generate" };
  const isRefinement = String(node?.comfyClass || node?.type || "") === "AIPMPromptRefinement";
  const isVideo = String(node?.comfyClass || node?.type || "") === "AIPMVideoPrompt";
  const isImage = String(node?.comfyClass || node?.type || "") === "AIPMImagePrompt";
  const previousResult = node.widgets?.find((item) => item.name === "上次结果JSON");
  const referenceManifest = node.widgets?.find((item) => item.name === "参考素材清单JSON");
  const modificationInput = node.widgets?.find((item) => item.name === "修改意见");
  const previousResultIndex = Math.max(node.widgets?.indexOf(previousResult) ?? -1, 0);
  node.properties ||= {};
  if (isVideo && ["重写时间轴", "续写时间轴"].includes(String(modificationInput?.value || ""))) {
    const shiftedInstruction = String(referenceManifest?.value || "").trim();
    let manifestIsValid = false;
    try { manifestIsValid = Array.isArray(JSON.parse(shiftedInstruction)); } catch (_) {}
    if (shiftedInstruction && !manifestIsValid) {
      // v47-v49 could persist the two runtime combos ahead of the backend
      // fields. Recover the user's instruction from the displaced manifest
      // slot; the real manifest is rebuilt from connected references on run.
      modificationInput.value = shiftedInstruction;
      referenceManifest.value = "[]";
    } else {
      modificationInput.value = "";
    }
  }
  if (!node.properties.aipm_previous_result && String(previousResult?.value || "").trim()) {
    node.properties.aipm_previous_result = String(previousResult.value);
  }
  hideInternalWidget(previousResult);
  hideInternalWidget(referenceManifest);

  const nativeWidgets = [];
  const keepRuntimeOnly = (widget) => {
    if (!widget) return widget;
    // ComfyUI serializes widgets positionally. Passing serialize:false only in
    // addWidget options is not honoured by every frontend release, so mark the
    // widget itself as runtime-only as well. Otherwise these helper controls
    // shift saved values into backend inputs such as 修改意见.
    widget.serialize = false;
    widget.options ||= {};
    widget.options.serialize = false;
    return widget;
  };
  const operationLabels = { rewrite: "重写时间轴", append: "续写时间轴" };
  const operationFromLabel = (value) => value === operationLabels.append ? "append" : "rewrite";
  let operationSelect = null;
  let targetSelect = null;
  const targetIdsByLabel = new Map();
  if (isVideo) {
    operationSelect = keepRuntimeOnly(node.addWidget(
      "combo", "时间轴处理方式",
      operationLabels[String(node.properties?.aipm_timeline_operation || "rewrite")] || operationLabels.rewrite,
      (value) => {
        node.properties.aipm_timeline_operation = operationFromLabel(value);
        app.graph?.change?.();
      },
      { values: Object.values(operationLabels), serialize: false },
    ));
    targetSelect = keepRuntimeOnly(node.addWidget(
      "combo", "修改目标分段", "暂无缓存",
      (value) => {
        node.properties.aipm_target_segment_id = targetIdsByLabel.get(String(value)) || "";
        app.graph?.change?.();
      },
      { values: ["暂无缓存"], serialize: false },
    ));
    nativeWidgets.push(operationSelect, targetSelect);
  }
  let run = async () => {};
  const button = keepRuntimeOnly(node.addWidget("button", isRefinement ? "分析并细化" : "生成 / 重新创作", null, () => run(false), { serialize: false }));
  const reviseButton = keepRuntimeOnly(node.addWidget("button", isRefinement ? "根据新意见继续细化" : "按修改意见优化", null, () => run(true), { serialize: false }));
  // Some property panels capture the callback when addWidget registers it.
  // Register the real handler immediately, not a placeholder replaced later.
  const cacheButton = keepRuntimeOnly(node.addWidget("button", "输出缓存", null, outputCachedResult, { serialize: false }));
  const clearButton = keepRuntimeOnly(node.addWidget("button", "清空结果", null, clearCachedResult, { serialize: false }));
  const status = keepRuntimeOnly(node.addWidget("text", "AIPM 状态", "仅执行当前节点，不触发工作流其他生成节点。", () => {}, { serialize: false }));
  const videoPromptPreview = isVideo && keepRuntimeOnly(node.addWidget(
    "text", "视频提示词预览", "", () => {},
    { multiline: true, serialize: false },
  ));
  if (isVideo && modificationInput && operationSelect && targetSelect) {
    // These controls are runtime-only and explicitly excluded from
    // serialization. Reorder only their visual slots so the timeline choices
    // remain adjacent to, and immediately above, the modification request.
    const controls = [operationSelect, targetSelect];
    node.widgets = (node.widgets || []).filter((widget) => !controls.includes(widget));
    const modificationIndex = Math.max(node.widgets.indexOf(modificationInput), 0);
    node.widgets.splice(modificationIndex, 0, ...controls);
  }
  status.options ||= {};
  status.options.disabled = true;
  nativeWidgets.push(button, reviseButton, cacheButton, clearButton, status);
  if (videoPromptPreview) nativeWidgets.push(videoPromptPreview);
  // Clear stale absolute layout coordinates after restoring/reordering widgets.
  for (const widget of node.widgets || []) {
    delete widget.y;
    delete widget.last_y;
  }
  node.setDirtyCanvas?.(true, true);

  const setStatus = (message, type = "") => {
    status.value = message;
    app.graph?.setDirtyCanvas(true, true);
  };

  const describeSubmissionError = (error) => {
    if (!error) return "未知错误";
    try {
      const detailed = typeof error.toString === "function" ? String(error.toString()) : "";
      if (detailed && detailed !== "[object Object]" && detailed !== String(error.message || "")) return detailed;
      const response = error.response;
      const serverError = response?.error;
      const nodeErrors = response?.node_errors;
      const parts = [];
      if (typeof serverError === "string") parts.push(serverError);
      else if (serverError) parts.push([serverError.message, serverError.details].filter(Boolean).join(": "));
      if (nodeErrors && Object.keys(nodeErrors).length) parts.push(JSON.stringify(nodeErrors));
      return parts.filter(Boolean).join(" | ") || String(error.message || error);
    } catch (_) {
      return String(error?.message || error);
    }
  };

  const cachedAuthoring = () => {
    try {
      const value = JSON.parse(String(node.properties?.aipm_previous_result || ""));
      return ["cine_timeline", "cine_keyframe_timeline"].includes(value?.schema) ? value?.metadata?.aipm : value;
    } catch (_) {
      return null;
    }
  };

  const refreshSegmentTargets = () => {
    if (!isVideo) return;
    const segments = cachedAuthoring()?.segments || [];
    const wanted = String(node.properties?.aipm_target_segment_id || "");
    targetIdsByLabel.clear();
    const labels = segments.map((segment, index) => {
      const id = String(segment?.segment_id || `SEGMENT_${String(index + 1).padStart(3, "0")}`);
      const label = `${id} · ${String(segment?.title || `分段 ${index + 1}`)}`;
      targetIdsByLabel.set(label, id);
      return label;
    });
    targetSelect.options.values = labels.length ? labels : ["暂无缓存"];
    const selectedLabel = labels.find((label) => targetIdsByLabel.get(label) === wanted) || labels[0] || "暂无缓存";
    targetSelect.value = selectedLabel;
    node.properties.aipm_target_segment_id = targetIdsByLabel.get(selectedLabel) || "";
  };

  const hasInterruptedVideo = () =>
    !isRefinement && cachedAuthoring()?.generation_status === "interrupted";

  const updateRevisionAvailability = () => {
    const cachedText = String(node.properties?.aipm_previous_result || "").trim();
    const hasCache = Boolean(cachedText);
    cacheButton.name = hasCache ? `输出缓存（已有 ${cachedText.length} 字符）` : "输出缓存（无缓存）";
    // Native canvas widgets do not reliably repaint when `disabled` changes
    // after workflow cache restoration. Keep actions physically clickable and
    // let their callbacks explain missing prerequisites in the status widget.
    reviseButton.disabled = false;
    cacheButton.disabled = false;
    if (!requestState.running && hasInterruptedVideo()) button.name = "继续生成";
    refreshSegmentTargets();
  };

  const queueCurrentOutputs = async (requestInputs = {}) => {
    // Queue direct text-preview consumers as execution endpoints. This keeps
    // prompt assistants independent from the expensive generation chain.
    const activeGraph = node.graph || app.graph || app.rootGraph;
    if (!activeGraph) throw new Error("找不到AIPM节点所属工作流图");
    const previewNodeIds = new Set();
    for (const output of node.outputs || []) {
      for (const linkId of output?.links || []) {
        const link = activeGraph.links?.[linkId];
        const target = link ? activeGraph.getNodeById?.(link.target_id) : null;
        const type = String(target?.type || target?.comfyClass || "").toLowerCase();
        if (type.includes("showtext") || type.includes("displaytext") || type.includes("previewtext")) {
          previewNodeIds.add(String(target.id));
        }
      }
    }
    const executionTargets = previewNodeIds.size ? [...previewNodeIds] : [String(node.id)];
    if (typeof app.graphToPrompt !== "function" || typeof app.api?.queuePrompt !== "function") {
      throw new Error("当前 ComfyUI 不支持局部执行接口");
    }
    // Workflows can restore a node created under an older definition where
    // the frontend constructor lost the backend output_node flag. Without it
    // graphToPrompt serializes an empty prompt even though AIPM is an
    // independently executable OUTPUT_NODE on the server.
    node.constructor.nodeData ||= {};
    node.constructor.nodeData.output_node = true;
    node.mode = 0;
    const prompt = await app.graphToPrompt(activeGraph);
    const apiNodes = prompt?.output || {};
    let targetIds = executionTargets.filter((id) => apiNodes[String(id)]).map(String);
    if (!targetIds.length) {
      const comfyClass = String(node.comfyClass || node.type || "");
      const title = String(node.title || "");
      const candidates = Object.entries(apiNodes).filter(([, value]) =>
        String(value?.class_type || "") === comfyClass
      );
      const titled = candidates.filter(([, value]) => String(value?._meta?.title || "") === title);
      const scoped = (titled.length ? titled : candidates).filter(([id]) =>
        String(id) === String(node.id) || String(id).endsWith(`:${node.id}`)
      );
      const resolved = scoped.length ? scoped : (titled.length ? titled : candidates);
      if (resolved.length === 1) targetIds = [String(resolved[0][0])];
    }
    if (!targetIds.length) {
      throw new Error(`当前工作流图没有序列化AIPM执行节点 ${node.id}`);
    }
    // Build a self-contained prompt containing only the requested endpoint(s)
    // and their upstream dependencies. This avoids ComfyUI 0.34's partial
    // target filter occasionally reducing multi-workflow graphs to no outputs.
    const keep = new Set();
    const pending = [...targetIds.map(String)];
    while (pending.length) {
      const id = pending.pop();
      if (keep.has(id) || !apiNodes[id]) continue;
      keep.add(id);
      for (const value of Object.values(apiNodes[id].inputs || {})) {
        if (Array.isArray(value) && value.length === 2 && apiNodes[String(value[0])]) {
          pending.push(String(value[0]));
        }
      }
    }
    prompt.output = Object.fromEntries(Object.entries(apiNodes).filter(([id]) => keep.has(String(id))));
    // Private execution markers belong only to the API payload, never widgets
    // or the workflow snapshot. Resolve exactly one node; fail closed if ambiguous.
    const requestClass = String(node.comfyClass || node.type || "");
    const matches = Object.entries(prompt.output).filter(([id, entry]) =>
      entry.class_type === requestClass &&
      (id === String(node.id) || id.endsWith(`:${node.id}`))
    );
    if (matches.length !== 1) throw new Error("无法唯一定位AIPM请求节点，未提交。");
    matches[0][1].inputs = { ...matches[0][1].inputs, ...requestInputs };
    const queued = await app.api.queuePrompt(0, prompt);
    if (!queued?.prompt_id) throw new Error("AIPM提交未返回任务编号");
    requestState.activePromptId = String(queued.prompt_id);
    node.properties.aipm_pending_request = { id: requestState.activePromptId, action: requestState.currentAction };
    const buffered = requestState.pendingQueueEvents;
    requestState.pendingQueueEvents = [];
    for (const [handler, event] of buffered) handler(event);
  };

  run = async (revise = false) => {
    if (requestState.running) {
      setStatus("当前AIPM请求仍在执行，请等待完成；无需重复点击。", "");
      return;
    }
    const idea = node.widgets?.find((widget) =>
      widget.name === "画面描述与创作要求" || widget.name === "视频内容与导演要求" || widget.name === "原始提示词"
    );
    if (!String(idea?.value || "").trim()) {
      setStatus("请先填写创作内容与导演要求。", "error");
      return;
    }
    const modification = node.widgets?.find((widget) =>
      widget.name === "修改意见" || widget.name === "遇到的问题与修改目标"
    );
    const originalModification = String(modification?.value || "");
    let requestModification = originalModification;
    if (revise && !String(modification?.value || "").trim()) {
      setStatus("请先填写修改意见。", "error");
      return;
    }
    if (revise && !String(node.properties?.aipm_previous_result || "").trim()) {
      setStatus("还没有上次结果，请先生成一次提示词。", "error");
      return;
    }
    if (isVideo && !revise && operationFromLabel(operationSelect.value) === "append" && !String(node.properties?.aipm_previous_result || "").trim()) {
      setStatus("续写需要已有AIPM缓存，请先生成初始时间轴。", "error");
      return;
    }
    if (isVideo && revise && !String(targetIdsByLabel.get(String(targetSelect.value)) || "").trim()) {
      setStatus("请选择要修改的分段。", "error");
      return;
    }
    let editorTimeline = null;
    if (isVideo && !revise && operationFromLabel(operationSelect.value) === "append") {
      try { editorTimeline = linkedAppendTimeline(node); }
      catch (error) { setStatus(String(error.message || error), "error"); return; }
    }
    requestState.running = true;
    requestState.activePromptId = "";
    requestState.pendingQueueEvents = [];
    requestState.currentAction = revise ? "revise" : (hasInterruptedVideo() ? "resume" : (
      isVideo && operationFromLabel(operationSelect.value) === "append" ? "append" : "generate"
    ));
    if (isVideo && modification) {
      requestModification = "__AIPM_RUN_V2__" + JSON.stringify({
        operation: revise ? "revise_segment" : operationFromLabel(operationSelect.value),
        target_segment_id: revise ? (targetIdsByLabel.get(String(targetSelect.value)) || "") : "",
        instruction: originalModification,
        previous_result: String(node.properties?.aipm_previous_result || ""),
        editor_timeline: editorTimeline,
      });
    } else if (revise && modification) {
      requestModification = REVISION_MARKER + JSON.stringify({
        instruction: originalModification,
        previous_result: String(node.properties?.aipm_previous_result || ""),
      });
    } else {
      if (modification) requestModification = isRefinement
        ? `${RUN_MARKER}${originalModification}`
        : `${RUN_MARKER}${Date.now()}`;
      // Preserve an interrupted video package as a resumable checkpoint.
      // Complete packages are still ignored by the backend on a fresh run.
      if (previousResult) previousResult.value = String(node.properties?.aipm_previous_result || "");
    }
    if (referenceManifest) {
      referenceManifest.value = JSON.stringify(collectReferenceAssetManifest(node));
    }
    setStatus(revise
      ? "正在保留未修改内容并定向优化……"
      : requestState.currentAction === "resume"
        ? "正在从上次失败分段继续生成……"
        : "正在分析输入并生成专业提示词……");
    node.mode = 0;
    if (previousResult && !node.widgets?.includes(previousResult)) {
      node.widgets.splice(Math.min(previousResultIndex, node.widgets.length), 0, previousResult);
    }
    try {
      await queueCurrentOutputs(modification ? { [modification.name]: requestModification } : {});
    } catch (error) {
      requestState.running = false;
      button.disabled = false;
      reviseButton.disabled = false;
      cacheButton.disabled = false;
      clearButton.disabled = false;
      button.name = isRefinement ? "分析并细化" : "生成 / 重新创作";
      reviseButton.name = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
      updateRevisionAvailability();
      setStatus(`提交失败：${describeSubmissionError(error)}`, "error");
    } finally {
      // The revision field is user-authored working text. Keep it after every
      // submission so the user can refine or reuse the same instruction.
      // Do not restore widgets: the user may have edited them during submission.
      node.mode = 0;
    }
  };
  button.callback = () => run(false);
  reviseButton.callback = () => run(true);
  async function outputCachedResult() {
    if (requestState.running) {
      setStatus("当前AIPM请求仍在执行，请等待完成；无需重复点击。", "");
      return;
    }
    const cached = String(node.properties?.aipm_previous_result || "").trim();
    if (!cached) {
      setStatus("还没有可输出的缓存，请先生成一次提示词。", "error");
      updateRevisionAvailability();
      return;
    }
    const modification = node.widgets?.find((widget) =>
      widget.name === "修改意见" || widget.name === "遇到的问题与修改目标"
    );
    const originalModification = String(modification?.value || "");
    requestState.running = true;
    requestState.activePromptId = "";
    requestState.pendingQueueEvents = [];
    requestState.currentAction = "cache";
    if (previousResult) previousResult.value = cached;
    // Image/video nodes interpret a non-empty modification as a revision.
    // Refinement nodes can keep their issue text because their cached branch
    // is selected whenever no independent execution marker is present.
    const requestInputs = modification && !isRefinement ? { [modification.name]: "" } : {};
    setStatus("正在从本地缓存重新输出，不调用远程服务……");
    node.mode = 0;
    if (previousResult && !node.widgets?.includes(previousResult)) {
      node.widgets.splice(Math.min(previousResultIndex, node.widgets.length), 0, previousResult);
    }
    try {
      await queueCurrentOutputs(requestInputs);
    } catch (error) {
      requestState.running = false;
      button.disabled = false;
      reviseButton.disabled = false;
      cacheButton.disabled = false;
      clearButton.disabled = false;
      updateRevisionAvailability();
      setStatus(`缓存输出失败：${describeSubmissionError(error)}`, "error");
    } finally {
      // User-authored modification text is never changed for cache output.
      node.mode = 0;
    }
  };
  function clearCachedResult() {
    if (requestState.running) {
      setStatus("当前AIPM请求仍在执行，完成后才能清空结果。", "");
      return;
    }
    const modification = node.widgets?.find((widget) =>
      widget.name === "修改意见" || widget.name === "遇到的问题与修改目标"
    );
    node.properties ||= {};
    node.properties.aipm_previous_result = "";
    node.properties.aipm_target_segment_id = "";
    if (previousResult) previousResult.value = "";
    if (videoPromptPreview) videoPromptPreview.value = "";
    // Clear result displays only. The authored timeline is an independent
    // document and must not be blanked through its connected STRING input.
    const graph = node.graph || app.graph || app.rootGraph;
    for (const source of node.outputs || []) {
      for (const linkId of source?.links || []) {
        const link = graph?.links?.[linkId] || graph?.links?.get?.(linkId);
        const target = link ? graph?.getNodeById?.(link.target_id) : null;
        const type = String(target?.type || target?.comfyClass || "").toLowerCase();
        if (type.includes("showtext") || type.includes("displaytext") || type.includes("previewtext")) {
          target.onExecuted?.({ text: [""] });
          target.setDirtyCanvas?.(true, true);
        }
      }
    }
    app.graph?.change?.();
    updateRevisionAvailability();
    setStatus("已清空 AIPM 缓存与结果预览；时间轴内容保留。", "ok");
  };

  // The Vue property panel turns callbacks into value updates; a button has
  // no value, so the parent discards that update. Handle its forwarded DOM
  // activation directly and stop the synthetic path to prevent duplicates.
  for (const actionWidget of [button, reviseButton, cacheButton, clearButton]) {
    actionWidget.options.onClickCapture = (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      actionWidget.callback?.();
    };
  }

  const acceptResult = (output) => {
    // Only an explicit authoring/cache action may import a result. ComfyUI
    // dispatches the same result through onExecuted and the websocket event;
    // after the first acceptance requestState.running is false, so replay cannot overwrite
    // subsequent edits or import cached results during segment generation.
    if (!requestState.running || !Array.isArray(output?.text)) return;
    if (videoPromptPreview && output?.text?.[0] != null) {
      videoPromptPreview.value = String(output.text[0]);
      node.setDirtyCanvas?.(true, true);
    }
    writeTextToLinkedPreviews(node, output);
    const raw = output?.text?.[2];
    let authoring = null;
    let importError = "";
    if (raw) {
      node.properties ||= {};
      node.properties.aipm_previous_result = String(raw);
      if (previousResult) previousResult.value = String(raw);
      authoring = cachedAuthoring();
      if (authoring?.generation_status !== "interrupted") {
        const resultOperation = String(authoring?.aipm_operation || "");
        const writeStrategy = requestState.currentAction === "revise" || resultOperation === "revise_segment"
          ? "revise_segment"
          : requestState.currentAction === "append" || resultOperation === "append"
            ? "append"
            : "rewrite";
        try {
          const importedCount = writeResultToLinkedCineTimelines(
            node, raw, writeStrategy,
            String(node.properties?.aipm_target_segment_id || ""),
          );
          if (isVideo && importedCount === 0 && writeStrategy === "rewrite") {
            throw new Error("未找到可接收结果的时间轴，请检查完整结果 JSON 连线与时间轴模式；结果已保留在 AIPM 缓存。");
          }
        } catch (error) {
          importError = String(error?.message || error);
        }
      }
    }
    app.graph?.change?.();
    updateRevisionAvailability();
    if (!requestState.running) return;
    requestState.running = false;
    delete node.properties.aipm_pending_request;
    button.disabled = false;
    reviseButton.disabled = false;
    cacheButton.disabled = false;
    clearButton.disabled = false;
    button.name = isRefinement
      ? "分析并细化"
      : authoring?.generation_status === "interrupted" ? "继续生成" : "生成 / 重新创作";
    reviseButton.name = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
    if (importError) {
      setStatus(`结果已缓存，但未导入时间轴：${importError}`, "error");
    } else if (authoring?.generation_status === "interrupted") {
      const next = Number(authoring?.resume_from_segment || 1);
      setStatus(`第 ${next} 段连续失败 2 次，已保留前面完成的分段；再次点击“继续生成”将从本段继续。`, "error");
    } else setStatus(requestState.currentAction === "cache"
      ? "缓存已重新输出，未调用远程服务。"
      : requestState.currentAction === "revise"
        ? "提示词优化完成，已保存为新的有效版本。"
        : requestState.currentAction === "resume"
          ? "剩余分段生成完成，已保存完整结果。"
          : requestState.currentAction === "append"
            ? "续写分段已追加到AIPM缓存与已连接时间轴。"
          : "提示词生成完成，已保存为上次有效结果。", "ok");
  };
  // Explicit recovery only: never import arbitrary history on page load.
  const recoverHistory = async () => {
    if (requestState.running) { setStatus("当前请求仍在跟踪，请等待结束。", ""); return; }
    const id = globalThis.prompt("输入需要恢复的 AIPM 任务编号（不会调用远程服务）", node.properties?.aipm_pending_request?.id || "");
    if (!id || !/^[0-9a-f-]{36}$/i.test(id.trim())) return;
    try {
      const response = await api.fetchApi("/history/" + encodeURIComponent(id.trim()));
      if (!response.ok) throw new Error("读取任务历史失败");
      const item = (await response.json())[id.trim()];
      const original = item?.prompt?.[2]?.[String(node.id)];
      const submitted = item?.prompt?.[3]?.extra_pnginfo?.workflow;
      const graphId = (node.graph || app.graph)?.id;
      if (original?.class_type !== "AIPMVideoPrompt" || submitted?.id !== graphId) {
        throw new Error("任务不属于当前工作流的这个 AIPM 节点，未导入。");
      }
      const output = item?.outputs?.[String(node.id)];
      if (!Array.isArray(output?.text) || !output.text[2]) throw new Error("任务尚无可恢复结果");
      if (!globalThis.confirm("恢复此结果将替换当前连接时间轴的内容，继续吗？")) return;
      requestState.activePromptId = id.trim();
      requestState.currentAction = "generate";
      requestState.running = true;
      acceptResult(output);
    } catch (error) {
      requestState.running = false;
      setStatus("恢复失败：" + String(error?.message || error), "error");
    }
  };
  if (isVideo) {
    const recoveryButton = keepRuntimeOnly(node.addWidget("button", "按任务编号恢复结果", null, recoverHistory, { serialize: false }));
    recoveryButton.options.onClickCapture = event => {
      event.preventDefault(); event.stopImmediatePropagation(); recoverHistory();
    };
  }
  const scopeEvent = (callback) => {
    const scoped = (event) => {
      if (!requestState.running) return;
      if (!requestState.activePromptId) {
        if (requestState.pendingQueueEvents.length < 128) requestState.pendingQueueEvents.push([scoped, event]);
        return;
      }
      if (String(event?.detail?.prompt_id || "") !== requestState.activePromptId) return;
      callback(event);
    };
    return scoped;
  };
  const executed = scopeEvent(({ detail }) => {
    if (String(detail?.node ?? detail?.display_node ?? "") !== String(node.id)) return;
    acceptResult(detail?.output);
  });
  const failed = scopeEvent(({ detail }) => {
    requestState.running = false;
    button.disabled = false;
    reviseButton.disabled = false;
    cacheButton.disabled = false;
    clearButton.disabled = false;
    button.name = isRefinement ? "分析并细化" : "生成 / 重新创作";
    reviseButton.name = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
    updateRevisionAvailability();
    setStatus(`生成失败：${detail?.exception_message || detail?.message || "请查看执行错误"}`, "error");
  });
  const completedWithoutNodeResult = scopeEvent(() => {
    setTimeout(() => {
      if (!requestState.running) return;
      requestState.running = false;
      button.disabled = false;
      clearButton.disabled = false;
      updateRevisionAvailability();
      setStatus("本次队列已经结束，但没有收到新的AIPM结果；按钮已自动恢复，请检查任务队列或再次提交。", "error");
    }, 0);
  });
  api.addEventListener("executed", executed);
  api.addEventListener("execution_error", failed);
  api.addEventListener("execution_success", completedWithoutNodeResult);
  api.addEventListener("execution_interrupted", completedWithoutNodeResult);

  const originalNodeExecuted = node.onExecuted;
  const nodeExecuted = function (output) {
    const result = originalNodeExecuted?.apply(this, arguments);
    // This callback has no prompt_id. The scoped websocket handler is the
    // authoritative importer, so callbacks from another queue cannot replay data.
    return result;
  };
  node.onExecuted = nodeExecuted;
  const originalSerialize = node.onSerialize;
  const serialize = function () {
    if (previousResult && Object.prototype.hasOwnProperty.call(this.properties || {}, "aipm_previous_result")) {
      previousResult.value = String(this.properties.aipm_previous_result || "");
    }
    return originalSerialize?.apply(this, arguments);
  };
  node.onSerialize = serialize;

  updateRevisionAvailability();
  const cleanup = () => {
    api.removeEventListener("executed", executed);
    api.removeEventListener("execution_error", failed);
    api.removeEventListener("execution_success", completedWithoutNodeResult);
    api.removeEventListener("execution_interrupted", completedWithoutNodeResult);
    if (node.onExecuted === nodeExecuted) node.onExecuted = originalNodeExecuted;
    if (node.onSerialize === serialize) node.onSerialize = originalSerialize;
  };
  let panelRoot = null;
  let panelWidget = null;
  if (isImage) {
    // Canvas-native button hit testing can be lost in large workflows with
    // overlapping groups/DOM widgets. Use real DOM buttons for image prompt
    // actions while preserving the same callbacks and status widget.
    for (const actionWidget of [button, reviseButton, cacheButton, clearButton]) {
      actionWidget.hidden = true;
      actionWidget.computeSize = () => [0, -4];
    }
    panelRoot = document.createElement("div");
    panelRoot.className = "aipm-image-actions-v76";
    Object.assign(panelRoot.style, {
      display: "grid", gridTemplateColumns: "1fr", gridAutoRows: "20px",
      alignContent: "start", gap: "2px", boxSizing: "border-box",
      width: "100%", height: "86px", maxHeight: "86px", padding: "0",
      pointerEvents: "auto", overflow: "hidden",
    });
    const actions = [
      ["生成 / 重新创作", () => run(false)],
      ["按修改意见优化", () => run(true)],
      ["输出缓存", () => cacheButton.callback?.()],
      ["清空结果", () => clearButton.callback?.()],
    ];
    for (const [label, action] of actions) {
      const domButton = document.createElement("button");
      domButton.type = "button";
      domButton.textContent = label;
      Object.assign(domButton.style, {
        width: "100%", height: "20px", minHeight: "20px", padding: "0 6px",
        font: "inherit", lineHeight: "18px", border: "1px solid #555",
        borderRadius: "3px", background: "#252525", color: "#ddd",
        cursor: "pointer", pointerEvents: "auto",
      });
      domButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        action();
      });
      panelRoot.append(domButton);
    }
    panelWidget = node.addDOMWidget?.("aipm_image_actions", "AIPMImageActions", panelRoot, {
      serialize: false, hideOnZoom: false, getMinHeight: () => 86,
    }) || null;
    if (panelWidget) {
      panelWidget.computeSize = (width) => [width, 86];
      keepRuntimeOnly(panelWidget);
    }
  }
  node._aipmGeneratePanel = {
    version: VERSION, root: panelRoot, widget: panelWidget, nativeWidgets, cleanup,
  };
  const originalRemoved = node.onRemoved;
  node.onRemoved = function () {
    cleanup();
    return originalRemoved?.apply(this, arguments);
  };
  requestAnimationFrame(() => {
    node._aipmFitContentInput?.();
    const currentWidth = Number(node.size?.[0]) || 430;
    const computedHeight = Number(node.computeSize?.([currentWidth, 0])?.[1]) || 0;
    const requiredHeight = Math.max(computedHeight, 300);
    const currentHeight = Number(node.size?.[1]) || 0;
    // Preserve saved height; only grow nodes too short for fixed controls.
    if (currentHeight < requiredHeight) {
      node.setSize?.([currentWidth, requiredHeight]);
    }
    app.graph?.setDirtyCanvas(true, true);
  });
}

app.registerExtension({
  name: "AIPM.GenerateButton",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!["AIPMImagePrompt", "AIPMVideoPrompt", "AIPMPromptRefinement"].includes(nodeData.name)) return;
    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      this._aipmLoadedFromWorkflow = true;
      // Workflow values are restored positionally. Runtime-only controls may
      // already have been added by onNodeCreated, so remove them before the
      // core loader assigns widgets_values, then rebuild them afterwards.
      removeOldPanel(this);
      const result = originalConfigure?.apply(this, arguments);
      migrateReferenceInputNames(this);
      syncDynamicReferenceInputs(this);
      migrateModelNameWidget(this);
      migrateImageModelDefault(this);
      migrateVideoTargetModel(this);
      migrateImageReferencePurpose(this);
      migrateVideoGenerationMode(this);
      migrateShiftedCachedResult(this);
      migrateVideoDurationWidget(this);
      configureStableNodeLayout(this);
      installGeneratePanel(this);
      return result;
    };
    const original = nodeType.prototype.onNodeCreated;
    const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
      const result = originalConnectionsChange?.apply(this, arguments);
      requestAnimationFrame(() => syncDynamicReferenceInputs(this));
      return result;
    };
    nodeType.prototype.onNodeCreated = function () {
      const result = original?.apply(this, arguments);
      requestAnimationFrame(() => {
        migrateReferenceInputNames(this);
        syncDynamicReferenceInputs(this);
        migrateModelNameWidget(this);
        migrateImageModelDefault(this);
        migrateVideoTargetModel(this);
        migrateImageReferencePurpose(this);
        migrateVideoGenerationMode(this);
        migrateShiftedCachedResult(this);
        migrateVideoDurationWidget(this);
        configureStableNodeLayout(this);
        installGeneratePanel(this);
      });
      return result;
    };
  },
});

}
