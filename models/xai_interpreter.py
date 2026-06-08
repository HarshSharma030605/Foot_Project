import os
import json
import textwrap
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class XAIScoutInterpreter:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def generate_brief(self, xai_json_str):
        try: data = json.loads(xai_json_str)
        except Exception as e: return f"Error parsing payload: {str(e)}"

        system_instructions = textwrap.dedent("""\
            You are the Lead Technical Scout and Data Analyst for an elite football club. Write a highly analytical, authoritative executive scouting brief.
            RULES:
            1. Use three bold headers: **Performance Baseline**, **Tactical Synergy**, and **Market Efficiency**.
            2. Explicitly cite raw data metrics.
            3. Explain why the System Fit and Archetype Match scores apply.
            4. Keep output under 200 words. Maintain a clinical, data-driven tone.
        """)

        user_context = f"Evaluate Candidate: {data['candidate_profile']['name']}\nData: {json.dumps(data)}"
        try:
            return self.client.chat.completions.create(
                model="llama-3.1-8b-instant", messages=[{"role": "system", "content": system_instructions}, {"role": "user", "content": user_context}], temperature=0.3, max_tokens=350
            ).choices[0].message.content.strip()
        except Exception as e: return f"LLM Gateway Error: {str(e)}"

    def generate_profile_brief(self, xai_json_str):
        """Generates a profile for a current squad member."""
        try: data = json.loads(xai_json_str)
        except Exception as e: return f"Error parsing payload: {str(e)}"

        system_instructions = textwrap.dedent("""\
            You are the Lead Technical Coach. Write a performance review for a current squad member.
            RULES:
            1. Use two bold headers: **Performance Overview** and **Tactical Identity**.
            2. In Performance Overview, evaluate their raw stats.
            3. In Tactical Identity, explain their designated Archetype and their confidence score in playing that role.
            4. Keep output under 150 words. Be clinical and objective.
        """)

        user_context = f"Review Player: {data['candidate_profile']['name']}\nData: {json.dumps(data)}"
        try:
            return self.client.chat.completions.create(
                model="llama-3.1-8b-instant", messages=[{"role": "system", "content": system_instructions}, {"role": "user", "content": user_context}], temperature=0.3, max_tokens=350
            ).choices[0].message.content.strip()
        except Exception as e: return f"LLM Gateway Error: {str(e)}"