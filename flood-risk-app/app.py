from flask import Flask, render_template, request, jsonify
from shapely.geometry import shape, Point
import numpy as np
import requests
import random

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'aqua_guard_session_2'



def get_rainfall_data(lat, lon):
    """Fetches annual and peak monthly rainfall for better variance analysis."""
    url = f"https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=PRECTOTCORR&community=RE&longitude={lon}&latitude={lat}&format=JSON"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        params = data["properties"]["parameter"]["PRECTOTCORR"]
        
        annual = float(params["ANN"])
        
        monthly_values = [params[m] for m in ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]]
        peak_month = max([float(x) for x in monthly_values])
        
        return annual, peak_month
    except Exception as e:
        print(f"Rainfall API Error: {e}")
        return 800, 100 

def get_elevations(points):
    """Batch fetch elevations to minimize API overhead."""
    locations = [{"latitude": p.y, "longitude": p.x} for p in points]
    url = "https://api.open-elevation.com/api/v1/lookup"
    try:
        response = requests.post(url, json={"locations": locations}, timeout=15)
        results = response.json()["results"]
        return [r["elevation"] for r in results]
    except Exception as e:
        print(f"Elevation API Error: {e}")
        return [50.0] * len(points)



def sample_points_in_polygon(polygon, num_points=15):
    minx, miny, maxx, maxy = polygon.bounds
    points = []
    attempts = 0
    while len(points) < num_points and attempts < 100:
        p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(p):
            points.append(p)
        attempts += 1
    return points

def calculate_advanced_risk(elevations, annual_rain, peak_rain):
    
    avg_elev = np.mean(elevations)
    elev_score = 100 * (1 / (1 + np.exp(0.1 * (avg_elev - 15)))) 
    
   
    std_elev = np.std(elevations)
    slope_factor = 1.0 if std_elev < 2 else 0.6 
    
    
    rain_score = (annual_rain / 3000 * 50) + (peak_rain / 500 * 50)
    
    
    total_risk = (elev_score * 0.6) + (rain_score * 0.4)
    final_risk = total_risk * slope_factor
    
    return min(round(final_risk, 2), 100)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    geojson = request.json["geometry"]
    polygon = shape(geojson)
    
    
    points = sample_points_in_polygon(polygon, 15)
    elevations = get_elevations(points)
     
    
    centroid = polygon.centroid
    annual_rain, peak_rain = get_rainfall_data(centroid.y, centroid.x)
    
   
    risk = calculate_advanced_risk(elevations, annual_rain, peak_rain)
    
    return jsonify({
        "flood_risk_percent": risk,
        "metrics": {
            "avg_elevation_m": round(float(np.mean(elevations)), 2),
            "elevation_std": round(float(np.std(elevations)), 2),
            "annual_rainfall_mm": annual_rain,
            "peak_monthly_mm": peak_rain
        }
    })

if __name__ == "__main__":
    app.run(debug=True, port=8080)



