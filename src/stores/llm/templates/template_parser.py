import os
from string import Template

class TemplateParser:
    LANGUAGE_ALIASES = {
        "en": "eng",
    }

    def __init__(self, language: str=None, default_language: str = "en"):

        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.default_language = self.normalize_language(default_language)
        self.language = None

        self.set_language(language)

    def normalize_language(self, language: str):
        return self.LANGUAGE_ALIASES.get(language, language)

    def set_language(self, language: str):
        language = self.normalize_language(language)

        if not language:
            self.language = self.default_language

        if language and os.path.exists(os.path.join(self.current_path, "locales", language)):
            self.language = language

        else:
            self.language = self.default_language


    def get(self, group: str, key: str, vars: dict = None) -> str:

        if not group or not key:
            return None
        
        group_path = os.path.join(self.current_path, "locales", self.language, f"{group}.py")
        targeted_language = self.language

        if not os.path.exists(group_path):
            group_path = os.path.join(self.current_path, "locales", self.default_language, f"{group}.py")
            targeted_language = self.default_language

        if not os.path.exists(group_path):
            return None
        
        module = __import__(f"src.stores.llm.templates.locales.{targeted_language}.{group}", fromlist=[group])

        if not module:
            return None
        
        key_attribute = getattr(module, key, None)

        if isinstance(key_attribute, Template):
            return key_attribute.safe_substitute(vars or {})

        return key_attribute

      

   
