from ttap.adapters.inbound.rest_api import create_app
from ttap.bootstrap import build_live

_services, _keys = build_live()
app = create_app(_services, _keys)
