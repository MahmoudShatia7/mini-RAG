from pydantic import BaseModel , Field , validator
from typing import Optional
from bson.objectid import ObjectId


class project(BaseModel) :
    _id :Optional[ObjectId] 
    project_id : str = Field (... , min_length=1)

    @classmethod
    @validator('project_id')
    def validate_project(cls, value):
        if not value.isalnum():
            raise ValueError ('project_id Must be Alphanumeric')

        return value
    
    class config :
        arbitrary_types_allowed = True
