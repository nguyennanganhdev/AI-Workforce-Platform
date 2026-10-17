# -*- coding: utf-8 -*-
"""AI Workforce Platform application modules.

The first implementation phase intentionally exposes only stable contracts.
Concrete registry, builder, lifecycle, orchestration, and execution services
are composed in later phases by their respective owners.
"""

from . import contracts

__all__ = ["contracts"]
