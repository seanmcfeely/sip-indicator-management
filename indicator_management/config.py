"""Configuration related items.
"""

import os
import sys
import stat
import logging
import tzlocal


from datetime import datetime
from configparser import ConfigParser

LOGGER = logging.getLogger("indicator_management.config")

# path to sip-indicator-management/indicator_management/
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))

# path to sip-indicator-management/
HOME_PATH = os.path.dirname(PROJECT_PATH)

# Required directories
REQUIRED_DIRS = ["logs", "var", "etc"]
for path in [os.path.join(HOME_PATH, x) for x in REQUIRED_DIRS]:
    if not os.path.isdir(path):
        try:
            os.mkdir(path)
        except Exception as e:
            sys.stderr.write("ERROR: cannot create directory {0}: {1}\n".format(path, str(e)))
            sys.exit(1)


# Create the config file from template if it does not already exist
default_config_path = os.path.join(HOME_PATH, "etc", "config.ini")
template_config_path = os.path.join(PROJECT_PATH, "etc", "template.config.ini")
if not os.path.exists(default_config_path):
    import shutil
    shutil.copyfile(template_config_path, default_config_path)

# Allow for additional config flexibility
user_config_path = os.path.join(os.path.expanduser("~"), ".config", "sip", "indicator_management.ini")
CONFIG_SEARCH_PATHS = [
    default_config_path,
    "/etc/sip/indicator_management.ini",
    user_config_path,
]

CONFIG = ConfigParser()
CONFIG.optionxform = str  # preserve case
CONFIG.read(CONFIG_SEARCH_PATHS)
