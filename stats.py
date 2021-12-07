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
            name, addr, aleo = line.split(";")
            hosts[addr] = [name, aleo]
    return hosts


async def get_network_info():
    async with aiohttp.ClientSession() as http:
        r = await http.get("https://www.aleo.network/api/latestBlocks?limit=1")
        data = await r.json()
    return dict(height=data[0]["height"],
                timestamp=data[0]["timestamp"],
                block_hash=data[0]["blockHash"])


async def get_leaderboard_info(aleo_addr):
    async with aiohttp.ClientSession() as http:
        r = await http.get(
            "https://www.aleo.network/api/leaderboard?search=%s" % aleo_addr)
        data = await r.json()

    result = {
        "position": 0,
        "last_mined": 0,
        "pre_mined": 0,
        "testnet_mined": 0,
    }

    try:
        stat = data["leaderboard"][0]
    except IndexError:
        return result

    result["position"] = stat["position"]
    result["last_mined"] = stat["lastBlockMined"]
    result["pre_mined"] = stat["calibrationScore"]
    result["testnet_mined"] = stat["score"]
    return result


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

    lb_tasks = []
    lb_stat = dict()
    for idx, ipaddr in enumerate(hosts):
        (ssh_alias, aleo_addr) = hosts[ipaddr]
        lb_tasks.append(get_leaderboard_info(aleo_addr))

    lb_results = await asyncio.gather(*lb_tasks)
    for idx, ipaddr in enumerate(hosts):
        (ssh_alias, aleo_addr) = hosts[ipaddr]
        lb_stat[ipaddr] = lb_results[idx]

    table = []
    forked = []

    for idx, host in enumerate(hosts):
        if info[idx]["block_hash"] != network_info["block_hash"]:
            hash_str = "FORK [%s]" % str(info[idx]["block_hash"])[-5:]
            forked.append(hosts[host][0])
        else:
            hash_str = "OK"

        lb_str = "%3d [%d + %d]" % (
            lb_stat[host]["position"],
            lb_stat[host]["pre_mined"],
            lb_stat[host]["testnet_mined"],
        )

        table.append([
            host,
            hosts[host][0],
            hosts[host][1],
            info[idx]["status"],
            info[idx]["height"],
            info[idx]["peers_sync"],
            len(info[idx]["peers_conn"]),
            lb_str,
            hash_str
        ])

    print(tabulate(table, showindex="always", tablefmt="pretty",
                   colalign=("left", "left", "left", "left",),
                   headers=[
                       "IPAddr",
                       "Alias",
                       "Addr",
                       "Status",
                       "Height",
                       "Psynced",
                       "Ptotal",
                       "Leaderboard",
                       "Hash @ %d" % network_info["height"]
                   ]
    ))

    print("=" * 75)

    if forked:
        with open("restart.hosts", "w+") as w:
            for ssh_alias in forked:
                w.write("%s\n" % ssh_alias)
        print("%d forked hosts found. Generated restart.hosts" % len(forked))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
