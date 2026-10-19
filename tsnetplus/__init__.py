"""Top-level package for TSNetPlus."""
import logging
from tsnetplus import network
from tsnetplus import simulation
from tsnetplus import postprocessing 
from tsnetplus import utils
from tsnetplus.utils import configure_logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__author__ = """Tomasz Janus, Hector Duque"""
__email__ = 'tomasz.janus@manchester.ac.uk'
__version__ = '0.4.0'
