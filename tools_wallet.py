from langchain.agents import tool
from solana.rpc.api import Client
from spl.token.client import Token
from web3 import Web3

# Chain configuration data
CHAIN_CONFIG = {
    "ethereum": {
        "chainId": "0x1",
        "chainData": {
            "chainId": "0x1",
            "chainName": "Ethereum Mainnet",
            "nativeCurrency": {"name": "Ether", "symbol": "ETH", "decimals": 18},
            "rpcUrls": ["https://eth.public-rpc.com"],
            "blockExplorerUrls": ["https://etherscan.io"],
        },
    },
    "bsc": {
        "chainId": "0x38",
        "chainData": {
            "chainId": "0x38",
            "chainName": "Binance Smart Chain",
            "nativeCurrency": {"name": "BNB", "symbol": "BNB", "decimals": 18},
            "rpcUrls": ["https://bsc-dataseed.bnbchain.org"],
            "blockExplorerUrls": ["https://bscscan.com"],
        },
    },
    "polygon": {
        "chainId": "0x89",
        "chainData": {
            "chainId": "0x89",
            "chainName": "Polygon Mainnet",
            "nativeCurrency": {"name": "MATIC", "symbol": "MATIC", "decimals": 18},
            "rpcUrls": ["https://polygon-rpc.com"],
            "blockExplorerUrls": ["https://polygonscan.com"],
        },
    },
    "arbitrum": {
        "chainId": "0xa4b1",
        "chainData": {
            "chainId": "0xa4b1",
            "chainName": "Arbitrum One",
            "nativeCurrency": {"name": "Ethereum", "symbol": "ETH", "decimals": 18},
            "rpcUrls": ["https://arb1.arbitrum.io/rpc"],
            "blockExplorerUrls": ["https://arbiscan.io"],
        },
    },
    "optimism": {
        "chainId": "0xa",
        "chainData": {
            "chainId": "0xa",
            "chainName": "Optimism",
            "nativeCurrency": {"name": "Ethereum", "symbol": "ETH", "decimals": 18},
            "rpcUrls": ["https://mainnet.optimism.io"],
            "blockExplorerUrls": ["https://optimistic.etherscan.io"],
        },
    },
    "solana": {
        "chainId": "solana",

        "chainData": {
            "chainId": "0x65",
            "chainName": "Solana Mainnet",
            "nativeCurrency": {"name": "Solana", "symbol": "SOL", "decimals": 9},
            "rpcUrls": ["https://api.mainnet-beta.solana.com"],
            "blockExplorerUrls": ["https://explorer.solana.com"],
        },
    },
}

# Minimal ABI for ERC20 balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
]


@tool
def connect_to_wallet():
    """Notify front end to connect to wallet."""

    return "Error: The wallet is not ready. But already notify front end to connect to wallet."


def generate_erc20_transfer_data(to_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token transfer.

    Args:
        to_address: The recipient address
        amount: The amount to transfer (in token's smallest unit)

    Returns:
        The hex string of unsigned transaction data
    """
    # ERC20 transfer function signature
    transfer_function_signature = "transfer(address,uint256)"

    # Create Web3 instance
    w3 = Web3()

    # Create function signature
    fn_selector = w3.keccak(text=transfer_function_signature)[:4].hex()

    # Encode parameters
    # Pad address to 32 bytes
    padded_address = Web3.to_bytes(hexstr=to_address).rjust(32, b"\0")
    # Pad amount to 32 bytes
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")

    # Combine all parts
    data = fn_selector + padded_address.hex() + padded_amount.hex()

    return data


@tool
def get_erc20_decimals(token_address: str, chain_id) -> dict:
    """Get the decimals of an ERC20 token.

    Args:
        token_address: The address of the ERC20 token contract
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the decimals information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure address is checksummed
    token_address = Web3.to_checksum_address(token_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get decimals
        decimals = token_contract.functions.decimals().call()

        return {
            "success": True,
            "decimals": decimals,
            "token_address": token_address,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "token_address": token_address,
        }


@tool
def generate_transfer_erc20_tx_data(
    token_address: str, to_address: str, amount: str, chain_id: int = 1
):
    """Generate transaction data for transfer ERC20 token to `to_address`.

    Args:
        token_address: The address of the ERC20 token contract
        to_address: The recipient address
        amount: The amount to transfer (in token's smalest unit)
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A message and the hex string of unsigned transaction data
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id, rpc_urls[1]
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    to_address = Web3.to_checksum_address(to_address)

    # Generate transaction data
    tx_data = generate_erc20_transfer_data(to_address=to_address, amount=amount)

    # Prepare transaction object for gas estimation
    tx = {
        "to": token_address,
        "data": tx_data,
        "from": to_address,  # Using recipient address for estimation
    }

    try:
        # Estimate gas limit
        gas_limit = w3.eth.estimate_gas(tx)
        # Get current gas price
        gas_price = w3.eth.gas_price
    except Exception as e:
        gas_limit = 0
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": token_address,
            "data": tx_data,
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "value": "0x0",
            "chain_id": chain_id,
        },
    )


@tool
def get_balance_of_address(
    token_address: str, wallet_address: str, chain_id: int
) -> dict:
    """Get the balance of an ERC20 token for a specific address.

    Args:
        token_address: The address of the ERC20 token contract
        wallet_address: The address to check the balance for
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the balance information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found
    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    wallet_address = Web3.to_checksum_address(wallet_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get balance
        balance = token_contract.functions.balanceOf(wallet_address).call()

        return {
            "success": True,
            "balance": str(balance),
            "wallet_address": wallet_address,
            "token_address": token_address,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "wallet_address": wallet_address,
            "token_address": token_address,
        }


@tool
def generate_transfer_native_token(to_address: str, amount: str, chain_id: int = 1):
    """Generate transaction data for transfer native token (like ETH, BNB) to `to_address`.

    Args:
        to_address: The recipient address
        amount: The amount to transfer (in wei)
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A message and the transaction data for signing
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id, rpc_urls[1]
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure address is checksummed
    to_address = Web3.to_checksum_address(to_address)

    try:
        # Get current gas price
        gas_price = w3.eth.gas_price
        # For native token transfers, gas limit is typically 21000
        gas_limit = 21000
    except Exception as e:
        gas_limit = 21000
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": to_address,
            "value": amount,  # amount in wei
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "data": "0x",  # Empty data for native token transfer
            "chain_id": chain_id,
        },
    )


@tool
def change_network_to(target_network: str):
    """Change the connected network to the target network in wallet.

    Args:
        target_network: Network name to switch to. Available networks: ethereum, bsc, polygon, arbitrum, optimism

    Returns:
        A tuple containing a message and the chain configuration data
    """
    target_network = target_network.lower()
    if target_network not in CHAIN_CONFIG:
        return (
            "Invalid network specified. Available networks: ethereum, bsc, polygon, arbitrum, optimism",
            None,
        )

    chain_config = CHAIN_CONFIG[target_network]
    return (
        f"Already notify the front end to switch to {target_network.capitalize()} network.",
        chain_config,
    )


def generate_erc20_approve_data(spender_address: str, amount: str) -> str:
    """Generate unsigned transaction data for ERC20 token approve.

    Args:
        spender_address: The spender address to approve
        amount: The amount to approve (in token's smallest unit)

    Returns:
        The hex string of unsigned transaction data
    """
    # ERC20 approve function signature
    approve_function_signature = "approve(address,uint256)"

    # Create Web3 instance
    w3 = Web3()

    # Create function signature
    fn_selector = w3.keccak(text=approve_function_signature)[:4].hex()

    # Encode parameters
    # Pad address to 32 bytes
    padded_address = Web3.to_bytes(hexstr=spender_address).rjust(32, b"\0")
    # Pad amount to 32 bytes
    amount_int = int(amount)
    padded_amount = amount_int.to_bytes(32, "big")

    # Combine all parts
    data = fn_selector + padded_address.hex() + padded_amount.hex()

    return data


@tool
def generate_approve_erc20(
    token_address: str, spender_address: str, amount: str, chain_id: int
):
    """Generate tansaction data for approve spender to use ERC20 token.

    Args:
        token_address: The address of the ERC20 token contract
        spender_address: The address to approve
        amount: The amount to approve (in token's smallest unit)
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A message and the hex string of unsigned transaction data
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    spender_address = Web3.to_checksum_address(spender_address)

    # Generate transaction data
    tx_data = generate_erc20_approve_data(
        spender_address=spender_address, amount=amount
    )

    # Prepare transaction object for gas estimation
    tx = {
        "to": token_address,
        "data": tx_data,
        "from": spender_address,  # Using spender address for estimation
    }

    try:
        # Estimate gas limit
        gas_limit = w3.eth.estimate_gas(tx)
        # Get current gas price
        gas_price = w3.eth.gas_price
    except Exception as e:
        gas_limit = 0
        gas_price = 0

    return (
        "Already notify the front end to sign the transaction data and send the transaction.",
        {
            "to": token_address,
            "data": tx_data,
            "gasLimit": str(gas_limit),
            "gasPrice": str(gas_price),
            "value": "0x0",
            "chain_id": chain_id,
        },
    )


@tool
def allowance_erc20(
    token_address: str, owner_address: str, spender_address: str, chain_id: int
) -> dict:
    """Check the approved amount of an ERC20 token for a specific spender.

    Args:
        token_address: The address of the ERC20 token contract
        owner_address: The address who approved the tokens
        spender_address: The address to check the allowance for
        chain_id: Chain ID of the network (default: 1 for Ethereum mainnet)

    Returns:
        A dictionary containing the allowance information
    """
    # RPC URL mapping for different chains
    rpc_urls = {
        1: "https://eth.public-rpc.com",  # Ethereum mainnet
        56: "https://bsc-dataseed.bnbchain.org",  # BSC mainnet
        137: "https://polygon-rpc.com",  # Polygon mainnet
        42161: "https://arb1.arbitrum.io/rpc",  # Arbitrum One
        10: "https://mainnet.optimism.io",  # Optimism
    }
    rpc_url = rpc_urls.get(
        chain_id
    )  # Default to Ethereum mainnet if chain_id not found

    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Ensure addresses are checksummed
    token_address = Web3.to_checksum_address(token_address)
    owner_address = Web3.to_checksum_address(owner_address)
    spender_address = Web3.to_checksum_address(spender_address)

    try:
        # Create contract instance
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Get allowance
        allowance = token_contract.functions.allowance(
            owner_address, spender_address
        ).call()

        return {
            "success": True,
            "allowance": str(allowance),
            "owner_address": owner_address,
            "spender_address": spender_address,
            "token_address": token_address,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "owner_address": owner_address,
            "spender_address": spender_address,
            "token_address": token_address,
        }


@tool
def get_sol_token_balance(wallet_address: str, token_mint_address: str) -> dict:
    """Get the balance of a SPL token for a specific Solana address.

    Args:
        wallet_address: The Solana address to check the balance for
        token_mint_address: The mint address of the SPL token

    Returns:
        A dictionary containing the balance information
    """
    # try:
    # Connect to Solana network using default RPC URL
    client = Client(CHAIN_CONFIG['solana']['chainData']['rpcUrls'][0])
    
    # Get token account
    token_accounts = client.get_token_accounts_by_owner(
        wallet_address,
        {'mint': token_mint_address}
    ).value
    
    if not token_accounts:
        return {
            'success': False,
            'error': 'No token account found',
            'wallet_address': wallet_address,
            'token_mint_address': token_mint_address
        }
    
    # Get balance from the first token account
    balance = int(token_accounts[0].account.data['parsed']['info']['tokenAmount']['amount'])
    decimals = int(token_accounts[0].account.data['parsed']['info']['tokenAmount']['decimals'])
    
    return {
        'success': True,
        'balance': str(balance),
        'decimals': decimals,
        'wallet_address': wallet_address,
        'token_mint_address': token_mint_address
    }
        
    # except Exception as e:
    #     return {
    #         'success': False,
    #         'error': str(e),
    #         'wallet_address': wallet_address,
    #         'token_mint_address': token_mint_address
    #     }

tools = [
    connect_to_wallet,
    # generate_transfer_erc20_tx_data,
    get_balance_of_address,
    get_erc20_decimals,
    # generate_transfer_native_token,
    change_network_to,
    generate_approve_erc20,
    allowance_erc20,
    get_sol_token_balance,
]
