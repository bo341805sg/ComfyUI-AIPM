import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const VERSION = 38;
const AIPM_MIN_WIDTH = 480;
const REVISION_MARKER = "__AIPM_REVISION_V1__";
const RUN_MARKER = "__AIPM_RUN_V1__";

function removeOldPanel(node) {
  const oldPanel = node._aipmGeneratePanel;
  if (!oldPanel) return;
  oldPanel.cleanup?.();
  oldPanel.root?.remove?.();
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

function writeResultToLinkedCineTimelines(node, rawTimelineJson) {
  const raw = String(rawTimelineJson || "").trim();
  if (!raw || String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return 0;
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.schema !== "cine_timeline" || !Array.isArray(parsed?.shots)) return 0;
  } catch {
    return 0;
  }
  const jsonOutput = (node.outputs || []).find((output) => output?.name === "完整结果 JSON");
  let updated = 0;
  for (const linkId of jsonOutput?.links || []) {
    const link = app.graph?.links?.[linkId] || app.graph?.links?.get?.(linkId);
    const target = link ? app.graph?.getNodeById?.(link.target_id) : null;
    if (!target || !["CineTimelinePlan", "CineTimelineStudio", "CineTimelineEditor"].includes(String(target.comfyClass || target.type || ""))) continue;
    const targetInput = target.inputs?.[link.target_slot];
    if (targetInput?.name !== "timeline_json") continue;
    const timelineWidget = target.widgets?.find((widget) => widget.name === "timeline_state");
    if (!timelineWidget) continue;
    try {
      const current = JSON.parse(String(timelineWidget.value || "{}"));
      if (String(current?.metadata?.render_target_shot_id || "").trim()) continue;
    } catch {}
    timelineWidget.value = raw;
    timelineWidget.callback?.(raw);
    target.cineTimelineEditor?.reloadState?.();
    target.setDirtyCanvas?.(true, true);
    updated += 1;
  }
  if (updated) app.graph?.change?.();
  return updated;
}

function migrateVideoDurationWidget(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMVideoPrompt") return;
  const widget = node.widgets?.find((item) => item.name === "视频时长");
  if (!widget) return;
  const matched = String(widget.value ?? "").match(/\d+/);
  const seconds = Math.max(4, Math.min(15, matched ? Number(matched[0]) : Number(widget.value) || 5));
  widget.value = seconds;
  widget.type = "number";
  widget.options = {
    ...(widget.options || {}), min: 4, max: 15, step: 1, precision: 0,
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
  delete node.properties.aipm_locked_width;

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
  if (widget?.value === "自动判断 / 通用（推荐）") {
    widget.value = "Krea 2 / Krea 2 Turbo 系列";
  }
}

function migrateImageReferencePurpose(node) {
  if (String(node?.comfyClass || node?.type || "") !== "AIPMImagePrompt") return;
  const widget = node.widgets?.find((item) => item.name === "参考图用途");
  if (widget && !["多参考改图", "仅分析参考"].includes(String(widget.value || ""))) {
    widget.value = "多参考改图";
  }
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
    && ["aipm_video_prompt", "cine_timeline"].includes(parsed?.schema);
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
  let running = false;
  let currentAction = "generate";
  const isRefinement = String(node?.comfyClass || node?.type || "") === "AIPMPromptRefinement";
  const previousResult = node.widgets?.find((item) => item.name === "上次结果JSON");
  const referenceManifest = node.widgets?.find((item) => item.name === "参考素材清单JSON");
  const previousResultIndex = Math.max(node.widgets?.indexOf(previousResult) ?? -1, 0);
  node.properties ||= {};
  if (!node.properties.aipm_previous_result && String(previousResult?.value || "").trim()) {
    node.properties.aipm_previous_result = String(previousResult.value);
  }
  hideInternalWidget(previousResult);
  hideInternalWidget(referenceManifest);

  const root = document.createElement("div");
  root.className = "aipm-generate-panel";
  root.innerHTML = `<style>
    .aipm-generate-panel{box-sizing:border-box;width:100%;padding:7px 4px 11px;font:12px Inter,system-ui,sans-serif}
    .aipm-generate-panel .actions{display:grid;width:100%;min-width:0;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
    .aipm-generate-panel button{box-sizing:border-box;min-width:0;width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:7px 10px;border:1px solid #59759d;border-radius:6px;background:#293b55;color:#f3f7ff;font-weight:650;cursor:pointer}
    .aipm-generate-panel button.secondary{background:#3a334e;border-color:#75638f}
    .aipm-generate-panel button.clear{margin-top:6px;padding:4px 8px;background:transparent;border-color:#536273;color:#b9c5d4;font-weight:500}
    .aipm-generate-panel button:hover{background:#354e70}.aipm-generate-panel button:disabled{opacity:.5;cursor:default}
    .aipm-generate-panel .status{min-height:18px;padding:0 2px 5px;color:#aebdd0;white-space:normal;line-height:1.35}
    .aipm-generate-panel .status.ok{color:#74d69b}.aipm-generate-panel .status.error{color:#ff8e98}
  </style>`;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = isRefinement ? "分析并细化" : "生成 / 重新创作";
  const reviseButton = document.createElement("button");
  reviseButton.type = "button";
  reviseButton.className = "secondary";
  reviseButton.textContent = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
  const cacheButton = document.createElement("button");
  cacheButton.type = "button";
  cacheButton.className = "secondary";
  cacheButton.textContent = "输出缓存";
  const clearButton = document.createElement("button");
  clearButton.type = "button";
  clearButton.className = "clear";
  clearButton.textContent = "清空结果";
  const status = document.createElement("div");
  status.className = "status";
  status.textContent = "仅执行当前节点，不触发工作流其他生成节点。";
  const actions = document.createElement("div");
  actions.className = "actions";
  actions.append(button, reviseButton, cacheButton);
  root.append(status, actions, clearButton);

  const setStatus = (message, type = "") => {
    status.textContent = message;
    status.className = `status ${type}`;
    app.graph?.setDirtyCanvas(true, true);
  };

  const updateRevisionAvailability = () => {
    const hasCache = Boolean(String(node.properties?.aipm_previous_result || "").trim());
    reviseButton.disabled = running || !hasCache;
    cacheButton.disabled = running || !hasCache;
  };

  const queueCurrentOutputs = async () => {
    const previewNodeIds = new Set();
    for (const output of node.outputs || []) {
      for (const linkId of output?.links || []) {
        const link = app.graph?.links?.[linkId];
        const target = link ? app.graph?.getNodeById?.(link.target_id) : null;
        const type = String(target?.type || target?.comfyClass || "").toLowerCase();
        if (type.includes("showtext") || type.includes("displaytext") || type.includes("previewtext")) {
          previewNodeIds.add(String(target.id));
        }
      }
    }
    const executionTargets = previewNodeIds.size ? [...previewNodeIds] : [String(node.id)];
    await app.queuePrompt(0, 1, executionTargets);
  };

  const run = async (revise = false) => {
    if (running) return;
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
    if (revise && !String(modification?.value || "").trim()) {
      setStatus("请先填写修改意见。", "error");
      return;
    }
    if (revise && !String(node.properties?.aipm_previous_result || "").trim()) {
      setStatus("还没有上次结果，请先生成一次提示词。", "error");
      return;
    }
    running = true;
    currentAction = revise ? "revise" : "generate";
    if (revise && modification) {
      modification.value = REVISION_MARKER + JSON.stringify({
        instruction: originalModification,
        previous_result: String(node.properties?.aipm_previous_result || ""),
      });
    } else {
      if (modification) modification.value = isRefinement
        ? `${RUN_MARKER}${originalModification}`
        : `${RUN_MARKER}${Date.now()}`;
      if (previousResult) previousResult.value = "";
    }
    if (referenceManifest) {
      referenceManifest.value = JSON.stringify(collectReferenceAssetManifest(node));
    }
    button.disabled = true;
    reviseButton.disabled = true;
    cacheButton.disabled = true;
    clearButton.disabled = true;
    setStatus(revise ? "正在保留未修改内容并定向优化……" : "正在分析输入并生成专业提示词……");
    const previousMode = node.mode;
    node.mode = 0;
    if (previousResult && !node.widgets?.includes(previousResult)) {
      node.widgets.splice(Math.min(previousResultIndex, node.widgets.length), 0, previousResult);
    }
    try {
      await queueCurrentOutputs();
    } catch (error) {
      running = false;
      button.disabled = false;
      reviseButton.disabled = false;
      cacheButton.disabled = false;
      clearButton.disabled = false;
      button.textContent = isRefinement ? "分析并细化" : "生成 / 重新创作";
      reviseButton.textContent = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
      updateRevisionAvailability();
      setStatus(`提交失败：${error?.message || error}`, "error");
    } finally {
      // The revision field is user-authored working text. Keep it after every
      // submission so the user can refine or reuse the same instruction.
      if (modification) modification.value = originalModification;
      node.mode = previousMode;
    }
  };
  button.onclick = () => run(false);
  reviseButton.onclick = () => run(true);
  cacheButton.onclick = async () => {
    if (running) return;
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
    running = true;
    currentAction = "cache";
    if (previousResult) previousResult.value = cached;
    if (modification && !isRefinement) modification.value = "";
    button.disabled = true;
    reviseButton.disabled = true;
    cacheButton.disabled = true;
    clearButton.disabled = true;
    setStatus("正在从本地缓存重新输出，不调用远程服务……");
    const previousMode = node.mode;
    node.mode = 0;
    if (previousResult && !node.widgets?.includes(previousResult)) {
      node.widgets.splice(Math.min(previousResultIndex, node.widgets.length), 0, previousResult);
    }
    try {
      await queueCurrentOutputs();
    } catch (error) {
      running = false;
      button.disabled = false;
      reviseButton.disabled = false;
      cacheButton.disabled = false;
      clearButton.disabled = false;
      updateRevisionAvailability();
      setStatus(`缓存输出失败：${error?.message || error}`, "error");
    } finally {
      if (modification) modification.value = originalModification;
      node.mode = previousMode;
    }
  };
  clearButton.onclick = () => {
    if (running) return;
    const modification = node.widgets?.find((widget) =>
      widget.name === "修改意见" || widget.name === "遇到的问题与修改目标"
    );
    node.properties ||= {};
    node.properties.aipm_previous_result = "";
    if (previousResult) previousResult.value = "";
    app.graph?.change?.();
    updateRevisionAvailability();
    setStatus("已清空上次结果，下一次将重新创作。", "ok");
  };

  const acceptResult = (output) => {
    const raw = output?.text?.[2];
    if (raw) {
      node.properties ||= {};
      node.properties.aipm_previous_result = String(raw);
      if (previousResult) previousResult.value = String(raw);
      writeResultToLinkedCineTimelines(node, raw);
    }
    app.graph?.change?.();
    updateRevisionAvailability();
    if (!running) return;
    running = false;
    button.disabled = false;
    reviseButton.disabled = false;
    cacheButton.disabled = false;
    clearButton.disabled = false;
    button.textContent = isRefinement ? "分析并细化" : "生成 / 重新创作";
    reviseButton.textContent = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
    setStatus(currentAction === "cache"
      ? "缓存已重新输出，未调用远程服务。"
      : currentAction === "revise"
        ? "提示词优化完成，已保存为新的有效版本。"
        : "提示词生成完成，已保存为上次有效结果。", "ok");
  };
  const executed = ({ detail }) => {
    if (String(detail?.node ?? detail?.display_node ?? "") !== String(node.id)) return;
    acceptResult(detail?.output);
  };
  const failed = ({ detail }) => {
    const failedNode = String(detail?.node_id ?? detail?.node ?? "");
    if (!running || (failedNode && failedNode !== String(node.id))) return;
    running = false;
    button.disabled = false;
    reviseButton.disabled = false;
    cacheButton.disabled = false;
    clearButton.disabled = false;
    button.textContent = isRefinement ? "分析并细化" : "生成 / 重新创作";
    reviseButton.textContent = isRefinement ? "根据新意见继续细化" : "按修改意见优化";
    updateRevisionAvailability();
    setStatus(`生成失败：${detail?.exception_message || detail?.message || "请查看执行错误"}`, "error");
  };
  api.addEventListener("executed", executed);
  api.addEventListener("execution_error", failed);

  const originalNodeExecuted = node.onExecuted;
  const nodeExecuted = function (output) {
    const result = originalNodeExecuted?.apply(this, arguments);
    acceptResult(output);
    return result;
  };
  node.onExecuted = nodeExecuted;
  const originalSerialize = node.onSerialize;
  const serialize = function () {
    if (previousResult && String(this.properties?.aipm_previous_result || "").trim()) {
      previousResult.value = String(this.properties.aipm_previous_result);
    }
    return originalSerialize?.apply(this, arguments);
  };
  node.onSerialize = serialize;

  const widget = node.addDOMWidget("aipm_generate", "AIPMGenerate", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => 108,
  });
  widget.computeSize = (width) => [width, 112];
  updateRevisionAvailability();
  const cleanup = () => {
    api.removeEventListener("executed", executed);
    api.removeEventListener("execution_error", failed);
    if (node.onExecuted === nodeExecuted) node.onExecuted = originalNodeExecuted;
    if (node.onSerialize === serialize) node.onSerialize = originalSerialize;
  };
  node._aipmGeneratePanel = { version: VERSION, root, widget, cleanup };
  requestAnimationFrame(() => syncGeneratePanelWidth(node));
  const originalRemoved = node.onRemoved;
  node.onRemoved = function () {
    cleanup();
    return originalRemoved?.apply(this, arguments);
  };
  requestAnimationFrame(() => {
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
      const result = originalConfigure?.apply(this, arguments);
      migrateReferenceInputNames(this);
      migrateModelNameWidget(this);
      migrateImageModelDefault(this);
      migrateImageReferencePurpose(this);
      migrateShiftedCachedResult(this);
      return result;
    };
    const original = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = original?.apply(this, arguments);
      requestAnimationFrame(() => {
        migrateReferenceInputNames(this);
        migrateModelNameWidget(this);
        migrateImageModelDefault(this);
        migrateImageReferencePurpose(this);
        migrateShiftedCachedResult(this);
        migrateVideoDurationWidget(this);
        configureStableNodeLayout(this);
        installGeneratePanel(this);
      });
      return result;
    };
  },
});
