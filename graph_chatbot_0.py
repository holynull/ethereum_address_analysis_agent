from typing import Annotated, Any, Dict, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere

from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import (
    Runnable,
    RunnableBinding,
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="llm"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_5_sonnet",
    anthropic_claude_3_opus=ChatAnthropic(
        model="claude-3-opus-20240229",
        # max_tokens=,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        verbose=True,
    ),
    anthropic_claude_3_7_sonnet=ChatAnthropic(
        model="claude-3-7-sonnet-20250219",
        # max_tokens=,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        verbose=True,
    ),
    openai_gpt_4o=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_3_5_turbo_1106=ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        verbose=True,
        streaming=True,
        temperature=0.9,
    ),
    openai_gpt_4_turbo_preview=ChatOpenAI(
        temperature=0.9,
        model="gpt-4-turbo-preview",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o_mini=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o-mini",
        verbose=True,
        streaming=True,
    ),
    pplx_sonar_medium_chat=ChatPerplexity(
        model="sonar-medium-chat", temperature=0.9, verbose=True, streaming=True
    ),
    mistral_large=ChatMistralAI(
        model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)

from system_prompt_9_swap import system_prompt


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    wallet_is_connected: bool
    chain_id: int
    wallet_address: str
    llm: str


graph_builder = StateGraph(State)

from tools_basic import tools


from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable


def format_messages(state: State):
    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
    )
    return system_message + state["messages"]


system_message = RunnableCallable(format_messages)


def call_model(state: State, config: RunnableConfig) -> State:
    llm_with_tools = llm.with_config(
        {
            "configurable": {"llm": state["llm"]},
        }
    ).bind_tools(tools)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, model_runnable.invoke(state, config))

    return {"messages": [response]}


async def acall_model(state: State, config: RunnableConfig) -> State:
    llm_with_tools = llm.with_config(
        {
            "configurable": {"llm": state["llm"]},
        }
    ).bind_tools(tools)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, await model_runnable.ainvoke(state, config))

    return {"messages": [response]}


# def chatbot(state: State):
#     system_template = SystemMessagePromptTemplate.from_template(system_prompt)
#     system_message = system_template.format_messages(
#         wallet_is_connected=state["wallet_is_connected"],
#         chain_id=state["chain_id"],
#         wallet_address=state["wallet_address"],
#     )

#     return {"messages": [llm_with_tools.invoke(system_message + state["messages"])]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="tools")

from langgraph.utils.runnable import RunnableCallable

# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", RunnableCallable(call_model, acall_model))
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
    {"tools": "tools", END: END},
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile()
