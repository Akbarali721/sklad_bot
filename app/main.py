from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from .routers import admin, dealer
from .routers import auth, panel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Sklad Mini WebApp")

# jadval yaratish
Base.metadata.create_all(bind=engine)

# statik
app.mount("/static", StaticFiles(directory="static"), name="static")

# marshrutlar
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(dealer.router)
app.include_router(panel.router)

@app.get("/")
def root():
    return {"ok": True, "app": "sklad-mini-webapp", "routes": ["/admin", "/dealer/start"]}
