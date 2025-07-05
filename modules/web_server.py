import os
import asyncio
from aiohttp import web
from modules.app_config import env_config  # Імпортуємо env_config для доступу до LARDI_COOKIE
from modules.lardi_api_client import LardiOfferClient  # Імпортуємо LardiOfferClient

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), 'webapp')

lardi_offer_client = LardiOfferClient()


async def webapp_handler(request):
    """
    Обробник запитів для Web App. Подає HTML-файл.
    Замінює плейсхолдер WEBAPP_API_PROXY_URL у HTML.
    HTML-файл відповідає за отримання ID вантажу з параметрів URL
    та здійснення клієнтського запиту до проксі-API.
    """
    file_path = os.path.join(WEBAPP_DIR, 'cargo_details.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Замінюємо плейсхолдер у HTML на реальний URL проксі-API
        # Це дозволить JavaScript на клієнті знати, куди відправляти запит за даними.
        html_content = html_content.replace(
            "{{WEBAPP_API_PROXY_URL}}",
            env_config.WEBAPP_API_PROXY_URL
        )
        return web.Response(text=html_content, content_type='text/html')

    return web.Response(text="404: Not Found", status=404)


async def cargo_details_proxy_api(request):
    """
    Проксі-ендпоінт для отримання детальної інформації про вантаж з Lardi-Trans API.
    Використовує LARDI_COOKIE з серверного боку.
    Очікує cargo_id як параметр запиту 'id'.
    """
    cargo_id = request.query.get('id')
    if not cargo_id:
        return web.json_response({"error": "Missing cargo ID"}, status=400)
    try:
        cargo_data = await lardi_offer_client.get_offer(int(cargo_id))
        return web.json_response(cargo_data)
    except Exception as e:
        print(f"Error fetching cargo details via proxy: {e}")
        return web.json_response({"error": f"Failed to fetch cargo details: {e}"}, status=500)


async def start_web_app():
    app = web.Application()
    # Маршрут для подачі HTML-сторінки Web App
    app.router.add_get('/webapp/cargo_details.html', webapp_handler)
    # Маршрут для проксі-API
    app.router.add_get('/api/cargo_details', cargo_details_proxy_api)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Слухаємо на порту 8080
    print("Web server started on http://0.0.0.0:8080")
    await site.start()


if __name__ == '__main__':
    # Для запуску сервера web_server.py окремо
    asyncio.run(start_web_app())

