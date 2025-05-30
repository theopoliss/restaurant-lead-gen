import csv
import yaml
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
# from doordash_scraper import scrape_doordash # Old scraper
from google_maps_scraper import scrape_google_maps # New scraper
import time

# Constants
METERS_IN_MILE = 1609.34

def geocode_address(address):
    """Geocode an address to latitude and longitude."""
    # It's good practice to have a unique user_agent for Nominatim
    geolocator = Nominatim(user_agent=f"lead_gen_tool_{time.time()}") 
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        print(f"Error during geocoding {address}: {e}")
    return None, None


def calculate_distance(coord1, coord2):
    """Calculate distance in miles between two coordinates."""
    if coord1 and coord2 and None not in coord1 and None not in coord2:
        try:
            pt1 = (float(coord1[0]), float(coord1[1]))
            pt2 = (float(coord2[0]), float(coord2[1]))
            return geodesic(pt1, pt2).miles
        except (ValueError, TypeError) as e:
            print(f"Invalid coordinates for distance calculation: {coord1}, {coord2}. Error: {e}")
            return float('inf')
    return float('inf')


def filter_restaurants(restaurants, base_coord, config):
    """Filter restaurants based on distance and ratings."""
    filtered_leads = []
    search_radius_miles = config["search_radius_miles"]
    # Use the renamed config key for minimum ratings
    min_ratings = config["min_ratings_source"] 

    for restaurant in restaurants:
        r_address = restaurant["Address"]
        # For Google Places API, 'vicinity' might not be precise enough for re-geocoding.
        # However, the distance calculation ideally should use the lat/lon provided by Google directly if available.
        # For now, we are re-geocoding the address. If Google provides precise lat/lon for each place, 
        # we could use that directly instead of re-geocoding its 'vicinity' address.
        # Let's assume for now the address is geocodable for distance calc, or use Google's provided lat/lon if available.
        
        # Modification: If restaurant dict contains lat/lon from Google, use that directly.
        # This depends on what scrape_google_maps returns. For now, assume it doesn't add lat/lon directly to the dict.
        r_lat, r_lon = geocode_address(r_address)
        
        time.sleep(1) # Respect Nominatim rate limits for re-geocoding

        if r_lat is None or r_lon is None:
            print(f"Could not geocode restaurant address: {r_address} for distance calculation. Skipping.")
            continue

        distance = calculate_distance(base_coord, (r_lat, r_lon))
        
        try:
            # Handle cases where rating or num_ratings might be 'N/A' or not convertible to number
            current_num_ratings = restaurant["Number of Ratings"]
            if isinstance(current_num_ratings, str) and current_num_ratings.lower() == 'n/a':
                num_ratings = 0 # Treat N/A as 0 for comparison
            else:
                num_ratings = int(current_num_ratings)
        except ValueError:
            print(f"Warning: Could not parse number of ratings for {restaurant['Restaurant Name']} ('{restaurant['Number of Ratings']}'). Skipping.")
            continue

        print(f"Processing: {restaurant['Restaurant Name']} - Distance: {distance:.2f} miles, Ratings: {num_ratings}")

        if distance <= search_radius_miles and num_ratings >= min_ratings:
            # Prepare lead data, ensuring all keys are present as expected by CSV writer
            lead_data = {
                "Restaurant Name": restaurant["Restaurant Name"],
                "Address": r_address,
                "Approximate Rating": restaurant.get("Approximate Rating", "N/A"),
                "Number of Ratings": num_ratings,
                "Source URL": restaurant.get("Google Maps URL", "N/A") # Generic URL field
            }
            filtered_leads.append(lead_data)
            print(f"ADDED: {restaurant['Restaurant Name']}")
        else:
            if distance > search_radius_miles:
                print(f"SKIPPED (distance): {restaurant['Restaurant Name']} - {distance:.2f} miles > {search_radius_miles} miles")
            if num_ratings < min_ratings:
                 print(f"SKIPPED (ratings): {restaurant['Restaurant Name']} - {num_ratings} < {min_ratings} ratings")

    return filtered_leads


def save_to_csv(leads, filename="leads.csv"):
    """Save leads to a CSV file."""
    if not leads:
        print("No leads to save.")
        return

    # Ensure all dicts have the same keys for DictWriter, define them explicitly
    field_names = ["Restaurant Name", "Address", "Approximate Rating", "Number of Ratings", "Source URL"]
    
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=field_names)
        dict_writer.writeheader()
        for lead in leads:
            # Ensure each lead dictionary conforms to field_names, providing defaults if necessary
            row_to_write = {key: lead.get(key, "N/A") for key in field_names}
            dict_writer.writerow(row_to_write)
            
    print(f"Successfully saved {len(leads)} leads to {filename}")


def main():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    base_address = config["base_address"]
    google_api_key = config.get("google_maps_api_key")

    if not google_api_key or google_api_key == "YOUR_GOOGLE_MAPS_API_KEY_HERE":
        print("Critical: Google Maps API key is missing or not set in config.yaml. Please add it to proceed. Exiting.")
        return

    print(f"Geocoding base address: {base_address}...")
    base_lat, base_lon = geocode_address(base_address)

    if not base_lat or not base_lon:
        print(f"Critical: Could not geocode base address: {base_address}. Exiting.")
        return

    print(f"Base address geocoded: ({base_lat}, {base_lon})")

    search_radius_miles = config["search_radius_miles"]
    search_radius_meters = search_radius_miles * METERS_IN_MILE

    keywords = config.get("search_keywords", [])
    all_scraped_restaurants = []
    processed_place_ids = set() # To keep track of unique restaurants by place_id

    if not keywords: # Default to a single search with no specific keyword if none are provided
        print(f"No specific keywords provided. Scraping Google Maps for all restaurants near base address (Radius: {search_radius_miles} miles)...")
        scraped_restaurants = scrape_google_maps(google_api_key, base_lat, base_lon, int(search_radius_meters))
        all_scraped_restaurants.extend(scraped_restaurants)
    else:
        print(f"Processing {len(keywords)} keywords: {keywords}")
        for keyword in keywords:
            print(f"\nScraping Google Maps for '{keyword}' restaurants near base address (Radius: {search_radius_miles} miles / {search_radius_meters:.0f} meters)...")
            restaurants_for_keyword = scrape_google_maps(google_api_key, base_lat, base_lon, int(search_radius_meters), keyword=keyword)
            
            new_restaurants_found_for_keyword = 0
            for r in restaurants_for_keyword:
                # Extract place_id from the Google Maps URL for de-duplication
                # Assumes URL format: https://www.google.com/maps/search/?api=1&query=Google&query_place_id=PLACE_ID
                try:
                    place_id = r["Google Maps URL"].split("query_place_id=")[-1]
                    if place_id == "N/A" or not place_id: # Handle cases where place_id might be missing or N/A
                        print(f"Warning: Could not extract valid place_id for {r.get('Restaurant Name', 'Unknown Restaurant')}. URL: {r.get('Google Maps URL')}. Skipping for de-duplication.")
                        # Optionally, still add if you want to risk duplicates for places without valid IDs, or skip
                        all_scraped_restaurants.append(r) # Adding it anyway, might lead to duplicates if IDs are bad for some
                        continue 
                except (AttributeError, IndexError, KeyError):
                    print(f"Warning: Could not parse place_id from URL for {r.get('Restaurant Name', 'Unknown Restaurant')}. URL: {r.get('Google Maps URL')}. Skipping for de-duplication.")
                    all_scraped_restaurants.append(r)
                    continue

                if place_id not in processed_place_ids:
                    all_scraped_restaurants.append(r)
                    processed_place_ids.add(place_id)
                    new_restaurants_found_for_keyword += 1
            print(f"Found {len(restaurants_for_keyword)} restaurants for keyword '{keyword}'. Added {new_restaurants_found_for_keyword} new unique restaurants.")
            time.sleep(1) # Small delay between API calls for different keywords

    if not all_scraped_restaurants:
        print("No restaurants scraped from Google Maps across all keywords. Exiting.")
        return
    
    print(f"Scraped {len(all_scraped_restaurants)} unique potential restaurants from Google Maps. Now filtering...")

    filtered_leads = filter_restaurants(all_scraped_restaurants, (base_lat, base_lon), config)

    if filtered_leads:
        save_to_csv(filtered_leads, "google_maps_leads.csv") # Updated filename
    else:
        print("No restaurants matched the filtering criteria.")

    print("Lead generation process completed.")

if __name__ == "__main__":
    main() 