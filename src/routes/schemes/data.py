from pydantic import AliasChoices, BaseModel, Field
from typing import Optional


class ProcessRequest(BaseModel) :

    file_id : str 
    chunk_size : Optional[int] = 100
    overlap_size: Optional[int] = Field(
        default=20,
        validation_alias=AliasChoices("overlap_size", "overlab_size"),
    )

    do_reset : Optional[int] = 0
