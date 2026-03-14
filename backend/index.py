from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "AI Healthcare Backend Running"}
