#!/usr/bin/env python3
"""biobloom_parametric_coarse -- the parametric skeleton (algos/biobloom_param-
etric.py) with COARSE regeneration: the wiggle walk runs every 2*STEP and the
in-between radii are midpoint-filled, halving the per-frame hash16/isin cost at
the price of a chunkier wiggle. Same dish otherwise."""
import importlib.util
import os

_p = os.path.join(os.path.dirname(__file__), "biobloom_parametric.py")
_spec = importlib.util.spec_from_file_location("biobloom_parametric", _p)
bbp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bbp)


def build():
    return {"background": bbp.COLOR_BLACK,
            "components": [bbp.BioBloomParam(coarse=True)]}
