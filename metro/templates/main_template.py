main_template = """from metro import Metro
from contextlib import asynccontextmanager
from app.controllers import *


@asynccontextmanager
async def lifespan(app: Metro):
    app.connect_db()
    yield


app = Metro(lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
