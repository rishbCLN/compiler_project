/**
 * Main Web Application Controller for IR Compression Studio.
 * Handles compiler execution, UI event dispatching, and state management.
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const sourceCodeElem = document.getElementById('source-code');
    const lineNumbersElem = document.getElementById('line-numbers');
    const btnCompile = document.getElementById('btn-compile');
    const btnExport = document.getElementById('btn-export');
    const btnClear = document.getElementById('btn-clear');
    const sampleSelect = document.getElementById('sample-select');
    const compilerStatus = document.getElementById('compiler-status');
    const cursorPosElem = document.getElementById('cursor-pos');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const btnFitCfg = document.getElementById('btn-fit-cfg');
    const btnRelayoutCfg = document.getElementById('btn-relayout-cfg');
    const cfgModeRadios = document.querySelectorAll('input[name="cfg-view"]');

    // State
    let lastCompileResult = null;
    let samples = [];

    // ---------------- Line Numbers & Editor Sync ----------------

    function updateLineNumbers() {
        const lines = sourceCodeElem.value.split('\n').length;
        lineNumbersElem.innerHTML = Array.from({ length: lines }, (_, i) => i + 1).join('<br>');
    }

    sourceCodeElem.addEventListener('input', updateLineNumbers);
    sourceCodeElem.addEventListener('scroll', () => {
        lineNumbersElem.scrollTop = sourceCodeElem.scrollTop;
    });

    sourceCodeElem.addEventListener('keyup', updateCursorPos);
    sourceCodeElem.addEventListener('click', updateCursorPos);

    function updateCursorPos() {
        const text = sourceCodeElem.value;
        const pos = sourceCodeElem.selectionStart;
        const lines = text.slice(0, pos).split('\n');
        const line = lines.length;
        const col = lines[lines.length - 1].length + 1;
        cursorPosElem.textContent = `Ln ${line}, Col ${col}`;
    }

    // ---------------- Tab Switching ----------------

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add('active');
            }

            // Trigger canvas relayout when switching to graph tabs
            if (targetId === 'cfg-tab') {
                setTimeout(() => {
                    const viz = getCfgVisualizer();
                    viz.fit();
                }, 100);
            } else if (targetId === 'ssa-tab') {
                setTimeout(() => {
                    const domViz = getDomTreeVisualizer();
                    domViz.fit();
                }, 100);
            }
        });
    });

    // ---------------- Sample Benchmarks ----------------

    async function loadSamples() {
        try {
            const resp = await fetch('/api/samples');
            const data = await resp.json();
            samples = data.samples || [];

            sampleSelect.innerHTML = '<option value="">Load Academic Benchmark...</option>';
            samples.forEach((sample, idx) => {
                const opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = `${sample.title}`;
                sampleSelect.appendChild(opt);
            });

            // Pre-load sample 1 by default
            if (samples.length > 0) {
                sampleSelect.value = 0;
                sourceCodeElem.value = samples[0].code;
                updateLineNumbers();
                runCompilation();
            }
        } catch (err) {
            console.error('Failed to load samples:', err);
        }
    }

    sampleSelect.addEventListener('change', () => {
        const idx = sampleSelect.value;
        if (idx !== '' && samples[idx]) {
            sourceCodeElem.value = samples[idx].code;
            updateLineNumbers();
            runCompilation();
        }
    });

    // ---------------- Compilation Runner ----------------

    async function runCompilation() {
        const code = sourceCodeElem.value.trim();
        if (!code) return;

        compilerStatus.textContent = 'Compiling...';
        compilerStatus.className = 'badge';

        try {
            const resp = await fetch('/api/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            const data = await resp.json();

            if (!data.success) {
                compilerStatus.textContent = `Error: ${data.error_type}`;
                compilerStatus.className = 'badge error';
                alert(`Compiler Error at L${data.line || 1}:C${data.col || 1}\n\n${data.message}`);
                return;
            }

            lastCompileResult = data;
            compilerStatus.textContent = 'Optimized & Compressed';
            compilerStatus.className = 'badge';

            updateAllViews(data);

        } catch (err) {
            console.error('Compilation failed:', err);
            compilerStatus.textContent = 'API Error';
            compilerStatus.className = 'badge error';
        }
    }

    btnCompile.addEventListener('click', runCompilation);
    btnClear.addEventListener('click', () => {
        sourceCodeElem.value = '';
        updateLineNumbers();
    });

    // Shortcut: Ctrl+Enter to compile
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            runCompilation();
        }
    });

    // ---------------- Update All Studio Views ----------------

    function updateAllViews(data) {
        // 1. Overview & Metrics
        const comp = data.compression_metrics;
        document.getElementById('stat-final-ratio').textContent = `${comp.final_compression_ratio_percent}%`;
        document.getElementById('stat-bytes-detail').textContent = `Raw: ${comp.raw_ir_text_bytes} B → Comp: ${comp.huffman_compressed_bytes} B`;

        document.getElementById('stat-instr-ratio').textContent = `${comp.instruction_reduction_percent}%`;
        document.getElementById('stat-instr-detail').textContent = `${comp.raw_instruction_count} → ${comp.optimized_instruction_count} Instructions`;

        const cfgStats = data.cfg.stats;
        document.getElementById('stat-cfg-complexity').textContent = cfgStats.cyclomatic_complexity;
        document.getElementById('stat-cfg-detail').textContent = `${cfgStats.basic_block_count} Blocks, ${cfgStats.edge_count} Edges`;

        const symStats = comp.symbol_table_stats;
        document.getElementById('stat-sym-ratio').textContent = `${symStats.compression_percentage}%`;
        document.getElementById('stat-sym-detail').textContent = `${symStats.symbol_count} Symbols Minified`;

        // Tiers
        document.getElementById('tier1-metric').textContent = `-${comp.structural_reduction_percent}%`;
        document.getElementById('tier2-metric').textContent = `-${comp.constant_pool_stats.compression_percentage}%`;
        document.getElementById('tier3-metric').textContent = `-${comp.bytecode_reduction_percent}%`;
        document.getElementById('tier4-metric').textContent = `-${comp.final_compression_ratio_percent}%`;

        // Hex Dump
        document.getElementById('hex-dump').textContent = comp.hex_dump_sample || '(empty)';

        // Advanced Architecture (Design Spec)
        if (data.advanced_compression) {
            const adv = data.advanced_compression;
            document.getElementById('adv-rpo-elided').textContent = `${adv.elided_fallthrough_edges} / ${adv.total_cfg_blocks} Blocks`;
            document.getElementById('adv-opcodes-stream').textContent = `${adv.columnar_sizes.opcodes_bytes} B`;
            document.getElementById('adv-deltas-stream').textContent = `${adv.columnar_sizes.deltas_bytes} B`;
            document.getElementById('adv-immediates-stream').textContent = `${adv.columnar_sizes.immediates_bytes} B`;
            const vBadge = document.getElementById('verification-badge');
            if (vBadge) {
                vBadge.textContent = adv.verification_status;
            }
        }

        // Chart
        renderCompressionChart(comp);

        // 2. CFG Graph
        updateCfgGraph();

        // 3. Dominance & SSA
        updateDominanceView(data.dominance);
        document.getElementById('raw-tac-code').textContent = data.raw_ir.text || '(empty)';
        document.getElementById('ssa-tac-code').textContent = data.ssa.text || '(empty)';

        const domViz = getDomTreeVisualizer();
        domViz.render(data.dominance.elements);

        // 4. Symbols & Constants
        updateSymbolsTable(data.symbol_table);
        updateConstantPoolTable(data.constant_pool);

        // 5. Optimization Passes
        const optStats = data.optimized_ir.stats;
        document.getElementById('opt-stat-folds').textContent = optStats.constant_folds;
        document.getElementById('opt-stat-props').textContent = optStats.constant_propagations;
        document.getElementById('opt-stat-gvn').textContent = optStats.gvn_eliminations;
        document.getElementById('opt-stat-dce').textContent = optStats.dead_instructions_removed;
        document.getElementById('optimized-ir-code').textContent = data.optimized_ir.text || '(empty)';

        // 6. AST & Tokens
        document.getElementById('ast-tree-view').textContent = JSON.stringify(data.ast, null, 2);
        updateTokensTable(data.tokens);
    }

    // ---------------- CFG Graph Modes ----------------

    function updateCfgGraph() {
        if (!lastCompileResult) return;
        const selectedMode = document.querySelector('input[name="cfg-view"]:checked')?.value || 'raw';
        const viz = getCfgVisualizer();

        if (selectedMode === 'raw') {
            viz.render(lastCompileResult.cfg.elements);
        } else if (selectedMode === 'ssa') {
            viz.render(lastCompileResult.ssa.elements);
        } else if (selectedMode === 'optimized') {
            viz.render(lastCompileResult.optimized_ir.elements);
        }
    }

    cfgModeRadios.forEach(radio => {
        radio.addEventListener('change', updateCfgGraph);
    });

    btnFitCfg.addEventListener('click', () => {
        getCfgVisualizer().fit();
    });

    btnRelayoutCfg.addEventListener('click', () => {
        updateCfgGraph();
    });

    // ---------------- Dominance Table ----------------

    function updateDominanceView(domData) {
        const tbody = document.querySelector('#dominance-table tbody');
        if (!tbody || !domData) return;

        const idoms = domData.data.idom || {};
        const frontiers = domData.data.dominance_frontiers || {};
        const dominators = domData.data.dominators || {};

        tbody.innerHTML = '';
        Object.keys(dominators).sort().forEach(bId => {
            const tr = document.createElement('tr');
            const idomVal = idoms[bId] || '(None / Entry)';
            const dfVal = (frontiers[bId] && frontiers[bId].length > 0) ? frontiers[bId].join(', ') : '∅';
            const domsVal = dominators[bId] ? dominators[bId].join(', ') : '';

            tr.innerHTML = `
                <td><strong style="color: var(--accent-cyan);">${bId}</strong></td>
                <td><span class="badge" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; border-color: rgba(168, 85, 247, 0.3);">${idomVal}</span></td>
                <td><strong>{ ${dfVal} }</strong></td>
                <td style="color: var(--text-muted);">{ ${domsVal} }</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ---------------- Symbols & Constants Tables ----------------

    function updateSymbolsTable(symData) {
        const tbody = document.querySelector('#symbol-table-view tbody');
        const badge = document.getElementById('sym-count-badge');
        if (!tbody || !symData) return;

        const syms = symData.symbols || [];
        badge.textContent = `${syms.length} Symbols`;

        if (syms.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No symbols registered.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        syms.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${s.name}</strong></td>
                <td><span class="stage-tag" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">${s.minified_name}</span></td>
                <td style="color: var(--accent-amber);">${s.type}</td>
                <td>Level ${s.scope_level}</td>
                <td>${s.ref_count}x</td>
                <td>+${s.offset} B</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function updateConstantPoolTable(cpData) {
        const tbody = document.querySelector('#constant-pool-view tbody');
        const badge = document.getElementById('const-count-badge');
        if (!tbody || !cpData) return;

        const entries = cpData.entries || [];
        badge.textContent = `${entries.length} Unique Literals`;

        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No constants pooled.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        entries.forEach(e => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="stage-tag">CP#${e.index}</span></td>
                <td><strong style="color: var(--text-primary);">${e.value}</strong></td>
                <td style="color: var(--accent-cyan);">${e.type}</td>
                <td>${e.occurrences} references</td>
                <td>${e.raw_size_bytes} Bytes</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ---------------- Tokens Table ----------------

    function updateTokensTable(tokens) {
        const tbody = document.querySelector('#tokens-table tbody');
        if (!tbody || !tokens) return;

        tbody.innerHTML = '';
        tokens.slice(0, 100).forEach(tok => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);">${tok.type}</span></td>
                <td><strong>${escapeHtml(tok.value)}</strong></td>
                <td>${tok.line}</td>
                <td>${tok.col}</td>
            `;
            tbody.appendChild(tr);
        });

        if (tokens.length > 100) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="4" class="text-center">... and ${tokens.length - 100} more tokens</td>`;
            tbody.appendChild(tr);
        }
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ---------------- Export Binary ----------------

    btnExport.addEventListener('click', async () => {
        const code = sourceCodeElem.value.trim();
        if (!code) {
            alert('Please enter code before exporting.');
            return;
        }

        try {
            const resp = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (!resp.ok) throw new Error('Export failed');

            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'compiled_compressed_ir.cir';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error(err);
            alert('Failed to export binary IR file.');
        }
    });

    // Initialize application
    loadSamples();
});
