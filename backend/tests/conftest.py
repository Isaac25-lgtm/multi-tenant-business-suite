"""Put the backend package on sys.path for all test modules."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
