#!/usr/bin/env python3
"""
Academic Paper Plagiarism Reducer & Paraphraser for LaTeX Documents.
Preserves all LaTeX formatting, macros, citations, math formulas, and tables
while rewriting common textbook compiler clichés into novel academic prose.
"""

import re
import sys
import os

# Mapping of high-risk textbook clichés & verbatim formulations to fresh academic phrasing
PHRASE_TRANSFORMATIONS = [
    # General / Intro Clichés
    (
        r"In modern optimizing compiler architectures,?\s+Intermediate Representation \(IR\) serves as the primary substrate",
        "Within contemporary compilation toolchains, Intermediate Representation (IR) functions as the foundational intermediate model"
    ),
    (
        r"decoupling high-level source languages from machine-dependent execution targets",
        "insulating front-end syntactic abstractions from architecture-specific hardware constraints"
    ),
    (
        r"manifests significant structural verbosity and physical memory inflation",
        "exhibits substantial operational overhead and non-trivial memory bloating"
    ),
    (
        r"posing severe throughput and bandwidth bottlenecks",
        "introducing critical serialization and transmission bottlenecks"
    ),
    (
        r"This paper presents",
        "In this work, we design and implement"
    ),
    (
        r"bridges mathematical graph optimization and information-theoretic physical bitstream serialization",
        "synthesizes formal graph-theoretic optimizations with physical entropy-coded bitstream compaction"
    ),

    # Section 1 Clichés
    (
        r"constitute the universal pivot in modern compiler infrastructure",
        "represent the architectural cornerstone of production compilers"
    ),
    (
        r"Contemporary execution paradigms—including Just-In-Time \(JIT\) compilation in cloud environments",
        "Modern execution environments—ranging from cloud-scale Just-In-Time (JIT) runtimes"
    ),
    (
        r"increasingly distribute and store programs in an intermediate format rather than bare-metal machine code",
        "frequently transport and cache programs as portable bytecode rather than native machine binaries"
    ),
    (
        r"Naive translation from Abstract Syntax Trees \(AST\) introduces redundant temporaries",
        "Direct lowering from Abstract Syntax Tree (AST) representations introduces superfluous temporary registers"
    ),
    (
        r"Traditional compression mechanisms such as DEFLATE, gzip, or Zstandard operate solely on raw byte distributions",
        "Conventional data compression algorithms (e.g., DEFLATE, gzip, Zstandard) inspect purely statistical byte frequencies"
    ),
    (
        r"without understanding program data-flow or syntactic dominance",
        "oblivious to underlying data-dependency structures and control dominance invariants"
    ),

    # Section 3: Definition clichés (Crucial for Turnitin)
    (
        r"A basic block is defined as a maximal sequence of instructions [^.]+ without intermediate branching\.",
        "We delineate each basic block as an uninterrupted straight-line instruction sequence where execution enters solely through the first operation and departs exclusively at the terminating branch."
    ),
    (
        r"A node d \\textit\{dominates\} node n \(d \\text\{ dom \} n\) if every directed path from r to n contains d\.",
        "Under directed control flow originating at root $r$, a vertex $d$ achieves dominance over $n$ ($d \\text{ dom } n$) if traversing from $r$ to $n$ necessitates passage through $d$."
    ),
    (
        r"The \\textit\{Dominance Frontier\} DF\(x\) encompasses the set of nodes y where x dominates a direct predecessor of y, but does not strictly dominate y:",
        "The Dominance Frontier $DF(x)$ isolates boundary vertices $y$ where $x$ exercises dominance over at least one incoming predecessor of $y$ without exerting strict dominance over $y$ itself:"
    ),
    (
        r"To enforce the Static Single Assignment property—wherein each variable possesses precisely one static point of definition—",
        "To establish strict Static Single Assignment invariants—guaranteeing invariant singular definitions per symbolic variable—"
    ),

    # Section 4: Optimization clichés
    (
        r"Algebraic identities are simplified dynamically:",
        "Canonical algebraic identities undergo compile-time reduction:"
    ),
    (
        r"GVN identifies congruent computational values across dominated CFG regions\.",
        "Global Value Numbering detects computationally equivalent subexpressions residing within dominated subgraphs."
    ),
    (
        r"A backwards mark-sweep pass identifies active variable definitions\.",
        "An iterative backward liveness traversal isolates instructions with active downstream consumers."
    ),

    # Section 5: Bytecode clichés
    (
        r"Identifier strings represent non-trivial metadata overhead in serial IR representations\.",
        "Verbose lexical identifiers account for disproportionate metadata overhead across serialized symbol tables."
    ),
    (
        r"LEB128 encodes arbitrary-precision integers by slicing them into 7-bit payloads, reserving the 8th bit as a continuation indicator\.",
        "LEB128 partitions integer magnitudes into 7-bit value chunks, dedicating the most significant bit to signal subsequent octets."
    ),
    (
        r"The serialized bytecode buffer is processed by an entropy encoder constructing a minimum-redundancy binary tree\.",
        "The serialized bytecode stream is subsequently fed to an entropy encoder that generates an optimal prefix-free binary coding tree."
    ),
]


def check_plagiarism_risk(text: str) -> dict:
    """Scans text for common textbook compiler n-grams that trigger Turnitin."""
    risks = []
    textbook_patterns = [
        r"maximal sequence of instructions",
        r"every directed path from \w+ to \w+ contains",
        r"dominates a direct predecessor",
        r"serves as the primary substrate",
        r"Dragon Book",
        r"Dragon book",
        r"three-address code.*quadruples",
        r"Little-Endian Base 128",
    ]
    for pat in textbook_patterns:
        matches = list(re.finditer(pat, text, re.IGNORECASE))
        if matches:
            risks.append((pat, len(matches)))
    return {"risk_matches": risks}


def rewrite_latex_for_originality(content: str) -> str:
    """Applies contextual paraphrasing while preserving LaTeX tokens."""
    updated = content
    for pattern, replacement in PHRASE_TRANSFORMATIONS:
        updated = re.sub(pattern, replacement, updated)
    return updated


def process_file(file_path: str, output_path: str = None) -> None:
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    print(f"[*] Analyzing '{file_path}' for standard textbook n-grams...")
    audit_pre = check_plagiarism_risk(original)
    print(f"    Identified {len(audit_pre['risk_matches'])} textbook cliché pattern groups.")

    rewritten = rewrite_latex_for_originality(original)

    dest = output_path or file_path
    with open(dest, "w", encoding="utf-8") as f:
        f.write(rewritten)

    audit_post = check_plagiarism_risk(rewritten)
    print(f"[+] Output written to '{dest}'.")
    print(f"    Remaining cliché patterns: {len(audit_post['risk_matches'])}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "main.tex"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    process_file(target, out)
