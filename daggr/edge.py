from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from daggr.port import PortLike


class Edge:
    def __init__(self, source: PortLike, target: PortLike):
        from daggr.port import GatheredPort, ScatteredPort

        self.is_scattered = isinstance(source, ScatteredPort)
        self.is_gathered = isinstance(target, GatheredPort)
        self.item_output: Optional[Any] = None

        if self.is_scattered:
            self.item_output = source.item_output

        self.source_node = source.node
        self.source_port = source.name
        self.target_node = target.node
        self.target_port = target.name

    def __repr__(self):
        prefix = ""
        if self.is_scattered:
            prefix = "scatter:"
        elif self.is_gathered:
            prefix = "gather:"
        return (
            f"Edge({prefix}{self.source_node._name}.{self.source_port} -> "
            f"{self.target_node._name}.{self.target_port})"
        )

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.source_node._name,
            self.source_port,
            self.target_node._name,
            self.target_port,
        )
