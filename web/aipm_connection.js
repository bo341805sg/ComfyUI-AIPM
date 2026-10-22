import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

export function migrateConnectionSettings(graph) {
  const walk = (value) => {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value.nodes)) {
      const removedLinks = new Set();
      for (const node of value.nodes) {
        const index = { AIPMImagePrompt: 1, AIPMVideoPrompt: 1, AIPMPromptRefinement: 5 }[node.type];
        if (index === undefined) continue;
        const values = node.widgets_values;
        if (Array.isArray(values) && /^https?:\/\//i.test(String(values[index] || ""))) {
          values.splice(index, 2);
        }
        const remap = new Map();
        node.inputs = (node.inputs || []).filter((input, oldIndex) => {
          if (["远程服务地址", "模型名称", "服务模型"].includes(input.name)) {
            if (input.link != null) removedLinks.add(input.link);
            return false;
          }
          remap.set(oldIndex, remap.size); return true;
        });
        if (Array.isArray(value.links)) {
          for (const link of value.links) {
            if (Array.isArray(link) && link[3] === node.id && !removedLinks.has(link[0]) && remap.has(link[4])) link[4] = remap.get(link[4]);
          }
        }
      }
      if (Array.isArray(value.links)) value.links = value.links.filter(link => !removedLinks.has(Array.isArray(link) ? link[0] : link.id));
      for (const node of value.nodes) for (const output of node.outputs || []) {
        if (Array.isArray(output.links)) output.links = output.links.filter(id => !removedLinks.has(id));
      }
    }
    for (const [key, child] of Object.entries(value)) {
      if (key !== "widgets_values") {
        if (Array.isArray(child)) child.forEach(walk);
        else if (child && typeof child === "object") walk(child);
      }
    }
  };
  walk(graph);
}

app.registerExtension({
  name: "AIPM.ConnectionSettings",
  beforeConfigureGraph(graph) { migrateConnectionSettings(graph); },
  setup() {
    app.ui.settings.addSetting({
      id: "AIPM.Connection", name: "服务连接", category: ["AIPM", "服务", "连接"],
      type() {
        const row = document.createElement("tr");
        const cell = document.createElement("td"); cell.colSpan = 2; row.append(cell);
        const fields = {};
        for (const [key, label, type] of [["service_url", "服务地址（含 /v1）", "text"], ["model_id", "模型 ID", "text"], ["api_key", "API Key（留空保留已保存密钥）", "password"]]) {
          const caption = document.createElement("label"); caption.textContent = label;
          const input = document.createElement("input"); input.type = type; input.autocomplete = "off";
          input.style.cssText = "display:block;width:100%;margin:6px 0 12px;padding:8px;box-sizing:border-box";
          caption.append(input); cell.append(caption); fields[key] = input;
        }
        const clearLabel = document.createElement("label");
        const clear = document.createElement("input"); clear.type = "checkbox";
        clearLabel.append(clear, "清除本地保存的密钥（环境变量仍可生效）"); cell.append(clearLabel);
        const save = document.createElement("button"); save.textContent = "保存 AIPM 连接";
        save.style.cssText = "display:block;margin-top:12px;padding:8px";
        const status = document.createElement("div"); cell.append(save, status);
        save.disabled = true;
        api.fetchApi("/aipm/connection", { cache: "no-store" }).then(async response => {
          if (!response.ok) throw new Error();
          const data = await response.json();
          fields.service_url.value = data.service_url; fields.model_id.value = data.model_id;
          status.textContent = data.has_api_key ? "已配置密钥；所有 AIPM 节点共用此连接。" : "尚未配置密钥；无需鉴权的服务可留空。";
          save.disabled = false;
        }).catch(() => { status.textContent = "无法读取 AIPM 配置，请确认后端已重启。"; });
        save.onclick = async () => {
          save.disabled = true;
          const data = { service_url: fields.service_url.value, model_id: fields.model_id.value };
          if (clear.checked) data.api_key = "";
          else if (fields.api_key.value) data.api_key = fields.api_key.value;
          try {
            const response = await api.fetchApi("/aipm/connection", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
            if (!response.ok) throw new Error();
            fields.api_key.value = ""; clear.checked = false;
            status.textContent = "已保存，后续请求立即生效；密钥未写入工作流。";
          } catch { status.textContent = "保存失败，请检查服务地址、模型 ID 和后端日志。"; }
          finally { save.disabled = false; }
        };
        return row;
      },
    });
  },
});
