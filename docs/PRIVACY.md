# Privacy Policy
Last Updated: 2026-01-19

## What information do we collect about you?

### Frontier Authentication

This application would not function without utilising the API provided as
part of the [Frontier User Portal](https://user.frontierstore.net/user/information).

When Frontier Authentication is performed this application inevitably receives:

- Frontier ID - your unique ID for this system.
- Name - The real name specified in your account.
- Email - The email address associated with your account.
- Platform - Whether this is a Frontier account, Xbox, Playstation,
  Steam, etc.  The 'Authorized Applications' lists all the Clients (applications)
  you've authorized to request data on your behalf.  This might include
  sites like Inara.

EDMC does not persistently store or transmit your Frontier personal profile information (name, email, etc.), 
only the access tokens required to query the API. For clarity, it also does *not* pass any of the information
outlined above to any plugins.

### Elite Commander details

While this app is running it collects the following information about you:

- Your in-game “CMDR” name.
- Your in-game location.
- Your in-game ship(s), ship loadout and inventory.
- Various actions that you perform in the game.

### Operating System & IP Address

Due to various system processes, such as checking for updates, GitHub may receive 
some limited information about you, including:

- Your Operating System.
- Your Internet Protocol (“IP”) Address.

We do not control or record this information.

### Data Storage

EDMC stores configuration, logs, and authentication tokens locally on your computer. EDMC does 
not intentionally retain personal data longer than necessary for normal operation. All data is stored 
locally and can be removed by deleting the application and its configuration directory.

EDMC is an open-source, community-developed application. There is no central service operated by the 
developers that collects or aggregates user data. 

Any future analytics tracking (for diagnostic or service purposes) will be anonymous by default, 
and will not transmit personally identifiable information. Such analytics tracking will (if implemented) always 
include opt-out parameters, and be clearly communicated in changelogs.


---
## Third-Party Sites
At your choice, this app may transmit some of your CMDR details to third-party services as follows:

### EDDN

If you have active either of the following options on the 'EDDN' tab
of the application's settings:

- Send station data to the Elite Dangerous Data Network (on by default)
- Send system and scan data to the Elite Dangerous Data Network (on by default)

then your CMDR name and your in-game location are transmitted to the
[Elite Dangerous Data Network](https://github.com/EDCD/EDDN/wiki) (“EDDN”). 
Your CMDR name is not visible to other users of the EDDN service.

### EDSM

If you have active the option:

- 'Send flight log and CMDR status to EDSM' (on by default)

on the 'EDSM' settings tab, *and filled in valid 'Commander Name' and
'API Key' values* then this application transmits details about your
Commander to the
[Elite Dangerous Star Map](https://www.edsm.net/) (“EDSM”) website.

You can control how much of this information is visible to other people [here](https://www.edsm.net/settings/public-profile).

### Inara

If you have enabled the following configuration option:

- 'Send flight log and CMDR status to Inara' (on by default)

on the 'Inara' settings tab, *and filled in a valid 'API Key' value* then
this application transmits details about your Commander to the
[Inara](https://inara.cz/) website.

You can control how much of this information is visible to other people [here](https://inara.cz/settings/).

## Plugins

If you have installed any [plugins](https://github.com/EDCD/EDMarketConnector/wiki/Plugins) this app makes 
your CMDR details available to those plugins. Plugins run as code on your computer and can access any data EDMC
can access. Only install plugins you trust. You are responsible for protecting your local system.

## Changes to this Policy

This policy may be updated as the software evolves. Material changes will be documented in the project changelog.

Users are also encouraged to review this document from time to time to stay informed of any changes. This privacy policy can be 
found in [EDMC's Documentation Folder](/docs/PRIVACY.md).
