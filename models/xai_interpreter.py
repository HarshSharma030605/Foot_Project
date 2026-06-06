import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class XAIScoutInterpreter:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def generate_brief(self, xai_json_str):
        try: data = json.loads(xai_json_str)
        except Exception as e: return f"Error parsing: {str(e)}"

        system_instructions = (
            "You are a Chief Data Scout for an elite football club. Write a concise, authoritative scouting brief.\n"
            "RULES:\n"
            "1. NEVER use ML terminology (e.g., JSON, SHAP, feature attribution, weight).\n"
            "2. Note that 'Financial Efficiency' measures budget saved (High = Inexpensive/Good, Low = Expensive/Risk).\n"
            "3. Explicitly mention the player's real-world 'Raw Performance' metrics in your evaluation to justify the tactical fit.\n"
            "4. Keep the output under 140 words. Do not use generic introductory greetings."
        )

        user_context = f"""
        Analyze the following candidate:
        - Player: {data['candidate_profile']['name']} ({data['candidate_profile']['position']})
        - Archetype Target: {data['rec_metadata']['requested_archetype']}
        - System Suitability: {data['explainable_ai_matrix']['composite_suit_score']}/100
        
        Raw Performance (This Season):
        {json.dumps(data['raw_performance'])}
        
        Tactical & Financial Drivers:
        {json.dumps(data['explainable_ai_matrix']['feature_attributions'])}
        """

        try:
            return self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": system_instructions}, {"role": "user", "content": user_context}],
                temperature=0.2, max_tokens=250
            ).choices[0].message.content.strip()
        except Exception as e: return f"LLM Gateway Error: {str(e)}"