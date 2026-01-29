# Available Traces
This file was last updated on 2026-01-27.
This document lists all of the available `--trace-on` options to enable additional debug logging.

| Trace Key                         | Enables Log Message                                                                                                             | Source Location           |
|-----------------------------------|---------------------------------------------------------------------------------------------------------------------------------|---------------------------|
| `CMDR_CREDS`                      | `f'cmdr={cmdr!r}'`                                                                                                              | plugins\edsm.py:455       |
| `CMDR_CREDS`                      | `f'cmdr={cmdr!r}: returning (edsm_usernames[idx]={edsm_usernames[idx]!r}, edsm_apikeys[idx]={edsm_apikeys[idx]!r})'`            | plugins\edsm.py:487       |
| `CMDR_CREDS`                      | `f'cmdr={cmdr!r}: returning None'`                                                                                              | plugins\edsm.py:490       |
| `CMDR_EVENTS`                     | `f'"LoadGame" event, queueing Materials: cmdr={cmdr!r}'`                                                                        | plugins\edsm.py:618       |
| `CMDR_EVENTS`                     | `f""""entry["event"]={entry['event']!r}" event, queueing: cmdr={cmdr!r}"""`                                                     | plugins\edsm.py:626       |
| `CMDR_EVENTS`                     | `f"""De-queued (cmdr={cmdr!r}, game_version={game_version!r}, game_build={game_build!r}, entry["event"]={entry['event']!r})"""` | plugins\edsm.py:805       |
| `CMDR_EVENTS`                     | `f"""(cmdr={cmdr!r}, entry["event"]={entry['event']!r}): not in discarded_events, appending to pending"""`                      | plugins\edsm.py:828       |
| `CMDR_EVENTS`                     | `f"""(cmdr={cmdr!r}, entry["event"]={entry['event']!r}): should_send() said True"""`                                            | plugins\edsm.py:855       |
| `CMDR_EVENTS`                     | `f'pending contains:\n{chr(10).join((str(p) for p in pending))}'`                                                               | plugins\edsm.py:856       |
| `CMDR_EVENTS`                     | `f"""(cmdr={cmdr!r}, entry["event"]={entry['event']!r}): Using username={username!r} from credentials()"""`                     | plugins\edsm.py:874       |
| `CMDR_EVENTS`                     | `f"Blanked pending because of event: {entry['event']}"`                                                                         | plugins\edsm.py:923       |
| `CMDR_EVENTS`                     | `f'True because event={event!r}'`                                                                                               | plugins\edsm.py:960       |
| `CMDR_EVENTS`                     | `f'False because this.navbeaconscan={this.navbeaconscan!r}' if not should_send_result else ''`                                  | plugins\edsm.py:967       |
| `CMDR_EVENTS`                     | `f'False as default: this.newgame_docked={this.newgame_docked!r}' if not should_send_result else ''`                            | plugins\edsm.py:974       |
| `STARTUP`                         | `f""""Commander" event, monitor.cmdr={monitor.cmdr!r}, monitor.state["FID"]={monitor.state['FID']!r}"""`                        | monitor.py:594            |
| `STARTUP`                         | `f""""LoadGame" event, monitor.cmdr={monitor.cmdr!r}, monitor.state["FID"]={monitor.state['FID']!r}"""`                         | monitor.py:645            |
| `capi.auth.refresh`               | `f'Found CMDRs: {cmdrs} in config.'`                                                                                            | companion.py:327          |
| `capi.auth.refresh`               | `f'Found tokens: {tokens} in config.'`                                                                                          | companion.py:336          |
| `capi.auth.refresh`               | `f'Session Data: {r.json()}'`                                                                                                   | companion.py:352          |
| `capi.auth.refresh`               | `f'Status Code: {r.status_code}'`                                                                                               | companion.py:353          |
| `capi.auth.refresh`               | `f'Token Data: {token_data}'`                                                                                                   | companion.py:356          |
| `capi.auth.refresh`               | `f'Challenge: {challenge}'`                                                                                                     | companion.py:375          |
| `capi.auth.refresh`               | `f'OAuth callback params: {data}'`                                                                                              | companion.py:396          |
| `capi.auth.refresh`               | `f'Token Data: {data_token}'`                                                                                                   | companion.py:421          |
| `capi.auth.refresh`               | `f'Decode Token: {data_decode}'`                                                                                                | companion.py:433          |
| `capi.worker`                     | `f'Sending HTTP request for {capi_endpoint} ...'`                                                                               | companion.py:734          |
| `capi.worker`                     | `'... got result...'`                                                                                                           | companion.py:745          |
| `capi.worker`                     | `'De-queued request'`                                                                                                           | companion.py:917          |
| `capi.worker`                     | `f'Processing query: {query.endpoint}'`                                                                                         | companion.py:926          |
| `capi.worker`                     | `'Sending <<CAPIResponse>>'`                                                                                                    | companion.py:962          |
| `capi.worker`                     | `'Enqueueing request'`                                                                                                          | companion.py:995          |
| `capi.worker`                     | `'Enqueueing Fleet Carrier request'`                                                                                            | companion.py:1024         |
| `capi.worker`                     | `'Begin'`                                                                                                                       | EDMarketConnector.py:1119 |
| `capi.worker`                     | `'Aborting Query: Cmdr unknown'`                                                                                                | EDMarketConnector.py:1134 |
| `capi.worker`                     | `'Aborting Query: Game Mode unknown'`                                                                                           | EDMarketConnector.py:1140 |
| `capi.worker`                     | `'Aborting Query: GameVersion unknown'`                                                                                         | EDMarketConnector.py:1146 |
| `capi.worker`                     | `'Aborting Query: Current star system unknown'`                                                                                 | EDMarketConnector.py:1152 |
| `capi.worker`                     | `'Aborting Query: In multi-crew'`                                                                                               | EDMarketConnector.py:1158 |
| `capi.worker`                     | `'Aborting Query: In CQC'`                                                                                                      | EDMarketConnector.py:1164 |
| `capi.worker`                     | `'Auth in progress? Aborting query'`                                                                                            | EDMarketConnector.py:1170 |
| `capi.worker`                     | `'Requesting full station data'`                                                                                                | EDMarketConnector.py:1192 |
| `capi.worker`                     | `'Calling companion.session.station'`                                                                                           | EDMarketConnector.py:1194 |
| `capi.worker`                     | `'Begin'`                                                                                                                       | EDMarketConnector.py:1209 |
| `capi.worker`                     | `'Aborting Query: Cmdr unknown'`                                                                                                | EDMarketConnector.py:1222 |
| `capi.worker`                     | `'Aborting Query: GameVersion unknown'`                                                                                         | EDMarketConnector.py:1228 |
| `capi.worker`                     | `'Requesting Fleet Carrier data'`                                                                                               | EDMarketConnector.py:1243 |
| `capi.worker`                     | `'Calling companion.session.fleetcarrier'`                                                                                      | EDMarketConnector.py:1245 |
| `capi.worker`                     | `'Handling response'`                                                                                                           | EDMarketConnector.py:1256 |
| `capi.worker`                     | `'Pulling answer off queue'`                                                                                                    | EDMarketConnector.py:1262 |
| `capi.worker`                     | `f'Failed Request: {capi_response.message}'`                                                                                    | EDMarketConnector.py:1265 |
| `capi.worker`                     | `'Answer is not a Failure'`                                                                                                     | EDMarketConnector.py:1271 |
| `capi.worker`                     | `'Raising CmdrError()'`                                                                                                         | EDMarketConnector.py:1326 |
| `capi.worker`                     | `'Updating suit and cooldown...'`                                                                                               | EDMarketConnector.py:1502 |
| `capi.worker`                     | `'...done'`                                                                                                                     | EDMarketConnector.py:1506 |
| `capi.worker`                     | `f'Failed Request: {capi_response.message}'`                                                                                    | EDMC.py:313               |
| `capi.worker`                     | `'Answer is not a Failure'`                                                                                                     | EDMC.py:318               |
| `frontier-auth`                   | `f'Payload: {self.lastpayload}'`                                                                                                | protocol.py:50            |
| `frontier-auth.http`              | `f'Got message on path: {self.path}'`                                                                                           | protocol.py:400           |
| `frontier-auth.windows`           | `'Begin...'`                                                                                                                    | EDMarketConnector.py:286  |
| `frontier-auth.windows`           | `f'DDE message of type: {msg.message}'`                                                                                         | protocol.py:281           |
| `frontier-auth.windows`           | `f'args are: {args}'`                                                                                                           | protocol.py:291           |
| `journal-lock`                    | `f'journal_dir_lockfile_name = {self.journal_dir_lockfile_name!r}'`                                                             | journal_lock.py:62        |
| `journal-lock`                    | `'win32, using msvcrt'`                                                                                                         | journal_lock.py:101       |
| `journal-lock`                    | `'NOT win32, using fcntl'`                                                                                                      | journal_lock.py:114       |
| `journal-lock`                    | `'Done'`                                                                                                                        | journal_lock.py:134       |
| `journal-lock`                    | `'win32, using msvcrt'`                                                                                                         | journal_lock.py:150       |
| `journal-lock`                    | `'NOT win32, using fcntl'`                                                                                                      | journal_lock.py:167       |
| `journal-lock`                    | `'User selected: Ignore'`                                                                                                       | journal_lock.py:246       |
| `journal-lock`                    | `'User force-closed popup, treating as Ignore'`                                                                                 | journal_lock.py:252       |
| `journal-lock`                    | `f'We should retry: {retry}'`                                                                                                   | journal_lock.py:282       |
| `journal-lock_if`                 | `'User selected: Retry'`                                                                                                        | journal_lock.py:240       |
| `journal.continuation`            | `'****'`                                                                                                                        | monitor.py:453            |
| `journal.continuation`            | `'Found a Continue event, its being added to the list, we will finish this file up and then continue with the next'`            | monitor.py:454            |
| `journal.file`                    | `'****'`                                                                                                                        | monitor.py:468            |
| `journal.loadgame.cqc`            | `f'loadgame to cqc: {entry}'`                                                                                                   | monitor.py:605            |
| `journal.locations`               | `'"Location" event in the past at startup'`                                                                                     | monitor.py:381            |
| `journal.locations`               | `'"Location" event'`                                                                                                            | monitor.py:965            |
| `journal.locations`               | `'"Location" event'`                                                                                                            | monitor.py:2178           |
| `journal.locations`               | `'Notifying plugins of "Location" event'`                                                                                       | plug.py:366               |
| `journal.locations`               | `f"{entry['event']}\nCommander: {cmdr}\nSystem: {system}\nStation: {station}\nstate: {state!r}\nentry: {entry!r}"`              | plugins\edsm.py:529       |
| `journal.locations`               | `f"{entry['event']}\nQueueing: {entry!r}"`                                                                                      | plugins\edsm.py:622       |
| `journal.locations`               | `"pending has at least one of ('CarrierJump', 'FSDJump', 'Location', 'Docked') and it passed should_send()"`                    | plugins\edsm.py:859       |
| `journal.locations`               | `f""""Location" event in pending passed should_send(), timestamp: {p['timestamp']}"""`                                          | plugins\edsm.py:864       |
| `journal.locations`               | `"pending has at least one of ('CarrierJump', 'FSDJump', 'Location', 'Docked') Attempting API call with the following events:"` | plugins\edsm.py:893       |
| `journal.locations`               | `f'Event: {p!r}'`                                                                                                               | plugins\edsm.py:899       |
| `journal.locations`               | `f"""Attempting API call for "Location" event with timestamp: {p['timestamp']}"""`                                              | plugins\edsm.py:901       |
| `journal.locations`               | `f'Overall POST data (elided) is:\n{json.dumps(data_elided, indent=2)}'`                                                        | plugins\edsm.py:905       |
| `journal.queue`                   | `'No entry from monitor.get_entry()'`                                                                                           | EDMarketConnector.py:1551 |
| `journal.queue`                   | `'Startup, returning'`                                                                                                          | EDMarketConnector.py:1641 |
| `journal.queue`                   | `'Sending <<JournalEvent>>'`                                                                                                    | monitor.py:461            |
| `journal.queue`                   | `'Sending <<JournalEvent>>'`                                                                                                    | monitor.py:500            |
| `journal.queue`                   | `'Begin'`                                                                                                                       | monitor.py:2169           |
| `journal.queue`                   | `'event_queue NOT empty'`                                                                                                       | monitor.py:2174           |
| `plugin.eddn.fsssignaldiscovered` | `f'Appending FSSSignalDiscovered entry:\n {json.dumps(entry)}'`                                                                 | plugins\eddn.py:1750      |
| `plugin.eddn.fsssignaldiscovered` | `f'This other event is: {json.dumps(entry)}'`                                                                                   | plugins\eddn.py:1766      |
| `plugin.eddn.fsssignaldiscovered` | `'USSType is $USS_Type_MissionTarget;, dropping'`                                                                               | plugins\eddn.py:1817      |
| `plugin.eddn.fsssignaldiscovered` | `f'FSSSignalDiscovered batch is {json.dumps(msg)}'`                                                                             | plugins\eddn.py:1842      |
| `plugin.eddn.send`                | `f'First queue run scheduled for {self.eddn.REPLAY_STARTUP_DELAY}ms from now'`                                                  | plugins\eddn.py:177       |
| `plugin.eddn.send`                | `f"Message for msg['$schemaRef']={msg['$schemaRef']!r}"`                                                                        | plugins\eddn.py:248       |
| `plugin.eddn.send`                | `f"Message for msg['$schemaRef']={msg['$schemaRef']!r} recorded, id={self.db.lastrowid}"`                                       | plugins\eddn.py:287       |
| `plugin.eddn.send`                | `f'Deleting message with row_id={row_id!r}'`                                                                                    | plugins\eddn.py:296       |
| `plugin.eddn.send`                | `f'Sending message with id={id!r}'`                                                                                             | plugins\eddn.py:312       |
| `plugin.eddn.send`                | `'Sending message'`                                                                                                             | plugins\eddn.py:361       |
| `plugin.eddn.send`                | `'Called'`                                                                                                                      | plugins\eddn.py:424       |
| `plugin.eddn.send`                | `"Couldn't obtain mutex"`                                                                                                       | plugins\eddn.py:427       |
| `plugin.eddn.send`                | `f'Next run scheduled for {self.eddn.REPLAY_PERIOD}ms from now'`                                                                | plugins\eddn.py:429       |
| `plugin.eddn.send`                | `'NO next run scheduled (there should be another one already set)'`                                                             | plugins\eddn.py:438       |
| `plugin.eddn.send`                | `'Obtained mutex'`                                                                                                              | plugins\eddn.py:444       |
| `plugin.eddn.send`                | `'Should send'`                                                                                                                 | plugins\eddn.py:449       |
| `plugin.eddn.send`                | `f'Next run scheduled for {self.eddn.REPLAY_DELAY}ms from now'`                                                                 | plugins\eddn.py:485       |
| `plugin.eddn.send`                | `'Should NOT send'`                                                                                                             | plugins\eddn.py:493       |
| `plugin.eddn.send`                | `'Mutex released'`                                                                                                              | plugins\eddn.py:496       |
| `plugin.eddn.send`                | `f'Next run scheduled for {self.eddn.REPLAY_PERIOD}ms from now'`                                                                | plugins\eddn.py:499       |
| `plugin.eddn.send`                | `"Recording/sending 'station' message"`                                                                                         | plugins\eddn.py:997       |
| `plugin.eddn.send`                | `"Recording 'non-station' message"`                                                                                             | plugins\eddn.py:1007      |
| `plugin.eddn.send`                | `"Sending 'non-station' message"`                                                                                               | plugins\eddn.py:1014      |
| `plugin.edsm.api`                 | `f'API response content: {response.content!r}'`                                                                                 | plugins\edsm.py:716       |
| `plugin.edsm.api`                 | `'Overall OK'`                                                                                                                  | plugins\edsm.py:756       |
| `plugin.edsm.api`                 | `'Event(s) not currently processed, but saved for later'`                                                                       | plugins\edsm.py:759       |
| `plugin.inara.events`             | `f'Events:\n{json.dumps(data)}\n'`                                                                                              | plugins\inara.py:1538     |
| `tk`                              | `f'Default tk scaling = {theme.default_ui_scale}'`                                                                              | EDMarketConnector.py:2365 |
