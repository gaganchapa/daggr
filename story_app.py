import gradio as gr

from daggr import FnNode, InferenceNode, GradioNode

story_prompt = InputNode(inputs=[gr.Textbox(label="Story Prompt", value="Write a story about a cat")])
story_writer = InferenceNode(model="moonshotai/Kimi-K2-Instruct-0905", outputs=[gr.Textbox(label="Story", lines=10)])






