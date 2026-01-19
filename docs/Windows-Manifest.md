# Introduction

There are some attributes that can be set on a Windows executable via a
manifest.  This is a section in the executable.  The easiest way to set
this is to include an XML-format .manifest file at build time.

## Build time

We specify .manifest files in `build.py`.

## Editing or changing a manifest

You can use the `mt.exe` from your Windows SDK
e.g. "c:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\mt.exe"
to inspect or change an executable's manifest.

To set a whole new manifest:

1. Make a copy of the relevant manifest file, e.g. `EDMarketConnector.manifest`.
2. Edit this file.
3. Run mt.exe thus: `mt.exe -manifest EDMarketConnector-new.manifest -outputresource:EDMarketConnector.exe`.
