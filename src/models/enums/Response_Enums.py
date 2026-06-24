from enum import Enum

class ResponseSignal(Enum) :

    FILE_VALIDATE_SUCCESS = "File_Validate_Successfully"
    FILE_TYPE_NOT_SUPPORTED = "File_Type_Not_Supported"
    FILE_SIZE_EXCEEDED = "File_Type_Exceeded"
    FILE_UPLOADED_PASSED = "File_Uploaded_Success"
    FILE_UPLOADED_FAILED = "File_Uploaded_Fail"
    PROCESSING_SUCESS = "processing_sucess"
    PROCESSINF_FAILD = "processing_faild"
    NO_FILES_ERROR = "No_Files_To_Process"
    FILE_ID_ERROR = "no_file_found_with_this_id"
    PROJECT_NOT_FOUND_ERROR = "project_not_found"
    INSERT_INTO_VECTORDB_ERROR = "insert_into_vectordb_error"
    INSERT_INTO_VECTORDB_SUCCESS="insert_into_vectordb_success"
    VECTORDB_COLLECTION_RETRIVED = "vectordb_collection_retrived"
    VECTORDB_SEARCH_ERROR = "vectordb_search_error"
    VECTORDB_SEARCH_SUCCESS="vectordb_search_success"
