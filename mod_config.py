"""
parse config
    * getConfig(section) import whole section
    * getConfig(section, key) import value the key points to
"""
import configparser
import os
CONFIG_FILENAME = 'dns.conf'


def get_config(section, key=None):
    """
    getConfig(section, key=None)
    """
    config = configparser.ConfigParser()
    path = os.path.split(os.path.realpath(__file__))[0] + '/' + CONFIG_FILENAME
    config.read(path)
    if key is None:
        return config.items(section)
    else:
        return config.get(section, key)
