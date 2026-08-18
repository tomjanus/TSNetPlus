"""Top-level package for tsnet."""
import logging
from tsnet import network
from tsnet import simulation
from tsnet import postprocessing 
from tsnet import utils
from tsnet.utils import configure_logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__author__ = """Lu Xing, Tomasz Janus"""
__email__ = 'xinglu@utexas.edu, tomasz.k.janus@gmail.com'
__version__ = '0.2.3'
