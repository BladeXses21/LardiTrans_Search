import os
from aiohttp import web

# Переконайтеся, що файл cargo_details.html знаходиться всередині цієї папки або її підпапок
WEBAPP_DIR = os.path.join(os.path.dirname(__file__), 'webapp')  # Припускаємо, що webapp папка на тому ж рівні, що й main.py


async def webapp_handler(request):
    """
    Обробник запитів для Web App. Подає HTML-файл.
    """
    file_path = os.path.join(WEBAPP_DIR, 'cargo_details.html')
    if os.path.exists(file_path):
        return web.FileResponse(file_path)
    else:
        return web.Response(text="Web App HTML file not found", status=404)


async def main():
    app = web.Application()
    # Додаємо маршрут для вашої HTML-сторінки.
    # Маршрут "/webapp/cargo_details.html" повинен відповідати WEBAPP_BASE_URL в app_config.py
    app.router.add_get('/webapp/cargo_details.html', webapp_handler)

    # Додаємо маршрут для статичних файлів, якщо у вас є CSS/JS файли окремо
    # Якщо все в одному HTML, цей маршрут може не знадобитися
    # app.router.add_static('/webapp/', WEBAPP_DIR)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Слухаємо на порту 8080
    print("Web server started on http://0.0.0.0:8080")
    await site.start()

    # Залишаємо сервер працювати
    while True:
        await asyncio.sleep(3600)  # Чекаємо 1 годину, щоб сервер не закрився


if __name__ == '__main__':
    import asyncio

    # Для запуску сервера web_server.py
    asyncio.run(main())
