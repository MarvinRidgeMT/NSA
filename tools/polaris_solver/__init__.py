"""POLARIS X solver API: one JSON request in, one JSON result out.

Geometric visibility of the Sun and Earth centre from a point near the lunar south pole, on NASA PGDA 78 5 m LOLA terrain
(+ PGDA 90 80 m to 280 km) with JPL Horizons ephemerides. SOURCE-BASED, UNVALIDATED. Not power, not communications.
"pass on k of N terrain maps" is a count of NASA clones tested, never a probability.
"""
from .api import solve, REQUEST_SCHEMA, TOOL_SPEC, VERSION  # noqa: F401
