from ntplib import NTPClient
from tkMessageBox import showerror

from config import applongname

if __debug__:
    from traceback import print_exc

def NTPCheck(parent):

    DRIFT_THRESHOLD = 3 * 60
    TZ_THRESHOLD = 30 * 60
    CLOCK_THRESHOLD = 12 * 60 * 60 + DRIFT_THRESHOLD

    try:
        response = NTPClient().request('pool.ntp.org')
        if abs(response.offset) > DRIFT_THRESHOLD:
            showerror(applongname,
                      _('This app requires accurate timestamps.') + '\n' +	# Error message shown if system time is wrong
                      (TZ_THRESHOLD < abs(response.offset) < CLOCK_THRESHOLD and
                       _("Check your system's Time Zone setting.") or		# Error message shown if system time is wrong
                       _("Check your system's Date and Time settings.")),	# Error message shown if system time is wrong
                      parent = parent)
            return False
    except:
        if __debug__: print_exc()

    return True
