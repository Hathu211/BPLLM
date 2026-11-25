from typing import Dict, List 
from openai import OpenAI
from bpllm.config import get_settings

class LLMClient:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(base_url=settings.llm_base_url,
                             api_key=settings.llm_api_key,
                             timeout=300)
        self.model = settings.llm_model

    def chat(self, messages, max_tokens = 512): 
        response = self.client.chat.completions.create(model = self.model, messages = messages, 
                                                       temperature = 0, max_tokens = max_tokens)
        return response.choices[0].message.content.strip()

