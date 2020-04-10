import logging
import sys
import yaml

log = logging.getLogger(__name__)

try:
    with open('config.yml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    log.error('config.yml file not found')
    sys.exit(1)

if config is None or config.get('DISCORD_TOKEN') is None:
    log.error('DISCORD_TOKEN is unset')
    sys.exit(1)
