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
        r = await http.get("https://www.aleo.network/api/latestBlocks?limit=1")
        data = await r.json()
    return dict(height=data[0]["height"],
                timestamp=data[0]["timestamp"],
                block_hash=data[0]["blockHash"])


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
    except KeyError:
        return None
    except Exception as e:
        print("Unable to parse response: status=%s, text=%s\n%s" % (
            response.status_code, response.text, e))
        exit(-1)


    print("Unable to call: %s" % {{**payload, **params}})
    exit(-1)


async def get_host_info(host, net_height):
    async with aiohttp.ClientSession() as http:
        state = await call_rpc({"method": "getnodestate"}, host, http)
        height = await call_rpc({"method": "latestblockheight"}, host, http)
        peers_conn = await call_rpc({"method": "getconnectedpeers"}, host, http)
        block_hash = await call_rpc(
            {"method": "getblockhash", "params": [net_height]},
            host=host, http=http
        )

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
        height=height or "_____",
        block_hash=block_hash
    )


async def main():
    hosts = read_hosts()

    network_info = await get_network_info()
    print("=" * 75)
    print("Network height: %d (%d sec ago), block hash: %s" % (
        network_info["height"],
        (time.time() - 3600) - network_info["timestamp"],
        network_info["block_hash"]
    ))

    tasks = [get_host_info(h, network_info["height"]) for h in hosts]
    info = await asyncio.gather(*tasks)

    table = []

    for idx, host in enumerate(hosts):

        hash_str = "%s" % info[idx]["block_hash"]
        if info[idx]["block_hash"] != network_info["block_hash"]:
            hash_str += " !!!"

        table.append([
            host,
            hosts[host],
            info[idx]["status"],
            info[idx]["height"],
            info[idx]["peers_sync"],
            len(info[idx]["peers_conn"]),
            hash_str
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
                       "Hash @ %d" % network_info["height"]
                   ]
    ))

    print("=" * 75)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
