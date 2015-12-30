# twitter client - Ian Norton
import sys
try:
    from twitter import Twitter, OAuth
except ImportError:
    Twitter = None
    UserPassAuth = None

from config import config


def _set_status(message):
    """
    Set our twitter status
    :param message:
    :return:
    """
    if Twitter is not None:
        try:
            if not _set_status.twclient:
                con_key = config.get("twit_consumer_key")
                con_sec = config.get("twit_consumer_secret")
                acc_tok = config.get("twit_access_token")
                acc_sec = config.get("twit_access_secret")
                if con_key and con_sec and acc_tok and acc_sec:
                    _set_status.twclient = Twitter(auth=OAuth(
                        acc_tok, acc_sec, con_key, con_sec))
            if _set_status.twclient:
                _set_status.twclient.statuses.update(status=message)
        except Exception as err:
            print >> sys.stderr, err
_set_status.twclient = None


def systemchanged(system):
    """
    Tweet when our star system has changed
    :param system:
    :return:
    """
    _set_status('at ' + system)


def stationchanged(system, station):
    """
    Tweet if we've arrived at a station
    :param system:
    :param station:
    :return:
    """
    if stationchanged.last[0] != system:
        if stationchanged.last[1] != station:
            _set_status('docked at ' + station + ' in the ' + system + ' system')
    stationchanged.last = [system, station]
stationchanged.last = [None, None]

if __name__ == "__main__":
    stationchanged("testsystem", "teststation")