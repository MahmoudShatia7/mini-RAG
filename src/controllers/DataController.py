from .BaseController import BaseController
from fastapi import UploadFile
from .ProjectController import ProjectController
from src.models import ResponseSignal

import logging
import mimetypes
import re
import os 
logger = logging.getLogger("uvicorn.error")


class DataController(BaseController) :

    def __init__(self):
        super().__init__()
        self.size_scale = 1024 * 1024  # Convert MB to bytes

    def resolve_content_type(self, file: UploadFile) -> str:
        """Normalise the declared content type before checking it.

        Clients legitimately send parameters ("text/plain; charset=utf-8"), and
        some send "application/octet-stream" when they cannot infer a type at
        all. Both are matched against the allowed list by media type alone,
        falling back to the file extension when the header is uninformative.
        """
        declared = (file.content_type or "").split(";")[0].strip().lower()

        if declared and declared != "application/octet-stream":
            return declared

        guessed, _ = mimetypes.guess_type(file.filename or "")
        return (guessed or declared).lower()

    def validate_uploaded_file(self , file: UploadFile )  :

        content_type = self.resolve_content_type(file=file)

        if content_type not in self.app_settings.FILE_ALLOWED_TYPES :
            logger.warning(
                "Rejected upload %s: resolved type %r (declared %r) is not in %s.",
                file.filename,
                content_type,
                file.content_type,
                self.app_settings.FILE_ALLOWED_TYPES,
            )
            return False , ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value

        file_size = file.size or 0
        if file_size > self.app_settings.FILE_MAX_SIZE * self.size_scale:
            return  False  , ResponseSignal.FILE_SIZE_EXCEEDED.value
        
        return True , ResponseSignal.FILE_VALIDATE_SUCCESS.value

    def generate_unique_filepath (self, orig_file_name : str, project_id :str) :
        
        random_key = self.generate_random_string()
        project_path = ProjectController().get_project_path(project_id=project_id)

        cleaned_file_name = self.get_clean_file_name(
            orig_file_name=orig_file_name
        )

        new_file_path =os.path.join(
            project_path,
            random_key + "_" + cleaned_file_name
        )

        while os.path.exists(new_file_path):
            random_key = self.generate_random_string()
            new_file_path =os.path.join(

                project_path,
                random_key + "_" + cleaned_file_name
            )

        return new_file_path, random_key + "_" + cleaned_file_name


        
    def get_clean_file_name (self , orig_file_name : str ):


        cleaned_file_name = re.sub(r'[^\w.]', '' , orig_file_name.strip())

        cleaned_file_name =cleaned_file_name.replace(" " , "_")

        if not cleaned_file_name:
            return "uploaded_file"

        return cleaned_file_name
