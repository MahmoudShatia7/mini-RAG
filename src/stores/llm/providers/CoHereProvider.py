from ..LLMInterface import LLMInterface
from ..LLMEnums import CoHereEnum , DocumentTypeEnum
import cohere
import logging
import asyncio
from typing import List, Union

class CoHereProvider(LLMInterface):

    def __init__ (self, api_key: str , api_url: str = None,
                  default_input_max_characters: int = 1000, 
                  default_generation_max_output_tokens: int = 1000,
                  default_generation_temperature: float = 0.1,
                  default_embedding_batch_size: int = 96,
                  default_embedding_retries: int = 5):
        
        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.default_embedding_batch_size = default_embedding_batch_size
        self.default_embedding_retries = default_embedding_retries

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = cohere.AsyncClient(self.api_key)

        self.logger = logging.getLogger(__name__)
        self.enums = CoHereEnum


    def set_generation_model (self,model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model (self,model_id: str , embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    # A 429 can mean the per-minute rate limit, which clears on its own, or the
    # monthly / trial allowance, which does not. Only the former is retryable.
    QUOTA_EXHAUSTED_MARKERS = (
        "calls / month",
        "calls/month",
        "per month",
        "monthly limit",
    )

    def is_quota_exhausted(self, message: str) -> bool:
        lowered = (message or "").lower()
        return any(marker in lowered for marker in self.QUOTA_EXHAUSTED_MARKERS)

    async def generate_text (self, prompt: str,chat_history: list = None, max_output_tokens: int = None, temperature: float = None) :
        
        if not self.client:
            self.logger.error("Cohere client is not initialized.")
            return None
        
        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return None
        
        max_output_tokens = max_output_tokens if max_output_tokens is not None else self.default_generation_max_output_tokens
        temperature = temperature if temperature is not None else self.default_generation_temperature
        chat_history = chat_history or []

        cohere_chat_history = []
        system_prompts = []
        for item in chat_history:
            role = item.get("role")
            message = item.get("message") or item.get("content")

            if not role or not message:
                continue

            if role == CoHereEnum.SYSTEM.value:
                system_prompts.append(message)
                continue

            cohere_chat_history.append({
                "role": role,
                "message": message
            })

        if system_prompts:
            prompt = "\n\n".join(system_prompts + [prompt])

        try:
            response = await self.client.chat(
                model=self.generation_model_id,
                message=prompt.strip(),
                chat_history=cohere_chat_history,
                max_tokens=max_output_tokens,
                temperature=temperature
            )
        except Exception as e:
            self.logger.error(f"Cohere generation request failed: {e}")
            return None

        if not response or not response.text:
            self.logger.error("No response received from Cohere API.")
            return None
        return response.text.strip()
    
    async def embed_text(self, text : Union[str, List[str]], document_type :str = None):
        embeddings = await self.embed_texts(texts=[text] if isinstance(text, str) else text, document_type=document_type)
        if embeddings is None:
            return None
        if isinstance(text, str):
            return embeddings[0] if embeddings else None
        return embeddings

    async def _embed_text_batch(self, texts: List[str], document_type: str = None):
        if not self.client:
            self.logger.error("Cohere client is not initialized.")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model ID for Cohere is not set.")
            return None
        
        input_type = CoHereEnum.DOCUMENT
        if document_type == DocumentTypeEnum.QUERY.value:
            input_type = CoHereEnum.QUERY

        response = None
        for attempt in range(self.default_embedding_retries + 1):
            try:
                response = await self.client.embed(
                    model=self.embedding_model_id,
                    texts=[ self.process_text(t) for t in texts],
                    input_type=input_type.value,
                    embedding_types=['float'],
                )
                break
            except Exception as e:
                message = str(e)
                is_rate_limit = "429" in message or "rate limit" in message.lower()

                # A monthly quota 429 will not clear on its own, so backing off
                # only wastes time and further calls against a dead budget.
                if is_rate_limit and self.is_quota_exhausted(message):
                    self.logger.error(
                        f"Cohere quota exhausted, not retrying: {e}"
                    )
                    return None

                if not is_rate_limit or attempt >= self.default_embedding_retries:
                    self.logger.error(f"Cohere embedding request failed: {e}")
                    return None

                sleep_seconds = min(2 ** attempt, 30)
                self.logger.warning(
                    f"Cohere rate limit hit while embedding {len(texts)} texts. "
                    f"Retrying in {sleep_seconds}s (attempt {attempt + 1}/{self.default_embedding_retries})."
                )
                await asyncio.sleep(sleep_seconds)

        if not response or not response.embeddings or not response.embeddings.float:
            self.logger.error("No embeddings received from Cohere API.")
            return None
        return [ f for f in response.embeddings.float]

    async def embed_texts(self, texts: List[str], document_type: str = None):
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.default_embedding_batch_size):
            batch = texts[i : i + self.default_embedding_batch_size]
            batch_embeddings = await self._embed_text_batch(texts=batch, document_type=document_type)
            if batch_embeddings is None:
                return None
            all_embeddings.extend(batch_embeddings)
        return all_embeddings
       

    def construct_prompt (self , prompt : str , role: str ):
        return{
            "role" : role,
            "message" : prompt,
        }
