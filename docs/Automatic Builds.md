# Introduction

Instead of building manually as laid out by
[Releasing](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Releasing.md),
you can build the EDMarketConnector installer using GitHub actions.

## Initiating a workflow run

### Automatically on tag push
Once you are sure you have a branch all ready for release as a new version you
should be adding a `Release/<semantic version>` tag at that HEAD.  Pushing 
such a tag to GitHub will cause
[the GitHub Windows Build Action file](../.github/workflows/windows-build.yml)
to build an installer and create a draft release, with the pre-release box
pre-ticked.  This ensures you don't accidentally create a new non-pre 
release which will always become the target of the `latest` shortcut on GitHub.

You can monitor such an auto-build from the Actions tab on GitHub.  If it 
completes successfully then check the Releases tab on GitHub for the draft 
that was created.

See [Releasing.md#Distribution](./Releasing.md#distribution) for details on
how to fully publish an automatic release so that running EDMarketConnector.exe
clients pick it up as an update.

### Manually
Starting a workflow run is done from the Actions tab at the top of the main
GitHub UI

NB: The branch you want to build must have the workflow file
(`.github/workflows/windows-build.yml`), and the version of the file in that
branch is the version that will be used for the build (e.g. for different
python versions)

1. Select the Actions tab at the top of the main GitHub interface
2. Select the `Build EDMC for Windows` workflow on the left
3. Click the "Run workflow" button on the right side of the blue banner
   1. Select the branch you want to build
   2. Click the "Run Workflow"

## Downloading built installer files

When the workflow is (successfully) completed, it will upload the msi file it
built as a "Workflow Artifact". You can find the artifacts as follows:

1. Select `All workflows` on the left
2. Select the `Build EDMC for Windows` action
3. Select your build (probably the top one)
4. Find the `Built Files` artifact

Within the `Built Files` zip file is the installer msi

**Please ensure you test the built msi before creating a release.**
