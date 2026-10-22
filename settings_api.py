from urllib.parse import urlsplit
from aiohttp import web
from server import PromptServer
from . import connection_settings as settings

def allowed(request):
    origin = request.headers.get('Origin')
    return not origin or urlsplit(origin).netloc == request.host

@PromptServer.instance.routes.get('/aipm/connection')
async def get_connection(request):
    if not allowed(request):
        return web.json_response({'error': 'Origin not allowed'}, status=403)
    return web.json_response(settings.public(), headers={'Cache-Control': 'no-store'})

@PromptServer.instance.routes.post('/aipm/connection')
async def set_connection(request):
    if not allowed(request):
        return web.json_response({'error': 'Origin not allowed'}, status=403)
    try:
        changes = await request.json()
        result = settings.save(changes)
    except (ValueError, TypeError):
        return web.json_response({'error': '配置无效：请检查服务地址、模型 ID 和密钥；不要填写换行。'}, status=400)
    return web.json_response(result, headers={'Cache-Control': 'no-store'})
