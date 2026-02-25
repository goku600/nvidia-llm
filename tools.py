"""
tools.py
External utilities for the AI (e.g. Web Search).
"""
import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def search_web(query: str, max_results: int = 5) -> str:
    """
    Search DuckDuckGo for the given query and return a formatted string of results.
    """
    try:
        results = ""
        with DDGS() as ddgs:
            # text() returns an iterable of dictionaries: {'title':..., 'href':..., 'body':...}
            for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                results += f"[{i+1}] {r.get('title', 'No Title')}\n"
                results += f"Source: {r.get('href', 'No URL')}\n"
                results += f"Snippet: {r.get('body', 'No Description')}\n\n"
        
        if not results:
            return "No search results found."
        
        return results.strip()
    
    except Exception as e:
        logger.error(f"Web search error for '{query}': {e}")
        return f"Error performing web search: {e}"
