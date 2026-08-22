from fastapi import FastAPI

app = FastAPI(title="Timepay Analytics")


@app.get("/")
def read_root():
    return {"message": "Hello World"}
