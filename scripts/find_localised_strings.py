"""Search all given paths recursively for localised string calls."""
from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import pathlib
import re
import sys
from typing import Optional

# spell-checker: words dedupe deduping deduped


def get_func_name(thing: ast.AST) -> str:
    """Get the name of a function from a Call node."""
    if isinstance(thing, ast.Name):
        return thing.id

    if isinstance(thing, ast.Attribute):
        return get_func_name(thing.value)
    return ''


def get_arg(call: ast.Call) -> str:
    """Extract the argument string to the translate function."""
    if len(call.args) > 1:
        print('??? > 1 args', call.args, file=sys.stderr)

    arg = call.args[0]
    if isinstance(arg, ast.Constant):
        return arg.value
    if isinstance(arg, ast.Name):
        return f'VARIABLE! CHECK CODE! {arg.id}'
    return f'Unknown! {type(arg)=} {ast.dump(arg)} ||| {ast.unparse(arg)}'


def find_calls_in_stmt(statement: ast.AST) -> list[ast.Call]:
    """Recursively find ast.Calls in a statement."""
    out = []
    for n in ast.iter_child_nodes(statement):
        out.extend(find_calls_in_stmt(n))
    if isinstance(statement, ast.Call) and get_func_name(statement.func) == '_':

        out.append(statement)

    return out


"""
Regular expressions for finding comments.

COMMENT_SAME_LINE_RE is for an in-line comment on the end of code.
COMMENT_OWN_LINE_RE is for a comment on its own line.

The difference is necessary in order to tell if a 'above' LANG comment is for
its own line (SAME_LINE), or meant to be for this following line (OWN_LINE).
"""
COMMENT_SAME_LINE_RE = re.compile(r'^.*?(#.*)$')
COMMENT_OWN_LINE_RE = re.compile(r'^\s*?(#.*)$')


def extract_comments(call: ast.Call, lines: list[str], file: pathlib.Path) -> Optional[str]:  # noqa: CCR001
    """
    Extract comments from source code based on the given call.

    This returns comments on the same line as the call preferentially to comments above.
    All comments must be prefixed with LANG, ie `# LANG: `

    :param call: The call node to look for comments around.
    :param lines: The file that the call node came from, as a list of strings where each string is a line.
    :param file: The path to the file this call node came from
    :return: The first comment that matches the rules, or None
    """
    out: Optional[str] = None
    above = call.lineno - 2
    current = call.lineno - 1

    above_line = lines[above].strip() if len(lines) >= above else None
    above_comment: Optional[str] = None
    current_line = lines[current].strip()
    current_comment: Optional[str] = None

    bad_comment: Optional[str] = None
    if above_line is not None:
        match = COMMENT_OWN_LINE_RE.match(above_line)
        if match:
            above_comment = match.group(1).strip()
            if not above_comment.startswith('# LANG:'):
                bad_comment = f'Unknown comment for {file}:{call.lineno} {above_line}'
                above_comment = None

            else:
                above_comment = above_comment.replace('# LANG:', '').strip()

    if current_line is not None:
        match = COMMENT_SAME_LINE_RE.match(current_line)
        if match:
            current_comment = match.group(1).strip()
            if not current_comment.startswith('# LANG:'):
                bad_comment = f'Unknown comment for {file}:{call.lineno} {current_line}'
                current_comment = None

            else:
                current_comment = current_comment.replace('# LANG:', '').strip()

    if current_comment is not None:
        out = current_comment

    elif above_comment is not None:
        out = above_comment

    elif bad_comment is not None:
        print(bad_comment, file=sys.stderr)

    if out is None:
        print(f'No comment for {file}:{call.lineno} {current_line}', file=sys.stderr)

    return out


def scan_file(path: pathlib.Path) -> list[ast.Call]:
    """Scan a file for ast.Calls."""
    data = path.read_text(encoding='utf-8')
    lines = data.splitlines()
    parsed = ast.parse(data)
    out: list[ast.Call] = []

    for statement in parsed.body:
        out.extend(find_calls_in_stmt(statement))

    # see if we can extract any comments
    for call in out:
        setattr(call, 'comment', extract_comments(call, lines, path))

    out.sort(key=lambda c: c.lineno)
    return out


def scan_directory(path: pathlib.Path, skip: list[pathlib.Path] | None = None) -> dict[pathlib.Path, list[ast.Call]]:
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


def parse_template(path) -> set[str]:
    """
    Parse a lang.template file.

    The regexp this uses was extracted from l10n.py.

    :param path: The path to the lang file
    """
    lang_re = re.compile(r'\s*"([^"]+)"\s*=\s*"([^"]+)"\s*;\s*$')
    out = set()
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        match = lang_re.match(line)
        if not match:
            continue
        if match.group(1) != '!Language':
            out.add(match.group(1))

    return out


@dataclasses.dataclass
class FileLocation:
    """FileLocation is the location of a given string in a file."""

    path: pathlib.Path
    line_start: int
    line_start_col: int
    line_end: Optional[int]
    line_end_col: Optional[int]

    @staticmethod
    def from_call(path: pathlib.Path, c: ast.Call) -> 'FileLocation':
        """
        Create a FileLocation from a Call and Path.

        :param path: Path to the file this FileLocation is in
        :param c: Call object to extract line information from
        """
        return FileLocation(path, c.lineno, c.col_offset, c.end_lineno, c.end_col_offset)


@dataclasses.dataclass
class LangEntry:
    """LangEntry is a single translation that may span multiple files or locations."""

    locations: list[FileLocation]
    string: str
    comments: list[Optional[str]]

    def files(self) -> str:
        """Return a string representation of all the files this LangEntry is in, and its location therein."""
        out = ''
        for loc in self.locations:
            start = loc.line_start
            end = loc.line_end
            end_str = f':{end}' if end is not None and end != start else ''
            out += f'{loc.path.name}:{start}{end_str}; '

        return out


def dedupe_lang_entries(entries: list[LangEntry]) -> list[LangEntry]:
    """
    Deduplicate a list of lang entries.

    This will coalesce LangEntries that have that same string but differing files and comments into a single
    LangEntry that cotains all comments and FileLocations

    :param entries: The list to deduplicate
    :return: The deduplicated list
    """
    deduped: list[LangEntry] = []
    for e in entries:
        cont = False
        for d in deduped:
            if d.string == e.string:
                cont = True
                d.locations.append(e.locations[0])
                d.comments.extend(e.comments)

        if cont:
            continue

        deduped.append(e)

    return deduped


def generate_lang_template(data: dict[pathlib.Path, list[ast.Call]]) -> str:
    """Generate a full en.template from the given data."""
    entries: list[LangEntry] = []
    for path, calls in data.items():
        for c in calls:
            entries.append(LangEntry([FileLocation.from_call(path, c)], get_arg(c), [getattr(c, 'comment')]))

    deduped = dedupe_lang_entries(entries)
    out = '''/* Language name */
"!Language" = "English";

'''
    print(f'Done Deduping entries {len(entries)=}  {len(deduped)=}', file=sys.stderr)
    for entry in deduped:
        assert len(entry.comments) == len(entry.locations)
        comment = ''
        files = f'In files: {entry.files()}'
        string = f'"{entry.string}"'

        for i, comment_text in enumerate(entry.comments):
            if comment_text is None:
                continue

            loc = entry.locations[i]
            to_append = f'{loc.path.name}: {comment_text}; '
            if to_append not in comment:
                comment += to_append

        header = f'{comment.strip()} {files}'.strip()
        out += f'/* {header} */\n'
        out += f'{string} = {string};\n'
        out += '\n'

    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', help='Directory to search from', default='.')
    parser.add_argument('--ignore', action='append', help='directories to ignore', default=['venv', '.venv', '.git'])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--json', action='store_true', help='JSON output')
    group.add_argument('--lang', help='en.template "strings" output to specified file, "-" for stdout')
    group.add_argument('--compare-lang', help='en.template file to compare against')

    args = parser.parse_args()

    directory = pathlib.Path(args.directory)
    res = scan_directory(directory, [pathlib.Path(p) for p in args.ignore])

    if args.compare_lang is not None and len(args.compare_lang) > 0:
        seen = set()
        template = parse_template(args.compare_lang)

        for file, calls in res.items():
            for c in calls:
                arg = get_arg(c)
                if arg in template:
                    seen.add(arg)
                else:
                    print(f'NEW! {file}:{c.lineno}: {arg!r}')

        for old in set(template) ^ seen:
            print(f'No longer used: {old}')

    elif args.json:
        to_print_data = [
            {
                'path': str(path),
                'string': get_arg(c),
                'reconstructed': ast.unparse(c),
                'start_line': c.lineno,
                'start_offset': c.col_offset,
                'end_line': c.end_lineno,
                'end_offset': c.end_col_offset,
                'comment': getattr(c, 'comment', None)
            } for (path, calls) in res.items() for c in calls
        ]

        print(json.dumps(to_print_data, indent=2))

    elif args.lang:
        if args.lang == '-':
            print(generate_lang_template(res))

        else:
            with open(args.lang, mode='w+', newline='\n') as langfile:
                langfile.writelines(generate_lang_template(res))

    else:
        for path, calls in res.items():
            if len(calls) == 0:
                continue

            print(path)
            for c in calls:
                print(
                    f'    {c.lineno:4d}({c.col_offset:3d}):{c.end_lineno:4d}({c.end_col_offset:3d})\t', ast.unparse(c)
                )

            print()
