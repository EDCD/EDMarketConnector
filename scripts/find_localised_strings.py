"""Search all given paths recursively for localised string calls."""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import pathlib
import re
import sys


def get_func_name(thing: ast.AST) -> str:
    """Get the name of a function from a Call node."""
    if isinstance(thing, ast.Name):
        return thing.id

    if isinstance(thing, ast.Attribute):
        return get_func_name(thing.value)
    return ""


def get_arg(call: ast.Call) -> str:
    """Extract the argument string to the translate function."""
    if len(call.args) > 1:
        print("??? > 1 args", call.args, file=sys.stderr)

    arg = call.args[0]
    if isinstance(arg, ast.Constant):
        return str(arg.value)
    if isinstance(arg, ast.Name):
        return f"VARIABLE! CHECK CODE! {arg.id}"
    return f"Unknown! {type(arg)=} {ast.dump(arg)} ||| {ast.unparse(arg)}"


def find_calls_in_stmt(statement: ast.AST) -> list[ast.Call]:
    """Recursively find ast.Calls in a statement."""
    out = []
    for n in ast.iter_child_nodes(statement):
        out.extend(find_calls_in_stmt(n))
    if isinstance(statement, ast.Call) and get_func_name(statement.func) in (
        "tr",
        "translations",
    ):
        if (
            ast.unparse(statement).find(".tl") != -1
            or ast.unparse(statement).find("translate") != -1
        ):
            out.append(statement)
    return out


"""
Regular expressions for finding comments.

COMMENT_SAME_LINE_RE is for an in-line comment on the end of code.
COMMENT_OWN_LINE_RE is for a comment on its own line.

The difference is necessary in order to tell if a 'above' LANG comment is for
its own line (SAME_LINE), or meant to be for this following line (OWN_LINE).
"""
COMMENT_SAME_LINE_RE = re.compile(r"^.*(#.*)$")
COMMENT_OWN_LINE_RE = re.compile(r"^\s*?(#.*)$")


def _extract_lang_comment(line: str, pattern: re.Pattern, file: pathlib.Path,
                          lineno: int) -> tuple[str | None, str | None]:
    """Attempt to extract a LANG comment from a line using a given regex pattern."""
    match = pattern.match(line)
    if match:
        comment = match.group(1).strip()
        if comment.startswith("# LANG:"):
            return comment.replace("# LANG:", "").strip(), None
        return None, f"Unknown comment for {file}:{lineno} {line}"
    return None, None


def extract_comments(call: ast.Call, lines: list[str], file: pathlib.Path) -> str | None:
    """
    Extract comments from source code based on the given call.

    This returns comments on the same line as the call preferentially to comments above.
    All comments must be prefixed with LANG, ie `# LANG: `

    :param call: The call node to look for comments around.
    :param lines: The file that the call node came from, as a list of strings where each string is a line.
    :param file: The path to the file this call node came from
    :return: The first comment that matches the rules, or None
    """
    out: str | None = None
    above = call.lineno - 2
    current = call.lineno - 1

    above_line = lines[above].strip() if len(lines) >= above else None
    above_comment: str | None = None
    current_line = lines[current].strip()
    current_comment: str | None = None
    bad_comment: str | None = None

    if above_line:
        above_comment, bad_comment = _extract_lang_comment(above_line, COMMENT_OWN_LINE_RE, file, call.lineno)

    if current_line:
        current_comment, bad_comment = _extract_lang_comment(current_line, COMMENT_SAME_LINE_RE, file, call.lineno)

    if current_comment is not None:
        out = current_comment
    elif above_comment is not None:
        out = above_comment
    elif bad_comment is not None:
        print(bad_comment, file=sys.stderr)

    if out is None:
        print(f"No comment for {file}:{call.lineno} {current_line}", file=sys.stderr)
    return out


def scan_file(path: pathlib.Path) -> list[ast.Call]:
    """Scan a file for ast.Calls."""
    data = path.read_text(encoding="utf-8")
    lines = data.splitlines()
    parsed = ast.parse(data)
    out: list[ast.Call] = []

    for statement in parsed.body:
        out.extend(find_calls_in_stmt(statement))

    # see if we can extract any comments
    for call in out:
        setattr(call, "comment", extract_comments(call, lines, path))

    out.sort(key=lambda c: c.lineno)
    return out


def scan_directory(
    path: pathlib.Path, skip: list[pathlib.Path] | None = None
) -> dict[pathlib.Path, list[ast.Call]]:
    """
    Scan a directory for expected callsites.

    :param path: path to scan
    :param skip: paths to skip, if any, defaults to None
    """
    if skip is None:
        skip = []
    out = {}
    for thing in path.iterdir():
        if any(same_path.name == thing.name for same_path in skip):
            continue

        if thing.is_file() and thing.suffix == ".py":
            out[thing] = scan_file(thing)
        elif thing.is_dir():
            out.update(scan_directory(thing, skip))

    return out


def parse_template(path) -> set[str]:
    """
    Parse a lang.template file.

    The regexp this uses was extracted from l10n.py.

    :param path: The path to the lang file
    """
    lang_re = re.compile(r'\s*"([^"]+)"\s*=\s*"([^"]+)"\s*;\s*$')
    out = set()
    with open(path, encoding="utf-8") as file:
        for line in file:
            match = lang_re.match(line.strip())
            if match and match.group(1) != "!Language":
                out.add(match.group(1))

    return out


@dataclasses.dataclass
class FileLocation:
    """FileLocation is the location of a given string in a file."""

    path: pathlib.Path
    line_start: int
    line_start_col: int
    line_end: int | None
    line_end_col: int | None

    @staticmethod
    def from_call(path: pathlib.Path, c: ast.Call) -> FileLocation:
        """
        Create a FileLocation from a Call and Path.

        :param path: Path to the file this FileLocation is in
        :param c: Call object to extract line information from
        """
        return FileLocation(
            path, c.lineno, c.col_offset, c.end_lineno, c.end_col_offset
        )


@dataclasses.dataclass
class LangEntry:
    """LangEntry is a single translation that may span multiple files or locations."""

    locations: list[FileLocation]
    string: str
    comments: list[str | None]

    def files(self) -> str:
        """Return a string representation of all the files this LangEntry is in, and its location therein."""
        file_locations = [
            f"{loc.path.name}:{loc.line_start}:{loc.line_end or ''}"
            for loc in self.locations
        ]
        return "; ".join(file_locations)


def dedupe_lang_entries(entries: list[LangEntry]) -> list[LangEntry]:
    """
    Deduplicate a list of lang entries.

    This will coalesce LangEntries that have that same string but differing files and comments into a single
    LangEntry that cotains all comments and FileLocations

    :param entries: The list to deduplicate
    :return: The deduplicated list
    """
    deduped: dict[str, LangEntry] = {}
    for e in entries:
        existing = deduped.get(e.string)
        if existing:
            existing.locations.extend(e.locations)
            existing.comments.extend(e.comments)
        else:
            deduped[e.string] = LangEntry(
                locations=e.locations[:], string=e.string, comments=e.comments[:]
            )
    return list(deduped.values())


def generate_lang_template(data: dict[pathlib.Path, list[ast.Call]]) -> str:
    """Generate a full en.template from the given data."""
    entries: list[LangEntry] = []
    for path, calls in data.items():
        for c in calls:
            if getattr(c, "comment") == "Ignore":
                continue
            entries.append(
                LangEntry(
                    [FileLocation.from_call(path, c)],
                    get_arg(c),
                    [getattr(c, "comment")],
                )
            )

    deduped = dedupe_lang_entries(entries)
    out = """/* Language name */
"!Language" = "English";

"""
    print(f"Done Deduping entries {len(entries)=}  {len(deduped)=}", file=sys.stderr)

    for entry in sorted(deduped, key=lambda e: e.string.lower()):
        if len(entry.comments) != len(entry.locations):
            raise ValueError("Mismatch: 'comments' and 'locations' must have the same length.")

        comment_set = set()
        for comment, loc in zip(entry.comments, entry.locations):
            if comment:
                comment_set.add(f"{loc.path.name}: {comment};")

        files = "In files: " + entry.files()
        comment = " ".join(comment_set).strip()

        header = f"{comment} {files}".strip()
        string = f'"{entry.string}"'
        out += f"/* {header} */\n"
        out += f"{string} = {string};\n\n"

    return out


def main():  # noqa: CCR001
    """Run the Translation Checker."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", help="Directory to search from", default=".")
    parser.add_argument(
        "--ignore",
        action="append",
        help="Directories to ignore",
        default=["venv", ".venv", ".git"],
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="JSON output")
    group.add_argument(
        "--lang", help='en.template "strings" output to specified file, "-" for stdout'
    )
    group.add_argument("--compare-lang", help="en.template file to compare against")

    args = parser.parse_args()

    directory = pathlib.Path(args.directory)
    res = scan_directory(directory, [pathlib.Path(p) for p in args.ignore])

    output = []

    if args.compare_lang:
        seen = set()
        template = parse_template(args.compare_lang)
        for file, calls in res.items():
            for c in calls:
                arg = get_arg(c)
                if arg in template:
                    seen.add(arg)
                else:
                    output.append(f"NEW! {file}:{c.lineno}: {arg!r}")

        for old in set(template) ^ seen:
            output.append(f"No longer used: {old!r}")

    elif args.json:
        to_print_data = [
            {
                "path": str(path),
                "string": get_arg(c),
                "reconstructed": ast.unparse(c),
                "start_line": c.lineno,
                "start_offset": c.col_offset,
                "end_line": c.end_lineno,
                "end_offset": c.end_col_offset,
                "comment": getattr(c, "comment", None),
            }
            for path, calls in res.items()
            for c in calls
        ]
        output.append(json.dumps(to_print_data, indent=2))

    elif args.lang:
        lang_template = generate_lang_template(res)
        if args.lang == "-":
            output.append(lang_template)
        else:
            with open(args.lang, mode="w+", newline="\n", encoding="UTF-8") as langfile:
                langfile.writelines(lang_template)

    else:
        for path, calls in res.items():
            if not calls:
                continue
            output.append(str(path))
            for c in calls:
                output.append(
                    f"    {c.lineno:4d}({c.col_offset:3d}):{c.end_lineno:4d}({c.end_col_offset:3d})\t{ast.unparse(c)}"
                )
            output.append("")

    # Print all collected output at the end
    if output:
        print("\n".join(output))
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
