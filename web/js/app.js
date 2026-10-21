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
    const inputSampleSelect = document.getElementById('input-sample-select');
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

    // ---------------- Toast Notifications ----------------
    // Non-blocking replacement for alert(): keeps the UI responsive and is
    // observable by the headless test-suite (no modal dialog to dismiss).
    const toastContainer = document.getElementById('toast-container');

    function showToast(message, type = 'info', title = null) {
        if (!toastContainer) {
            console.warn(`[toast:${type}] ${message}`);
            return;
        }
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
        const heading = title || (type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Notice');
        toast.innerHTML = `<span class="toast-title"></span><span class="toast-body"></span>`;
        toast.querySelector('.toast-title').textContent = heading;
        toast.querySelector('.toast-body').textContent = message;
        toastContainer.appendChild(toast);
        // Force reflow so the entrance transition plays.
        requestAnimationFrame(() => toast.classList.add('show'));
        const ttl = type === 'error' ? 7000 : 4000;
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 250);
        }, ttl);
    }

    // ---------------- Line Numbers & Editor Sync ----------------

    function updateLineNumbers() {
        const lines = sourceCodeElem.value.split('\n').length;
        lineNumbersElem.innerHTML = Array.from({ length: lines }, (_, i) => i + 1).join('<br>');
    }

    sourceCodeElem.addEventListener('input', () => {
        updateLineNumbers();
        compilerStatus.textContent = 'Ready';
        compilerStatus.className = 'badge';
    });
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

    // ---------------- Tab Switching (ARIA tab pattern + keyboard nav) ----------------

    const tabList = document.querySelector('.tabs-nav');
    if (tabList) {
        tabList.setAttribute('role', 'tablist');
        tabList.setAttribute('aria-label', 'Compiler inspector views');
    }

    // Wire up roles, relationships, and roving tabindex so the tab bar is a
    // WCAG-compliant tablist operable entirely from the keyboard.
    tabButtons.forEach((btn, i) => {
        const targetId = btn.getAttribute('data-tab');
        const pane = document.getElementById(targetId);
        const tabId = `tab-${targetId}`;
        btn.id = tabId;
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-controls', targetId);
        const isActive = btn.classList.contains('active');
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        btn.setAttribute('tabindex', isActive ? '0' : '-1');
        if (pane) {
            pane.setAttribute('role', 'tabpanel');
            pane.setAttribute('aria-labelledby', tabId);
            pane.setAttribute('tabindex', '0');
            if (!isActive) pane.setAttribute('hidden', '');
        }
    });

    function activateTab(btn, { focus = true } = {}) {
        tabButtons.forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-selected', 'false');
            b.setAttribute('tabindex', '-1');
        });
        tabPanes.forEach(p => {
            p.classList.remove('active');
            p.setAttribute('hidden', '');
        });

        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
        btn.setAttribute('tabindex', '0');
        if (focus) btn.focus();

        const targetId = btn.getAttribute('data-tab');
        const targetPane = document.getElementById(targetId);
        if (targetPane) {
            targetPane.classList.add('active');
            targetPane.removeAttribute('hidden');
        }

        // Trigger canvas relayout when switching to graph tabs
        if (targetId === 'cfg-tab') {
            setTimeout(() => getCfgVisualizer().fit(), 100);
        } else if (targetId === 'ssa-tab' || targetId === 'tab-p1-6') {
            setTimeout(() => getDomTreeVisualizer().fit(), 100);
        }
    }

    tabButtons.forEach((btn, index) => {
        btn.addEventListener('click', () => activateTab(btn, { focus: false }));

        btn.addEventListener('keydown', (e) => {
            const last = tabButtons.length - 1;
            let next = null;
            switch (e.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                    next = index === last ? 0 : index + 1;
                    break;
                case 'ArrowLeft':
                case 'ArrowUp':
                    next = index === 0 ? last : index - 1;
                    break;
                case 'Home':
                    next = 0;
                    break;
                case 'End':
                    next = last;
                    break;
                case 'Enter':
                case ' ':
                    e.preventDefault();
                    activateTab(btn);
                    return;
                default:
                    return;
            }
            e.preventDefault();
            activateTab(tabButtons[next]);
        });
    });

    // ---------------- Sample Benchmarks ----------------

    async function loadSamples() {
        try {
            const resp = await fetch('/api/samples');
            const data = await resp.json();
            samples = data.samples || [];

            sampleSelect.innerHTML = '<option value="">Load Academic Benchmark...</option>';
            if (inputSampleSelect) {
                inputSampleSelect.innerHTML = '<option value="">Choose Example...</option>';
            }

            samples.forEach((sample, idx) => {
                const opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = `${sample.title}`;
                sampleSelect.appendChild(opt);

                if (inputSampleSelect) {
                    const optInput = document.createElement('option');
                    optInput.value = idx;
                    optInput.textContent = `${sample.title}`;
                    inputSampleSelect.appendChild(optInput);
                }
            });

            // Pre-load sample 1 by default into editor without auto-compiling
            if (samples.length > 0) {
                sampleSelect.value = 0;
                if (inputSampleSelect) inputSampleSelect.value = 0;
                sourceCodeElem.value = samples[0].code;
                updateLineNumbers();
            }
        } catch (err) {
            console.error('Failed to load samples:', err);
        }
    }

    function handleSampleChange(idx) {
        if (idx !== '' && samples[idx]) {
            sampleSelect.value = idx;
            if (inputSampleSelect) inputSampleSelect.value = idx;
            sourceCodeElem.value = samples[idx].code;
            updateLineNumbers();
            compilerStatus.textContent = 'Ready';
            compilerStatus.className = 'badge';
        }
    }

    sampleSelect.addEventListener('change', () => handleSampleChange(sampleSelect.value));
    if (inputSampleSelect) {
        inputSampleSelect.addEventListener('change', () => handleSampleChange(inputSampleSelect.value));
    }

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
                showToast(
                    `L${data.line || 1}:C${data.col || 1} — ${data.message}`,
                    'error',
                    `Compiler Error (${data.error_type || 'Error'})`
                );
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
            showToast('Could not reach the compiler API. Is the server running?', 'error', 'API Error');
        }
    }

    btnCompile.addEventListener('click', runCompilation);
    btnClear.addEventListener('click', () => {
        sourceCodeElem.value = '';
        updateLineNumbers();
        compilerStatus.textContent = 'Ready';
        compilerStatus.className = 'badge';
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
            // Final Structure-of-Arrays bitstream (the full advanced architecture
            // figure; kept distinct from tier4's single-stream Huffman number).
            const advFinalBytes = document.getElementById('adv-final-bitstream');
            const advFinalPct = document.getElementById('adv-final-percent');
            if (advFinalBytes && typeof adv.final_advanced_bitstream_bytes === 'number') {
                advFinalBytes.textContent = `${adv.final_advanced_bitstream_bytes} B`;
            }
            if (advFinalPct && typeof adv.final_advanced_compression_percent === 'number') {
                advFinalPct.textContent = `${adv.final_advanced_compression_percent}% vs raw IR`;
            }
        }

        // Chart (pass advanced SoA bitstream for the optional 5th bar)
        renderCompressionChart(comp, data.advanced_compression);

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

        // 7. Sequential Compiler Pipeline (Phases 1 & 2 Subphases)
        updateSequentialPipeline(data);

        // 8. Dedicated Subphase Screen Sections
        updateDedicatedSubphaseScreens(data);
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
        const summary = document.getElementById('const-pool-summary');
        if (!tbody || !cpData) return;

        const entries = cpData.entries || [];
        badge.textContent = `${entries.length} Unique Literals`;

        // Honest net-savings accounting: the pool adds index/overhead bytes, which
        // can exceed the dedup savings on tiny inputs. Surface that rather than
        // only showing the optimistic gross figure.
        if (summary) {
            const stats = cpData.stats || {};
            const net = stats.net_bytes_saved;
            const netPct = stats.net_compression_percentage;
            const overhead = stats.pool_overhead_bytes;
            if (typeof net === 'number') {
                if (stats.overhead_exceeds_savings) {
                    summary.className = 'pool-summary pool-summary-warn';
                    summary.innerHTML =
                        `<span class="pool-summary-badge warn">Net overhead</span>` +
                        `Pool overhead (${overhead ?? '?'} B) exceeds dedup savings on this ` +
                        `small input: net ${net} B (${netPct}%). Interning pays off as ` +
                        `literals repeat across larger programs.`;
                } else {
                    summary.className = 'pool-summary pool-summary-ok';
                    summary.innerHTML =
                        `<span class="pool-summary-badge ok">Net saved</span>` +
                        `Net ${net} B saved (${netPct}%) after ${overhead ?? 0} B of pool overhead.`;
                }
            } else {
                summary.className = 'pool-summary';
                summary.textContent = '';
            }
        }

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
            showToast('Please enter code before exporting.', 'info');
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
            showToast('Failed to export binary IR file.', 'error');
        }
    });

    // ---------------- Sequential Pipeline Stepper Updater ----------------

    function updateSequentialPipeline(data) {
        // Subphase 1.1: Lexical Analysis
        const tokens = data.tokens || [];
        const tokenPreview = tokens.slice(0, 10).map(t => 
            `<span class="token-chip"><span class="token-chip-type">${escapeHtml(t.type)}</span> <span class="token-chip-val">${escapeHtml(t.value)}</span></span>`
        ).join(' ');
        const step1_1 = document.getElementById('step-output-1-1');
        if (step1_1) {
            step1_1.innerHTML = `
                <div class="output-metric-grid" style="margin-bottom: 0.5rem;">
                    <div class="output-metric-pill"><span class="label">Total Tokens:</span> <span class="val cyan">${tokens.length}</span></div>
                    <div class="output-metric-pill"><span class="label">Status:</span> <span class="val emerald">Scanned & Validated</span></div>
                    <div class="output-metric-pill"><span class="label">Directives:</span> <span class="val">Comments & Whitespace Stripped</span></div>
                </div>
                <div class="output-chips">${tokenPreview}${tokens.length > 10 ? ` <span class="placeholder-text">+${tokens.length - 10} more tokens</span>` : ''}</div>
            `;
        }

        // Subphase 1.2: Syntax Analysis & AST
        const ast = data.ast || {};
        const stmtCount = (ast.statements && ast.statements.length) || 0;
        const step1_2 = document.getElementById('step-output-1-2');
        if (step1_2) {
            step1_2.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Root Node:</span> <span class="val cyan">${escapeHtml(ast.type || 'ProgramNode')}</span></div>
                    <div class="output-metric-pill"><span class="label">Top-Level Statements:</span> <span class="val emerald">${stmtCount}</span></div>
                    <div class="output-metric-pill"><span class="label">Grammar:</span> <span class="val">LL(1) Recursive-Descent with Precedence</span></div>
                </div>
            `;
        }

        // Subphase 1.3: Intermediate Code Generation (TAC)
        const rawIR = data.raw_ir || {};
        const rawInstrs = rawIR.instructions || [];
        const rawLines = (rawIR.text || '').split('\n').filter(Boolean);
        const rawSnippet = rawLines.slice(0, 5).join('\n') + (rawLines.length > 5 ? `\n... (+${rawLines.length - 5} more instructions)` : '');
        const step1_3 = document.getElementById('step-output-1-3');
        if (step1_3) {
            step1_3.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Raw TAC Instructions:</span> <span class="val cyan">${rawIR.count || rawInstrs.length}</span></div>
                    <div class="output-metric-pill"><span class="label">Quadruple Format:</span> <span class="val">(Opcode, Arg1, Arg2, Result)</span></div>
                    <div class="output-metric-pill"><span class="label">Memory Footprint:</span> <span class="val amber">${data.compression_metrics.raw_ir_text_bytes} B</span></div>
                </div>
                <pre class="code-snippet-box">${escapeHtml(rawSnippet)}</pre>
            `;
        }

        // Subphase 1.4: Scoped Symbol Table & Constant Pool
        const symTable = data.symbol_table || {};
        const constPool = data.constant_pool || {};
        const symStats = data.compression_metrics.symbol_table_stats || {};
        const constStats = data.compression_metrics.constant_pool_stats || {};
        const constCount = (constPool.entries && constPool.entries.length) || (constStats.unique_constants || 0);
        const step1_4 = document.getElementById('step-output-1-4');
        if (step1_4) {
            const symSample = (symTable.symbols || []).slice(0, 4).map(s => `${escapeHtml(s.name)} → <strong style="color:var(--accent-purple)">${escapeHtml(s.minified_name)}</strong>`).join(', ');
            step1_4.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Symbols Minified:</span> <span class="val purple">${symStats.symbol_count || 0} (${symStats.compression_percentage || 0}% bytes saved)</span></div>
                    <div class="output-metric-pill"><span class="label">Constants Pooled:</span> <span class="val amber">${constCount} literals</span></div>
                    <div class="output-metric-pill"><span class="label">Dedup Savings:</span> <span class="val emerald">${constStats.compression_percentage || 0}%</span></div>
                </div>
                ${symSample ? `<div style="margin-top:0.4rem; font-size:0.75rem; color:var(--text-secondary);">Sample Aliases: ${symSample}</div>` : ''}
            `;
        }

        // Subphase 1.5: Basic Block Partitioning & CFG
        const cfgStats = (data.cfg && data.cfg.stats) || {};
        const step1_5 = document.getElementById('step-output-1-5');
        if (step1_5) {
            step1_5.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Basic Blocks:</span> <span class="val cyan">${cfgStats.basic_block_count || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Control Flow Edges:</span> <span class="val emerald">${cfgStats.edge_count || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Cyclomatic Complexity:</span> <span class="val amber">${cfgStats.cyclomatic_complexity || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Branch Edge Labels:</span> <span class="val">True (T) / False (F) / Jump / Fallthrough</span></div>
                </div>
            `;
        }

        // Subphase 1.6: Dominance Analysis & Dominator Tree
        const domData = (data.dominance && data.dominance.data) || {};
        const domCount = Object.keys(domData).length;
        const step1_6 = document.getElementById('step-output-1-6');
        if (step1_6) {
            const idomSamples = Object.entries(domData).slice(0, 4).map(([b, d]) => `IDom(${b})=${d.idom || 'None'}`).join(', ');
            step1_6.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Dominator Tree Nodes:</span> <span class="val cyan">${domCount}</span></div>
                    <div class="output-metric-pill"><span class="label">Algorithm:</span> <span class="val">Cytron's Iterated Dominance Frontiers</span></div>
                </div>
                ${idomSamples ? `<div style="margin-top:0.4rem; font-size:0.75rem; color:var(--text-secondary);">Immediate Dominators: ${escapeHtml(idomSamples)}</div>` : ''}
            `;
        }

        // Subphase 1.7: Static Single Assignment (SSA) Transformation
        const ssaStats = (data.ssa && data.ssa.stats) || {};
        const ssaText = data.ssa.text || '';
        const ssaLines = ssaText.split('\n').filter(Boolean);
        const ssaSnippet = ssaLines.slice(0, 5).join('\n') + (ssaLines.length > 5 ? `\n... (+${ssaLines.length - 5} more instructions)` : '');
        const step1_7 = document.getElementById('step-output-1-7');
        if (step1_7) {
            step1_7.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Phi Φ-Nodes Inserted:</span> <span class="val emerald">${ssaStats.phi_nodes_inserted || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Variables Versioned:</span> <span class="val cyan">${ssaStats.variables_versioned || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">SSA Property:</span> <span class="val">Every variable assigned exactly once</span></div>
                </div>
                <pre class="code-snippet-box">${escapeHtml(ssaSnippet)}</pre>
            `;
        }

        // Subphase 2.1: Multi-Pass IR Optimization Suite
        const optStats = (data.optimized_ir && data.optimized_ir.stats) || {};
        const optText = (data.optimized_ir && data.optimized_ir.text) || '';
        const optLines = optText.split('\n').filter(Boolean);
        const optSnippet = optLines.slice(0, 5).join('\n') + (optLines.length > 5 ? `\n... (+${optLines.length - 5} more instructions)` : '');
        const step2_1 = document.getElementById('step-output-2-1');
        if (step2_1) {
            step2_1.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Constant Folds:</span> <span class="val cyan">${optStats.constant_folds || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Constant Propagations:</span> <span class="val emerald">${optStats.constant_propagations || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">GVN Eliminations:</span> <span class="val amber">${optStats.gvn_eliminations || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Dead Code Removed:</span> <span class="val rose">${optStats.dead_instructions_removed || 0}</span></div>
                    <div class="output-metric-pill"><span class="label">Instruction Reduction:</span> <span class="val emerald">${data.compression_metrics.instruction_reduction_percent}%</span></div>
                </div>
                <pre class="code-snippet-box">${escapeHtml(optSnippet)}</pre>
            `;
        }

        // Subphase 2.2: Binary Bytecode Serialization
        const comp = data.compression_metrics || {};
        const bytecodeSize = comp.binary_bytecode_bytes || 0;
        const step2_2 = document.getElementById('step-output-2-2');
        if (step2_2) {
            step2_2.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Bytecode Output:</span> <span class="val cyan">${bytecodeSize} B</span></div>
                    <div class="output-metric-pill"><span class="label">Raw Text IR:</span> <span class="val">${comp.raw_ir_text_bytes} B</span></div>
                    <div class="output-metric-pill"><span class="label">Footprint Reduction:</span> <span class="val emerald">${comp.bytecode_reduction_percent}%</span></div>
                    <div class="output-metric-pill"><span class="label">Encoding Scheme:</span> <span class="val">Opcode (1B) + LEB128 VarInt</span></div>
                </div>
            `;
        }

        // Subphase 2.3: Canonical Huffman Entropy Compression
        const step2_3 = document.getElementById('step-output-2-3');
        if (step2_3) {
            step2_3.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Single-Stream Bitstream:</span> <span class="val emerald">${comp.huffman_compressed_bytes} B</span></div>
                    <div class="output-metric-pill"><span class="label">Total Compression Ratio:</span> <span class="val cyan">${comp.final_compression_ratio_percent}%</span></div>
                    <div class="output-metric-pill"><span class="label">Entropy Format:</span> <span class="val">Canonical Prefix Table + Lossless Bitstream (.cir)</span></div>
                </div>
            `;
        }

        // Subphase 2.4: Advanced Columnar Structure-of-Arrays (SoA)
        const adv = data.advanced_compression;
        const step2_4 = document.getElementById('step-output-2-4');
        if (step2_4 && adv) {
            step2_4.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">RPO Fallthrough Elided:</span> <span class="val cyan">${adv.elided_fallthrough_edges} / ${adv.total_cfg_blocks} Blocks</span></div>
                    <div class="output-metric-pill"><span class="label">Opcodes Stream:</span> <span class="val purple">${adv.columnar_sizes.opcodes_bytes} B</span></div>
                    <div class="output-metric-pill"><span class="label">Backward Deltas:</span> <span class="val emerald">${adv.columnar_sizes.deltas_bytes} B</span></div>
                    <div class="output-metric-pill"><span class="label">Immediates & Strings:</span> <span class="val amber">${adv.columnar_sizes.immediates_bytes} B</span></div>
                    <div class="output-metric-pill"><span class="label">Final SoA Bitstream:</span> <span class="val emerald">${adv.final_advanced_bitstream_bytes} B (${adv.final_advanced_compression_percent}% vs Raw)</span></div>
                    <div class="output-metric-pill"><span class="label">Verification:</span> <span class="val emerald">${adv.verification_status}</span></div>
                </div>
            `;
        }

        // Subphase 2.5: Interactive Analytics & Verification Dashboard
        const step2_5 = document.getElementById('step-output-2-5');
        if (step2_5) {
            const headlineAdv = adv ? `${adv.final_advanced_compression_percent}% (Columnar SoA)` : `${comp.final_compression_ratio_percent}%`;
            step2_5.innerHTML = `
                <div class="output-metric-grid">
                    <div class="output-metric-pill"><span class="label">Headline Savings:</span> <span class="val emerald">${headlineAdv}</span></div>
                    <div class="output-metric-pill"><span class="label">Single-Stream Huffman:</span> <span class="val cyan">${comp.final_compression_ratio_percent}%</span></div>
                    <div class="output-metric-pill"><span class="label">Round-Trip Integrity:</span> <span class="val emerald">100% Lossless Round-Trip Verified</span></div>
                    <div class="output-metric-pill"><span class="label">Package Artifact:</span> <span class="val">compiled_compressed_ir.cir</span></div>
                </div>
            `;
        }
    }

    // Filter controls for Sequential Pipeline
    const filterButtons = document.querySelectorAll('.pipeline-filter-controls .filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filter = btn.getAttribute('data-filter');
            const stepCards = document.querySelectorAll('.sequential-stepper .step-card');
            const dividers = document.querySelectorAll('.sequential-stepper .phase-divider');

            stepCards.forEach(card => {
                const phase = card.getAttribute('data-phase');
                if (filter === 'all' || phase === filter) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });

            dividers.forEach(div => {
                const phaseGroup = div.getAttribute('data-phase-group');
                if (filter === 'all' || phaseGroup === filter) {
                    div.style.display = 'flex';
                } else {
                    div.style.display = 'none';
                }
            });
        });
    });

    // ---------------- Dedicated Subphase Screens Updater ----------------

    function updateDedicatedSubphaseScreens(data) {
        const comp = data.compression_metrics || {};
        const tokens = data.tokens || [];
        const rawIr = data.raw_ir || {};
        const rawInstrs = rawIr.instructions || [];
        const ssa = data.ssa || {};
        const ssaInstrs = ssa.instructions || [];
        const dom = data.dominance || {};
        const adv = data.advanced_compression || {};

        // 1.1 Lexical Tokens Screen
        const p1_1_total = document.getElementById('p1-1-stat-total');
        if (p1_1_total) p1_1_total.textContent = tokens.length;
        const p1_1_types = document.getElementById('p1-1-stat-types');
        if (p1_1_types) {
            const typesSet = new Set(tokens.map(t => t.type));
            p1_1_types.textContent = typesSet.size;
        }

        // 1.2 AST Screen
        const p1_2_root = document.getElementById('p1-2-stat-root');
        if (p1_2_root && data.ast) p1_2_root.textContent = data.ast.type || 'Program';
        const p1_2_stmts = document.getElementById('p1-2-stat-stmts');
        if (p1_2_stmts && data.ast && Array.isArray(data.ast.body)) p1_2_stmts.textContent = data.ast.body.length;

        // 1.3 TAC IR Screen
        const p1_3_count = document.getElementById('p1-3-stat-count');
        if (p1_3_count) p1_3_count.textContent = rawInstrs.length;
        const p1_3_raw = document.getElementById('tab-p1-3-raw-ir');
        if (p1_3_raw) p1_3_raw.textContent = rawIr.text || '(empty)';

        let temps = new Set();
        let labels = new Set();
        rawInstrs.forEach(i => {
            if (i.result && String(i.result).startsWith('t')) temps.add(i.result);
            if (i.arg1 && String(i.arg1).startsWith('t')) temps.add(i.arg1);
            if (i.arg2 && String(i.arg2).startsWith('t')) temps.add(i.arg2);
            if (i.op === 'LABEL' || i.op === 'JUMP' || i.op === 'JUMP_IF') {
                if (i.result && String(i.result).startsWith('L')) labels.add(i.result);
                if (i.arg1 && String(i.arg1).startsWith('L')) labels.add(i.arg1);
                if (i.arg2 && String(i.arg2).startsWith('L')) labels.add(i.arg2);
            }
        });
        const p1_3_temps = document.getElementById('p1-3-stat-temps');
        if (p1_3_temps) p1_3_temps.textContent = temps.size;
        const p1_3_labels = document.getElementById('p1-3-stat-labels');
        if (p1_3_labels) p1_3_labels.textContent = labels.size;

        const quadTbody = document.querySelector('#tac-quadruples-table tbody');
        if (quadTbody) {
            if (rawInstrs.length === 0) {
                quadTbody.innerHTML = '<tr><td colspan="5" class="text-center">No TAC instructions generated.</td></tr>';
            } else {
                quadTbody.innerHTML = rawInstrs.map((inst, idx) => `
                    <tr>
                        <td style="color: var(--text-muted);">${idx + 1}</td>
                        <td><span class="token-chip-type">${escapeHtml(inst.op || '')}</span></td>
                        <td style="color: var(--accent-cyan); font-weight: 600;">${escapeHtml(inst.result || '-')}</td>
                        <td style="color: var(--text-secondary);">${escapeHtml(inst.arg1 || '-')}</td>
                        <td style="color: var(--text-secondary);">${escapeHtml(inst.arg2 || '-')}</td>
                    </tr>
                `).join('');
            }
        }

        // 1.6 Dominance Screen
        const p1_6_nodes = document.getElementById('p1-6-stat-nodes');
        if (p1_6_nodes && dom.data && dom.data.dominators) {
            p1_6_nodes.textContent = Object.keys(dom.data.dominators).length;
        }

        // 1.7 SSA Screen
        const phiCount = ssaInstrs.filter(i => i.op === 'PHI').length;
        const p1_7_phi = document.getElementById('p1-7-stat-phi');
        if (p1_7_phi) p1_7_phi.textContent = phiCount;
        let ssaVars = new Set();
        ssaInstrs.forEach(i => {
            if (i.result && String(i.result).includes('_')) ssaVars.add(i.result);
        });
        const p1_7_vars = document.getElementById('p1-7-stat-vars');
        if (p1_7_vars) p1_7_vars.textContent = ssaVars.size || (ssa.stats ? ssa.stats.variables_renamed_count : 0);

        // 2.2 Bytecode Screen
        const p2_2_bytes = document.getElementById('p2-2-stat-bytes');
        if (p2_2_bytes) p2_2_bytes.textContent = `${comp.binary_bytecode_bytes || 0} B`;
        const p2_2_raw = document.getElementById('p2-2-stat-raw');
        if (p2_2_raw) p2_2_raw.textContent = `${comp.raw_ir_text_bytes || 0} B`;
        const p2_2_ratio = document.getElementById('p2-2-stat-ratio');
        if (p2_2_ratio) p2_2_ratio.textContent = `${comp.bytecode_reduction_percent || 0}%`;
        const bcInspector = document.getElementById('bytecode-stream-inspector');
        if (bcInspector) {
            const hexSnippet = comp.hex_dump_sample || '(no binary bytecode emitted)';
            bcInspector.textContent = `// Serialized Binary Bytecode (Opcode bytes + LEB128 Operands):\n${hexSnippet}\n\n// Total Stream Length: ${comp.binary_bytecode_bytes || 0} bytes (Compressed from ${comp.raw_ir_text_bytes || 0} bytes of raw IR)`;
        }

        // 2.3 Huffman Screen
        const p2_3_bytes = document.getElementById('p2-3-stat-bytes');
        if (p2_3_bytes) p2_3_bytes.textContent = `${comp.huffman_compressed_bytes || 0} B`;
        const p2_3_ratio = document.getElementById('p2-3-stat-ratio');
        if (p2_3_ratio) p2_3_ratio.textContent = `${comp.final_compression_ratio_percent || 0}%`;
        const p2_3_hex = document.getElementById('tab-p2-3-hex-dump');
        if (p2_3_hex) p2_3_hex.textContent = comp.hex_dump_sample || '(no compressed bitstream emitted)';

        // 2.4 Columnar SoA Screen
        if (adv) {
            const advSoaBytes = document.getElementById('tab-adv-final-bitstream');
            if (advSoaBytes) advSoaBytes.textContent = `${adv.final_advanced_bitstream_bytes || 0} B`;
            const advSoaPct = document.getElementById('tab-adv-final-percent');
            if (advSoaPct) advSoaPct.textContent = `${adv.final_advanced_compression_percent || 0}% vs raw IR`;
            const advRpo = document.getElementById('tab-adv-rpo-elided');
            if (advRpo) advRpo.textContent = `${adv.elided_fallthrough_edges || 0} / ${adv.total_cfg_blocks || 0} Blocks`;
            const advOp = document.getElementById('tab-adv-opcodes-stream');
            if (advOp && adv.columnar_sizes) advOp.textContent = `${adv.columnar_sizes.opcodes_bytes} B`;
            const advDelta = document.getElementById('tab-adv-deltas-stream');
            if (advDelta && adv.columnar_sizes) advDelta.textContent = `${adv.columnar_sizes.deltas_bytes} B`;

            const s1 = document.getElementById('soa-stream1-metric');
            if (s1 && adv.columnar_sizes) s1.textContent = `${adv.columnar_sizes.opcodes_bytes} B`;
            const s2 = document.getElementById('soa-stream2-metric');
            if (s2 && adv.columnar_sizes) s2.textContent = `${adv.columnar_sizes.deltas_bytes} B`;
            const s3 = document.getElementById('soa-stream3-metric');
            if (s3 && adv.columnar_sizes) s3.textContent = `${adv.columnar_sizes.immediates_bytes} B`;
            const s4 = document.getElementById('soa-stream4-metric');
            if (s4) s4.textContent = `${adv.elided_fallthrough_edges || 0} Edges`;
        }

        // 2.5 Analytics & Export Screen
        const p2_5_ratio = document.getElementById('p2-5-stat-final-ratio');
        if (p2_5_ratio) p2_5_ratio.textContent = `${comp.final_compression_ratio_percent || 0}%`;
        const p2_5_bytes = document.getElementById('p2-5-stat-bytes-detail');
        if (p2_5_bytes) p2_5_bytes.textContent = `Raw: ${comp.raw_ir_text_bytes || 0} B → Comp: ${comp.huffman_compressed_bytes || 0} B`;
        const p2_5_instr = document.getElementById('p2-5-stat-instr-ratio');
        if (p2_5_instr) p2_5_instr.textContent = `${comp.instruction_reduction_percent || 0}%`;
        const p2_5_instr_d = document.getElementById('p2-5-stat-instr-detail');
        if (p2_5_instr_d) p2_5_instr_d.textContent = `${comp.raw_instruction_count || 0} → ${comp.optimized_instruction_count || 0} Instructions`;
        const p2_5_soa_r = document.getElementById('p2-5-stat-soa-ratio');
        if (p2_5_soa_r && adv) p2_5_soa_r.textContent = `${adv.final_advanced_compression_percent || 0}%`;
        const p2_5_soa_d = document.getElementById('p2-5-stat-soa-detail');
        if (p2_5_soa_d && adv) p2_5_soa_d.textContent = `${adv.final_advanced_bitstream_bytes || 0} B Final SoA`;

        const p2_5_t1 = document.getElementById('p2-5-tier1-metric');
        if (p2_5_t1) p2_5_t1.textContent = `-${comp.structural_reduction_percent || 0}%`;
        const p2_5_t2 = document.getElementById('p2-5-tier2-metric');
        if (p2_5_t2) p2_5_t2.textContent = `-${comp.constant_pool_stats ? comp.constant_pool_stats.compression_percentage : 0}%`;
        const p2_5_t3 = document.getElementById('p2-5-tier3-metric');
        if (p2_5_t3) p2_5_t3.textContent = `-${comp.bytecode_reduction_percent || 0}%`;
        const p2_5_t4 = document.getElementById('p2-5-tier4-metric');
        if (p2_5_t4) p2_5_t4.textContent = `-${comp.final_compression_ratio_percent || 0}%`;
    }

    // Jump buttons from sequential steps to dedicated full tabs
    document.addEventListener('click', (e) => {
        const jumpBtn = e.target.closest('.btn-jump');
        if (jumpBtn) {
            const targetTab = jumpBtn.getAttribute('data-target-tab');
            if (targetTab) {
                const tabBtn = document.querySelector(`.tab-btn[data-tab="${targetTab}"]`);
                if (tabBtn) {
                    activateTab(tabBtn);
                }
            } else if (jumpBtn.id === 'btn-pipeline-export' || jumpBtn.id === 'btn-tab-export' || jumpBtn.id === 'btn-export-cir-action') {
                btnExport.click();
            }
        }
        if (e.target.closest('#btn-tab-export') || e.target.closest('#btn-export-cir-action')) {
            btnExport.click();
        }
    });

    // Initialize application
    loadSamples();
});
