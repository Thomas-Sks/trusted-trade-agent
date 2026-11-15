import logging

from ttap.adapters.inbound.rest_api import create_app
from ttap.bootstrap import build_live

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs full URLs, which contain the Telegram bot token
_live = build_live()
app = create_app(_live.services, _live.agent_keys, _live.approver_keys, lifecycle=_live.lifecycle)
