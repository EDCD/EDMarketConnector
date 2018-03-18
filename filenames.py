"Functions to handle filenames responsibly."

import re

def slugify(shipname):
    "Remove or transform parts of a ship name likely to hurt a filename."
    sanitised = re.sub(r'[^\w\s-]', '', shipname)
    consolidated = re.sub(r'[-\s]+', '-', sanitised)
    return consolidated
