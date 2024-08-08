from pathlib import Path
import sys
from fastapi import FastAPI
from dotenv import load_dotenv

from my_langchain_anthropic.experimental import ChatAnthropicTools
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere

# from callback import AgentCallbackHandler
# from langchain.callbacks.manager import AsyncCallbackManager
from datetime import datetime


# from langsmith import Client
from fastapi.middleware.cors import CORSMiddleware

from langchain.agents import AgentExecutor
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from datetime import datetime
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from anthropic_tools import (
    AnthropicToolsAgentOutputParser,
    format_to_anthropic_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser

# from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import Runnable


from langchain import hub
from tools_basic import tools
from eddie_tools import getHTMLOfURL

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")

from langsmith import Client

langsmith_client = Client()

# client = Client()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def create_agent_executor(llm_agent: Runnable) -> AgentExecutor:

    system_message = """You are an expert in the Ethereum blockchain. When answering users' questions, please use the user's language.

To begin, please obtain the current date and time first.

When asked to analyze an Ethereum address or query for recent data, follow these steps to ensure a comprehensive analysis:

1. **Get Current Time**: Before analyzing any time-sensitive data or querying recent information, please obtain the current date and time.

2. **Organization or Project Representation**: Identify the organization or project that this address represents, providing as much relevant information as possible.

3. **Transaction Behavior Analysis**: Analyze the transaction behavior and fund movements of this address, including significant transactions and interactions with other addresses.

4. **Risk Identification**: Highlight any potential risks associated with this address, such as security vulnerabilities, fund freezing risks, and possible involvement in illicit activities.

5. **Frequent Interactions**: Provide insights into other addresses that frequently interact with this one. Utilize address labeling tools to identify and explain the labels of these addresses, offering background information on the associated projects, organizations, or individuals. Specifically, fulfill the following requirements:
   a. Obtain a list of addresses that have frequent interactions with this address.
   b. Use address labeling tools to retrieve label information for these addresses (such as project, organization, or individual).
   c. Analyze these labels to describe the projects, organizations, or individuals these interacting addresses represent.

6. **Use Cases or Strategies**: Suggest potential use cases or strategies involving this address.

7. **Current Token Holdings Analysis**: Conduct a detailed analysis of the current token holdings of this address, including:
   a. The types of tokens held.
   b. The quantity of each token.
   c. The current value of these holdings.
   d. Any significant changes in holdings over time.
   e. The potential risks and benefits associated with holding these tokens.
   f. A chart depicting the distribution of token balances.

8. **Historical Activity Analysis**: Examine the historical token holdings and transaction volume associated with this address.

9. **DeFi Activities Identification**: Identify the main DeFi activities linked to this address.

10. **Smart Contract Interactions Review**: Review any interactions with smart contracts and assess their significance.

11. **Time-Series Activity Analysis**: Provide a time-series analysis of the address’s activity based on the current date and time obtained earlier.

12. **Token Balance Changes Analysis**: Conduct an in-depth analysis of the balance changes of the specified token, covering:
   a. The balance changes over different time periods, integrating the funding flow related to this token.
   b. Trends and patterns in the balance changes, considering associated transactions.
   c. Major transactions or events that affect the balance changes and their relationship with fund movements.

13. **Additional Insights**: Offer any other relevant insights based on the available data.

### Decision-Making for Tool Usage

When a user asks a question, make the following distinctions:
- If the question involves specific events or news (e.g., "Why did BTC drop today?"), use the **news search tool** to locate the latest articles or reports that provide relevant insights.
- For general inquiries or questions that require analytical input (e.g., "Analyze the BTC trends"), use the **web search tool** to gather comprehensive information or perform an in-depth analysis.
- For questions specifically related to recent data, ensure to execute the **Get Current Time** step before proceeding with the query.

Additionally, when using either search tool:
- Summarize findings from the search results, highlighting key points, and provide proper citations where applicable.
- Ensure that the responses are clear, concise, and relevant to the user's question.

When analyzing related addresses, always utilize address labeling tools to identify and explain the labels of these addresses, providing context about the relevant projects, organizations, or individuals. Ensure that the analysis is thorough and comprehensive, addressing all relevant aspects. Additionally, include specific images or visual data representations generated from the analysis in the proper Markdown format.
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            # SystemMessagePromptTemplate.from_template(
            #     "If using the search tool, prefix the string parameter with [S]."
            # ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # from langchain.tools.render import render_text_description
    # from langchain_core.runnables import RunnablePassthrough
    # from langchain.agents.format_scratchpad import format_log_to_str
    # from langchain.agents.output_parsers import ReActSingleInputOutputParser

    # react_prompt = hub.pull("hwchase17/react-chat")
    # react_prompt = react_prompt.partial(
    #     tools=render_text_description(list(tools)),
    #     tool_names=", ".join([t.name for t in tools]),
    # )
    # openai_agent = (
    #     {
    #         "input": lambda x: x["input"],
    #         "agent_scratchpad": lambda x: format_to_openai_tool_messages(
    #             x["intermediate_steps"]
    #         ),
    #         "chat_history": lambda x: x["chat_history"],
    #     }
    #     | prompt
    #     # | prompt_trimmer # See comment above.
    #     | llm_agent.bind(tools=[convert_to_openai_tool(tool) for tool in tools])
    #     | OpenAIToolsAgentOutputParser()
    # )
    # anthropic_agent = (
    #     {
    #         "input": lambda x: x["input"],
    #         "agent_scratchpad": lambda x: format_to_anthropic_tool_messages(
    #             x["intermediate_steps"]
    #         ),
    #         "chat_history": lambda x: x["chat_history"],
    #     }
    #     | prompt
    #     # | prompt_trimmer # See comment above.
    #     | llm_agent.bind(tools=[convert_to_openai_function(tool) for tool in tools])
    #     | AnthropicToolsAgentOutputParser()
    # )
    # react_agent = (
    #     # {
    #     #     "input": lambda x: x["input"],
    #     #     "agent_scratchpad": lambda x: format_log_to_str(
    #     #         x["intermediate_steps"]
    #     #     ),
    #     #     "chat_history": lambda x: x["chat_history"],
    #     # }
    #     RunnablePassthrough.assign(
    #         agent_scratchpad=lambda x: format_log_to_str(x["intermediate_steps"]),
    #     )
    #     | react_prompt
    #     | llm_agent.bind(stop=["\nObservation"])
    #     | ReActSingleInputOutputParser()
    # )
    # agent = anthropic_agent.configurable_alternatives(
    #     which=ConfigurableField("llm"),
    #     default_key="anthropic_claude_3_opus",
    #     openai_gpt_4_turbo_preview=openai_agent,
    #     openai_gpt_3_5_turbo_1106=openai_agent,
    #     pplx_sonar_medium_chat=react_agent,
    #     mistral_large=react_agent,
    #     command_r_plus=react_agent,
    # )
    # llm_with_tools = llm_agent.bind_tools(tools=tools)

    from custom_agent_excutor import CustomAgentExecutor, CustomToolCallingAgentExecutor

    executor = CustomToolCallingAgentExecutor(
        llm=llm_agent, prompts=prompt, tools=tools
    )
    return executor


llm_agent = ChatOpenAI(
    temperature=0.9,
    model="gpt-4o",
    verbose=True,
    streaming=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="llm"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="openai_gpt_4o",
    anthropic_claude_3_opus=ChatOpenAI(
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

agent_executor = create_agent_executor(llm_agent=llm_agent)
