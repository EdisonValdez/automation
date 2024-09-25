#!/usr/bin/env python
print('If you get error "ImportError: No module named \'asyncio\'" install asyncio:\n'+\
    '$ sudo pip install asyncio');
print('If you get error "ImportError: No module named \'aiohttp\'" install ' +\
    'aiohttp:\n$ sudo pip install aiohttp');
print('To enable your free eval account and get CUSTOMER, YOURZONE and ' + \
    'YOURPASS, please contact sales@brightdata.com')

import asyncio
import aiohttp/
import random
import socket
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

super_proxy = socket.gethostbyname('brd.superproxy.io')

class SingleSessionRetriever:
    url = "http://%s-country-us-session-%s:%s@"+super_proxy+":%d"
    port = 22225

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._reset_session()

    def _reset_session(self):
        session_id = str(random.random())
        self._proxy = self.url % (self._username, session_id, self._password, SingleSessionRetriever.port)
    
    async def retrieve(self, url, timeout):
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, proxy=self._proxy, timeout=timeout) as response:
                    return await response.text()
            except Exception as e:
                print(f"Request failed: {e}, Type: {type(e).__name__}")
                return None


class MultiSessionRetriever:
    def __init__(self, username, password, session_requests_limit, session_failures_limit):
        self._username = username
        self._password = password
        self.session_requests_limit = session_requests_limit
        self.session_failures_limit = session_failures_limit
        self._sessions_stack = []
        self._requests = 0

    async def retrieve(self, urls, timeout, parallel_sessions_limit, callback):
        semaphore = asyncio.Semaphore(parallel_sessions_limit)
        tasks = [self._retrieve_single(url, timeout, semaphore, callback) for url in urls]
        await asyncio.gather(*tasks)

    async def _retrieve_single(self, url, timeout, semaphore, callback):
        async with semaphore:
            if not self._sessions_stack or self._requests >= self.session_requests_limit:
                if self._sessions_stack:
                    self._requests = 0
                session_retriever = SingleSessionRetriever(self._username, self._password)
                self._sessions_stack.append(session_retriever)
            else:
                session_retriever = self._sessions_stack[-1]
            self._requests += 1
            body = await session_retriever.retrieve(url, timeout)
            if body is not None:
                await callback(url, body)

async def output(url, body):
    print(f"URL: {url}, Body: {body[:1000]}...")

async def main():
    n_total_req = 10
    req_timeout = 30
    n_parallel_exit_nodes = 10
    switch_ip_every_n_req = 1
    max_failures = 2

    retriever = MultiSessionRetriever('brd-customer-hl_94348bae-zone-serp_api1', '14fx4peh5op1', switch_ip_every_n_req, max_failures)
    await retriever.retrieve(["http://www.google.com/search?q=pizza"] * n_total_req, req_timeout, n_parallel_exit_nodes, output)

if __name__ == '__main__':
    asyncio.run(main())