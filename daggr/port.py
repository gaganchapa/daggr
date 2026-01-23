from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from daggr.node import Node


class Port:
    def __init__(self, node: Node, name: str):
        self.node = node
        self.name = name

    def __repr__(self):
        return f"Port({self.node._name}.{self.name})"

    def _as_source(self) -> tuple[Node, str]:
        return (self.node, self.name)

    def _as_target(self) -> tuple[Node, str]:
        return (self.node, self.name)


class ScatteredPort:
    def __init__(self, port: Port, item_output: Optional[Any] = None):
        self.port = port
        self.item_output = item_output

    @property
    def node(self):
        return self.port.node

    @property
    def name(self):
        return self.port.name

    def __repr__(self):
        return f"ScatteredPort({self.port})"


class GatheredPort:
    def __init__(self, port: Port):
        self.port = port

    @property
    def node(self):
        return self.port.node

    @property
    def name(self):
        return self.port.name

    def __repr__(self):
        return f"GatheredPort({self.port})"


def scatter(port: Port, item_output: Optional[Any] = None) -> ScatteredPort:
    return ScatteredPort(port, item_output)


def gather(port: Port) -> GatheredPort:
    return GatheredPort(port)


PortLike = Union[Port, ScatteredPort, GatheredPort]


class PortNamespace:
    def __init__(self, node: Node, port_names: list[str]):
        self._node = node
        self._names = set(port_names)

    def __getattr__(self, name: str) -> Port:
        if name.startswith("_"):
            raise AttributeError(name)
        return Port(self._node, name)

    def __dir__(self) -> list[str]:
        return list(self._names)

    def __repr__(self):
        return f"PortNamespace({list(self._names)})"
