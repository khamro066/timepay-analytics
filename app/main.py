from fastapi import FastAPI

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router

app = FastAPI(title="Timepay Analytics")
app.include_router(auth_router)
app.include_router(analytics_router)


@app.get("/")
def read_root():
    return {"message": "Hello World"}
