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

|       Key |          Type          | Description                                                                  |
| --------: | :--------------------: | :--------------------------------------------------------------------------- |
| `version` |     `version spec`     | The version of EDMC these kill switches apply to (Must be valid semver spec) |
|   `kills` | `Dict[str, Dict[...]]` | The various keys disabled -> definition of the killswitch behaviour          |

Each entry in `kills` must contain at least a `reason` field describing why the killswitch was added. EDMC will show
this to the user (for internal killswitches, anyway).
| Key (* = required) |       Type       | Description                                                                                   |
| -----------------: | :--------------: | :-------------------------------------------------------------------------------------------- |
|          `reason`* |      `str`       | The reason that this killswitch was added                                                     |
|    `delete_fields` |   `List[str]`    | A list of fields in the matching event to be removed, if they exist.                          |
|       `set_fields` | `Dict[str, Any]` | A map of key -> contents to update (or overwrite) existing data with                          |
|    `redact_fields` |   `List[str]`    | A list of fields to redact. This is equivalent to setting the fields to the string "REDACTED" |

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
                }
            }
        }
    ]
}
```

### Versions

Versions are checked using contains checks on `semantic_version.SimpleSpec` instances.

## Plugin support

Plugins may use the killswitch system simply by hosting their own version of the killswitch file, and fetching it
using `killswitch.get_kill_switches(target='https://example.com/myplugin_killswitches.json')`. The returned object can
be used to query the kill switch set, see the docstrings for more information on specifying versions.

The version of the JSON file will be automatically upgraded if possible by the code KillSwitch code.

## Currently supported killswitch strings

 <!-- TODO: update this with new behaviour for various fields -->
The current recognised (to EDMC and its internal plugins) killswitch strings are as follows:
| Kill Switch                                            | Description                                                                                                                                    |
| :----------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins.eddn.send`                                    | Disables all use of the send method on EDDN (effectively disables EDDN updates)                                                                |
| `plugins.(eddn\|inara\|edsm\|eddb).journal`            | Disables all journal processing for EDDN/EDSM/INARA                                                                                            |
| `plugins.(edsm\|inara).worker`                         | Disables the EDSM/INARA worker thread (effectively disables updates) (does not close thread)                                                   |
| `plugins.(edsm\|inara).worker.$eventname`              | Disables the EDSM/INARA worker for the given eventname, OR if delete_fields exists, removes the fields from the event                          |
| `plugins.(eddn\|inara\|edsm).journal.event.$eventname` | Specific events to disable processing for. OR, if delete_fields exists as additional_data, the fields listed will be removed before processing |

## File location

The main killswitch file is kept in the `releases` branch on the EDMC github repo. The file should NEVER be committed to
any other repos. In the case that the killswitch file is found in other repos, the one in releases should always
be taken as correct regardless of others.
