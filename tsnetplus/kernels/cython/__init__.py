""" """
try:
    from .inner_node import inner_node
    from .friction import friction
    HAS_CYTHON = True
except ImportError:
    HAS_CYTHON = False
