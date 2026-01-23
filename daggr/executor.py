from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from daggr.graph import Graph


class SequentialExecutor:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.clients: Dict[str, Any] = {}
        self.results: Dict[str, Any] = {}
        self.scattered_results: Dict[str, List[Any]] = {}

    def _get_client(self, node_name: str):
        from daggr.node import GradioNode

        if node_name not in self.clients:
            node = self.graph.nodes[node_name]
            if isinstance(node, GradioNode):
                from gradio_client import Client

                self.clients[node_name] = Client(node._src)
        return self.clients.get(node_name)

    def _get_scattered_input_edge(self, node_name: str):
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                return edge
        return None

    def _get_gathered_output_edges(self, node_name: str):
        gathered = []
        for edge in self.graph._edges:
            if edge.source_node._name == node_name and edge.is_gathered:
                gathered.append(edge)
        return gathered

    def _prepare_inputs(
        self, node_name: str, skip_scattered: bool = False
    ) -> Dict[str, Any]:
        inputs = {}

        for edge in self.graph._edges:
            if edge.target_node._name == node_name:
                if skip_scattered and edge.is_scattered:
                    continue

                source_name = edge.source_node._name
                source_output = edge.source_port
                target_input = edge.target_port

                if source_name in self.results:
                    source_result = self.results[source_name]

                    if (
                        edge.is_gathered
                        and isinstance(source_result, dict)
                        and "_scattered_results" in source_result
                    ):
                        scattered_results = source_result["_scattered_results"]
                        extracted = []
                        for item_result in scattered_results:
                            if (
                                isinstance(item_result, dict)
                                and source_output in item_result
                            ):
                                extracted.append(item_result[source_output])
                            else:
                                extracted.append(item_result)
                        inputs[target_input] = extracted
                    elif (
                        isinstance(source_result, dict)
                        and source_output in source_result
                    ):
                        inputs[target_input] = source_result[source_output]
                    elif isinstance(source_result, (list, tuple)):
                        try:
                            output_idx = int(
                                source_output.replace("output_", "").replace(
                                    "output", "0"
                                )
                            )
                            if 0 <= output_idx < len(source_result):
                                inputs[target_input] = source_result[output_idx]
                        except (ValueError, TypeError):
                            if len(source_result) > 0:
                                inputs[target_input] = source_result[0]
                    else:
                        inputs[target_input] = source_result

        return inputs

    def _execute_single_node(self, node_name: str, inputs: Dict[str, Any]) -> Any:
        from daggr.node import FnNode, GradioNode, InferenceNode, InteractionNode

        node = self.graph.nodes[node_name]

        all_inputs = dict(node._fixed_inputs)
        for port_name, component in node._input_components.items():
            if hasattr(component, "value") and component.value is not None:
                all_inputs[port_name] = component.value
        all_inputs.update(inputs)

        if isinstance(node, GradioNode):
            client = self._get_client(node_name)
            if client:
                api_name = node._api_name or "/predict"
                if not api_name.startswith("/"):
                    api_name = "/" + api_name
                call_inputs = {
                    k: v for k, v in all_inputs.items() if k in node._input_ports
                }
                raw_result = client.predict(api_name=api_name, **call_inputs)
                result = self._map_gradio_result(node, raw_result)
            else:
                result = None

        elif isinstance(node, FnNode):
            fn_kwargs = {}
            for port_name in node._input_ports:
                if port_name in all_inputs:
                    fn_kwargs[port_name] = all_inputs[port_name]
            raw_result = node._fn(**fn_kwargs)
            result = self._map_fn_result(node, raw_result)

        elif isinstance(node, InferenceNode):
            from huggingface_hub import InferenceClient

            client = InferenceClient(model=node._model)
            input_value = all_inputs.get(
                "input",
                all_inputs.get(node._input_ports[0]) if node._input_ports else None,
            )
            result = client.text_generation(input_value) if input_value else None

        elif isinstance(node, InteractionNode):
            result = all_inputs.get(
                "input",
                all_inputs.get(node._input_ports[0]) if node._input_ports else None,
            )

        else:
            result = None

        return result

    def _map_gradio_result(self, node, raw_result: Any) -> Dict[str, Any]:
        if raw_result is None:
            return {}

        output_ports = node._output_ports
        if not output_ports:
            return {"output": raw_result}

        if isinstance(raw_result, (list, tuple)):
            result = {}
            for i, port_name in enumerate(output_ports):
                if i < len(raw_result):
                    result[port_name] = raw_result[i]
                else:
                    result[port_name] = None
            return result
        elif len(output_ports) == 1:
            return {output_ports[0]: raw_result}
        else:
            return {output_ports[0]: raw_result}

    def _map_fn_result(self, node, raw_result: Any) -> Dict[str, Any]:
        if raw_result is None:
            return {}

        output_ports = node._output_ports
        if not output_ports:
            return {"output": raw_result}

        if isinstance(raw_result, dict):
            return raw_result
        elif isinstance(raw_result, (list, tuple)):
            result = {}
            for i, port_name in enumerate(output_ports):
                if i < len(raw_result):
                    result[port_name] = raw_result[i]
                else:
                    result[port_name] = None
            return result
        elif len(output_ports) == 1:
            return {output_ports[0]: raw_result}
        else:
            return {output_ports[0]: raw_result}

    def execute_node(
        self, node_name: str, user_inputs: Optional[Dict[str, Any]] = None
    ) -> Any:
        node = self.graph.nodes[node_name]
        scattered_edge = self._get_scattered_input_edge(node_name)

        if scattered_edge:
            result = self._execute_scattered_node(
                node_name, scattered_edge, user_inputs
            )
        else:
            inputs = self._prepare_inputs(node_name)
            if user_inputs:
                if isinstance(user_inputs, dict):
                    inputs.update(user_inputs)
                else:
                    if node._input_ports:
                        inputs[node._input_ports[0]] = user_inputs
                    else:
                        inputs["input"] = user_inputs

            try:
                result = self._execute_single_node(node_name, inputs)
            except Exception as e:
                raise RuntimeError(f"Error executing node '{node_name}': {e}")

        self.results[node_name] = result
        return result

    def _execute_scattered_node(
        self,
        node_name: str,
        scattered_edge,
        user_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Any]]:
        source_name = scattered_edge.source_node._name
        source_port = scattered_edge.source_port
        target_port = scattered_edge.target_port

        source_result = self.results.get(source_name)
        if source_result is None:
            items = []
        elif isinstance(source_result, dict) and source_port in source_result:
            items = source_result[source_port]
        else:
            items = source_result

        if not isinstance(items, list):
            items = [items]

        context_inputs = self._prepare_inputs(node_name, skip_scattered=True)
        if user_inputs:
            context_inputs.update(user_inputs)

        results = []
        for item in items:
            item_inputs = dict(context_inputs)
            item_inputs[target_port] = item

            try:
                item_result = self._execute_single_node(node_name, item_inputs)
                results.append(item_result)
            except Exception as e:
                results.append({"error": str(e)})

        self.scattered_results[node_name] = results
        return {"_scattered_results": results, "_items": items}

    def execute_scattered_item(
        self, node_name: str, item_index: int, inputs: Optional[Dict[str, Any]] = None
    ) -> Any:
        scattered_edge = self._get_scattered_input_edge(node_name)
        if not scattered_edge:
            raise ValueError(f"Node '{node_name}' does not have a scattered input")

        source_name = scattered_edge.source_node._name
        source_port = scattered_edge.source_port
        target_port = scattered_edge.target_port

        source_result = self.results.get(source_name)
        if source_result is None:
            items = []
        elif isinstance(source_result, dict) and source_port in source_result:
            items = source_result[source_port]
        else:
            items = source_result

        if not isinstance(items, list):
            items = [items]

        if item_index < 0 or item_index >= len(items):
            raise IndexError(f"Item index {item_index} out of range")

        item = items[item_index]
        context_inputs = self._prepare_inputs(node_name, skip_scattered=True)
        if inputs:
            context_inputs.update(inputs)

        item_inputs = dict(context_inputs)
        item_inputs[target_port] = item
        result = self._execute_single_node(node_name, item_inputs)

        if node_name in self.scattered_results:
            self.scattered_results[node_name][item_index] = result

        return result

    def execute_all(self, entry_inputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        execution_order = self.graph.get_execution_order()
        self.results = {}

        for node_name in execution_order:
            user_input = entry_inputs.get(node_name, {})
            self.execute_node(node_name, user_input)

        return self.results
