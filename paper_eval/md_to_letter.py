"""Converts paper/response_to_reviewers.md to LaTeX (paper/response_to_reviewers.tex) for a PDF build:
    python3 paper_eval/md_to_letter.py paper/response_to_reviewers.md paper/response_to_reviewers.tex
    cd paper && tectonic response_to_reviewers.tex     (or xelatex; the letter uses fontspec)
Handles only the Markdown this letter uses: headings, bullets, bold, italics, code, rules."""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")

def esc(t):
    out, parts = [], re.split(r"(`[^`]*`)", t)
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            code = part[1:-1]
            code = code.replace("\\", r"\textbackslash{}")
            for a, b in [("_", r"\_"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}")]:
                code = code.replace(a, b)
            code = code.replace(r"\textbackslash\{\}", r"\textbackslash{}")
            out.append(r"\texttt{" + code + "}")
            continue
        s = part
        for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"),
                     ("$", r"\$"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")]:
            s = s.replace(a, b)
        s = s.replace(r"\textbackslash{}", r"\textbackslash{}")
        s = s.replace("×", r"$\times$").replace("φ", r"$\phi$").replace("–", "--")
        s = s.replace("⟨", r"$\langle$").replace("⟩", r"$\rangle$")
        s = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", s)
        s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"\\emph{\1}", s)
        s = re.sub(r'"([^"]*)"', r"``\1''", s)
        out.append(s)
    return "".join(out)

body, depth_stack, para = [], [], []

def flush_para():
    if para:
        body.append(esc(" ".join(para)).replace(" BRKMARK", r" \\") + "\n")
        para.clear()

def close_lists(to=0):
    while len(depth_stack) > to:
        depth_stack.pop()
        body.append(r"\end{itemize}")

for line in lines:
    m = re.match(r"^( *)\* (.*)$", line)
    if line.startswith("# "):
        flush_para(); close_lists()
        body.append(r"\begin{center}{\Large\bfseries " + esc(line[2:]) + r"}\end{center}")
    elif line.startswith("### "):
        flush_para(); close_lists()
        body.append(r"\subsection*{" + esc(line[4:]) + "}")
    elif line.strip() == "---":
        flush_para(); close_lists()
        body.append(r"\medskip\hrule\medskip")
    elif m:
        flush_para()
        level = len(m.group(1)) // 2 + 1
        while len(depth_stack) < level:
            depth_stack.append(level); body.append(r"\begin{itemize}")
        close_lists(level)
        body.append(r"\item " + esc(m.group(2)))
    elif line.strip() == "":
        flush_para()
        if depth_stack:
            pass
    elif depth_stack and line.startswith("  "):
        body[-1] += " " + esc(line.strip())
    else:
        close_lists()
        if line.endswith("  "):
            para.append(line.strip() + " BRKMARK")
        else:
            para.append(line.strip())
flush_para(); close_lists()

tex = r"""%% Generated from response_to_reviewers.md -- edit the Markdown file and regenerate.
\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{fontspec}
\setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, BoldFont=*-bold, ItalicFont=*-italic, BoldItalicFont=*-bolditalic]
\setmonofont{texgyrecursor}[Extension=.otf, Scale=0.95, UprightFont=*-regular, BoldFont=*-bold, ItalicFont=*-italic, BoldItalicFont=*-bolditalic]
\usepackage{parskip}
\usepackage{enumitem}
\setlist{itemsep=2pt,topsep=3pt}
\sloppy
\begin{document}
""" + "\n".join(body) + "\n\\end{document}\n"
open(dst, "w", encoding="utf-8").write(tex)
