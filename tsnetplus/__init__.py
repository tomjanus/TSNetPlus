"""Top-level package for tsnet."""
import logging
from tsnetplus import network
from tsnetplus import simulation
from tsnetplus import postprocessing 
from tsnetplus import utils
from tsnetplus.utils import configure_logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__author__ = """Lu Xing, Tomasz Janus"""
__email__ = 'xinglu@utexas.edu, tomasz.k.janus@gmail.com'
__version__ = '0.2.3'
