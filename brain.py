import os
import httpx
import json
import logging

logger = logging.getLogger("Adjnt.Brain")

class AdjntBrain:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/api/generate")
        self.model = "llama3.2"

    async def decide(self, text):
        prompt = f"""
        Analyze this message: "{text}"
        Respond in JSON only with 'intent' (TASK, PRIVACY, or CHAT) and 'data'.
        If TASK, include 'item'. If CHAT, include 'answer'.
        Example: {{"intent": "CHAT", "data": {{"answer": "Hello!"}}}}
        """
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.ollama_url, json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json" # This tells Ollama to force JSON
                })
                
                # STEP 1: Get the outer Ollama response
                full_json = response.json() 
                
                # STEP 2: The actual AI content is inside the 'response' field as a STRING
                content_string = full_json.get('response', '{}')
                
                # STEP 3: Convert that string into a Python dictionary
                return json.loads(content_string)
                
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return {"intent": "CHAT", "data": {"answer": "I'm having trouble thinking."}}