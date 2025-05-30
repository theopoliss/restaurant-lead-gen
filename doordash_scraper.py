import requests
from bs4 import BeautifulSoup
import json
import re

# Note: This is a simplified scraper and might need adjustments if DoorDash changes its site structure.
# It also doesn't handle pagination or dynamic content loading beyond the initial store feed.

def scrape_doordash(lat, lon):
    """
    Scrapes DoorDash for restaurants near the given latitude and longitude.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        A list of dictionaries, where each dictionary contains information
        about a restaurant.
    """
    # This URL is a general one for fetching stores, it might need adjustments
    # or a different approach if it doesn't work reliably.
    # It's based on observing network requests, DoorDash might change this.
    url = f"https://www.doordash.com/store/feed/?latitude={lat}&longitude={lon}&offset=0&limit=50" # Fetching 50 stores as a starting point
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.doordash.com/",
        "Origin": "https://www.doordash.com",
        "DNT": "1", # Do Not Track
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "TE": "trailers"
        # "Content-Type": "application/json" # Already there, but ensure it is if you modify heavily
    }

    restaurants_data = []

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        data = response.json()
        
        stores = data.get("stores", [])
        if not stores: # Fallback or alternative if the above structure for 'stores' is not found
            stores = data.get("storeFeed", {}).get("stores", [])


        for store in stores:
            try:
                name = store.get("business", {}).get("name")
                address_info = store.get("address", {})
                address_street = address_info.get("street")
                address_city = address_info.get("city")
                address_state = address_info.get("state")
                address_zip = address_info.get("zipCode")
                
                full_address = f"{address_street}, {address_city}, {address_state} {address_zip}"
                
                rating = store.get("averageRating") 
                num_ratings = store.get("numRatings")
                
                # Construct DoorDash URL - this is a guess based on common patterns
                # The actual URL structure might be different or require a slug.
                # For a more robust solution, one might need to extract this from a different part of the page
                # or make another request if the store ID is available.
                # Using a simplified approach based on name and address for now if no direct URL.
                # The store.get("url") or similar might be available in some API responses.
                # Let's assume we have a store_id for a more direct URL.
                store_id = store.get("id")
                doordash_url = f"https://www.doordash.com/store/{store_id}/" if store_id else "N/A"
                
                # If store_id isn't directly available, a more complex URL construction or extraction is needed.
                # For now, if no store_id, URL will be "N/A".

                if name and full_address and num_ratings is not None: # Rating can be 0 or None initially
                    restaurants_data.append({
                        "Restaurant Name": name,
                        "Address": full_address,
                        "Approximate Rating": rating if rating is not None else "N/A",
                        "Number of Ratings": num_ratings,
                        "DoorDash URL": doordash_url
                    })
            except Exception as e:
                print(f"Error processing one store: {e}")
                continue # Skip to the next store if there's an error

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from DoorDash: {e}")
    except json.JSONDecodeError:
        print("Error decoding JSON response from DoorDash. The page structure might have changed.")
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")

    return restaurants_data

if __name__ == '__main__':
    # Example usage (replace with actual lat/lon for testing)
    # For Mountain View, CA (approximate)
    test_lat = 37.3861
    test_lon = -122.0839
    print(f"Scraping DoorDash for restaurants near ({test_lat}, {test_lon})...")
    scraped_restaurants = scrape_doordash(test_lat, test_lon)
    
    if scraped_restaurants:
        print(f"Found {len(scraped_restaurants)} restaurants:")
        for i, restaurant in enumerate(scraped_restaurants[:5]): # Print first 5
            print(f"--- Restaurant {i+1} ---")
            print(f"  Name: {restaurant['Restaurant Name']}")
            print(f"  Address: {restaurant['Address']}")
            print(f"  Rating: {restaurant['Approximate Rating']}")
            print(f"  Num Ratings: {restaurant['Number of Ratings']}")
            print(f"  URL: {restaurant['DoorDash URL']}")
    else:
        print("No restaurants found or an error occurred.") 