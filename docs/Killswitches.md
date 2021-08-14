# Kill Switches

EDMarketConnector implements a Kill Switch system that allows us to disable features based on a version mask. Meaning that we can stop major bugs from affecting the services we support, at the expense of disabling that support.

## Format

Killswitches are stored in a JSON file that is queried by EDMC on startup. The format is as follows:

|             Key |   Type   | Description                                                                                  |
| --------------: | :------: | :------------------------------------------------------------------------------------------- |
|       `version` |  `int`   | the version of the Kill Switch JSON file, always 2, 1 exists and will be upgraded if needed. |
|  `last_updated` | `string` | When last the kill switches were updated (for human use only)                                |
| `kill_switches` | `array`  | The kill switches this file contains (expanded below)                                        |

The `kill_switches` array contains kill switch objects. Each contains the following fields:

|       Key |             Type              | Description                                                                  |
| --------: | :---------------------------: | :--------------------------------------------------------------------------- |
| `version` | `version spec (see Versions)` | The version of EDMC these kill switches apply to (Must be valid semver spec) |
|   `kills` |    `Dict[str, Dict[...]]`     | The various keys disabled -> definition of the killswitch behaviour          |

Each entry in `kills` must contain at least a `reason` field describing why the killswitch was added. EDMC will show
this to the user (for internal killswitches, anyway).

| Key (* = required) |       Type       | Description                                                                                   |
| -----------------: | :--------------: | :-------------------------------------------------------------------------------------------- |
|          `reason`* |      `str`       | The reason that this killswitch was added                                                     |
|       `set_fields` | `Dict[str, Any]` | A map of key -> contents to update (or overwrite) existing data with                          |
|    `redact_fields` |   `List[str]`    | A list of fields to redact. This is equivalent to setting the fields to the string "REDACTED" |
|    `delete_fields` |   `List[str]`    | A list of fields in the matching event to be removed, if they exist.                          |

The order listed above is the precedence for actions. i.e. All set fields are set, then all redact fields are redacted
then all delete fields are deleted.

An example follows:

```json
{
    "version": 2,
    "last_updated": "3 July 2021",
    "kill_switches": [
        {
            "version": "1.0.0",
            "kills": {
                "plugins.eddn.send": {
                    "reason": "some reason",
                    "delete_fields": ["world_domination_plans"],
                    "set_fields": {
                        "bad_bases_for_systems_of_government": ["Strange women lying in ponds distributing swords"],
                        "ruler_map": {"emperor": "scimitar"}
                    },
                    "redact_fields": ["relation_to_thargoids"]
                },
                "plugins.some_plugin.some_thing": {
                    "reason": "Some thing is disabled pending investigation of NMLA relations."
                }
            }
        }
    ]
}
```

- `plugins.edsm.send` will have fields deleted, set, and redacted, and then will *not* be halted, the send will continue with the modified data.
- `plugins.some_plugin.some_thing` will never be allowed to continue (as all fields are blank)


### Versions

Versions are checked using contains checks on `semantic_version.SimpleSpec` instances. SimpleSpec supports both specific
versions (`1.2.3`), non-specific ranges (`1.0` will match `1.0.1` and `1.0.5` etc), wildcards (`1.2.*`),
and ranges (`<1.0.0`, `>=2.0.0`)

## Plugin support

Plugins may use the killswitch system simply by hosting their own version of the killswitch file, and fetching it
using `killswitch.get_kill_switches(target='https://example.com/myplugin_killswitches.json')`. The returned object can
be used to query the kill switch set, see the docstrings for more information on specifying versions.

The version of the JSON file will be automatically upgraded if possible by the code KillSwitch code. No behaviour changes will occur--Any killswitches defined in older
 versions will simply become unconditional kills in the new version.

## Currently supported killswitch strings

The current recognised (to EDMC and its internal plugins) killswitch strings are as follows:

| Kill Switch                                  |    Supported Plugins    | Description                                                                               |
| :------------------------------------------- | :---------------------: | :---------------------------------------------------------------------------------------- |
| *`plugins.eddn.send`                         |          eddn           | Disables all use of the send method on EDDN (effectively disables EDDN updates)           |
| `plugins.<plugin>.journal`                   | eddn, inara, edsm, eddb | Disables all journal processing for the plugin                                            |
| `plugins.<plugin>.worker`                    |       edsm, inara       | Disables the plugins worker thread (effectively disables updates) (does not close thread) |
| `plugins.<plugin>.worker.<eventname>`        |       edsm, inara       | Disables the plugin worker for the given eventname                                        |
| `plugins.<plugin>.journal.event.<eventname>` |    eddn, inara, edsm    | Specific events to disable processing for.                                                |

Killswitches marked with `*` do **not** support modification of their values via set/redact/delete. And as such any match
will simply stop processing.

## File location

The main killswitch file is kept in the `releases` branch on the EDMC github repo. The file should NEVER be committed to
any other repos. In the case that the killswitch file is found in other repos, the one in releases should always
be taken as correct regardless of others.
