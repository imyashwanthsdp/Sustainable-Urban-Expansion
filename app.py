from flask import Flask, render_template, request, jsonify
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon
from geopy.distance import geodesic
import joblib
import numpy as np

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'aqua_guard_session_1'


try:
    model = joblib.load("models/random_forest_model.pkl")
    print("Model is working on the area")
except:
    print("⚠️ Warning: Model not found. Predictions will fail.")
    model = None


def safe_features(polygon, tags):
    try:
        gdf = ox.features_from_polygon(polygon, tags=tags)
        if gdf is None or gdf.empty:
            return 0
        return len(gdf)
    except Exception as e:
        
        return 0


def extract_osm_features(polygon):
    
    gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon])
    area_km2 = gdf.to_crs(epsg=3857).area.iloc[0] / 10**6

    
    try:
        G = ox.graph_from_polygon(polygon, network_type='all_public')
        if G:
            edges = ox.graph_to_gdfs(G, nodes=False)
            road_length = edges.length.sum() / 1000
            road_density = road_length / area_km2 if area_km2 > 0 else 0
        else:
            road_density = 0
    except:
        road_density = 0

    
    building_count = safe_features(polygon, {"building": True})
    pop_density = building_count / area_km2 if area_km2 > 0 else 0

    
    green_cover = safe_features(polygon, {"leisure": "park", "landuse": "forest"}) * 5

    
    min_distance = 5
    try:
        water_gdf = ox.features_from_polygon(polygon, tags={"natural": "water"})
        if water_gdf is not None and not water_gdf.empty:
            center = polygon.centroid
            
            for _, row in water_gdf.iterrows():
                water_center = row.geometry.centroid
                dist = geodesic((center.y, center.x), (water_center.y, water_center.x)).km
                if dist < min_distance:
                    min_distance = dist
    except:
        min_distance = 5

   
    elevation = 30 + (polygon.bounds[3] - polygon.bounds[1]) * 1000 
    flood_risk = max(0, min(1, 1 - elevation / 100))

    return {
        "pop_density": pop_density,
        "road_density": road_density,
        "green_cover": green_cover,
        "distance_water": min_distance,
        "elevation": elevation,
        "flood_risk": flood_risk,
        "area_km2": area_km2
    }


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predict_zone", methods=["POST"])
def predict_zone():
    try:
        data = request.get_json()
        north, south, east, west = data["north"], data["south"], data["east"], data["west"]

        polygon = Polygon([(west, south), (west, north), (east, north), (east, south)])

        
        feats = extract_osm_features(polygon)

        
        features_array = np.array([[
            feats["pop_density"],
            feats["road_density"],
            feats["green_cover"],
            feats["distance_water"],
            feats["elevation"],
            feats["flood_risk"]
        ]])

        
        if model:
            prediction = model.predict(features_array)[0]
            try:
                
                probs = model.predict_proba(features_array)[0]
                confidence = float(np.max(probs)) * 100
            except:
                confidence = 0
        else:
            prediction = 0 
            confidence = 0

        
        if prediction == 2:
            decision = "✅Sustainable"
        elif prediction == 1:
            decision = "⚠️ Moderately Sustainable"
        else:
            decision = "❌ Not Sustainable"

       
        
        norm_green = min(feats["green_cover"], 100) 
        norm_infra = min(feats["road_density"] * 5, 100) 
        norm_pop = min(feats["pop_density"] * 2, 100)
        norm_flood = (1 - feats["flood_risk"]) * 100 

        
        calculated_score = (
            (norm_green * 0.35) + 
            (norm_infra * 0.25) + 
            (norm_pop * 0.20) + 
            (norm_flood * 0.20)
        )
        calculated_score = round(min(max(calculated_score, 0), 100), 1)

        return jsonify({
            "score": calculated_score,          
            "prediction_class": int(prediction),
            "decision": decision,
            "confidence": round(confidence, 1),
            "area_km2": round(feats["area_km2"], 2),
            "road_density": round(feats["road_density"], 2),
            "pop_density": round(feats["pop_density"], 2),
            "distance_water": round(feats["distance_water"], 2),
            "green_cover": round(feats["green_cover"], 2),
            "elevation": round(feats["elevation"], 2),
            "flood_risk": round(feats["flood_risk"], 2)
        })

    except Exception as e:
        print("ERROR:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)
