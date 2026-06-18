from abc import ABC , abstractmethod

class LLMInterface(ABC):

    @abstractmethod
    def set_generation_model (self,model_id: str):
        pass
    