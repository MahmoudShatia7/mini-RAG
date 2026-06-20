from enum import Enum

class LLMEnum(Enum):

    OPENAI = "openai"
    COHERE = "cohere"

class OpenAIEnum(Enum):

    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'