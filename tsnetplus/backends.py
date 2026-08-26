""" """
from enum import StrEnum

class ComputeBackend(StrEnum):
    AUTO = "auto"
    PYTHON = "python"
    NUMBA = "numba"
    CYTHON = "cython"
    ORIGINAL = "original"
