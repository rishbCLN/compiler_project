"""
Static checks of the manuscript that do not need a LaTeX installation:
every number macro (\\n...) is defined in tables/numbers.tex, every table-row
file and figure exists, every \\ref and \\eqref has a \\label, every \\cite has
a \\bibitem and every \\bibitem is cited, and braces are balanced.

    python3 paper_eval/check_paper.py        (exit status 1 on any problem)
"""

import os
import re
import sys

from common import PAPER

MAIN = os.path.join(PAPER, "ir_compaction_access.tex")


def main():
    with open(MAIN, encoding="utf-8") as f:
        tex = f.read()
    body = re.sub(r"(?<!\\)%.*", "", tex)
    with open(os.path.join(PAPER, "tables", "numbers.tex"), encoding="utf-8") as f:
        defined = set(re.findall(r"\\newcommand\{\\(n[A-Za-z]+)\}", f.read()))
    problems = []

    used = set(re.findall(r"\\(n[a-z][A-Za-z]*)", body))
    # Standard LaTeX commands that also start with n.
    used -= {"newcommand", "newif", "noindent", "newtheorem", "nolinkurl", "neq", "notin", "newline",
             "nabla", "nu", "ni", "not", "neg", "newpage", "nonumber", "noalign"}
    for name in sorted(used - defined):
        problems.append(f"undefined number macro \\{name}")

    for path in re.findall(r"\\rowsfrom\{([^}]+)\}", body):
        if not os.path.exists(os.path.join(PAPER, path)):
            problems.append(f"missing table rows {path}")
    for path in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body):
        if not os.path.exists(os.path.join(PAPER, path)):
            problems.append(f"missing figure {path}")

    labels = set(re.findall(r"\\label\{([^}]+)\}", body))
    for ref in set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", body)):
        if ref not in labels:
            problems.append(f"undefined reference {ref}")

    cited = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", body):
        cited.update(k.strip() for k in group.split(","))
    items = re.findall(r"\\bibitem\{([^}]+)\}", body)
    for key in sorted(cited - set(items)):
        problems.append(f"citation without bibitem: {key}")
    for key in sorted(set(items) - cited):
        problems.append(f"bibitem never cited: {key}")
    if len(items) != len(set(items)):
        problems.append("duplicate bibitem keys")

    depth = 0
    for ch in re.sub(r"\\[{}]", "", body):
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            problems.append("unbalanced braces: '}' without '{'")
            break
    if depth > 0:
        problems.append(f"unbalanced braces: {depth} unclosed '{{'")

    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(used & defined)} number macros, {len(labels)} labels, {len(items)} references checked; "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
