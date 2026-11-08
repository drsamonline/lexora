"""Language plugins shipped with lexora (ADR-0022).

English is the first and, for now, only one — deliberately. It is implemented *as a
plugin* rather than as a special case so the seam is exercised from the day it exists:
a plugin system with zero plugins behind it is an untested abstraction.
"""
