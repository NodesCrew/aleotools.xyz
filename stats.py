# coding: utf-8
import json
import time
import aiohttp
import asyncio

from tabulate import tabulate


def read_hosts():
    hosts = dict()
    with open("hosts.txt") as f:
        for line in f:
            line = line.strip()
            name, addr = line.split(";")
            hosts[addr] = name
    return hosts


async def get_network_info():
    async with aiohttp.ClientSession() as http:
        r = await http.get("https://www.aleo.network/api/latestblocks?limit=1")
        data = await r.json()
    return dict(height=data[0]["height"], timestamp=data[0]["timestamp"])


async def call_rpc(params, host, http):
    """ Send request to RPC endpoint and returns result
    """
    payload = {
        "jsonrpc": "2.0",
        "id": "documentation",
        "params": []
    }
    try:
        response = await http.post(
            f"http://{host}:3032/",
            data=json.dumps({**payload, **params}),
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return None

    try:
        json_ = json.loads(await response.text())
        return json_["result"]
    except Exception as e:
        print("Unable to parse response: status=%s, text=%s\n%s" % (
            response.status_code, response.text, e))
        exit(-1)

    print("Unable to call: %s" % {{**payload, **params}})
    exit(-1)


async def get_host_info(host):
    async with aiohttp.ClientSession() as http:
        state = await call_rpc({"method": "getnodestate"}, host, http)
        height = await call_rpc({"method": "latestblockheight"}, host, http)
        peers_conn = await call_rpc({"method": "getconnectedpeers"}, host, http)

    try:
        status = state["status"]
        peers_sync = state["number_of_connected_sync_nodes"]
    except (ValueError, KeyError, TypeError):
        status = "_____"
        peers_sync = "?"

    return dict(
        peers_conn=peers_conn or "?",
        peers_sync=peers_sync,
        status=status,
        height=height or "_____"
    )


async def main():
    hosts = read_hosts()

    tasks = [get_host_info(h) for h in hosts]
    info = await asyncio.gather(*tasks)

    # network_info = await get_network_info()
    # print("=" * 75)
    #
    # print("Network height: %d, %d seconds ago" % (
    #     network_info["height"], (time.time() - 3600) - network_info["timestamp"]
    # ))

    table = []
    hash_list = []
    hash_tasks = []
    height_min = 999999999

    # Get min height
    for idx, host in enumerate(hosts):
        height_min = min(info[idx]["height"], height_min)

    # Get heights
    async with aiohttp.ClientSession() as http:
        for idx, host in enumerate(hosts):
            hash_tasks.append(
                call_rpc(
                    {"method": "getblockhash", "params": [height_min]},
                    host=host, http=http
                ))
        hash_list = await asyncio.gather(*hash_tasks)

    for idx, host in enumerate(hosts):
        table.append([
            host,
            hosts[host],
            info[idx]["status"],
            info[idx]["height"],
            info[idx]["peers_sync"],
            len(info[idx]["peers_conn"]),
            hash_list[idx]
        ])

    print(tabulate(table, showindex="always", tablefmt="pretty",
                   colalign=("left", "left", "left", "left",),
                   headers=[
                       "IPAddr",
                       "Alias",
                       "Status",
                       "Height",
                       "Psynced",
                       "Ptotal",
                       "Hash @ %d" % height_min
                   ]
    ))

    print("=" * 75)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
