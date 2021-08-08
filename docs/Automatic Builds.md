# Introduction

Instead of building manually as laid out by [Releasing](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Releasing.md), you can build the EDMC installer using GitHub actions.

## Initiating a workflow run

Starting a workflow run is done from the Actions tab at the top of the main GitHub UI

NB: The branch you want to build must have the workflow file (`.github/workflows/windows-build.yml`), and the version of the file in that branch is the version that will be used for the build (e.g. for different python versions)

1. Select the Actions tab at the top of the main GitHub interface
2. Select the `Build EDMC for Windows` workflow on the left
3. Click the "Run workflow" button at the right side of the blue banner
   1. Select the branch you want to build
   2. Click the "Run Workflow"

## Downloading built installer files

When the workflow is (successfully) completed, it will upload the msi file it built as a "Workflow Artifact". You can find the artifacts as follows:

1. Select `All workflows` on the left
2. Select the `Build EDMC for Windows` action
3. Select your build (probably the top one)
4. Find the `Built Files` artifact

Within the `Built Files` zip file is the installer msi

**Please ensure you test the built msi before creating a release.**

## Automatic release creation

Github Actions can automatically create a release after finishing a build (as mentioned above). To make this happen,
simply push a tag to the repo with the format `v1.2.3` where 1.2.3 is the semver for the version (Note that this is
**DISTINCT** from the normal `Release/1.2.3` format for release tags).

Once the push is completed, a build will start, and once that is complete, a draft release will be created. Edit the
release as needed and publish it. **Note that you should still test the built msi before publishing the release**
