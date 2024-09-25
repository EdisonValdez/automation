import json
import csv
from serpapi import GoogleSearch
import time

# List of SERPAPI keys
SERPAPI_KEYS = [
    "fbea901a1b57ef902de8c53e4c4e25e5865e61c734376753e7a19626e6aadac8", 
    "8204fd950a0e0e49544db853253aaf93e5977a1ddb1709a68bd7a4de841cda74", 
    "c63b29e92a3a15f1974d4ca626d4f3ad5d752768608c5e2c8d96b03e2b2c7689",
    
    ]  
CURRENT_KEY_INDEX = 0

# Function to get the current API key
def get_current_api_key():
    global CURRENT_KEY_INDEX
    return SERPAPI_KEYS[CURRENT_KEY_INDEX]

# Function to switch to the next API key when limit is reached
def switch_api_key():
    global CURRENT_KEY_INDEX
    CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(SERPAPI_KEYS)
    print(f"Switching to API key: {SERPAPI_KEYS[CURRENT_KEY_INDEX]}")

# Function to check if the API key limit has been reached based on the response
def has_reached_limit(response):
    # Check if the response contains an error indicating the key has reached its limit
    return "error" in response and "quota" in response["error"].get("message", "").lower()

# Function to read queries from q.txt
def read_queries_from_file(file_path):
    with open(file_path, 'r') as file:
        queries = file.readlines()
    return [query.strip() for query in queries if query.strip()]

# Function to search Google Maps using SerpAPI
def search_google_maps(query, latitude=None, longitude=None):
    params = {
        "api_key": get_current_api_key(),
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com",
        "q": query,
        "hl": "en",
        "no_cache": "true"
    }

    if latitude and longitude:
        params["ll"] = f"{latitude},{longitude}"

    search = GoogleSearch(params)
    results = search.get_dict()

    # If the key has reached its limit, switch and retry
    if has_reached_limit(results):
        print("API key limit reached. Switching to the next key.")
        switch_api_key()
        time.sleep(1)  # Delay before retrying to avoid rapid-fire requests
        return search_google_maps(query, latitude, longitude)

    return results

# Function to save results in JSON format
def save_results_to_json(results, query):
    filename = f"results_{query.replace(' ', '_')}.json"
    with open(filename, 'w') as json_file:
        json.dump(results, json_file, indent=4)
    print(f"Results saved to {filename}")

# Function to save results in CSV format
def save_results_to_csv(results, query):
    filename = f"results_{query.replace(' ', '_')}.csv"
    keys = results[0].keys() if results else []
    with open(filename, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"Results saved to {filename}")

# Main function to run the search for each query
def main():
    # Read queries from q.txt
    queries = read_queries_from_file('q.txt')

    if not queries:
        print("No queries found in q.txt")
        return

    for query in queries:
        print(f"Searching for: {query}")
        results = search_google_maps(query)

        search_results = results.get("local_results", [])

        if search_results:
            save_results_to_json(search_results, query)
            save_results_to_csv(search_results, query)
        else:
            print(f"No results found for: {query}")

if __name__ == "__main__":
    main()
