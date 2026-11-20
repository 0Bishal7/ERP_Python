from fastapi import FastAPI

app = FastAPI(title="ERP Backend")


@app.get("/")
def read_root():
    return {"message": "ERP backend is running"}
