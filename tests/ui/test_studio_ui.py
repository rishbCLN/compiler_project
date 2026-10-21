"""
Headless Playwright UI tests for the IR Compression Studio.

These exercise the real browser->FastAPI round trip against a live uvicorn
server (see the `live_server` fixture in the root conftest.py). They retire the
"not verified live in a browser" gap and guard the cy.resize()/fit() fix and the
server-side pre-SSA CFG snapshot.

Requires:  pip install -r requirements-dev.txt  &&  playwright install chromium
"""

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync.sync_playwright


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        br = p.chromium.launch()
        yield br
        br.close()


@pytest.fixture()
def page(browser, live_server):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(live_server, wait_until="networkidle")
    # Click Run Pipeline and wait for compilation to complete
    pg.click("#btn-compile")
    pg.wait_for_function(
        "() => document.getElementById('compiler-status')"
        ".textContent.trim() === 'Optimized & Compressed'",
        timeout=30000,
    )
    yield pg
    ctx.close()


def _switch_tab(page, data_tab):
    page.click(f'.tab-btn[data-tab="{data_tab}"]')


# ---------------------------------------------------------------- load & compile

def test_initial_page_load_awaits_run_pipeline(browser, live_server):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(live_server, wait_until="networkidle")
    # Editor is loaded with sample code, but has NOT run compilation yet
    assert len(pg.input_value("#source-code").strip()) > 0
    assert pg.text_content("#compiler-status").strip() == "Ready"
    assert pg.text_content("#stat-final-ratio").strip() == "0.0%"
    ctx.close()


def test_default_sample_compiles_overview(page):
    ratio = page.text_content("#stat-final-ratio").strip()
    assert ratio != "0.0%"
    assert "%" in ratio
    # Instruction reduction detail populated.
    assert "Instructions" in page.text_content("#stat-instr-detail")


def test_input_section_dropdown_syncs_and_loads(page):
    # Select sample via the input section dropdown
    page.select_option("#input-sample-select", index=6)
    assert page.text_content("#compiler-status").strip() == "Ready"
    # Ensure header dropdown also synced
    assert page.input_value("#sample-select") == page.input_value("#input-sample-select")
    page.click("#btn-compile")
    page.wait_for_function(
        "() => document.getElementById('compiler-status').textContent.trim() === 'Optimized & Compressed'",
        timeout=30000,
    )


def test_offline_vendor_assets_loaded(page):
    # Globals provided by the vendored libs must be present (proves local load).
    assert page.evaluate("() => typeof window.cytoscape === 'function'")
    assert page.evaluate("() => typeof window.Chart === 'function'")


# ---------------------------------------------------------------- graph render / resize fix

def test_cfg_tab_renders_nodes_with_nonzero_size(page):
    _switch_tab(page, "cfg-tab")
    # Wait for the exposed Cytoscape instance to carry rendered nodes.
    page.wait_for_function(
        "() => window.__cfgViz && window.__cfgViz.cy "
        "&& window.__cfgViz.cy.nodes().length > 0",
        timeout=10000,
    )
    node_count = page.evaluate("() => window.__cfgViz.cy.nodes().length")
    assert node_count > 0
    # The rendered graph must gain real pixel extent -> guards the resize()/fit()
    # fix (the old collapsed-pane bug produced width 0 on first activation). The
    # fit()/resize() runs on a 100ms setTimeout after the tab click, so wait for
    # it to settle rather than racing the deferred relayout.
    page.wait_for_function(
        "() => window.__cfgViz.cy.width() > 0", timeout=10000
    )
    width = page.evaluate("() => window.__cfgViz.cy.width()")
    assert width > 0


def test_cfg_view_modes_rerender(page):
    _switch_tab(page, "cfg-tab")
    page.wait_for_function(
        "() => window.__cfgViz && window.__cfgViz.cy "
        "&& window.__cfgViz.cy.nodes().length > 0",
        timeout=10000,
    )
    for mode in ("ssa", "optimized", "raw"):
        page.check(f'input[name="cfg-view"][value="{mode}"]')
        page.wait_for_function(
            "() => window.__cfgViz.cy.nodes().length > 0", timeout=10000
        )
        assert page.evaluate("() => window.__cfgViz.cy.nodes().length") > 0


def test_ssa_tab_renders_dominator_tree(page):
    _switch_tab(page, "ssa-tab")
    page.wait_for_function(
        "() => window.__domViz && window.__domViz.cy "
        "&& window.__domViz.cy.nodes().length > 0",
        timeout=10000,
    )
    assert page.evaluate("() => window.__domViz.cy.nodes().length") > 0


# ---------------------------------------------------------------- raw CFG snapshot (server fix)

def test_raw_cfg_shows_unoptimized_ir(page):
    # Load sample 4 (dead-code) which contains ghost_var / 999 in the dead branch.
    page.select_option("#sample-select", label="Dead Code Elimination (DCE) & Unreachable Branch Pruning")
    page.click("#btn-compile")
    page.wait_for_function(
        "() => document.getElementById('compiler-status')"
        ".textContent.trim() === 'Optimized & Compressed'",
        timeout=30000,
    )
    raw_text = page.text_content("#raw-tac-code")
    opt_text = page.text_content("#optimized-ir-code")
    assert "999" in raw_text or "ghost_var" in raw_text
    assert "999" not in opt_text and "ghost_var" not in opt_text


# ---------------------------------------------------------------- export

def test_export_downloads_cir(page):
    with page.expect_download(timeout=30000) as dl_info:
        page.click("#btn-export")
    download = dl_info.value
    assert download.suggested_filename.endswith(".cir")


# ---------------------------------------------------------------- Phase 2: UX / metrics

def test_empty_export_shows_toast_not_alert(page):
    # Clear the editor, then attempt export: must raise a non-blocking toast
    # (the old alert() would have blocked and failed this assertion path).
    page.fill("#source-code", "")
    page.click("#btn-export")
    toast = page.wait_for_selector("#toast-container .toast", timeout=5000)
    assert "exporting" in toast.text_content().lower()


def test_advanced_final_bitstream_surfaced(page):
    # The full Structure-of-Arrays bitstream figure (previously computed but not
    # shown) must be rendered in the advanced architecture card.
    bytes_text = page.text_content("#adv-final-bitstream").strip()
    pct_text = page.text_content("#adv-final-percent").strip()
    assert bytes_text.endswith("B") and bytes_text != "0 B"
    assert "%" in pct_text


def test_fifth_chart_bar_is_advanced_soa(page):
    labels = page.evaluate(
        "() => compressionChartInstance "
        "? compressionChartInstance.data.labels : []"
    )
    assert len(labels) == 5
    assert "Advanced SoA" in labels[4]


def test_constant_pool_net_savings_summary(page):
    # The honesty summary must reflect net savings/overhead, not just the gross
    # dedup figure. Default sample 1 should render a non-empty summary.
    summary = page.text_content("#const-pool-summary").strip()
    assert summary != ""
    assert "net" in summary.lower()


# ---------------------------------------------------------------- Phase 3: accessibility

def test_tabs_expose_aria_tab_pattern(page):
    tablist = page.get_by_role("tablist")
    assert tablist.count() == 1
    # Exactly one tab is selected and it is the only one in the tab order.
    selected = page.eval_on_selector_all(
        '.tab-btn',
        "els => els.map(e => e.getAttribute('aria-selected'))",
    )
    assert selected.count("true") == 1
    tabindexes = page.eval_on_selector_all(
        '.tab-btn',
        "els => els.map(e => e.getAttribute('tabindex'))",
    )
    assert tabindexes.count("0") == 1


def test_tabs_keyboard_arrow_navigation(page):
    first = page.query_selector('.tab-btn')
    first.focus()
    page.keyboard.press("ArrowRight")
    # Arrow key moves selection to the first sequential subphase tab (ast-tab / P1.1) and reveals its panel.
    active_id = page.evaluate("() => document.activeElement.getAttribute('data-tab')")
    assert active_id == "ast-tab"
    assert page.get_attribute('#tab-ast-tab', "aria-selected") == "true"
    assert page.is_hidden("#overview-tab")
    assert page.is_visible("#ast-tab")


def test_branch_edges_have_non_color_labels(page):
    # Load the branch-heavy dead-code sample and verify T/F glyphs exist so the
    # true/false meaning is conveyed without relying on color alone.
    page.select_option("#sample-select", label="Dead Code Elimination (DCE) & Unreachable Branch Pruning")
    page.click("#btn-compile")
    page.wait_for_function(
        "() => document.getElementById('compiler-status')"
        ".textContent.trim() === 'Optimized & Compressed'",
        timeout=30000,
    )
    _switch_tab(page, "cfg-tab")
    page.wait_for_function(
        "() => window.__cfgViz && window.__cfgViz.cy "
        "&& window.__cfgViz.cy.edges().length > 0",
        timeout=10000,
    )
    labels = page.evaluate(
        "() => window.__cfgViz.cy.edges().map(e => e.style('label'))"
    )
    assert "T" in labels and "F" in labels


# ---------------------------------------------------------------- Sequential Pipeline Verification

def test_sequential_pipeline_subphases_populated(page):
    # Verify all 12 subphases have their live output boxes populated with real metrics
    subphase_ids = [
        "step-output-1-1",  # Lexical tokens
        "step-output-1-2",  # AST
        "step-output-1-3",  # Raw TAC
        "step-output-1-4",  # Symbols & Constants
        "step-output-1-5",  # CFG Basic Blocks
        "step-output-1-6",  # Dominance IDom
        "step-output-1-7",  # SSA Form
        "step-output-2-1",  # Multi-Pass Optimizer
        "step-output-2-2",  # Binary Bytecode
        "step-output-2-3",  # Canonical Huffman
        "step-output-2-4",  # Columnar SoA
        "step-output-2-5",  # Analytics & Export
    ]

    for sid in subphase_ids:
        text = page.text_content(f"#{sid}").strip()
        assert len(text) > 0, f"Subphase container #{sid} is empty!"
        assert "Run pipeline" not in text, f"Subphase container #{sid} still shows uncompiled placeholder!"

    # Specific subphase content checks
    assert "Total Tokens:" in page.text_content("#step-output-1-1")
    assert "Root Node:" in page.text_content("#step-output-1-2")
    assert "Raw TAC Instructions:" in page.text_content("#step-output-1-3")
    assert "Symbols Minified:" in page.text_content("#step-output-1-4")
    assert "Basic Blocks:" in page.text_content("#step-output-1-5")
    assert "Dominator Tree Nodes:" in page.text_content("#step-output-1-6")
    assert "Phi" in page.text_content("#step-output-1-7")
    assert "Constant Folds:" in page.text_content("#step-output-2-1")
    assert "Bytecode Output:" in page.text_content("#step-output-2-2")
    assert "Single-Stream Bitstream:" in page.text_content("#step-output-2-3")
    assert "Final SoA Bitstream:" in page.text_content("#step-output-2-4")
    assert "Lossless Decompression Integrity" in page.text_content("#step-output-2-5") or "Verified" in page.text_content("#step-output-2-5")


def test_sequential_pipeline_filter_buttons(page):
    # Test Phase 1 filter hides Phase 2 cards
    page.click('.filter-btn[data-filter="phase1"]')
    assert page.is_visible("#step-1-1")
    assert page.is_visible("#step-1-7")
    assert page.is_hidden("#step-2-1")
    assert page.is_hidden("#step-2-5")

    # Test Phase 2 filter hides Phase 1 cards
    page.click('.filter-btn[data-filter="phase2"]')
    assert page.is_hidden("#step-1-1")
    assert page.is_hidden("#step-1-7")
    assert page.is_visible("#step-2-1")
    assert page.is_visible("#step-2-5")

    # Test All filter shows all cards
    page.click('.filter-btn[data-filter="all"]')
    assert page.is_visible("#step-1-1")
    assert page.is_visible("#step-2-1")


def test_sequential_pipeline_jump_button(page):
    # Clicking jump button on CFG step card switches to CFG tab
    jump_btn = page.query_selector('#step-1-5 .btn-jump')
    assert jump_btn is not None
    jump_btn.click()
    page.wait_for_selector("#cfg-tab.active", timeout=5000)
    assert page.is_visible("#cfg-tab")
    assert page.is_hidden("#overview-tab")

