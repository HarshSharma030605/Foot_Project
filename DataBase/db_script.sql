-- Step 1: Initialize the database space
CREATE DATABASE IF NOT EXISTS main_db;
USE main_db;

-- Step 2: Create Master Tables (No external dependencies)
CREATE TABLE teams (
    team_id INT PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    manager VARCHAR(100),
    squad_size INT
);

CREATE TABLE players (
    player_id INT PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    age INT,
    nationality VARCHAR(50)
);

-- Step 3: Create Dependent/Bridge Tables (With Foreign Keys)
CREATE TABLE squad_assignments (
    player_id INT PRIMARY KEY,   -- A player can only have one active club contract
    team_id INT,
    squad_role VARCHAR(50),      -- e.g., 'Starter', 'Substitute'
    jersey_number INT,
    contract_end_date DATE,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE player_positions (
    player_id INT,
    position VARCHAR(10),        -- e.g., 'LW', 'ST', 'RW', 'CAM'
    position_priority VARCHAR(20), -- e.g., 'Primary', 'Secondary'
    PRIMARY KEY (player_id, position), -- Prevents duplicating the same position for a player
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE TABLE tactical_profiles (
    player_id INT PRIMARY KEY,   -- One primary profile output per player
    archetype_label VARCHAR(50), -- Assigned by our Python ML engine (e.g., 'Trickster')
    confidence DECIMAL, -- Value between 0.00 and 1.00
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

-- Final Table Checks
SHOW TABLES;

ALTER TABLE teams
ADD style_of_play VARCHAR(100),
ADD squad_success_metric DECIMAL(4, 2);

select * from teams;

SET SQL_SAFE_UPDATES = 0;

UPDATE teams t
INNER JOIN (
    SELECT team_id, COUNT(*) AS total_count 
    FROM squad_assignments 
    GROUP BY team_id
) sa_counts ON t.team_id = sa_counts.team_id
SET t.squad_size = sa_counts.total_count;

SET SQL_SAFE_UPDATES = 1;

set foreign_key_checks = 0;

truncate players;
truncate player_positions;

set foreign_key_checks = 1;

SELECT * from squad_assignments;

ALTER table teams
ADD column transfer_budget DECIMAL(15,2);


-- Test Query after player and team data fullt inserted 
SELECT 
    t.team_name,
    sa.jersey_number,
    p.player_name,
    p.age,
    p.nationality,
    pp.position AS primary_position,
    sa.squad_role
FROM squad_assignments sa
INNER JOIN teams t ON sa.team_id = t.team_id
INNER JOIN players p ON sa.player_id = p.player_id
LEFT JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
ORDER BY t.team_name, sa.jersey_number;


-- 1. Safely drop the old constraint-bound schema layout
DROP TABLE IF EXISTS seasonal_team_stats;

-- 2. Build the optimized high-accuracy feature engineering table
CREATE TABLE seasonal_team_stats (
    stats_id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    possession_pct DECIMAL(5,2) NOT NULL DEFAULT 50.00,
    shots_per_90 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    shots_on_target_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    goals_per_shot DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    ppda_metric DECIMAL(5,2) NOT NULL DEFAULT 11.20,
    goals_scored INT NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE KEY uq_team_season (team_id)
);

ALTER TABLE teams MODIFY COLUMN squad_success_metric DECIMAL(6, 2) DEFAULT 0.00;
select * from squad_assignments;


-- Player Stats Tables, Classified based on positions and a standard table for good baselines
CREATE TABLE player_general_stats (
    player_id INT PRIMARY KEY,
    matches_played INT NOT NULL DEFAULT 0,
    starts INT NOT NULL DEFAULT 0,
    minutes_played INT NOT NULL DEFAULT 0,
    yellow_cards INT NOT NULL DEFAULT 0,
    red_cards INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

-- 2. Goalkeeper Table (Unchanged)
CREATE TABLE player_gk_stats (
    player_id INT PRIMARY KEY,
    goals_against INT NOT NULL DEFAULT 0,
    saves INT NOT NULL DEFAULT 0,
    save_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    clean_sheets INT NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

-- 3. Defensive & Midfield Retention Table
CREATE TABLE player_def_mid_stats (
    player_id INT PRIMARY KEY,
    tackles_won INT NOT NULL DEFAULT 0,
    interceptions INT NOT NULL DEFAULT 0,
    blocks INT NOT NULL DEFAULT 0,
    passes_completed INT NOT NULL DEFAULT 0,
    progressive_passes INT NOT NULL DEFAULT 0,
    assists INT NOT NULL DEFAULT 0,             -- Added for cross-archetype tracking
    aerials_won_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- From Miscellaneous table
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

-- 4. Attacking & Creation Table
CREATE TABLE player_att_stats (
    player_id INT PRIMARY KEY,
    goals INT NOT NULL DEFAULT 0,
    assists INT NOT NULL DEFAULT 0,             -- Shared playmaking metric
    shots_per_90 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    shots_on_target_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    goals_per_shot DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

Select distinct 