# -*- coding: utf-8 -*-
import json


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self.payload
