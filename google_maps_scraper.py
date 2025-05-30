import requests
import time

BASE_GOOGLE_MAPS_URL = "https://maps.googleapis.com/maps/api/place"
PAGE_LOAD_DELAY_SECONDS = 2 # Delay before fetching the next page as per Google's recommendation
MAX_PAGES_TO_FETCH = 10 # Changed from 3 to 10 as per user request

def _parse_place_data(place):
    """Helper function to parse data for a single place."""
    name = place.get("name")
    address = place.get("vicinity")
    rating = place.get("rating", "N/A")
    num_ratings = place.get("user_ratings_total", "N/A")
    place_id = place.get("place_id")
    google_maps_url = f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={place_id}" if place_id else "N/A"

    if name and address and place_id:
        return {
            "Restaurant Name": name,
            "Address": address,
            "Approximate Rating": rating,
            "Number of Ratings": num_ratings,
            "Google Maps URL": google_maps_url
        }
    else:
        print(f"Skipping place due to missing essential data: Name: {name}, Address: {address}, Place ID: {place_id}")
        return None

def scrape_google_maps(api_key, lat, lon, radius_meters, keyword=None):
    """
    Scrapes Google Maps Places API for restaurants near the given latitude and longitude,
    handling pagination to fetch more results. Can be filtered by an optional keyword.

    Args:
        api_key: Your Google Maps API key.
        lat: Latitude.
        lon: Longitude.
        radius_meters: Search radius in meters.
        keyword (str, optional): A specific keyword to refine the search (e.g., "pizza"). Defaults to None.

    Returns:
        A list of dictionaries, where each dictionary contains information
        about a restaurant.
    """
    nearby_search_url = f"{BASE_GOOGLE_MAPS_URL}/nearbysearch/json"
    restaurants_data = []
    pages_fetched = 0
    
    params = {
        "key": api_key,
        "location": f"{lat},{lon}",
        "radius": radius_meters,
        "type": "restaurant",
    }

    if keyword:
        params["keyword"] = keyword
        print(f"Querying Google Maps API: {nearby_search_url} with params: location={params['location']}, radius={params['radius']}, type={params['type']}, keyword={keyword}")
    else:
        print(f"Querying Google Maps API: {nearby_search_url} with params: location={params['location']}, radius={params['radius']}, type={params['type']}")

    while pages_fetched < MAX_PAGES_TO_FETCH: # Loop for pagination
        pages_fetched += 1
        print(f"Fetching page {pages_fetched}...")
        
        try:
            response = requests.get(nearby_search_url, params=params, timeout=20)
            response.raise_for_status()
            results_data = response.json()

            if results_data.get("status") == "OK":
                for place in results_data.get("results", []):
                    parsed_restaurant = _parse_place_data(place)
                    if parsed_restaurant:
                        restaurants_data.append(parsed_restaurant)
                
                next_page_token = results_data.get("next_page_token")
                if next_page_token and pages_fetched < MAX_PAGES_TO_FETCH:
                    print(f"Next page token found. Waiting {PAGE_LOAD_DELAY_SECONDS}s before fetching next page...")
                    time.sleep(PAGE_LOAD_DELAY_SECONDS) # Wait before using the token
                    params["pagetoken"] = next_page_token # Add token for the next request
                else:
                    if next_page_token: # Token exists but we hit MAX_PAGES_TO_FETCH
                        print(f"Reached max pages to fetch ({MAX_PAGES_TO_FETCH}). More results might be available from API with token: {next_page_token[:20]}...")
                    else:
                        print("No more pages available.")
                    break # Exit pagination loop if no token or max pages reached
            
            elif results_data.get("status") == "ZERO_RESULTS":
                if pages_fetched == 1: # Only print if it's the first page that has zero results
                    print("Google Maps API returned ZERO_RESULTS for the initial query.")
                else:
                    print("Google Maps API returned ZERO_RESULTS for a subsequent page.")
                break # No results, no need to paginate further
            
            else: # Handle other statuses like REQUEST_DENIED, OVER_QUERY_LIMIT etc.
                print(f"Error from Google Maps API on page {pages_fetched}: {results_data.get('status')} - {results_data.get('error_message', '')}")
                if results_data.get("status") == "REQUEST_DENIED":
                    print("REQUEST_DENIED: This often means an issue with the API key. Check your Google Cloud Console.")
                elif results_data.get("status") == "INVALID_REQUEST" and "pagetoken" in params:
                     print("INVALID_REQUEST with pagetoken. The token might have expired or is invalid.")
                break # Stop on error

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Google Maps API on page {pages_fetched}: {e}")
            break # Stop on connection error
        except Exception as e:
            print(f"An unexpected error occurred during Google Maps scraping on page {pages_fetched}: {e}")
            break # Stop on unexpected error
        
        # Clear pagetoken from params if it was the last page or an error occurred, for safety on any potential retry (though current loop breaks)
        if "pagetoken" in params and (not next_page_token or pages_fetched >= MAX_PAGES_TO_FETCH):
            del params["pagetoken"]

    return restaurants_data

if __name__ == '__main__':
    # Example Usage (Requires a valid API Key)
    # Replace with your actual API key and desired coordinates/radius for testing
    # Ensure your API key is stored securely and not hardcoded in production versions.
    import os
    API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY") # Try to get from env var for testing
    if not API_KEY:
        print("Please set the GOOGLE_MAPS_API_KEY environment variable or provide it directly for testing.")
    else:
        test_lat = 37.3861
        test_lon = -122.0839
        test_radius_meters = 3 * 1609.34 # 3 miles for quicker keyword test
        test_keywords = ["sushi", "bakery"]

        all_scraped_restaurants = []
        processed_place_ids = set()

        for kw in test_keywords:
            print(f"\nScraping Google Maps for '{kw}' restaurants near ({test_lat}, {test_lon}) within {test_radius_meters:.0f}m...")
            # Pass keyword to the scraper
            scraped_restaurants_for_keyword = scrape_google_maps(API_KEY, test_lat, test_lon, int(test_radius_meters), keyword=kw)
            
            for r in scraped_restaurants_for_keyword:
                place_id = r["Google Maps URL"].split("query_place_id=")[-1] # Extract place_id from URL for uniqueness
                if place_id not in processed_place_ids:
                    all_scraped_restaurants.append(r)
                    processed_place_ids.add(place_id)
            print(f"Found {len(scraped_restaurants_for_keyword)} for '{kw}'. Total unique so far: {len(all_scraped_restaurants)}")
            time.sleep(1) # Small delay between different keyword searches

        if all_scraped_restaurants:
            print(f"\nFound a total of {len(all_scraped_restaurants)} unique restaurants after keyword searches and pagination:")
            for i, restaurant in enumerate(all_scraped_restaurants[:10]): # Print first 10 or fewer
                print(f"--- Restaurant {i+1} ---")
                print(f"  Name: {restaurant['Restaurant Name']}")
                print(f"  Address: {restaurant['Address']}")
                print(f"  Rating: {restaurant['Approximate Rating']}")
                print(f"  Num Ratings: {restaurant['Number of Ratings']}")
                print(f"  URL: {restaurant['Google Maps URL']}")
            if len(all_scraped_restaurants) > 10:
                print(f"... and {len(all_scraped_restaurants) - 10} more.")
        else:
            print("No restaurants found or an error occurred during Google Maps scraping.") 