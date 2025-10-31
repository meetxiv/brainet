"""
Groq Cloud API Client - Lightning-fast LLM inference.

This module provides async access to Groq's ultra-fast inference API.
Groq specializes in high-speed, low-latency LLM generation using custom hardware.

Why Groq:
- Speed: 500+ tokens/second (10x faster than typical cloud LLMs)
- Free tier: Generous rate limits for development
- Model: Llama 3.3 70B Versatile (open weights, excellent reasoning)
- OpenAI-compatible API for easy integration

Rate Limits (Free Tier):
- 30 requests/minute
- 7,000 tokens/minute
- Perfect for Brainet's summary + Q&A workload

Get API Key: https://console.groq.com
"""

import json
import aiohttp
from typing import Dict, Any, Optional

class GroqClient:
    """
    Async client for Groq Cloud API.
    
    Handles:
    - OpenAI-compatible chat completions
    - Automatic error handling and retries
    - Configurable temperature and token limits
    """
    
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq client with credentials.
        
        Args:
            api_key: Groq API key from https://console.groq.com
            model: Model identifier (default: llama-3.3-70b-versatile)
                   Alternative: llama-3.1-70b-versatile for higher throughput
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        self.temperature = 0.3  # Low temp for consistent technical summaries
    
    async def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        Generate completion via Groq API.
        
        Args:
            prompt: Input text for generation
            **kwargs: Override defaults:
                - model: Alternative model name
                - temperature: 0.0-2.0 (lower = more deterministic)
                - max_tokens: Response length limit
            
        Returns:
            Generated text string, or None if request fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": kwargs.get("model", self.model),
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", 500),
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"].strip()
                    else:
                        error_text = await response.text()
                        print(f"❌ Groq API error: Status {response.status}")
                        print(f"   {error_text}")
                        return None
        except aiohttp.ClientTimeout:
            print("❌ Groq API timeout (30s)")
            return None
        except Exception as e:
            print(f"❌ Error calling Groq API: {e}")
            return None
    
    async def generate_summary(self, context: str) -> Optional[str]:
        """Generate a summary of development context.
        
        Args:
            context: Development context to summarize
            
        Returns:
            Optional[str]: Generated summary
        """
        prompt = (
            "Analyze this development context and provide a concise summary "
            "focusing on current tasks, changes, and important patterns:\n\n"
            f"{context}"
        )
        
        return await self.generate(prompt, temperature=0.3, max_tokens=300)

    async def classify_task(self, context: str) -> Dict[str, Any]:
        """Classify the type and priority of development tasks.
        
        Args:
            context: Development context to analyze
            
        Returns:
            Dict[str, Any]: Task classification with type and priority
        """
        prompt = (
            "Analyze this development context and classify the task. "
            "Respond with a JSON object containing 'task_type' (feature, bug, refactor, docs) "
            "and 'priority' (high, medium, low):\n\n"
            f"{context}"
        )
        
        try:
            result = await self.generate(prompt, temperature=0.1, max_tokens=100)
            if result:
                return json.loads(result)
            return {"task_type": "unknown", "priority": "unknown"}
        except json.JSONDecodeError:
            return {"task_type": "unknown", "priority": "unknown"}

    async def answer_query(self, query: str, context: str) -> Optional[str]:
        """Answer a natural language query about the development context.
        
        Args:
            query: The question to answer
            context: Development context to reference
            
        Returns:
            Optional[str]: Answer to the query
        """
        prompt = f"""Based on this development context, answer the following question:

Question: {query}

Context:
{context}

Provide a clear, concise answer."""
        
        return await self.generate(prompt, temperature=0.3, max_tokens=400)

    async def health_check(self) -> bool:
        """Check if Groq API is accessible.
        
        Returns:
            bool: True if API is healthy
        """
        try:
            result = await self.generate("test", max_tokens=10)
            return result is not None
        except Exception:
            return False
