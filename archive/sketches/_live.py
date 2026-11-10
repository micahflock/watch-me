"""Import this first from an archived script: it puts the live sandbox
(sketches/: device, day, harness, twchrome, the engine mirrors) on sys.path
right behind the script's own directory, so the archive keeps running without
the working set having to know it exists.
"""
import os
import sys

ARCHIVE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(os.path.dirname(ARCHIVE)), "sketches")
if LIVE not in sys.path:
    sys.path.insert(1, LIVE)
