import sys
import uvicorn
from fastapi import FastAPI

app = FastAPI(
    title="SwarmWarm Local AI Tunnel Mock",
    description="Simulates the local inference engine (Gemma 4B) on Port 11434 to test proxy tunnels."
)

@app.get("/")
def read_root():
    return {"status": "online", "model": "gemma4b-mock", "msg": "Secure proxy tunnel connection confirmed."}

@app.post("/api/generate")
def generate_text(prompt: str = ""):
    # Mimics the Ollama generate endpoint format
    return {
        "model": "gemma4b-mock",
        "response": f"[MOCK INFERENCE RESPONSE] Generating response for: {prompt[:30]}...",
        "done": True
    }

def main():
    print("================================================================================")
    print("                 SWARMWARM LOCAL AI TUNNEL MOCK SERVER")
    print("================================================================================")
    print("Spinning up local mock inference interface on Port 11434...")
    print("Use Cloudflare Tunnel or ngrok to route public HTTPS requests to localhost:11434.")
    print("================================================================================")
    
    # Port 11434 is the default Ollama / Local AI interface engine port
    uvicorn.run(app, host="127.0.0.1", port=11434)

if __name__ == "__main__":
    main()
