#automation/serpapi_integration.py
from serpapi import GoogleSearch
from django.conf import settings


def fetch_google_events(query, location=None, date_filter=None, event_type=None):
    """
    Fetches events using SerpApi's Google Events API.
    
    Parameters:
        query (str): Main search query, e.g., "Events in Austin".
        location (str): Location to filter events, e.g., "Austin, TX".
        date_filter (str): Date filter for events, e.g., "today", "week", "month".
        event_type (str): Type of events, e.g., "Virtual-Event".
    
    Returns:
        List[Dict]: A list of events with relevant details.
    """
 
    params = {
        "engine": "google_events",
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "hl": "en",   
        "gl": "us",   
        "no_cache": True
    }
 
    if location:
        params["location"] = location
    if date_filter:
        params["htichips"] = f"date:{date_filter}"
    if event_type:
        params["htichips"] = f"{params.get('htichips', '')},event_type:{event_type}".strip(',')
 
    search = GoogleSearch(params)
    results = search.get_dict()
 
    events = results.get("events_results", [])
 
    for event in events:
        print(event)   
        
    return events
