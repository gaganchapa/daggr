import gradio as gr

from daggr import FnNode, Graph


def generate_items(prefix: str) -> list:
    return [
        {"name": f"{prefix}_apple", "value": 10},
        {"name": f"{prefix}_banana", "value": 20},
    ]


items = FnNode(
    fn=generate_items,
    inputs={
        "prefix": gr.Textbox(label="Prefix", value="fruit"),
    },
    outputs={
        "items": gr.JSON(visible=False),  # THE FIX
    },
)


def process(name: str, value: int) -> str:
    return name


processed = FnNode(
    fn=process,
    inputs={
        "name": items.items.each["name"],  # scatter
        "value": items.items.each["value"],
    },
    outputs={"result": gr.Textbox()},
)


def combine(results: list) -> str:
    return f"Got: {results}"


final = FnNode(
    fn=combine,
    inputs={"results": processed.result.all()},  # gather
    outputs={"out": gr.Textbox()},
)


graph = Graph(name="Scatter Bug Fixed", nodes=[items, processed, final])
graph.launch()
