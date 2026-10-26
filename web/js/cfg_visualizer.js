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
            minZoom: 0.2,
            maxZoom: 2.0,
            style: [
                // Node Styles
                {
                    selector: 'node',
                    style: {
                        'shape': 'round-rectangle',
                        'background-color': '#18181b',
                        'border-width': 1.5,
                        'border-color': 'rgba(255, 255, 255, 0.18)',
                        'border-opacity': 1.0,
                        'label': 'data(label)',
                        'color': '#ffffff',
                        'font-size': '12px',
                        'font-family': 'SF Mono, Menlo, monospace',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'padding': '16px',
                        'width': 'label',
                        'height': 'label',
                        'text-wrap': 'wrap',
                        'text-max-width': '220px',
                        'transition-property': 'border-color, background-color, transform',
                        'transition-duration': '0.12s'
                    }
                },
                {
                    selector: 'node[type = "entry"]',
                    style: {
                        'border-color': '#0a84ff',
                        'border-width': 2.5,
                        'background-color': 'rgba(10, 132, 255, 0.15)',
                    }
                },
                {
                    selector: 'node[type = "exit"]',
                    style: {
                        'border-color': '#30d158',
                        'border-width': 2.5,
                        'background-color': 'rgba(48, 209, 88, 0.15)',
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#ff9f0a',
                        'border-width': 3,
                        'background-color': 'rgba(255, 159, 10, 0.2)',
                    }
                },
                // Edge Styles
                {
                    selector: 'edge',
                    style: {
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#545458',
                        'line-color': '#545458',
                        'width': 2,
                        'arrow-scale': 1.2,
                        'label': 'data(label)',
                        'font-size': '10px',
                        'font-family': '-apple-system, BlinkMacSystemFont, sans-serif',
                        'color': '#8e8e93',
                        'text-background-color': '#1c1c1e',
                        'text-background-opacity': 0.95,
                        'text-background-padding': '3px',
                        'text-background-shape': 'roundrectangle',
                    }
                },
                {
                    selector: 'edge[edge_type = "branch_true"]',
                    style: {
                        'line-color': '#30d158',
                        'target-arrow-color': '#30d158',
                        'color': '#30d158',
                        'width': 2.5,
                        // Non-color cue (WCAG 1.4.1): a text glyph so the
                        // true/false meaning survives color-blind rendering.
                        'label': 'T',
                        'font-weight': 'bold',
                        'font-size': '13px',
                        'source-label': '',
                    }
                },
                {
                    selector: 'edge[edge_type = "branch_false"]',
                    style: {
                        'line-color': '#ff453a',
                        'target-arrow-color': '#ff453a',
                        'color': '#ff453a',
                        'width': 2.5,
                        'line-style': 'dashed',
                        // Non-color cue: dashed line + 'F' glyph distinguish the
                        // false edge independent of its red hue.
                        'label': 'F',
                        'font-weight': 'bold',
                        'font-size': '13px',
                    }
                },
                {
                    selector: 'edge[edge_type = "jump"]',
                    style: {
                        'line-color': '#0a84ff',
                        'target-arrow-color': '#0a84ff',
                        'line-style': 'dashed',
                        'color': '#0a84ff',
                    }
                },
                {
                    selector: 'edge[label = "idom"]',
                    style: {
                        'line-color': '#bf5af2',
                        'target-arrow-color': '#bf5af2',
                        'color': '#bf5af2',
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
        // Honor the user's reduced-motion preference (WCAG 2.3.3): skip the
        // layout tween entirely when the OS/browser requests less animation.
        const reduceMotion = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const layoutOptions = isDagre ? {
            name: 'dagre',
            rankDir: 'TB',
            nodeSep: 70,
            rankSep: 90,
            padding: 30,
            animate: !reduceMotion,
            animationDuration: reduceMotion ? 0 : 300
        } : {
            name: 'breadthfirst',
            directed: true,
            padding: 30,
            spacingFactor: 1.4,
            animate: !reduceMotion
        };

        const layout = this.cy.layout(layoutOptions);
        layout.run();
        // Ensure the viewport matches the (possibly previously-hidden) container
        // before fitting, otherwise a graph first laid out while its tab pane was
        // display:none renders at 0x0 and fit() alone cannot recover it.
        this.cy.resize();
        this.cy.fit(undefined, 40);
        if (this.cy.zoom() > 1.25) {
            this.cy.zoom(1.0);
            this.cy.center();
        }
    }

    fit() {
        if (this.cy) {
            // resize() re-reads the container dimensions; required when the tab
            // becomes visible for the first time after being display:none.
            this.cy.resize();
            this.cy.fit(undefined, 40);
            if (this.cy.zoom() > 1.25) {
                this.cy.zoom(1.0);
                this.cy.center();
            }
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
        // Expose for the headless UI test-suite to introspect rendered nodes.
        window.__cfgViz = cfgVisualizerInstance;
    }
    return cfgVisualizerInstance;
}

function getDomTreeVisualizer() {
    if (!domTreeVisualizerInstance) {
        domTreeVisualizerInstance = new GraphVisualizer('domtree-canvas');
        domTreeVisualizerInstance.init();
        // Expose for the headless UI test-suite to introspect rendered nodes.
        window.__domViz = domTreeVisualizerInstance;
    }
    return domTreeVisualizerInstance;
}

class RigVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cy = null;
        this.currentElements = [];
    }

    init() {
        if (!this.container || typeof cytoscape === 'undefined') return;

        this.cy = cytoscape({
            container: this.container,
            boxSelectionEnabled: false,
            autounselectify: false,
            minZoom: 0.2,
            maxZoom: 3.0,
            style: [
                {
                    selector: 'node',
                    style: {
                        'shape': 'ellipse',
                        'background-color': 'data(color)',
                        'border-width': 2,
                        'border-color': 'rgba(255, 255, 255, 0.45)',
                        'label': 'data(label)',
                        'color': '#ffffff',
                        'font-size': '11px',
                        'font-family': 'SF Mono, Menlo, monospace',
                        'font-weight': '600',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 54,
                        'height': 54,
                        'text-wrap': 'wrap',
                        'text-max-width': '100px',
                        'text-outline-color': '#09090b',
                        'text-outline-width': 2,
                        'transition-property': 'border-color, transform',
                        'transition-duration': '0.15s'
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#ffffff',
                        'border-width': 4,
                        'border-opacity': 1.0,
                        'shadow-blur': 12,
                        'shadow-color': 'data(color)',
                        'shadow-opacity': 0.8
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'curve-style': 'straight',
                        'line-color': 'rgba(255, 255, 255, 0.22)',
                        'width': 1.8,
                        'opacity': 0.85
                    }
                },
                {
                    selector: 'edge:selected',
                    style: {
                        'line-color': '#f59e0b',
                        'width': 3,
                        'opacity': 1.0
                    }
                }
            ],
            layout: {
                name: 'concentric',
                concentric: function(node) {
                    return node.data('degree') || 1;
                },
                levelWidth: function() { return 2; },
                padding: 40
            }
        });
    }

    render(elements) {
        if (!this.cy) this.init();
        if (!this.cy) return;

        this.currentElements = elements || [];
        this.cy.elements().remove();

        if (this.currentElements.length > 0) {
            this.cy.add(this.currentElements);
            this.layout();
        }
    }

    layout() {
        if (!this.cy) return;
        const layout = this.cy.layout({
            name: 'concentric',
            concentric: function(node) {
                return node.data('degree') || 1;
            },
            levelWidth: function() { return 2; },
            padding: 40,
            animate: true,
            animationDuration: 400
        });
        layout.run();
        setTimeout(() => this.fit(), 420);
    }

    fit() {
        if (!this.cy) return;
        this.cy.resize();
        this.cy.fit(undefined, 40);
    }
}

let rigVisualizerInstance = null;

function getRigVisualizer() {
    if (!rigVisualizerInstance) {
        rigVisualizerInstance = new RigVisualizer('rig-canvas');
        rigVisualizerInstance.init();
        // Expose for headless tests and studio inspector
        window.__rigViz = rigVisualizerInstance;
    }
    return rigVisualizerInstance;
}

