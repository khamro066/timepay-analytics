from fastapi import FastAPI

from app.api.analytics import router as analytics_router

app = FastAPI(title="Timepay Analytics")
app.include_router(analytics_router)


@app.get("/")
def read_root():
    return {"message": "Hello World"}
