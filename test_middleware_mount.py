import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from starlette.testclient import TestClient

root_app = FastAPI()
sub_app = FastAPI()

@sub_app.get("/")
def sub_root():
    return {"message": "hello from sub"}

root_app.mount("/sub", sub_app)

@root_app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/sub") and not request.cookies.get("auth"):
        return PlainTextResponse("BLOCKED BY AUTH", status_code=401)
    return await call_next(request)

client = TestClient(root_app)
r1 = client.get("/sub/")
print("Without cookie status:", r1.status_code, r1.text)

r2 = client.get("/sub/", cookies={"auth": "valid"})
print("With cookie status:", r2.status_code, r2.json())
