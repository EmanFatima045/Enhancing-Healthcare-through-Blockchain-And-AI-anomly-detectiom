"""Print only the exception class when checking FastAPI startup in a deployment container."""

import asyncio

from .app.main import app


try:
    async def check():
        async with app.router.lifespan_context(app):
            print("lifespan-ok")
    asyncio.run(check())
except Exception as exc:  # diagnostic helper intentionally omits exception details
    print(f"startup-error:{type(exc).__module__}.{type(exc).__name__}")
    raise SystemExit(1)
