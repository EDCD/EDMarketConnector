# Kill Switches

EDMarketConnector implements a Kill Switch system that allows us to disable
features based on a version mask. Meaning that we can stop major bugs from
affecting the services we support, at the expense of disabling that support.

## Format

Killswitches are stored in a JSON file that is queried by EDMC on startup.
The format is as follows:

|             Key |   Type   | Description                                                                                  |
| --------------: | :------: | :------------------------------------------------------------------------------------------- |
|       `version` |  `int`   | the version of the Kill Switch JSON file, always 2, 1 exists and will be upgraded if needed. |
|  `last_updated` | `string` | When last the kill switches were updated (for human use only)                                |
| `kill_switches` | `array`  | The kill switches this file contains (expanded below)                                        |

The `kill_switches` array contains kill switch objects. Each contains the
following fields:

|       Key |             Type              | Description                                                                  |
| --------: | :---------------------------: | :--------------------------------------------------------------------------- |
| `version` | `version spec (see Versions)` | The version of EDMC these kill switches apply to (Must be valid semver spec) |
|   `kills` |    `Dict[str, Dict[...]]`     | The various keys disabled -> definition of the killswitch behaviour          |

Each entry in `kills` must contain at least a `reason` field describing why the
killswitch was added. EDMC will show this to the user
(for internal killswitches, anyway).

| Key (* = required) |       Type       | Description                                                                                   |
| -----------------: | :--------------: | :-------------------------------------------------------------------------------------------- |
|          `reason`* |      `str`       | The reason that this killswitch was added                                                     |
|       `set_fields` | `Dict[str, Any]` | A map of key -> contents to update (or overwrite) existing data with                          |
|    `redact_fields` |   `List[str]`    | A list of traversal paths to redact. This is the same as using set with a value of "REDACTED" |
|    `delete_fields` |   `List[str]`    | A list of traversal paths in the matching event to be removed, if they exist.                 |

The order listed above is the precedence for actions. i.e. All set fields are
set, then all redact fields are redacted then all delete fields are deleted.

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

- `plugins.edsm.send` will have fields deleted, set, and redacted, and then
  will *not* be halted, the send will continue with the modified data.
- `plugins.some_plugin.some_thing` will never be allowed to continue
  (as all fields are blank)

Indexing of lists (and any other `Sequence`) is done with numbers as normal.
Negative numbers do work to reference the end of sequences.

### Traversal paths

`set_fields`, `delete_fields`, and `redact_fields` all accept a single traversal
path to target particular fields.

When following paths, there are some caveats one should know.

- If a field (for example `a.b`) exists in the data dict
  (ie, `{'a.b': True}`) it will be the thing accessed by a killswitch that
  includes `a.b` at the current "level". This means that if both a key `a.b`
  and a nested key exist with the same name (`{'a.b': 0, 'a': { 'b': 1 }}`),
  the former is always referenced. No backtracking takes place to attempt to
  resolve conflicts, even if the dotted field name is not at the end of a key.

- Traversal can and will error, especially if you attempt to pass though keys
  that do not exist (eg past the end of a `Sequence` or a key that does not
  exist in a `Mapping`).

- If any exception occurs during your traversal, **the entire killswitch is**
  **assumed to be faulty, and will be treated as a permanent killswitch**

### Individual action rules

All actions (as noted above) can fail during traversal to their targets. If this
happens, the entire killswitch is assumed to be a permanent one and execution
stops.

#### Deletes

For both `MutableMapping` and `MutableSequence` targets, deletes never fail.
If a key doesn't exist it simply is a no-op.

#### Sets

Sets always succeed for `MutableMapping` objects, either creating new keys
or updating existing ones. For `MutableSequence`s, however, a set can fail if
the index is not within `len(target)`. If the index is exactly `len(target)`,
`append` is used.

You can set values other than strings, but you are limited to what json itself
supports, and the translation thereof to python. In general this means that only
JSON primitives and their python equivalents
(`int`, `float`, `string`, `bool`, and `None` (json `null`)), and
json compound types (`object -- {}` and `array -- []`) may be set.

### Testing

Killswitch files can be tested using the script in `scripts/killswitch_test.py`.
Providing a file as an argument or `-` for stdin will output the behaviour of
the provided file, including indicating typos, if applicable.

### Versions

Versions are checked using contains checks on `semantic_version.SimpleSpec`
instances. SimpleSpec supports both specific versions (`1.2.3`), non-specific
ranges (`1.0` will match `1.0.1` and `1.0.5` etc), wildcards (`1.2.*`),
and ranges (`<1.0.0`, `>=2.0.0`)

## Plugin support

Plugins may use the killswitch system simply by hosting their own version of the
killswitch file, and fetching it using
`killswitch.get_kill_switches(target='https://example.com/myplugin_killswitches.json')`.
The returned object can be used to query the kill switch set, see the docstrings
for more information on specifying versions.

A helper method `killswitch.get_kill_switch_thread` is provided to allow for
simple nonblocking requests for KillSwitches. It starts a new thread, performs
the HTTP request, and sends the results to the given callback.

**Note that your callback is invoked off-thread. Take precaution for locking**
**if required, and do _NOT_ use tkinter methods**

The version of the JSON file will be automatically upgraded if possible by the
code KillSwitch code. No behaviour changes will occur, any killswitches defined
in older versions will simply become unconditional kills in the new version.

## Currently supported killswitch strings

The current recognised (to EDMC and its internal plugins) killswitch strings are
as follows:

| Kill Switch                                  |    Supported Plugins    | Description                                                                               |
| :------------------------------------------- | :---------------------: | :---------------------------------------------------------------------------------------- |
| `plugins.eddn.send`                          |          eddn           | Disables all use of the send method on EDDN (effectively disables EDDN updates)           |
| `plugins.<plugin>.journal`                   | eddn, inara, edsm, eddb | Disables all journal processing for the plugin                                            |
| `plugins.<plugin>.worker`                    |      edsm, *inara       | Disables the plugins worker thread (effectively disables updates) (does not close thread) |
| `plugins.<plugin>.worker.<eventname>`        |       edsm, inara       | Disables the plugin worker for the given eventname                                        |
| `plugins.<plugin>.journal.event.<eventname>` |    eddn, inara, edsm    | Specific events to disable processing for.                                                |

Killswitches marked with `*` do **not** support modification of their values via
set/redact/delete. And as such any match will simply stop processing.

For `plugin.inara.worker`, events are checked individually later by the
eventname version. Use that to modify individual inara events. This is due to
inara event batching meaning that the data that would be passed to `.worker`
would not be in a form that could be easily understood (except to blank it)

## File location

The main killswitch file (`killswitches_v2.json`) is kept in the `releases`
branch on the EDMC github repo. The file should NEVER be committed to any other
repos. In the case that the killswitch file is found in other repos, the one in
releases should always be taken as correct regardless of others.

## In depth example

In a hypothetical situation where we have released version 1.0.0 with a bug that
means `FSDJump` events are not correctly stripped of extraneous data, such as
the user specific `HomeSystem` field in the `Factions` object.

The simplest way to go about this is to remove the field whenever the event is
passed to `eddn.py`s `journal_entry` function.

`journal_entry` checks against both `plugins.eddn.journal` and
`plugins.eddn.journal.event.<eventname>`. As we just want to modify a single
events handling, we can use the latter form.

The killswitch definition is as follows (this is just for this hypothetical,
it is not a full valid file, see below)

```json
{
  "plugins.eddn.journal.event.FSDJump": {
    "reason": "EDMC Does not correctly strip the user specific HomeSystem field from Factions",
    "delete_fields": ["Factions.HomeSystem"]
  }
}
```

This can be slotted into a full killswitch (using a modified version of the
example at the top of this file)

```json
{
    "version": 2,
    "last_updated": "23 August 2021",
    "kill_switches": [{
        "version": "1.0.0",
        "kills": {
          "plugins.eddn.journal.event.FSDJump": {
            "reason": "EDMC 1.0.0 Does not correctly strip the user specific HomeSystem field from Factions",
            "delete_fields": ["Factions.HomeSystem"]
          }
        }
    }]
}
Running the above example though `killswitch_test.py` returns:

```plaintext
Kills matching version mask 1.0.0
        - plugins.eddn.journal.event.FSDJump
                Reason specified is: 'EDMC Does not correctly strip the user specific HomeSystem field from Factions'

                The folowing changes are required for plugins.eddn.journal.event.FSDJump execution to continue
                Deletes 1 fields:
                        - Factions.HomeSystem
```

Telling us that we have not made any typos, and that our killswitch matches the
expected version, and does the expected actions.

Now that we're sure that everything is right, we can place this in the correct
location (see above for paths). Once there, EDMC instances will begin to behave
as expected, filtering out the field during EDDN processing.
