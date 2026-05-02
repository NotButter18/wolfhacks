# Synapse Project Lineup

This version of Synapse is set up so two people can work in parallel.

## Folder Structure

- `flask_app/`
  - Python backend for routing, data handling, and simulation
- `templates/`
  - HTML page for the dashboard layout
- `static/css/`
  - Styling for the dashboard
- `static/js/`
  - Client-side behavior, button actions, and chart updates
- `run.py`
  - Simple startup script for Flask

## Team Split

### Person 1: Python + Flask
- Build and maintain the simulation engine
- Create API routes
- Return JSON for the dashboard
- Handle scenario logic and overload prediction

### Person 2: HTML + CSS + JavaScript
- Build the dashboard layout
- Style the page for the hackathon demo
- Connect the button to the backend
- Render charts and update the results live

## Workflow

1. Python teammate defines the data shape returned by the backend.
2. Frontend teammate builds the cards, chart, and controls around that data.
3. Both teammates connect through the `/simulate` API.
4. Final step: polish the visuals and rehearse the demo.

