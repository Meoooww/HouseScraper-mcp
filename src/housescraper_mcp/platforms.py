"""Platform normalization for first-party MCP inputs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_PLATFORMS = ("beike", "anjuke")

_PLATFORM_MAP = {
    "beike": "beike",
    "lianjia": "beike",
    "anjuke": "anjuke",
}

_COOKIE_DOMAIN_MAP = {
    "beike": "ke.com",
    "anjuke": "anjuke.com",
}


@dataclass(frozen=True, slots=True)
class RequestedPlatform:
    """A user-requested platform name and its canonical adapter target."""

    requested: str
    canonical: str
    cookie_domain: str


def resolve_platforms(platforms: Iterable[str] | None) -> list[RequestedPlatform]:
    """Normalize user-supplied platform names.

    The first version only supports `beike`, `lianjia`, and `anjuke`.
    `lianjia` is intentionally mapped to the `beike` adapter.
    """

    normalized = [name.strip().lower() for name in platforms or DEFAULT_PLATFORMS if name.strip()]
    if not normalized:
        normalized = list(DEFAULT_PLATFORMS)

    resolved: list[RequestedPlatform] = []
    invalid: list[str] = []
    for requested in normalized:
        canonical = _PLATFORM_MAP.get(requested)
        if canonical is None:
            invalid.append(requested)
            continue
        resolved.append(
            RequestedPlatform(
                requested=requested,
                canonical=canonical,
                cookie_domain=_COOKIE_DOMAIN_MAP[canonical],
            )
        )

    if invalid:
        supported = ", ".join(sorted(_PLATFORM_MAP))
        invalid_list = ", ".join(sorted(set(invalid)))
        raise ValueError(f"Unsupported platforms: {invalid_list}. Supported: {supported}.")

    return resolved


def group_by_canonical(targets: Iterable[RequestedPlatform]) -> dict[str, list[RequestedPlatform]]:
    """Group requested names by the adapter they map to."""

    grouped: dict[str, list[RequestedPlatform]] = defaultdict(list)
    for target in targets:
        grouped[target.canonical].append(target)
    return dict(grouped)
