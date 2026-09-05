from pydantic import AliasChoices, BaseModel, Field
from typing import Optional


class ProcessRequest(BaseModel) :

    file_id : str = None
    chunk_size : Optional[int] = 512
    overlap_size: Optional[int] = Field(
        default=64,
        validation_alias=AliasChoices("overlap_size", "overlab_size"),
    )

    do_reset : Optional[int] = 0
