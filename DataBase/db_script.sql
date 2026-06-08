-- =========================================================
-- SQUADRA RECRUITMENT MATRIX: DATABASE SCHEMA
-- =========================================================

-- Step 1: Initialize Database Space
CREATE DATABASE IF NOT EXISTS main_db;
USE main_db;

-- =========================================================
-- CORE ENTITIES
-- =========================================================

-- Step 2: Create Master Tables
CREATE TABLE teams (
    team_id INT PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    manager VARCHAR(100),
    squad_size INT DEFAULT 0,
    style_of_play VARCHAR(100),
    squad_success_metric DECIMAL(6, 2) DEFAULT 0.00,
    transfer_budget DECIMAL(15, 2) DEFAULT 0.00
);

CREATE TABLE players (
    player_id INT PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    age INT,
    nationality VARCHAR(50)
);

-- =========================================================
-- RELATIONSHIPS & TACTICAL PROFILES
-- =========================================================

-- Step 3: Create Bridge Tables
CREATE TABLE squad_assignments (
    player_id INT PRIMARY KEY,   -- A player can only have one active club contract
    team_id INT,
    squad_role VARCHAR(50),      -- e.g., 'Starter', 'Substitute'
    jersey_number INT,
    contract_end_date DATE,
    market_value DECIMAL(15, 2) DEFAULT 0.00,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE SET NULL
);

CREATE TABLE player_positions (
    player_id INT,
    position VARCHAR(10),        -- e.g., 'LW', 'ST', 'RW', 'CAM'
    position_priority VARCHAR(20), -- e.g., 'Primary', 'Secondary'
    PRIMARY KEY (player_id, position),
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE tactical_profiles (
    player_id INT PRIMARY KEY,   -- One primary profile output per player
    archetype_label VARCHAR(50), -- Assigned by Python ML engine (e.g., 'Trickster')
    confidence DECIMAL(5,4),     -- Value between 0.0000 and 1.0000
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

-- =========================================================
-- STATISTICAL DATA TABLES
-- =========================================================

-- Step 4: Team Level Statistics
CREATE TABLE seasonal_team_stats (
    stats_id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    possession_pct DECIMAL(5,2) NOT NULL DEFAULT 50.00,
    shots_per_90 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    shots_on_target_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    goals_per_shot DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    ppda_metric DECIMAL(5,2) NOT NULL DEFAULT 11.20,
    goals_scored INT NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    UNIQUE KEY uq_team_season (team_id)
);

-- Step 5: Player Level Statistics (Position Based)
CREATE TABLE player_general_stats (
    player_id INT PRIMARY KEY,
    matches_played INT NOT NULL DEFAULT 0,
    starts INT NOT NULL DEFAULT 0,
    minutes_played INT NOT NULL DEFAULT 0,
    yellow_cards INT NOT NULL DEFAULT 0,
    red_cards INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE player_gk_stats (
    player_id INT PRIMARY KEY,
    goals_against INT NOT NULL DEFAULT 0,
    saves INT NOT NULL DEFAULT 0,
    save_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    clean_sheets INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE player_def_mid_stats (
    player_id INT PRIMARY KEY,
    tackles_won INT NOT NULL DEFAULT 0,
    interceptions INT NOT NULL DEFAULT 0,
    blocks INT NOT NULL DEFAULT 0,
    passes_completed INT NOT NULL DEFAULT 0,
    progressive_passes INT NOT NULL DEFAULT 0,
    assists INT NOT NULL DEFAULT 0,
    aerials_won_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE player_att_stats (
    player_id INT PRIMARY KEY,
    goals INT NOT NULL DEFAULT 0,
    assists INT NOT NULL DEFAULT 0,
    shots_per_90 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    shots_on_target_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    goals_per_shot DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

-- UTILITY QUERIES: TO BE RUN AFTER DATA INSERTION
-- 1. Sync Squad Sizes dynamically based on active contracts
SET SQL_SAFE_UPDATES = 0;

UPDATE teams t
INNER JOIN (
    SELECT team_id, COUNT(*) AS total_count 
    FROM squad_assignments 
    GROUP BY team_id
) sa_counts ON t.team_id = sa_counts.team_id
SET t.squad_size = sa_counts.total_count;

SET SQL_SAFE_UPDATES = 1;

-- 2. Master Diagnostic Query to Verify Roster Connections
SELECT 
    t.team_name,
    sa.jersey_number,
    p.player_name,
    p.age,
    p.nationality,
    pp.position AS primary_position,
    sa.squad_role,
    sa.market_value
FROM squad_assignments sa
INNER JOIN teams t ON sa.team_id = t.team_id
INNER JOIN players p ON sa.player_id = p.player_id
LEFT JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
ORDER BY t.team_name, sa.jersey_number;