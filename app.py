import os, sys, json, requests
from flask import Flask, render_template, request, jsonify

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'models')))
from models.scouting_engine import AdvancedScoutingEngine
from models.xai_interpreter import XAIScoutInterpreter

app = Flask(__name__)

def fetch_player_image(player_name):
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={player_name} footballer&utf8=&format=json"
        res = requests.get(url, timeout=3).json()
        if res.get('query') and res['query'].get('search'):
            title = res['query']['search'][0]['title']
            img_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={title}&prop=pageimages&format=json&pithumbsize=400"
            pages = requests.get(img_url, timeout=3).json()['query']['pages']
            for page_id in pages:
                if 'thumbnail' in pages[page_id]: return pages[page_id]['thumbnail']['source']
    except Exception: pass
    return f"https://ui-avatars.com/api/?name={player_name.replace(' ', '+')}&background=1e293b&color=38bdf8&size=200&font-size=0.4&rounded=true"

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/teams', methods=['GET'])
def get_teams():
    return jsonify(AdvancedScoutingEngine().get_all_teams())

@app.route('/api/macro-audit', methods=['POST'])
def macro_audit():
    return jsonify(AdvancedScoutingEngine().run_macro_club_audit(int(request.json.get('team_id', 4))))

@app.route('/api/scout', methods=['POST'])
def run_scout():
    data = request.json
    engine = AdvancedScoutingEngine()
    xai_data = engine.get_tactical_recommendations(int(data.get('team_id', 4)), data.get('archetype', 'Playmaker'))
    if not xai_data: return jsonify({"error": "No matches found."}), 404
    top_name = list(xai_data.keys())[0]
    brief = XAIScoutInterpreter().generate_brief(xai_data[top_name])
    return jsonify({ "candidates": [json.loads(p) for p in xai_data.values()], "top_target": top_name, "top_image_url": fetch_player_image(top_name), "executive_brief": brief })

@app.route('/api/roster', methods=['POST'])
def get_roster():
    team_id = request.json.get('team_id')
    return jsonify(AdvancedScoutingEngine().get_team_roster(team_id))

@app.route('/api/player/<int:player_id>', methods=['GET'])
def get_player(player_id):
    engine = AdvancedScoutingEngine()
    data_str = engine.get_player_profile(player_id)
    if not data_str: return jsonify({"error": "Player not found"}), 404
    
    data = json.loads(data_str)
    brief = XAIScoutInterpreter().generate_profile_brief(data_str)
    return jsonify({ "profile": data, "image_url": fetch_player_image(data['candidate_profile']['name']), "brief": brief })

if __name__ == '__main__': app.run(debug=True, port=5000)