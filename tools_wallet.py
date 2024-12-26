from langchain.agents import tool
import boto3
import os
import uuid
from langchain.prompts import PromptTemplate

@tool
def connect_to_metamask():
    """Notify front end to connect to MetaMask Wallet.
    """

    return "Already notify front end to connect to MetaMask Wallet." 

tools = [
    connect_to_metamask,
]
