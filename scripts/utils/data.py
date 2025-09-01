import json

def get_location_ids():
  with open("data/locations.json", "r") as f:
    locations = json.load(f)
  return [location["id"] for location in locations if "id" in location]