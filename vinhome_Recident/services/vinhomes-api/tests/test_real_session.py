import asyncio
import json
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from vinhomes_api.v3_auth import _actor_id
from vinhomes_api.v3_config import V3Settings


def settings():
    return V3Settings("127.0.0.1", 8000, None, UUID("22222222-2222-5222-a222-222222222222"), "http://127.0.0.1:3001/api/auth/get-session", None)


@pytest.mark.parametrize("payload,status", [(None,401), ({"user":None},401), ({"unexpected":True},401), ({"user":{"id":None}},503)])
def test_invalid_or_missing_session_never_becomes_a_demo_actor(payload, status):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,*args,**kwargs): return httpx.Response(200,content=json.dumps(payload),headers={"content-type":"application/json"})
    request = Request({"type":"http","headers":[(b"x-demo-actor",b"admin")],"client":("127.0.0.1",1)})
    with patch("vinhomes_api.v3_auth.httpx.AsyncClient",return_value=Client()):
        with pytest.raises(HTTPException) as error:
            asyncio.run(_actor_id(request,settings()))
        assert error.value.status_code == status


def test_real_session_uses_authenticated_user_ignoring_demo_header():
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,headers):
            assert headers == {"cookie":"session=opaque"}
            return httpx.Response(200,json={"user":{"id":"authenticated-user"}})
    request = Request({"type":"http","headers":[(b"cookie",b"session=opaque"),(b"x-demo-actor",b"admin")],"client":("127.0.0.1",1)})
    with patch("vinhomes_api.v3_auth.httpx.AsyncClient",return_value=Client()):
        assert asyncio.run(_actor_id(request,settings())) == "authenticated-user"
