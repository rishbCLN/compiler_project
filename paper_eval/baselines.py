"""
Existing compact program formats for the ten kernels (K1-K10):

  LLVM bitcode   clang -O2 -c -emit-llvm (and -Oz), no debug information
  Java class     the kernel translated mechanically to Java, javac -g:none;
                 the sizes of all class files of the program are added up

Each tool is also run on an empty program (main returning 0), whose size is
the fixed per-file overhead of the format. Every kernel is compiled natively
with clang and run on its input; the printed numbers are the reference for
the C-Lite pipeline, and the Java translation must print the same numbers.
WebAssembly is compared by design only, because the installed clang has no
wasm32 target.

The script needs clang, javac and java; results are cached in
results/baselines.json so the tables can be rebuilt without them.

    python3 paper_eval/baselines.py          -> results/baselines.json
"""

import os
import re
import shutil
import subprocess
import tempfile

from common import KERNELS, load, benchmark_path, save, deflate_raw, clir
from paper_eval.pipeline import compile_source
from paper_eval.interp import run_tac, observe

EMPTY_C = "int main() {\n    return 0;\n}\n"


def tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return (out.stdout or out.stderr).splitlines()[0].strip()
    except Exception:
        return None


def to_java(c_source: str, class_name: str) -> str:
    """Mechanical C-to-Java translation for the kernels' subset of C: functions
    become static methods, scanf reads with a Scanner, printf("%d\\n", e)
    prints e, and main's final `return 0;` becomes `return;`."""
    lines = []
    for line in c_source.splitlines():
        if line.startswith("#include") or line.lstrip().startswith("//"):
            continue
        m = re.match(r"^int (\w+)\((.*)\) \{$", line)
        if m and m.group(1) == "main":
            lines.append("    public static void main(String[] args) {")
            lines.append("        java.util.Scanner in = new java.util.Scanner(System.in);")
            continue
        if m:
            lines.append(f"    static int {m.group(1)}({m.group(2)}) {{")
            continue
        s = re.match(r"^(\s*)scanf\(\"[^\"]*\"((?:, &\w+)+)\);$", line)
        if s:
            for name in re.findall(r"&(\w+)", s.group(2)):
                lines.append(f"{s.group(1)}{name} = in.nextInt();")
            continue
        p = re.match(r'^(\s*)printf\("%d\\n", (.*)\);$', line)
        if p:
            lines.append(f"{p.group(1)}System.out.println({p.group(2)});")
            continue
        lines.append("    " + line if line else line)
    body = "\n".join(lines)
    # The kernels declare scanf targets without an initializer; Java needs one.
    body = re.sub(r"^(\s*)int (\w+);$", r"\1int \2 = 0;", body, flags=re.M)
    # main's `return 0;` is its last statement.
    idx = body.rfind("return 0;")
    body = body[:idx] + "return;" + body[idx + len("return 0;"):]
    return f"public class {class_name} {{\n{body}\n}}\n"


def numbers(text: str):
    return [int(x) for x in text.split()]


def run_native(path, inputs, work):
    exe = os.path.join(work, "native")
    subprocess.run(["clang", "-O0", "-w", "-o", exe, path], check=True)
    out = subprocess.run([exe], input=" ".join(map(str, inputs)), capture_output=True, text=True, check=True)
    return numbers(out.stdout)


def bitcode_size(path, opt, work):
    bc = os.path.join(work, f"k{opt}.bc")
    subprocess.run(["clang", f"-{opt}", "-g0", "-c", "-emit-llvm", "-w", "-o", bc, path], check=True)
    with open(bc, "rb") as f:
        data = f.read()
    return len(data), len(deflate_raw(data))


def java_size(c_source, inputs, work, name):
    d = os.path.join(work, name)
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, f"{name}.java")
    with open(src, "w") as f:
        f.write(to_java(c_source, name))
    subprocess.run(["javac", "-g:none", "-d", d, src], check=True)
    classes = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".class")]
    data = b"".join(open(p, "rb").read() for p in sorted(classes))
    out = None
    if inputs is not None:
        run = subprocess.run(["java", "-cp", d, name], input=" ".join(map(str, inputs)),
                             capture_output=True, text=True, check=True)
        out = numbers(run.stdout)
    return len(data), len(deflate_raw(data)), out


def main():
    if not (shutil.which("clang") and shutil.which("javac") and shutil.which("java")):
        print("clang, javac and java are needed; keeping results/baselines.json")
        return
    rows = []
    with tempfile.TemporaryDirectory() as work:
        empty_c = os.path.join(work, "empty.c")
        with open(empty_c, "w") as f:
            f.write(EMPTY_C)
        empty = {"bitcode_O2": bitcode_size(empty_c, "O2", work)[0],
                 "bitcode_Oz": bitcode_size(empty_c, "Oz", work)[0],
                 "java_class": java_size(EMPTY_C, None, work, "Empty")[0]}
        empty_c_lite = compile_source(EMPTY_C)
        empty["clir"] = len(clir(empty_c_lite)[0])
        for bid, fname, _ in KERNELS:
            src, inputs = load(fname)
            path = benchmark_path(fname)
            native = run_native(path, inputs, work)
            c = compile_source(src)
            ours = observe(run_tac, c.raw_module(), inputs)
            ours_numbers = [v for v in ours[1][:-1] if isinstance(v, int)] if ours[0] == "ok" else None
            bc2, bc2_deflate = bitcode_size(path, "O2", work)
            bcz, bcz_deflate = bitcode_size(path, "Oz", work)
            jav, jav_deflate, java_out = java_size(src, inputs, work, f"K{bid[1:]}")
            row = {"id": bid, "clir": len(clir(c)[0]),
                   "bitcode_O2": bc2, "bitcode_O2_deflate": bc2_deflate,
                   "bitcode_Oz": bcz, "bitcode_Oz_deflate": bcz_deflate,
                   "java_class": jav, "java_class_deflate": jav_deflate,
                   "c_lite_matches_native": ours_numbers == native,
                   "java_matches_native": java_out == native}
            print(row)
            rows.append(row)
    save("baselines.json", {
        "tools": {"clang": tool_version(["clang", "--version"]),
                  "javac": tool_version(["javac", "-version"]),
                  "java": tool_version(["java", "-version"])},
        "empty_program": empty,
        "kernels": rows,
    })


if __name__ == "__main__":
    main()
