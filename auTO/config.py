import logging
import sys
import yaml

try:
    with open('config.yml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logging.error('config.yml file not found')
    sys.exit(1)

if config is None or config.get('DISCORD_TOKEN') is None:
    logging.error('DISCORD_TOKEN is unset')
    sys.exit(1)
