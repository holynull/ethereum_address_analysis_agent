import datetime
from langchain_core.tools import tool


@tool
def route_to_swap_agent():
    """
    This tool will hand over the question to a Cryptocurrency Swap Expert.
    Expert capabilities include:
        - Get the list of supported tokens for token cross chain swap functionality.
        - Get a detailed quote for token cross chain swap transaction, including expected output amount, fees, and transaction parameters.
        - Notify the front end to generate a button to send a token swap transaction.
        - Get transaction records using the Bridgers API.
        - Get detailed information about a specific transaction using the Bridgers API.
    """
    return "Now requesting a Cryptocurrency Swap Expert."


@tool
def route_to_wallet_agent():
    """
    This tool will hand over the question to a Cryptocurrency Wallet Expert.
    Expert capabilities include:
        - Notify front end to connect to wallet.
        - Generate unsigned transaction data for ERC20 token transfer.
        - Get the decimals of an ERC20 token.
        - Generate transaction data for transfer ERC20 token to `to_address`.
        - Get the balance of an ERC20 token for a specific address.
        - Generate transaction data for transfer native token (like ETH, BNB) to `to_address`.
        - Notify the front end to change the connected network to the target network in wallet.
        - Generate unsigned transaction data for ERC20 token approve.
        - Notify the front end to generate a button to send tansaction data for approve spender to use ERC20 token.
        - Check the approved amount of an ERC20 token for a specific spender.
        - Query SOL balance for a specified wallet address on Solana blockchain.
        - Query SPL token balance for a specified wallet address on Solana blockchain.
        - Get TRC20 token balance of a wallet address.
        - Get TRX balance of a wallet address.
        - Notify the front end to generate a button to send transaction data for TRC20 token approve.
        - Generate transaction data for approving TRC20 token spending.
        - Get the approved amount of a TRC20 token for a specific spender.
    """
    return "Now requesting a Cryptocurrency Wallet Expert"


@tool
def route_to_search_agent():
    """
    This tool will hand over the question to a Search Engine Expert.
    Expert capabilities include:
        - Performs a web search using Google search engine and returns formatted results.
        - Performs a news search using Google News and returns formatted results in JSON format.
        - Performs a place search using Google Places API and returns raw search results.
        - Performs an image search using Google Images and returns raw search results.
        - Access the links content
    """
    return "Now requesting a Search Engine Expert."


@tool
def route_to_cryptocurrency_quote_agent():
    """
    This tool will hand over the question to a Cryptocurrency Market Analysis Expert.
    Expert capabilities include:
        - Retrieves the latest cryptocurrency quotation data from CoinMarketCap API.
        - Retrieves detailed metadata and information about a cryptocurrency from CoinMarketCap API.
        - Analyzes trading signals for cryptocurrency pairs against USDT using TradingView technical analysis.
    """
    return "Now requesting a Cryptocurrency Market Analysis Expert."


@tool
def route_to_image_agent():
    """
    This tool will hand over the question to a Text-to-Image Generation Expert.
    Expert capabilities include:
        - Generate images and return markdown format image links of generated images, separated by newlines.
    """
    return "Now requesting a Text-to-Image Generation Expert."


@tool
def get_utc_time():
    """
    Useful when you need to get the current UTC time of the system.
    Returns the current UTC time in ISO format (YYYY-MM-DD HH:MM:SS.mmmmmm).
    """
    import pytz

    return datetime.datetime.now(tz=pytz.UTC).isoformat(" ")


from graph_swap import graph as swap_graph
from graph_wallet import graph as wallet_graph
from graph_search import graph as search_webpage_graph
from graph_quote import graph as quote_graph
from graph_image import graph as image_graph


def get_next_node(tool_name: str):
    if tool_name == route_to_swap_agent.get_name():
        return swap_graph.get_name()
    elif tool_name == route_to_wallet_agent.get_name():
        return wallet_graph.get_name()
    elif tool_name == route_to_search_agent.get_name():
        return search_webpage_graph.get_name()
    elif tool_name == route_to_cryptocurrency_quote_agent.get_name():
        return quote_graph.get_name()
    elif tool_name == route_to_image_agent.get_name():
        return image_graph.get_name()
    else:
        return None


tools = [
    get_utc_time,
    route_to_swap_agent,
    route_to_wallet_agent,
    route_to_search_agent,
    route_to_cryptocurrency_quote_agent,
    route_to_image_agent,
]
