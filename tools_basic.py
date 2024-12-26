from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import re
from langchain.agents import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
)
from tradingview_ta import TA_Handler, Interval, Exchange
from langchain_core.output_parsers import StrOutputParser
from openai_assistant_tools import GoogleSerperAPIWrapper
import openai_assistant_api_docs
import json
from openai_assistant_tools import TradingviewWrapper
from html import unescape
from typing import Any, Dict, List
import asyncio
import os
from langchain.agents import Tool
from langchain.chains.qa_with_sources.retrieval import RetrievalQAWithSourcesChain
from rebyte_langchain.rebyte_langchain import RebyteEndpoint
from pydantic import BaseModel, Field
from langchain.output_parsers import (
    PydanticToolsParser,
    StructuredOutputParser,
    ResponseSchema,
    PydanticOutputParser,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import ConfigurableField
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_cohere import ChatCohere
from pathlib import Path
import sys

from langchain.agents import load_tools
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")

headers = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
}

llm = ChatAnthropic(
    model="claude-3-opus-20240229",
    # max_tokens=,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="model"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_opus",
    anthropic_claude_3_5_sonnet=ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        max_tokens=2000,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        stream_usage=True,
        verbose=True,
    ),
    openai_gpt_3_5_turbo_1106=ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        verbose=True,
        streaming=True,
        temperature=0.9,
    ),
    openai_gpt_4_turbo_preview=ChatOpenAI(
        temperature=0.9,
        model="gpt-4-turbo-2024-04-09",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o",
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
        model="mistral-large-latest", temperature=0.9, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)


@tool
def getTokenMetadata(symbol: str) -> str:
    """
    Useful when you need get the metadata of a token.
    """
    url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/info?symbol={symbol}"
    response = requests.get(url, headers=headers)
    return json.dumps(response.json())


@tool
def getLatestQuote(symbol: str) -> str:
    """
    Useful when you need get the latest quote of a token.
    """
    url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol={symbol}"
    response = requests.get(url, headers=headers)
    return json.dumps(response.json())


@tool
def get_multiple_token_prices(addresses: list[str]):
    """
    Useful when you need get some cryptocurrency's latest price.
    """
    # url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    # parameters = {
    #     'symbol': ','.join(symbols),
    #     'convert': 'USD'
    # }

    # response = requests.get(url, headers=headers, params=parameters)

    # if response.status_code == 200:
    #     data = response.json()
    #     prices = {}
    #     for symbol in symbols:
    #         if symbol in data['data']:
    #             price = data['data'][symbol]['quote']['USD']['price']
    #             prices[symbol] = price
    #         else:
    #             print(f"Symbol {symbol} not found in response.")
    #             prices[symbol] = None
    #     return prices
    # else:
    #     print(f"Error {response.status_code}: {response.json()['status']['error_message']}")
    #     return None
    _addresses = ",".join(addresses)
    url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={_addresses}&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    price_info = []
    for address in addresses:
        price = data.get(address, {}).get("usd")
        if price:
            price_info.append({"contract_address": address, "price": price})
        else:
            print(f"Address: {address}, Price information not available.")
    return data


tradingview = TradingviewWrapper(llm=llm)


class GoogleSearchEngineQuery(BaseModel):
    """Search over Google Search."""

    terms: str = Field(
        ...,
        description="The keywords to search.",
    )

    tbs: str = Field(..., description="")


class GoogleSearchEngineQueryTerms(BaseModel):
    """Search over Google Search."""

    terms: str = Field(
        ...,
        description="The keywords to search.",
    )


class GoogleSearchEngineResult(BaseModel):
    """Search over Google Search."""

    # title: str
    link: str
    # snippet: str
    # imageUrl: str


@tool
def searchNewsToAnswer(question: str) -> str:
    """Useful when you need answer questions use news. Input for this should be a complete question or request.
    After executing this tool, you need to execute `summarizeRelevantContentsNews`.
    """

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQuery)
    prompt_template_0 = """{format_instructions}

Generate news search parameters `terms` and `tbs`  based on the question. 
Search engines only search for news, so do not include words like news in terms.

Use `tbs` to set the time range and do not generate time-related terms.
`tbs` is required.
The `tbs` parameter of the Google Search API is a very useful tool that allows you to refine and filter search results. Its primary use is to filter search results by time range, but it can also be utilized for other purposes. When using the `tbs` parameter, you can specify a time range for the search results (e.g., past 24 hours, past week, etc.), or filter results by specific dates.

### Some common examples of using the `tbs` parameter:

1. **Time Range**:
   - `tbs=qdr:w`: Content from the past week.
   - `tbs=qdr:m`: Content from the past month.
   - `tbs=qdr:y`: Content from the past year.

2. **Specific Dates**:
   - Combine `cd_min` and `cd_max` to specify a specific date range, format as `mm/dd/yyyy`. For example, `tbs=cdr:1,cd_min:01/01/2022,cd_max:12/31/2022` would search for all content within the year 2022.

3. **Custom Time Range**:
   - You can also use specific syntax to define a custom time range. For example, `tbs=qdr:n10` to search for content from the past 10 minutes.

### Points to Note When Using the `tbs` Parameter:

- The `tbs` parameter is flexible but needs to be used correctly to achieve the desired filtering effect.
- Besides time filtering, the `tbs` parameter can be used for other advanced search features, though these are generally less discussed and documented.
- When using the Google Search API, ensure you comply with its terms of use, including but not limited to rate limits, restrictions on commercial usage, etc.

Return Example:
```json
{{
    "terms":"Hello World Keywords",
    "tbs":"qdr:w"
}}
```

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="news", tbs=query.tbs)
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = [
        {
            "title": r["title"],
            "link": r["link"] if "link" in r else "",
            # "snippet": r["snippet"],
            "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
        }
        for r in results
    ]
    re = {"question": question, "search_result": search_result}
    result_str = json.dumps(re)
    return result_str


@tool
def searchWebPageToAnswer(question: str) -> str:
    """Useful when you need answer questions use web page. Input for this should be a complete question or request.
    After executing this tool, you need to execute `summarizeRelevantContents`.
    """

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms` based on the question. 
Extract the keywords required for search from the question.

Return Example:
```json
{{
    "terms":"Hello World Keywords"
}}
```

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="search")
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = [
        {
            "title": r["title"],
            "link": r["link"] if "link" in r else "",
            # "snippet": r["snippet"],
            "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
        }
        for r in results
    ]
    re = {"question": question, "search_result": search_result}
    result_str = json.dumps(re)
    return result_str


@tool
def searchPlacesToAnswer(question: str) -> str:
    """Useful when you need search some places to answer question. Input for this should be a complete question."""

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms`  based on the question. 
`terms` are search terms generated based on question.

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="places")
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = results
    result_str = json.dumps(search_result)
    return result_str


@tool
def searchImagesToAnswer(question: str) -> str:
    """Useful when you need search some images to answer question. Input for this should be a complete question."""

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms` based on the question. 
`terms` are search terms generated based on question.

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="images")
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = results
    result_str = json.dumps(search_result)
    return result_str


from langchain_community.document_loaders import SpiderLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_transformers import Html2TextTransformer
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document

h2tTransformer = Html2TextTransformer()


# @tool
def getDocumentFromLink(
    link: str, chunk_size: int, chunk_overlap: int
) -> List[Document]:
    """get documents from link."""
    loader = SpiderLoader(
        url=link,
        mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
    )
    try:
        html = loader.load()
    except Exception as e:
        print(e)
        clean_html = getHTMLFromURL(link)
        html = [Document(clean_html)]
    html = filter_complex_metadata(html)
    html[0].metadata["source"] = ""
    # docs_text = h2tTransformer.transform_documents(html)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    _split = text_splitter.split_documents(html)
    splits = []
    if len(splits) == 0:
        splits = _split
    else:
        splits = splits + _split
    return splits


@tool
def summarizeRelevantContents(links: List[str], question: str) -> str:
    """
    Get relevant content from returned by `searchWebPageToAnswer`.
    The parameter `links` should be top 10 links returned by `searchWebPageToAnswer`.
    The parameter `question` is required. It should be a complete question which returned from `searchWebPageToAnswer`.
    """
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    # text = "\n".join([remove_html_tags(getHTMLFromURL(link)) for link in links])
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()

    splits = []
    for link in links:
        _s = getDocumentFromLink(link, chunk_size=10000, chunk_overlap=1500)
        if _s is not None and len(splits) == 0:
            splits = _s
        elif _s is not None and len(splits) > 0:
            splits = splits + _s
        else:
            continue

    contents = chain.batch(
        [
            {
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return (
        "The contents of the first three search results are extracted as follows:\n"
        + "\n".join(contents)
    )


@tool
def answerQuestionFromLinks(link: str, question: str) -> str:
    """
    Useful when the question that needs to be answered points to a specific link.
    The parameter `links` should be complete url links.
    The parameter `question` should be a complete question about `links`.
    """
    prompt_template = """Context is the content fragment extracted from the link.  Please organize the context clearly. And answer questions based on the collation results.

The format of the returned result is as follows:

```
Final Fragment: xxxxxx

Answer: xxxxxx
```

Link:{link}

Question: {question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    splits = getDocumentFromLink(link, chunk_size=1000, chunk_overlap=200)
    contents = chain.batch(
        [
            {
                "link": link,
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return "The content snippet obtained from the link is as follows:\n" + (
        "\n" + "#" * 70 + "\n"
    ).join(contents)


@tool
def summarizeRelevantContentsNews(links: List[str], question: str) -> str:
    """
    Get relevant content from returned by `searchNewsToAnswer`.
    The parameter `links` should be top 10 links returned by `searchNewsToAnswer`.
    The parameter `question` is required. It should be a complete question which returned from `searchNewsToAnswer`.
    """
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    # text = "\n".join([remove_html_tags(getHTMLFromURL(link)) for link in links])
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()

    splits = []
    for link in links:
        _s = getDocumentFromLink(link, chunk_size=10000, chunk_overlap=1500)
        if _s is not None and len(splits) == 0:
            splits = _s
        elif _s is not None and len(splits) > 0:
            splits = splits + _s
        else:
            continue

    contents = chain.batch(
        [
            {
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return (
        "The contents of the first three search results are extracted as follows:\n"
        + "\n".join(contents)
    )


def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile("<.*?>")
    text = re.sub(clean, "", text)  # Remove HTML tags
    text = unescape(text)  # Unescape HTML entities
    text = re.sub(r"(?m)^[\t ]+$", "", text)
    text = re.sub(r"\n+", "", text)
    return text


from pyppeteer import launch


async def fetch_page(url):
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    html_content = await page.content()
    await browser.close()
    return html_content


# from langchain_community.tools.arxiv.tool import ArxivQueryRun
from arxiv_wrapper import ArxivAPIWrapper

# arxiv = ArxivQueryRun()


@tool
def arxiv_search(query: str):
    """A wrapper around Arxiv.org
    Useful for when you need to answer questions about Physics, Mathematics,
    Computer Science, Quantitative Biology, Quantitative Finance, Statistics,
    Electrical Engineering, and Economics
    from scientific articles on arxiv.org.
    Input should be a search query."""
    api_wrapper = ArxivAPIWrapper(doc_content_chars_max=10000)
    return api_wrapper.run(query=query)


@tool
def arxiv_load(entry_id: str):
    """Useful for when your need to know the content of some paper on Arxiv.org.
    Input should be the entry_id return from `arxiv_search`."""
    api_wrapper = ArxivAPIWrapper(doc_content_chars_max=10000)
    return api_wrapper.load(query=entry_id)


import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

driver_path = "chromedriver-linux64/chromedriver"
service = Service(executable_path=driver_path)
# 创建ChromeOptions对象
chrome_options = Options()
# 添加无头模式参数
chrome_options.add_argument("--headless")


@tool
def getHTMLFromURL(url: str) -> str:
    """useful when you need get the HTML of URL. The input to this should be URL."""
    # response = requests.get(url)
    # soup = BeautifulSoup(response.text, "html.parser")
    # return soup.prettify()
    # driver_path = "chromedriver-mac-x64/chromedriver"
    # service = Service(executable_path=driver_path)
    # 创建ChromeOptions对象
    # chrome_options = Options()
    # 添加无头模式参数
    # chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(service=service, options=chrome_options)

    # 获取网页内容
    browser.get(url=url)
    html_content = browser.page_source
    soup = BeautifulSoup(html_content, "html.parser")
    # if response.status_code == 200:
    # soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    for tag in body.find_all(
        [
            "link",
            "script",
            "style",
            "button",
            "input",
            "meta",
            "iframe",
            "img",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()
    for tag in body.findAll(True):
        tag.attrs = {
            key: value
            for key, value in tag.attrs.items()
            if key not in ["class", "style"]
        }

    # 可选：清理空白行
    clean_html = re.sub(r"(?m)^[\t ]+$", "", str(body))
    browser.quit()
    return clean_html
    # else:
    #     return f"Failed to retrieve the webpage from {url}. status: {response.status_code}"


@tool
def getContentFromURL(url: str, tag: str, class_: str) -> str:
    """Useful when you need to get the text content of the html tag in the URL page.
    The parameter `url` is the URL link of the page you need to read.
    The parameters `tag` and `class_` represent extracting the text content of `tag` whose classes attribute is equal to `class_`.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    html = soup.find(tag, class_=class_)
    return remove_html_tags(str(html))


@tool
async def getHTMLFromURLs(urls: list[str]) -> str:
    """useful when you need get the HTML of URLs. The input to this should be URL list."""
    req_tasks = []
    for url in urls:
        req_tasks.append(fetch_page(url=url))
    contents = await asyncio.gather(*req_tasks)
    result = ""
    for c in contents:
        soup = BeautifulSoup(c, "html.parser")
        result += "\n" + remove_html_tags(soup.prettify())
    return result


@tool
def moderation(text: str) -> Dict[str, Any]:
    """
    Use OpenAI's Moderation API to check if the input text complies with community standards,
    filtering out inappropriate or harmful content.

    Args:
    text (str): The text to be moderated

    Returns:
    Dict[str, Any]: A dictionary containing the moderation results
    """
    api_key = "YOUR_OPENAI_API_KEY"  # Replace with your actual OpenAI API key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
    }
    data = {"input": text}

    response = requests.post(
        "https://api.openai.com/v1/moderations", headers=headers, data=json.dumps(data)
    )

    if response.status_code != 200:
        raise Exception(f"API request failed with status code: {response.status_code}")

    result = response.json()
    if result["results"][0]["flagged"]:
        return "Text was found that violates Mlion's content policy."
    else:
        return text
    # return {
    #     "flagged": result["results"][0]["flagged"],
    #     "categories": result["results"][0]["categories"],
    #     "category_scores": result["results"][0]["category_scores"]
    # }


@tool
def buy_sell_signal(symbol: str) -> str:
    """Analyzes trading signals for cryptocurrency pairs against USDT using TradingView technical analysis.

    This function provides comprehensive technical analysis including:
    - Overall market summary (buy/sell/neutral signals)
    - Oscillator analysis (RSI, Stochastic, CCI, etc.)
    - Moving averages analysis (EMA, SMA across different periods)
    - Detailed technical indicators

    Input:
    - symbol (str): Cryptocurrency symbol (e.g., 'BTC' for Bitcoin, 'ETH' for Ethereum)

    Output:
    - Returns a detailed analysis string containing:
        * Current market trend analysis
        * Signal strength score (1-10 scale)
        * Trading recommendations based on technical indicators
        * Comprehensive market analysis combining multiple technical factors

    Example usage:
    buy_sell_signal("BTC") - Analyzes BTC/USDT trading pair
    buy_sell_signal("ETH") - Analyzes ETH/USDT trading pair
    """
    btc_usdt = TA_Handler(
        symbol=f"{symbol}USDT",
        screener="crypto",
        exchange="GATEIO",
        interval=Interval.INTERVAL_1_DAY,
    )
    summary = btc_usdt.get_analysis().summary
    oscillators = btc_usdt.get_analysis().oscillators
    moving_averages = btc_usdt.get_analysis().moving_averages
    indicators = btc_usdt.get_analysis().indicators
    # return "\n".join([f"Summary:{summary}",f"Oscillators:{oscillators}",f"Moving Averages:{moving_averages}",f"Indicators:{indicators}"])
    PROMPT_TEMPLATE = """We have an unofficial python API wrapper to retrieve technical analysis from TradingView.
Retrieving the analysis:
- summary: Technical analysis (based on both oscillators and moving averages).
```
# Example
{{'RECOMMENDATION': 'BUY', 'BUY': 12, 'SELL': 7, 'NEUTRAL': 9}}
```
- oscillators: Technical analysis (based on oscillators).
```
# Example
{{'RECOMMENDATION': 'BUY', 'BUY': 2, 'SELL': 1, 'NEUTRAL': 8, 'COMPUTE': {{'RSI': 'NEUTRAL', 'STOCH.K': 'NEUTRAL', 'CCI': 'NEUTRAL', 'ADX': 'NEUTRAL', 'AO': 'NEUTRAL', 'Mom': 'BUY', 'MACD': 'SELL', 'Stoch.RSI': 'NEUTRAL', 'W%R': 'NEUTRAL', 'BBP': 'BUY', 'UO': 'NEUTRAL'}}}}
```
- moving_averages: Technical analysis (based on moving averages).
```
# Example
{{'RECOMMENDATION': 'BUY', 'BUY': 9, 'SELL': 5, 'NEUTRAL': 1, 'COMPUTE': {{'EMA10': 'SELL', 'SMA10': 'SELL', 'EMA20': 'SELL', 'SMA20': 'SELL', 'EMA30': 'BUY', 'SMA30': 'BUY', 'EMA50': 'BUY', 'SMA50': 'BUY', 'EMA100': 'BUY', 'SMA100': 'BUY', 'EMA200': 'BUY', 'SMA200': 'BUY', 'Ichimoku': 'NEUTRAL', 'VWMA': 'SELL', 'HullMA': 'BUY'}}}}
```
- indicators: Technical indicators.
```
# Example
{{'Recommend.Other': 0, 'Recommend.All': 0.26666667, 'Recommend.MA': 0.53333333, 'RSI': 60.28037412, 'RSI[1]': 58.58364778, 'Stoch.K': 73.80404453, 'Stoch.D': 79.64297643, 'Stoch.K[1]': 78.88160227, 'Stoch.D[1]': 85.97647064, 'CCI20': 46.58442886, 'CCI20[1]': 34.57058796, 'ADX': 35.78754863, 'ADX+DI': 23.16948389, 'ADX-DI': 13.82449817, 'ADX+DI[1]': 24.15991909, 'ADX-DI[1]': 13.87125505, 'AO': 6675.72158824, 'AO[1]': 7283.92420588, 'Mom': 1532.6, 'Mom[1]': 108.29, 'MACD.macd': 2444.73734978, 'MACD.signal': 2606.00138275, 'Rec.Stoch.RSI': 0, 'Stoch.RSI.K': 18.53740187, 'Rec.WR': 0, 'W.R': -26.05634845, 'Rec.BBPower': 0, 'BBPower': 295.52055898, 'Rec.UO': 0, 'UO': 55.68311917, 'close': 45326.97, 'EMA5': 45600.06414333, 'SMA5': 45995.592, 'EMA10': 45223.22433151, 'SMA10': 45952.635, 'EMA20': 43451.52018338, 'SMA20': 43609.214, 'EMA30': 41908.5944052, 'SMA30': 40880.391, 'EMA50': 40352.10222373, 'SMA50': 37819.3566, 'EMA100': 40356.09177879, 'SMA100': 38009.7808, 'EMA200': 39466.50411569, 'SMA200': 45551.36135, 'Rec.Ichimoku': 0, 'Ichimoku.BLine': 40772.57, 'Rec.VWMA': 1, 'VWMA': 43471.81729377, 'Rec.HullMA9': -1, 'HullMA9': 45470.37107407, 'Pivot.M.Classic.S3': 11389.27666667, 'Pivot.M.Classic.S2': 24559.27666667, 'Pivot.M.Classic.S1': 33010.55333333, 'Pivot.M.Classic.Middle': 37729.27666667, 'Pivot.M.Classic.R1': 46180.55333333, 'Pivot.M.Classic.R2': 50899.27666667, 'Pivot.M.Classic.R3': 64069.27666667, 'Pivot.M.Fibonacci.S3': 24559.27666667, 'Pivot.M.Fibonacci.S2': 29590.21666667, 'Pivot.M.Fibonacci.S1': 32698.33666667, 'Pivot.M.Fibonacci.Middle': 37729.27666667, 'Pivot.M.Fibonacci.R1': 42760.21666667, 'Pivot.M.Fibonacci.R2': 45868.33666667, 'Pivot.M.Fibonacci.R3': 50899.27666667, 'Pivot.M.Camarilla.S3': 37840.08, 'Pivot.M.Camarilla.S2': 39047.33, 'Pivot.M.Camarilla.S1': 40254.58, 'Pivot.M.Camarilla.Middle': 37729.27666667, 'Pivot.M.Camarilla.R1': 42669.08, 'Pivot.M.Camarilla.R2': 43876.33, 'Pivot.M.Camarilla.R3': 45083.58, 'Pivot.M.Woodie.S3': 21706.84, 'Pivot.M.Woodie.S2': 25492.42, 'Pivot.M.Woodie.S1': 34876.84, 'Pivot.M.Woodie.Middle': 38662.42, 'Pivot.M.Woodie.R1': 48046.84, 'Pivot.M.Woodie.R2': 51832.42, 'Pivot.M.Woodie.R3': 61216.84, 'Pivot.M.Demark.S1': 35369.915, 'Pivot.M.Demark.Middle': 38908.9575, 'Pivot.M.Demark.R1': 48539.915, 'open': 44695.95, 'P.SAR': 48068.64, 'BB.lower': 37961.23510877, 'BB.upper': 49257.19289123, 'AO[2]': 7524.31223529, 'volume': 32744.424503, 'change': 1.44612354, 'low': 44203.28, 'high': 45560}}
```

We got the analysis data of {symbol} from python-tradingview-ta as following:
summary:{summary}
oscillators:{oscillators}
moving_averages:{moving_averages}
indicators:{indicators}
"""
    PROMPT_TEMPLATE = (
        PROMPT_TEMPLATE
        + """\nPlease generate the analysis results by analyzing data the above, and provide the market trend. If the strength of the signal is represented by a score from 1 to 10, where a higher score indicates a stronger signal, please give a score to the strength of the signal in the end.
Your generation:
"""
    )

    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke(
        {
            "symbol": f"{symbol}/usdt",
            "summary": summary,
            "oscillators": "oscillators",
            "moving_averages": moving_averages,
            "indicators": indicators,
        },
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )


from dune_tools import dune_tools
from tools_image import tools as image_tools
from tools_wallet import tools as wallet_tools

# from exa_tools import tools as exa_tools
# import tools_amberdata

tools = (
    # exa_tools
    [
        # moderation,
        searchWebPageToAnswer,
        searchNewsToAnswer,
        searchPlacesToAnswer,
        searchImagesToAnswer,
        summarizeRelevantContents,
        summarizeRelevantContentsNews,
        answerQuestionFromLinks,
        getLatestQuote,
        getTokenMetadata,
        buy_sell_signal,
        arxiv_search,
        arxiv_load,
    ]
    + dune_tools
    # + tools_amberdata.tools
    + image_tools
    + wallet_tools
)
