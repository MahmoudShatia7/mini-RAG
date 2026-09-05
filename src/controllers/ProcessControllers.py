from .BaseController import BaseController
from .ProjectController import ProjectController
import os
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from typing import List
from dataclasses import dataclass

from src.models import ProcessingEnum


@dataclass
class Document:
    page_content: str
    metadata: dict


class ProcessControllers (BaseController) :

    def __init__(self , project_id : str ):
        super().__init__()

        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id =project_id)


    def get_file_extention (self, file_id : str) :

       return os.path.splitext(file_id)[-1]
    
    def get_file_loader (self , file_id : str ) :

        file_ext = self.get_file_extention(file_id=file_id)
        file_path = os.path.join(
            self.project_path,
            file_id
        )

        if not os.path.exists(file_path) :
            return None

        if file_ext == ProcessingEnum.TXT.value : 
            return TextLoader(file_path , encoding= "utf-8")

        if file_ext == ProcessingEnum.PDF.value :
            return PyMuPDFLoader(file_path)
        
        return None
    
    def get_file_content(self ,file_id : str):
        
        loader = self.get_file_loader(file_id=file_id)
        if loader is None:
            return []
        return loader.load()
    
    def process_file_content(self, file_content: list, file_id: str,
                              chunk_size: int = 512, overlap_size: int = 64):
        
        # Separators are tried in order, so paragraph and sentence breaks are
        # preferred over slicing mid-word. Arabic full stop is included for the
        # ar locale.
       

        file_content_texts = [
            rec.page_content
            for rec in file_content
        ]

        file_content_metadata = [
            rec.metadata
            for rec in file_content
        ]

        if not file_content_texts:
            return []

        # chunks = text_spliter.create_documents(
        #     file_content_texts,
        #     metadatas=file_content_metadata
        # )
        chunks = self.process_simpler_splitter(
            texts=file_content_texts,
            metadatas=file_content_metadata,
            chunk_size=chunk_size,
            splitter="\n",
            overlap_size=overlap_size
        )

        return chunks

    def build_chunk_overlap(self, chunk: str, overlap_size: int, splitter: str = "\n"):
        """Tail of a finished chunk that is carried into the next one.

        The carry-over starts at the first line break, or failing that the first
        space, inside the tail so a chunk never begins mid-word.
        """
        if overlap_size <= 0 or not chunk:
            return ""

        tail = chunk[-overlap_size:]

        for boundary in (splitter, " "):
            position = tail.find(boundary)
            if position != -1:
                return tail[position + len(boundary):].strip()

        return tail.strip()

    def split_oversized_line(self, line: str, chunk_size: int):
        """Break a single line that is longer than chunk_size into safe pieces.

        Each piece stops at the last space inside the limit so words stay whole;
        a run with no space at all is cut at the limit rather than overflowing.
        """
        line = line.strip()

        if len(line) <= chunk_size:
            return [line] if line else []

        pieces = []
        remaining = line

        while len(remaining) > chunk_size:
            window = remaining[:chunk_size]
            cut = window.rfind(" ")

            if cut <= 0:
                cut = chunk_size

            pieces.append(remaining[:cut].strip())
            remaining = remaining[cut:].lstrip()

        if remaining:
            pieces.append(remaining)

        return [piece for piece in pieces if piece]

    def process_simpler_splitter(self , texts: List[str], metadatas: List[dict], chunk_size: int,
                                 splitter: str = "\n", overlap_size: int = 0):

        chunks = []
        metadatas = metadatas or []

        # Each loaded document is split on its own, so a chunk never spans a
        # document or PDF page boundary and keeps that document's metadata.
        for index, text in enumerate(texts):
            if not text:
                continue

            source_metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}

            lines = [doc.strip() for doc in text.split(splitter) if len(doc.strip()) > 1]

            current_chunk = ""
            has_new_content = False

            for line in lines:
                # An oversized line is broken up first, so no single piece can
                # push the chunk past chunk_size on its own.
                for piece in self.split_oversized_line(line, chunk_size):

                    if current_chunk and len(current_chunk) + len(splitter) + len(piece) > chunk_size:
                        if has_new_content:
                            chunks.append(Document(page_content=current_chunk, metadata=dict(source_metadata)))
                            current_chunk = self.build_chunk_overlap(current_chunk, overlap_size, splitter)
                        else:
                            # Only the carried overlap is held, so drop it rather
                            # than emit a chunk that repeats the previous one.
                            current_chunk = ""

                        has_new_content = False

                    # The carry-over may still leave no room for this piece.
                    if current_chunk and len(current_chunk) + len(splitter) + len(piece) > chunk_size:
                        current_chunk = ""

                    current_chunk = f"{current_chunk}{splitter}{piece}" if current_chunk else piece
                    has_new_content = True

            # Keep the trailing text, unless it is only the carried overlap.
            if has_new_content and current_chunk:
                chunks.append(Document(page_content=current_chunk, metadata=dict(source_metadata)))

        return chunks

