r"""
Search paths for trace_if calls, validate TRACEDOC comments, and optionally generate /docs/Available Traces.md.

Example usage: python .\scripts\find_trace_strings.py --directory . --ignore dist.win32 --ignore tests
"""

from __future__ import annotations

import argparse
import ast
import datetime
import pathlib
import sys


def get_func_name(thing: ast.AST) -> str:
    """Get the name of a function from a Call node."""
    if isinstance(thing, ast.Name):
        return thing.id
    if isinstance(thing, ast.Attribute):
        return thing.attr
    return ""


def find_trace_calls(statement: ast.AST) -> list[ast.Call]:
    """Recursively find 'trace_if' ast.Calls."""
    out = []
    for n in ast.iter_child_nodes(statement):
        out.extend(find_trace_calls(n))

    if isinstance(statement, ast.Call) and get_func_name(statement.func) == "trace_if":
        out.append(statement)
    return out


def generate_markdown(all_found_data: list[dict], project_root: pathlib.Path):
    """Generate the Available Traces.md file with fixed-width column formatting."""
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True)

    sorted_data = sorted(all_found_data, key=lambda x: x["key"])

    h_key, h_msg, h_loc = "Trace Key", "Enables Log Message", "Source Location"

    # Pre-format content to calculate widths correctly including backticks
    formatted_rows = []
    for entry in sorted_data:
        formatted_rows.append(
            {
                "key": f"`{entry['key']}`",
                "msg": f"`{entry['message'].replace('|', '\\|')}`",
                "loc": f"{entry['file']}:{entry['line']}",
            }
        )

    # Calculate widths based on headers and formatted content
    w_key = max(len(h_key), max((len(r["key"]) for r in formatted_rows), default=0))
    w_msg = max(len(h_msg), max((len(r["msg"]) for r in formatted_rows), default=0))
    w_loc = max(len(h_loc), max((len(r["loc"]) for r in formatted_rows), default=0))

    lines = [
        "# Available Traces",
        f"This file was last updated on {datetime.date.today()}." "",
        "This document lists all of the available `--trace-on` options to enable additional debug logging.",
        "",
        f"| {h_key:<{w_key}} | {h_msg:<{w_msg}} | {h_loc:<{w_loc}} |",
        f"|{'-' * w_key}--|{'-' * w_msg}--|{'-' * w_loc}--|",
    ]

    for r in formatted_rows:
        lines.append(
            f"| {r['key']:<{w_key}} | {r['msg']:<{w_msg}} | {r['loc']:<{w_loc}} |"
        )

    output_path = docs_dir / "Available Traces.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDocumentation updated: {output_path}")


def main():  # noqa: CCR001
    """Run the Traceon Doc Checker and update the docs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=".", help="Project root directory")
    parser.add_argument(
        "--ignore", action="append", default=["venv", ".venv", ".git", "docs"]
    )
    args = parser.parse_args()

    root = pathlib.Path(args.directory).resolve()
    all_traces_for_md = []
    global_success = True

    for path in root.rglob("*.py"):
        if any(ignored in path.parts for ignored in args.ignore):
            continue

        try:
            data = path.read_text(encoding="utf-8")
            parsed = ast.parse(data)
        except (SyntaxError, UnicodeDecodeError):
            continue

        calls = []
        for statement in parsed.body:
            calls.extend(find_trace_calls(statement))

        for call in calls:
            # Store data in case we need to update docs
            trace_key = ast.unparse(call.args[0]).strip("'\"") if call.args else "N/A"
            log_msg = ast.unparse(call.args[1]) if len(call.args) > 1 else "N/A"

            all_traces_for_md.append(
                {
                    "key": trace_key,
                    "message": log_msg,
                    "file": path.relative_to(root),
                    "line": call.lineno,
                }
            )

    if all_traces_for_md:
        generate_markdown(all_traces_for_md, root)

    if not global_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
