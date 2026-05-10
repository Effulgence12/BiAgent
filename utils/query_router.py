"""Route generated SQL to pre-aggregated views when possible."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from config.views_desc import VIEW_NAMES

_VIEW_PATTERN = re.compile(r"\b(?:from|join)\s+([`\w.]+)", re.IGNORECASE)


@dataclass(frozen=True)
class QueryRoute:
    """Routing decision for an SQL statement."""

    route: str
    matched_views: tuple[str, ...]
    reason: str


def referenced_relations(sql: str) -> tuple[str, ...]:
    """Extract table/view names referenced after FROM or JOIN clauses."""
    relations: list[str] = []
    for raw_name in _VIEW_PATTERN.findall(sql):
        name = raw_name.strip("`").split(".")[-1].lower()
        relations.append(name)
    return tuple(relations)


def decide_query_route(sql: str, available_views: Iterable[str] = VIEW_NAMES) -> QueryRoute:
    """Decide whether a SQL statement hits materialized views or falls back to base tables."""
    normalized_views = {view.lower() for view in available_views}
    relations = referenced_relations(sql)
    matched = tuple(relation for relation in relations if relation in normalized_views)
    if matched:
        return QueryRoute("materialized_view", matched, "SQL references known mv_* pre-aggregated views.")
    return QueryRoute("base_table_fallback", tuple(), "No known mv_* view reference found; use base-table fallback path.")
