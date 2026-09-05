/**
 * Cytoscape.js Visualizer for Control Flow Graph (CFG) and Dominator Tree.
 */

class GraphVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cy = null;
        this.currentElements = [];
    }

    init() {
        if (!this.container) return;

        const isDagreAvailable = typeof cytoscape !== 'undefined' && cytoscape('layout', 'dagre');
        const defaultLayout = isDagreAvailable ? {
            name: 'dagre',
            rankDir: 'TB',
            nodeSep: 60,
            rankSep: 80,
            padding: 30
        } : {
            name: 'breadthfirst',
            directed: true,
            padding: 30,
            spacingFactor: 1.5
        };

        this.cy = cytoscape({
            container: this.container,
            boxSelectionEnabled: false,
            autounselectify: false,
            style: [
                // Node Styles
                {
                    selector: 'node',
                    style: {
                        'shape': 'round-rectangle',
                        'background-color': '#1e293b',
                        'border-width': 2,
                        'border-color': '#38bdf8',
                        'border-opacity': 0.8,
                        'label': 'data(label)',
                        'color': '#f8fafc',
                        'font-size': '12px',
                        'font-family': 'Fira Code, monospace',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'padding': '16px',
                        'width': 'label',
                        'height': 'label',
                        'text-wrap': 'wrap',
                        'text-max-width': '220px',
                        'transition-property': 'border-color, background-color, transform',
                        'transition-duration': '0.15s'
                    }
                },
                {
                    selector: 'node[type = "entry"]',
                    style: {
                        'border-color': '#06b6d4',
                        'border-width': 3,
                        'background-color': '#0c4a6e',
                    }
                },
                {
                    selector: 'node[type = "exit"]',
                    style: {
                        'border-color': '#10b981',
                        'border-width': 3,
                        'background-color': '#064e3b',
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#f59e0b',
                        'border-width': 4,
                        'background-color': '#334155',
                    }
                },
                // Edge Styles
                {
                    selector: 'edge',
                    style: {
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#64748b',
                        'line-color': '#64748b',
                        'width': 2,
                        'arrow-scale': 1.2,
                        'label': 'data(label)',
                        'font-size': '10px',
                        'font-family': 'Inter, sans-serif',
                        'color': '#94a3b8',
                        'text-background-color': '#0b0f19',
                        'text-background-opacity': 0.8,
                        'text-background-padding': '2px',
                        'text-background-shape': 'roundrectangle',
                    }
                },
                {
                    selector: 'edge[edge_type = "branch_true"]',
                    style: {
                        'line-color': '#10b981',
                        'target-arrow-color': '#10b981',
                        'color': '#10b981',
                        'width': 2.5,
                    }
                },
                {
                    selector: 'edge[edge_type = "branch_false"]',
                    style: {
                        'line-color': '#f43f5e',
                        'target-arrow-color': '#f43f5e',
                        'color': '#f43f5e',
                        'width': 2.5,
                    }
                },
                {
                    selector: 'edge[edge_type = "jump"]',
                    style: {
                        'line-color': '#38bdf8',
                        'target-arrow-color': '#38bdf8',
                        'line-style': 'dashed',
                        'color': '#38bdf8',
                    }
                },
                {
                    selector: 'edge[label = "idom"]',
                    style: {
                        'line-color': '#a855f7',
                        'target-arrow-color': '#a855f7',
                        'color': '#c084fc',
                        'width': 2.5,
                    }
                }
            ],
            layout: defaultLayout
        });

        // Event listener for node click
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            this.onNodeClick(node.data());
        });
    }

    render(elements) {
        if (!this.cy) {
            this.init();
        }
        if (!this.cy) return;

        this.currentElements = elements;
        this.cy.elements().remove();
        this.cy.add(elements);

        const isDagre = typeof cytoscape !== 'undefined' && cytoscape('layout', 'dagre');
        const layoutOptions = isDagre ? {
            name: 'dagre',
            rankDir: 'TB',
            nodeSep: 70,
            rankSep: 90,
            padding: 30,
            animate: true,
            animationDuration: 300
        } : {
            name: 'breadthfirst',
            directed: true,
            padding: 30,
            spacingFactor: 1.4,
            animate: true
        };

        const layout = this.cy.layout(layoutOptions);
        layout.run();
        this.cy.fit(undefined, 30);
    }

    fit() {
        if (this.cy) {
            this.cy.fit(undefined, 30);
        }
    }

    onNodeClick(data) {
        const inspector = document.getElementById('inspector-content');
        if (!inspector) return;

        inspector.innerHTML = `
            <div style="margin-bottom: 0.5rem;">
                <strong style="color: var(--accent-cyan); font-size: 1rem;">${data.id}</strong>
                ${data.label && data.label !== data.id ? `<span class="badge" style="margin-left: 0.5rem;">${data.label}</span>` : ''}
            </div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.75rem;">
                Instructions: <strong>${data.instr_count || 0}</strong>
            </div>
            <div style="font-weight: 600; font-size: 0.8rem; margin-bottom: 0.25rem;">Block Code:</div>
            <pre>${data.code || '(empty block)'}</pre>
        `;
    }
}

// Global visualizer instances
let cfgVisualizerInstance = null;
let domTreeVisualizerInstance = null;

function getCfgVisualizer() {
    if (!cfgVisualizerInstance) {
        cfgVisualizerInstance = new GraphVisualizer('cfg-canvas');
        cfgVisualizerInstance.init();
    }
    return cfgVisualizerInstance;
}

function getDomTreeVisualizer() {
    if (!domTreeVisualizerInstance) {
        domTreeVisualizerInstance = new GraphVisualizer('domtree-canvas');
        domTreeVisualizerInstance.init();
    }
    return domTreeVisualizerInstance;
}
