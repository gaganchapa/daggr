<script context="module" lang="ts">
	// Truly module-level Set - persists across all component instances/re-renders
	const globalProcessedSet = new Set<string>();
</script>

<script lang="ts">
	import { Block } from "@gradio/atoms";
	import { StatusTracker } from "@gradio/statustracker";
	import { Gradio } from "@gradio/utils";

	// Types
	interface Port {
		name: string;
		history_count?: number;
	}

	interface GradioComponentData {
		component: string;
		type: string;
		port_name: string;
		props: Record<string, any>;
		value?: any;
	}

	interface MapItem {
		index: number;
		preview: string;
		output: string | null;
		is_audio_output: boolean;
		status?: string;
	}

	interface ItemListItem {
		index: number;
		fields: Record<string, any>;
	}

	interface GraphNode {
		id: string;
		name: string;
		type: string;
		inputs: Port[];
		outputs: string[];
		input_components?: GradioComponentData[];
		output_components?: GradioComponentData[];
		x: number;
		y: number;
		status: string;
		is_output_node: boolean;
		is_input_node: boolean;
		is_map_node?: boolean;
		map_items?: MapItem[];
		map_item_count?: number;
		item_list_schema?: GradioComponentData[];
		item_list_items?: ItemListItem[];
	}

	interface GraphEdge {
		id: string;
		from_node: string;
		from_port: string;
		to_node: string;
		to_port: string;
		is_scattered?: boolean;
		is_gathered?: boolean;
	}

	interface CanvasData {
		name: string;
		nodes: GraphNode[];
		edges: GraphEdge[];
		inputs?: Record<string, Record<string, string>>;
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

	// Data from props - keep previous values if new data is empty (prevents UI clearing)
	let lastValidNodes: GraphNode[] = [];
	let lastValidEdges: GraphEdge[] = [];
	
	let nodes = $derived.by(() => {
		const newNodes = gradio.props.value?.nodes;
		if (newNodes && newNodes.length > 0) {
			lastValidNodes = newNodes;
			return newNodes;
		}
		return lastValidNodes;
	});
	
	let edges = $derived.by(() => {
		const newEdges = gradio.props.value?.edges;
		if (newEdges && newEdges.length > 0) {
			lastValidEdges = newEdges;
			return newEdges;
		}
		return lastValidEdges;
	});

	// Track input component values (keyed by node.id for correct data flow)
	let inputValues = $state<Record<string, Record<string, any>>>({});

	// Track pending run IDs per node (queue of run IDs waiting for results)
	let pendingRunIds = $state<Record<string, string[]>>({});

	// Track which nodes are being executed for each run_id
	let runIdToNodes = $state<Record<string, string[]>>({});

	// Track multiple results per node (array of results)
	let nodeResults = $state<Record<string, any[]>>({});

	// Track which result index is selected per node
	let selectedResultIndex = $state<Record<string, number>>({});

	// Track which map nodes are expanded (showing all items)
	let expandedMapNodes = $state<Record<string, boolean>>({});

	// Computed running counts from pending runs
	let runningCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const [nodeName, ids] of Object.entries(pendingRunIds)) {
			counts[nodeName] = ids.length;
		}
		return counts;
	});

	// Get ancestors of a node from the edges
	function getAncestors(nodeName: string): string[] {
		const ancestors = new Set<string>();
		const toVisit = [nodeName];
		
		while (toVisit.length > 0) {
			const current = toVisit.pop()!;
			for (const edge of edges) {
				if (edge.to_node === current.replace(/ /g, '_').replace(/-/g, '_')) {
					const sourceNode = nodes.find(n => n.id === edge.from_node);
					if (sourceNode && !sourceNode.is_input_node && !ancestors.has(sourceNode.name)) {
						ancestors.add(sourceNode.name);
						toVisit.push(sourceNode.name);
					}
				}
			}
		}
		
		return Array.from(ancestors);
	}

	function handleInputChange(nodeId: string, portName: string, value: any) {
		if (!inputValues[nodeId]) {
			inputValues[nodeId] = {};
		}
		inputValues[nodeId][portName] = value;
	}

	function getComponentValue(node: GraphNode, comp: GradioComponentData): any {
		return inputValues[node.id]?.[comp.port_name] ?? comp.value ?? '';
	}

	function handleItemListChange(nodeId: string, itemIndex: number, fieldName: string, value: any) {
		if (!itemListValues[nodeId]) {
			itemListValues[nodeId] = {};
		}
		if (!itemListValues[nodeId][itemIndex]) {
			itemListValues[nodeId][itemIndex] = {};
		}
		itemListValues[nodeId][itemIndex][fieldName] = value;
	}

	function getItemListValue(node: GraphNode, itemIndex: number, fieldName: string): any {
		const edited = itemListValues[node.id]?.[itemIndex]?.[fieldName];
		if (edited !== undefined) return edited;
		const item = node.item_list_items?.find(i => i.index === itemIndex);
		return item?.fields?.[fieldName] ?? '';
	}

	function getComponentsToRender(node: GraphNode): GradioComponentData[] {
		if (node.is_input_node && node.input_components?.length) {
			return node.input_components;
		}
		// For output nodes, use selected results if available
		return getSelectedResults(node);
	}

	// Node layout constants - MUST match CSS exactly
	const NODE_WIDTH = 220;
	const NODE_HEIGHT_BASE = 100;
	const HEADER_HEIGHT = 36;
	const HEADER_BORDER = 1;
	const BODY_PADDING_TOP = 8;
	const PORT_ROW_HEIGHT = 22;
	const EMBEDDED_COMPONENT_HEIGHT = 60;

	// Calculate node height
	function getNodeHeight(node: GraphNode): number {
		const portRows = Math.max(node.inputs.length, node.outputs.length, 1);
		const componentsToRender = getComponentsToRender(node);
		const embeddedHeight = componentsToRender.length * EMBEDDED_COMPONENT_HEIGHT;
		return HEADER_HEIGHT + HEADER_BORDER + BODY_PADDING_TOP + (portRows * PORT_ROW_HEIGHT) + embeddedHeight + BODY_PADDING_TOP;
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
		const paths: { 
			id: string; 
			d: string; 
			is_scattered: boolean; 
			is_gathered: boolean;
			forkPaths?: string[];
		}[] = [];
		
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

			const is_scattered = edge.is_scattered || false;
			const is_gathered = edge.is_gathered || false;

			let forkPaths: string[] = [];

			if (is_scattered) {
				// Fork at the END - edge splits into 3 lines near target
				const forkStart = x2 - 30;
				const forkSpread = 8;
				// Main path stops before the fork
				const d = `M ${x1} ${y1} C ${x1 + cp} ${y1}, ${forkStart - 20} ${y2}, ${forkStart} ${y2}`;
				// Fork lines spread out to target
				forkPaths = [
					`M ${forkStart} ${y2} L ${x2} ${y2 - forkSpread}`,
					`M ${forkStart} ${y2} L ${x2} ${y2}`,
					`M ${forkStart} ${y2} L ${x2} ${y2 + forkSpread}`,
				];
				paths.push({ id: edge.id, d, is_scattered, is_gathered, forkPaths });
			} else if (is_gathered) {
				// Fork at the START - 3 lines converge from source
				const forkEnd = x1 + 30;
				const forkSpread = 8;
				// Fork lines from source
				forkPaths = [
					`M ${x1} ${y1 - forkSpread} L ${forkEnd} ${y1}`,
					`M ${x1} ${y1} L ${forkEnd} ${y1}`,
					`M ${x1} ${y1 + forkSpread} L ${forkEnd} ${y1}`,
				];
				// Main path continues from fork point
				const d = `M ${forkEnd} ${y1} C ${forkEnd + cp - 30} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}`;
				paths.push({ id: edge.id, d, is_scattered, is_gathered, forkPaths });
			} else {
				const d = `M ${x1} ${y1} C ${x1 + cp} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}`;
				paths.push({ id: edge.id, d, is_scattered, is_gathered });
			}
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
		
		const rect = canvasEl.getBoundingClientRect();
		const mouseX = e.clientX - rect.left;
		const mouseY = e.clientY - rect.top;
		
		const canvasX = (mouseX - transform.x) / transform.scale;
		const canvasY = (mouseY - transform.y) / transform.scale;
		
		const delta = e.deltaY > 0 ? 0.97 : 1.03;
		const newScale = Math.max(0.2, Math.min(3, transform.scale * delta));
		
		transform = {
			x: mouseX - canvasX * newScale,
			y: mouseY - canvasY * newScale,
			scale: newScale
		};
	}

	function handleRunToNode(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		
		const runId = `${nodeName}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
		const ancestors = getAncestors(nodeName);
		const nodesToExecute = [...ancestors, nodeName];
		
		// Only add pending badges for nodes that don't already have results (will be skipped on backend)
		const nodesToRun = nodesToExecute.filter(n => !nodeResults[n] || nodeResults[n].length === 0);
		
		for (const nodeToRun of nodesToRun) {
			if (!pendingRunIds[nodeToRun]) {
				pendingRunIds[nodeToRun] = [];
			}
			pendingRunIds[nodeToRun] = [...pendingRunIds[nodeToRun], runId];
		}
		
		// Track which nodes this run_id will actually execute
		runIdToNodes[runId] = nodesToRun;
		
		if (gradio.props.value) {
			const newValue = {
				...gradio.props.value,
				inputs: { ...gradio.props.value.inputs, ...inputValues },
				item_list_values: { ...itemListValues },
				run_to_node: nodeName,
				run_id: runId,
				completed_node: null,
				selected_results: { ...selectedResultIndex }  // Pass selected result indices to backend
			};
			gradio.props.value = newValue;
			gradio.dispatch("change", newValue);
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

	// Process incoming results from backend (streaming)
	$effect(() => {
		try {
			const data = gradio.props.value;
			if (!data) return;
			
			const runId = data.run_id;
			const completedNode = data.completed_node;
			if (!runId || !completedNode) return;
			
			const completionKey = `${runId}:${completedNode}`;
			
			if (globalProcessedSet.has(completionKey)) return;
			globalProcessedSet.add(completionKey);
			
			if (pendingRunIds[completedNode]) {
				pendingRunIds[completedNode] = pendingRunIds[completedNode].filter(id => id !== runId);
			}
			
			const executedNodes = runIdToNodes[runId];
			if (executedNodes) {
				const allDone = executedNodes.every(n => globalProcessedSet.has(`${runId}:${n}`));
				if (allDone) {
					delete runIdToNodes[runId];
					setTimeout(() => {
						for (const n of executedNodes) {
							globalProcessedSet.delete(`${runId}:${n}`);
						}
					}, 1000);
				}
			}
			
			const node = data.nodes?.find((n: GraphNode) => n.name === completedNode);
			if (node && node.output_components?.length > 0) {
				const hasResult = node.output_components.some((c: GradioComponentData) => c.value != null);
				if (hasResult) {
					if (!nodeResults[completedNode]) {
						nodeResults[completedNode] = [];
					}
					
					const resultSnapshot = node.output_components.map((c: GradioComponentData) => ({
						...c
					}));
					
					nodeResults[completedNode] = [...nodeResults[completedNode], resultSnapshot];
					selectedResultIndex[completedNode] = nodeResults[completedNode].length - 1;
				}
			}
		} catch (err) {
			console.error('[daggr] Error processing result:', err);
		}
	});

	// Get the currently selected results for a node
	function getSelectedResults(node: GraphNode): GradioComponentData[] {
		const results = nodeResults[node.name];
		if (!results || results.length === 0) {
			return node.output_components || [];
		}
		const idx = selectedResultIndex[node.name] ?? results.length - 1;
		return results[idx] || node.output_components || [];
	}

	// Get total result count for a node
	function getResultCount(nodeName: string): number {
		return nodeResults[nodeName]?.length || 0;
	}

	// Navigate to previous result
	function prevResult(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		const current = selectedResultIndex[nodeName] ?? 0;
		if (current > 0) {
			selectedResultIndex[nodeName] = current - 1;
		}
	}

	// Navigate to next result
	function nextResult(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		const total = getResultCount(nodeName);
		const current = selectedResultIndex[nodeName] ?? 0;
		if (current < total - 1) {
			selectedResultIndex[nodeName] = current + 1;
		}
	}

	// Zoom percentage display
	let zoomPercent = $derived(Math.round(transform.scale * 100));

	// Toggle map node expansion
	function toggleMapExpand(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		expandedMapNodes[nodeName] = !expandedMapNodes[nodeName];
	}

	// Replay individual map item
	function handleReplayItem(e: MouseEvent, nodeName: string, itemIndex: number) {
		e.stopPropagation();
		// TODO: Implement individual item replay via backend
		console.log(`Replay item ${itemIndex} for node ${nodeName}`);
	}

	// Get visible map items (first 3 or all if expanded)
	function getVisibleMapItems(node: GraphNode): MapItem[] {
		const items = node.map_items || [];
		if (expandedMapNodes[node.name] || items.length <= 3) {
			return items;
		}
		return items.slice(0, 3);
	}
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

	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
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
			<!-- Edges SVG (rendered first so it's behind nodes) -->
			<svg class="edges-svg">
				{#each edgePaths as edge (edge.id)}
					<path 
						d={edge.d} 
						class="edge-path"
					/>
					{#if edge.forkPaths}
						{#each edge.forkPaths as forkD}
							<path d={forkD} class="edge-path edge-fork" />
						{/each}
					{/if}
				{/each}
			</svg>

			<!-- Nodes -->
			{#each nodes as node (node.id)}
				{@const componentsToRender = getComponentsToRender(node)}
				<div 
					class="node"
					style="left: {node.x}px; top: {node.y}px; width: {NODE_WIDTH}px;"
				>
					<div class="node-header">
						<span class="type-badge" style={getBadgeStyle(node.type)}>{node.type}</span>
						<span class="node-name">{node.name}</span>
						{#if !node.is_input_node}
							<span 
								class="run-btn"
								class:running={runningCounts[node.name] > 0}
								onclick={(e) => handleRunToNode(e, node.name)}
								title={node.is_map_node ? "Run all items" : "Run to here"}
								role="button"
								tabindex="0"
							>
								{#if node.is_map_node}
									<svg class="run-icon-svg run-icon-map" viewBox="0 0 14 12" fill="currentColor">
										<path d="M2 1 L12 6 L2 11 Z" opacity="0.5" transform="translate(-2, 0)"/>
										<path d="M2 1 L12 6 L2 11 Z" transform="translate(2, 0)"/>
									</svg>
								{:else}
									<svg class="run-icon-svg" viewBox="0 0 10 12" fill="currentColor">
										<path d="M1 1 L9 6 L1 11 Z"/>
									</svg>
								{/if}
								{#if runningCounts[node.name] > 0}
									<span class="run-badge">{runningCounts[node.name]}</span>
								{/if}
							</span>
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

					{#if componentsToRender.length > 0}
						<div class="embedded-components">
							{#each componentsToRender as comp (comp.port_name)}
								<div class="embedded-component">
									{#if comp.component === 'textbox' || comp.component === 'text'}
										<div class="gr-textbox-wrap">
											<span class="gr-label">{comp.props?.label || comp.port_name}</span>
											{#if comp.props?.lines && comp.props.lines > 1}
												<textarea
													class="gr-input"
													placeholder={comp.props?.placeholder || ''}
													rows={comp.props?.lines || 3}
													disabled={!node.is_input_node}
													value={getComponentValue(node, comp)}
													oninput={(e) => handleInputChange(node.id, comp.port_name, (e.target as HTMLTextAreaElement).value)}
												></textarea>
											{:else}
												<input
													type="text"
													class="gr-input"
													placeholder={comp.props?.placeholder || ''}
													disabled={!node.is_input_node}
													value={getComponentValue(node, comp)}
													oninput={(e) => handleInputChange(node.id, comp.port_name, (e.target as HTMLInputElement).value)}
												/>
											{/if}
										</div>
									{:else if comp.component === 'number'}
										<div class="gr-textbox-wrap">
											<span class="gr-label">{comp.props?.label || comp.port_name}</span>
											<input
												type="number"
												class="gr-input"
												disabled={!node.is_input_node}
												value={getComponentValue(node, comp)}
												oninput={(e) => handleInputChange(node.id, comp.port_name, parseFloat((e.target as HTMLInputElement).value))}
											/>
										</div>
									{:else if comp.component === 'checkbox'}
										<label class="gr-checkbox-wrap">
											<input
												type="checkbox"
												disabled={!node.is_input_node}
												checked={getComponentValue(node, comp)}
												onchange={(e) => handleInputChange(node.id, comp.port_name, (e.target as HTMLInputElement).checked)}
											/>
											<span class="gr-check-label">{comp.props?.label || comp.port_name}</span>
										</label>
{:else if comp.component === 'markdown'}
								<div class="gr-textbox-wrap">
									<span class="gr-label">{comp.props?.label || comp.port_name}</span>
									<div class="gr-markdown">{@html comp.value || ''}</div>
								</div>
							{:else if comp.component === 'html'}
								<div class="gr-textbox-wrap">
									<span class="gr-label">{comp.props?.label || comp.port_name}</span>
									<div class="gr-html">{@html comp.value || ''}</div>
								</div>
							{:else if comp.component === 'json'}
										<div class="gr-textbox-wrap">
											<span class="gr-label">{comp.props?.label || comp.port_name}</span>
											<pre class="gr-json">{typeof comp.value === 'string' ? comp.value : JSON.stringify(comp.value, null, 2)}</pre>
										</div>
									{:else if comp.component === 'audio'}
										<div class="gr-audio-wrap">
											<span class="gr-label">{comp.props?.label || comp.port_name}</span>
											{#if comp.value}
												<div class="gr-audio-container">
													<audio controls class="gr-audio" src={comp.value?.url || comp.value}></audio>
												</div>
											{:else}
												<div class="gr-empty">No audio</div>
											{/if}
										</div>
									{:else if comp.component === 'image'}
										<div class="gr-textbox-wrap">
											<span class="gr-label">{comp.props?.label || comp.port_name}</span>
											{#if comp.value}
												<img class="gr-image" src={comp.value?.url || comp.value} alt={comp.props?.label || ''} />
											{:else}
												<div class="gr-empty">No image</div>
											{/if}
										</div>
									{:else}
										<div class="gr-fallback">
											<span class="fallback-type">{comp.component}</span>
											{#if comp.value}
												<pre>{typeof comp.value === 'string' ? comp.value : JSON.stringify(comp.value, null, 2)}</pre>
											{/if}
										</div>
									{/if}
								</div>
							{/each}
						</div>
						
						{#if !node.is_input_node && getResultCount(node.name) > 1}
							<div class="result-selector">
								<button 
									class="result-nav" 
									onclick={(e) => prevResult(e, node.name)}
									disabled={(selectedResultIndex[node.name] ?? 0) === 0}
								>‹</button>
								<span class="result-counter">
									{(selectedResultIndex[node.name] ?? 0) + 1}/{getResultCount(node.name)}
								</span>
								<button 
									class="result-nav" 
									onclick={(e) => nextResult(e, node.name)}
									disabled={(selectedResultIndex[node.name] ?? 0) >= getResultCount(node.name) - 1}
								>›</button>
							</div>
						{/if}
					{/if}

					{#if node.is_map_node && node.map_items && node.map_items.length > 0}
						<div class="map-items-section">
							<div class="map-items-header">
								<span class="map-items-title">Items ({node.map_items.length})</span>
							</div>
							<div class="map-items-list">
								{#each getVisibleMapItems(node) as item (item.index)}
									<div class="map-item" class:has-output={item.output}>
										<span class="map-item-index">{item.index}.</span>
										<span class="map-item-preview" title={item.preview}>
											{item.preview.length > 25 ? item.preview.slice(0, 25) + '...' : item.preview}
										</span>
										<button 
											class="map-item-replay"
											onclick={(e) => handleReplayItem(e, node.name, item.index)}
											title={item.output ? "Replay this item" : "Run this item"}
										>
											{item.output ? '↻' : '▶'}
										</button>
									</div>
								{/each}
							</div>
							{#if node.map_items.length > 3}
								<button 
									class="map-expand-btn"
									onclick={(e) => toggleMapExpand(e, node.name)}
								>
									{expandedMapNodes[node.name] ? '▲ Show less' : `▼ Show all (${node.map_items.length})`}
								</button>
							{/if}
						</div>
					{/if}

					{#if node.item_list_schema && node.item_list_items && node.item_list_items.length > 0}
						<div class="item-list-section">
							<div class="item-list-header">
								<span class="item-list-title">Items ({node.item_list_items.length})</span>
							</div>
							<div class="item-list-items">
								{#each node.item_list_items as item (item.index)}
									<div class="item-list-item">
										<span class="item-list-index">{item.index + 1}.</span>
										<div class="item-list-fields">
											{#each node.item_list_schema as comp (comp.port_name)}
												{#if comp.component === 'dropdown'}
													<select
														class="gr-select"
														value={getItemListValue(node, item.index, comp.port_name)}
														onchange={(e) => handleItemListChange(node.id, item.index, comp.port_name, (e.target as HTMLSelectElement).value)}
													>
														{#each comp.props?.choices || [] as choice}
															<option value={choice}>{choice}</option>
														{/each}
													</select>
												{:else if comp.component === 'textbox' || comp.component === 'text'}
													{#if comp.props?.lines && comp.props.lines > 1}
														<textarea
															class="gr-input item-list-textarea"
															rows={comp.props?.lines || 2}
															value={getItemListValue(node, item.index, comp.port_name)}
															oninput={(e) => handleItemListChange(node.id, item.index, comp.port_name, (e.target as HTMLTextAreaElement).value)}
														></textarea>
													{:else}
														<input
															type="text"
															class="gr-input"
															value={getItemListValue(node, item.index, comp.port_name)}
															oninput={(e) => handleItemListChange(node.id, item.index, comp.port_name, (e.target as HTMLInputElement).value)}
														/>
													{/if}
												{/if}
											{/each}
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/each}
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
	}

	.edge-path {
		fill: none;
		stroke: #f97316;
		stroke-width: 2.5;
		stroke-linecap: round;
	}

	.edge-fork {
		stroke-width: 2;
	}

	/* Node */
	.node {
		position: absolute;
		background: linear-gradient(175deg, rgba(24, 24, 24, 0.92) 0%, rgba(18, 18, 18, 0.92) 100%);
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
		position: relative;
		font-size: 10px;
		color: #f97316;
		cursor: pointer;
		padding: 2px 6px;
		border-radius: 4px;
		border: 1px solid #f97316;
		background: transparent;
		user-select: none;
		transition: all 0.15s;
	}

	.run-btn:hover {
		background: rgba(249, 115, 22, 0.2);
	}

	.run-btn.running {
		animation: pulse 1.5s ease-in-out infinite;
	}

	.run-icon-svg {
		width: 10px;
		height: 10px;
		display: block;
	}

	.run-icon-svg.run-icon-map {
		width: 14px;
		height: 12px;
	}

	@keyframes pulse {
		0%, 100% { box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.4); }
		50% { box-shadow: 0 0 0 4px rgba(249, 115, 22, 0); }
	}

	.run-badge {
		position: absolute;
		top: -6px;
		right: -6px;
		min-width: 14px;
		height: 14px;
		background: #f97316;
		color: #000;
		font-size: 9px;
		font-weight: 700;
		border-radius: 7px;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 3px;
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

	.embedded-components {
		padding: 8px 10px;
		border-top: 1px solid rgba(249, 115, 22, 0.08);
		max-height: 200px;
		overflow-y: auto;
	}

	.embedded-component {
		margin-bottom: 8px;
	}

	.embedded-component:last-child {
		margin-bottom: 0;
	}

	.gr-textbox-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-label {
		display: block;
		font-size: 10px;
		font-weight: 400;
		color: #888;
		padding: 6px 10px 0;
	}

	.gr-input {
		width: 100%;
		padding: 4px 10px 8px;
		font-size: 11px;
		font-family: inherit;
		color: #e5e7eb;
		background: transparent;
		border: none;
		outline: none;
		box-sizing: border-box;
	}

	.gr-input::placeholder {
		color: #555;
	}

	.gr-textbox-wrap:focus-within {
		border-color: #f97316;
	}

	.gr-input:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	textarea.gr-input {
		resize: none;
		min-height: 36px;
		line-height: 1.4;
	}

	.gr-checkbox-wrap {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		padding: 6px 0;
	}

	.gr-checkbox-wrap input[type="checkbox"] {
		width: 14px;
		height: 14px;
		accent-color: #f97316;
		cursor: pointer;
	}

	.gr-check-label {
		font-size: 11px;
		color: #e5e7eb;
	}

	.gr-markdown {
		font-size: 11px;
		color: #d1d5db;
		line-height: 1.4;
		padding: 6px 10px 8px;
		max-height: 100px;
		overflow: auto;
	}

	.gr-html {
		font-size: 11px;
		color: #d1d5db;
		line-height: 1.4;
		padding: 6px 10px 8px;
		max-height: 100px;
		overflow: auto;
	}

	.gr-html :global(strong), .gr-html :global(b) {
		font-weight: 600;
		color: #f3f4f6;
	}

	.gr-html :global(em), .gr-html :global(i) {
		font-style: italic;
	}

	.gr-html :global(a) {
		color: #f97316;
		text-decoration: underline;
	}

	.gr-html :global(code) {
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		background: rgba(249, 115, 22, 0.1);
		padding: 1px 4px;
		border-radius: 3px;
		font-size: 10px;
	}

	.gr-json {
		font-size: 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		color: #9ca3af;
		padding: 6px 10px 8px;
		max-height: 100px;
		overflow: auto;
		margin: 0;
		white-space: pre-wrap;
		word-break: break-all;
	}

	.gr-audio-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-audio-container {
		padding: 6px 8px 8px;
		background: linear-gradient(135deg, #2a2a2a 0%, #222 100%);
		border-radius: 4px;
		margin: 6px 8px 8px;
	}

	.gr-audio {
		width: 100%;
		height: 32px;
		border-radius: 4px;
		filter: brightness(0.85) contrast(1.1) saturate(0.9);
	}

	.gr-image {
		width: 100%;
		max-height: 80px;
		object-fit: contain;
	}

	.gr-empty {
		font-size: 11px;
		color: #555;
		font-style: italic;
		padding: 10px;
		text-align: center;
	}

	.gr-fallback {
		font-size: 10px;
		color: #9ca3af;
		background: #1a1a1a;
		border: 1px solid #333;
		padding: 8px 10px;
		border-radius: 6px;
	}

	.gr-fallback .fallback-type {
		display: inline-block;
		color: #666;
		font-style: italic;
		font-size: 9px;
		background: #2a2a2a;
		padding: 2px 6px;
		border-radius: 4px;
		margin-bottom: 4px;
	}

	.gr-fallback pre {
		margin: 0;
		font-size: 9px;
		white-space: pre-wrap;
		word-break: break-all;
		max-height: 60px;
		overflow: auto;
	}

	.result-selector {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 6px 10px;
		background: rgba(249, 115, 22, 0.05);
		border-top: 1px solid rgba(249, 115, 22, 0.1);
	}

	.result-nav {
		width: 20px;
		height: 20px;
		border: none;
		background: rgba(249, 115, 22, 0.1);
		color: #f97316;
		font-size: 14px;
		font-weight: 600;
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}

	.result-nav:hover:not(:disabled) {
		background: rgba(249, 115, 22, 0.25);
	}

	.result-nav:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.result-counter {
		font-size: 11px;
		font-weight: 600;
		color: #888;
		font-family: 'SF Mono', Monaco, monospace;
		min-width: 32px;
		text-align: center;
	}

	/* Map items section */
	.map-items-section {
		border-top: 1px solid rgba(168, 85, 247, 0.2);
		background: rgba(168, 85, 247, 0.03);
	}

	.map-items-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		border-bottom: 1px solid rgba(168, 85, 247, 0.1);
	}

	.map-items-title {
		font-size: 10px;
		font-weight: 600;
		color: #a855f7;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.map-items-list {
		max-height: 150px;
		overflow-y: auto;
	}

	.map-item {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 10px;
		border-bottom: 1px solid rgba(168, 85, 247, 0.06);
		transition: background 0.15s;
	}

	.map-item:hover {
		background: rgba(168, 85, 247, 0.08);
	}

	.map-item:last-child {
		border-bottom: none;
	}

	.map-item-index {
		font-size: 10px;
		font-weight: 600;
		color: #a855f7;
		min-width: 18px;
		font-family: 'SF Mono', Monaco, monospace;
	}

	.map-item-preview {
		flex: 1;
		font-size: 10px;
		color: #888;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.map-item.has-output .map-item-preview {
		color: #aaa;
	}

	.map-item-replay {
		width: 20px;
		height: 20px;
		border: none;
		background: rgba(168, 85, 247, 0.15);
		color: #a855f7;
		font-size: 10px;
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		flex-shrink: 0;
	}

	.map-item-replay:hover {
		background: rgba(168, 85, 247, 0.3);
	}

	.map-expand-btn {
		width: 100%;
		padding: 6px 10px;
		border: none;
		background: transparent;
		color: #a855f7;
		font-size: 10px;
		font-weight: 500;
		cursor: pointer;
		transition: background 0.15s;
		border-top: 1px solid rgba(168, 85, 247, 0.1);
	}

	.map-expand-btn:hover {
		background: rgba(168, 85, 247, 0.1);
	}

	/* Item List Styles */
	.item-list-section {
		border-top: 1px solid rgba(34, 197, 94, 0.2);
		background: rgba(34, 197, 94, 0.03);
	}

	.item-list-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		border-bottom: 1px solid rgba(34, 197, 94, 0.1);
	}

	.item-list-title {
		font-size: 10px;
		font-weight: 600;
		color: #22c55e;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.item-list-items {
		max-height: 300px;
		overflow-y: auto;
	}

	.item-list-item {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px 10px;
		border-bottom: 1px solid rgba(34, 197, 94, 0.08);
	}

	.item-list-item:last-child {
		border-bottom: none;
	}

	.item-list-index {
		font-size: 10px;
		font-weight: 600;
		color: #22c55e;
		min-width: 18px;
		padding-top: 6px;
		font-family: 'SF Mono', Monaco, monospace;
	}

	.item-list-fields {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.gr-select {
		width: 100%;
		padding: 6px 8px;
		font-size: 11px;
		background: rgba(34, 197, 94, 0.08);
		border: 1px solid rgba(34, 197, 94, 0.2);
		border-radius: 4px;
		color: #e5e5e5;
		cursor: pointer;
	}

	.gr-select:focus {
		outline: none;
		border-color: rgba(34, 197, 94, 0.5);
	}

	.item-list-textarea {
		resize: vertical;
		min-height: 40px;
	}
</style>
