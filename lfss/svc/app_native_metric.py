from fastapi import Depends
from typing import Literal
from ..eng.datatype import UserRecord
from ..eng.request_log import RequestDB
from .app_base import *

@router_metric.get("/http-traffic")
@handle_exception
async def get_http_traffic(
    resolution: Literal['minute', 'hour', 'day'],
    time: int,
    count: int = 1,
    user: UserRecord = Depends(registered_user)
    ):
    t = await RequestDB().get_traffics(resolution, time, count)
    return t if user.is_admin else [x.desensitize() for x in t]
