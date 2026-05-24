from fastapi import FastAPI

try:
    from src.routes import base, data
except ModuleNotFoundError:
    # Allow running from inside src/ as `python main.py`
    from routes import base, data

app = FastAPI()

app.include_router(base.base_router)
app.include_router(data.data_router)
