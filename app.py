import os
import sys
import json
import requests
from flask import Flask, render_template, request, jsonify

# Ensure the models directory is accessible to Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'models')))

from models.scouting_engine import AdvancedScoutingEngine
from models.xai_interpreter import XAIScoutInterpreter

app = Flask(__name__)

def fetch_player_image(player_name):
    """Uses UI-Avatars for guaranteed production reliability."""
    try:
        encoded_name = player_name.replace(" ", "+")
        return f"https://ui-avatars.com/api/?name={encoded_name}&background=1e293b&color=38bdf8&size=200&font-size=0.4&rounded=true"
    except Exception:
        return "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=400"

@app.route('/')
def index():
    """Serves the main frontend Single Page Application (SPA)."""
    return render_template('index.html')

@app.route('/api/macro-audit', methods=['POST'])
def macro_audit():
    """Endpoint: Runs the squad health audit and checks internal academy depth."""
    try:
        engine = AdvancedScoutingEngine()
        result = engine.run_macro_club_audit(int(request.json.get('team_id', 4)))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scout', methods=['POST'])
def run_scout():
    """Endpoint: Runs the Archetype Search and generates the XAI brief."""
    data = request.json
    try:
        engine = AdvancedScoutingEngine()
        xai_data = engine.get_tactical_recommendations(int(data.get('team_id', 4)), data.get('archetype', 'Playmaker'))
        
        if not xai_data:
            return jsonify({"error": "No affordable candidates matching this profile were found."}), 404

        top_name = list(xai_data.keys())[0]
        
        # Initialize Interpreter
        interpreter = XAIScoutInterpreter()
        brief = interpreter.generate_brief(xai_data[top_name])

        return jsonify({
            "candidates": [json.loads(p) for p in xai_data.values()],
            "top_target": top_name,
            "top_image_url": fetch_player_image(top_name),
            "executive_brief": brief
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)