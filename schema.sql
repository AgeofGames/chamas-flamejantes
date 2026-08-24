PRAGMA foreign_keys = ON;

-- Configurações visuais/globais do site.
CREATE TABLE IF NOT EXISTS tournament_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    title TEXT NOT NULL DEFAULT 'Chamas Flamejantes',
    subtitle TEXT NOT NULL DEFAULT 'Age of Mythology: Retold',
    hero_text TEXT NOT NULL DEFAULT 'Escolha sua arena. Entre na guerra.',
    description TEXT NOT NULL DEFAULT 'Torneios abertos, chaves, séries MD3, equipes e histórico completo em uma única arena.',
    prize_total REAL NOT NULL DEFAULT 300.00,
    currency TEXT NOT NULL DEFAULT 'R$',
    max_players INTEGER NOT NULL DEFAULT 12,
    registration_open INTEGER NOT NULL DEFAULT 1,
    tournament_status TEXT NOT NULL DEFAULT 'inscricoes',
    event_date TEXT DEFAULT '', event_time TEXT DEFAULT '', lobby_name TEXT DEFAULT '', lobby_password TEXT DEFAULT '',
    show_lobby_credentials INTEGER NOT NULL DEFAULT 0, map_name TEXT DEFAULT 'A definir', notes TEXT DEFAULT '',
    elo_mode TEXT NOT NULL DEFAULT '1v1', discord_field_mode TEXT NOT NULL DEFAULT 'optional',
    accent_color TEXT NOT NULL DEFAULT '#e95d20', background_preset TEXT NOT NULL DEFAULT 'ember',
    register_button_text TEXT NOT NULL DEFAULT 'GARANTIR MINHA VAGA',
    footer_text TEXT NOT NULL DEFAULT 'Chamas Flamejantes • Age of Mythology: Retold',
    hero_image_url TEXT NOT NULL DEFAULT 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/d01c42f3798b9a73859b3947148cddcac0f272a0/ss_d01c42f3798b9a73859b3947148cddcac0f272a0.1920x1080.jpg',
    gallery_image_1 TEXT NOT NULL DEFAULT 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/d01c42f3798b9a73859b3947148cddcac0f272a0/ss_d01c42f3798b9a73859b3947148cddcac0f272a0.1920x1080.jpg',
    gallery_image_2 TEXT NOT NULL DEFAULT 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257058147/movie_full.jpg',
    gallery_image_3 TEXT NOT NULL DEFAULT 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257070884/501a50c366e017ae0e22c4dae1530a428f852f99/movie_full.jpg',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO tournament_settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS site_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '');

-- Legado V1/V2/V3, mantido para migração.
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL, discord TEXT DEFAULT '', aomstats_url TEXT NOT NULL DEFAULT '',
    aomstats_profile_id TEXT NOT NULL UNIQUE, elo_1v1 INTEGER, elo_team INTEGER, elo_display INTEGER,
    elo_verified INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'inscrito', registration_order INTEGER NOT NULL,
    avatar_url TEXT DEFAULT '', avatar_file TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS winners (
    id INTEGER PRIMARY KEY AUTOINCREMENT, participant_id INTEGER NOT NULL UNIQUE, prize_share REAL NOT NULL DEFAULT 0,
    label TEXT DEFAULT 'Vencedor', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, details TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Plataforma V5: torneios são INSTÂNCIAS. É possível criar vários do mesmo modo ao mesmo tempo.
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    mode_key TEXT NOT NULL DEFAULT 'custom',
    format_type TEXT NOT NULL CHECK(format_type IN ('ffa','round_robin','elimination')),
    team_size INTEGER NOT NULL DEFAULT 1,
    best_of INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    prize_total REAL NOT NULL DEFAULT 0,
    prize_name TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'R$',
    max_entries INTEGER NOT NULL DEFAULT 12,
    registration_open INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'inscricoes' CHECK(status IN ('inscricoes','andamento','finalizado')),
    is_public INTEGER NOT NULL DEFAULT 1,
    event_date TEXT DEFAULT '', event_time TEXT DEFAULT '', map_name TEXT DEFAULT 'A definir',
    lobby_name TEXT DEFAULT '', lobby_password TEXT DEFAULT '', show_lobby_credentials INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '', elo_mode TEXT NOT NULL DEFAULT '1v1',
    accent TEXT DEFAULT '#e95d20', display_order INTEGER NOT NULL DEFAULT 0,
    matches_generated INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL,
    discord TEXT DEFAULT '',
    aomstats_url TEXT DEFAULT '',
    aomstats_profile_id TEXT NOT NULL UNIQUE,
    elo_1v1 INTEGER, elo_team INTEGER,
    elo_verified INTEGER NOT NULL DEFAULT 0,
    avatar_url TEXT DEFAULT '', avatar_file TEXT DEFAULT '',
    quote TEXT NOT NULL DEFAULT '',
    normal_wins INTEGER NOT NULL DEFAULT 0,
    normal_losses INTEGER NOT NULL DEFAULT 0,
    normal_games INTEGER NOT NULL DEFAULT 0,
    normal_win_rate REAL NOT NULL DEFAULT 0,
    normal_level INTEGER NOT NULL DEFAULT 1,
    normal_level_label TEXT NOT NULL DEFAULT 'Novato',
    normal_stats_available INTEGER NOT NULL DEFAULT 0,
    normal_stats_updated_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    captain_discord TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    slot_no INTEGER NOT NULL,
    role TEXT DEFAULT '',
    UNIQUE(team_id, slot_no), UNIQUE(team_id, player_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tournament_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER,
    team_id INTEGER,
    status TEXT NOT NULL DEFAULT 'inscrito' CHECK(status IN ('inscrito','confirmado','reserva','removido')),
    registration_order INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    CHECK ((player_id IS NOT NULL AND team_id IS NULL) OR (player_id IS NULL AND team_id IS NOT NULL)),
    UNIQUE(tournament_id, player_id), UNIQUE(tournament_id, team_id)
);

-- score_a / score_b representam vitórias de mapas/jogos dentro da série.
-- Em MD3, o vencedor precisa chegar a 2 (2x0 ou 2x1).
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_no INTEGER NOT NULL,
    match_no INTEGER NOT NULL,
    entry_a_id INTEGER,
    entry_b_id INTEGER,
    score_a INTEGER DEFAULT 0, score_b INTEGER DEFAULT 0,
    winner_entry_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','finalizado','bye')),
    scheduled_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (entry_a_id) REFERENCES tournament_entries(id) ON DELETE SET NULL,
    FOREIGN KEY (entry_b_id) REFERENCES tournament_entries(id) ON DELETE SET NULL,
    FOREIGN KEY (winner_entry_id) REFERENCES tournament_entries(id) ON DELETE SET NULL,
    UNIQUE(tournament_id, round_no, match_no)
);

CREATE TABLE IF NOT EXISTS tournament_winners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    entry_id INTEGER NOT NULL,
    prize_share REAL NOT NULL DEFAULT 0,
    label TEXT DEFAULT 'Vencedor',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, entry_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (entry_id) REFERENCES tournament_entries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_tournament ON tournament_entries(tournament_id,status,registration_order);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id,round_no,match_no);
CREATE INDEX IF NOT EXISTS idx_members_team ON team_members(team_id,slot_no);

-- Sete torneios iniciais. Depois o administrador pode criar quantos quiser, inclusive repetindo o modo.
-- Os registros iniciais são inseridos pelo init_db() depois das migrações, para compatibilidade com bancos V4.


-- V6: patrocinadores oficiais do projeto.
CREATE TABLE IF NOT EXISTS sponsors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    aomstats_url TEXT DEFAULT '',
    aomstats_profile_id TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    avatar_file TEXT DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sponsors_aomstats_profile
ON sponsors(aomstats_profile_id)
WHERE aomstats_profile_id <> '';

-- V6: ranking interno da comunidade. Apenas o administrador cadastra.
CREATE TABLE IF NOT EXISTS community_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    community_elo INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_community_elo ON community_members(community_elo DESC);


-- =====================================================================
-- V10.2 — BIBLIOTECA DE MAPAS + GRUPOS OFICIAIS + DUELOS X1
-- =====================================================================

CREATE TABLE IF NOT EXISTS custom_maps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    creator TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'Outro',
    description TEXT NOT NULL DEFAULT '',
    image_file TEXT NOT NULL DEFAULT '',
    map_file TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL DEFAULT '',
    downloads INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_custom_maps_active
ON custom_maps(is_active, created_at DESC);

CREATE TABLE IF NOT EXISTS community_links (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    whatsapp TEXT NOT NULL DEFAULT '',
    discord TEXT NOT NULL DEFAULT '',
    telegram TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO community_links(id) VALUES (1);

CREATE TABLE IF NOT EXISTS duels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player1_id INTEGER NOT NULL,
    player2_id INTEGER NOT NULL,
    winner_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','active','finished','rejected')),
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TEXT DEFAULT '',
    finished_at TEXT DEFAULT '',
    admin_notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (player1_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (player2_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_id) REFERENCES players(id) ON DELETE SET NULL,
    CHECK(player1_id <> player2_id)
);

CREATE INDEX IF NOT EXISTS idx_duels_status
ON duels(status, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_duels_players
ON duels(player1_id, player2_id, status);
