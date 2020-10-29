# Kill Switches

EDMarketConnector implements a Kill Switch system that allows us to disable features based on a version mask. Meaning that we can stop major bugs from affecting the services we support, at the expense of disabling that support.

## Format

Killswitches are stored in a JSON file that is queried by EDMC on startup. The format is as follows:

|             Key |   Type   | Description                                                   |
| --------------: | :------: | :------------------------------------------------------------ |
|       `version` |  `int`   | the version of the Kill Switch JSON file, always 1            |
|  `last_updated` | `string` | When last the kill switches were updated (for human use only) |
| `kill_switches` | `array`  | The kill switches this file contains (expanded below)         |

The `kill_switches` array contains kill switch objects. Each contains two fields:

|       Key |       Type       | Description                                                                  |
| --------: | :--------------: | :--------------------------------------------------------------------------- |
| `version` |  `version spec`  | The version of EDMC these kill switches apply to (Must be valid semver spec) |
|   `kills` | `Dict[str, str]` | The different keys to disable, and the reason for the disable                |
An example follows:

```json
{
    "version": 1,
    "last_updated": "19 October 2020",
    "kill_switches": [
        {
            "version": "1.0.0",
            "kills": {
                "plugins.eddn.send": "some reason"
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

## Currently supported killswitch strings

The current recognised (to EDMC and its internal plugins) killswitch strings are as follows:
| Kill Switch                                          | Description                                                                                  |
| :--------------------------------------------------- | :------------------------------------------------------------------------------------------- |
| `plugins.eddn.send`                                  | Disables all use of the send method on EDDN (effectively disables EDDN updates)              |
| `plugins.(eddn|inara|edsm|eddb).journal`             | Disables all journal processing for EDDN/EDSM/INARA                                          |
| `plugins.(edsm|inara).worker`                        | Disables the EDSM/INARA worker thread (effectively disables updates) (does not close thread) |
| `plugins.(eddn|inara|edsm).journal.event.$eventname` | Specific events to disable processing for                                                    |
