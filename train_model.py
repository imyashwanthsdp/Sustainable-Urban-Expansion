import os
import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, Point
from geopy.distance import geodesic
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

# ----------------------------------------
# ⚙ Parameters — change if needed
# ----------------------------------------

CITY_CENTER = (13.0827, 80.2707)  # e.g., Chennai
GRID_SIZE_KM = 1  # grid cell size in kilometers
NUM_ROWS = 10  # number of grid rows
NUM_COLS = 10  # number of grid columns

# ----------------------------------------
# 🛠 Helper Functions
# ----------------------------------------

def make_grid(center, grid_size_km, rows, cols):
    """Create a simple grid of rectangles around a central lat/lng."""
    lat, lng = center
    grid_cells = []
    step = grid_size_km / 110.0  # rough degree per km

    for i in range(rows):
        for j in range(cols):
            south = lat - (rows/2 - i) * step
            north = south + step
            west = lng - (cols/2 - j) * step
            east = west + step
            grid_cells.append((north, south, east, west))

    return grid_cells

def extract_osm_features(polygon):

    # area in km2
    gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon])
    area_km2 = gdf.to_crs(epsg=3857).area.iloc[0] / 10**6

    # road density
    try:
        G = ox.graph_from_polygon(polygon, network_type='drive')
        edges = ox.graph_to_gdfs(G, nodes=False)
        total_road_length = edges.length.sum() / 1000
        road_density = total_road_length / area_km2 if area_km2 > 0 else 0
    except Exception:
        road_density = 0

    # building count proxy
    try:
        build = ox.features_from_polygon(polygon, tags={"building": True})
        building_count = len(build)
        pop_density = building_count / area_km2 if area_km2 > 0 else 0
    except:
        pop_density = 0

    # green parks
    try:
        parks = ox.features_from_polygon(polygon, tags={"leisure": "park"})
        green_cover = len(parks)
    except:
        green_cover = 0

    # distance to water
    try:
        water = ox.features_from_polygon(polygon, tags={"natural": "water"})
        if len(water) > 0:
            center = polygon.centroid
            dists = [
                geodesic((center.y, center.x), (row.geometry.centroid.y, row.geometry.centroid.x)).km
                for _, row in water.iterrows()
            ]
            distance_water = min(dists)
        else:
            distance_water = 5
    except:
        distance_water = 5

    # elevation approximation
    elevation = 30 + (polygon.bounds[3] - polygon.bounds[1]) * 1000
    flood_risk = max(0, min(1, 1 - elevation/100))

    return {
        "pop_density": pop_density,
        "road_density": road_density,
        "green_cover": green_cover,
        "distance_water": distance_water,
        "elevation": elevation,
        "flood_risk": flood_risk,
        "area_km2": area_km2
    }

def label_zone(row):
    """Rule‑based labeling for training."""
    score = (
        row["road_density"] * 2 +
        row["green_cover"] * 1.5 -
        row["flood_risk"] * 3 -
        row["distance_water"] * 0.5
    )
    if score > 7:
        return 2  # highly sustainable
    elif score > 3:
        return 1  # moderately
    else:
        return 0  # not suitable

# ----------------------------------------
# 🟦 Generate Training Data
# ----------------------------------------

print("Generating grid …")
grid = make_grid(CITY_CENTER, GRID_SIZE_KM, NUM_ROWS, NUM_COLS)

dataset = []

for idx, (north, south, east, west) in enumerate(grid):
    print(f"Processing cell {idx+1}/{len(grid)} …")
    poly = Polygon([(west, south), (west, north), (east, north), (east, south)])
    feats = extract_osm_features(poly)
    feats["north"], feats["south"], feats["east"], feats["west"] = north, south, east, west
    dataset.append(feats)

df = pd.DataFrame(dataset)
df["label"] = df.apply(label_zone, axis=1)

print("Dataset created with shape:", df.shape)
df.to_csv("data/urban_dataset_real.csv", index=False)

# ----------------------------------------
# 🧠 Train Random Forest
# ----------------------------------------

features = [
    "pop_density", "road_density", "green_cover",
    "distance_water", "elevation", "flood_risk"
]

X = df[features]
y = df["label"]

print("Training model …")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

clf = RandomForestClassifier(n_estimators=150, random_state=42)
clf.fit(X_train, y_train)

pred = clf.predict(X_test)
acc = accuracy_score(y_test, pred)

print("Test Accuracy:", acc)

# ----------------------------------------
# 💾 Save Model
# ----------------------------------------

if not os.path.exists("models"):
    os.makedirs("models")

joblib.dump(clf, "models/random_forest_model.pkl")
print("Model saved: models/random_forest_model.pkl")