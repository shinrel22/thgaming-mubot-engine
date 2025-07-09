import json
from datetime import datetime, date, time


class CustomJsonEncoder(json.JSONEncoder):
    def default(self, o: any) -> any:
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        return super(CustomJsonEncoder, self).default(o)
