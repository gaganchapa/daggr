import gradio as gr
from fastapi.testclient import TestClient

from daggr import FnNode, Graph
from daggr.server import DaggrServer


class TestWorkflowAPI:
    def test_simple_two_node_workflow_api(self):
        def double(x):
            return x * 2

        def add_ten(y):
            return y + 10

        node_a = FnNode(
            double,
            name="doubler",
            inputs={"x": gr.Number(label="Input Number", value=5)},
            outputs={"result": gr.Number(label="Doubled")},
        )
        node_b = FnNode(
            add_ten,
            name="adder",
            inputs={"y": node_a.result},
            outputs={"result": gr.Number(label="Final Result")},
        )

        graph = Graph("test_simple", nodes=[node_b], persist_key=False)
        server = DaggrServer(graph)
        client = TestClient(server.app)

        schema_response = client.get("/api/schema")
        assert schema_response.status_code == 200
        schema = schema_response.json()
        assert len(schema["subgraphs"]) == 1
        assert schema["subgraphs"][0]["id"] == "main"
        assert len(schema["subgraphs"][0]["inputs"]) == 1
        assert schema["subgraphs"][0]["inputs"][0]["node"] == "doubler"
        assert schema["subgraphs"][0]["inputs"][0]["port"] == "x"

        call_response = client.post(
            "/api/call",
            json={"inputs": {"doubler__x": 7}},
        )
        assert call_response.status_code == 200
        outputs = call_response.json()["outputs"]
        assert "adder" in outputs
        assert outputs["adder"]["result"] == 24  # (7 * 2) + 10 = 24

    def test_multi_node_chain_workflow_api(self):
        def step1(a, b):
            return a + b

        def step2(x):
            return x * 3

        def step3(val):
            return val - 5

        node_a = FnNode(
            step1,
            name="adder",
            inputs={
                "a": gr.Number(label="First Number", value=1),
                "b": gr.Number(label="Second Number", value=2),
            },
            outputs={"result": gr.Number(label="Sum")},
        )
        node_b = FnNode(
            step2,
            name="multiplier",
            inputs={"x": node_a.result},
            outputs={"result": gr.Number(label="Tripled")},
        )
        node_c = FnNode(
            step3,
            name="subtractor",
            inputs={"val": node_b.result},
            outputs={"result": gr.Number(label="Final")},
        )

        graph = Graph("test_chain", nodes=[node_c], persist_key=False)
        server = DaggrServer(graph)
        client = TestClient(server.app)

        schema_response = client.get("/api/schema")
        assert schema_response.status_code == 200
        schema = schema_response.json()
        assert len(schema["subgraphs"][0]["inputs"]) == 2
        input_ids = {inp["id"] for inp in schema["subgraphs"][0]["inputs"]}
        assert "adder__a" in input_ids
        assert "adder__b" in input_ids
        assert len(schema["subgraphs"][0]["outputs"]) == 1
        assert schema["subgraphs"][0]["outputs"][0]["node"] == "subtractor"

        call_response = client.post(
            "/api/call",
            json={"inputs": {"adder__a": 10, "adder__b": 5}},
        )
        assert call_response.status_code == 200
        outputs = call_response.json()["outputs"]
        assert "subtractor" in outputs
        assert outputs["subtractor"]["result"] == 40  # ((10 + 5) * 3) - 5 = 40
