from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import gradio as gr
from gradio_canvas_component import CanvasComponent

from daggr.executor import SequentialExecutor
from daggr.state import SessionState

if TYPE_CHECKING:
    from daggr.graph import Graph


class WorkflowCanvas(gr.HTML):
    """Legacy HTML-based canvas - kept for reference."""

    def __init__(self, graph_data: dict | None = None, **kwargs):
        html_template = """
        <div class="workflow-container">
            <div class="workflow-canvas" id="workflow-canvas">
                {{#each value.nodes}}
                <div class="node node-{{this.type}}" 
                     id="node-{{this.id}}" 
                     style="left: {{this.x}}px; top: {{this.y}}px;"
                     data-node-id="{{this.id}}"
                     data-node-name="{{this.name}}"
                     data-node-type="{{this.type}}">
                    <div class="node-header">
                        <span class="node-type-badge">{{this.type}}</span>
                        <span class="node-title">{{this.name}}</span>
                        {{#unless this.is_input_node}}
                        <button class="node-play-btn {{#if this.is_output_node}}node-play-btn-primary{{/if}}" data-node="{{this.name}}" title="Run to here">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="6,4 20,12 6,20"/>
                            </svg>
                        </button>
                        {{/unless}}
                    </div>
                    <div class="node-body">
                        <div class="node-ports">
                            <div class="input-ports">
                                {{#each this.inputs}}
                                <div class="port input-port" data-port="{{this.name}}" data-node="{{../id}}" data-history-count="{{this.history_count}}">
                                    <span class="port-dot"></span>
                                    <span class="port-label">{{this.name}}</span>
                                    {{#if this.history_count}}
                                    <button class="history-btn" data-node="{{../name}}" data-port="{{this.name}}" title="View history">
                                        <span class="history-count">{{this.history_count}}</span>
                                        📂
                                    </button>
                                    {{/if}}
                                </div>
                                {{/each}}
                            </div>
                            <div class="output-ports">
                                {{#each this.outputs}}
                                <div class="port output-port" data-port="{{this}}" data-node="{{../id}}">
                                    <span class="port-label">{{this}}</span>
                                    <span class="port-dot"></span>
                                </div>
                                {{/each}}
                            </div>
                        </div>
                        {{#if this.input_components}}
                        <div class="node-input-area">
                            {{#each this.input_components}}
                            <div class="input-component" data-component-type="{{this.type}}" data-port="{{this.label}}">
                                {{#if this.is_textbox}}
                                <label class="input-label">{{this.label}}</label>
                                <input type="text" class="node-text-input" 
                                       data-node="{{../name}}" 
                                       data-port="{{this.label}}"
                                       placeholder="{{this.placeholder}}"
                                       value="{{this.value}}">
                                {{/if}}
                                {{#if this.is_textarea}}
                                <label class="input-label">{{this.label}}</label>
                                <textarea class="node-textarea-input" 
                                          data-node="{{../name}}" 
                                          data-port="{{this.label}}"
                                          placeholder="{{this.placeholder}}">{{this.value}}</textarea>
                                {{/if}}
                            </div>
                            {{/each}}
                        </div>
                        {{/if}}
                        {{#if this.has_input}}
                        <div class="node-input-area">
                            <input type="text" class="node-text-input" 
                                   data-node="{{this.name}}" 
                                   placeholder="Enter value..."
                                   value="{{this.input_value}}">
                        </div>
                        {{/if}}
                    </div>
                    {{#if this.output_components}}
                    <div class="node-outputs">
                        {{#each this.output_components}}
                        <div class="output-component" data-component-type="{{this.type}}">
                            {{#if this.is_audio}}
                            <div class="audio-player">
                                <span class="audio-label">{{this.label}}</span>
                                {{#if this.value}}
                                <audio controls src="{{this.value}}"></audio>
                                {{else}}
                                <div class="audio-placeholder">No audio generated</div>
                                {{/if}}
                            </div>
                            {{/if}}
                            {{#if this.is_json}}
                            <div class="json-display">
                                <span class="json-label">{{this.label}}</span>
                                <pre class="json-content">{{this.value}}</pre>
                            </div>
                            {{/if}}
                            {{#if this.is_text}}
                            <div class="text-display">
                                <span class="text-label">{{this.label}}</span>
                                <div class="text-content">{{this.value}}</div>
                            </div>
                            {{/if}}
                        </div>
                        {{/each}}
                    </div>
                    {{/if}}
                    {{#if this.is_map_node}}
                    <div class="map-node-items" data-node="{{this.name}}" data-expanded="false">
                        <div class="map-header" onclick="toggleMapExpand(this)">
                            <span class="map-count">[{{this.map_item_count}} items]</span>
                            <span class="map-toggle">▼ Expand</span>
                        </div>
                        <div class="map-items-list">
                            {{#each this.map_items}}
                            <div class="map-item" data-index="{{this.index}}">
                                <div class="map-item-header">
                                    <span class="map-item-index">{{this.index}}.</span>
                                    <span class="map-item-preview">{{this.preview}}</span>
                                    <button class="map-item-rerun" data-node="{{../name}}" data-index="{{this.index}}" title="Re-run this item">🔄</button>
                                </div>
                                {{#if this.output}}
                                <div class="map-item-output">
                                    {{#if this.is_audio_output}}
                                    <audio controls src="{{this.output}}"></audio>
                                    {{else}}
                                    <pre>{{this.output}}</pre>
                                    {{/if}}
                                </div>
                                {{/if}}
                            </div>
                            {{/each}}
                        </div>
                    </div>
                    {{/if}}
                    <div class="node-status" data-status="{{this.status}}">
                        <span class="status-indicator"></span>
                        <span class="status-text">{{this.status}}</span>
                    </div>
                    {{#if this.result}}
                    <div class="node-result">
                        <pre>{{this.result}}</pre>
                    </div>
                    {{/if}}
                </div>
                {{/each}}
            </div>
            <svg class="workflow-edges" id="workflow-edges">
                {{#each value.edges}}
                <g class="edge-group" data-edge-id="{{this.id}}">
                    <path class="edge" 
                          data-from="{{this.from_node}}" 
                          data-from-port="{{this.from_port}}"
                          data-to="{{this.to_node}}" 
                          data-to-port="{{this.to_port}}"
                          d=""/>
                </g>
                {{/each}}
            </svg>
            <div class="history-modal" id="history-modal" style="display:none;">
                <div class="history-modal-backdrop"></div>
                <div class="history-modal-content">
                    <div class="history-modal-header">
                        <span class="history-modal-title">Select version</span>
                        <button class="history-modal-close">✕</button>
                    </div>
                    <div class="history-modal-body">
                    </div>
                    <div class="history-modal-footer">
                        <button class="history-use-btn">Use Selected</button>
                    </div>
                </div>
            </div>
        </div>
        """

        css_template = """
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap');
        
        .workflow-container {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(249, 115, 22, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(251, 146, 60, 0.05) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(234, 88, 12, 0.03) 0%, transparent 70%),
                linear-gradient(180deg, #0a0a0a 0%, #0f0f0f 50%, #0a0a0a 100%);
            border-radius: 0;
            overflow: auto;
            font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
            border: none;
        }
        
        .workflow-canvas {
            position: absolute;
            width: 3000px;
            height: 2000px;
            background-image: 
                radial-gradient(circle at center, rgba(249, 115, 22, 0.015) 0%, transparent 2px),
                linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
            background-size: 40px 40px, 20px 20px, 20px 20px;
        }
        
        .workflow-edges {
            position: absolute;
            width: 3000px;
            height: 2000px;
            pointer-events: none;
            z-index: 5;
        }
        
        .edge-group {
            pointer-events: auto;
        }
        
        .edge {
            fill: none;
            stroke: #f97316;
            stroke-width: 3;
            stroke-linecap: round;
            filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.5));
            transition: stroke-width 0.2s, opacity 0.2s;
            opacity: 0.85;
        }
        
        .edge-group:hover .edge {
            stroke-width: 4;
            opacity: 1;
        }
        
        .node {
            position: absolute;
            min-width: 280px;
            max-width: 360px;
            background: linear-gradient(165deg, rgba(20, 20, 20, 0.98) 0%, rgba(10, 10, 10, 0.99) 100%);
            border: 1px solid rgba(249, 115, 22, 0.25);
            border-radius: 16px;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.6),
                0 0 0 1px rgba(255, 255, 255, 0.02) inset,
                0 0 60px -20px rgba(249, 115, 22, 0.1);
            z-index: 10;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(20px);
        }
        
        .node:hover {
            box-shadow: 
                0 16px 48px rgba(0, 0, 0, 0.7),
                0 0 0 1px rgba(249, 115, 22, 0.5) inset,
                0 0 80px -20px rgba(249, 115, 22, 0.25);
            border-color: rgba(249, 115, 22, 0.6);
            transform: translateY(-3px);
        }
        
        .node-header {
            padding: 14px 16px;
            background: linear-gradient(135deg, rgba(249, 115, 22, 0.15) 0%, rgba(234, 88, 12, 0.08) 100%);
            border-radius: 15px 15px 0 0;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid rgba(249, 115, 22, 0.15);
        }
        
        .node-play-btn {
            margin-left: auto;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            border: 2px solid #f97316;
            background: rgba(249, 115, 22, 0.15);
            color: #f97316;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            padding: 0;
        }
        
        .node-play-btn svg {
            width: 12px;
            height: 12px;
            margin-left: 2px;
            fill: #f97316;
        }
        
        .node-play-btn:hover {
            background: rgba(249, 115, 22, 0.3);
            border-color: #fb923c;
            transform: scale(1.1);
        }
        
        .node-play-btn:hover svg {
            fill: #fb923c;
        }
        
        .node-play-btn-primary {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            border: none;
            color: #fff;
            box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4);
        }
        
        .node-play-btn-primary svg {
            width: 14px;
            height: 14px;
            fill: #fff;
        }
        
        .node-play-btn-primary:hover {
            background: linear-gradient(135deg, #fb923c 0%, #f97316 100%);
            transform: scale(1.15);
            box-shadow: 0 6px 20px rgba(249, 115, 22, 0.6);
        }
        
        .node-play-btn-primary:hover svg {
            fill: #fff;
        }
        
        .node-type-badge {
            font-size: 9px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 5px 10px;
            border-radius: 8px;
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .node-FN .node-type-badge { 
            background: linear-gradient(135deg, #fb923c 0%, #f97316 100%);
            box-shadow: 0 4px 12px rgba(251, 146, 60, 0.4);
        }
        .node-GRADIO .node-type-badge { 
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4);
        }
        .node-MODEL .node-type-badge { 
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
            box-shadow: 0 4px 12px rgba(34, 197, 94, 0.4);
        }
        .node-MAP .node-type-badge {
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4);
        }
        .node-INPUT .node-type-badge {
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.4);
        }
        .node-ACTION .node-type-badge,
        .node-SELECT .node-type-badge,
        .node-IMAGE .node-type-badge,
        .node-APPROVE .node-type-badge { 
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            color: #000000;
            box-shadow: 0 4px 12px rgba(251, 191, 36, 0.4);
        }
        
        .node-title {
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            letter-spacing: 0.3px;
        }
        
        .node-body {
            padding: 16px;
        }
        
        .node-ports {
            display: flex;
            justify-content: space-between;
            gap: 24px;
        }
        
        .input-ports, .output-ports {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .output-ports {
            align-items: flex-end;
        }
        
        .port {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 4px 0;
            transition: all 0.2s ease;
        }
        
        .port:hover {
            transform: translateX(2px);
        }
        
        .output-port:hover {
            transform: translateX(-2px);
        }
        
        .port-dot {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: rgba(30, 30, 30, 0.9);
            border: 2px solid rgba(249, 115, 22, 0.4);
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
            flex-shrink: 0;
        }
        
        .input-port .port-dot { 
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            border-color: #f97316;
            box-shadow: 0 0 16px rgba(249, 115, 22, 0.5);
        }
        .output-port .port-dot { 
            background: linear-gradient(135deg, #fb923c 0%, #f97316 100%);
            border-color: #fb923c;
            box-shadow: 0 0 16px rgba(251, 146, 60, 0.5);
        }
        
        .port:hover .port-dot {
            transform: scale(1.3);
            box-shadow: 0 0 20px rgba(249, 115, 22, 0.7);
        }
        
        .port-label {
            font-family: 'JetBrains Mono', 'Monaco', 'Consolas', monospace;
            font-size: 12px;
            font-weight: 500;
            letter-spacing: 0.4px;
            color: #e5e5e5;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
        }
        
        .history-btn {
            background: rgba(249, 115, 22, 0.2);
            border: 1px solid rgba(249, 115, 22, 0.4);
            border-radius: 6px;
            padding: 2px 6px;
            font-size: 10px;
            color: #fb923c;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: all 0.2s;
        }
        
        .history-btn:hover {
            background: rgba(249, 115, 22, 0.4);
            border-color: #f97316;
        }
        
        .history-count {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }
        
        .node-input-area {
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid rgba(249, 115, 22, 0.15);
        }
        
        .input-component {
            margin-bottom: 12px;
        }
        
        .input-label {
            display: block;
            font-size: 11px;
            font-weight: 600;
            color: #a3a3a3;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .node-text-input, .node-textarea-input {
            width: 100%;
            padding: 12px 14px;
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid rgba(249, 115, 22, 0.3);
            border-radius: 10px;
            color: #ffffff;
            font-size: 13px;
            font-family: 'JetBrains Mono', 'Monaco', 'Consolas', monospace;
            box-sizing: border-box;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .node-textarea-input {
            min-height: 80px;
            resize: vertical;
        }
        
        .node-text-input::placeholder, .node-textarea-input::placeholder {
            color: rgba(180, 180, 180, 0.5);
        }
        
        .node-text-input:focus, .node-textarea-input:focus {
            outline: none;
            border-color: #f97316;
            box-shadow: 
                0 0 0 4px rgba(249, 115, 22, 0.15),
                0 0 30px rgba(249, 115, 22, 0.2);
            background: rgba(0, 0, 0, 0.8);
        }
        
        .node-outputs {
            padding: 12px 16px;
            border-top: 1px solid rgba(249, 115, 22, 0.1);
            background: rgba(0, 0, 0, 0.3);
        }
        
        .output-component {
            margin-bottom: 10px;
        }
        
        .output-component:last-child {
            margin-bottom: 0;
        }
        
        .audio-player {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            padding: 10px;
        }
        
        .audio-label, .json-label, .text-label {
            display: block;
            font-size: 10px;
            font-weight: 600;
            color: #a3a3a3;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .audio-player audio {
            width: 100%;
            height: 36px;
        }
        
        .audio-placeholder {
            color: #666;
            font-size: 12px;
            font-style: italic;
            padding: 8px;
            text-align: center;
        }
        
        .json-display, .text-display {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            padding: 10px;
        }
        
        .json-content, .text-content {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #4ade80;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 120px;
            overflow-y: auto;
        }
        
        .map-node-items {
            border-top: 1px solid rgba(139, 92, 246, 0.2);
            background: rgba(139, 92, 246, 0.05);
        }
        
        .map-header {
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .map-header:hover {
            background: rgba(139, 92, 246, 0.1);
        }
        
        .map-count {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #a78bfa;
            font-weight: 600;
        }
        
        .map-toggle {
            font-size: 11px;
            color: #8b5cf6;
        }
        
        .map-items-list {
            display: none;
            max-height: 300px;
            overflow-y: auto;
            padding: 0 16px 16px;
        }
        
        .map-node-items[data-expanded="true"] .map-items-list {
            display: block;
        }
        
        .map-node-items[data-expanded="true"] .map-toggle {
            transform: rotate(180deg);
        }
        
        .map-item {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(139, 92, 246, 0.2);
            border-radius: 8px;
            margin-bottom: 8px;
            overflow: hidden;
        }
        
        .map-item:last-child {
            margin-bottom: 0;
        }
        
        .map-item-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            background: rgba(139, 92, 246, 0.1);
        }
        
        .map-item-index {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #a78bfa;
            font-weight: 600;
        }
        
        .map-item-preview {
            flex: 1;
            font-size: 11px;
            color: #d4d4d4;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .map-item-rerun {
            background: rgba(139, 92, 246, 0.2);
            border: 1px solid rgba(139, 92, 246, 0.4);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .map-item-rerun:hover {
            background: rgba(139, 92, 246, 0.4);
        }
        
        .map-item-output {
            padding: 8px 10px;
        }
        
        .map-item-output audio {
            width: 100%;
            height: 32px;
        }
        
        .map-item-output pre {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: #4ade80;
            margin: 0;
        }
        
        .node-status {
            padding: 12px 16px;
            border-top: 1px solid rgba(249, 115, 22, 0.1);
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: rgba(80, 80, 80, 0.5);
            transition: all 0.3s ease;
        }
        
        .node-status[data-status="pending"] .status-indicator { 
            background: rgba(120, 120, 120, 0.5);
            box-shadow: 0 0 8px rgba(120, 120, 120, 0.3);
        }
        .node-status[data-status="pending"] .status-text { 
            color: rgba(180, 180, 180, 0.8);
        }
        
        .node-status[data-status="running"] .status-indicator { 
            background: #f97316;
            box-shadow: 0 0 16px rgba(249, 115, 22, 0.7);
            animation: pulse 1s ease-in-out infinite;
        }
        .node-status[data-status="running"] .status-text { 
            color: #fb923c;
        }
        
        .node-status[data-status="completed"] .status-indicator { 
            background: #22c55e;
            box-shadow: 0 0 16px rgba(34, 197, 94, 0.6);
        }
        .node-status[data-status="completed"] .status-text { 
            color: #4ade80;
        }
        
        .node-status[data-status="error"] .status-indicator { 
            background: #ef4444;
            box-shadow: 0 0 16px rgba(239, 68, 68, 0.6);
        }
        .node-status[data-status="error"] .status-text { 
            color: #f87171;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.4); }
        }
        
        .node-result {
            padding: 12px 16px;
            border-top: 1px solid rgba(249, 115, 22, 0.1);
            background: rgba(0, 0, 0, 0.5);
            border-radius: 0 0 15px 15px;
            max-height: 140px;
            overflow-y: auto;
        }
        
        .node-result::-webkit-scrollbar {
            width: 6px;
        }
        .node-result::-webkit-scrollbar-track {
            background: rgba(20, 20, 20, 0.5);
            border-radius: 3px;
        }
        .node-result::-webkit-scrollbar-thumb {
            background: rgba(249, 115, 22, 0.4);
            border-radius: 3px;
        }
        
        .node-result pre {
            margin: 0;
            font-size: 11px;
            color: #4ade80;
            font-family: 'JetBrains Mono', 'Monaco', 'Consolas', monospace;
            white-space: pre-wrap;
            word-break: break-word;
            line-height: 1.6;
            text-shadow: 0 0 15px rgba(74, 222, 128, 0.3);
        }
        
        .history-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 1000;
        }
        
        .history-modal-backdrop {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(4px);
        }
        
        .history-modal-content {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 500px;
            max-width: 90vw;
            max-height: 80vh;
            background: linear-gradient(165deg, rgba(30, 30, 30, 0.98) 0%, rgba(15, 15, 15, 0.99) 100%);
            border: 1px solid rgba(249, 115, 22, 0.3);
            border-radius: 16px;
            box-shadow: 0 24px 64px rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
        }
        
        .history-modal-header {
            padding: 16px 20px;
            border-bottom: 1px solid rgba(249, 115, 22, 0.2);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .history-modal-title {
            font-size: 16px;
            font-weight: 600;
            color: #fff;
        }
        
        .history-modal-close {
            background: none;
            border: none;
            color: #888;
            font-size: 18px;
            cursor: pointer;
            padding: 4px 8px;
            transition: color 0.2s;
        }
        
        .history-modal-close:hover {
            color: #fff;
        }
        
        .history-modal-body {
            flex: 1;
            overflow-y: auto;
            padding: 16px 20px;
        }
        
        .history-item {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(249, 115, 22, 0.2);
            border-radius: 10px;
            margin-bottom: 12px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .history-item:hover {
            border-color: rgba(249, 115, 22, 0.5);
            background: rgba(249, 115, 22, 0.05);
        }
        
        .history-item.selected {
            border-color: #f97316;
            background: rgba(249, 115, 22, 0.1);
        }
        
        .history-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .history-item-version {
            font-weight: 600;
            color: #fb923c;
        }
        
        .history-item-time {
            font-size: 11px;
            color: #888;
        }
        
        .history-item-input {
            font-size: 11px;
            color: #a3a3a3;
            margin-bottom: 8px;
        }
        
        .history-item-preview {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 6px;
            padding: 8px;
        }
        
        .history-item-preview audio {
            width: 100%;
            height: 32px;
        }
        
        .history-modal-footer {
            padding: 16px 20px;
            border-top: 1px solid rgba(249, 115, 22, 0.2);
            display: flex;
            justify-content: flex-end;
        }
        
        .history-use-btn {
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            border: none;
            color: #fff;
            padding: 10px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .history-use-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(249, 115, 22, 0.4);
        }
        """

        js_on_load = """
        const container = element.querySelector('.workflow-container');
        const canvas = element.querySelector('.workflow-canvas');
        const svgEdges = element.querySelector('.workflow-edges');
        const historyModal = element.querySelector('#history-modal');
        
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = `
            <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#f97316;stop-opacity:1" />
                <stop offset="50%" style="stop-color:#fb923c;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#fdba74;stop-opacity:1" />
            </linearGradient>
        `;
        svgEdges.insertBefore(defs, svgEdges.firstChild);
        
        function getPortPosition(node, portEl, isOutput) {
            if (portEl) {
                const svgRect = svgEdges.getBoundingClientRect();
                const portRect = portEl.getBoundingClientRect();
                const x = portRect.left - svgRect.left + portRect.width / 2;
                const y = portRect.top - svgRect.top + portRect.height / 2;
                return { x, y };
            }
            
            const nodeX = parseFloat(node.style.left) || 0;
            const nodeY = parseFloat(node.style.top) || 0;
            if (isOutput) {
                return { x: nodeX + node.offsetWidth, y: nodeY + node.offsetHeight / 2 };
            }
            return { x: nodeX, y: nodeY + node.offsetHeight / 2 };
        }
        
        function updateEdges() {
            const edgeGroups = svgEdges.querySelectorAll('.edge-group');
            edgeGroups.forEach(group => {
                const edge = group.querySelector('.edge');
                const fromNodeId = edge.dataset.from;
                const fromPort = edge.dataset.fromPort;
                const toNodeId = edge.dataset.to;
                const toPort = edge.dataset.toPort;
                
                const fromNode = element.querySelector(`#node-${fromNodeId}`);
                const toNode = element.querySelector(`#node-${toNodeId}`);
                
                if (!fromNode || !toNode) return;
                
                const fromPortEl = fromNode.querySelector(`.output-port[data-port="${fromPort}"] .port-dot`);
                const toPortEl = toNode.querySelector(`.input-port[data-port="${toPort}"] .port-dot`);
                
                const from = getPortPosition(fromNode, fromPortEl, true);
                const to = getPortPosition(toNode, toPortEl, false);
                
                const dx = Math.abs(to.x - from.x);
                const controlOffset = Math.max(dx * 0.4, 60);
                const path = `M ${from.x} ${from.y} C ${from.x + controlOffset} ${from.y}, ${to.x - controlOffset} ${to.y}, ${to.x} ${to.y}`;
                edge.setAttribute('d', path);
            });
        }
        
        element.querySelectorAll('.node-text-input, .node-textarea-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const nodeName = e.target.dataset.node;
                const portName = e.target.dataset.port || nodeName;
                if (!props.value.inputs) {
                    props.value.inputs = {};
                }
                if (!props.value.inputs[nodeName]) {
                    props.value.inputs[nodeName] = {};
                }
                props.value.inputs[nodeName][portName] = e.target.value;
            });
        });
        
        element.querySelectorAll('.node-play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nodeName = btn.dataset.node;
                props.value.run_to_node = nodeName;
                props.value = {...props.value};
            });
        });
        
        element.querySelectorAll('.history-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nodeName = btn.dataset.node;
                const portName = btn.dataset.port;
                props.value.show_history = { node: nodeName, port: portName };
                props.value = {...props.value};
            });
        });
        
        element.querySelectorAll('.map-item-rerun').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nodeName = btn.dataset.node;
                const index = parseInt(btn.dataset.index);
                props.value.rerun_map_item = { node: nodeName, index: index };
                props.value = {...props.value};
            });
        });
        
        window.toggleMapExpand = function(header) {
            const mapItems = header.closest('.map-node-items');
            const expanded = mapItems.dataset.expanded === 'true';
            mapItems.dataset.expanded = !expanded;
            header.querySelector('.map-toggle').textContent = expanded ? '▼ Expand' : '▲ Collapse';
        };
        
        if (historyModal) {
            historyModal.querySelector('.history-modal-backdrop').addEventListener('click', () => {
                historyModal.style.display = 'none';
            });
            historyModal.querySelector('.history-modal-close').addEventListener('click', () => {
                historyModal.style.display = 'none';
            });
        }
        
        setTimeout(updateEdges, 100);
        setTimeout(updateEdges, 300);
        setTimeout(updateEdges, 500);
        setTimeout(updateEdges, 1000);
        
        window.addEventListener('load', () => setTimeout(updateEdges, 100));
        
        const resizeObserver = new ResizeObserver(() => requestAnimationFrame(updateEdges));
        resizeObserver.observe(container);
        
        container.addEventListener('scroll', () => requestAnimationFrame(updateEdges));
        
        const mutationObserver = new MutationObserver(() => requestAnimationFrame(updateEdges));
        mutationObserver.observe(canvas, { childList: true, subtree: true });
        """

        super().__init__(
            value=graph_data
            or {
                "nodes": [],
                "edges": [],
                "inputs": {},
                "history": {},
                "session_id": None,
            },
            html_template=html_template,
            css_template=css_template,
            js_on_load=js_on_load,
            **kwargs,
        )


class UIGenerator:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.executor = SequentialExecutor(graph)
        self.state = SessionState()
        self.session_id: Optional[str] = None

    def _get_node_type(self, node, node_name: str) -> str:
        if self._has_scattered_input(node_name):
            base_type = self._get_base_node_type(node)
            return f"MAP:{base_type}"

        return self._get_base_node_type(node)

    def _get_base_node_type(self, node) -> str:
        type_map = {
            "FnNode": "FN",
            "TextInput": "INPUT",
            "ImageInput": "IMAGE",
            "ChooseOne": "SELECT",
            "Approve": "APPROVE",
            "GradioNode": "GRADIO",
            "InferenceNode": "MODEL",
            "InteractionNode": "ACTION",
        }
        class_name = node.__class__.__name__
        return type_map.get(class_name, class_name.upper())

    def _has_scattered_input(self, node_name: str) -> bool:
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                return True
        return False

    def _get_scattered_edge(self, node_name: str):
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                return edge
        return None

    def _is_entry_or_interaction(self, node_name: str) -> bool:
        from daggr.node import InteractionNode

        node = self.graph.nodes[node_name]
        if isinstance(node, InteractionNode):
            return True
        if node._input_components:
            return True
        return self.graph._nx_graph.in_degree(node_name) == 0

    def _has_component_inputs(self, node_name: str) -> bool:
        node = self.graph.nodes[node_name]
        return bool(node._input_components)

    def _get_node_name(self, node) -> str:
        return node._name

    def _get_component_type(self, component) -> str:
        class_name = component.__class__.__name__
        type_map = {
            "Audio": "audio",
            "Textbox": "textbox",
            "TextArea": "textarea",
            "JSON": "json",
            "Chatbot": "json",
            "Image": "image",
            "Number": "number",
            "Markdown": "markdown",
            "Text": "text",
        }
        return type_map.get(class_name, "text")

    def _build_input_components(self, node) -> List[Dict[str, Any]]:
        if not node._input_components:
            return []

        components = []
        for port_name, comp in node._input_components.items():
            comp_type = self._get_component_type(comp)
            label = getattr(comp, "label", "") or port_name
            placeholder = getattr(comp, "placeholder", "") or ""
            default_value = getattr(comp, "value", "") or ""
            components.append(
                {
                    "type": comp_type,
                    "label": label,
                    "port_name": port_name,
                    "placeholder": placeholder,
                    "value": default_value,
                    "is_textbox": comp_type == "textbox",
                    "is_textarea": comp_type == "textarea",
                }
            )
        return components

    def _build_output_components(
        self, node, result: Any = None
    ) -> List[Dict[str, Any]]:
        if not node._output_components:
            return []

        components = []
        for port_name, comp in node._output_components.items():
            visible = getattr(comp, "visible", True)
            if visible is False:
                continue

            comp_type = self._get_component_type(comp)
            label = getattr(comp, "label", "") or port_name

            value = None
            if result is not None:
                if isinstance(result, dict):
                    value = result.get(port_name, result.get(label))
                else:
                    value = result

            if comp_type == "json" and value is not None:
                value = json.dumps(value, indent=2, default=str)
            elif comp_type == "markdown" and value is not None:
                value = str(value)
            elif value is not None:
                value = str(value)

            components.append(
                {
                    "type": comp_type,
                    "label": label,
                    "port_name": port_name,
                    "value": value or "",
                    "is_audio": comp_type == "audio",
                    "is_json": comp_type == "json",
                    "is_text": comp_type in ("text", "textbox"),
                    "is_markdown": comp_type == "markdown",
                }
            )
        return components

    def _build_scattered_items(
        self, node_name: str, result: Any = None
    ) -> List[Dict[str, Any]]:
        scattered_edge = self._get_scattered_edge(node_name)
        if not scattered_edge:
            return []

        item_output_type = "text"
        if scattered_edge.item_output:
            item_output_type = self._get_component_type(scattered_edge.item_output)

        items = []
        if result and isinstance(result, dict) and "_scattered_results" in result:
            results = result["_scattered_results"]
            source_items = result.get("_items", [])
            for i, item_result in enumerate(results):
                source_item = source_items[i] if i < len(source_items) else None
                preview = ""
                output = None

                if isinstance(source_item, dict):
                    preview_parts = []
                    for k, v in list(source_item.items())[:2]:
                        preview_parts.append(f"{k}: {str(v)[:20]}")
                    preview = ", ".join(preview_parts)
                elif source_item:
                    preview = str(source_item)[:50]

                if isinstance(item_result, dict):
                    first_key = list(item_result.keys())[0] if item_result else None
                    if first_key:
                        output = str(item_result[first_key])
                else:
                    output = str(item_result) if item_result else None

                items.append(
                    {
                        "index": i + 1,
                        "preview": preview or f"Item {i + 1}",
                        "output": output,
                        "is_audio_output": item_output_type == "audio",
                    }
                )
        return items

    def _compute_node_depths(self) -> Dict[str, int]:
        depths: Dict[str, int] = {}
        connections = self.graph.get_connections()

        for node_name in self.graph.nodes:
            if self.graph._nx_graph.in_degree(node_name) == 0:
                depths[node_name] = 0

        changed = True
        while changed:
            changed = False
            for source, _, target, _ in connections:
                if source in depths:
                    new_depth = depths[source] + 1
                    if target not in depths or depths[target] < new_depth:
                        depths[target] = new_depth
                        changed = True

        for node_name in self.graph.nodes:
            if node_name not in depths:
                depths[node_name] = 0

        return depths

    def _is_output_node(self, node_name: str) -> bool:
        return self.graph._nx_graph.out_degree(node_name) == 0

    def _build_graph_data(
        self,
        node_results: Dict[str, Any] | None = None,
        node_statuses: Dict[str, str] | None = None,
        input_values: Dict[str, Any] | None = None,
        history: Dict[str, Dict[str, List[Dict]]] | None = None,
    ) -> dict:
        node_results = node_results or {}
        node_statuses = node_statuses or {}
        input_values = input_values or {}
        history = history or {}

        depths = self._compute_node_depths()
        max_depth = max(depths.values()) if depths else 0

        nodes_by_depth: Dict[int, List[str]] = {}
        for node_name, depth in depths.items():
            if depth not in nodes_by_depth:
                nodes_by_depth[depth] = []
            nodes_by_depth[depth].append(node_name)

        x_spacing = 400
        y_spacing = 320
        x_start = 50
        y_start = 50

        node_positions: Dict[str, tuple] = {}
        for depth in range(max_depth + 1):
            depth_nodes = nodes_by_depth.get(depth, [])
            for idx, node_name in enumerate(depth_nodes):
                x = x_start + depth * x_spacing
                y = y_start + idx * y_spacing
                node_positions[node_name] = (x, y)

        nodes = []
        for node_name in self.graph.nodes:
            node = self.graph.nodes[node_name]
            x, y = node_positions.get(node_name, (50, 50))

            has_component_inputs = self._has_component_inputs(node_name)

            result = node_results.get(node_name)
            result_str = ""
            is_scattered = self._has_scattered_input(node_name)
            if result is not None and not node._output_components and not is_scattered:
                if isinstance(result, dict):
                    display_result = {
                        k: v for k, v in result.items() if not k.startswith("_")
                    }
                    result_str = json.dumps(display_result, indent=2, default=str)[:300]
                elif isinstance(result, (list, tuple)):
                    result_str = json.dumps(list(result)[:5], default=str)
                else:
                    result_str = str(result)[:300]

            node_id = node_name.replace(" ", "_").replace("-", "_")

            connected_input_ports = set()
            for edge in self.graph._edges:
                if edge.target_node._name == node_name:
                    connected_input_ports.add(edge.target_port)

            input_ports_data = []
            for port in node._input_ports or []:
                if port in node._input_components:
                    continue
                if port in node._fixed_inputs:
                    continue
                port_history = history.get(node_name, {}).get(port, [])
                input_ports_data.append(
                    {
                        "name": port,
                        "history_count": len(port_history) if port_history else 0,
                    }
                )

            input_components = self._build_input_components(node)
            if input_components and node_name in input_values:
                for comp in input_components:
                    port_name = comp.get("port_name", comp["label"])
                    if port_name in input_values[node_name]:
                        comp["value"] = input_values[node_name][port_name]

            output_components = self._build_output_components(node, result)
            scattered_items = (
                self._build_scattered_items(node_name, result) if is_scattered else []
            )

            item_output_type = "text"
            scattered_edge = self._get_scattered_edge(node_name)
            if scattered_edge and scattered_edge.item_output:
                item_output_type = self._get_component_type(scattered_edge.item_output)

            is_output = self._is_output_node(node_name)
            is_entry = self.graph._nx_graph.in_degree(node_name) == 0

            nodes.append(
                {
                    "id": node_id,
                    "name": node_name,
                    "type": self._get_node_type(node, node_name),
                    "inputs": input_ports_data,
                    "outputs": node._output_ports or [],
                    "x": x,
                    "y": y,
                    "has_input": False,
                    "input_value": input_values.get(node_name, ""),
                    "input_components": input_components,
                    "output_components": output_components,
                    "is_map_node": is_scattered,
                    "map_items": scattered_items,
                    "map_item_count": len(scattered_items),
                    "item_output_type": item_output_type,
                    "status": node_statuses.get(node_name, "pending"),
                    "result": result_str,
                    "is_output_node": is_output,
                    "is_input_node": is_entry and not has_component_inputs,
                }
            )

        edges = []
        for i, edge in enumerate(self.graph._edges):
            edges.append(
                {
                    "id": f"edge_{i}",
                    "from_node": edge.source_node._name.replace(" ", "_").replace(
                        "-", "_"
                    ),
                    "from_port": edge.source_port,
                    "to_node": edge.target_node._name.replace(" ", "_").replace(
                        "-", "_"
                    ),
                    "to_port": edge.target_port,
                }
            )

        return {
            "name": self.graph.name,
            "nodes": nodes,
            "edges": edges,
            "inputs": input_values,
            "history": history,
            "session_id": self.session_id,
        }

    def _execute_workflow(self, canvas_data: dict) -> dict:
        from daggr.node import InteractionNode

        self.session_id = canvas_data.get("session_id") if canvas_data else None
        if not self.session_id:
            self.session_id = self.state.create_session(self.graph.name)

        execution_order = self.graph.get_execution_order()
        input_values = canvas_data.get("inputs", {}) if canvas_data else {}
        history = canvas_data.get("history", {}) if canvas_data else {}

        for node_name, node_inputs in input_values.items():
            if isinstance(node_inputs, dict):
                for port_name, value in node_inputs.items():
                    self.state.save_input(self.session_id, node_name, port_name, value)

        entry_inputs: Dict[str, Dict[str, Any]] = {}
        for node_name in execution_order:
            node = self.graph.nodes[node_name]
            if node._input_components:
                node_input_values = input_values.get(node_name, {})
                if isinstance(node_input_values, dict):
                    entry_inputs[node_name] = node_input_values
                else:
                    first_port = list(node._input_components.keys())[0]
                    entry_inputs[node_name] = {first_port: node_input_values}
            elif isinstance(node, InteractionNode):
                value = input_values.get(node_name, "")
                port = node._input_ports[0] if node._input_ports else "input"
                entry_inputs[node_name] = {port: value}

        node_results = {}
        node_statuses = {}
        self.executor.results = {}

        try:
            for node_name in execution_order:
                node_statuses[node_name] = "running"
                user_input = entry_inputs.get(node_name, {})
                result = self.executor.execute_node(node_name, user_input)
                node_results[node_name] = result
                node_statuses[node_name] = "completed"

                self.state.save_result(self.session_id, node_name, result)

                for edge in self.graph._edges:
                    if edge.source_node._name == node_name:
                        target_node = edge.target_node._name
                        target_port = edge.target_port
                        source_port = edge.source_port

                        if isinstance(result, dict) and source_port in result:
                            value = result[source_port]
                        else:
                            value = result

                        source_input = input_values.get(node_name, {})
                        self.state.add_to_history(
                            self.session_id,
                            target_node,
                            target_port,
                            value,
                            source_input,
                        )

                        if target_node not in history:
                            history[target_node] = {}
                        if target_port not in history[target_node]:
                            history[target_node][target_port] = []
                        history[target_node][target_port].append(
                            {
                                "value": value,
                                "source_input": source_input,
                            }
                        )

        except Exception as e:
            if len(node_results) < len(execution_order):
                current_node = execution_order[len(node_results)]
                node_statuses[current_node] = "error"
                node_results[current_node] = {"error": str(e)}

        return self._build_graph_data(
            node_results, node_statuses, input_values, history
        )

    def _rerun_edge(self, canvas_data: dict, edge_id: str) -> dict:
        edge_idx = int(edge_id.replace("edge_", ""))
        if edge_idx < 0 or edge_idx >= len(self.graph._edges):
            return canvas_data

        edge = self.graph._edges[edge_idx]
        source_node_name = edge.source_node._name

        input_values = canvas_data.get("inputs", {})
        history = canvas_data.get("history", {})

        user_input = input_values.get(source_node_name, {})
        result = self.executor.execute_node(source_node_name, user_input)

        target_node = edge.target_node._name
        target_port = edge.target_port
        source_port = edge.source_port

        if isinstance(result, dict) and source_port in result:
            value = result[source_port]
        else:
            value = result

        if self.session_id:
            self.state.add_to_history(
                self.session_id, target_node, target_port, value, user_input
            )

        if target_node not in history:
            history[target_node] = {}
        if target_port not in history[target_node]:
            history[target_node][target_port] = []
        history[target_node][target_port].append(
            {
                "value": value,
                "source_input": user_input,
            }
        )

        node_results = {source_node_name: result}
        node_statuses = {source_node_name: "completed"}

        return self._build_graph_data(
            node_results, node_statuses, input_values, history
        )

    def generate_ui(self) -> gr.Blocks:
        initial_data = self._build_graph_data()

        self._custom_css = """
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
            
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body, .gradio-container {
                background: #000000 !important;
                min-height: 100vh !important;
                font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif !important;
                overflow: hidden !important;
            }
            
            .gradio-container {
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
            }
            
            .main-container, .contain, .block {
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                background: transparent !important;
                border: none !important;
            }
            
            footer, .footer { display: none !important; }
            
            .run-btn { 
                position: fixed !important;
                bottom: 32px !important;
                right: 32px !important;
                z-index: 1000 !important;
                background: linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%) !important;
                border: none !important;
                font-weight: 600 !important;
                font-size: 14px !important;
                padding: 14px 32px !important;
                border-radius: 12px !important;
                box-shadow: 
                    0 8px 24px rgba(249, 115, 22, 0.5),
                    0 0 0 1px rgba(255, 255, 255, 0.1) inset !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                letter-spacing: 0.5px !important;
                text-transform: uppercase !important;
                font-family: 'Space Grotesk', sans-serif !important;
                color: #ffffff !important;
            }
            .run-btn:hover {
                transform: translateY(-3px) scale(1.02) !important;
                box-shadow: 
                    0 12px 35px rgba(249, 115, 22, 0.6),
                    0 0 0 1px rgba(255, 255, 255, 0.15) inset !important;
            }
            .run-btn:active {
                transform: translateY(-1px) scale(0.99) !important;
            }
            
            .button-row {
                position: fixed !important;
                bottom: 0 !important;
                right: 0 !important;
                z-index: 1000 !important;
                background: transparent !important;
                border: none !important;
                padding: 0 !important;
            }
        """

        def handle_canvas_action(canvas_data):
            if not canvas_data:
                return self._build_graph_data()

            run_to_node = canvas_data.get("run_to_node")
            if run_to_node:
                canvas_data["run_to_node"] = None
                return self._execute_to_node(canvas_data, run_to_node)

            return canvas_data

        with gr.Blocks(title=self.graph.name) as demo:
            canvas = CanvasComponent(value=initial_data)

            canvas.change(
                fn=handle_canvas_action,
                inputs=[canvas],
                outputs=[canvas],
            )

        return demo

    def _get_ancestors(self, node_name: str) -> List[str]:
        ancestors = set()
        to_visit = [node_name]
        while to_visit:
            current = to_visit.pop()
            for source, _, target, _ in self.graph.get_connections():
                if target == current and source not in ancestors:
                    ancestors.add(source)
                    to_visit.append(source)
        return list(ancestors)

    def _execute_to_node(self, canvas_data: dict, target_node: str) -> dict:
        from daggr.node import InteractionNode

        self.session_id = canvas_data.get("session_id") if canvas_data else None
        if not self.session_id:
            self.session_id = self.state.create_session(self.graph.name)

        ancestors = self._get_ancestors(target_node)
        nodes_to_run = ancestors + [target_node]

        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in nodes_to_run]

        input_values = canvas_data.get("inputs", {}) if canvas_data else {}
        history = canvas_data.get("history", {}) if canvas_data else {}

        entry_inputs: Dict[str, Dict[str, Any]] = {}
        for node_name in nodes_to_execute:
            node = self.graph.nodes[node_name]
            if node._input_components:
                node_input_values = input_values.get(node_name, {})
                if isinstance(node_input_values, dict):
                    entry_inputs[node_name] = node_input_values
                else:
                    first_port = list(node._input_components.keys())[0]
                    entry_inputs[node_name] = {first_port: node_input_values}
            elif isinstance(node, InteractionNode):
                value = input_values.get(node_name, "")
                port = node._input_ports[0] if node._input_ports else "input"
                entry_inputs[node_name] = {port: value}

        node_results = {}
        node_statuses = {}
        self.executor.results = {}

        try:
            for node_name in nodes_to_execute:
                node_statuses[node_name] = "running"
                user_input = entry_inputs.get(node_name, {})
                result = self.executor.execute_node(node_name, user_input)
                node_results[node_name] = result
                node_statuses[node_name] = "completed"

                self.state.save_result(self.session_id, node_name, result)

        except Exception as e:
            if nodes_to_execute:
                current_idx = len(node_results)
                if current_idx < len(nodes_to_execute):
                    current_node = nodes_to_execute[current_idx]
                    node_statuses[current_node] = "error"
                    node_results[current_node] = {"error": str(e)}

        return self._build_graph_data(
            node_results, node_statuses, input_values, history
        )
