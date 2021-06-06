"""Search all given paths recursively for localised string calls."""
import sys
import argparse
import ast
import json
import pathlib


def get_func_name(thing: ast.AST) -> str:
    """Get the name of a function from a Call node."""
    if isinstance(thing, ast.Name):
        return thing.id

    elif isinstance(thing, ast.Attribute):
        return get_func_name(thing.value)

    else:
        return ""


def get_arg(call: ast.Call) -> str:
    """Extract the argument string to the translate function."""
    if len(call.args) > 1:
        print("??? > 1 args", call.args, file=sys.stderr)

    arg = call.args[0]
    if isinstance(arg, ast.Constant):
        return arg.value
    else:
        return f'Unknown! {type(arg)=} {ast.dump(arg)} ||| {ast.unparse(arg)}'


def find_calls_in_stmt(statement: ast.AST) -> list[ast.Call]:
    """Recursively find ast.Calls in a statement."""
    out = []
    for n in ast.iter_child_nodes(statement):
        out.extend(find_calls_in_stmt(n))
    if isinstance(statement, ast.Call) and get_func_name(statement.func) == "_":
        out.append(statement)

    return out


def scan_file(path: pathlib.Path) -> list[ast.Call]:
    """Scan a file for ast.Calls."""
    data = path.read_text()
    parsed = ast.parse(data)
    out: list[ast.Call] = []

    for statement in parsed.body:
        out.extend(find_calls_in_stmt(statement))

    out.sort(key=lambda c: c.lineno)
    return out


def scan_directory(path: pathlib.Path, skip: list[pathlib.Path] = None) -> dict[pathlib.Path, list[ast.Call]]:
    """
    Scan a directory for expected callsites.

    :param path: path to scan
    :param skip: paths to skip, if any, defaults to None
    """
    out = {}
    for thing in path.iterdir():
        if skip is not None and any(s.name == thing.name for s in skip):
            continue

        if thing.is_file():
            if not thing.name.endswith('.py'):
                continue

            out[thing] = scan_file(thing)

        elif thing.is_dir():
            out |= scan_directory(thing)

        else:
            raise ValueError(type(thing), thing)

    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", help="Directory to search from", default=".")
    parser.add_argument("--ignore", action='append', help="directories to ignore", default=["venv", ".git"])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--json', action='store_true', help='JSON output')
    group.add_argument('--lang', action='store_true', help='lang file outpot')

    args = parser.parse_args()

    directory = pathlib.Path(args.directory)
    res = scan_directory(directory, [pathlib.Path(p) for p in args.ignore])

    if args.json:
        to_print = json.dumps({
            str(path): [{
                "string": get_arg(c),
                "reconstructed": ast.unparse(c),
                "start_line": c.lineno,
                "start_offset": c.col_offset,
                "end_line": c.end_lineno,
                "end_offset": c.end_col_offset,
            } for c in calls] for (path, calls) in res.items() if len(calls) > 0
        }, indent=2)

        print(to_print)

    elif args.lang:
        for path, calls in res.items():
            for c in calls:
                arg = json.dumps(get_arg(c))
                print(f'/* {path.name}:{c.lineno}({c.col_offset}):{c.end_lineno}({c.end_col_offset}) */')
                print(f'{arg} = {arg};')
                print()

    else:
        for path, calls in res.items():
            if len(calls) == 0:
                continue

            print(path)
            for c in calls:
                print(
                    f"    {c.lineno:4d}({c.col_offset:3d}):{c.end_lineno:4d}({c.end_col_offset:3d})\t", ast.unparse(c)
                )

            print()
