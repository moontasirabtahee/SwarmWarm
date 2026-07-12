import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import auth, mailboxes, analytics, stream

app = FastAPI(
    title="SwarmWarm REST API Gateway",
    description=(
        "Production-grade control plane API for the SwarmWarm Multi-Tenant P2P Email Warmup Engine. "
        "Enables account credentials encryption, mailbox fleet CRUD controls, and real-time deliverability score analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for standard dashboard frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints routers
app.include_router(auth.router)
app.include_router(mailboxes.router)
app.include_router(analytics.router)
app.include_router(stream.router)

# Mount static folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", tags=["Gateway Status"])
async def root():
    """
    Serves the SwarmWarm frontend UI dashboard SPA.
    """
    return FileResponse("app/static/index.html")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
