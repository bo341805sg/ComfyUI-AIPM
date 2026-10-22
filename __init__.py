from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


if __package__:
    try:
        from server import PromptServer as _AIPMServer
    except ImportError:
        _AIPMServer = None
    if _AIPMServer is not None and _AIPMServer.instance is not None:
        from . import settings_api as _settings_api
