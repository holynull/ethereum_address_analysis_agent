"""Main entrypoint for the app."""

import asyncio
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import langsmith
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from api_handler import APIHandler

# from langsmith import Client
from pydantic import BaseModel, Field
import requests

from agent import create_agent_executor
from agent import llm_agent
from langchain.memory import ConversationBufferMemory

# client = Client()
origins = [
    "*",
    "http://localhost",
    "http://localhost:3000",
    "http://192.168.3.6:3000",
    "http://musse.ai",
]
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage


class Input(BaseModel):
    messages: list[dict]
    wallet_address: str
    chain_id: str
    wallet_is_connected: bool
    time_zone: str
    llm: str
    # image_urls: list[str]
    # pdf_files: list[str]
    # chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]]


class Output(BaseModel):
    output: Any


chat_memories = {}
agent_executors = {}

# from graph_chatbot import graph_builder as swap_graph_builder

from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

# graph = swap_graph_builder.compile(checkpointer=memory, debug=False)

from graph_chatbot import graph_builder

graph = graph_builder.compile(checkpointer=memory, debug=False)


@app.post("/chat/stream", include_in_schema=False)
async def simple_invoke(request: Request) -> Response:
    """Handle a request."""
    # The API Handler validates the parts of the request
    # that are used by the runnnable (e.g., input, config fields)
    # body = await request.json()
    # conversation_id = body["config"]["metadata"]["conversation_id"]
    # is_multimodal = body["config"]["metadata"]["is_multimodal"]
    # image_urls = body["input"]["image_urls"]
    # pdf_files = body["input"]["pdf_files"]
    # if conversation_id in chat_memories:
    #     # agent_executor = agent_executors[conversation_id]
    #     memory = chat_memories[conversation_id]
    #     agent_executor = create_agent_executor(
    #         llm_agent=llm_agent,
    #         memory=memory,
    #         is_multimodal=is_multimodal,
    #         image_urls=image_urls,
    #         pdf_files=pdf_files,
    #     )
    #     agent_executors[conversation_id] = {
    #         "executor": agent_executor,
    #         "is_multimodal": is_multimodal,
    #     }
    #     api_handler = APIHandler(
    #         agent_executor.with_types(input_type=Input, output_type=Output),
    #         path="/chat",
    #         # config_keys=["metadata", "configurable", "tags", "llm"],
    #     )
    # else:
    #     memory = ConversationBufferMemory(
    #         input_key="input", memory_key="chat_history", return_messages=True
    #     )
    #     agent_executor = create_agent_executor(
    #         llm_agent=llm_agent,
    #         memory=memory,
    #         is_multimodal=is_multimodal,
    #         image_urls=image_urls,
    #         pdf_files=pdf_files,
    #     )
    #     chat_memories[conversation_id] = memory
    #     agent_executors[conversation_id] = {
    #         "executor": agent_executor,
    #         "is_multimodal": is_multimodal,
    #     }
    #     api_handler = APIHandler(
    #         agent_executor.with_types(input_type=Input, output_type=Output),
    #         path="/chat",
    #         # config_keys=["metadata", "configurable", "tags", "llm"],
    #     )
    api_handler = APIHandler(
        graph.with_types(input_type=Input, output_type=Output),
        path="/chat",
    )
    return await api_handler.astream_events(request)


def generate_swap_order(
    hash: str,
    from_token_address: str,
    to_token_address: str,
    from_address: str,
    to_address: str,
    from_token_chain: str,
    to_token_chain: str,
    from_token_amount: str,
    amount_out_min: str,
    from_coin_code: str,
    to_coin_code: str,
    source_type: str = None,
    slippage: str = None,
) -> Optional[Dict]:
    """
    Generate an order record for token swap transaction using the Bridgers API.

    Args:
        hash (str): Transaction hash
        from_token_address (str): Source token contract address
        to_token_address (str): Destination token contract address
        from_address (str): User's wallet address
        to_address (str): Destination address
        from_token_chain (str): Source token chain
        to_token_chain (str): Destination token chain
        from_token_amount (str): Amount of source token
        amount_out_min (str): Minimum output amount
        from_coin_code (str): Source token code
        to_coin_code (str): Destination token code
        source_type (str, optional): Device type (H5/IOS/Android)
        slippage (str, optional): Slippage tolerance

    Returns:
        Optional[Dict]: Returns order information containing:
            - resCode: Response code (100 for success)
            - resMsg: Response message
            - data.orderId: Generated order ID
        Returns error message string if the request fails
    """
    try:
        # API endpoint
        url = "https://api.bridgers.xyz/api/exchangeRecord/updateDataAndStatus"

        # Prepare required parameters
        params = {
            "equipmentNo": from_address,
            "sourceFlag": "MUSSE_AI",
            "hash": hash,
            "fromTokenAddress": from_token_address,
            "toTokenAddress": to_token_address,
            "fromAddress": from_address,
            "toAddress": to_address,
            "fromTokenChain": from_token_chain,
            "toTokenChain": to_token_chain,
            "fromTokenAmount": from_token_amount,
            "amountOutMin": amount_out_min,
            "fromCoinCode": from_coin_code,
            "toCoinCode": to_coin_code,
        }

        # Add optional parameters if provided
        if source_type:
            params["sourceType"] = source_type
        if slippage:
            params["slippage"] = slippage

        # Send POST request
        response = requests.post(url, json=params)
        response.raise_for_status()

        # Parse response data
        data = response.json()

        # Check response status code
        if data.get("resCode") != 100:
            return f"API request failed: {data.get('resMsg')}"

        # Return order data
        return data

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except ValueError as e:
        return f"API response parsing failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# add_routes(
#     app,
#     agent_executor.with_types(input_type=Input, output_type=Output),
#     path="/chat",
#     input_type=Input,
#     output_type=Output,
#     # config_keys=["metadata", "configurable", "tags"],
# )


class GenerateSwapOrderRequest(BaseModel):
    hash: str
    from_token_address: str
    to_token_address: str
    from_address: str
    to_address: str
    from_token_chain: str
    to_token_chain: str
    from_token_amount: str
    amount_out_min: str
    from_coin_code: str
    to_coin_code: str
    source_type: str | None = Field(default=None)
    slippage: str | None = Field(default=None)


@app.post("/api/generate_swap_order")
async def create_swap_order(request: GenerateSwapOrderRequest) -> dict:
    """Generate a swap order record.

    Args:
        request (GenerateSwapOrderRequest): The swap order details

    Returns:
        dict: The generated order information or error message
    """
    try:
        result = generate_swap_order(
            hash=request.hash,
            from_token_address=request.from_token_address,
            to_token_address=request.to_token_address,
            from_address=request.from_address,
            to_address=request.to_address,
            from_token_chain=request.from_token_chain.upper(),
            to_token_chain=request.to_token_chain.upper(),
            from_token_amount=request.from_token_amount,
            amount_out_min=request.amount_out_min,
            from_coin_code=request.from_coin_code,
            to_coin_code=request.to_coin_code,
            source_type=request.source_type,
            slippage=request.slippage,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


class SendFeedbackBody(BaseModel):
    run_id: UUID
    key: str = "user_score"

    score: Union[float, int, bool, None] = None
    feedback_id: Optional[UUID] = None
    comment: Optional[str] = None


@app.post("/feedback")
async def send_feedback(body: SendFeedbackBody):
    # client.create_feedback(
    #     body.run_id,
    #     body.key,
    #     score=body.score,
    #     comment=body.comment,
    #     feedback_id=body.feedback_id,
    # )
    return {"result": "posted feedback successfully", "code": 200}


class UpdateFeedbackBody(BaseModel):
    feedback_id: UUID
    score: Union[float, int, bool, None] = None
    comment: Optional[str] = None


@app.patch("/feedback")
async def update_feedback(body: UpdateFeedbackBody):
    feedback_id = body.feedback_id
    if feedback_id is None:
        return {
            "result": "No feedback ID provided",
            "code": 400,
        }
    # client.update_feedback(
    #     feedback_id,
    #     score=body.score,
    #     comment=body.comment,
    # )
    return {"result": "patched feedback successfully", "code": 200}


# TODO: Update when async API is available
async def _arun(func, *args, **kwargs):
    return await asyncio.get_running_loop().run_in_executor(None, func, *args, **kwargs)


# async def aget_trace_url(run_id: str) -> str:
#     for i in range(5):
#         try:
#             await _arun(client.read_run, run_id)
#             break
#         except langsmith.utils.LangSmithError:
#             await asyncio.sleep(1**i)

#     if await _arun(client.run_is_shared, run_id):
#         return await _arun(client.read_run_shared_link, run_id)
#     return await _arun(client.share_run, run_id)


class GetTraceBody(BaseModel):
    run_id: UUID


# @app.post("/get_trace")
# async def get_trace(body: GetTraceBody):
#     run_id = body.run_id
#     if run_id is None:
#         return {
#             "result": "No LangSmith run ID provided",
#             "code": 400,
#         }
#     return await aget_trace_url(str(run_id))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
