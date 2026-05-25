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