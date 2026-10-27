"""
Seeded generator of random C-Lite programs for differential testing,
ablation and scaling.

Every program declares integer variables, assigns them expressions over
+, -, *, / and %, and nests if/else statements and counter-controlled loops.
Every variable is initialized before use and has a name that is unique in the
whole program (the front end does not rename shadowed variables), divisors are
nonzero literals, loop counters are never assigned in their loop body, loops
run at most four times and nesting is at most three levels deep, so every
program terminates without a run-time error.

With `with_input=True` some initializers read a value with input() instead of
using an expression, so those values are unknown at compile time.
"""

import random
from typing import List, Set


class ProgramGenerator:
    def __init__(self, seed: int, with_input: bool = False, max_depth: int = 3):
        self.rng = random.Random(seed)
        self.with_input = with_input
        self.max_depth = max_depth
        self.counter = 0
        self.inputs_used = 0
        self.readonly: Set[str] = set()
        self.lines: List[str] = []

    def fresh(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}{self.counter}"

    def expr(self, scope: List[str], depth: int = 0) -> str:
        rng = self.rng
        if depth >= 2 or rng.random() < 0.35:
            if scope and rng.random() < 0.7:
                return rng.choice(scope)
            return str(rng.randint(0, 20))
        op = rng.choice(["+", "-", "*", "/", "%", "+", "-"])
        left = self.expr(scope, depth + 1)
        if op in ("/", "%"):
            right = str(rng.choice([2, 3, 5, 7, 10, 100, 1000]))
        else:
            right = self.expr(scope, depth + 1)
        return f"({left} {op} {right})"

    def cond(self, scope: List[str]) -> str:
        op = self.rng.choice(["<", "<=", ">", ">=", "==", "!="])
        return f"{self.expr(scope, 1)} {op} {self.expr(scope, 1)}"

    def initializer(self, scope: List[str]) -> str:
        if self.with_input and self.rng.random() < 0.3:
            self.inputs_used += 1
            return "input()"
        return self.expr(scope)

    def statement(self, scope: List[str], depth: int, indent: str) -> None:
        rng = self.rng
        kinds = ["decl", "decl", "assign", "assign", "print"]
        if depth < self.max_depth:
            kinds += ["if", "loop"]
        kind = rng.choice(kinds)
        writable = [v for v in scope if v not in self.readonly]
        if kind == "assign" and not writable:
            kind = "decl"

        if kind == "decl":
            name = self.fresh("v")
            self.lines.append(f"{indent}int {name} = {self.initializer(scope)};")
            scope.append(name)
        elif kind == "assign":
            name = rng.choice(writable)
            self.lines.append(f"{indent}{name} = {self.expr(scope)};")
        elif kind == "print":
            self.lines.append(f"{indent}print({self.expr(scope)});")
        elif kind == "if":
            self.lines.append(f"{indent}if ({self.cond(scope)}) {{")
            self.block(list(scope), depth + 1, indent + "    ")
            if rng.random() < 0.6:
                self.lines.append(f"{indent}}} else {{")
                self.block(list(scope), depth + 1, indent + "    ")
            self.lines.append(f"{indent}}}")
        else:
            counter = self.fresh("i")
            bound = rng.randint(1, 4)
            self.readonly.add(counter)
            if rng.random() < 0.5:
                self.lines.append(f"{indent}for (int {counter} = 0; {counter} < {bound}; "
                                  f"{counter} = {counter} + 1) {{")
                self.block(list(scope) + [counter], depth + 1, indent + "    ")
                self.lines.append(f"{indent}}}")
                self.readonly.discard(counter)
            else:
                self.lines.append(f"{indent}int {counter} = 0;")
                self.lines.append(f"{indent}while ({counter} < {bound}) {{")
                self.block(list(scope) + [counter], depth + 1, indent + "    ")
                self.lines.append(f"{indent}    {counter} = {counter} + 1;")
                self.lines.append(f"{indent}}}")
                self.readonly.discard(counter)
                scope.append(counter)

    def block(self, scope: List[str], depth: int, indent: str) -> None:
        for _ in range(self.rng.randint(1, 4)):
            self.statement(scope, depth, indent)

    def program(self, n_statements: int) -> str:
        scope: List[str] = []
        for _ in range(n_statements):
            self.statement(scope, 1, "")
        for name in scope[-3:]:
            self.lines.append(f"print({name});")
        return "\n".join(self.lines) + "\n"


def generate(seed: int, n_statements: int, with_input: bool = False) -> str:
    return ProgramGenerator(seed, with_input=with_input).program(n_statements)
