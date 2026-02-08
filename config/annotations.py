"""Key regulatory event annotations for charts."""

# List of notable regulatory events to annotate on Chart 3
# Each entry: (year, label, description)
REGULATORY_EVENTS = [
    (2013, "Abbott deregulation", "Coalition government launches deregulation agenda"),
    (2020, "COVID response", "Emergency regulatory changes for pandemic response"),
    (2024, "AICD report", "Australian Institute of Company Directors regulatory burden report"),
]

def get_event_annotations():
    """Return list of event annotations for Plotly charts."""
    annotations = []
    for year, label, description in REGULATORY_EVENTS:
        annotations.append({
            "x": year,
            "y": 1,
            "yref": "paper",
            "text": label,
            "showarrow": True,
            "arrowhead": 0,
            "ax": 0,
            "ay": -40,
            "font": {"size": 10, "color": "#666"},
            "hovertext": description,
        })
    return annotations

def get_vline_shapes():
    """Return vertical line shapes for key events."""
    shapes = []
    for year, label, description in REGULATORY_EVENTS:
        shapes.append({
            "type": "line",
            "x0": year,
            "x1": year,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": "#999", "width": 1, "dash": "dash"},
        })
    return shapes
