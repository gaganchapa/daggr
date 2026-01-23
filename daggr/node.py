from __future__ import annotations

import inspect
import warnings
from abc import ABC
from typing import Any, Callable, List, Optional

from daggr.port import Port, PortNamespace


class Node(ABC):
    _id_counter = 0

    def __init__(self, name: Optional[str] = None, outputs: Optional[List[Any]] = None):
        self._id = Node._id_counter
        Node._id_counter += 1
        self._name = name or ""
        self._input_ports: List[str] = []
        self._output_ports: List[str] = []
        self._output_components: List[Any] = outputs or []

    def __getattr__(self, name: str) -> Port:
        if name.startswith("_"):
            raise AttributeError(name)
        return Port(self, name)

    def __dir__(self) -> List[str]:
        base = ["_name", "_inputs", "_outputs", "_input_ports", "_output_ports"]
        return base + self._input_ports + self._output_ports

    @property
    def _inputs(self) -> PortNamespace:
        return PortNamespace(self, self._input_ports)

    @property
    def _outputs(self) -> PortNamespace:
        return PortNamespace(self, self._output_ports)

    def _default_output_port(self) -> Port:
        if self._output_ports:
            return Port(self, self._output_ports[0])
        return Port(self, "output")

    def _default_input_port(self) -> Port:
        if self._input_ports:
            return Port(self, self._input_ports[0])
        return Port(self, "input")

    def _validate_ports(self):
        all_ports = set(self._input_ports + self._output_ports)
        underscore_ports = [p for p in all_ports if p.startswith("_")]
        if underscore_ports:
            warnings.warn(
                f"Port names {underscore_ports} start with underscore. "
                f"Use node._inputs.{underscore_ports[0]} or node._outputs.{underscore_ports[0]} to access."
            )

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self._name})"


class GradioNode(Node):
    def __init__(
        self,
        src: str,
        name: Optional[str] = None,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[Any]] = None,
    ):
        super().__init__(name, outputs)
        self._src = src
        self._inputs_override = inputs
        self._discovered = False
        if not self._name:
            self._name = self._src.split("/")[-1]

    def discover_api(self):
        if self._discovered:
            return
        try:
            from gradio_client import Client

            client = Client(self._src)
            api_info = client.view_api(return_format="dict")

            if isinstance(api_info, dict):
                endpoints = api_info.get("named_endpoints", {})
                predict_info = None
                for key, value in endpoints.items():
                    if "/predict" in key or key == "predict":
                        predict_info = value
                        break
                if not predict_info and endpoints:
                    predict_info = list(endpoints.values())[0]

                if predict_info:
                    params = predict_info.get("parameters", [])
                    returns = predict_info.get("returns", [])
                    self._input_ports = [
                        p.get("parameter_name") or p.get("label") or f"input_{i}"
                        for i, p in enumerate(params)
                    ]
                    self._output_ports = [
                        r.get("label") or f"output_{i}" for i, r in enumerate(returns)
                    ]
        except Exception as e:
            print(f"Warning: Could not discover API for {self._name}: {e}")

        if self._inputs_override:
            self._input_ports = self._inputs_override

        if not self._output_ports:
            self._output_ports = ["output"]
        if not self._input_ports:
            self._input_ports = ["input"]

        self._discovered = True
        self._validate_ports()


class InferenceNode(Node):
    def __init__(
        self,
        model: str,
        name: Optional[str] = None,
        outputs: Optional[List[Any]] = None,
    ):
        super().__init__(name, outputs)
        self._model = model
        self._input_ports = ["input"]
        self._output_ports = ["output"]
        if not self._name:
            self._name = self._model.split("/")[-1]
        self._validate_ports()


class FnNode(Node):
    def __init__(
        self,
        fn: Callable,
        name: Optional[str] = None,
        outputs: Optional[List[Any]] = None,
    ):
        super().__init__(name, outputs)
        self._fn = fn
        self._discover_signature()
        if not self._name:
            self._name = self._fn.__name__
        self._validate_ports()

    def _discover_signature(self):
        sig = inspect.signature(self._fn)
        self._input_ports = list(sig.parameters.keys())
        if self._output_components:
            self._output_ports = [
                self._get_component_label(c, i)
                for i, c in enumerate(self._output_components)
            ]
        else:
            self._output_ports = ["output"]

    def _get_component_label(self, component: Any, index: int) -> str:
        if hasattr(component, "label") and component.label:
            return component.label
        return f"output_{index}"


class InteractionNode(Node):
    def __init__(
        self,
        name: Optional[str] = None,
        interaction_type: str = "generic",
        outputs: Optional[List[Any]] = None,
    ):
        super().__init__(name, outputs)
        self._interaction_type = interaction_type
        self._input_ports = ["input"]
        self._output_ports = ["output"]
        if not self._name:
            self._name = f"interaction_{self._id}"
        self._validate_ports()


class InputNode(Node):
    _instance_counter = 0

    def __init__(
        self,
        inputs: List[Any],
        name: Optional[str] = None,
    ):
        super().__init__(name)
        InputNode._instance_counter += 1
        self._input_components = inputs
        self._input_ports = []
        self._output_ports = []
        for i, component in enumerate(inputs):
            label = self._get_component_label(component, i)
            self._output_ports.append(label)
        if not self._name:
            self._name = f"input_{InputNode._instance_counter}"
        self._validate_ports()

    def _get_component_label(self, component: Any, index: int) -> str:
        if hasattr(component, "label") and component.label:
            return component.label
        return f"input_{index}"


