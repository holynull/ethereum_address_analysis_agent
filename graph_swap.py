from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

_llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)

from system_prompt_9_swap import system_prompt


class SwapGraphState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    wallet_is_connected: bool
    chain_id: int
    wallet_address: str


graph_builder = StateGraph(SwapGraphState)

from tools_swap import tools as tools_swap

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable


def format_messages(state: SwapGraphState):
    from prompt_swap import system_prompt

    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
    )
    return system_message + state["messages"]


system_message = RunnableCallable(format_messages)


def call_model_swap(state: SwapGraphState, config: RunnableConfig) -> SwapGraphState:
    llm_with_tools = _llm.bind_tools(tools_swap)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, model_runnable.invoke(state, config))

    return {"messages": [response]}


async def acall_model_swap(
    state: SwapGraphState, config: RunnableConfig
) -> SwapGraphState:
    llm_with_tools = _llm.bind_tools(tools_swap)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, await model_runnable.ainvoke(state, config))

    return {"messages": [response]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools_swap, name="node_tools")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model_swap, acall_model_swap, name="node_llm")
graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())
graph = graph_builder.compile()
graph.name = "graph_swap"
