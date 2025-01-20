import re
from dotenv import load_dotenv
import os
from dune_client.client import DuneClient
from dune_client.types import QueryParameter
from dune_client.query import QueryBase
from langchain.agents import tool
import json
from decimal import Decimal
from web3 import Web3
import numpy as np

from dateutil.relativedelta import relativedelta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from langchain_community.document_loaders import SpiderLoader
import matplotlib

matplotlib.use("Agg")  # 使用非交互后端
import matplotlib.pyplot as plt
import numpy as np
import uuid
import matplotlib.dates as mdates
from datetime import datetime
import pytz
import boto3

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx

load_dotenv(".env")

DUNE_API_KEY = os.getenv("DUNE_API_KEY")
dune = DuneClient(api_key=DUNE_API_KEY)

# 初始化 S3 客户端
s3_client = boto3.client("s3")


@tool
def get_ethereum_symbol_info(symbol: str) -> str:
    """
    Useful when you need to get the contract's address and decimals from a cryptocurrency symbol on Ethereum. The input for this should be complete symbol of a cryptocurrency.
    """
    query = QueryBase(
        name="ethereum_get_info_from_symbol",
        query_id=3893389,
        params=[
            QueryParameter.text_type(name="symbol", value=symbol),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_ethereum_erc20_info(contract_address: list[str]) -> str:
    """
    Useful when you need to get the contract's address and decimals from a cryptocurrency symbol on Ethereum. The input for this should be complete address of a ERC20 contract.
    """
    query = QueryBase(
        name="ethereum_get_info_from_contract_address",
        query_id=3912799,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(contract_address)
            ),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def top_10_eth_transaction(min_amount: float, min_block_time: str) -> str:
    """
    Useful when you need to get the top 10 transactions by eth transaction amount.
    The parameter `min_amout` must be an integer representing the minimum transaction amount in ETH.
    The `min_block_time` parameter must be a time string in the format of yyyy-mm-dd hh:mm:ss, indicating that block_time must exceed this time.
    """
    query = QueryBase(
        name="ethereum_top_eth_transactions",
        query_id=3912752,
        params=[
            QueryParameter.text_type(name="min_amount", value=min_amount),
            QueryParameter.text_type(
                name="min_block_time", value=min_block_time
            ),  # yyyy-MM-dd HH:mm:ss
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def top_10_erc20_transaction(
    token_contract_address: str, min_amout: float, min_block_time: str
) -> str:
    """
    Useful when you need to get the top 10 volume transactions in the entire Ethereum network.
    The parameter `token_contract_address` is the token contract's address.
    The parameter `min_amout` must be an integer representing the minimum transaction amount in the token.
    The `min_block_time` parameter must be a time string in the format of yyyy-mm-dd hh:mm:ss, indicating that block_time must exceed this time.
    """
    contract_info = json.loads(
        get_ethereum_erc20_info.invoke({"contract_address": [token_contract_address]})
    )
    query = QueryBase(
        name="ethereum_top_erc20_token_transaction",
        query_id=3912780,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=token_contract_address
            ),
            QueryParameter.number_type(
                name="min_amount",
                value=min_amout * (10 ** contract_info[0]["decimals"]),
            ),
            QueryParameter.text_type(
                name="min_block_time", value=min_block_time
            ),  # yyyy-MM-dd HH:mm:ss
        ],
    )
    results_df = dune.run_query_dataframe(query)
    results_df["amount"] = results_df["amount"].apply(lambda a: Decimal(a))
    results_df["amount"] = results_df["amount"].apply(
        lambda a: a / (Decimal(10) ** contract_info[0]["decimals"])
    )
    return results_df.to_json(orient="records")


ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_URL = "https://api.etherscan.io/api"


INFURA_API_KEY = os.getenv("INFURA_API_KEY")
# 连接到Infura的以太坊节点
INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"

ethers = Web3(Web3.HTTPProvider(INFURA_URL))


@tool
def is_contract_address(address):
    """
    Useful when you need to check if an address is a contract address.
    """
    code = ethers.eth.get_code(Web3.to_checksum_address(address))
    return code != b"" and code != b"0x"


address_info_cache = {}


@tool
def get_token_symbol(contract_address) -> str:
    """
    Get the token symbol for a given Ethereum contract address using Web3.py.

    :param contract_address: Contract address of the token.
    :return: Token symbol or None if not found.
    """
    if not is_contract_address.invoke({"address": contract_address}):
        return ""
    erc20_abi = [
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        }
    ]

    contract = ethers.eth.contract(
        address=Web3.to_checksum_address(contract_address), abi=erc20_abi
    )
    try:
        symbol = contract.functions.symbol().call()
        return symbol
    except Exception as e:
        print(f"Error: {e}")
        return None


@tool
def get_address_labels(addresses: list[str]) -> str:
    """
    Fetches labels for specified Ethereum addresses. Input should be a complete Ethereum address.
    """
    query = QueryBase(
        name="ethereum_get_labels_of_address",
        query_id=3912735,
        params=[
            QueryParameter.text_type(name="addresses", value=",".join(addresses)),
        ],
    )
    results_df = dune.run_query_dataframe(query=query)
    if results_df.empty:
        results_df = pd.DataFrame([{"address": ad, "labels": ""} for ad in addresses])
    tag_df = pd.DataFrame(get_multiple_address_tags.invoke({"addresses": addresses}))
    results_df = results_df.merge(tag_df, on="address", how="left")

    # 定义合并函数
    def merge_labels_and_tags(row):
        if pd.notna(row["tag"]):
            return row["labels"] + "[" + row["tag"] + "]"
        else:
            return row["labels"]

    # 应用合并函数
    results_df["labels"] = results_df.apply(merge_labels_and_tags, axis=1)

    # 删除 tag 列
    results_df.drop(columns=["tag"], inplace=True)
    return results_df.to_json(orient="records")


@tool
def get_funds_transfer_status_in_transaction(tx_hash: str) -> str:
    """
    Useful when you need get funds transfer status in a Ethereum's transaction. Input for this should be a complete transaction's hash.
    """

    result = {}

    # transaction
    try:
        transaction = ethers.eth.get_transaction(tx_hash)
    except Exception as e:
        return str(e)
    # RPC请求获取交易的trace
    trace_call = {
        "jsonrpc": "2.0",
        "method": "trace_transaction",
        "params": [tx_hash],
        "id": 1,
    }

    response = ethers.manager.request_blocking(
        trace_call["method"], trace_call["params"]
    )
    data = json.loads(ethers.to_json(response))
    _action = [d["action"] for d in data if d["action"]["callType"] == "call"]
    eth_transfer_action = []
    for act in _action:
        act["value"] = int(act["value"], 16)
        act["gas"] = int(act["gas"], 16)
        act["inpu"] = ""  # 去掉input节省token
        if act["value"] > 0:
            act["value"] = Web3.from_wei(act["value"], "ether").to_eng_string()
            eth_transfer_action.append(act)
    # logs
    event_signature_hash = ethers.keccak(text="Transfer(address,address,uint256)").hex()
    receipt = ethers.eth.get_transaction_receipt(tx_hash)
    if receipt and receipt["logs"]:
        logs = [
            log
            for log in receipt["logs"]
            if log["topics"][0].hex() == event_signature_hash
        ]
        contract_addresses = [log["address"] for log in logs]
        contract_addresses = np.unique(contract_addresses)
        erc20_info = json.loads(
            get_ethereum_erc20_info.invoke(
                {"contract_address": contract_addresses.tolist()}
            )
        )
        decoded_logs = []
        for log in logs:
            if log["topics"][0].hex() == event_signature_hash:
                # 解析 Transfer 事件
                from_address = Web3.to_checksum_address(
                    "0x" + log["topics"][1].hex()[-40:]
                )
                to_address = Web3.to_checksum_address(
                    "0x" + log["topics"][2].hex()[-40:]
                )
                value = int(log["data"].hex(), 16)
                ei = [
                    ei for ei in erc20_info if ei["contract_address"] == log["address"]
                ]
                decimals = ei[0]["decimals"] if len(ei) > 0 else 1
                decoded_logs.append(
                    {
                        "from": from_address,
                        "to": to_address,
                        "value": (value / 10**decimals),
                        "token_contract_address": log["address"],
                        # "token_symbol": get_token_symbol(log["address"]),
                    }
                )
            transaction = json.loads(ethers.to_json(transaction))
            transaction["input"] = ""  # 节省token
            result = {
                "transaction": transaction,
                "eth_transfer_action": eth_transfer_action,
                "token_transfer_action": decoded_logs,
            }
    else:
        result = {
            "transaction": json.loads(ethers.to_json(transaction)),
            "eth_transfer_action": eth_transfer_action,
        }
    address_list = (
        [result["transaction"]["from"]]
        + [result["transaction"]["to"]]
        + [t["from"] for t in result["eth_transfer_action"]]
        + [t["to"] for t in result["eth_transfer_action"]]
        + [t["from"] for t in result["token_transfer_action"]]
        + [t["to"] for t in result["token_transfer_action"]]
    )
    unique_addresses = np.unique(address_list)
    no_cached_address = [ad for ad in unique_addresses if ad not in address_info_cache]
    if len(no_cached_address) > 0:
        labels = json.loads(get_address_labels.invoke({"addresses": no_cached_address}))
    for ad in no_cached_address:
        ad_info = {
            "address": ad,
            "symbol": get_token_symbol.invoke({"contract_address": ad}),
            "labels": (
                [l["labels"] for l in labels if l["address"] == ad][0]
                if len([l["labels"] for l in labels if l["address"] == ad]) > 0
                else ""
            ),
        }
        address_info_cache[ad] = ad_info
    ad_info = [address_info_cache[ad] for ad in unique_addresses]
    result["address_info"] = ad_info
    return json.dumps(result)


@tool
def get_address_tag_from_etherscan(address) -> str:
    """
    Useful when you need get the tag of an address.
    """
    url = f"https://etherscan.io/address/{address}"
    loader = SpiderLoader(
        url=url,
        mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
    )
    try:
        html = loader.load()

        def extract_tag(s):
            # 定义正则表达式模式
            pattern = r"^(.*?)\s*\|\s*Address"

            # 使用re.search找到匹配的部分
            match = re.search(pattern, s)

            if match:
                # 返回匹配的组1，即我们感兴趣的标签部分
                tag = match.group(1).strip()
                if tag:  # 检查tag是否为空
                    return tag
                else:
                    return "No tag found"
            return "No tag found"

        return extract_tag(html[0].page_content.split("\n", 1)[0])
    except Exception as e:
        print(e)
        return "No tag found"


@tool
def get_multiple_address_tags(addresses: list[str]):
    """
    Get tags for multiple Ethereum addresses.
    """
    address_tags = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(get_address_tag_from_etherscan, addresses)

    for address, tag in zip(addresses, results):
        a_tag = {"address": address, "tag": tag}
        address_tags.append(a_tag)

    return address_tags


@tool
def get_transactions_history_from_dune(address: str) -> str:
    """
    Useful when you need to get the transactions history of an address on Ethereum.
    The parameter `address` must be the contract address of the token.
    """
    query = QueryBase(
        name="get_token_usd_price",
        query_id=3924844,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="N", value=100),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_address_interact_with(address: str) -> str:
    """
    This is useful when you need to obtain which addresses the address interacted with within 1 months and the transaction behavior of the address.
    The parameter `address` must be complete a address.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_address_interaction_with",
        query_id=3957299,
        params=[
            QueryParameter.text_type(name="address", value=address),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: f"{row['tx_count']} transactions were made with address {row['to']}({row['to_address_labels']}) from {formatted_time}.",
            axis=1,
        ).tolist()
        # return results_df.to_json(orient="records")
        return "\n".join(r_arr)
    else:
        return ""


@tool
def what_is_time_now():
    """
    Retrieves the current date and time.
    """
    # 获取当前系统时区
    local_timezone = datetime.now(pytz.timezone("UTC")).astimezone().tzinfo

    # 获取当前时间
    current_time = datetime.now(local_timezone)

    # 打印当前时间和时区信息
    return f"Current time:{current_time}\nCurrent timezone:{local_timezone}"


@tool
def get_addres_funds_movements_of(
    address: str,
    contract_address: str,
) -> str:
    """
    This is useful when you need to get the token flow of an address.
    The parameter `address` must be a complete address.
    The parameter `contract_address` must be the erc20 token's complete address.
    By default, it returns the latest 20 transactions.
    """
    query = QueryBase(
        name="eddie_get_some_erc20_transfer_of_address",
        query_id=3940668,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="contract_address", value=contract_address),
            QueryParameter.number_type(name="N", value=20),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        results_df["from"] = results_df["from"].str.lower()
        results_df["to"] = results_df["to"].str.lower()
        address = address.lower()
        # Convert 'block_time' to datetime and 'amount' to float
        results_df["block_time"] = pd.to_datetime(results_df["block_time"])
        results_df["amount"] = results_df["amount"].astype(float)

        # Function to shorten address
        def shorten_address(addr):
            return addr[:6] + "..." + addr[-4:] if len(addr) > 10 else addr

        # Calculate total inflow and outflow
        total_inflow = results_df[results_df["to"] == address]["amount"].sum()
        total_outflow = results_df[results_df["from"] == address]["amount"].sum()

        # Create pie chart for inflow/outflow
        pie_fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Inflow", "Outflow"],
                    values=[total_inflow, total_outflow],
                    hole=0.3,
                )
            ]
        )
        pie_fig.update_layout(title_text="Total Inflow vs Outflow")

        # Create time series of balance changes
        results_df["balance_change"] = results_df.apply(
            lambda row: row["amount"] if row["to"] == address else -row["amount"],
            axis=1,
        )
        results_df["cumulative_balance"] = results_df["balance_change"].cumsum()

        balance_fig = go.Figure(
            data=[
                go.Scatter(
                    x=results_df["block_time"],
                    y=results_df["cumulative_balance"],
                    mode="lines+markers",
                )
            ]
        )
        balance_fig.update_layout(
            title_text="Balance Changes Over Time",
            xaxis_title="Time",
            yaxis_title="Balance",
        )

        # Create network graph
        G = nx.DiGraph()
        for _, row in results_df.iterrows():
            if row["from"] == address.lower():
                G.add_edge(
                    shorten_address(address),
                    shorten_address(row["to"]),
                    weight=row["amount"],
                    time=row["block_time"],
                    direction="out",
                )
            elif row["to"] == address.lower():
                G.add_edge(
                    shorten_address(row["from"]),
                    shorten_address(address),
                    weight=row["amount"],
                    time=row["block_time"],
                    direction="in",
                )

        # Calculate node volumes
        node_volumes = {node: 0 for node in G.nodes()}
        for u, v, data in G.edges(data=True):
            node_volumes[u] += data["weight"]
            node_volumes[v] += data["weight"]

        # Ensure the central node is at the center
        center_node = shorten_address(address)
        import math

        # Function to calculate star layout
        def calculate_star_layout(G, center_node):
            pos = {}
            other_nodes = [node for node in G.nodes() if node != center_node]
            n = len(other_nodes)

            # 将中心节点放在坐标原点
            pos[center_node] = np.array([0, 0])

            # 计算其他节点的位置
            for i, node in enumerate(other_nodes):
                angle = 2 * math.pi * i / n
                radius = 1  # 可以根据需要调整这个值来改变节点距离中心的远近
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                pos[node] = np.array([x, y])

            return pos

        # Calculate initial positions
        pos = calculate_star_layout(G, center_node)

        # Adjust node sizes and positions
        node_sizes = []
        for node in G.nodes():
            if node == center_node:
                node_sizes.append(30)  # 中心节点稍大一些
            else:
                volume = node_volumes[node]
                size = 10 + (
                    volume / max(node_volumes.values()) * 20
                )  # 根据交易量调整大小
                node_sizes.append(size)

                # 调整非中心节点的位置，使交易量大的节点离中心更远
                direction = pos[node] - pos[center_node]
                distance = np.linalg.norm(direction)
                new_distance = distance * (1 + volume / max(node_volumes.values()))
                pos[node] = pos[center_node] + direction / distance * new_distance

        # Create node trace
        node_x = [pos[node][0] for node in G.nodes()]
        node_y = [pos[node][1] for node in G.nodes()]

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            hoverinfo="text",
            marker=dict(
                showscale=True,
                colorscale="YlOrRd",
                reversescale=True,
                color=[],
                size=node_sizes,
                colorbar=dict(
                    thickness=15,
                    title="Transaction Volume",
                    xanchor="left",
                    titleside="right",
                    y=0.5,  # 将颜色条移到中间
                ),
                line_width=2,
            ),
        )

        # Set node properties
        node_text = []
        node_colors = []
        for node in G.nodes():
            if node == center_node:
                node_text.append(
                    f"{node}<br>Central Address<br>Volume: {node_volumes[node]:.2f}"
                )
                node_colors.append("#00FFFF")  # Cyan color for central node
            else:
                node_text.append(f"{node}<br>Volume: {node_volumes[node]:.2f}")
                node_colors.append(node_volumes[node])  # 使用 volume 作为颜色值

        node_trace.text = node_text
        node_trace.marker.color = node_colors

        # Create edge traces
        edge_x_in, edge_y_in, edge_text_in = [], [], []
        edge_x_out, edge_y_out, edge_text_out = [], [], []

        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            if edge[2]["direction"] == "in":
                edge_x_in.extend([x0, x1, None])
                edge_y_in.extend([y0, y1, None])
                edge_text_in.append(
                    f"From: {edge[0]}<br>To: {edge[1]}<br>Amount: {edge[2]['weight']:.2f}<br>Time: {edge[2]['time']}"
                )
            else:
                edge_x_out.extend([x0, x1, None])
                edge_y_out.extend([y0, y1, None])
                edge_text_out.append(
                    f"From: {edge[0]}<br>To: {edge[1]}<br>Amount: {edge[2]['weight']:.2f}<br>Time: {edge[2]['time']}"
                )

        edge_trace_in = go.Scatter(
            x=edge_x_in,
            y=edge_y_in,
            line=dict(width=0.5, color="green"),
            hoverinfo="text",
            mode="lines",
            text=edge_text_in,
            name="Incoming Transfer",
        )

        edge_trace_out = go.Scatter(
            x=edge_x_out,
            y=edge_y_out,
            line=dict(width=0.5, color="red"),
            hoverinfo="text",
            mode="lines",
            text=edge_text_out,
            name="Outgoing Transfer",
        )

        # Create network figure
        network_fig = go.Figure(
            data=[edge_trace_in, edge_trace_out, node_trace],
            layout=go.Layout(
                title="Network of Transactions",
                titlefont_size=16,
                showlegend=True,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                annotations=[
                    dict(
                        text="",
                        showarrow=False,
                        xref="paper",
                        yref="paper",
                        x=0.005,
                        y=-0.002,
                    )
                ],
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                legend=dict(
                    orientation="h",  # 将图例设置为水平方向
                    yanchor="bottom",  # 将图例锚点设在底部
                    y=-0.2,  # 将图例向下移动
                    xanchor="center",  # 将图例的x轴锚点设在中心
                    x=0.5,  # 将图例居中
                ),
            ),
        )

        # Add zoom and pan controls
        network_fig.update_layout(
            dragmode="pan",
            updatemenus=[
                dict(
                    type="buttons",
                    showactive=False,
                    buttons=[
                        dict(
                            label="Reset",
                            method="relayout",
                            args=[{"xaxis.range": None, "yaxis.range": None}],
                        ),
                    ],
                    direction="left",
                    pad={"r": 10, "t": 10},
                    x=0.9,
                    xanchor="right",
                    y=1.1,
                    yanchor="top",
                )
            ],
        )

        # Add central address to legend
        network_fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=20, color="#00FFFF"),
                name="Central Address",
            )
        )

        # Create bar chart for all transfer relationships
        inflow_df = (
            results_df[results_df["to"] == address]
            .groupby("from")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        outflow_df = (
            results_df[results_df["from"] == address]
            .groupby("to")["amount"]
            .sum()
            .sort_values(ascending=False)
        )

        # Combine inflow and outflow data
        all_addresses = set(inflow_df.index) | set(outflow_df.index)
        if (
            all_addresses
        ):  # Only create the transfer chart if there are addresses to show
            transfer_data = pd.DataFrame(
                {
                    "inflow": inflow_df.reindex(all_addresses).fillna(0),
                    "outflow": outflow_df.reindex(all_addresses).fillna(0),
                }
            ).sort_values("inflow", ascending=False)

            transfer_fig = go.Figure(
                data=[
                    go.Bar(
                        name="Inflow",
                        x=transfer_data.index.map(shorten_address),
                        y=transfer_data["inflow"],
                        marker_color="green",
                    ),
                    go.Bar(
                        name="Outflow",
                        x=transfer_data.index.map(shorten_address),
                        y=transfer_data["outflow"],
                        marker_color="red",
                    ),
                ]
            )
            transfer_fig.update_layout(
                barmode="group",
                title_text="All Transfer Relationships",
                xaxis_title="Addresses",
                yaxis_title="Amount",
                height=max(
                    400, len(all_addresses) * 20
                ),  # Adjust height based on number of addresses
            )
            transfer_fig.update_xaxes(tickangle=45)
        else:
            # Create an empty figure if there are no transfers
            transfer_fig = go.Figure()
            transfer_fig.update_layout(
                title_text="No Transfers Found",
                annotations=[
                    dict(
                        x=0.5,
                        y=0.5,
                        xref="paper",
                        yref="paper",
                        text="No transfer data available",
                        showarrow=False,
                        font=dict(size=20),
                    )
                ],
            )

        # Generate random filename
        random_filename = f"{uuid.uuid4()}.html"

        # Create HTML content with all charts and explanations
        html_content = f"""
        <html>
        <head>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                h1 {{
                    color: #2c3e50;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                h2 {{
                    color: #34495e;
                }}
                .grid-container {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 20px;
                }}
                .chart-container {{
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    padding: 20px;
                    margin-bottom: 20px;
                }}
                .explanation {{
                    background-color: #e8f4f8;
                    border-left: 5px solid #3498db;
                    padding: 10px;
                    margin-top: 10px;
                }}
                .full-width {{
                    grid-column: 1 / -1;
                }}
            </style>
        </head>
        <body>
            <h1>Token {results_df['symbol'].iloc[0]} Flow Analysis for {shorten_address(address)}</h1>
            
            <div class="explanation full-width">
                <h2>What do these charts mean?</h2>
                <p>We've analyzed the latest {len(results_df)} transactions for this address. Here's what we found:</p>
            </div>
        
            <div class="grid-container">
                <div class="chart-container">
                    <div id="pie_chart" style="width:100%;height:400px;"></div>
                    <div class="explanation">
                        <p>This pie chart shows the total amount of tokens flowing in (green) versus flowing out (red) of your address.</p>
                        <p>A larger green section means you're receiving more tokens than you're sending out.</p>
               </div>
                </div>
        
                <div class="chart-container">
                    <div id="balance_chart" style="width:100%;height:400px;"></div>
                    <div class="explanation">
                        <p>This line chart shows how your token balance has changed over time.</p>
                        <p>An upward trend means your balance is increasing, while a downward trend means it's decreasing.</p>
                    </div>
                </div>
        
                <div class="chart-container full-width">
                    <div id="network_chart" style="width:100%;height:600px;"></div>
                    <div class="explanation">
                        <p>This network graph shows the relationships between addresses involved in transactions.</p>
                        <p>Each node represents an address, with your address at the center in cyan.</p>
                        <p>Green lines indicate incoming transfers, while red lines indicate outgoing transfers.</p>
                        <p>Larger nodes and those further from the center represent addresses with higher transaction volumes.</p>
                    </div>
                </div>
        
                <div class="chart-container full-width">
                    <div id="transfer_chart" style="width:100%;height:{max(400, len(all_addresses) * 20)}px;"></div>
                    <div class="explanation">
                        <p>This bar chart shows all addresses you've interacted with, in terms of token amount.</p>
                        <p>Green bars represent incoming transfers (tokens you've received), while red bars represent outgoing transfers (tokens you've sent).</p>
                        <p>Addresses are sorted by the amount of incoming transfers, from highest to lowest.</p>
                    </div>
                </div>
            </div>
        
            <script>
                var pie_data = {pie_fig.to_json()};
                var balance_data = {balance_fig.to_json()};
                var network_data = {network_fig.to_json()};
                var transfer_data = {transfer_fig.to_json()};
                Plotly.newPlot('pie_chart', pie_data.data, pie_data.layout);
                Plotly.newPlot('balance_chart', balance_data.data, balance_data.layout);
                Plotly.newPlot('network_chart', network_data.data, network_data.layout);
                Plotly.newPlot('transfer_chart', transfer_data.data, transfer_data.layout);
            </script>
        </body>
        </html>
        """

        # Save as HTML file
        with open(random_filename, "w") as f:
            f.write(html_content)

        # Upload file to S3 bucket's charts folder
        s3_client.upload_file(
            random_filename,
            "musse.ai",
            f"charts/{random_filename}",
            ExtraArgs={"ContentType": "text/html"},
        )

        # Remove local file
        os.remove(random_filename)
        # img_str = (
        #     f"Below is the URL of the token flow analysis chart. The title of the chart is: Token {results_df['symbol'].iloc[0]} Flow Analysis for {shorten_address(address)}"
        #     + "\n"
        #     + f'You can use the Interactive Chart in HTML like this: <iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="2000px" title="Token Flow Analysis chart"></iframe>'
        # )
        img_str = f'<iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="2000px" title="Token Flow Analysis chart"></iframe>'

        summary = f"""
        Simple analysis summary for {shorten_address(address)}:
        1. Total tokens received: {total_inflow} {results_df['symbol'].iloc[0]}
        2. Total tokens sent: {total_outflow} {results_df['symbol'].iloc[0]}
        3. Net change in balance: {total_inflow - total_outflow} {results_df['symbol'].iloc[0]}
        4. Number of transactions analyzed: {len(results_df)}
        5. Time period: from {results_df['block_time'].min()} to {results_df['block_time'].max()}
        6. Number of unique addresses interacted with: {len(all_addresses)}
        """

        # Add highest incoming transfer info if available
        if not inflow_df.empty:
            summary += f"7. Address with highest incoming transfer: {shorten_address(inflow_df.index[0])} ({inflow_df.values[0]} {results_df['symbol'].iloc[0]})\n"
        else:
            summary += "7. No incoming transfers found.\n"

        # Add highest outgoing transfer info if available
        if not outflow_df.empty:
            summary += f"8. Address with highest outgoing transfer: {shorten_address(outflow_df.index[0])} ({outflow_df.values[0]} {results_df['symbol'].iloc[0]})\n"
        else:
            summary += "8. No outgoing transfers found.\n"

        summary += "\nTo see a visual representation of this data, please check the interactive chart provided below."

        return summary, img_str
    else:
        return "No relevant data found."


@tool
def get_addres_how_much_funds_received(
    address: str,
    token_sybmol: str,
    contract_address: str,
    sta_time: str,
    end_time: str,
) -> str:
    """
    This is useful when you need to get how much and where the address received the token from.
    The parameter `address` must be complete a address.
    The parameter `contract_address` must be the erc20 token's complete address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    """
    # 1. 获取当前时间
    # now = datetime.now()

    # 2. 计算前一天的时间
    # yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    # formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddit_get_address_erc20_token_recived",
        query_id=3964664,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="contract_address", value=contract_address),
            QueryParameter.text_type(name="min_time", value=sta_time),
            QueryParameter.text_type(name="max_time", value=end_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_list = results_df.apply(
            lambda row: f"Recieved a total of {row['amount']} {token_sybmol} from the address {row['from']} through {row['cnt']} transactions.",
            axis=1,
        ).tolist()
        return "\n".join(r_list)
    else:
        return "No data found."


@tool
def get_addres_how_much_funds_transfered(
    address: str,
    contract_address: str,
    token_sybmol: str,
    sta_time: str,
    end_time: str,
) -> str:
    """
    This is useful when you need to get how much and where the address transfered the token to.
    The parameter `address` must be complete a address.
    The parameter `contract_address` must be the erc20 token's complete address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    """
    # 1. 获取当前时间
    # now = datetime.now()

    # 2. 计算前一天的时间
    # yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    # formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_address_erc20_token_transfered",
        query_id=3964680,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="contract_address", value=contract_address),
            QueryParameter.text_type(name="min_time", value=sta_time),
            QueryParameter.text_type(name="max_time", value=end_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_list = results_df.apply(
            lambda row: f"Transferred a total of {row['amount']} {token_sybmol} to the address {row['to']} through {row['cnt']} transactions.",
            axis=1,
        ).tolist()
        return "\n".join(r_list)
    else:
        return "No data found."


@tool
def get_eth_movements_of(
    address: str,
    sta_time: str,
    end_time: str,
    sort_by: str,
    ascending: bool,
) -> str:
    """
    This is useful when you need to get the ETH changes of an address.
    It's useful also when you need to get the transactions of the address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    The returned dataframe can be sorted according to the parameter `sort_by`. The fields of `sort_by` include 'block_time', 'eth_value'.
    The `ascending` parameter indicates the returned dataframe whether to be sorted in ascending order.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_eth_transfer_of_address",
        query_id=3924889,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="min_time", value=sta_time),
            QueryParameter.text_type(name="max_time", value=end_time),
            QueryParameter.text_type(name="sort_by", value=sort_by),
            QueryParameter.text_type(
                name="ascending", value="asc" if ascending else "desc"
            ),
            QueryParameter.number_type(name="N", value=500),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: ("Recieve " if row["to"] == address else "Transfer ")
            + f"{row['eth_value']} ETH "
            + ("from " + row["from"] if row["to"] == address else "to " + row["to"])
            + f" at {row['block_time']}. Transation hash: {row['hash']}",
            axis=1,
        ).tolist()
        # return results_df.to_json(orient="records")
        # print("#" * 100 + f"{len(r_arr)}")
        if len(results_df) >= 500:
            pre_re = f"We found 500 data records, but the actual data may exceed 500. Due to the limitation of processing capacity, we can only provide you with the data within 500 as follows:\n"
        else:
            pre_re = (
                f"The information obtained from returned dataframe is as follows:\n"
            )
        return pre_re + "\n".join(r_arr)
    else:
        return "No data found."


@tool
def get_how_much_eth_transfered(
    address: str,
    sta_time: str,
    end_time: str,
) -> str:
    """
    This is useful when you need to get how much and where the address transfered the ETH to.
    It's useful also when you need to get the transactions of the address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_address_eth_transfer",
        query_id=3964690,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="min_time", value=sta_time),
            QueryParameter.text_type(name="max_time", value=end_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_list = results_df.apply(
            lambda row: f"Transferred a total of {row['eth_value']} ETH to the address {row['to']} through {row['cnt']} transactions.",
            axis=1,
        ).tolist()
        if len(results_df) >= 500:
            return (
                "We have only returned the top 500 results due to the large number of query results. As following:\n"
                + "\n".join(r_list)
            )
        if len(results_df) >= 500:
            return (
                "We have only returned the top 500 results due to the large number of query results. As following:\n"
                + "\n".join(r_list)
            )
        return "\n".join(r_list)
    else:
        return "No data found."


@tool
def get_how_much_eth_recieved(
    address: str,
    sta_time: str,
    end_time: str,
) -> str:
    """
    This is useful when you need to get how much and where the address recieved ETH from.
    It's useful also when you need to get the transactions of the address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_address_eth_recieved",
        query_id=3964703,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="min_time", value=sta_time),
            QueryParameter.text_type(name="max_time", value=end_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_list = results_df.apply(
            lambda row: f"Recieved a total of {row['eth_value']} from the address {row['from']} through {row['cnt']} transactions.",
            axis=1,
        ).tolist()
        if len(results_df) >= 500:
            return (
                "We have only returned the top 500 results due to the large number of query results. As following:\n"
                + "\n".join(r_list)
            )
        return "\n".join(r_list)
    else:
        return "No data found."


# @tool
# def analysis_address_on_ethereum(question: str) -> str:
#     """
#     Useful when you need answer user's question about a Ethereum address. Input for this should be a complete question about some Ethereum address.
#     """
#     llm = ChatAnthropic(
#         model="claude-3-opus-20240229",
#         # max_tokens=,
#         temperature=0.9,
#         # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#         streaming=True,
#         verbose=True,
#     ).configurable_alternatives(  # This gives this field an id
#         # When configuring the end runnable, we can then use this id to configure this field
#         ConfigurableField(id="llm"),
#         # default_key="openai_gpt_4_turbo_preview",
#         default_key="anthropic_claude_3_opus",
#         openai_gpt_3_5_turbo_1106=ChatOpenAI(
#             model="gpt-3.5-turbo-1106",
#             verbose=True,
#             streaming=True,
#             temperature=0.1,
#         ),
#         openai_gpt_4_turbo_preview=ChatOpenAI(
#             temperature=0.9,
#             model="gpt-4-turbo-preview",
#             verbose=True,
#             streaming=True,
#         ),
#         openai_gpt_4o=ChatOpenAI(
#             temperature=0.9,
#             model="gpt-4o",
#             verbose=True,
#             streaming=True,
#         ),
#         mistral_large=ChatMistralAI(
#             model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
#         ),
#         command_r_plus=ChatCohere(
#             model="command-r-plus", temperature=0.9, verbose=True, streaming=True
#         ),
#     )
#     llm_extract_address_chain = llm.with_config(
#         {"configurable": {"llm": "openai_gpt_3_5_turbo_1106"}}
#     )
#     prompt_template = """
#     Context:
#     {context}

#     We need extract the Ethereum address from the context above, please extract the address.

#     The Ethereum address in above context is:
#     """
#     _chain_extract_address = (
#         PromptTemplate.from_template(prompt_template)
#         | llm_extract_address_chain
#         | StrOutputParser()
#     )
#     address = _chain_extract_address.invoke({"context": question})
#     address = Web3.to_checksum_address(address)
#     if address == "None":
#         raise Exception(f"Can't extract any address from question:{question}")

#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         future_labels = executor.submit(get_address_labels, {"addresses": [address]})
#         future_token_balances = executor.submit(
#             get_token_balances_of_address, {"address": address}
#         )
#         future_erc20_transfers = executor.submit(
#             get_erc20_transfer_of, {"address": address}
#         )
#         future_eth_transfers = executor.submit(
#             get_eth_transfer_of, {"address": address}
#         )

#         labels = future_labels.result()
#         token_balances_str = future_token_balances.result()
#         erc20_transfer = future_erc20_transfers.result()
#         eth_transfer = future_eth_transfers.result()

#     labels_df = pd.DataFrame(json.loads(labels))
#     if not labels_df.empty:
#         labels = "\n".join(
#             labels_df.apply(
#                 lambda row: row["labels"] + "[" + row["tag"] + "]", axis=1
#             ).tolist()
#         )
#     else:
#         labels = ""

#     token_balances = json.loads(token_balances_str)
#     #

#     # 生成Token余额分析报表
#     token_balance_report = []
#     for token in token_balances:
#         balance_usd = token.get("balance_usd", "N/A")
#         token_balance_report.append(
#             f"Token: {token['token_symbol']} (Contract: {token['token_address']}, Liquidity on DEX in 3 months:${token['total_liquidity_usd']})\n"
#             f"Balance: {token['balance']} (USD: {balance_usd} Price:${token['price_usd']})"
#         )

#     # Token余额分析部分
#     token_analysis = "\n".join(token_balance_report)

#     is_contract = is_contract_address.invoke({"address": address})

#     erc20_transfer_df = pd.DataFrame(json.loads(erc20_transfer))
#     eth_transfer_df = pd.DataFrame(json.loads(eth_transfer))

#     unique_to_addresses = []
#     if not erc20_transfer_df.empty:
#         unique_to_addresses = erc20_transfer_df["to"].unique().tolist()

#     if not eth_transfer_df.empty:
#         unique_to_addresses = np.unique(
#             unique_to_addresses + eth_transfer_df["to"].unique().tolist()
#         ).tolist()

#     if len(unique_to_addresses) > 0:
#         addresses_tags = get_multiple_address_tags.invoke(
#             {"addresses": unique_to_addresses}
#         )
#         tag_df = pd.DataFrame(addresses_tags)

#     if not erc20_transfer_df.empty and not tag_df.empty:
#         erc20_transfer_df = erc20_transfer_df.merge(
#             tag_df, left_on="to", right_on="address", how="left"
#         )
#         erc20_transfer_df.drop(columns=["address"], inplace=True)
#         erc20_transfer_df.rename(columns={"tag": "to_address_tag"}, inplace=True)
#         erc20_transfer = erc20_transfer_df.to_json(orient="records")

#     if not eth_transfer_df.empty and not tag_df.empty:
#         eth_transfer_df = eth_transfer_df.merge(
#             tag_df, left_on="to", right_on="address", how="left"
#         )
#         eth_transfer_df.drop(columns=["address"], inplace=True)
#         eth_transfer_df.rename(columns={"tag": "to_address_tag"}, inplace=True)
#         eth_transfer = eth_transfer_df.to_json(orient="records")

#     if not erc20_transfer_df.empty:
#         erc20_transfer_list = erc20_transfer_df.apply(
#             lambda row: f"{row['from_address']}({row['from_address_labels']}) transfer {row['amount']} USDT({row['contract_address']}) to address {row['to']} (Tags:{row['to_address_labels']}[{row['to_address_tag']}]) at {row['block_time']}.",
#             axis=1,
#         ).tolist()
#         erc20_transfer = "\n".join(erc20_transfer_list)
#     else:
#         erc20_transfer = ""

#     if not eth_transfer_df.empty:
#         eth_transfer_list = eth_transfer_df.apply(
#             lambda row: f"{row['from_address']}({row['from_address_labels']}) transfer {row['eth_value']} ETH to address {row['to']} (Labels:{row['to_address_labels']}[{row['to_address_tag']}]) at {row['block_time']}.",
#             axis=1,
#         ).tolist()
#         eth_transfer = "\n".join(eth_transfer_list)
#     else:
#         eth_transfer = ""

#     llm_chain = llm.with_config({"configurable": {"llm": "openai_gpt_4o"}})
#     prompt_template_1 = """
#     Address: {address}

#     Is a contract address?: {is_contract}

#     Labels:
#     {labels}

#     Token Balances:
#     {token_analysis}

#     Latest 100 ERC20 Transfers History:
#     {erc20_transfer}

#     Lastest 100 ETH Transfers History:
#     {eth_transfer}


#     Please answer the flowing question, and provide a detailed analysis of the address, explaining the following:
#     1. What organization or project this address represents, and give as much information as possible.
#     2. Analyze the transaction behavior and fund movements of this address, including significant transactions and interactions with other addresses.
#     3. Identify and highlight any potential risks associated with this address, such as security risks, fund freezing risks, and any involvement in illicit activities.
#     4. Provide information on other addresses this address interacts with frequently. As much as possible, inform users what project or organization these address data belong to, or who these addresses represent.
#     5. Suggest potential use cases or strategies involving this address.
#     6. Analyze the historical token holdings and transaction volume of this address.
#     7. Identify the main DeFi activities of this address.
#     8. Review any smart contract interactions and assess their significance.
#     9. Provide a time-series analysis of the address’s activity.
#     10. Offer any additional relevant insights based on the available data.

#     Ensure the analysis is deep and comprehensive, covering all relevant aspects.

#     Question: {question}

#     Answer:
#     """
#     _chain = (
#         PromptTemplate.from_template(prompt_template_1) | llm_chain | StrOutputParser()
#     )
#     return _chain.invoke(
#         {
#             "address": address,
#             "is_contract": is_contract,
#             "labels": labels,
#             "token_analysis": token_analysis,
#             "erc20_transfer": erc20_transfer,
#             "eth_transfer": eth_transfer,
#             "question": question,
#         }
#     )


@tool
def get_token_lastest_usd_price(addresses: list[str]) -> str:
    """
    Useful when you need to get the price of token.
    The parameter `address` must be the contract address of the token.
    """
    query = QueryBase(
        name="get_token_usd_price",
        query_id=3917050,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(addresses)
            ),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_token_dex_liquidity_in_3_month(addresses: list[str]) -> str:
    """
    Useful when you need to get the price of token.
    The parameter `address` must be the contract address of the token.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=7)
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="get_token_dex_volume",
        query_id=3922413,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(addresses)
            ),
            QueryParameter.text_type(name="min_time", value=formatted_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def analysis_balances_of_address(address: str):
    """
    Obtains the balance of all tokens for a specified address and provides a distribution chart in USD. Input should be a complete Ethereum address.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算三个月前的时间
    three_months_ago = now - relativedelta(months=3)

    # 3. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = three_months_ago.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_token_balance_of_address",
        query_id=3916915,
        params=[
            QueryParameter.text_type(name="address", value=address),
        ],
    )
    try:
        results_df = dune.run_query_dataframe(query=query)
    except Exception as e:
        return f"Get balance failed. {e}"
    if not results_df.empty:
        # 从数据中提取标签和余额
        labels = results_df["token_symbol"].apply(lambda x: x if x else "NaN").tolist()
        sizes = (
            results_df["balance_usd"]
            .apply(lambda item: float(item) if item != "<nil>" else 0)
            .tolist()
        )

        if sum(sizes) > 0:
            # 创建饼图数据
            pie_data = go.Pie(
                labels=labels,
                values=sizes,
                textinfo="percent+label",
                insidetextorientation="radial",
                textposition="inside",
                hole=0.3,  # 添加一个中心孔，使图表更现代
                marker=dict(line=dict(color="#000000", width=2)),  # 添加黑色边框
                pull=[
                    0.1 if size > 0.05 * sum(sizes) else 0 for size in sizes
                ],  # 突出显示大于5%的部分
            )

            # 创建布局
            layout = go.Layout(
                title="Token Balance Distribution in USD",
                showlegend=True,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",  # 设置背景透明
                plot_bgcolor="rgba(0,0,0,0)",
            )

            # 创建图形
            fig = go.Figure(data=[pie_data], layout=layout)

            # 保存为HTML文件
            random_filename = f"token_balance_distribution_{uuid.uuid4()}.html"
            fig.write_html(random_filename)

            # 上传文件到 S3 存储桶的 charts 文件夹
            s3_client.upload_file(
                random_filename,
                "musse.ai",
                f"charts/{random_filename}",
                ExtraArgs={"ContentType": "text/html"},
            )
            os.remove(random_filename)

            # img_str = (
            #     f"Below is the URL of the balance distribution chart. The title of the chart is: Token Balance Distribution in USD."
            #     + "\n"
            #     + f'You can use the Interactive Chart in HTML like this: <iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="800px" title="Token Balance Distribution chart"></iframe>'
            # )
            img_str = f'\n<iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="800px" title="Token Balance Distribution chart"></iframe>'
            r_arr = results_df.apply(
                lambda row: f"Token: {row['token_symbol']}\nContract address: {row['token_address']}\n"
                + f"Balance: {row['balance']} (USD: {row['balance_usd']} Price:${row['price_usd']})",
                axis=1,
            ).tolist()
            result = f"\n## Balances of address {address}:\n" + "\n".join(r_arr)
            return result, img_str
        else:
            r_arr = results_df.apply(
                lambda row: f"Token: {row['token_symbol']}\nContract address: {row['token_address']}\n"
                + f"Balance: {row['balance']} (USD: {row['balance_usd']} Price:${row['price_usd']})",
                axis=1,
            ).tolist()
            result = f"## Balances of address {address}:\n" + "\n".join(r_arr)
            return result
    else:
        return "No Balances Found."


@tool
def get_token_balance_daily_of_address(address: str, token_address: str):
    """
    Retrieves daily balance data for a specified token on an address for the past month. Input should include the address and token address.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一个月的时间
    one_month_ago = now - relativedelta(months=1)

    # 3. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = one_month_ago.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_address_token_balances_daily",
        query_id=3954430,
        params=[
            QueryParameter.text_type(name="min_time", value=formatted_time),
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="token_address", value=token_address),
        ],
    )
    df = dune.run_query_dataframe(query=query)
    if not df.empty:
        # 将日期列转换为 datetime 对象
        df["block_time"] = pd.to_datetime(df["block_time"])

        # 按日期排序
        df.sort_values(by="block_time", inplace=True)

        # 使用plotly创建图表
        fig = make_subplots(specs=[[{"secondary_y": False}]])

        symbol = df["token_symbol"].iloc[0]

        fig.add_trace(
            go.Scatter(
                x=df["block_time"],
                y=df["balance"],
                mode="lines+markers",
                name="Balance",
                line=dict(color="skyblue", width=2),
                marker=dict(size=8),
            )
        )

        # 设置布局
        fig.update_layout(
            title=f"Daily Balance Changes for {symbol} Token",
            xaxis_title="Date",
            yaxis_title=f"Balance ({symbol})",
            font=dict(size=14),
            legend=dict(x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.8)"),
            hovermode="x unified",
        )

        # 设置x轴日期格式
        fig.update_xaxes(
            tickformat="%b %d, %Y", tickangle=45, tickmode="auto", nticks=20
        )

        # 保存图表为HTML文件
        random_filename = f"daily_balance_changes_{uuid.uuid4()}.html"
        fig.write_html(random_filename)

        # 上传文件到 S3 存储桶的 charts 文件夹
        s3_client.upload_file(
            random_filename,
            "musse.ai",
            f"charts/{random_filename}",
            ExtraArgs={"ContentType": "text/html"},
        )
        os.remove(random_filename)

        # img_str = (
        #     f"Below is the URL for the daily balance change chart. The title of the chart is: Daily Balance Changes for {symbol} Token"
        #     + "\n"
        #     + f'You can use the Interactive Chart in HTML like this: <iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="800px" title="Daily Balance Changes for {symbol} Token"></iframe>'
        # )
        img_str = (
            +f'\n<iframe src="https://musse.ai/charts/{random_filename}" width="100%" height="800px" title="Daily Balance Changes for {symbol} Token"></iframe>'
        )

        if not df.empty:
            r_arr = df.apply(
                lambda row: f"The balance on {row['block_time'].strftime('%Y-%m-%d')} is {row['balance']}.",
                axis=1,
            ).tolist()
            result = f"Daily Balance Changes for {symbol} Token:\n" + "\n".join(r_arr)
            return result, img_str
        return result
    else:
        return "No daily balances data found."


# @tool
# def extract_main_token_of_balances(balances_json: str) -> str:
#     """
#     Useful when you need extract main token in the balances return from `get_token_balances_of_address`.
#     """
#     return json.dumps(extract_token_from_balances(balances_json))


def update_top_tokens(token_list, new_token, key, top_n=5):
    token_list.append(new_token)
    token_list.sort(key=lambda x: x[key], reverse=True)

    if len(token_list) > top_n:
        token_list.pop()


def extract_token_from_balances(data: str) -> dict:
    data = json.loads(data)
    top_value_tokens = []
    top_liquidity_tokens = []

    for token in data:
        balance_usd = token.get("balance_usd")
        total_liquidity_usd = token.get("total_liquidity_usd")

        if balance_usd is not None and balance_usd != "<nil>":
            balance_usd = float(balance_usd)
            update_top_tokens(top_value_tokens, token, "balance_usd")

        if total_liquidity_usd is not None and total_liquidity_usd != "<nil>":
            total_liquidity_usd = float(total_liquidity_usd)
            update_top_tokens(top_liquidity_tokens, token, "total_liquidity_usd")

    top_value_addresses = [
        {
            "address": token["token_address"],
            "symbol": token["token_symbol"],
        }
        for token in top_value_tokens
    ]
    top_liquidity_addresses = [
        {
            "address": token["token_address"],
            "symbol": token["token_symbol"],
        }
        for token in top_liquidity_tokens
    ]

    result = {
        "high_price_token": top_value_addresses,
        "high_liquidity_token": top_liquidity_addresses,
    }
    return result


dune_tools = [
    what_is_time_now,
    get_address_labels,
    analysis_balances_of_address,
    get_token_balance_daily_of_address,
    get_funds_transfer_status_in_transaction,
    get_address_interact_with,
    get_addres_funds_movements_of,
    # get_eth_movements_of,
    # get_addres_how_much_funds_received,
    # get_addres_how_much_funds_transfered,
    get_how_much_eth_recieved,
    get_how_much_eth_transfered,
]
