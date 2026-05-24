from enum import Enum

class ResponseSignal(Enum) :

    FILE_VALIDATE_SUCCESS = "File_Validate_Successfully"
    FILE_TYPE_NOT_SUPPORTED = "File_Type_Not_Supported"
    FILE_SIZE_EXCEEDED = "File_Type_Exceeded"
    FILE_UPLOADED_PASSED = "File_Uploaded_Success"
    FILE_UPLOADED_FAILED = "File_Uploaded_Fail"