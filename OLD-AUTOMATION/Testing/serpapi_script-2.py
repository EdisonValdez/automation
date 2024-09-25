
from serpapi import GoogleSearch
import json
import csv
import os
SERPAPI_KEY = "68ea65477e6d1364cb779432e97386315b6b6de331a2fcdb00580d2e5f00201e"

# Function to read queries from q.txt
def read_queries_from_file(file_path):
    with open(file_path, 'r') as file:
        queries = file.readlines()
    # Remove any empty lines or spaces
    return [query.strip() for query in queries if query.strip()]

# Function to search Google Maps using SerpAPI
def search_google_maps(query, latitude, longitude):
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com",
        "q": query,
        "hl": "en",
        "no_cache": "true"
    }
    search = GoogleSearch(params)
    return search.get_dict()

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
    # Set the default coordinates
    latitude = "40.7455096"
    longitude = "-74.0083012"

    # Read queries from q.txt
    queries = read_queries_from_file('q.txt')

    if not queries:
        print("No queries found in q.txt")
        return

    for query in queries:
        print(f"Searching for: {query}")
        results = search_google_maps(query, latitude, longitude)

        # Extract the search results from the SerpAPI response
        search_results = results.get("local_results", [])
        
        # Save the results in JSON and CSV format
        if search_results:
            save_results_to_json(search_results, query)
            save_results_to_csv(search_results, query)
        else:
            print(f"No results found for: {query}")

if __name__ == "__main__":
    main()
