"""Server-side connection settings. Secrets never belong to a workflow."""
import json
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

_lock = threading.RLock()
DEFAULTS = {"service_url": "http://192.168.10.27:8080/v1", "model_id": "Huihui-Qwen3.8-27B-abliterated-Q5_K.gguf", "api_key": ""}

def config_path():
    if os.getenv("AIPM_CONFIG_PATH"):
        return Path(os.environ["AIPM_CONFIG_PATH"])
    import folder_paths
    return Path(folder_paths.get_user_directory()) / "default" / "AIPM" / "connection.json"

def load():
    with _lock:
        path = config_path()
        if not path.exists():
            return dict(DEFAULTS)
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("AIPM 本地连接配置格式无效")
        return {key: str(data.get(key, default)) for key, default in DEFAULTS.items()}

def effective_key(settings):
    return settings["api_key"].strip() or os.getenv("AIPM_API_KEY", "").strip() or os.getenv("PROMPT_ASSISTANT_API_KEY", "").strip()

def public():
    data = load()
    return {"service_url": data["service_url"], "model_id": data["model_id"], "has_api_key": bool(effective_key(data))}

def save(changes):
    if not isinstance(changes, dict) or set(changes) - set(DEFAULTS):
        raise ValueError("AIPM 连接配置字段无效")
    if any(not isinstance(value, str) for value in changes.values()):
        raise ValueError("AIPM 连接配置必须为文本")
    with _lock:
        data = load()
        data.update({key: value.strip() for key, value in changes.items()})
        url = urlsplit(data["service_url"])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("服务地址须为完整的 http(s) 地址，例如 http://127.0.0.1:8080/v1")
        if not data["model_id"] or any(c in ''.join(data.values()) for c in ('\r', '\n', '\x00')):
            raise ValueError("模型 ID 不能为空，配置不能包含换行或空字符")
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".connection-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, indent=2)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return public()

def api_key_for(service_url):
    data = load()
    # Never forward a saved credential to an unrelated endpoint.
    normalize = lambda value: str(value).rstrip('/').removesuffix('/chat/completions').rstrip('/')
    return effective_key(data) if normalize(service_url) == normalize(data['service_url']) else ''

def configure_nodes(mapping):
    import functools
    import inspect
    for name in ('AIPMImagePrompt', 'AIPMVideoPrompt', 'AIPMPromptRefinement'):
        cls = mapping[name]
        original_inputs = cls.INPUT_TYPES
        def inputs(original=original_inputs):
            schema = original()
            for section in ('required', 'optional'):
                for field in ('远程服务地址', '模型名称', '服务模型'):
                    schema.get(section, {}).pop(field, None)
            return schema
        cls.INPUT_TYPES = classmethod(lambda cls, fn=inputs: fn())
        def changed(cls, **kwargs):
            import hashlib
            settings = load()
            settings['api_key'] = effective_key(settings)
            settings['prompt_contract_version'] = getattr(cls, 'H3_CONTRACT_VERSION', '')
            return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
        cls.IS_CHANGED = classmethod(changed)
        method = getattr(cls, cls.FUNCTION)
        signature = inspect.signature(method)
        def wrap(method, signature):
            @functools.wraps(method)
            def run(self, *args, **kwargs):
                bound = signature.bind_partial(self, *args, **kwargs)
                settings = load()
                bound.arguments['远程服务地址'] = settings['service_url']
                bound.arguments['模型名称'] = settings['model_id']
                return method(*bound.args, **bound.kwargs)
            return run
        setattr(cls, cls.FUNCTION, wrap(method, signature))
