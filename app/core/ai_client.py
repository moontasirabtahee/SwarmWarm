import os
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger("swarmwarm.ai_client")

# Load environment configs
load_dotenv()

class AIClientError(Exception):
    """Custom exception raised on localized inference tunnel errors."""
    pass

class AIClient:
    """
    Asynchronous connection client responsible for routing generation prompts
    down through secure proxy tunnels to the local Gemma 4B runtime.
    """
    def __init__(self):
        self.tunnel_url = os.getenv("LOCAL_AI_TUNNEL_URL", "http://localhost:11434")
        self.api_key = os.getenv("LOCAL_AI_API_KEY", "")
        
        # Configure request headers (useful for custom ngrok or Cloudflare authentication)
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            
    async def generate(self, model: str, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        """
        Sends asynchronous inference requests to the local Ollama/vLLM server.
        """
        url = f"{self.tunnel_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        logger.info(f"Dispatching inference POST request to: {url} (Model: {model}, Temp: {temperature})")
        
        # Set a generous timeout (e.g. 45 seconds) to accommodate local GPU latency on first token runs
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                
                # Check for HTTP errors
                if response.status_code != 200:
                    raise AIClientError(f"Local AI endpoint returned error status {response.status_code}: {response.text}")
                    
                data = response.json()
                return data.get("response", "").strip()
                
            except httpx.ConnectError as conn_err:
                logger.error(f"Failed to connect to local tunnel: {conn_err}")
                raise AIClientError(f"Could not connect to the local inference tunnel at {self.tunnel_url}. Check if your proxy is running.")
                
            except httpx.TimeoutException as timeout_err:
                logger.error(f"Inference request timed out: {timeout_err}")
                raise AIClientError("Local inference client request timed out. Local hardware may be under high load.")
                
            except Exception as e:
                logger.error(f"Unhandled HTTP error during inference: {e}")
                raise AIClientError(f"AI Client transaction failed: {e}")
