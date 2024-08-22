from exa_py import Exa
from langchain.agents import tool
from dotenv import load_dotenv
import os

load_dotenv(".env")

exa = Exa(api_key=os.getenv("EXA_API_KEY"))


@tool
def search(query: str, include_domains=None, start_published_date=None):
    """Search for a webpage based on the query.
    Set the optional include_domains (list[str]) parameter to restrict the search to a list of domains.
    Set the optional start_published_date (str) parameter to restrict the search to documents published after the date (YYYY-MM-DD).
    """
    search_results = exa.search_and_contents(
        f"{query}",
        use_autoprompt=True,
        num_results=10,
        include_domains=include_domains,
        start_published_date=start_published_date,
    )
    results = []
    for r in search_results.results:
        results.append(
            {
                "title":r.title,
                "url":r.url,
                "text":r,
            }
        )
    return results 


@tool
def find_similar(url: str):
    """Search for webpages similar to a given URL.
    The url passed in should be a URL returned from `search`.
    """
    return exa.find_similar_and_contents(url, num_results=5)


@tool
def get_contents(ids: list[str]):
    """Get the contents of a webpage.
    The ids passed in should be a list of ids returned from `search`.
    """
    return exa.get_contents(ids)


tools = [search, get_contents, find_similar]
