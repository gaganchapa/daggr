<script lang="ts">
	import { Block } from "@gradio/atoms";
	import { StatusTracker } from "@gradio/statustracker";
	import { Gradio } from "@gradio/utils";
	import { onMount } from "svelte";

	// Types
	interface Port {
		name: string;
		history_count?: number;
	}

	interface GraphNode {
		id: string;
		name: string;
		type: string;
		inputs: Port[];
		outputs: string[];
		x: number;
		y: number;
		status: string;
		is_output_node: boolean;
		is_input_node: boolean;
	}

	interface GraphEdge {
		id: string;
		from_node: string;
		from_port: string;
		to_node: string;
		to_port: string;
	}

	interface CanvasData {
		name: string;
		nodes: GraphNode[];
		edges: GraphEdge[];
		run_to_node?: string;
	}

	interface CanvasEvents {
		change: CanvasData;
	}

	interface CanvasProps {
		value: CanvasData;
		height: number | string | undefined;
	}

	let props = $props();
	const gradio = new Gradio<CanvasEvents, CanvasProps>(props);

	// Canvas element ref
	let canvasEl: HTMLDivElement;

	// Canvas pan/zoom state
	let transform = $state({ x: 0, y: 0, scale: 1 });
	let isPanning = $state(false);
	let startPan = $state({ x: 0, y: 0 });

	// Data from props
	let nodes = $derived(gradio.props.value?.nodes || []);
	let edges = $derived(gradio.props.value?.edges || []);

	// Node layout constants - MUST match CSS exactly
	const NODE_WIDTH = 220;
	const NODE_HEIGHT_BASE = 100;
	const HEADER_HEIGHT = 36;
	const HEADER_BORDER = 1;
	const BODY_PADDING_TOP = 8;
	const PORT_ROW_HEIGHT = 22;
	const STATUS_HEIGHT = 26;

	// Calculate node height
	function getNodeHeight(node: GraphNode): number {
		const portRows = Math.max(node.inputs.length, node.outputs.length, 1);
		return HEADER_HEIGHT + HEADER_BORDER + BODY_PADDING_TOP + (portRows * PORT_ROW_HEIGHT) + BODY_PADDING_TOP + STATUS_HEIGHT;
	}

	// Build lookup map
	let nodeMap = $derived.by(() => {
		const map = new Map<string, GraphNode>();
		for (const node of nodes) {
			map.set(node.id, node);
		}
		return map;
	});

	// Calculate Y position for a port (relative to node top)
	function getPortY(portIndex: number): number {
		return HEADER_HEIGHT + HEADER_BORDER + BODY_PADDING_TOP + (portIndex * PORT_ROW_HEIGHT) + (PORT_ROW_HEIGHT / 2);
	}

	// Compute all edge paths reactively
	let edgePaths = $derived.by(() => {
		const paths: { id: string; d: string }[] = [];
		
		for (const edge of edges) {
			const fromNode = nodeMap.get(edge.from_node);
			const toNode = nodeMap.get(edge.to_node);
			
			if (!fromNode || !toNode) continue;

			const fromPortIdx = fromNode.outputs.indexOf(edge.from_port);
			const toPortIdx = toNode.inputs.findIndex(p => p.name === edge.to_port);

			if (fromPortIdx === -1 || toPortIdx === -1) continue;

			const fromPortY = getPortY(fromPortIdx);
			const toPortY = getPortY(toPortIdx);

			const x1 = fromNode.x + NODE_WIDTH;
			const y1 = fromNode.y + fromPortY;
			const x2 = toNode.x;
			const y2 = toNode.y + toPortY;

			const dx = Math.abs(x2 - x1);
			const cp = Math.max(dx * 0.4, 50);

			const d = `M ${x1} ${y1} C ${x1 + cp} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}`;
			paths.push({ id: edge.id, d });
		}
		
		return paths;
	});

	// Zoom to fit all nodes
	function zoomToFit() {
		if (nodes.length === 0 || !canvasEl) return;

		const padding = 40;
		const canvasRect = canvasEl.getBoundingClientRect();
		const canvasWidth = canvasRect.width;
		const canvasHeight = canvasRect.height;

		// Calculate bounding box of all nodes
		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
		for (const node of nodes) {
			const nodeHeight = getNodeHeight(node);
			minX = Math.min(minX, node.x);
			minY = Math.min(minY, node.y);
			maxX = Math.max(maxX, node.x + NODE_WIDTH);
			maxY = Math.max(maxY, node.y + nodeHeight);
		}

		const contentWidth = maxX - minX;
		const contentHeight = maxY - minY;

		// Calculate scale to fit
		const scaleX = (canvasWidth - padding * 2) / contentWidth;
		const scaleY = (canvasHeight - padding * 2) / contentHeight;
		const newScale = Math.min(scaleX, scaleY, 1.5); // Cap at 150%

		// Calculate translation to center
		const centerX = (minX + maxX) / 2;
		const centerY = (minY + maxY) / 2;
		const newX = canvasWidth / 2 - centerX * newScale;
		const newY = canvasHeight / 2 - centerY * newScale;

		transform = { x: newX, y: newY, scale: Math.max(0.2, newScale) };
	}

	// Zoom controls
	function zoomIn() {
		transform.scale = Math.min(3, transform.scale * 1.2);
	}

	function zoomOut() {
		transform.scale = Math.max(0.2, transform.scale / 1.2);
	}

	// Pan handlers
	function handleMouseDown(e: MouseEvent) {
		if (e.button === 0 && e.target === canvasEl) {
			isPanning = true;
			startPan = { x: e.clientX - transform.x, y: e.clientY - transform.y };
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (isPanning) {
			transform.x = e.clientX - startPan.x;
			transform.y = e.clientY - startPan.y;
		}
	}

	function handleMouseUp() {
		isPanning = false;
	}

	function handleWheel(e: WheelEvent) {
		e.preventDefault();
		const delta = e.deltaY > 0 ? 0.9 : 1.1;
		transform.scale = Math.max(0.2, Math.min(3, transform.scale * delta));
	}

	function handleRunToNode(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		if (gradio.props.value) {
			gradio.props.value = {
				...gradio.props.value,
				run_to_node: nodeName
			};
		}
	}

	function getBadgeStyle(type: string): string {
		const colors: Record<string, string> = {
			'FN': '#f97316',
			'INPUT': '#06b6d4',
			'MAP': '#a855f7',
			'GRADIO': '#ea580c',
			'MODEL': '#22c55e',
		};
		return `background: ${colors[type] || '#666'};`;
	}

	function getStatusStyles(status: string): { dot: string; text: string; glow: string } {
		const styles: Record<string, { dot: string; text: string; glow: string }> = {
			'pending': { dot: '#444', text: '#666', glow: 'none' },
			'running': { dot: '#f97316', text: '#fb923c', glow: '0 0 8px rgba(249, 115, 22, 0.7)' },
			'completed': { dot: '#22c55e', text: '#4ade80', glow: '0 0 8px rgba(34, 197, 94, 0.6)' },
			'error': { dot: '#ef4444', text: '#f87171', glow: '0 0 8px rgba(239, 68, 68, 0.6)' },
		};
		return styles[status] || styles['pending'];
	}

	// Zoom to fit on mount
	onMount(() => {
		setTimeout(zoomToFit, 100);
	});

	// Zoom percentage display
	let zoomPercent = $derived(Math.round(transform.scale * 100));
</script>

<Block
	elem_id={gradio.shared.elem_id}
	elem_classes={gradio.shared.elem_classes}
	visible={gradio.shared.visible}
	padding={false}
	scale={gradio.shared.scale}
	min_width={gradio.shared.min_width}
	height={gradio.props.height || "100vh"}
	allow_overflow={false}
	flex={true}
>
	{#if gradio.shared.loading_status}
		<StatusTracker
			autoscroll={gradio.shared.autoscroll}
			i18n={gradio.i18n}
			{...gradio.shared.loading_status}
			on_clear_status={() => gradio.dispatch("clear_status", gradio.shared.loading_status)}
		/>
	{/if}

	<div 
		class="canvas"
		bind:this={canvasEl}
		onmousedown={handleMouseDown}
		onmousemove={handleMouseMove}
		onmouseup={handleMouseUp}
		onmouseleave={handleMouseUp}
		onwheel={handleWheel}
		role="application"
	>
		<div class="grid-bg"></div>

		<div 
			class="canvas-transform"
			style="transform: translate({transform.x}px, {transform.y}px) scale({transform.scale})"
		>
			<!-- Nodes -->
			{#each nodes as node (node.id)}
				{@const status = getStatusStyles(node.status)}
				<div 
					class="node"
					style="left: {node.x}px; top: {node.y}px; width: {NODE_WIDTH}px;"
				>
					<div class="node-header">
						<span class="type-badge" style={getBadgeStyle(node.type)}>{node.type}</span>
						<span class="node-name">{node.name}</span>
						{#if !node.is_input_node}
							<button 
								class="run-btn"
								class:run-btn-primary={node.is_output_node}
								onclick={(e) => handleRunToNode(e, node.name)}
								title="Run to here"
							>
								<svg viewBox="0 0 24 24"><polygon points="8,5 19,12 8,19"/></svg>
							</button>
						{/if}
					</div>

					<div class="node-body">
						<div class="ports-left">
							{#each node.inputs as port (port.name)}
								<div class="port-row">
									<span class="port-dot input"></span>
									<span class="port-label">{port.name}</span>
								</div>
							{/each}
						</div>
						<div class="ports-right">
							{#each node.outputs as portName (portName)}
								<div class="port-row">
									<span class="port-label">{portName}</span>
									<span class="port-dot output"></span>
								</div>
							{/each}
						</div>
					</div>

					<div class="node-footer">
						<span class="status-dot" style="background: {status.dot}; box-shadow: {status.glow};"></span>
						<span class="status-label" style="color: {status.text};">{node.status}</span>
					</div>
				</div>
			{/each}

			<!-- Edges SVG -->
			<svg class="edges-svg">
				{#each edgePaths as edge (edge.id)}
					<path d={edge.d} class="edge-path" />
				{/each}
			</svg>
		</div>

		<!-- Zoom Controls -->
		<div class="zoom-controls">
			<button class="zoom-btn" onclick={zoomOut} title="Zoom out">−</button>
			<span class="zoom-level">{zoomPercent}%</span>
			<button class="zoom-btn" onclick={zoomIn} title="Zoom in">+</button>
			<button class="zoom-btn fit-btn" onclick={zoomToFit} title="Fit all nodes">⊡</button>
		</div>
	</div>
</Block>

<style>
	.canvas {
		position: relative;
		width: 100%;
		height: 100%;
		overflow: hidden;
		background: #0c0c0c;
		cursor: grab;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
	}

	.canvas:active {
		cursor: grabbing;
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image: radial-gradient(circle, rgba(249, 115, 22, 0.06) 1px, transparent 1px);
		background-size: 20px 20px;
		pointer-events: none;
	}

	.canvas-transform {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
	}

	/* Zoom controls */
	.zoom-controls {
		position: absolute;
		bottom: 16px;
		left: 16px;
		display: flex;
		align-items: center;
		gap: 4px;
		background: rgba(20, 20, 20, 0.9);
		border: 1px solid rgba(249, 115, 22, 0.2);
		border-radius: 8px;
		padding: 4px;
		z-index: 100;
	}

	.zoom-btn {
		width: 28px;
		height: 28px;
		border: none;
		background: transparent;
		color: #999;
		font-size: 16px;
		font-weight: 600;
		cursor: pointer;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}

	.zoom-btn:hover {
		background: rgba(249, 115, 22, 0.15);
		color: #f97316;
	}

	.fit-btn {
		font-size: 14px;
		margin-left: 4px;
		border-left: 1px solid rgba(249, 115, 22, 0.15);
		padding-left: 8px;
		border-radius: 0 4px 4px 0;
	}

	.zoom-level {
		font-size: 11px;
		font-weight: 600;
		color: #888;
		min-width: 40px;
		text-align: center;
		font-family: 'SF Mono', Monaco, monospace;
	}

	/* SVG for edges */
	.edges-svg {
		position: absolute;
		top: 0;
		left: 0;
		width: 4000px;
		height: 3000px;
		pointer-events: none;
		overflow: visible;
		transform: translateY(-8px);
	}

	.edge-path {
		fill: none;
		stroke: #f97316;
		stroke-width: 2.5;
		stroke-linecap: round;
	}

	/* Node */
	.node {
		position: absolute;
		background: linear-gradient(175deg, #181818 0%, #121212 100%);
		border: 1px solid rgba(249, 115, 22, 0.2);
		border-radius: 10px;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
		overflow: hidden;
	}

	.node-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 12px;
		height: 36px;
		background: rgba(249, 115, 22, 0.06);
		border-bottom: 1px solid rgba(249, 115, 22, 0.1);
	}

	.type-badge {
		font-size: 8px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		padding: 3px 8px;
		border-radius: 4px;
		color: #fff;
		flex-shrink: 0;
	}

	.node-name {
		flex: 1;
		font-size: 11px;
		font-weight: 600;
		color: #eee;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.run-btn {
		width: 20px;
		height: 20px;
		border-radius: 50%;
		border: 1.5px solid #f97316;
		background: transparent;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		flex-shrink: 0;
	}

	.run-btn svg {
		width: 8px;
		height: 8px;
		fill: #f97316;
	}

	.run-btn-primary {
		background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
		border: none;
		box-shadow: 0 2px 8px rgba(249, 115, 22, 0.4);
	}

	.run-btn-primary svg {
		fill: #fff;
	}

	.node-body {
		display: flex;
		justify-content: space-between;
		padding-top: 8px;
		padding-bottom: 8px;
		min-height: 30px;
	}

	.ports-left, .ports-right {
		display: flex;
		flex-direction: column;
	}

	.ports-right {
		align-items: flex-end;
	}

	.port-row {
		display: flex;
		align-items: center;
		gap: 6px;
		height: 22px;
		padding: 0 10px;
	}

	.port-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.port-dot.input {
		background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
		box-shadow: 0 0 6px rgba(249, 115, 22, 0.5);
	}

	.port-dot.output {
		background: linear-gradient(135deg, #fb923c 0%, #f97316 100%);
		box-shadow: 0 0 6px rgba(251, 146, 60, 0.5);
	}

	.port-label {
		font-size: 10px;
		font-weight: 500;
		color: #888;
		font-family: 'SF Mono', Monaco, monospace;
	}

	.node-footer {
		display: flex;
		align-items: center;
		gap: 6px;
		height: 26px;
		padding: 0 10px;
		border-top: 1px solid rgba(249, 115, 22, 0.08);
	}

	.status-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
	}

	.status-label {
		font-size: 8px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
</style>
