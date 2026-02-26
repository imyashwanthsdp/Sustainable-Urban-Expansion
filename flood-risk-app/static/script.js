var map = L.map('map').setView([13.0827, 80.2707], 10);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data © OpenStreetMap'
}).addTo(map);

var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
    edit: { featureGroup: drawnItems }
});
map.addControl(drawControl);

var selectedLayer;

map.on(L.Draw.Event.CREATED, function (e) {
    drawnItems.clearLayers();
    selectedLayer = e.layer;
    drawnItems.addLayer(selectedLayer);
});

function analyze() {
    if (!selectedLayer) {
        alert("Please define a search area on the map using the drawing tools.");
        return;
    }

    const btn = document.querySelector(".btn-analyze");
    const riskElement = document.getElementById("risk");
    
    // UI Feedback: Disable button to prevent double-clicks
    btn.innerText = "Analyzing Satellite Data...";
    btn.disabled = true;

    const geojson = selectedLayer.toGeoJSON();

    fetch("/analyze", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({geometry: geojson.geometry})
    })
    .then(res => {
        if (!res.ok) throw new Error("Server error");
        return res.json();
    })
    .then(data => {
        // 1. Safe parsing of values (fallback to 0 if null/undefined)
        const rain = data.rainfall_mm || 0;
        const elev = data.mean_elevation_m || 0;
        const risk = data.flood_risk_percent || 0;

        // 2. Update stats
        document.getElementById("rainfall").innerText = rain.toLocaleString();
        document.getElementById("elevation").innerText = elev.toFixed(1);

        // 3. Determine Status and CSS class
        let status = "Low Risk";
        let colorClass = "low";

        if (risk >= 85) {
            status = "Critical";
            colorClass = "high";
        } else if (risk >= 60) {
            status = "High Alert";
            colorClass = "high";
        } else if (risk >= 30) {
            status = "Moderate";
            colorClass = "medium";
        }

        // 4. Update Risk Element (Replacing content instead of adding to it)
        riskElement.className = `risk-value ${colorClass}`;
        riskElement.innerHTML = `
            ${status}
            <div style="font-size: 14px; opacity: 0.6; font-weight: 400; margin-top: 4px;">
                Confidence Score: ${risk}%
            </div>
        `;
    })
    .catch(err => {
        console.error("Analysis failed:", err);
        alert("Could not process analysis. Ensure the area is within supported bounds.");
    })
    .finally(() => {
        // Reset button state
        btn.innerText = "Run Analysis";
        btn.disabled = false;
    });
}