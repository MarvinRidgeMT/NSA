"""POLARIS X v2 worlds (prompt §3.1): the world is a context selector, not a scenario axis.

    from science.worlds import get_world
    moon = get_world('moon'); mercury = get_world('mercury')
"""
from .registry import WORLDS, get_world  # noqa: F401
