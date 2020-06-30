Guidelines for contributing to EDMC
===

Work on Issues
---
If you are not part of the core development team then you should only be performing work that addresses an open issue.

So, if what you think needs doing isn't currently referred to in an [open issue](https://github.com/EDCD/EDMarketConnector/issues), then you should first [open an issue](https://github.com/EDCD/EDMarketConnector/issues/new/choose).

Check with us first
---
Whilst we welcome all efforts to improve the program it's best to ensure that you're not duplicating, or worse,
wasting effort.

There is sometimes a misconception that Open Source means that the primary project is obliged to accept Pull Requests.
That is not so. While you are 100% free to make changes in your own fork, we will only accept changes that are
consistent with our vision for EDMC. Fundamental changes in particular need to be agreed in advance.

Version conventions
---
The only currently supported format for the version is A.B.C.D, following [Semantic Versioning](https://semver.org/)
conventions.  Note that the 'D' part being different does *not* make the version different for purposes of the
WinSparkle update checking, XXX (true?): or the Windows installer thinking it's a newer version.

There is currently no support for appending any other string to the version (it will break some of the build
code), see [this issue](https://github.com/EDCD/EDMarketConnector/issues/534).

Historically the A.B.C.D version was collapsed into A.BC and then a tag added of the form `rel-ABC`.  Going
forwards we will always use the full version and 'folder style' tag names, e.g. `Release/A.B.C.D` .

Currently the only file that defines the version code-wise is `config.py`.  `Changelog.md` and `edmarketconnector.xml`
are another matter handled as part of [the release process](https://github.com/EDCD/EDMarketConnector/blob/master/docs/Releasing.md#distribution).

Git branch structure and tag contentions
---
Somewhat based on git-flow, but our particular take on it:

* `stable` - The HEAD of this Branch should always point to the code that was used in the last released stable version.

* `beta` - If we run any pre-release betas *with actual builds released, not just a branch to be run from source*,
then the HEAD of this Branch should always point to the code that was used in the last beta version.

* `develop` - This is the branch where all current development is integrated.  No commits should be made directly
  to this as the work should be done in a separate branch used in a Pull Request before being merged as part of
  resolving that Pull Request.

* `master` - To avoid accidental commits that could have unintended consequences we do NOT use this branch.
   see `develop` or `stable` instead.  However, whenever a new stable release is made `master` should be fast-forwarded
   to remain in sync with `stable`, as this is the default branch for code display on GitHub.  Anyone working on
   something without first reading these guidelines is also likely to have worked on either local `master`
   directly, or a branch based on it.

* `releases` - Currently the version of the `edmarketconnector.xml` 'appcast' file in this branch is what live
clients check to be notified of new versions.  This can potentially be replaced with the `stable` branch's version,
but some care will be necessary to ensure no users are left behind (their client checking the `releases` branch which
then no longer exists).  For the time being this should always be kept in sync with `stable` as each new release is
made.

Work in progress conventions
---
Remember, you should always be working versus a single issue, even if the work is part of a Milestone or Project. 
There might be cases where issues aren't duplicates, but your work still addresses more than one.  In that case
pick one for the naming scheme below, but mention all in commit messages and the Pull Request.

In all cases the branch should be named as per the scheme `<class>/<issue number>-<title>`:
* `<class>` - We have several classes of WIP branch:
  * `fix` - For working on bug fixes, e.g. `fix/184-crash-in-startup`
  * `enhancement` - For enhancing an *existing* feature, e.g. `enhancement/192-add-thing-to-wotsit`
  * `feature` - For working on *new* features, e.g. `feature/284-allow-users-to-frob`

* `<issue-number>` is for easy reference when citing the issue number in commit messages.
* `<title>` is intended to allow anyone to quickly know what the branch is addressing.  Try to choose something
   succinct for `<title>`, it's just there for easy reference, it doesn't need to be the entire title of
   the appropriate issue.

Which branch you base your work on will depend on which class of WIP it is.  If you're fixing a bug in the latest
`stable` then it's best to base your branch on its HEAD.  If it's a fix for a beta release then base off of `beta`'s
HEAD.  If you're working on a new feature then you'd want to base the work on `develop`'s HEAD.

**Important**: Please *under no circumstance* merge *from* the source branch after you have started work in
your WIP branch.  If there are any non-trivial conflicts when we merge your Pull Request then we might ask you
to rebase your WIP branch on the latest version of the source branch.  Otherwise we'll work out how to best
merge your changes via comments in the Pull Request.

General workflow
---

1. You will need a GitHub account.
1. Fork the repository on GitHub into your account there (hereafter referred to as 'your fork').
1. In your local copy of *your* fork create an appropriate WIP branch.
1. Develop the changes, testing as you go (no we don't have any actual tests yet).
    1. Be as sure as you can that the code works as you intend and hasn't introduced any other bugs or regressions.
1. When you're sure the work is final:
    1. Push your WIP branch to your fork (you probably should have been doing this as you worked as a form of backup).
    1. Access the WIP branch on your fork on GitHub and create a Pull Request.  Mention any Issue number(s) that it
    addresses.
1. Await feedback in the form of comments on the Pull Request.

**IMPORTANT**: Once you have created the Pull Request *any changes you make to that WIP branch and push to your fork
will be reflected in the Pull Request*.  Ensure that *only* the changes for the issue(s) you are addressing are in
the WIP branch.  Any other work should occur in its own separate WIP branch.  If needs be make one branch to work in
and another for the Pull Request, merging or cherry-picking commits as needed.

Coding Conventions
===
* Adhere to the spelling conventions of the libraries and modules used in the project.  Yes, this means using 'color'
  rather than 'colour', and in general will mean US, not British, spellings.
* **ALWAYS** place a single-statement control flow body, for control statements such as `if`, `else`, `for`, `foreach`,
  on a separate line, with consistent indentation.
  
  Yes:
  
        if somethingTrue:
            Things we then do
  
  No:
   
        if somethingTrue: One thing we do
  
  Yes, some existing code still flouts this rule.
  
* Going forwards please do place [type hints](https://docs.python.org/3/library/typing.html) on the declarations of your functions, both their arguments and return
  types.
  
Git commit conventions
===
* Please use the standard Git convention of a short title in the first line and fuller body text in subsequent lines.
* Please reference issue numbers using the "hashtag" format #123 in your commit message wherever possible.
  This lets GitHub create two-way hyperlinks between the issue report and the commit.
  Certain text in a PR that fixes an issue can auto-close the issue when the PR is merged.
* If in doubt, lean towards many small commits. This makes git bisect much more useful.
* Please try at all costs to avoid a "mixed-up" commit, i.e. one that addresses more than one issue at once.
  One thing at a time is best.

Build process
===
See [Releasing.md](docs/Releasing.md) for the environment and procedure necessary for building the application into
a .exe and Windows installer file.

Translations
===
See [Translations.md](docs/Translations.md) for how to ensure any new phrases your code adds can be easily
translated.

Acknowledgement
---
The overall structure, and some of the contents, of this document were taken from the [EDDI Contributing.md](https://github.com/EDCD/EDDI/blob/develop/docs/Contributing.md).
