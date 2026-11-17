"""World registry: get_world('moon' | 'mercury' | 'mars')."""
from __future__ import annotations

from .base import World


def get_world(name: str) -> World:
    n = name.lower()
    if n == 'moon':
        from .moon import MOON
        return MOON
    if n == 'mercury':
        from .mercury.world import MERCURY
        return MERCURY
    if n == 'mars':
        from .mars.world import MARS
        return MARS
    raise KeyError(f'unknown world {name!r}')


WORLDS = ('moon', 'mercury', 'mars')
