# Using 'main' as the primary branch in Git

This project uses 'main', instead of 'master', for its primary branch.

If you had previously cloned with 'master' as the primary then you
should follow these steps to migrate:

1. `git checkout master`
1. `git branch -m master main`
1. `git fetch`
1. `git branch --unset-upstream`
1. `git branch -u origin/main`
1. `git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main`

These steps are:

1.    Go to the master branch
1.    Rename master to main locally
1.    Get the latest commits from the server
1.    Remove the link to origin/master
1.    Add a link to origin/main
1.    Update the default branch to be origin/main

See
[Contributing.md](https://github.com/EDCD/EDMarketConnector/blob/main/Contributing.md)
for an outline of the other branches we use.

## Migrating your own project from 'master' to 'main'

We followed the instructions at https://www.hanselman.com/blog/EasilyRenameYourGitDefaultBranchFromMasterToMain.aspx
, which boil down to:

1. `git checkout master`
1. `git fetch origin`
1. `git branch -m master main`
1. `git push -u origin main`

