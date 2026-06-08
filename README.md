# SQUADRA // Recruitment Matrix ⚽📊

**Intelligent Recruitment, Tactically Decoded.**

SQUADRA is a next-generation football analytics and recruitment platform. It coordinates raw database processing with Explainable AI (XAI) layers to identify optimal tactical profiles, conduct automated squad health audits, and generate natural-language executive scouting briefs.

---

## 🚀 Core Features

* **Profile-Based Archetype Engine:** Search the global database for players matching specific tactical archetypes, filtered by positional logic, financial constraints, and system playstyle compatibility.
* **Macro Squad Health Audit:** An automated scanner that detects expiring contracts, calculates replacement urgency based on club success, and cross-references the internal academy before recommending external market targets.
* **Squad Roster Dashboard:** A holistic view of the current team, visualizing individual performance profiles and algorithmic role confidence.
* **Explainable AI (XAI) Briefs:** Powered by Groq (Llama-3.1-8b-instant), the system translates complex JSON feature attributions into readable executive briefs covering *Performance Baselines*, *Tactical Synergy*, and *Market Efficiency*.
* **Dynamic Hexa-Charts:** Auto-scaling radar charts utilizing Min-Max normalization against elite positional baselines to accurately visualize player output without data skewing.

---

## 🧠 The Tactical Engine

The core of SQUADRA evaluates a player's **Composite Suitability Score** out of 100. This is calculated using a weighted matrix:

1. **Archetype Match (50%):** The base confidence score from the ML tactical profiles table.
2. **System Fit (30%):** Adjusts the player's compatibility based on the buying club's established style of play (e.g., *Tiki-Taka / Possession-Based, Counter-Attacking / Low Block, Gegenpressing / High Intensity, Wing Play / Direct*). Transitions between conflicting styles incur penalties, while matching styles grant bonuses.
3. **Financial Efficiency (20%):** Evaluates the player's market value against the club's available transfer budget.

### Supported Tactical Archetypes
The system utilizes a 10-archetype classification model mapped dynamically to specific performance tables to prevent cross-column errors:

* **Goalkeepers:** Traditional GK, Shot Stopper
* **Defenders:** Ball Playing CB, Wing Back, Ball Winner
* **Midfielders:** Playmaker
* **Attackers:** Winger, Poacher, False Nine, Inside Forward

---

## 📊 Radar Chart Normalization

To plot raw data (like 2,000 passes vs. 15 goals) onto a uniform 0-100 radar chart, the engine applies Min-Max Normalization against elite positional baselines. 

**Baselines Examples:**
* **Goalkeeping:** Saves (Max: 120), Goals Against (Max: 50), Clean Sheets (Max: 15)
* **Defensive/Midfield:** Passes (Max: 2000), Tackles/Interceptions (Max: 50), Blocks (Max: 30)
* **Attacking:** Goals (Max: 20 or 25), Assists (Max: 15), Shots per 90 (Max: 4.0 or 5.0)

*(Stats stored as native percentages, like `save_pct` or `aerials_won_pct`, map 1:1).*

---

## 🏆 Club Success Metric & Trophy Logic

The Macro Audit dynamically determines squad urgency based on a club's `squad_success_metric`. A score of 75 or higher triggers a "stable" 12-month urgency window, while a lower score triggers an aggressive 24-month rebuild window.

This score is computed via a mathematically weighted algorithm merging offensive output, league table position, and explicit silverware points.

### 1. The Core Formula
The script extracts **Goals For (GF)** and **Table Position (Pos)**, applying an inverse positional multiplier:

$$ \text{Position Inverse Weight} = \frac{21 - \text{Pos}}{20.0} $$

$$ \text{Success Metric} = \text{Round}\left( (\text{GF} \times \text{Position Inverse Weight}) + \text{Trophy Points}, \,\, 2 \right) $$

**Positional Weight Decay Example:**
* **1st Place:** $(21 - 1) / 20.0 = 1.0$ (100% of GF)
* **10th Place:** $(21 - 10) / 20.0 = 0.55$ (55% of GF)
* **20th Place:** $(21 - 20) / 20.0 = 0.05$ (5% of GF)

### 2. Silverware Bonus Weights
If a club wins a competition, these fixed point values are stacked onto their account:

| Trophy Competition | Added Point Weight |
| :--- | :--- |
| UEFA Champions League | +75 Points |
| La Liga Title | +50 Points |
| UEFA Europa League | +45 Points |
| UEFA Conference League / Copa del Rey | +30 Points |
| UEFA Super Cup | +15 Points |
| Supercopa de España | +10 Points |

### 3. Real-World Calculation Example
* **Barcelona (1st Place / 94 Goals / La Liga Title Winner):**
  $(94 \times 1.0) + 50 = 144.00$
* **Real Madrid (15th Place / 58 Goals / No Trophies):**
  $58 \times 0.30 + 0 = 17.40$

---

## 🗄️ Database Architecture

SQUADRA runs on a highly optimized MySQL relational database segmented to prevent null-data skewing.

* `teams`, `players`: Core metadata.
* `squad_assignments`, `player_positions`: Bridge tables for contracts, market values, and primary/secondary roles.
* `tactical_profiles`: Machine Learning derived archetype assignments.
* `seasonal_team_stats`: Team-level underlying metrics (PPDA, possession).
* **Positional Stats Tables:** `player_gk_stats`, `player_def_mid_stats`, `player_att_stats`. (Query routing explicitly prevents attackers from being queried against Goalkeeper matrices).

---

## 🛠️ Tech Stack

* **Backend Engine:** Python 3, Pandas, MySQL Connector
* **Web Framework:** Flask
* **Explainable AI:** Groq API (Llama-3.1-8b-instant)
* **Frontend:** HTML5, Custom CSS (Glassmorphism UI), Vanilla JavaScript
* **Visualizations:** Chart.js (Radar/Hexa charts)
* **Avatars:** UI-Avatars API (with Wikipedia Infobox image fallback logic)

---

## ⚙️ Local Setup & Installation

**1. Clone the repository:**
```bash
git clone [https://github.com/yourusername/squadra-matrix.git](https://github.com/yourusername/squadra-matrix.git)
cd squadra-matrix
```

**2. Install Python Dependencies:**

```Bash
pip install -r requirements.txt
(Requires: flask, pandas, mysql-connector-python, python-dotenv, requests, groq)
```
**3. Initialize Database:**

Run the provided SQL scripts in your MySQL workbench to build the schemas and utility checks.

**4. Environment Variables (.env):**

Create a .env file in the root directory and configure your connections. Make sure to replace the placeholder API key with your own secure key:

```
# Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_sql_password
DB_NAME=main_db

# LLM Gateway
GROQ_API_KEY=your_api_key_here
```
**5. Launch the Matrix:**

```bash
python app.py
```
Navigate to http://127.0.0.1:5000 in your browser.

**Please feel free to pull ad update the repo with your ideas and suggestions.**

<p align = center>Made with Love by Harsh Sharma </p>