<!--
vim: textwidth=79 wrapmargin=79
-->
# Guidelines for contributing to EDMC

## Work on Issues

If you are not part of the core development team then you should only be performing work that addresses an open issue.

So, if what you think needs doing isn't currently referred to in an
[open issue](https://github.com/EDCD/EDMarketConnector/issues),
then you should first [open an issue](https://github.com/EDCD/EDMarketConnector/issues/new/choose).
**Please use the correct template if applicable**.

## Check with us first

Whilst we welcome all efforts to improve the program it's best to ensure that you're not duplicating, or worse,
wasting effort.

There is sometimes a misconception that Open Source means that the primary project is obliged to accept Pull Requests.
That is not so. While you are 100% free to make changes in your own fork, we will only accept changes that are
consistent with our vision for EDMC. Fundamental changes in particular need to be agreed in advance.

---

## Text formatting

The project contains an `.editorconfig` file at its root.  Please either ensure
your editor is taking note of those settings, or cross-check its contents
with the
[editorconfig documentation](https://github.com/editorconfig/editorconfig/wiki/EditorConfig-Properties)
, and ensure your editor/IDE's settings match.

---

## General workflow

1. You will need a GitHub account.
1. Fork the repository on GitHub into your account there (hereafter referred to as 'your fork').
1. In your local copy of *your* fork create an appropriate WIP branch.
1. Develop the changes, testing as you go (no we don't have any actual tests yet).
    1. Be as sure as you can that the code works as you intend and hasn't introduced any other bugs or regressions.
    1. Test the codebase as a whole against any unit tests that do exist, and add your own as you can.
    1. Check your code against flake8 periodically.
1. When you're sure the work is final:
    1. Push your WIP branch to your fork (you probably should have been doing this as you worked as a form of backup).
    1. Access the WIP branch on your fork on GitHub and create a Pull Request.  Mention any Issue number(s) that it
       addresses.
1. Await feedback in the form of comments on the Pull Request.

**IMPORTANT**: Once you have created the Pull Request *any changes you make to that WIP branch and push to your fork
will be reflected in the Pull Request*.  Ensure that *only* the changes for the issue(s) you are addressing are in
the WIP branch.  Any other work should occur in its own separate WIP branch.  If needs be make one branch to work in
and another for the Pull Request, merging or cherry-picking commits as needed.

---

## Git commit conventions

* Please use the standard Git convention of a short title in the first line and fuller body text in subsequent lines.
* Please reference issue numbers using the "hashtag" format #123 in your commit message wherever possible.
  This lets GitHub create two-way hyperlinks between the issue report and the commit.
  [Certain text](https://docs.github.com/en/issues/tracking-your-work-with-issues/creating-issues/linking-a-pull-request-to-an-issue#linking-a-pull-request-to-an-issue-using-a-keyword)
  in a PR that fixes an issue can auto-close the issue when the PR is merged.
  Note the caveats about the extended forms being necessary in some situations.
* If in doubt, lean towards many small commits. This makes git bisect much more useful.
* Please try at all costs to avoid a "mixed-up" commit, i.e. one that addresses more than one issue at once.
  One thing at a time is best.

---

## Git branch structure and tag conventions

Somewhat based on git-flow, but our particular take on it:

### Branches

#### `stable`

This will either have `HEAD` pointing to the latest stable release code *or* might have extra code merged in for a
hotfix that will shortly be in the next stable release. If you want the latest stable release code then use the
appropriate `Release/A.B.C` tag!

#### `beta`

If we run any pre-release betas *with actual builds released, not
just a branch to be run from source*, then this branch will contain that
code.  As per `stable` above, this branch might be ahead of the latest
pre-release due to merging of hotfixes.  Use the appropriate tag if you want
to be sure of the code you checkout.
*If there hasn't yet been a new beta version this could be far behind all
of: `main`, `develop`, `stable`.*

#### `develop`

This is the branch where all current development is integrated.  No commits should be made directly
to this as the work should be done in a separate branch used in a Pull Request before being merged as part of
resolving that Pull Request.

#### `main`

Yes, we've renamed this from `master`.  See
"[Using 'main' as the primary branch in Git](https://github.com/EDCD/EDMarketConnector/wiki/Git-Using-Main-Branch)"
for instructions on ensuring you're cleanly using it in any local clone.

  This branch should contain anything from `develop` that is considered well
    tested and ready for the next `stable` merge.

#### `master`

 **This is no longer used.  If the branch is even present then it's no longer updated.  You should be using `main` instead.**

#### `releases`

Currently the version of the `edmarketconnector.xml` 'appcast' file in this branch is what live
clients check to be notified of new versions.  This can potentially be replaced with the `stable` branch's version,
but some care will be necessary to ensure no users are left behind (their client checking the `releases` branch which
then no longer exists).  For the time being this should always be kept in sync with `stable` as each new release is
made.

### Work in progress conventions

Remember, you should always be working versus a single issue, even if the work is part of a Milestone or Project.
There might be cases where issues aren't duplicates, but your work still addresses more than one.  In that case
pick one for the naming scheme below, but mention all in commit messages and the Pull Request.

In all cases the branch should be named as per the scheme `<class>/<issue number>/<title>`:

* `<class>` - We have several classes of WIP branch:
    * `fix` - For working on bug fixes, e.g. `fix/184/crash-in-startup`
    * `enhancement` - For enhancing an *existing* feature, e.g. `enhancement/192/add-thing-to-wotsit`
    * `feature` - For working on *new* features, e.g. `feature/284/allow-users-to-frob`

* `<issue-number>` is for easy reference when citing the issue number in commit messages.  If you're somehow doing
  work that's not versus an issue then don't put the `<issue number>-` part in.
* `<title>` is intended to allow anyone to quickly know what the branch is addressing.  Try to choose something
  succinct for `<title>`, it's just there for easy reference, it doesn't need to be the entire title of
  the appropriate issue.

The branch you base your work on will depend on which class of WIP it is.  If you're fixing a bug in the latest
`stable` then it's best to base your branch on its HEAD.  If it's a fix for a beta release then base off of `beta`'s
HEAD.  If you're working on a new feature then you'd want to base the work on `develop`'s HEAD.

**Important**: Please *under no circumstance* merge *from* the source branch after you have started work in
your WIP branch.  If there are any non-trivial conflicts when we merge your Pull Request then we might ask you
to *rebase* your WIP branch on the latest version of the source branch.  Otherwise, we'll work out how to best
merge your changes via comments in the Pull Request.

### Tags

#### Stable Releases

All stable releases **MUST** have a tag of the form `Release/Major.Minor.Patch`
on the commit that was `HEAD` when the installer for it was built.

#### Pre-Releases

Tags for pre-releases should be of one of two forms, following [Version
 Strings](docs/Releasing.md#version-strings) conventions.

* Initial beta releases should have versions of the form:

    `Major.Minor.Patch-beta<serial>`

    with the `<serial>` starting with `1` and incrementing with each new beta
    pre-release.

* Release candidates should have versions of the form:

    `Major.Minor.Patch-rc<serial>`

    with the `<serial>` starting with `1` and incrementing with each new
    release candidate.

The tag should thus be `Release/Major.Minor.Patch-(beta|rc)<serial>`.

The Semantic Versioning `+<build metadata>` should never be a part of the tag.

---

## Version conventions

Please see [Version Strings](docs/Releasing.md#version-strings)
for a description of the currently used version strings.

Historically a `A.BC` form was used, based on an internal `A.B.C.D` version
string.  This was changed to simply `A.B.C.D` throughout for `4.0.0.0`,
`4.0.1.0` and `4.0.2.0`.  It would also continue for any other increment of
only the 'C' (Patch) component.

Going forwards we will always use the full [Semantic Version](https://semver.org/#semantic-versioning-specification-semver)
and 'folder style' tag names, e.g. `Release/Major.Minor.Patch`.

Currently, the only file that defines the version code-wise is
`config/__init__.py`. `Changelog.md` and `edmarketconnector.xml` are another
matter handled as part of
[the release process](docs/Releasing.md#distribution).

---
## Python Environment
Whilst you can use whatever IDE/development environment best suits you, much
of the setup in this project has only been tested against PyCharm or VSCode,
along with 'git bash' command-line.

### Use the version denoted by `.python-version`
We only test, and build with, the python version as defined in the file
`.python-version`.  Trying to use any other version might mean things just
don't run at all, or don't work as expected.

### Use a Python virtual environment
Always use a Python virtual environment specific to working on this project.

An example, when using Python 3.11.x would be:
```bash
python -m venv ../edmc-venv-3.11
```
Note how the 'venv' is placed in a sub-directory *of the parent directory* of
the project.  This avoids any issues with scripts working recursively picking
up your 'venv' files.

If you have good reason to put the 'venv' inside the project directory then
you **MUST** use either `venv` or `.venv`, else you'll run into all sorts of
problems with pre-commit checks.

### Install the development requirements
Whilst simply running the project only requires
`pip install -r requirements.txt`-provided modules, development work will
instead require:
```bash
pip install -r requirements-dev.txt
```
NB: This itself will also take note of `requirements.txt`.

This will ensure you have all the necessary tools to hand for the pre-commit
checks.

### Set up `pre-commit`
In order to have any submitted PR be in the least-worse shape when first opened
you **MUST** run the checks as specified in `.pre-commit-config.yaml`.
```bash
pre-commit install --install-hooks
```
Now whenever you `git commit` the various checks will be run to ensure your
code is compliant with our requirements.  If you have a *temporary* need to
bypass this (e.g. wanting to commit one change and fix a non-compliant file
later) you can add `-n` to the `git commit` arguments.

**NB: There is [a problem](https://github.com/microsoft/vscode-python/issues/10165)
with pre-commit if using VSCode.**  There's a workaround in
[one of the comments](https://github.com/microsoft/vscode-python/issues/10165#issuecomment-1277237676).

### Consider running `pytest` before any `git push`
The GitHub workflows for PRs and pushes will run `pytest` and flag an error
if the tests don't pass, so it's in your interests to ensure you've not broken
any tests.

You could endeavour to remember to run `pytest` manually, or you could add
this git hook:

`.git/hooks/pre-push`
```bash
#!/bin/sh

# If this script exits with a non-zero status nothing will be pushed.
#
# This hook is called with the following parameters:
#
# $1 -- Name of the remote to which the push is being done
# $2 -- URL to which the push is being done
#
# If pushing without using a named remote those arguments will be equal.
#
# Information about the commits which are being pushed is supplied as lines to
# the standard input in the form:
#
#   <local ref> <local sha1> <remote ref> <remote sha1>

remote="$1"
url="$2"

echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-"
echo " Running pytest..."
pytest || exit 1
echo " All tests passed, proceeding..."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-"

exit 0
```
It's probably overkill, and will become painful if enough tests are added, to
run `pytest` in a `pre-commit` hook.

---

## Linting

We use flake8 for linting all python source.

While working on your changes, please ensure that they pass a check from `flake8` using our configuration and plugins.
If you installed `requirements-dev.txt` with pip, you should simply be able to run `flake8 your_files_here` to lint
your files.

Note that if your PR does not cleanly (or mostly cleanly) pass a linting scan, your PR may be put on hold pending fixes.

## Unit testing

Where possible please write unit tests for your PRs, especially in the case of
bug fixes, having regression tests help ensure that we don't accidentally
re-introduce a bug down the line.

We use the [`pytest`](https://docs.pytest.org/en/stable/) for unit testing.

The files for a test should go in a sub-directory of `tests/` named after the
(principal) file or directory that contains the code they are testing.
For example:

- Tests for `journal_lock.py` are in
   `tests/journal_lock.py/test_journal_lock.py`. The `test_` prefix on
   `test_journal_lock.py` is necessary in order for `pytest` to recognise the
   file as containing tests to be run.
- Tests for `config/` code are located in `tests/config/test_config.py`, not
   `tests/config.py/test_config.py`

The sub-directory avoids having a mess of files in `tests`, particularly when
there might be supporting files, e.g. `tests/config/_old_config.py` or files
containing test data.

Invoking just a bare `pytest` command will run all tests.

To run only a sub-set of tests you can use, e.g. `pytest -k journal_lock`. You
might want to use `pytest -rA -k journal_lock` if you have any debug `print()`
statements within the test code itself, so you can see the output even when the
tests all succeed.

Adding `--trace` to a `pytest` invocation causes it to drop into a
[`pdb`](https://docs.python.org/3/library/pdb.html) prompt for each test,
handy if you want to step through the testing code to be sure of anything.

Otherwise, see the [pytest documentation](https://docs.pytest.org/en/stable/contents.html). 

### Test Coverage
As we work towards actually having tests for as much of the code as possible
it is useful to monitor the current test coverage.

Running `pytest` will also produce the overall coverage report, see the
configured options in `pyproject.toml`.

One issue you might run into is where there is code that only runs on one
platform.  By default `pytest-cov`/`coverage` will count this code as not
tested when run on a different platform.  We utilise the
`coverage-conditional-plugin` module so that `#pragma` comments can be used
to give hints to coverage about this.

The pragmas are defined in the
`tool.coverage.coverage_conditional_plugin.rules` section of `pyproject.toml`,
e.g.

```toml
[tool.coverage.coverage_conditional_plugin.rules]
sys-platform-win32 = "sys_platform != 'win32'"
...
```
And are used as in:
```python
import sys

if sys.platform == 'win32':  # pragma: sys-platform-win32
    ...
else:  # pragma: sys-platform-not-win32
    ...
```
Note the inverted sense of the pragma definitions, as the comments cause
`coverage` to *not* consider that code block on this platform.

As of 2022-10-02 and `coverage-conditional-plugin==0.7.0` there is no way to
signal that an entire file should be excluded from coverage reporting on the
current platform.  See
[this GitHub issue comment](https://github.com/wemake-services/coverage-conditional-plugin/issues/2#issuecomment-1263918296)
.

---

## Imports used only in core plugins

Because the 'core' plugins, as with any EDMarketConnector plugin, are only ever
loaded dynamically, not through an explicit `import` statement, there is no
way for `py2exe` to know about them when building the contents of the
`dist.win32` directory.  See [docs/Releasing.md](docs/Releasing.md) for more
information about this build process.

Thus, you **MUST** check if any imports you add in `plugins/*.py` files are only
referenced in that file (or also only in any other core plugin), and if so
**YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN `Build-exe-and-msi.py`
IN ORDER TO ENSURE THE FILES ARE ACTUALLY PRESENT IN AN END-USER
INSTALLATION ON WINDOWS.**

An exmaple is that as of 2022-02-01 it was noticed that `plugins/eddn.py` now
uses `util/text.py`, and is the only code to do so.  `py2exe` does not detect
this and thus the resulting `dist.win32/library.zip` does not contain the
`util/` directory, let alone the `util/text.py` file.  The fix was to update
the appropriate `packages` definition to:

```python
            'packages': [
                'sqlite3',  # Included for plugins
                'util',  # 2022-02-01 only imported in plugins/eddn.py
            ],
```

Note that in this case it's in `packages` because we want the whole directory
adding.  For a single file an extra item in `includes` would suffice.

Such additions to `Build-exe-and-msi.py` should not cause any issues if
subsequent project changes cause `py2exe` to automatically pick up the same
file(s).

---

## Debugging network sends

Rather than risk sending bad data to a remote service, even if only through
repeatedly sending the same data you can cause such code to instead send 
through a local web server and thence to a log file.

1. This utilises the `--debug-sender ...` command-line argument.  The argument
  to this is free-form, so there's nothing to edit in EDMarketConnector.py 
  in order to support a new target for this.
2. The debug web server is set up globally in EDMarketConnector.py.
3. In code where you want to utilise this you will need at least something 
  like this (taken from some plugins/edsm.py code):

```python
from config import debug_senders
from edmc_data import DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT

TARGET_URL = 'https://www.edsm.net/api-journal-v1'
if 'edsm' in debug_senders:
  TARGET_URL = f'http://{DEBUG_WEBSERVER_HOST}:{DEBUG_WEBSERVER_PORT}/edsm'

...
r = this.requests_session.post(TARGET_URL, data=data, timeout=_TIMEOUT)
```

   Be sure to set a URL path in the `TARGET_URL` that denotes where the data
   would normally be sent to.
4. The output will go into a file in `%TEMP%\EDMarketConnector\http_debug` 
  whose name is based on the path component of the URL.  In the code example 
  above it will come out as `edsm.log` due to how `TARGET_URL` is set.

---

## Coding Conventions

In general, please follow [PEP8](https://www.python.org/dev/peps/pep-0008/)

Adhere to the spelling conventions of the libraries and modules used in the 
project.

Yes, this means using 'color' rather than 'colour', and in general will mean
US, not British, spellings.

---

## Control flow

Never oneline any control flow (`if`, `else`, `for`), as it makes spotting what happens next difficult.
  
Yes:

```python
if something_true:
    one_thing_we_do()
```
  
No:

```python
if something_true: one_thing_we_do()
```
  
  Yes, some existing code still flouts this rule.

### Scope changes

**Always** use Line breaks after scope changes. It makes seeing where scope has changed far easier on a quick skim

Yes:

```python
  if True:
    do_something()

  else:
    raise UniverseBrokenException()

  return
```

No:

```python
  if True:
    do_something()
  else:
    raise UniverseBrokenException()
  return
```

---

## Use Type hints

Please do place [type hints](https://docs.python.org/3/library/typing.html) on the declarations of your functions,
both their arguments and return types.

---

## Use `logging` not `print()`, and definitely not `sys.stdout.write()`

`EDMarketConnector.py` sets up a `logging.Logger` for this under the
`appname`, so:

```python
import logging
from config import appname
logger = logging.getLogger(appname)

logger.info(f'Some message with a {variable}')

try:
    something
except Exception as e:  # Try to be more specific
    logger.error(f'Error in ... with ...', exc_info=e)
```

**DO NOT** use the following, as you might cause a circular import:

```python
    from EDMarketConnector import logger
```

Setting up [logging in plugins](./PLUGINS.md#logging) is slightly different.

We have implemented a `logging.Filter` that adds support for the following
in `logging.Formatter()` strings:

1. `%(qualname)s` which gets the full `<module>.ClassA(.ClassB...).func`
  of the calling function.
1. `%(class)s` which gets just the enclosing class name(s) of the calling
  function.

If you want to see how we did this, check `EDMCLogging.py`.

So don't worry about adding anything about the class or function you're
logging from, it's taken care of.

*Do use a pertinent message, even when using `exc_info=...` to log an
exception*.  e.g. Logging will know you were in your `get_foo()` function
but you should still tell it what actually (failed to have) happened
in there.

### Use the appropriate logging level
You must ensure necessary information is always in the log files, but 
not so much that it becomes more difficult to discern important information 
when diagnosing an issue.

`logging`, and thus our `logger` instances provide functions of the 
following names:

- `info` - For general messages that don't occur too often outside of startup 
  and shutdown.
- `warning` - An error has been detected, but it doesn't impact continuing 
  functionality.  In particular **use this when logging errors from 
  external services**.  This would include where we detected a known issue 
  with Frontier-supplied data.  A currently unknown issue *may* end up 
  triggering logging at `error` level or above.
- `error` - An error **in our code** has occurred.  The application might be 
  able to continue, but we want to make it obvious there's a bug that we 
  need to fix.
- `critical` - An error has occurred **in our code** that impacts the 
  continuation of the current process.
- `debug` - Information about code flow and data that is occurs too often
  to be at `info` level.  Keep in mind our *default* logging level is DEBUG,
  but users can change it for the
  [plain log file](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#plain-log-file),
  but the
  [debug log giles](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#debug-log-files)
  are always at least at DEBUG level.
  
In addition to that we utilise one of the user-defined levels as:

- `trace` - This is a custom log level intended for debug messages which 
  occur even more often and would cause too much log output for even 
  'normal' debug use. 
  In general only developers will set this log level, but we do supply a
  command-line argument and `.bat` file for users to enable it.  It cannot be
  selected from Settings in the UI.

  **Do not use a bare `logger.trace(...)` call** unless you're 100% certain 
  it's only temporary **and will be removed before any code merge**.  In 
  that case you would utilise `EDMarketConnector.py --trace` to see the output.

  Instead, you should gate any TRACE logging using the `trace_if()` helper 
  method provided on `logger`:

    ```python
      logger.trace_if('journal.event.scan', 'my-log-message')
    ```

  The string used to identify this tracing should be related to the 
  **function of the code**, not the particular file, or class, that it is in.
  This is so that the same string can be used to trace code that spans more 
  than one file, class, or other scope.
  
  This would then be triggered by running EDMarketConnector with the 
  appropriate command-line arguments:

      EDMarketConnector.py --trace-on journal.event.scan
  
  Note that you do **not** also need to specify `--trace`, that's implied.
  
  This way you can set up TRACE logging that won't spam just because `--trace`
  is used.

---

## Use fstrings, not modulo-formatting or .format

[fstrings](https://www.python.org/dev/peps/pep-0498/) are new in python 3.6,
and allow for string interpolation rather than more opaque formatting calls.

As part of our flake8 linting setup we have included a linter that warns when
you use `%` on string literals.

`.format()` won't throw flake8 errors, **but only because it's still the 
best way to handle [untranslated words](./docs/Translations.md#call-_)
in otherwise translated phrases**.  Thus, we allow this, and only this, use of
`.format()` for strings.

---

## Docstrings

Doc strings are preferred on all new modules, functions, classes, and methods, as they help others understand your code.
We use the `sphinx` formatting style, which for pycharm users is the default.

Lack of docstrings, or them not passing some checks, *will* cause a flake8 
failure in our setup.

---

## Comments

### LANG comments for translations

When adding translations you *must*
[add a LANG comment](./docs/Translations.md#add-a-lang-comment).

### Mark hacks and workarounds with a specific comment

We often write hacks or workarounds to make EDMC work on a given version or around a specific bug.
Please mark all hacks, workarounds, magic with one of the following comments, where applicable:

```py
# HACK $elite-version-number | $date: $description
# MAGIC $elite-version-number | $date: $description
# WORKAROUND $elite-version-number | $date: $description
```

The description should cover exactly why the hack is needed, what it does, what is required / expected for it to be removed.
Please be verbose here, more info about weird choices is always prefered over magic that we struggle to understand in six months.

Additionally, if your hack is over around 5 lines, please include a `# HACK END` or similar comment to indicate the end of the hack.

# Use `sys.platform` for platform guards

`mypy` (and `pylance`) understand platform guards and will show unreachable code / resolve imports correctly
for platform specific things. However, this only works if you directly reference `sys.platform`, importantly 
the following does not work:

```py
from sys import platform
if platform == 'darwin':
  ...
```

It **MUST** be `if sys.platform`.

---

## Build process

See [Releasing.md](docs/Releasing.md) for the environment and procedure necessary for building the application into
a .exe and Windows installer file.

---

## Translations

See [Translations.md](docs/Translations.md) for how to ensure any new phrases your code adds can be easily
translated.

---

## Acknowledgement

The overall structure, and some of the contents, of this document were taken from the [EDDI Contributing.md](https://github.com/EDCD/EDDI/blob/develop/docs/Contributing.md).
