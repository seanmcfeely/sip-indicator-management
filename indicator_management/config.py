"""Configuration related items.
"""

import os
import stat
import logging
import tzlocal
import zoneinfo

from datetime import datetime
from configparser import ConfigParser

LOGGER = logging.getLogger("indicator_management.config")

HOME_PATH = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = os.path.dirname(HOME_PATH)

default_config_path = os.path.join(HOME_PATH, "etc", "config.ini")
if not os.path.exists(default_config_path):
    import shutil
    shutil.copyfile(os.path.join(HOME_PATH, "etc", "template.config.ini"), default_config_path)

project_config_path = os.path.join(PROJECT_PATH, "etc", "config.ini")
user_config_path = os.path.join(os.path.expanduser("~"), ".config", "sip", "indicator_management.ini")
CONFIG_SEARCH_PATHS = [
    default_config_path,
    "/etc/sip/indicator_managment.ini",
    project_config_path,
    user_config_path,
]

CONFIG = ConfigParser()
CONFIG.read(CONFIG_SEARCH_PATHS)

# local timezone
LOCAL_TIMEZONE = zoneinfo.ZoneInfo(tzlocal.get_localzone_name())

