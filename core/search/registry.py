"""Registry for managing search provider classes.

Providers are registered by name via ``register_provider()``.  The
``SearchRegistry`` class provides factory and discovery methods.
"""
from __future__ import annotations

from typing import Any

import structlog

from core.search.base import SearchProvider

logger = structlog.get_logger(__name__)

# Module-level provider registry: name -> class
_PROVIDERS: dict[str, type[SearchProvider]] = {}


def register_provider(name: str, cls: type[SearchProvider]) -> None:
    """Register a SearchProvider class under the given name.

    Overwrites any previously registered provider with the same name.
    """
    logger.debug("registering_search_provider", name=name, cls=cls.__name__)
    _PROVIDERS[name] = cls


class SearchRegistry:
    """Factory and discovery interface for registered search providers."""

    @staticmethod
    def list_providers() -> list[str]:
        """Return the names of all currently registered providers."""
        names = list(_PROVIDERS.keys())
        logger.debug("listing_providers", count=len(names), providers=names)
        return names

    @staticmethod
    def create(name: str, **kwargs: Any) -> SearchProvider:
        """Instantiate a registered provider by name.

        Args:
            name: The registered provider name.
            **kwargs: Extra keyword arguments forwarded to the provider constructor.

        Raises:
            ValueError: If *name* is not found in the registry.
        """
        if name not in _PROVIDERS:
            logger.warning("unknown_provider_requested", name=name)
            raise ValueError(f"unknown search provider: '{name}'. Registered: {list(_PROVIDERS)}")

        cls = _PROVIDERS[name]
        logger.info("creating_search_provider", name=name, cls=cls.__name__)
        return cls(**kwargs)

    @staticmethod
    def get_enabled(
        *,
        patentsview_enabled: bool = True,
        uspto_odp_enabled: bool = True,
        serpapi_enabled: bool = False,
        **kwargs: Any,
    ) -> list[SearchProvider]:
        """Return instantiated providers for each enabled flag.

        Only providers that are both flagged as enabled *and* registered in
        ``_PROVIDERS`` are included.  Unregistered providers are silently skipped.

        Args:
            patentsview_enabled: Include the PatentsView provider.
            uspto_odp_enabled: Include the USPTO ODP provider.
            serpapi_enabled: Include the SerpAPI Google Patents provider.
            **kwargs: Extra kwargs forwarded to each provider constructor.

        Returns:
            A list of instantiated SearchProvider objects.
        """
        candidates: list[tuple[str, bool]] = [
            ("patentsview", patentsview_enabled),
            ("uspto_odp", uspto_odp_enabled),
            ("serpapi", serpapi_enabled),
        ]

        instances: list[SearchProvider] = []
        for name, enabled in candidates:
            if not enabled:
                logger.debug("provider_disabled", name=name)
                continue
            if name not in _PROVIDERS:
                logger.debug("provider_not_registered_skipped", name=name)
                continue
            provider = SearchRegistry.create(name, **kwargs)
            logger.info("provider_enabled", name=name)
            instances.append(provider)

        logger.info("enabled_providers_resolved", count=len(instances))
        return instances
