"""Optional HTTP stream primitive for evidenced C14 producer bindings.

Endpoint/credentials are supplied by trusted producer mapping, never model URLs.
Compressed bodies are rejected: identity bytes are the canonical artifact hash.
"""
import asyncio
from contextlib import asynccontextmanager
import httpx
from urllib.parse import urlsplit
from adapters.backend.errors import AdapterError


class BoundedHTTPDownload:
    def __init__(self, client, *, limit=10*1024*1024, deadline=30):
        self.client,self.limit,self.deadline=client,limit,deadline

    @asynccontextmanager
    async def stream(self, url, headers):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise AdapterError('report_download_origin_invalid')
        async with asyncio.timeout(self.deadline):
            async with self.client.stream('GET',url,headers={**headers,'Accept-Encoding':'identity'},follow_redirects=False) as response:
                if response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity':
                    raise AdapterError('report_download_transport_invalid')
                declared=response.headers.get('content-length')
                if declared is not None and (not declared.isdigit() or int(declared)>self.limit):
                    raise AdapterError('report_download_limit')
                async def chunks():
                    size=0
                    async for chunk in response.aiter_raw(chunk_size=65536):
                        size+=len(chunk)
                        if size>self.limit: raise AdapterError('report_download_limit')
                        yield chunk
                    if declared is not None and size!=int(declared):
                        raise AdapterError('report_download_length_mismatch')
                yield chunks()
