import logging
import argparse
import time
from quarkchain.utils import token_id_encode
from typing import Tuple, Dict
from quarkchain.tools.count_total_balance import Fetcher

try:
    # Custom dependencies. Required if the user needs to set up a prometheus client.
    from prometheus_client import start_http_server, Gauge
except Exception as e:
    print("======")
    print("Dependency requirement for prometheus client is not met.")
    print("Don't run cluster in this mode.")
    print("======")
    raise e

import jsonrpcclient

# Disable jsonrpcclient verbose logging.
logging.getLogger("jsonrpcclient.client.request").setLevel(logging.WARNING)
logging.getLogger("jsonrpcclient.client.response").setLevel(logging.WARNING)

TIMEOUT = 100
fetcher = None


def get_time_and_balance(
    root_block_height: int, token_id: int
) -> Tuple[int, Dict[str, int]]:
    global fetcher
    assert isinstance(fetcher, Fetcher)

    rb, minor_block_ids = fetcher.get_latest_minor_block_id_from_root_block(
        root_block_height
    )
    timestamp = rb["timestamp"]

    total_balances = {}
    for block_id in minor_block_ids:
        shard = "0x" + block_id[-8:]
        total, start = 0, None
        while start != "0x" + "0" * 64:
            balance, start = fetcher.count_total_balance(block_id, token_id, start)
            # TODO: add gap to avoid spam.
            total += balance
        total_balances[shard] = total
    return timestamp, total_balances


def get_highest() -> int:
    global fetcher
    assert isinstance(fetcher, Fetcher)

    res = fetcher.cli.send(
        jsonrpcclient.Request("getRootBlockByHeight"), timeout=TIMEOUT
    )
    if not res:
        raise RuntimeError("Failed to get latest block height")
    return int(res["height"], 16)


def prometheus_balance(args):
    tokens = {
        token_name: token_id_encode(token_name)
        for token_name in args.tokens.strip().split(sep=",")
    }
    # Create a metric to track token total balance.
    balance_gauge = Gauge(
        "token_total_balance", "Total balance of specified tokens", ("shard", "token")
    )
    # A meta gauge to track block height, because if things go wrong, we want
    # to know which root block has the wrong balance.
    block_height_gauge = Gauge("block_height", "Height for root block and minor block")

    while True:
        try:
            # Call when rpc server is ready.
            latest_block_height = get_highest()
            total_balance = {}
            for token_name, token_id in tokens.items():
                total_balance[token_name] = get_time_and_balance(
                    latest_block_height, token_id
                )
        except Exception as e:
            print("failed to get latest root block height", e)
            # Rpc not ready, wait and try again.
            time.sleep(3)
            continue
        block_height_gauge.set(latest_block_height)
        for token_name, (_, balance_dict) in total_balance.items():
            balance_gauge.labels("total", token_name).set(sum(balance_dict.values()))
            for shard_id, shard_bal in balance_dict.items():
                balance_gauge.labels(shard_id, token_name).set(shard_bal)
        time.sleep(args.interval)

def scf_blockHeight(args):
    block_ip_list=args.blockHeightIpList.strip().split(",")
    peer_ip_list=args.peerIpList.strip().split(",")

    block_fetchers = {}
    ip_fetchers = {}
    block_height_gauge=Gauge("GoQKCBeijingData","block_heitht_by_ip",("ip","type"))
    for ip in block_ip_list:
        block_fetchers[ip] = Fetcher(ip, TIMEOUT)
    for ip in peer_ip_list:
        ip_fetchers[ip]=Fetcher(ip,TIMEOUT)

    while True:
        try:
            print("start---")
            for ip,f in block_fetchers.items():
                res = f.cli.send(
                    jsonrpcclient.Request("getRootBlockByHeight",None), timeout=TIMEOUT
                )
                if not res:
                    raise RuntimeError("Failed to get latest block height-115")
                data=int(res["height"], 16)
                print("height_ip",ip,"data",data)
                block_height_gauge.labels(ip,"height").set(data)

            for ip,f in ip_fetchers.items():
                res=f.cli.send(
                    jsonrpcclient.Request("getPeers"), timeout=TIMEOUT
                )
                if not res:
                    raise RuntimeError("fdadsadsadsa")
                data=len(res["peers"])
                print("peer_ip", ip, "data", data)
                block_height_gauge.labels(ip,"peer_nubmer").set(data)
        except Exception as e:
            print("failed to get latest root block height---", e)
            # Rpc not ready, wait and try again.
            time.sleep(3)
            continue
        time.sleep(args.interval)

def main():

    #nohup python3 -u prom.py --host 127.0.0.1:38391 --enable_count_balance --tokens QKC,BTC --blockHeightIpList=http://13.228.159.171:38391,http://52.194.81.124:38391,http://34.208.170.17:38391,http://54.203.168.137:38391,http://209.97.147.80:38391 --peerIpList=http://13.228.159.171:38391,http://52.194.81.124:38391 --interval 60 > test.log 2>&1 &
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enable_count_balance",
        default=False,
        dest="balance",
        action="store_true",
        help="enable monitoring total balance",
    )
    parser.add_argument(
        "--interval", type=int, help="seconds between two queries", default=30
    )
    parser.add_argument(
        "--tokens",
        type=str,
        default="QKC",
        help="tokens to be monitored, separated by comma",
    )


    parser.add_argument("--host", type=str, help="host address of the cluster")
    parser.add_argument("--port", type=int, help="prometheus expose port", default=8000)

    parser.add_argument(
        "--blockHeightIpList",
        type=str,
        help="scf"
    )

    parser.add_argument(
        "--peerIpList",
        type=str,
        help="scf"
    )

    args = parser.parse_args()

    host = "http://localhost:38391,"
    if args.host:
        host = args.host
        # Assumes http by default.
        if not host.startswith("http"):
            host = "http://" + host

    # Local prometheus server.
    start_http_server(args.port)

    global fetcher
    fetcher = Fetcher(host, TIMEOUT)

    if args.balance:
        # prometheus_balance(args)
        scf_blockHeight(args)


if __name__ == "__main__":
    main()
