from __future__ import annotations

import csv
import html as html_lib
import io
import math
import os
import re
import secrets
import shutil
import sqlite3
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template,
    request, send_file, send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

# ----------------------------------------------------------------------
# V9 RAILWAY
# No Windows/local, mantém os caminhos da V7.5.
# No Railway, usa automaticamente o Volume persistente anexado ao serviço.
# ----------------------------------------------------------------------
RAILWAY_VOLUME_PATH = (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
RUNNING_ON_RAILWAY = bool(os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_ENVIRONMENT_ID"))

if RAILWAY_VOLUME_PATH:
    PERSISTENT_DIR = Path(RAILWAY_VOLUME_PATH).resolve()
    DB_PATH = PERSISTENT_DIR / "tournament.sqlite"
    UPLOAD_DIR = PERSISTENT_DIR / "uploads"
    MAPS_DIR = PERSISTENT_DIR / "maps"
else:
    PERSISTENT_DIR = None
    DB_PATH = BASE_DIR / "data" / "tournament.sqlite"
    UPLOAD_DIR = BASE_DIR / "static" / "uploads"
    MAPS_DIR = BASE_DIR / "static" / "maps"

MAP_FILES_DIR = MAPS_DIR / "files"
MAP_IMAGES_DIR = MAPS_DIR / "images"

SEED_DB_PATH = BASE_DIR / "data" / "tournament.sqlite"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAP_FILES_DIR.mkdir(parents=True, exist_ok=True)
MAP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def prepare_persistent_storage():
    """
    Prepara o armazenamento antes do Flask iniciar.
    No primeiro deploy Railway, copia o banco inicial para o Volume.
    Depois disso, o banco do Volume passa a ser a única fonte persistente.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    MAP_FILES_DIR.mkdir(parents=True, exist_ok=True)
    MAP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if RAILWAY_VOLUME_PATH and not DB_PATH.exists() and SEED_DB_PATH.exists():
        shutil.copy2(SEED_DB_PATH, DB_PATH)

    # Copia uploads empacotados apenas no primeiro uso, sem sobrescrever.
    if RAILWAY_VOLUME_PATH:
        packaged_uploads = BASE_DIR / "static" / "uploads"
        if packaged_uploads.exists():
            for source in packaged_uploads.iterdir():
                if not source.is_file() or source.name == ".gitkeep":
                    continue
                target = UPLOAD_DIR / source.name
                if not target.exists():
                    shutil.copy2(source, target)


def storage_is_persistent():
    return bool(RAILWAY_VOLUME_PATH)

app = Flask(__name__)
app.secret_key = os.environ.get("FFA_SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=120 * 1024 * 1024,
)

ACTIVE_STATUSES = ("inscrito", "confirmado")
ALL_STATUSES = ("inscrito", "confirmado", "reserva", "removido")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
AOM_IMAGE_DEFAULTS = {
    "hero_image_url": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/d01c42f3798b9a73859b3947148cddcac0f272a0/ss_d01c42f3798b9a73859b3947148cddcac0f272a0.1920x1080.jpg?t=1776875258",
    "gallery_image_1": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/d01c42f3798b9a73859b3947148cddcac0f272a0/ss_d01c42f3798b9a73859b3947148cddcac0f272a0.1920x1080.jpg?t=1776875258",
    "gallery_image_2": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257058147/movie_full.jpg",
    "gallery_image_3": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257070884/501a50c366e017ae0e22c4dae1530a428f852f99/movie_full.jpg",
}



# ============================================================
# V7 — FUNDOS DE AGE OF MYTHOLOGY: RETOLD POR PÁGINA
# Fontes visuais: Xbox / PlayStation / Steam.
# ============================================================
AOM_PAGE_BACKGROUNDS = [
    "https://assets.xboxservices.com/assets/bc/47/bc474335-7a87-4591-809d-624c55ee027e.jpg?n=9929222222_GLP-Page-Hero-1084_1920x1080.jpg",
    "https://assets.xboxservices.com/assets/86/bc/86bc5f46-80f4-40d6-aa30-8fda62e6cb2d.jpg?n=9929222222_Highlight-Feature-1084_1_1920x720.jpg",
    "https://assets.xboxservices.com/assets/b2/e6/b2e640cb-ec23-4889-bf4f-0896ee484fc0.jpg?n=9929222222_Highlight-Feature-1084_2_1920x720.jpg",
    "https://assets.xboxservices.com/assets/3d/7d/3d7d1a93-9e49-4ea7-baca-2c94bb0f7acd.jpg?n=9929222222_Highlight-Feature-1084_3_1920x720.jpg",
    "https://assets.xboxservices.com/assets/4a/cf/4acfd71c-be15-4e67-9a90-d3ed075e29eb.jpg?n=9929222222_Highlight-Feature-1084_4_1920x720.jpg",
    "https://assets.xboxservices.com/assets/55/3e/553e758b-13eb-4e73-9e92-64bdae52e7b4.jpg?n=9929222222_Image-1084_Details-intro_1920x300.jpg",
    "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/c301dfea0e791dbe444635a77a203eebcd9a287b/ss_c301dfea0e791dbe444635a77a203eebcd9a287b.1920x1080.jpg?t=1780429786",
    "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1934680/d01c42f3798b9a73859b3947148cddcac0f272a0/ss_d01c42f3798b9a73859b3947148cddcac0f272a0.1920x1080.jpg?t=1776875258",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-01-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-02-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-03-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-04-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-05-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-screenshot-06-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/Age-of-Mythology-Retold-background-desktop-01-en-24feb25?fmt=webp&wid=1920",
    "https://gmedia.playstation.com/is/image/SIEPDC/age-of-mythology-retold-video-hero-desktop-01-24feb25?fmt=webp&wid=1920",
    "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257058147/movie_full.jpg",
    "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/257070884/501a50c366e017ae0e22c4dae1530a428f852f99/movie_full.jpg",
]

STATIC_PAGE_BG_INDEX = {
    "home": 0,
    "open_tournaments_page": 1,
    "tournament_history": 3,
    "community_page": 12,
    "admin": 6,
    "admin_login": 14,
    "setup": 15,
}

TOURNAMENT_PAGE_BG_OFFSET = {
    "tournament_page": 0,
    "tournament_register": 2,
    "tournament_participants": 4,
    "tournament_matches": 6,
    "tournament_result": 8,
    "admin_tournament": 10,
}


def page_background_url():
    """Escolhe um cenário diferente conforme a página/torneio."""
    endpoint = request.endpoint or "home"
    if endpoint in STATIC_PAGE_BG_INDEX:
        return AOM_PAGE_BACKGROUNDS[STATIC_PAGE_BG_INDEX[endpoint] % len(AOM_PAGE_BACKGROUNDS)]

    if endpoint in TOURNAMENT_PAGE_BG_OFFSET:
        seed = 0
        try:
            if request.view_args:
                if request.view_args.get("slug"):
                    t = get_tournament(request.view_args["slug"])
                    seed = int(t["id"]) if t else sum(ord(c) for c in request.view_args["slug"])
                elif request.view_args.get("tournament_id"):
                    seed = int(request.view_args["tournament_id"])
        except Exception:
            seed = 0
        idx = (seed + TOURNAMENT_PAGE_BG_OFFSET[endpoint]) % len(AOM_PAGE_BACKGROUNDS)
        return AOM_PAGE_BACKGROUNDS[idx]

    # Demais páginas recebem um cenário estável baseado no nome da rota.
    idx = sum(ord(c) for c in endpoint) % len(AOM_PAGE_BACKGROUNDS)
    return AOM_PAGE_BACKGROUNDS[idx]


def get_db():
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 30000")
        # WAL melhora a convivência entre leituras e gravações no site.
        try:
            g.db.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _has_column(db, table: str, column: str) -> bool:
    return any(row[1] == column for row in db.execute(f"PRAGMA table_info({table})"))


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    # Migração automática para quem substituir a versão antiga mantendo o SQLite.
    if not _has_column(db, "participants", "avatar_url"):
        db.execute("ALTER TABLE participants ADD COLUMN avatar_url TEXT DEFAULT ''")
    if not _has_column(db, "participants", "avatar_file"):
        db.execute("ALTER TABLE participants ADD COLUMN avatar_file TEXT DEFAULT ''")

    # Imagens do tema Age of Mythology: Retold, editáveis no painel.
    for column, default_url in AOM_IMAGE_DEFAULTS.items():
        if not _has_column(db, "tournament_settings", column):
            safe_default = default_url.replace("'", "''")
            db.execute(f"ALTER TABLE tournament_settings ADD COLUMN {column} TEXT NOT NULL DEFAULT '{safe_default}'")

    db.execute(
        "UPDATE tournament_settings SET title='Chamas Flamejantes' WHERE id=1 AND title='FFA UNDERLORD'"
    )
    db.execute(
        "UPDATE tournament_settings SET footer_text='Chamas Flamejantes • Age of Mythology: Retold' "
        "WHERE id=1 AND footer_text LIKE 'FFA UNDERLORD%'"
    )
    db.commit()
    db.close()


def settings():
    return get_db().execute("SELECT * FROM tournament_settings WHERE id=1").fetchone()


def active_count():
    row = get_db().execute(
        "SELECT COUNT(*) AS c FROM participants WHERE status IN ('inscrito','confirmado')"
    ).fetchone()
    return int(row["c"])


def has_admin():
    return get_db().execute("SELECT 1 FROM admins LIMIT 1").fetchone() is not None


DEFAULT_ADMIN_USERNAME = "yukinochannyan"
DEFAULT_ADMIN_PASSWORD = "yukinochannyan60"


def ensure_default_admin():
    """
    Garante que o usuário padrão exista.
    Se ele já existir, sua senha atual é preservada para permitir
    que o administrador troque a senha pelo painel.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    exists = db.execute(
        "SELECT id FROM admins WHERE username=?",
        (DEFAULT_ADMIN_USERNAME,)
    ).fetchone()
    if not exists:
        db.execute(
            "INSERT INTO admins(username,password_hash) VALUES (?,?)",
            (
                DEFAULT_ADMIN_USERNAME,
                generate_password_hash(
                    DEFAULT_ADMIN_PASSWORD,
                    method="pbkdf2:sha256:260000"
                )
            )
        )
        db.commit()
    db.close()


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def require_csrf():
    token = request.form.get("_csrf", "")
    if not token or token != session.get("_csrf"):
        abort(400, "Token de segurança inválido. Atualize a página e tente novamente.")


def log_action(action: str, details: str = ""):
    db = get_db()
    db.execute("INSERT INTO audit_log(action, details) VALUES (?, ?)", (action, details[:1000]))
    db.commit()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def normalize_profile_url(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None, None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
    except Exception:
        return None, None
    host = parsed.netloc.lower().split(":")[0]
    if host not in ("aomstats.io", "www.aomstats.io"):
        return None, None
    match = re.fullmatch(r"/profile/(\d+)/?", parsed.path)
    if not match:
        return None, None
    profile_id = match.group(1)
    return f"https://aomstats.io/profile/{profile_id}", profile_id


def _first_srcset_url(value: str):
    if not value:
        return ""
    # srcset: "url 1x, url2 2x". Preferimos a maior versão disponível.
    parts = []
    for item in value.split(","):
        url = item.strip().split()[0] if item.strip() else ""
        if url:
            parts.append(url)
    return parts[-1] if parts else ""


def _looks_like_profile_avatar(url: str) -> bool:
    u = (url or "").lower()
    if not u:
        return False
    blocked = ("aomstats", "logo", "flag", "country", "god-", "/gods/", "map", "icon")
    if any(x in u for x in blocked) and "steamstatic" not in u:
        return False
    return any(x in u for x in (
        "steamstatic", "akamaihd", "steamcdn", "avatar", "profile", "xboxlive", "gamerpic"
    ))


def _normalize_external_image_url(raw: str):
    """Normaliza URLs que podem vir escapadas em JSON/Svelte/HTML."""
    if not raw:
        return ""
    value = html_lib.unescape(str(raw)).strip().strip('"\'')
    # Formas comuns dentro de payloads JSON/Svelte.
    value = value.replace(r"\/", "/")
    value = value.replace(r"\u002F", "/").replace(r"\u002f", "/")
    value = value.replace(r"\u003A", ":").replace(r"\u003a", ":")
    value = value.replace(r"\u0026", "&")
    value = value.replace("\\/", "/")
    if value.startswith("//"):
        value = "https:" + value
    return value


def _is_steam_avatar_url(url: str) -> bool:
    try:
        parsed = urlparse(_normalize_external_image_url(url))
        host = parsed.netloc.lower().split(":")[0]
    except Exception:
        return False
    return host in {
        "avatars.steamstatic.com",
        "avatars.cloudflare.steamstatic.com",
        "steamcdn-a.akamaihd.net",
    } and bool(re.search(r"\.(?:jpe?g|png|webp)(?:$|\?)", parsed.path + ("?" + parsed.query if parsed.query else ""), re.I))


def _extract_steam_avatar_from_text(text: str):
    """Encontra a URL exata de avatar Steam em HTML/JSON/Svelte, inclusive escapada."""
    if not text:
        return ""

    # Trabalhamos com cópias normalizadas para cobrir JSON com \/ e \u002F.
    candidates_text = [
        text,
        html_lib.unescape(text),
        text.replace(r"\/", "/"),
        text.replace(r"\u002F", "/").replace(r"\u002f", "/")
            .replace(r"\u003A", ":").replace(r"\u003a", ":"),
    ]

    # Primeiro: domínio EXATO usado nas fotos de perfil da Steam/AoMStats.
    patterns = [
        r'https?://avatars(?:\.cloudflare)?\.steamstatic\.com/[A-Za-z0-9_./%?=&+-]+',
        r'https?://steamcdn-a\.akamaihd\.net/[A-Za-z0-9_./%?=&+-]+',
        r'//avatars(?:\.cloudflare)?\.steamstatic\.com/[A-Za-z0-9_./%?=&+-]+',
    ]
    for blob in candidates_text:
        for pattern in patterns:
            for m in re.finditer(pattern, blob, re.I):
                candidate = _normalize_external_image_url(m.group(0)).rstrip('),;]}>')
                if _is_steam_avatar_url(candidate):
                    return candidate

    # Segundo: campos estruturados conhecidos.
    field_patterns = [
        r'"avatar_url"\s*:\s*"([^"]+)"',
        r'"avatarUrl"\s*:\s*"([^"]+)"',
        r'"avatar"\s*:\s*"([^"]+)"',
        r'"profile_picture"\s*:\s*"([^"]+)"',
        r'"profilePicture"\s*:\s*"([^"]+)"',
    ]
    for blob in candidates_text:
        for pattern in field_patterns:
            for m in re.finditer(pattern, blob, re.I):
                candidate = _normalize_external_image_url(m.group(1))
                if _is_steam_avatar_url(candidate):
                    return candidate
    return ""


def _extract_avatar_from_aomstats(soup, html: str, profile_url: str):
    """Extrai a MESMA foto Steam mostrada pelo AoMStats."""
    # 1) Prioridade absoluta: qualquer URL steamstatic no HTML/dados Svelte.
    direct_steam = _extract_steam_avatar_from_text(html)
    if direct_steam:
        return direct_steam

    # 2) Imagem renderizada pelo AoMStats com alt="... profile picture".
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip().lower()
        if "profile picture" not in alt and "avatar" not in alt:
            continue
        candidates = [
            img.get("src"), img.get("data-src"),
            _first_srcset_url(img.get("srcset") or ""),
            _first_srcset_url(img.get("data-srcset") or ""),
        ]
        for candidate in candidates:
            candidate = _normalize_external_image_url(candidate)
            if not candidate or candidate.startswith("data:"):
                continue
            candidate = urljoin(profile_url, candidate)
            # Se for Steam, devolvemos exatamente a mesma URL.
            if _is_steam_avatar_url(candidate):
                return candidate
            if _looks_like_profile_avatar(candidate):
                return candidate

    # 3) Campos de avatar serializados, mesmo que não sejam Steam.
    generic_patterns = [
        r'"avatar_url"\s*:\s*"([^"]+)"',
        r'"avatarUrl"\s*:\s*"([^"]+)"',
        r'"profile_picture"\s*:\s*"([^"]+)"',
        r'"profilePicture"\s*:\s*"([^"]+)"',
    ]
    normalized_html = html_lib.unescape(html).replace(r"\/", "/")
    for pattern in generic_patterns:
        for m in re.finditer(pattern, normalized_html, re.I):
            candidate = _normalize_external_image_url(m.group(1))
            if candidate.startswith("http") and _looks_like_profile_avatar(candidate):
                return candidate

    # 4) Metadados sociais, desde que realmente pareçam avatar.
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            candidate = urljoin(profile_url, _normalize_external_image_url(meta.get("content")))
            if _looks_like_profile_avatar(candidate):
                return candidate
    return ""

def _extract_steam_profile_link(soup, html: str):
    """Localiza o link Steam público associado ao jogador no AoMStats."""
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "steamcommunity.com/id/" in href or "steamcommunity.com/profiles/" in href:
            return href
    m = re.search(r'https?://steamcommunity\.com/(?:id|profiles)/[^"\'<>\\ ]+', html, re.I)
    return m.group(0).replace(r"\/", "/") if m else ""


def _fetch_steam_avatar(steam_profile_url: str):
    """Busca a foto pública da Steam. É a mesma origem usada em muitos perfis do AoMStats."""
    if not steam_profile_url:
        return ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    try:
        r = requests.get(steam_profile_url, headers=headers, timeout=8, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Steam publica a foto do perfil como og:image.
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            candidate = og.get("content").strip()
            if "steamstatic" in candidate or "akamaihd" in candidate:
                return candidate
        # Fallback para o elemento de avatar do perfil.
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            classes = " ".join(img.get("class") or []).lower()
            if src and ("playeravatar" in classes or "avatar" in classes) and ("steamstatic" in src or "akamaihd" in src):
                return src
    except Exception:
        pass
    return ""



def calculate_normal_level(wins: int, losses: int):
    """
    Nível 1-100 para jogadores SEM ELO.
    Combina quantidade de vitórias + taxa de vitória.
    Elo ranqueado SEMPRE tem prioridade sobre este nível no ranking.
    """
    wins = max(int(wins or 0), 0)
    losses = max(int(losses or 0), 0)
    games = wins + losses
    if games <= 0:
        return 1, "Novato"

    win_rate = wins / games
    # Vitória e consistência contam; derrotas reduzem a taxa.
    level = round((math.sqrt(wins) * 5.0) + (win_rate * 50.0))
    level = max(1, min(100, level))

    if level >= 95:
        label = "Lenda"
    elif level >= 80:
        label = "Mestre"
    elif level >= 60:
        label = "Veterano"
    elif level >= 40:
        label = "Guerreiro"
    elif level >= 20:
        label = "Aprendiz"
    else:
        label = "Novato"
    return level, label


def _aom_int(value):
    return int(re.sub(r"[^\d]", "", str(value or "")) or 0)


def fetch_aomstats_normal_stats(profile_url: str, headers=None):
    """
    Lê somente Customs/Quickplay (leaderboard=0), ou seja, partidas não ranqueadas.
    O AoMStats exibe um resumo no formato: '75 games - 28 W 47 L'.
    """
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
    }
    custom_url = profile_url + "?leaderboard=0"
    try:
        r = requests.get(custom_url, headers=headers, timeout=12, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        m = re.search(
            r"([\d.,]+)\s+games?\s*-\s*([\d.,]+)\s*W\s+([\d.,]+)\s*L",
            text,
            re.I,
        )
        if not m:
            return {
                "normal_games": 0, "normal_wins": 0, "normal_losses": 0,
                "normal_win_rate": 0.0, "normal_level": 1,
                "normal_level_label": "Novato", "normal_stats_available": 0,
            }

        games = _aom_int(m.group(1))
        wins = _aom_int(m.group(2))
        losses = _aom_int(m.group(3))
        # O resumo do próprio AoMStats é a fonte principal.
        if games <= 0 and wins + losses > 0:
            games = wins + losses
        rate = (wins / (wins + losses) * 100.0) if (wins + losses) else 0.0
        level, level_label = calculate_normal_level(wins, losses)
        return {
            "normal_games": games,
            "normal_wins": wins,
            "normal_losses": losses,
            "normal_win_rate": round(rate, 2),
            "normal_level": level,
            "normal_level_label": level_label,
            "normal_stats_available": 1,
        }
    except Exception:
        return {
            "normal_games": 0, "normal_wins": 0, "normal_losses": 0,
            "normal_win_rate": 0.0, "normal_level": 1,
            "normal_level_label": "Novato", "normal_stats_available": 0,
        }


def fetch_aomstats(profile_url: str):
    """Lê Nick, Elo e, principalmente, a MESMA foto exibida pelo AoMStats/Steam."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    response = requests.get(profile_url, headers=headers, timeout=12, allow_redirects=True)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    nickname = ""
    h1 = soup.find("h1")
    if h1:
        nickname = h1.get_text(" ", strip=True)

    avatar_url = _extract_avatar_from_aomstats(soup, html, profile_url)
    steam_profile_url = _extract_steam_profile_link(soup, html)

    # Se o HTML inicial do AoMStats não carregar a imagem (ex.: Svelte/SSR mudou),
    # seguimos o link social da Steam e buscamos a foto oficial do mesmo perfil.
    if (not avatar_url or not _looks_like_profile_avatar(avatar_url)) and steam_profile_url:
        steam_avatar = _fetch_steam_avatar(steam_profile_url)
        if steam_avatar:
            avatar_url = steam_avatar

    elos = {"1v1": None, "team": None}
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 3:
            continue
        mode = cells[0].lower()
        rating_match = re.search(r"\b(\d{3,5})\b", cells[2])
        if not rating_match:
            continue
        rating = int(rating_match.group(1))
        if "sup 1v1" in mode:
            elos["1v1"] = rating
        elif "sup team" in mode:
            elos["team"] = rating

    page_text = soup.get_text("\n", strip=True)
    for key, label in (("1v1", "Sup 1v1"), ("team", "Sup Team")):
        if elos[key] is None:
            m = re.search(re.escape(label) + r".{0,180}?\b(\d{3,5})\b", page_text, re.I | re.S)
            if m:
                elos[key] = int(m.group(1))

    if not nickname:
        raise ValueError("Não foi possível identificar o jogador no AoMStats.")

    normal_stats = fetch_aomstats_normal_stats(profile_url, headers=headers)
    return {
        "nickname": nickname,
        "elo_1v1": elos["1v1"],
        "elo_team": elos["team"],
        "avatar_url": avatar_url,
        "steam_profile_url": steam_profile_url,
        **normal_stats,
    }

def _safe_image_extension(filename: str):
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_IMAGE_EXTENSIONS else None


def remove_local_avatar(relative_file: str):
    if not relative_file or not relative_file.startswith("uploads/"):
        return
    filename = Path(relative_file).name
    target = (UPLOAD_DIR / filename).resolve()
    uploads = UPLOAD_DIR.resolve()
    try:
        target.relative_to(uploads)
    except ValueError:
        return
    if target.exists() and target.is_file():
        target.unlink(missing_ok=True)


def save_uploaded_avatar(file_storage, key: str):
    if not file_storage or not file_storage.filename:
        return ""
    ext = _safe_image_extension(file_storage.filename)
    if not ext:
        raise ValueError("Formato inválido. Use JPG, PNG ou WebP.")
    if file_storage.mimetype not in CONTENT_TYPE_EXTENSIONS:
        raise ValueError("O arquivo enviado não parece ser uma imagem JPG, PNG ou WebP.")
    safe_key = re.sub(r"[^A-Za-z0-9_-]", "_", str(key))[:60] or secrets.token_hex(8)
    filename = f"manual_{safe_key}_{secrets.token_hex(5)}{ext}"
    path = UPLOAD_DIR / filename
    file_storage.save(path)
    return f"uploads/{filename}"


def cache_remote_avatar(avatar_url: str, profile_id: str):
    if not avatar_url:
        return ""
    parsed = urlparse(avatar_url)
    if parsed.scheme not in ("http", "https"):
        return ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36",
        "Referer": "https://aomstats.io/",
    }
    try:
        r = requests.get(avatar_url, headers=headers, timeout=10, stream=True)
        r.raise_for_status()
        content_type = (r.headers.get("Content-Type") or "").split(";")[0].lower()
        ext = CONTENT_TYPE_EXTENSIONS.get(content_type)
        if not ext:
            ext = _safe_image_extension(urlparse(avatar_url).path)
        if not ext:
            return ""
        max_bytes = 4 * 1024 * 1024
        total = 0
        chunks = []
        for chunk in r.iter_content(65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                return ""
            chunks.append(chunk)
        safe_id = re.sub(r"\D", "", str(profile_id)) or secrets.token_hex(6)
        filename = f"aom_{safe_id}_{secrets.token_hex(4)}{ext}"
        (UPLOAD_DIR / filename).write_bytes(b"".join(chunks))
        return f"uploads/{filename}"
    except Exception:
        return ""


def avatar_src(participant):
    """Upload manual tem prioridade; sem upload, usa a foto Steam/AoMStats."""
    try:
        local = participant["avatar_file"] or ""
        remote = participant["avatar_url"] or ""
    except Exception:
        return ""

    remote = _normalize_external_image_url(remote)
    if local:
        return url_for("uploaded_media", filename=Path(local).name)
    if remote:
        return remote
    return ""


app.jinja_env.globals["avatar_src"] = avatar_src

@app.get("/uploads/<path:filename>")
def uploaded_media(filename):
    # send_from_directory impede escapar da pasta de uploads.
    return send_from_directory(UPLOAD_DIR, filename, max_age=86400)


def sponsor_avatar_src(sponsor):
    """Usa a mesma regra de avatar dos jogadores: Steam/AoMStats direto primeiro."""
    return avatar_src(sponsor)


app.jinja_env.globals["sponsor_avatar_src"] = sponsor_avatar_src


# ============================================================
# CHAMAS FLAMEJANTES V5 — MULTI-TORNEIOS + HISTÓRICO + MD3
# ============================================================

TOURNAMENT_TEMPLATES = {
    "ffa": {"label": "FFA — Sem Regras", "short": "FFA", "format_type": "ffa", "team_size": 1, "best_of": 1, "max_entries": 12, "hard_limit": 12, "elo_mode": "1v1", "accent": "#e95d20", "description": "Todos contra todos, alianças e traições permitidas. Pode haver um ou vários vencedores."},
    "food_wood_gold": {"label": "FOOD WOOD GOLD — 3x3", "short": "FOOD WOOD GOLD", "format_type": "elimination", "team_size": 3, "best_of": 1, "max_entries": 12, "hard_limit": 12, "elo_mode": "team", "accent": "#c89a42", "description": "Equipes de 3 com funções FOOD, WOOD e GOLD. Perdeu o confronto, está eliminada."},
    "1v1_round_robin": {"label": "1v1 — Todos Contra Todos", "short": "1v1", "format_type": "round_robin", "team_size": 1, "best_of": 1, "max_entries": 32, "hard_limit": 32, "elo_mode": "1v1", "accent": "#b54331", "description": "Até 32 jogadores. Todos enfrentam todos; a classificação é ordenada por vitórias."},
    "2v2_elimination": {"label": "2x2 — Eliminação", "short": "2x2", "format_type": "elimination", "team_size": 2, "best_of": 1, "max_entries": 16, "hard_limit": 32, "elo_mode": "team", "accent": "#8c6a35", "description": "Duplas em mata-mata. Perdeu, está fora; venceu, avança."},
    "bo3_1v1": {"label": "Melhor de 3 — 1x1", "short": "MD3 1x1", "format_type": "elimination", "team_size": 1, "best_of": 3, "max_entries": 32, "hard_limit": 32, "elo_mode": "1v1", "accent": "#a9442b", "description": "Mata-mata em séries Melhor de 3. O primeiro jogador a vencer 2 partidas avança."},
    "bo3_2v2": {"label": "Melhor de 3 — 2x2", "short": "MD3 2x2", "format_type": "elimination", "team_size": 2, "best_of": 3, "max_entries": 16, "hard_limit": 32, "elo_mode": "team", "accent": "#9f672f", "description": "Duplas em séries Melhor de 3. A primeira equipe a fazer 2 vitórias avança."},
    "bo3_3v3": {"label": "Melhor de 3 — 3x3", "short": "MD3 3x3", "format_type": "elimination", "team_size": 3, "best_of": 3, "max_entries": 12, "hard_limit": 24, "elo_mode": "team", "accent": "#73553a", "description": "Equipes de três em séries Melhor de 3. Venceu 2 jogos, avança; perdeu a série, acabou."},
}
ENTRY_ACTIVE_STATUSES = ("inscrito", "confirmado")
ENTRY_STATUSES = ("inscrito", "confirmado", "reserva", "removido")


def tournament_template(mode_key):
    return TOURNAMENT_TEMPLATES.get(mode_key) or TOURNAMENT_TEMPLATES["ffa"]


def tournament_hard_limit(tournament):
    try:
        return int(tournament_template(tournament["mode_key"])["hard_limit"])
    except Exception:
        return 32


def mode_icon(tournament):
    try:
        key = tournament["mode_key"]
    except Exception:
        key = ""
    return {
        "ffa": "🔥", "food_wood_gold": "🥩", "1v1_round_robin": "⚔️", "2v2_elimination": "🤝",
        "bo3_1v1": "⚔️", "bo3_2v2": "🛡️", "bo3_3v3": "🏛️"
    }.get(key, "🔥")


app.jinja_env.globals["mode_icon"] = mode_icon


def init_db():
    """Cria o schema V5 e migra automaticamente V1/V2/V3/V4 sem apagar inscrições."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    # Compatibilidade com bancos V1/V2/V3.
    if not _has_column(db, "participants", "avatar_url"):
        db.execute("ALTER TABLE participants ADD COLUMN avatar_url TEXT DEFAULT ''")
    if not _has_column(db, "participants", "avatar_file"):
        db.execute("ALTER TABLE participants ADD COLUMN avatar_file TEXT DEFAULT ''")
    for column, default_url in AOM_IMAGE_DEFAULTS.items():
        if not _has_column(db, "tournament_settings", column):
            safe_default = default_url.replace("'", "''")
            db.execute(f"ALTER TABLE tournament_settings ADD COLUMN {column} TEXT NOT NULL DEFAULT '{safe_default}'")

    # Migração V4 -> V5: transforma modalidades fixas em instâncias reutilizáveis e adiciona MD3/histórico.
    for column, ddl in (
        ("mode_key", "TEXT NOT NULL DEFAULT 'custom'"),
        ("best_of", "INTEGER NOT NULL DEFAULT 1"),
        ("is_public", "INTEGER NOT NULL DEFAULT 1"),
        ("completed_at", "TEXT DEFAULT ''"),
    ):
        if not _has_column(db, "tournaments", column):
            db.execute(f"ALTER TABLE tournaments ADD COLUMN {column} {ddl}")

    legacy_modes = {
        "ffa": ("ffa", 1), "food-wood-gold": ("food_wood_gold", 1),
        "1v1": ("1v1_round_robin", 1), "2v2": ("2v2_elimination", 1),
        "md3-1v1": ("bo3_1v1", 3), "md3-2v2": ("bo3_2v2", 3), "md3-3v3": ("bo3_3v3", 3),
    }
    for slug, (mode_key, best_of) in legacy_modes.items():
        db.execute("UPDATE tournaments SET mode_key=?,best_of=? WHERE slug=? AND (mode_key='custom' OR mode_key='' OR mode_key IS NULL)", (mode_key,best_of,slug))

    # Em bancos V4 já existentes, schema.sql não reinsere os 3 MD3 por causa de colunas antigas; garantimos aqui.
    seed_rows = [
        ("ffa","FFA — Sem Regras","FFA","ffa","ffa",1,1,"O modo clássico do Chamas Flamejantes: todos contra todos, alianças e traições permitidas. Pode haver um ou vários vencedores.",300,"R$",12,"1v1","#e95d20",1),
        ("food-wood-gold","FOOD WOOD GOLD — 3x3","FOOD WOOD GOLD","food_wood_gold","elimination",3,1,"Equipes de 3: um jogador FOOD, um WOOD e um GOLD. Perdeu o confronto, está eliminado.",0,"R$",12,"team","#c89a42",2),
        ("1v1","1v1 — Todos Contra Todos","1v1","1v1_round_robin","round_robin",1,1,"Até 32 jogadores. Todos enfrentam todos uma vez; a classificação é calculada automaticamente por vitórias.",0,"R$",32,"1v1","#b54331",3),
        ("2v2","2x2 — Eliminação","2x2","2v2_elimination","elimination",2,1,"Duplas em mata-mata. Perdeu, está fora; os vencedores avançam até a grande final.",0,"R$",16,"team","#8c6a35",4),
        ("md3-1v1","Melhor de 3 — 1x1","MD3 1x1","bo3_1v1","elimination",1,3,"Mata-mata em séries Melhor de 3. O primeiro jogador a vencer 2 partidas avança.",0,"R$",32,"1v1","#a9442b",5),
        ("md3-2v2","Melhor de 3 — 2x2","MD3 2x2","bo3_2v2","elimination",2,3,"Duplas em mata-mata Melhor de 3. A primeira equipe a fazer 2 vitórias na série avança.",0,"R$",16,"team","#9f672f",6),
        ("md3-3v3","Melhor de 3 — 3x3","MD3 3x3","bo3_3v3","elimination",3,3,"Equipes de três em séries Melhor de 3. Venceu 2 jogos, avança; perdeu a série, está fora.",0,"R$",12,"team","#73553a",7),
    ]
    for row in seed_rows:
        db.execute("""INSERT OR IGNORE INTO tournaments
            (slug,name,short_name,mode_key,format_type,team_size,best_of,description,prize_total,currency,max_entries,elo_mode,accent,display_order)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

    db.execute("UPDATE tournaments SET completed_at=COALESCE(NULLIF(completed_at,''),updated_at) WHERE status='finalizado' AND (completed_at='' OR completed_at IS NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status,is_public,created_at)")
    db.execute("UPDATE tournament_settings SET title='Chamas Flamejantes' WHERE id=1 AND title='FFA UNDERLORD'")
    db.execute("UPDATE tournament_settings SET footer_text='Chamas Flamejantes • Age of Mythology: Retold' WHERE id=1 AND footer_text LIKE 'FFA UNDERLORD%'")
    db.execute("UPDATE tournament_settings SET hero_text='Escolha sua arena. Entre na guerra.' WHERE id=1 AND hero_text='12 jogadores. Um campo de batalha. Sem regras.'")
    db.execute("UPDATE tournament_settings SET description='Torneios abertos, séries MD3, equipes, mata-mata, liga e histórico completo em uma única plataforma.' WHERE id=1 AND (description LIKE 'Entre no FFA%' OR description LIKE 'FFA, equipes,%')")

    # Migra o FFA antigo UMA única vez para a nova estrutura, sem apagar nada.
    migrated = db.execute("SELECT value FROM site_meta WHERE key='legacy_ffa_migrated'").fetchone()
    if not migrated:
        legacy_site = db.execute("SELECT * FROM tournament_settings WHERE id=1").fetchone()
        ffa = db.execute("SELECT * FROM tournaments WHERE slug='ffa'").fetchone()
        if ffa and legacy_site:
            db.execute(
                """UPDATE tournaments SET prize_total=?, currency=?, max_entries=?, registration_open=?, status=?,
                   event_date=?, event_time=?, map_name=?, lobby_name=?, lobby_password=?, show_lobby_credentials=?,
                   notes=?, elo_mode=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    legacy_site["prize_total"], legacy_site["currency"], min(int(legacy_site["max_players"]), 12),
                    legacy_site["registration_open"], legacy_site["tournament_status"], legacy_site["event_date"],
                    legacy_site["event_time"], legacy_site["map_name"], legacy_site["lobby_name"],
                    legacy_site["lobby_password"], legacy_site["show_lobby_credentials"], legacy_site["notes"],
                    legacy_site["elo_mode"], ffa["id"]
                )
            )

            legacy_players = db.execute("SELECT * FROM participants ORDER BY registration_order").fetchall()
            old_to_entry = {}
            for p in legacy_players:
                db.execute(
                    """INSERT OR IGNORE INTO players
                    (nickname,discord,aomstats_url,aomstats_profile_id,elo_1v1,elo_team,elo_verified,avatar_url,avatar_file,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (p["nickname"], p["discord"], p["aomstats_url"], p["aomstats_profile_id"], p["elo_1v1"], p["elo_team"],
                     p["elo_verified"], p["avatar_url"] or "", p["avatar_file"] or "", p["created_at"], p["updated_at"])
                )
                player = db.execute("SELECT id FROM players WHERE aomstats_profile_id=?", (p["aomstats_profile_id"],)).fetchone()
                if player:
                    db.execute(
                        """INSERT OR IGNORE INTO tournament_entries
                        (tournament_id,player_id,status,registration_order,created_at,updated_at)
                        VALUES (?,?,?,?,?,?)""",
                        (ffa["id"], player["id"], p["status"], p["registration_order"], p["created_at"], p["updated_at"])
                    )
                    entry = db.execute("SELECT id FROM tournament_entries WHERE tournament_id=? AND player_id=?", (ffa["id"], player["id"])).fetchone()
                    if entry:
                        old_to_entry[p["id"]] = entry["id"]

            legacy_winners = db.execute("SELECT * FROM winners").fetchall()
            for w in legacy_winners:
                entry_id = old_to_entry.get(w["participant_id"])
                if entry_id:
                    db.execute(
                        "INSERT OR IGNORE INTO tournament_winners(tournament_id,entry_id,prize_share,label) VALUES (?,?,?,?)",
                        (ffa["id"], entry_id, w["prize_share"], w["label"])
                    )
        db.execute("INSERT OR REPLACE INTO site_meta(key,value) VALUES ('legacy_ffa_migrated','1')")

    db.commit()
    db.close()


def get_tournament(value):
    db = get_db()
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return db.execute("SELECT * FROM tournaments WHERE id=?", (int(value),)).fetchone()
    return db.execute("SELECT * FROM tournaments WHERE slug=?", (value,)).fetchone()


def get_public_tournament(slug):
    t = get_tournament(slug)
    if not t:
        abort(404)
    if not t["is_public"] and not session.get("admin_id"):
        abort(404)
    return t


def all_tournaments(public_only=False):
    sql = "SELECT * FROM tournaments"
    params = ()
    if public_only:
        sql += " WHERE is_public=1"
    sql += " ORDER BY CASE status WHEN 'inscricoes' THEN 0 WHEN 'andamento' THEN 1 ELSE 2 END, display_order, id DESC"
    return get_db().execute(sql, params).fetchall()


def tournaments_by_status(status, public_only=True):
    sql = "SELECT * FROM tournaments WHERE status=?"
    params = [status]
    if public_only:
        sql += " AND is_public=1"
    if status == "finalizado":
        sql += " ORDER BY COALESCE(NULLIF(completed_at,''),updated_at) DESC, id DESC"
    else:
        sql += " ORDER BY CASE WHEN event_date<>'' THEN event_date ELSE '9999-12-31' END, display_order, id DESC"
    return get_db().execute(sql, tuple(params)).fetchall()


def slugify(value):
    import unicodedata
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "torneio"
    return value[:60]


def unique_tournament_slug(name):
    db = get_db()
    base = slugify(name)
    slug = base
    i = 2
    while db.execute("SELECT 1 FROM tournaments WHERE slug=?", (slug,)).fetchone():
        slug = f"{base}-{i}"
        i += 1
    return slug


def enriched_tournament(t):
    d = {k: t[k] for k in t.keys()}
    d["filled"] = tournament_entry_count(t["id"])
    d["left"] = max(int(t["max_entries"]) - d["filled"], 0)
    d["progress"] = min((d["filled"] / max(int(t["max_entries"]), 1)) * 100, 100)
    d["winners"] = winners_for_tournament(t["id"])
    d["matches"] = get_db().execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=?", (t["id"],)).fetchone()["c"]
    d["matches_done"] = get_db().execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=? AND status IN ('finalizado','bye')", (t["id"],)).fetchone()["c"]
    return d


def tournament_entry_count(tournament_id, active_only=True):
    db = get_db()
    if active_only:
        row = db.execute("SELECT COUNT(*) c FROM tournament_entries WHERE tournament_id=? AND status IN ('inscrito','confirmado')", (tournament_id,)).fetchone()
    else:
        row = db.execute("SELECT COUNT(*) c FROM tournament_entries WHERE tournament_id=?", (tournament_id,)).fetchone()
    return int(row["c"])


def display_elo(player, tournament):
    if not player:
        return None
    try:
        return player["elo_team"] if tournament["elo_mode"] == "team" else player["elo_1v1"]
    except Exception:
        return None


app.jinja_env.globals["display_elo"] = display_elo


def elo_label(player, tournament):
    value = display_elo(player, tournament)
    try:
        return str(int(value)) if value is not None and int(value) > 0 else "SEM ELO"
    except Exception:
        return "SEM ELO"


app.jinja_env.globals["elo_label"] = elo_label


def community_level_text(player):
    try:
        return f"Nível {int(player['normal_level'] or 1)} • {player['normal_level_label'] or 'Novato'}"
    except Exception:
        return "Nível 1 • Novato"


app.jinja_env.globals["community_level_text"] = community_level_text



def _player_dict(row):
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


def get_team_members(team_id):
    rows = get_db().execute(
        """SELECT tm.slot_no,tm.role,p.* FROM team_members tm
           JOIN players p ON p.id=tm.player_id WHERE tm.team_id=? ORDER BY tm.slot_no""", (team_id,)
    ).fetchall()
    return [_player_dict(r) | {"slot_no": r["slot_no"], "role": r["role"]} for r in rows]


def get_entries(tournament_id, include_removed=False):
    db = get_db()
    where = "" if include_removed else "AND e.status <> 'removido'"
    rows = db.execute(
        f"""SELECT e.*, p.nickname,p.discord,p.aomstats_url,p.aomstats_profile_id,p.elo_1v1,p.elo_team,
                   p.elo_verified,p.avatar_url,p.avatar_file,p.quote,
                   t.name team_name,t.captain_discord
            FROM tournament_entries e
            LEFT JOIN players p ON p.id=e.player_id
            LEFT JOIN teams t ON t.id=e.team_id
            WHERE e.tournament_id=? {where}
            ORDER BY e.registration_order""", (tournament_id,)
    ).fetchall()
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d["display_name"] = r["team_name"] if r["team_id"] else r["nickname"]
        d["members"] = get_team_members(r["team_id"]) if r["team_id"] else []
        out.append(d)
    return out


def get_entry(entry_id):
    db = get_db()
    r = db.execute(
        """SELECT e.*, p.nickname,p.discord,p.aomstats_url,p.aomstats_profile_id,p.elo_1v1,p.elo_team,
                  p.elo_verified,p.avatar_url,p.avatar_file,p.quote,t.name team_name,t.captain_discord
           FROM tournament_entries e LEFT JOIN players p ON p.id=e.player_id
           LEFT JOIN teams t ON t.id=e.team_id WHERE e.id=?""", (entry_id,)
    ).fetchone()
    if not r:
        return None
    d = {k: r[k] for k in r.keys()}
    d["display_name"] = r["team_name"] if r["team_id"] else r["nickname"]
    d["members"] = get_team_members(r["team_id"]) if r["team_id"] else []
    return d


def entrants_by_ids(ids):
    return {i: get_entry(i) for i in ids if i}


def winners_for_tournament(tournament_id):
    rows = get_db().execute(
        "SELECT * FROM tournament_winners WHERE tournament_id=? ORDER BY id", (tournament_id,)
    ).fetchall()
    result = []
    for w in rows:
        e = get_entry(w["entry_id"])
        if e:
            result.append({"entry": e, "prize_share": w["prize_share"], "label": w["label"]})
    return result


def _next_registration_order(tournament_id):
    return get_db().execute(
        "SELECT COALESCE(MAX(registration_order),0)+1 n FROM tournament_entries WHERE tournament_id=?", (tournament_id,)
    ).fetchone()["n"]


def player_in_tournament(player_id, tournament_id):
    row = get_db().execute(
        """SELECT 1 FROM tournament_entries e
           LEFT JOIN team_members tm ON tm.team_id=e.team_id
           WHERE e.tournament_id=? AND (e.player_id=? OR tm.player_id=?) LIMIT 1""",
        (tournament_id, player_id, player_id)
    ).fetchone()
    return bool(row)


def _store_avatar_for_info(info, profile_id):
    avatar_url = (info or {}).get("avatar_url", "") or ""
    avatar_file = ""
    if avatar_url and not _is_steam_avatar_url(avatar_url):
        avatar_file = cache_remote_avatar(avatar_url, profile_id)
    return avatar_url, avatar_file


def upsert_public_player(raw_url, nickname, manual_elo, discord, tournament, upload=None, quote=''):
    """
    Cria/atualiza jogador via AoMStats.
    Se não houver Elo, o jogador continua válido como SEM ELO.
    Upload manual de foto, quando enviado, tem prioridade sobre Steam/AoMStats.
    """
    profile_url, profile_id = normalize_profile_url(raw_url)
    if not profile_url:
        raise ValueError("Informe um link válido do AoMStats (aomstats.io/profile/ID).")

    info = None
    try:
        info = fetch_aomstats(profile_url)
    except Exception:
        info = None

    nickname = (info.get("nickname") if info else "") or (nickname or "").strip()
    if not nickname:
        raise ValueError("Não consegui obter o Nick. Digite o Nick manualmente.")
    quote = (quote or "").strip()[:220]

    fetched_elo = None
    if info:
        fetched_elo = info.get("elo_team") if tournament["elo_mode"] == "team" else info.get("elo_1v1")

    elo = fetched_elo
    if elo is None and str(manual_elo or "").strip():
        try:
            elo = int(str(manual_elo).strip())
        except Exception:
            raise ValueError("O Elo informado é inválido.")
    if elo is not None and not 0 <= int(elo) <= 5000:
        raise ValueError("Elo inválido.")

    db = get_db()
    existing = db.execute(
        "SELECT * FROM players WHERE aomstats_profile_id=?",
        (profile_id,)
    ).fetchone()

    avatar_url = (info or {}).get("avatar_url", "") or ""
    new_manual_file = ""
    if upload and upload.filename:
        new_manual_file = save_uploaded_avatar(upload, profile_id)

    cached_file = ""
    if not new_manual_file and avatar_url and not _is_steam_avatar_url(avatar_url):
        cached_file = cache_remote_avatar(avatar_url, profile_id)

    elo_1v1 = (info or {}).get("elo_1v1")
    elo_team = (info or {}).get("elo_team")
    if tournament["elo_mode"] == "team" and elo_team is None and elo is not None:
        elo_team = int(elo)
    if tournament["elo_mode"] == "1v1" and elo_1v1 is None and elo is not None:
        elo_1v1 = int(elo)
    verified = 1 if fetched_elo is not None else 0

    stats_available = bool((info or {}).get("normal_stats_available"))
    stat_values = {
        "normal_wins": (info or {}).get("normal_wins", 0),
        "normal_losses": (info or {}).get("normal_losses", 0),
        "normal_games": (info or {}).get("normal_games", 0),
        "normal_win_rate": (info or {}).get("normal_win_rate", 0.0),
        "normal_level": (info or {}).get("normal_level", 1),
        "normal_level_label": (info or {}).get("normal_level_label", "Novato"),
        "normal_stats_available": 1 if stats_available else 0,
    }

    if existing:
        old_file = existing["avatar_file"] or ""
        final_file = old_file
        if new_manual_file:
            remove_local_avatar(old_file)
            final_file = new_manual_file
        elif not old_file and cached_file:
            final_file = cached_file

        final_remote = avatar_url or existing["avatar_url"] or ""

        # Se a consulta falhar, não apagamos Elo/estatísticas já conhecidas.
        db.execute(
            """UPDATE players SET
               nickname=?, discord=?, aomstats_url=?,
               elo_1v1=COALESCE(?,elo_1v1),
               elo_team=COALESCE(?,elo_team),
               elo_verified=MAX(elo_verified,?),
               avatar_url=?, avatar_file=?,
               quote=CASE WHEN ?<>'' THEN ? ELSE quote END,
               normal_wins=CASE WHEN ? THEN ? ELSE normal_wins END,
               normal_losses=CASE WHEN ? THEN ? ELSE normal_losses END,
               normal_games=CASE WHEN ? THEN ? ELSE normal_games END,
               normal_win_rate=CASE WHEN ? THEN ? ELSE normal_win_rate END,
               normal_level=CASE WHEN ? THEN ? ELSE normal_level END,
               normal_level_label=CASE WHEN ? THEN ? ELSE normal_level_label END,
               normal_stats_available=CASE WHEN ? THEN 1 ELSE normal_stats_available END,
               normal_stats_updated_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE normal_stats_updated_at END,
               updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                nickname[:80], (discord or existing["discord"] or "")[:80], profile_url,
                elo_1v1, elo_team, verified, final_remote, final_file,
                quote, quote,
                stats_available, stat_values["normal_wins"],
                stats_available, stat_values["normal_losses"],
                stats_available, stat_values["normal_games"],
                stats_available, stat_values["normal_win_rate"],
                stats_available, stat_values["normal_level"],
                stats_available, stat_values["normal_level_label"],
                stats_available, stats_available,
                existing["id"],
            )
        )
        db.commit()
        return existing["id"]

    db.execute(
        """INSERT INTO players
           (nickname,discord,aomstats_url,aomstats_profile_id,elo_1v1,elo_team,elo_verified,
            avatar_url,avatar_file,quote,normal_wins,normal_losses,normal_games,normal_win_rate,
            normal_level,normal_level_label,normal_stats_available,normal_stats_updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE '' END)""",
        (
            nickname[:80], (discord or "")[:80], profile_url, profile_id,
            elo_1v1, elo_team, verified, avatar_url, new_manual_file or cached_file, quote,
            stat_values["normal_wins"], stat_values["normal_losses"], stat_values["normal_games"],
            stat_values["normal_win_rate"], stat_values["normal_level"], stat_values["normal_level_label"],
            stat_values["normal_stats_available"], stats_available,
        )
    )
    db.commit()
    return db.execute(
        "SELECT id FROM players WHERE aomstats_profile_id=?",
        (profile_id,)
    ).fetchone()["id"]


def create_manual_player(nickname, elo, discord, aomstats_url, tournament, upload=None, direct_avatar=""):
    nickname = (nickname or "").strip()
    if not nickname:
        raise ValueError("Informe o Nick do jogador.")
    try:
        elo = int(elo)
    except Exception:
        raise ValueError("Informe um Elo válido.")
    if not 0 <= elo <= 5000:
        raise ValueError("Elo inválido.")

    profile_url = ""
    profile_id = f"manual-{secrets.token_hex(10)}"
    info = None
    if (aomstats_url or "").strip():
        profile_url, parsed_id = normalize_profile_url(aomstats_url)
        if not profile_url:
            raise ValueError("Link do AoMStats inválido. Deixe vazio para jogador sem perfil.")
        profile_id = parsed_id
        try:
            info = fetch_aomstats(profile_url)
        except Exception:
            info = None

    db = get_db()
    existing = db.execute("SELECT * FROM players WHERE aomstats_profile_id=?", (profile_id,)).fetchone()
    if info and info.get("nickname"):
        nickname = info["nickname"]
        fetched = info.get("elo_team") if tournament["elo_mode"] == "team" else info.get("elo_1v1")
        if fetched is not None:
            elo = int(fetched)

    avatar_url = (info or {}).get("avatar_url", "") or ""
    if direct_avatar:
        direct_avatar = _normalize_external_image_url(direct_avatar)
        if not _is_steam_avatar_url(direct_avatar):
            raise ValueError("A URL direta precisa ser uma imagem de avatars.steamstatic.com.")
        avatar_url = direct_avatar
    avatar_file = ""
    if upload and upload.filename:
        avatar_file = save_uploaded_avatar(upload, profile_id)
        avatar_url = ""
    elif avatar_url and not _is_steam_avatar_url(avatar_url):
        avatar_file = cache_remote_avatar(avatar_url, profile_id)

    elo_1v1 = (info or {}).get("elo_1v1")
    elo_team = (info or {}).get("elo_team")
    if tournament["elo_mode"] == "team" and elo_team is None:
        elo_team = elo
    if tournament["elo_mode"] == "1v1" and elo_1v1 is None:
        elo_1v1 = elo
    verified = 1 if info else 0

    if existing:
        db.execute(
            """UPDATE players SET nickname=?,discord=?,aomstats_url=?,elo_1v1=COALESCE(?,elo_1v1),elo_team=COALESCE(?,elo_team),
               elo_verified=MAX(elo_verified,?),avatar_url=CASE WHEN ?<>'' THEN ? ELSE avatar_url END,
               avatar_file=CASE WHEN ?<>'' THEN ? ELSE avatar_file END,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (nickname[:80], (discord or existing["discord"] or "")[:80], profile_url or existing["aomstats_url"], elo_1v1, elo_team,
             verified, avatar_url, avatar_url, avatar_file, avatar_file, existing["id"])
        )
        db.commit()
        return existing["id"]

    db.execute(
        """INSERT INTO players(nickname,discord,aomstats_url,aomstats_profile_id,elo_1v1,elo_team,elo_verified,avatar_url,avatar_file)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (nickname[:80], (discord or "")[:80], profile_url, profile_id, elo_1v1, elo_team, verified, avatar_url, avatar_file)
    )
    db.commit()
    return db.execute("SELECT id FROM players WHERE aomstats_profile_id=?", (profile_id,)).fetchone()["id"]


def round_robin_standings(tournament_id):
    tournament = get_tournament(tournament_id)
    entries = get_entries(tournament_id)
    active = [e for e in entries if e["status"] in ENTRY_ACTIVE_STATUSES]
    stats = {e["id"]: {"entry": e, "wins": 0, "losses": 0, "played": 0, "points": 0} for e in active}
    matches = get_db().execute(
        "SELECT * FROM matches WHERE tournament_id=? AND status='finalizado'", (tournament_id,)
    ).fetchall()
    for m in matches:
        a, b, w = m["entry_a_id"], m["entry_b_id"], m["winner_entry_id"]
        if a in stats and b in stats and w:
            stats[a]["played"] += 1
            stats[b]["played"] += 1
            if w == a:
                stats[a]["wins"] += 1; stats[a]["points"] += 1; stats[b]["losses"] += 1
            elif w == b:
                stats[b]["wins"] += 1; stats[b]["points"] += 1; stats[a]["losses"] += 1
    def elo_for(st):
        e = st["entry"]
        if e["player_id"]:
            return e["elo_team"] if tournament["elo_mode"] == "team" else e["elo_1v1"]
        return 0
    ordered = sorted(stats.values(), key=lambda s: (-s["wins"], s["losses"], -(elo_for(s) or 0), s["entry"]["registration_order"]))
    for idx, s in enumerate(ordered, 1):
        s["position"] = idx
    return ordered


def matches_grouped(tournament_id):
    rows = get_db().execute("SELECT * FROM matches WHERE tournament_id=? ORDER BY round_no,match_no", (tournament_id,)).fetchall()
    groups = {}
    ids = set()
    for r in rows:
        groups.setdefault(r["round_no"], []).append({k: r[k] for k in r.keys()})
        ids.update(x for x in (r["entry_a_id"], r["entry_b_id"], r["winner_entry_id"]) if x)
    entry_map = entrants_by_ids(ids)
    return groups, entry_map


def generate_round_robin(tournament_id):
    db = get_db()
    t = get_tournament(tournament_id)
    entries = [e for e in get_entries(tournament_id) if e["status"] in ENTRY_ACTIVE_STATUSES]
    if len(entries) < 2:
        raise ValueError("São necessários pelo menos 2 jogadores.")
    if len(entries) > int(t["max_entries"]):
        raise ValueError("Há mais inscritos do que o limite configurado.")
    db.execute("DELETE FROM matches WHERE tournament_id=?", (tournament_id,))
    db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
    ids = [e["id"] for e in entries]
    if len(ids) % 2:
        ids.append(None)
    n = len(ids)
    current = ids[:]
    for rnd in range(1, n):
        match_no = 1
        for i in range(n // 2):
            a, b = current[i], current[n - 1 - i]
            if a is not None and b is not None:
                db.execute(
                    "INSERT INTO matches(tournament_id,round_no,match_no,entry_a_id,entry_b_id) VALUES (?,?,?,?,?)",
                    (tournament_id, rnd, match_no, a, b)
                )
                match_no += 1
        current = [current[0]] + [current[-1]] + current[1:-1]
    db.execute("UPDATE tournaments SET matches_generated=1,status='andamento',registration_open=0,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,))
    db.commit()


def _create_elimination_round(db, tournament_id, round_no, entry_ids):
    match_no = 1
    for i in range(0, len(entry_ids), 2):
        a = entry_ids[i]
        b = entry_ids[i + 1] if i + 1 < len(entry_ids) else None
        if b is None:
            db.execute(
                """INSERT INTO matches(tournament_id,round_no,match_no,entry_a_id,entry_b_id,winner_entry_id,status)
                   VALUES (?,?,?,?,?,?, 'bye')""", (tournament_id, round_no, match_no, a, None, a)
            )
        else:
            db.execute(
                "INSERT INTO matches(tournament_id,round_no,match_no,entry_a_id,entry_b_id) VALUES (?,?,?,?,?)",
                (tournament_id, round_no, match_no, a, b)
            )
        match_no += 1


def generate_elimination(tournament_id):
    db = get_db()
    t = get_tournament(tournament_id)
    entries = [e for e in get_entries(tournament_id) if e["status"] in ENTRY_ACTIVE_STATUSES]
    if len(entries) < 2:
        raise ValueError("São necessárias pelo menos 2 equipes/jogadores.")
    db.execute("DELETE FROM matches WHERE tournament_id=?", (tournament_id,))
    db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
    _create_elimination_round(db, tournament_id, 1, [e["id"] for e in entries])
    db.execute("UPDATE tournaments SET matches_generated=1,status='andamento',registration_open=0,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,))
    db.commit()
    advance_elimination_if_ready(tournament_id)


def advance_elimination_if_ready(tournament_id):
    db = get_db()
    t = get_tournament(tournament_id)
    if not t or t["format_type"] != "elimination":
        return
    current_round = db.execute("SELECT MAX(round_no) r FROM matches WHERE tournament_id=?", (tournament_id,)).fetchone()["r"]
    if not current_round:
        return
    rows = db.execute("SELECT * FROM matches WHERE tournament_id=? AND round_no=? ORDER BY match_no", (tournament_id, current_round)).fetchall()
    if any(r["status"] not in ("finalizado", "bye") or not r["winner_entry_id"] for r in rows):
        return
    winners = [r["winner_entry_id"] for r in rows]
    if len(winners) == 1:
        winner = winners[0]
        db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
        db.execute("INSERT INTO tournament_winners(tournament_id,entry_id,prize_share,label) VALUES (?,?,?,'Campeão')", (tournament_id, winner, t["prize_total"]))
        db.execute("UPDATE tournaments SET status='finalizado',registration_open=0,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,))
        db.commit()
        return
    next_exists = db.execute("SELECT 1 FROM matches WHERE tournament_id=? AND round_no=? LIMIT 1", (tournament_id, current_round + 1)).fetchone()
    if not next_exists:
        _create_elimination_round(db, tournament_id, current_round + 1, winners)
        db.commit()
        advance_elimination_if_ready(tournament_id)


def finalize_round_robin_if_complete(tournament_id):
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=?", (tournament_id,)).fetchone()["c"]
    done = db.execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=? AND status='finalizado'", (tournament_id,)).fetchone()["c"]
    if total and total == done:
        standings = round_robin_standings(tournament_id)
        db.execute("UPDATE tournaments SET status='finalizado',completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,))
        if standings:
            top_wins = standings[0]["wins"]
            leaders = [s for s in standings if s["wins"] == top_wins]
            if len(leaders) == 1:
                t = get_tournament(tournament_id)
                db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
                db.execute("INSERT INTO tournament_winners(tournament_id,entry_id,prize_share,label) VALUES (?,?,?,'Campeão')", (tournament_id, leaders[0]["entry"]["id"], t["prize_total"]))
        db.commit()



# ============================================================
# V6 — PRÊMIOS LIVRES + PATROCINADORES + ELO DA COMUNIDADE
# ============================================================

def migrate_v6_db():
    """Atualiza bancos V5 sem apagar inscrições, partidas ou histórico."""
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    if not _has_column(db, "tournaments", "prize_name"):
        db.execute("ALTER TABLE tournaments ADD COLUMN prize_name TEXT NOT NULL DEFAULT ''")

    db.executescript("""
    CREATE TABLE IF NOT EXISTS sponsors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        website TEXT DEFAULT '',
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
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
    """)


    # V6.2 — patrocinadores também podem ser sincronizados pelo AoMStats.
    sponsor_cols = {
        "aomstats_url": "TEXT DEFAULT ''",
        "aomstats_profile_id": "TEXT DEFAULT ''",
        "avatar_url": "TEXT DEFAULT ''",
        "avatar_file": "TEXT DEFAULT ''",
    }
    for col, definition in sponsor_cols.items():
        if not _has_column(db, "sponsors", col):
            db.execute(f"ALTER TABLE sponsors ADD COLUMN {col} {definition}")
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_sponsors_aomstats_profile
           ON sponsors(aomstats_profile_id)
           WHERE aomstats_profile_id <> ''"""
    )


    # V7 — estatísticas de partidas normais Customs/Quickplay.
    player_v7_cols = {
        "normal_wins": "INTEGER NOT NULL DEFAULT 0",
        "normal_losses": "INTEGER NOT NULL DEFAULT 0",
        "normal_games": "INTEGER NOT NULL DEFAULT 0",
        "normal_win_rate": "REAL NOT NULL DEFAULT 0",
        "normal_level": "INTEGER NOT NULL DEFAULT 1",
        "normal_level_label": "TEXT NOT NULL DEFAULT 'Novato'",
        "normal_stats_available": "INTEGER NOT NULL DEFAULT 0",
        "normal_stats_updated_at": "TEXT DEFAULT ''",
    }
    for col, definition in player_v7_cols.items():
        if not _has_column(db, "players", col):
            db.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")

    # V7.5 — frase pessoal de cada jogador.
    if not _has_column(db, "players", "quote"):
        db.execute("ALTER TABLE players ADD COLUMN quote TEXT NOT NULL DEFAULT ''")

    # As 7 modalidades são MODELOS de criação, não 7 torneios automaticamente abertos.
    # Remove somente instâncias padrão totalmente vazias; nunca toca em torneios usados.
    default_slugs = ("ffa","food-wood-gold","1v1","2v2","md3-1v1","md3-2v2","md3-3v3")
    for slug in default_slugs:
        row = db.execute("SELECT id FROM tournaments WHERE slug=?", (slug,)).fetchone()
        if not row:
            continue
        tid = row["id"]
        entries = db.execute("SELECT COUNT(*) c FROM tournament_entries WHERE tournament_id=?", (tid,)).fetchone()["c"]
        matches = db.execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=?", (tid,)).fetchone()["c"]
        winners = db.execute("SELECT COUNT(*) c FROM tournament_winners WHERE tournament_id=?", (tid,)).fetchone()["c"]
        if entries == 0 and matches == 0 and winners == 0:
            db.execute("DELETE FROM tournaments WHERE id=?", (tid,))

    db.execute("INSERT OR REPLACE INTO site_meta(key,value) VALUES ('v6_migrated','1')")
    db.commit()
    db.close()


def prize_label(tournament):
    """Texto único para dinheiro, objeto ou ambos."""
    try:
        name = (tournament["prize_name"] or "").strip()
    except Exception:
        name = ""
    try:
        total = float(tournament["prize_total"] or 0)
        currency = tournament["currency"] or "R$"
    except Exception:
        total, currency = 0, "R$"
    money = ""
    if total > 0:
        money = f"{currency} {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if name and money:
        return f"{name} + {money}"
    return name or money or "A definir"


app.jinja_env.globals["prize_label"] = prize_label


def sponsors_list(active_only=True):
    sql = "SELECT * FROM sponsors"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY display_order,id"
    return get_db().execute(sql).fetchall()


def community_ranking():
    rows = get_db().execute(
        """SELECT
              cm.id community_member_id,
              CASE WHEN p.elo_1v1 IS NOT NULL AND p.elo_1v1>0 THEN p.elo_1v1 ELSE 0 END community_elo,
              cm.notes,
              p.id player_id,p.nickname,p.discord,p.aomstats_url,p.aomstats_profile_id,
              p.elo_1v1,p.elo_team,p.elo_verified,p.avatar_url,p.avatar_file,p.quote,
              p.normal_wins,p.normal_losses,p.normal_games,p.normal_win_rate,
              p.normal_level,p.normal_level_label,p.normal_stats_available,p.normal_stats_updated_at,
              CASE WHEN p.elo_1v1 IS NOT NULL AND p.elo_1v1>0 THEN 1 ELSE 0 END has_elo
           FROM community_members cm
           JOIN players p ON p.id=cm.player_id
           ORDER BY
              CASE WHEN p.elo_1v1 IS NOT NULL AND p.elo_1v1>0 THEN 0 ELSE 1 END ASC,
              CASE WHEN p.elo_1v1 IS NOT NULL AND p.elo_1v1>0 THEN p.elo_1v1 ELSE 0 END DESC,
              p.normal_level DESC,
              p.normal_win_rate DESC,
              p.normal_wins DESC,
              p.normal_losses ASC,
              LOWER(p.nickname), cm.id"""
    ).fetchall()
    return [{k:r[k] for k in r.keys()} for r in rows]




# =====================================================================
# V10.2 — MAPAS, GRUPOS OFICIAIS E DUELOS X1
# =====================================================================

MAP_CATEGORIES = ("FFA", "1x1", "2x2", "3x3", "Outro")
ALLOWED_MAP_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".xs", ".xml", ".rms", ".scenario",
    ".scx", ".json", ".txt", ".mod", ".cfg", ".dat"
}


def _safe_download_name(name: str):
    cleaned = re.sub(r"[^A-Za-z0-9_.() -]", "_", (name or "").strip())
    return cleaned[:180] or "mapa.zip"


def _random_storage_name(prefix: str, original_name: str, allowed_exts):
    ext = Path(original_name or "").suffix.lower()
    if ext not in allowed_exts:
        return None
    safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "_", prefix or "")[:50] or "file"
    return f"{safe_prefix}_{secrets.token_hex(6)}{ext}"


def save_map_image(file_storage, key: str):
    if not file_storage or not file_storage.filename:
        return ""
    filename = _random_storage_name(f"map_{key}", file_storage.filename, ALLOWED_IMAGE_EXTENSIONS)
    if not filename:
        raise ValueError("Imagem inválida. Use JPG, PNG ou WebP.")
    if file_storage.mimetype not in CONTENT_TYPE_EXTENSIONS:
        raise ValueError("A prévia precisa ser uma imagem JPG, PNG ou WebP.")
    MAP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    file_storage.save(MAP_IMAGES_DIR / filename)
    return filename


def save_map_file(file_storage, key: str):
    if not file_storage or not file_storage.filename:
        raise ValueError("Selecione o arquivo do mapa.")
    filename = _random_storage_name(f"map_{key}", file_storage.filename, ALLOWED_MAP_EXTENSIONS)
    if not filename:
        allowed = ", ".join(sorted(ALLOWED_MAP_EXTENSIONS))
        raise ValueError(f"Formato do mapa não permitido. Extensões aceitas: {allowed}")
    MAP_FILES_DIR.mkdir(parents=True, exist_ok=True)
    file_storage.save(MAP_FILES_DIR / filename)
    return filename


def remove_map_storage(filename: str, image=False):
    if not filename:
        return
    base = MAP_IMAGES_DIR if image else MAP_FILES_DIR
    target = (base / Path(filename).name).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        return
    if target.exists() and target.is_file():
        target.unlink(missing_ok=True)


def maps_list(active_only=True, limit=None):
    sql = "SELECT * FROM custom_maps"
    params = []
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY created_at DESC,id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return get_db().execute(sql, params).fetchall()


def official_links():
    row = get_db().execute("SELECT * FROM community_links WHERE id=1").fetchone()
    if row:
        return row
    get_db().execute("INSERT OR IGNORE INTO community_links(id) VALUES (1)")
    get_db().commit()
    return get_db().execute("SELECT * FROM community_links WHERE id=1").fetchone()


def valid_public_url(raw: str):
    value = (raw or "").strip()[:800]
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return value
    except Exception:
        pass
    return ""


def duel_open():
    return get_db().execute(
        """SELECT d.*,
                  p1.nickname player1_name,p1.avatar_url player1_avatar_url,p1.avatar_file player1_avatar_file,
                  p1.aomstats_url player1_aomstats,p1.quote player1_quote,
                  p2.nickname player2_name,p2.avatar_url player2_avatar_url,p2.avatar_file player2_avatar_file,
                  p2.aomstats_url player2_aomstats,p2.quote player2_quote
           FROM duels d
           JOIN players p1 ON p1.id=d.player1_id
           JOIN players p2 ON p2.id=d.player2_id
           WHERE d.status IN ('pending','active')
           ORDER BY d.id DESC LIMIT 1"""
    ).fetchone()


def duel_history(limit=50):
    return get_db().execute(
        """SELECT d.*,
                  p1.nickname player1_name,p1.avatar_url player1_avatar_url,p1.avatar_file player1_avatar_file,p1.aomstats_url player1_aomstats,
                  p2.nickname player2_name,p2.avatar_url player2_avatar_url,p2.avatar_file player2_avatar_file,p2.aomstats_url player2_aomstats,
                  pw.nickname winner_name
           FROM duels d
           JOIN players p1 ON p1.id=d.player1_id
           JOIN players p2 ON p2.id=d.player2_id
           LEFT JOIN players pw ON pw.id=d.winner_id
           WHERE d.status='finished'
           ORDER BY COALESCE(NULLIF(d.finished_at,''),d.requested_at) DESC,d.id DESC
           LIMIT ?""",
        (int(limit),)
    ).fetchall()


def duel_streak(player_id: int):
    rows = get_db().execute(
        """SELECT winner_id
           FROM duels
           WHERE status='finished' AND (player1_id=? OR player2_id=?)
           ORDER BY COALESCE(NULLIF(finished_at,''),requested_at) DESC,id DESC""",
        (player_id, player_id)
    ).fetchall()
    streak = 0
    for row in rows:
        if row["winner_id"] == player_id:
            streak += 1
        else:
            break
    return streak


def duel_stats_for_player(player_id: int):
    row = get_db().execute(
        """SELECT
              COUNT(*) total,
              SUM(CASE WHEN winner_id=? THEN 1 ELSE 0 END) wins,
              SUM(CASE WHEN winner_id IS NOT NULL AND winner_id<>? THEN 1 ELSE 0 END) losses
           FROM duels
           WHERE status='finished' AND (player1_id=? OR player2_id=?)""",
        (player_id, player_id, player_id, player_id)
    ).fetchone()
    wins = int(row["wins"] or 0)
    losses = int(row["losses"] or 0)
    total = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "total": total,
        "win_rate": round((wins / total * 100.0), 1) if total else 0.0,
        "streak": duel_streak(player_id),
    }


def duel_ranking():
    rows = get_db().execute(
        """SELECT p.*
           FROM players p
           WHERE EXISTS (
             SELECT 1 FROM duels d
             WHERE d.status='finished' AND (d.player1_id=p.id OR d.player2_id=p.id)
           )"""
    ).fetchall()
    ranking = []
    for p in rows:
        item = {k: p[k] for k in p.keys()}
        item.update(duel_stats_for_player(int(p["id"])))
        ranking.append(item)
    ranking.sort(
        key=lambda x: (
            -x["wins"],
            -x["win_rate"],
            -x["streak"],
            x["losses"],
            (x["nickname"] or "").lower(),
        )
    )
    for idx, item in enumerate(ranking, 1):
        item["rank"] = idx
        item["duel_title"] = "Mestre do X1" if idx == 1 else ""
    return ranking


def player_by_aomstats(raw_url: str):
    _normalized, profile_id = normalize_profile_url(raw_url)
    if not profile_id:
        return None
    return get_db().execute(
        "SELECT * FROM players WHERE aomstats_profile_id=?",
        (profile_id,)
    ).fetchone()


def duel_player_view(prefix: str, row):
    """Cria dict compatível com avatar_src a partir de aliases de uma query de duelo."""
    return {
        "avatar_url": row[f"{prefix}_avatar_url"] or "",
        "avatar_file": row[f"{prefix}_avatar_file"] or "",
    }


@app.context_processor
def inject_globals_v5():
    try:
        ranking = community_ranking()
        return {
            "site": settings(),
            "nav_tournaments": [t for t in all_tournaments(public_only=True) if t["status"] != "finalizado"][:10],
            "admin_logged": bool(session.get("admin_id")),
            "sponsors": sponsors_list(active_only=True),
            "community_members": ranking,
            "community_best": ranking[0] if ranking else None,
            "community_worst": ranking[-1] if ranking else None,
            "official_links": official_links(),
            "page_background_url": page_background_url(),
        }
    except Exception:
        return {}


@app.get("/")
def home():
    open_tournaments = [enriched_tournament(t) for t in tournaments_by_status("inscricoes")]
    open_tournaments = [t for t in open_tournaments if t["registration_open"] and t["left"] > 0]
    running_tournaments = [enriched_tournament(t) for t in tournaments_by_status("andamento")]
    history_tournaments = [enriched_tournament(t) for t in tournaments_by_status("finalizado")][:6]
    return render_template(
        "home.html",
        open_tournaments=open_tournaments,
        running_tournaments=running_tournaments,
        history_tournaments=history_tournaments,
        templates=TOURNAMENT_TEMPLATES,
        map_preview=maps_list(active_only=True, limit=3),
        duel_top=duel_ranking()[:3],
        current_duel=duel_open(),
    )


@app.get("/torneios")
def open_tournaments_page():
    open_tournaments = [enriched_tournament(t) for t in tournaments_by_status("inscricoes")]
    open_tournaments = [t for t in open_tournaments if t["registration_open"] and t["left"] > 0]
    running_tournaments = [enriched_tournament(t) for t in tournaments_by_status("andamento")]
    return render_template("open_tournaments.html", open_tournaments=open_tournaments, running_tournaments=running_tournaments)


@app.get("/historico")
def tournament_history():
    history_tournaments = [enriched_tournament(t) for t in tournaments_by_status("finalizado")]
    return render_template("history.html", tournaments=history_tournaments)


@app.get("/torneio/<slug>")
def tournament_page(slug):
    t = get_public_tournament(slug)
    entries = get_entries(t["id"])
    active = [e for e in entries if e["status"] in ENTRY_ACTIVE_STATUSES]
    winners = winners_for_tournament(t["id"])
    standings = round_robin_standings(t["id"]) if t["format_type"] == "round_robin" and t["matches_generated"] else []
    match_count = get_db().execute("SELECT COUNT(*) c FROM matches WHERE tournament_id=?", (t["id"],)).fetchone()["c"]
    return render_template("tournament.html", tournament=t, entries=active, winners=winners, standings=standings, match_count=match_count,
                           filled=len(active), spots_left=max(int(t["max_entries"]) - len(active), 0))


@app.route("/torneio/<slug>/inscricao", methods=["GET", "POST"])
def tournament_register(slug):
    t = get_public_tournament(slug)
    filled = tournament_entry_count(t["id"])
    if request.method == "POST":
        require_csrf()
        if not t["registration_open"]:
            flash("As inscrições desta modalidade estão fechadas.", "error")
            return redirect(url_for("tournament_page", slug=slug))
        if filled >= int(t["max_entries"]):
            flash("As vagas desta modalidade já foram preenchidas.", "error")
            return redirect(url_for("tournament_participants", slug=slug))

        db = get_db()
        try:
            if int(t["team_size"]) == 1:
                player_id = upsert_public_player(
                    request.form.get("aomstats_url", ""), request.form.get("nickname", ""),
                    request.form.get("elo", ""), request.form.get("discord", ""), t,
                    upload=request.files.get("avatar"),
                    quote=request.form.get("quote", "")
                )
                if player_in_tournament(player_id, t["id"]):
                    raise ValueError("Este jogador já está inscrito nesta modalidade.")
                db.execute(
                    "INSERT INTO tournament_entries(tournament_id,player_id,status,registration_order) VALUES (?,?,'inscrito',?)",
                    (t["id"], player_id, _next_registration_order(t["id"]))
                )
            else:
                team_name = request.form.get("team_name", "").strip()
                if not team_name:
                    raise ValueError("Informe o nome da equipe.")
                member_ids = []
                roles = ["FOOD", "WOOD", "GOLD"] if t["mode_key"] == "food_wood_gold" else [f"JOGADOR {i}" for i in range(1, int(t["team_size"]) + 1)]
                for i in range(1, int(t["team_size"]) + 1):
                    pid = upsert_public_player(
                        request.form.get(f"member_{i}_aomstats", ""), request.form.get(f"member_{i}_nickname", ""),
                        request.form.get(f"member_{i}_elo", ""), request.form.get("captain_discord", "" if i > 1 else request.form.get("captain_discord", "")), t,
                        upload=request.files.get(f"member_{i}_avatar"),
                        quote=request.form.get(f"member_{i}_quote", "")
                    )
                    if pid in member_ids:
                        raise ValueError("O mesmo jogador não pode ocupar duas vagas na mesma equipe.")
                    if player_in_tournament(pid, t["id"]):
                        raise ValueError("Um dos jogadores já está inscrito nesta modalidade.")
                    member_ids.append(pid)
                cur = db.execute("INSERT INTO teams(tournament_id,name,captain_discord) VALUES (?,?,?)", (t["id"], team_name[:100], request.form.get("captain_discord", "")[:80]))
                team_id = cur.lastrowid
                for idx, pid in enumerate(member_ids, 1):
                    db.execute("INSERT INTO team_members(team_id,player_id,slot_no,role) VALUES (?,?,?,?)", (team_id, pid, idx, roles[idx - 1]))
                db.execute(
                    "INSERT INTO tournament_entries(tournament_id,team_id,status,registration_order) VALUES (?,?,'inscrito',?)",
                    (t["id"], team_id, _next_registration_order(t["id"]))
                )
            db.commit()
            flash("Inscrição realizada! Sua vaga já aparece publicamente.", "success")
            return redirect(url_for("tournament_participants", slug=slug))
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Não foi possível concluir: jogador/equipe duplicado nesta modalidade.", "error")

    return render_template("register.html", tournament=t, filled=filled, spots_left=max(int(t["max_entries"]) - filled, 0))


@app.get("/torneio/<slug>/participantes")
def tournament_participants(slug):
    t = get_public_tournament(slug)
    entries = [e for e in get_entries(t["id"]) if e["status"] in ENTRY_ACTIVE_STATUSES]
    sort = request.args.get("sort", "order")
    if sort == "elo" and int(t["team_size"]) == 1:
        entries.sort(key=lambda e: -(e["elo_team"] if t["elo_mode"] == "team" else e["elo_1v1"] or 0))
    return render_template("participants.html", tournament=t, entries=entries, sort=sort,
                           filled=len(entries), spots_left=max(int(t["max_entries"]) - len(entries), 0))


@app.get("/torneio/<slug>/confrontos")
def tournament_matches(slug):
    t = get_public_tournament(slug)
    groups, entry_map = matches_grouped(t["id"])
    standings = round_robin_standings(t["id"]) if t["format_type"] == "round_robin" else []
    return render_template("matches.html", tournament=t, groups=groups, entry_map=entry_map, standings=standings)


@app.get("/torneio/<slug>/resultado")
def tournament_result(slug):
    t = get_public_tournament(slug)
    winners = winners_for_tournament(t["id"])
    standings = round_robin_standings(t["id"]) if t["format_type"] == "round_robin" and t["matches_generated"] else []
    return render_template("result.html", tournament=t, winners=winners, standings=standings)


# Rotas antigas continuam funcionando e apontam para o FFA.
@app.get("/inscricao")
def legacy_register():
    return redirect(url_for("tournament_register", slug="ffa"))

@app.get("/participantes")
def legacy_participants():
    return redirect(url_for("tournament_participants", slug="ffa"))

@app.get("/resultado")
def legacy_result():
    return redirect(url_for("tournament_result", slug="ffa"))




# =====================================================================
# V10.2 — PÁGINAS PÚBLICAS
# =====================================================================

@app.get("/mapas")
def maps_page():
    return render_template("maps.html", maps=maps_list(active_only=True))


@app.get("/mapas/imagem/<path:filename>")
def map_image(filename):
    return send_from_directory(MAP_IMAGES_DIR, Path(filename).name, max_age=86400)


@app.get("/mapas/<int:map_id>/baixar")
def map_download(map_id):
    db = get_db()
    item = db.execute("SELECT * FROM custom_maps WHERE id=? AND is_active=1", (map_id,)).fetchone()
    if not item:
        abort(404)
    target = MAP_FILES_DIR / Path(item["map_file"]).name
    if not target.exists():
        abort(404, "Arquivo do mapa não encontrado no servidor.")
    db.execute("UPDATE custom_maps SET downloads=downloads+1 WHERE id=?", (map_id,))
    db.commit()
    return send_file(
        target,
        as_attachment=True,
        download_name=_safe_download_name(item["original_filename"] or item["name"]),
    )


@app.get("/grupos")
def official_groups_page():
    return render_template("groups.html", links=official_links())


@app.get("/duelos")
def duels_page():
    ranking = duel_ranking()
    players = get_db().execute(
        """SELECT * FROM players
           WHERE aomstats_url<>''
           ORDER BY LOWER(nickname)"""
    ).fetchall()
    return render_template(
        "duels.html",
        current_duel=duel_open(),
        history=duel_history(30),
        ranking=ranking,
        players=players,
    )


@app.post("/duelos/solicitar")
def request_duel():
    require_csrf()
    if duel_open():
        flash("Já existe um duelo aguardando aprovação ou em curso. Aguarde ele terminar.", "error")
        return redirect(url_for("duels_page"))

    challenger = player_by_aomstats(request.form.get("challenger_aomstats", ""))
    opponent = player_by_aomstats(request.form.get("opponent_aomstats", ""))

    if not challenger:
        flash("O desafiante precisa já estar cadastrado no site com perfil AoMStats.", "error")
        return redirect(url_for("duels_page"))
    if not opponent:
        flash("O adversário precisa já estar cadastrado no site com perfil AoMStats.", "error")
        return redirect(url_for("duels_page"))
    if challenger["id"] == opponent["id"]:
        flash("Você não pode desafiar o próprio perfil.", "error")
        return redirect(url_for("duels_page"))

    db = get_db()
    db.execute(
        "INSERT INTO duels(player1_id,player2_id,status) VALUES (?,?,'pending')",
        (challenger["id"], opponent["id"])
    )
    db.commit()
    flash(
        f"Duelo solicitado: {challenger['nickname']} x {opponent['nickname']}. "
        "Agora o administrador precisa aprovar.",
        "success"
    )
    return redirect(url_for("duels_page"))


@app.route("/duelos/desafiar/<int:target_player_id>", methods=["GET", "POST"])
def challenge_player(target_player_id):
    target = get_db().execute("SELECT * FROM players WHERE id=?", (target_player_id,)).fetchone()
    if not target:
        abort(404)

    if request.method == "POST":
        require_csrf()
        if duel_open():
            flash("Já existe um duelo aguardando aprovação ou em curso.", "error")
            return redirect(url_for("duels_page"))

        challenger = player_by_aomstats(request.form.get("challenger_aomstats", ""))
        if not challenger:
            flash("Seu perfil precisa já estar cadastrado no site.", "error")
            return redirect(url_for("challenge_player", target_player_id=target_player_id))
        if challenger["id"] == target["id"]:
            flash("Você não pode desafiar a si mesmo.", "error")
            return redirect(url_for("challenge_player", target_player_id=target_player_id))

        get_db().execute(
            "INSERT INTO duels(player1_id,player2_id,status) VALUES (?,?,'pending')",
            (challenger["id"], target["id"])
        )
        get_db().commit()
        flash(f"Desafio enviado para {target['nickname']}. Aguarde a aprovação do admin.", "success")
        return redirect(url_for("duels_page"))

    return render_template(
        "challenge_player.html",
        target=target,
        current_duel=duel_open(),
    )


@app.get("/jogador/<int:player_id>")
def player_profile(player_id):
    player = get_db().execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        abort(404)
    recent = get_db().execute(
        """SELECT d.*,
                  p1.nickname player1_name,p2.nickname player2_name,pw.nickname winner_name
           FROM duels d
           JOIN players p1 ON p1.id=d.player1_id
           JOIN players p2 ON p2.id=d.player2_id
           LEFT JOIN players pw ON pw.id=d.winner_id
           WHERE d.status='finished' AND (d.player1_id=? OR d.player2_id=?)
           ORDER BY COALESCE(NULLIF(d.finished_at,''),d.requested_at) DESC,d.id DESC
           LIMIT 15""",
        (player_id, player_id)
    ).fetchall()
    return render_template(
        "player_profile.html",
        player=player,
        duel_stats=duel_stats_for_player(player_id),
        recent_duels=recent,
        current_duel=duel_open(),
    )


@app.get("/api/aomstats")
def api_aomstats():
    raw_url = request.args.get("url", "")
    profile_url, _ = normalize_profile_url(raw_url)
    if not profile_url:
        return jsonify({"ok": False, "error": "Link inválido do AoMStats."}), 400
    try:
        info = fetch_aomstats(profile_url)
        mode = request.args.get("mode", "1v1")
        selected = info["elo_team"] if mode == "team" else info["elo_1v1"]
        return jsonify({
            "ok": True,
            "nickname": info["nickname"],
            "elo": selected,
            "elo_label": str(selected) if selected is not None and int(selected)>0 else "SEM ELO",
            "elo_1v1": info["elo_1v1"],
            "elo_team": info["elo_team"],
            "avatar_url": info.get("avatar_url", ""),
            "mode": mode,
            "normal_wins": info.get("normal_wins", 0),
            "normal_losses": info.get("normal_losses", 0),
            "normal_games": info.get("normal_games", 0),
            "normal_win_rate": info.get("normal_win_rate", 0),
            "normal_level": info.get("normal_level", 1),
            "normal_level_label": info.get("normal_level_label", "Novato"),
            "normal_stats_available": info.get("normal_stats_available", 0),
        })
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Não consegui consultar o perfil agora. Você ainda pode preencher o Nick e enviar uma foto manual."
        }), 502


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if has_admin():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(username) < 3:
            flash("O usuário precisa ter pelo menos 3 caracteres.", "error")
        elif len(password) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "error")
        elif password != confirm:
            flash("As senhas não coincidem.", "error")
        else:
            db = get_db(); db.execute("INSERT INTO admins(username,password_hash) VALUES (?,?)", (username, generate_password_hash(password))); db.commit()
            flash("Administrador criado. Faça login.", "success")
            return redirect(url_for("admin_login"))
    return render_template("setup.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not has_admin():
        return redirect(url_for("setup"))
    if request.method == "POST":
        require_csrf()
        admin_row = get_db().execute("SELECT * FROM admins WHERE username=?", (request.form.get("username", "").strip(),)).fetchone()
        if admin_row and check_password_hash(admin_row["password_hash"], request.form.get("password", "")):
            session.clear(); session["admin_id"] = admin_row["id"]; session["admin_username"] = admin_row["username"]; csrf_token()
            return redirect(url_for("admin"))
        flash("Usuário ou senha incorretos.", "error")
    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/admin")
@admin_required
def admin():
    cards = [enriched_tournament(t) for t in all_tournaments(public_only=False)]
    player_count = get_db().execute("SELECT COUNT(*) c FROM players").fetchone()["c"]
    open_cards = [t for t in cards if t["status"] == "inscricoes"]
    running_cards = [t for t in cards if t["status"] == "andamento"]
    history_cards = [t for t in cards if t["status"] == "finalizado"]
    return render_template("admin.html", tournaments=cards, open_tournaments=open_cards, running_tournaments=running_cards,
                           history_tournaments=history_cards, player_count=player_count, templates=TOURNAMENT_TEMPLATES)


@app.post("/admin/torneios/criar")
@admin_required
def admin_create_tournament():
    require_csrf()
    mode_key = request.form.get("mode_key", "ffa")
    if mode_key not in TOURNAMENT_TEMPLATES:
        flash("Modalidade inválida.", "error")
        return redirect(url_for("admin"))
    template = tournament_template(mode_key)
    name = (request.form.get("name") or template["label"]).strip()[:120]
    short_name = (request.form.get("short_name") or template["short"]).strip()[:60]
    try:
        max_entries = int(request.form.get("max_entries") or template["max_entries"])
        max_entries = min(max(max_entries, 2), int(template["hard_limit"]))
        prize = max(float((request.form.get("prize_total") or "0").replace(",", ".")), 0)
    except Exception:
        flash("Limite de vagas ou prêmio inválido.", "error")
        return redirect(url_for("admin"))

    # Novo comportamento: criar NÃO significa abrir.
    open_now = 1 if request.form.get("registration_open") else 0
    public_now = 1 if open_now or request.form.get("is_public") else 0

    slug = unique_tournament_slug(name)
    db = get_db()
    cur = db.execute(
        """INSERT INTO tournaments
        (slug,name,short_name,mode_key,format_type,team_size,best_of,description,prize_total,prize_name,currency,max_entries,
         registration_open,status,is_public,event_date,event_time,map_name,notes,elo_mode,accent,display_order)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'inscricoes',?,?,?,?,?,?,?,?)""",
        (slug,name,short_name,mode_key,template["format_type"],template["team_size"],template["best_of"],
         (request.form.get("description") or template["description"])[:900],prize,
         (request.form.get("prize_name") or "")[:180],
         (request.form.get("currency") or "R$")[:10],max_entries,open_now,public_now,
         request.form.get("event_date", "")[:20],request.form.get("event_time", "")[:20],
         request.form.get("map_name", "A definir")[:120],request.form.get("notes", "")[:1400],
         template["elo_mode"],template["accent"],
         db.execute("SELECT COALESCE(MAX(display_order),0)+1 n FROM tournaments").fetchone()["n"])
    )
    db.commit()
    log_action("criar_torneio", f"{cur.lastrowid} / {name} / {mode_key}")
    if open_now:
        flash(f"Torneio '{name}' criado com inscrições abertas.", "success")
    else:
        flash(f"Torneio '{name}' criado fechado. Abra as inscrições quando estiver pronto.", "success")
    return redirect(url_for("admin_tournament", tournament_id=cur.lastrowid))


@app.post("/admin/torneio/<int:tournament_id>/delete")
@admin_required
def admin_delete_tournament(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    name = t["name"]
    get_db().execute("DELETE FROM tournaments WHERE id=?", (tournament_id,))
    get_db().commit()
    log_action("excluir_torneio", f"{tournament_id} / {name}")
    flash("Torneio excluído definitivamente.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/site-settings")
@admin_required
def admin_site_settings():
    require_csrf()
    db = get_db()
    accent = request.form.get("accent_color", "#e95d20")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", accent):
        accent = "#e95d20"
    bg = request.form.get("background_preset", "ember")
    if bg not in ("obsidian", "temple", "ocean", "ember"):
        bg = "ember"
    def image_url(name):
        v = request.form.get(name, "").strip()[:1000]
        try:
            u = urlparse(v)
            return v if u.scheme in ("http", "https") and u.netloc else AOM_IMAGE_DEFAULTS.get(name, "")
        except Exception:
            return AOM_IMAGE_DEFAULTS.get(name, "")
    db.execute(
        """UPDATE tournament_settings SET title=?,subtitle=?,hero_text=?,description=?,accent_color=?,background_preset=?,
           footer_text=?,hero_image_url=?,gallery_image_1=?,gallery_image_2=?,gallery_image_3=?,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
        (request.form.get("title", "Chamas Flamejantes")[:100], request.form.get("subtitle", "Age of Mythology: Retold")[:120],
         request.form.get("hero_text", "")[:220], request.form.get("description", "")[:800], accent, bg,
         request.form.get("footer_text", "")[:180], image_url("hero_image_url"), image_url("gallery_image_1"),
         image_url("gallery_image_2"), image_url("gallery_image_3"))
    )
    db.commit(); flash("Identidade do site atualizada.", "success")
    return redirect(url_for("admin"))


@app.get("/admin/torneio/<int:tournament_id>")
@admin_required
def admin_tournament(tournament_id):
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    entries = get_entries(tournament_id, include_removed=True)
    groups, entry_map = matches_grouped(tournament_id)
    standings = round_robin_standings(tournament_id) if t["format_type"] == "round_robin" else []
    winner_ids = {w["entry"]["id"] for w in winners_for_tournament(tournament_id)}
    hard_limit = tournament_hard_limit(t)
    return render_template("admin_tournament.html", tournament=t, entries=entries, groups=groups, entry_map=entry_map,
                           standings=standings, winner_ids=winner_ids, hard_limit=hard_limit)


@app.post("/admin/torneio/<int:tournament_id>/settings")
@admin_required
def admin_tournament_settings(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    hard = tournament_hard_limit(t)
    try:
        max_entries = min(max(int(request.form.get("max_entries", t["max_entries"])), 2), hard)
        prize = max(float(request.form.get("prize_total", t["prize_total"]).replace(",", ".")), 0)
    except Exception:
        flash("Limite ou prêmio inválido.", "error")
        return redirect(url_for("admin_tournament", tournament_id=tournament_id))
    status = request.form.get("status", t["status"])
    if status not in ("inscricoes", "andamento", "finalizado"):
        status = t["status"]
    registration_open = 1 if request.form.get("registration_open") else 0
    if status == "finalizado":
        registration_open = 0
    # Se o admin abrir inscrição, o torneio precisa ficar público para aparecer em Torneios Abertos.
    is_public = 1 if registration_open else (1 if request.form.get("is_public") else 0)
    db = get_db()
    db.execute(
        """UPDATE tournaments SET name=?,short_name=?,description=?,prize_total=?,prize_name=?,currency=?,max_entries=?,
           registration_open=?,status=?,is_public=?,event_date=?,event_time=?,map_name=?,lobby_name=?,lobby_password=?,
           show_lobby_credentials=?,notes=?,
           completed_at=CASE WHEN ?='finalizado' THEN COALESCE(NULLIF(completed_at,''),CURRENT_TIMESTAMP) ELSE '' END,
           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (request.form.get("name", t["name"])[:120], request.form.get("short_name", t["short_name"])[:60],
         request.form.get("description", t["description"])[:900], prize, request.form.get("prize_name","")[:180],
         request.form.get("currency", t["currency"])[:10], max_entries, registration_open, status, is_public,
         request.form.get("event_date", "")[:20], request.form.get("event_time", "")[:20],
         request.form.get("map_name", "")[:120], request.form.get("lobby_name", "")[:120],
         request.form.get("lobby_password", "")[:120], 1 if request.form.get("show_lobby_credentials") else 0,
         request.form.get("notes", "")[:1400], status, tournament_id)
    )
    db.commit()
    flash("Torneio atualizado.", "success")
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/torneio/<int:tournament_id>/entry/new")
@admin_required
def admin_entry_new(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)

    if tournament_entry_count(tournament_id) >= int(t["max_entries"]):
        flash("O limite de vagas já foi atingido.", "error")
        return redirect(url_for("admin_tournament", tournament_id=tournament_id))

    db = get_db()
    try:
        # ====================================================
        # INDIVIDUAL — FFA / 1x1 / MD3 1x1
        # O perfil AoMStats passa a ser obrigatório no cadastro
        # feito pelo administrador, igual à inscrição pública.
        # ====================================================
        if int(t["team_size"]) == 1:
            raw_url = (request.form.get("aomstats_url") or "").strip()
            if not raw_url:
                raise ValueError("Informe o perfil AoMStats do jogador.")

            pid = upsert_public_player(
                raw_url,
                request.form.get("nickname", ""),
                request.form.get("elo", ""),
                request.form.get("discord", ""),
                t,
                upload=request.files.get("avatar"),
                quote=request.form.get("quote", "")
            )

            if player_in_tournament(pid, tournament_id):
                raise ValueError("Esse jogador já está inscrito neste torneio.")

            status = request.form.get("status", "inscrito")
            if status not in ENTRY_STATUSES:
                status = "inscrito"

            db.execute(
                """INSERT INTO tournament_entries
                   (tournament_id,player_id,status,registration_order)
                   VALUES (?,?,?,?)""",
                (tournament_id, pid, status, _next_registration_order(tournament_id))
            )

        # ====================================================
        # EQUIPES — 2x2 / 3x3 / Food Wood Gold / MD3 equipes
        # Cada integrante usa o próprio perfil AoMStats.
        # ====================================================
        else:
            team_name = (request.form.get("team_name") or "").strip()
            if not team_name:
                raise ValueError("Informe o nome da equipe.")

            roles = (
                ["FOOD", "WOOD", "GOLD"]
                if t["mode_key"] == "food_wood_gold"
                else [f"JOGADOR {i}" for i in range(1, int(t["team_size"]) + 1)]
            )

            member_ids = []
            for i in range(1, int(t["team_size"]) + 1):
                raw_url = (request.form.get(f"member_{i}_aomstats") or "").strip()
                if not raw_url:
                    raise ValueError(f"Informe o perfil AoMStats do jogador {i}.")

                pid = upsert_public_player(
                    raw_url,
                    request.form.get(f"member_{i}_nickname", ""),
                    request.form.get(f"member_{i}_elo", ""),
                    request.form.get("captain_discord", ""),
                    t,
                    upload=request.files.get(f"member_{i}_avatar"),
                    quote=request.form.get(f"member_{i}_quote", "")
                )

                if pid in member_ids:
                    raise ValueError("A mesma pessoa foi adicionada mais de uma vez na equipe.")
                if player_in_tournament(pid, tournament_id):
                    raise ValueError("Um dos jogadores já está inscrito neste torneio.")

                member_ids.append(pid)

            cur = db.execute(
                "INSERT INTO teams(tournament_id,name,captain_discord) VALUES (?,?,?)",
                (
                    tournament_id,
                    team_name[:100],
                    (request.form.get("captain_discord") or "")[:80]
                )
            )
            team_id = cur.lastrowid

            for i, pid in enumerate(member_ids, 1):
                db.execute(
                    """INSERT INTO team_members(team_id,player_id,slot_no,role)
                       VALUES (?,?,?,?)""",
                    (team_id, pid, i, roles[i - 1])
                )

            status = request.form.get("status", "inscrito")
            if status not in ENTRY_STATUSES:
                status = "inscrito"

            db.execute(
                """INSERT INTO tournament_entries
                   (tournament_id,team_id,status,registration_order)
                   VALUES (?,?,?,?)""",
                (tournament_id, team_id, status, _next_registration_order(tournament_id))
            )

        db.commit()
        flash(
            "Inscrição adicionada pelo administrador. "
            "Nick, Elo e foto foram sincronizados pelo AoMStats/Steam.",
            "success"
        )

    except ValueError as exc:
        db.rollback()
        flash(str(exc), "error")
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Não foi possível adicionar: jogador ou equipe duplicada.", "error")

    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/entry/<int:entry_id>/status")
@admin_required
def admin_entry_status(entry_id):
    require_csrf()
    e = get_entry(entry_id)
    if not e:
        abort(404)
    status = request.form.get("status", "inscrito")
    if status not in ENTRY_STATUSES:
        status = "inscrito"
    get_db().execute("UPDATE tournament_entries SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, entry_id)); get_db().commit()
    flash("Status atualizado.", "success")
    return redirect(url_for("admin_tournament", tournament_id=e["tournament_id"]))


@app.post("/admin/team/<int:team_id>/edit")
@admin_required
def admin_team_edit(team_id):
    require_csrf()
    row = get_db().execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    if not row:
        abort(404)
    get_db().execute("UPDATE teams SET name=?,captain_discord=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (request.form.get("team_name", row["name"])[:100], request.form.get("captain_discord", row["captain_discord"])[:80], team_id)); get_db().commit()
    flash("Equipe atualizada.", "success")
    return redirect(url_for("admin_tournament", tournament_id=row["tournament_id"]))


@app.post("/admin/player/<int:player_id>/edit")
@admin_required
def admin_player_edit(player_id):
    require_csrf()
    db = get_db(); p = db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not p:
        abort(404)
    tournament_id = int(request.form.get("tournament_id", 0) or 0)
    t = get_tournament(tournament_id) if tournament_id else get_tournament("ffa")
    try:
        elo = int(request.form.get("elo", display_elo(p, t) or 0))
    except Exception:
        elo = display_elo(p, t) or 0
    avatar_url = p["avatar_url"] or ""; avatar_file = p["avatar_file"] or ""
    direct = request.form.get("avatar_url_direct", "").strip()
    if direct:
        direct = _normalize_external_image_url(direct)
        if not _is_steam_avatar_url(direct):
            flash("A URL direta da foto precisa ser de avatars.steamstatic.com.", "error")
            return redirect(url_for("admin_tournament", tournament_id=tournament_id))
        remove_local_avatar(avatar_file); avatar_file = ""; avatar_url = direct
    if request.form.get("remove_avatar"):
        remove_local_avatar(avatar_file); avatar_file = ""; avatar_url = ""
    upload = request.files.get("avatar")
    if upload and upload.filename:
        try:
            new_file = save_uploaded_avatar(upload, p["aomstats_profile_id"])
            remove_local_avatar(avatar_file); avatar_file = new_file; avatar_url = ""
        except ValueError as exc:
            flash(str(exc), "error"); return redirect(url_for("admin_tournament", tournament_id=tournament_id))
    elo_1v1 = elo if t["elo_mode"] == "1v1" else p["elo_1v1"]
    elo_team = elo if t["elo_mode"] == "team" else p["elo_team"]
    db.execute("""UPDATE players SET nickname=?,discord=?,elo_1v1=?,elo_team=?,avatar_url=?,avatar_file=?,quote=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
               (request.form.get("nickname", p["nickname"])[:80], request.form.get("discord", p["discord"])[:80], elo_1v1, elo_team, avatar_url, avatar_file,
                (request.form.get("quote", p["quote"] or "") or "")[:220], player_id)); db.commit()
    flash("Jogador atualizado.", "success")
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/player/<int:player_id>/refresh")
@admin_required
def admin_player_refresh(player_id):
    require_csrf()
    db = get_db()
    p = db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    tournament_id = int(request.form.get("tournament_id", 0) or 0)
    if not p or not p["aomstats_url"]:
        flash("Esse jogador não possui AoMStats cadastrado.", "error")
        return redirect(url_for("admin_tournament", tournament_id=tournament_id))
    try:
        info = fetch_aomstats(p["aomstats_url"])
        avatar_url = info.get("avatar_url", "") or p["avatar_url"] or ""
        avatar_file = p["avatar_file"] or ""
        # Se não há foto manual, podemos criar cache de uma foto remota não-Steam.
        if not avatar_file and avatar_url and not _is_steam_avatar_url(avatar_url):
            avatar_file = cache_remote_avatar(avatar_url, p["aomstats_profile_id"]) or ""

        db.execute(
            """UPDATE players SET nickname=?,elo_1v1=?,elo_team=?,
               elo_verified=?,avatar_url=?,avatar_file=?,
               normal_wins=?,normal_losses=?,normal_games=?,normal_win_rate=?,
               normal_level=?,normal_level_label=?,normal_stats_available=?,
               normal_stats_updated_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                info["nickname"], info.get("elo_1v1"), info.get("elo_team"),
                1 if (info.get("elo_1v1") is not None or info.get("elo_team") is not None) else p["elo_verified"],
                avatar_url, avatar_file,
                info.get("normal_wins",0), info.get("normal_losses",0), info.get("normal_games",0),
                info.get("normal_win_rate",0), info.get("normal_level",1),
                info.get("normal_level_label","Novato"), info.get("normal_stats_available",0),
                player_id
            )
        )
        db.commit()
        flash(f"{info['nickname']} atualizado: Elo + normais + nível + perfil.", "success")
    except Exception:
        flash("Não foi possível atualizar o perfil agora.", "error")
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/entry/<int:entry_id>/delete")
@admin_required
def admin_entry_delete(entry_id):
    require_csrf()
    e = get_entry(entry_id)
    if not e:
        abort(404)
    if get_db().execute("SELECT 1 FROM matches WHERE tournament_id=? LIMIT 1", (e["tournament_id"],)).fetchone():
        flash("Zere os confrontos antes de excluir inscrições, para não quebrar a chave.", "error")
        return redirect(url_for("admin_tournament", tournament_id=e["tournament_id"]))
    db = get_db()
    team_id = e["team_id"]
    db.execute("DELETE FROM tournament_entries WHERE id=?", (entry_id,))
    if team_id:
        db.execute("DELETE FROM teams WHERE id=?", (team_id,))
    db.commit(); flash("Inscrição removida.", "success")
    return redirect(url_for("admin_tournament", tournament_id=e["tournament_id"]))


@app.post("/admin/torneio/<int:tournament_id>/generate")
@admin_required
def admin_generate_matches(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    try:
        if t["format_type"] == "round_robin":
            generate_round_robin(tournament_id)
            flash("Tabela todos-contra-todos gerada. Todos enfrentarão todos uma vez.", "success")
        elif t["format_type"] == "elimination":
            generate_elimination(tournament_id)
            flash("Chave eliminatória gerada. Perdeu, está fora.", "success")
        else:
            flash("O FFA não usa chave automática; selecione os vencedores ao final.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/torneio/<int:tournament_id>/reset-matches")
@admin_required
def admin_reset_matches(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    db = get_db(); db.execute("DELETE FROM matches WHERE tournament_id=?", (tournament_id,)); db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
    db.execute("UPDATE tournaments SET matches_generated=0,status='inscricoes',registration_open=1,completed_at='',updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,)); db.commit()
    flash("Confrontos zerados e inscrições reabertas.", "success")
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/match/<int:match_id>/result")
@admin_required
def admin_match_result(match_id):
    require_csrf()
    db = get_db(); m = db.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    if not m:
        abort(404)
    t = get_tournament(m["tournament_id"])
    try:
        score_a = max(int(request.form.get("score_a", 0)), 0)
        score_b = max(int(request.form.get("score_b", 0)), 0)
    except Exception:
        score_a = score_b = 0

    winner = None
    if int(t["best_of"] or 1) == 3:
        # MD3: placares válidos são 2x0, 2x1, 0x2 ou 1x2. O sistema decide o vencedor pelo placar.
        if max(score_a, score_b) != 2 or min(score_a, score_b) not in (0, 1) or score_a == score_b:
            flash("No Melhor de 3, o vencedor precisa fazer 2 vitórias: 2x0 ou 2x1.", "error")
            return redirect(url_for("admin_tournament", tournament_id=t["id"]))
        winner = m["entry_a_id"] if score_a == 2 else m["entry_b_id"]
    else:
        try:
            winner = int(request.form.get("winner_entry_id", ""))
        except Exception:
            flash("Selecione o vencedor.", "error")
            return redirect(url_for("admin_tournament", tournament_id=t["id"]))
        if winner not in (m["entry_a_id"], m["entry_b_id"]):
            flash("Vencedor inválido para este confronto.", "error")
            return redirect(url_for("admin_tournament", tournament_id=t["id"]))

    db.execute("UPDATE matches SET winner_entry_id=?,score_a=?,score_b=?,status='finalizado',updated_at=CURRENT_TIMESTAMP WHERE id=?", (winner, score_a, score_b, match_id))
    db.commit()
    if t["format_type"] == "elimination":
        advance_elimination_if_ready(t["id"])
    elif t["format_type"] == "round_robin":
        finalize_round_robin_if_complete(t["id"])
    flash("Resultado da série registrado." if int(t["best_of"] or 1) == 3 else "Resultado registrado.", "success")
    return redirect(url_for("admin_tournament", tournament_id=t["id"]))


@app.post("/admin/torneio/<int:tournament_id>/winners")
@admin_required
def admin_select_winners(tournament_id):
    require_csrf()
    t = get_tournament(tournament_id)
    if not t:
        abort(404)
    ids = []
    for v in request.form.getlist("winner_ids"):
        try: ids.append(int(v))
        except Exception: pass
    db = get_db(); db.execute("DELETE FROM tournament_winners WHERE tournament_id=?", (tournament_id,))
    if ids:
        valid = [e for e in get_entries(tournament_id) if e["id"] in ids and e["status"] in ENTRY_ACTIVE_STATUSES]
        if valid:
            share = round(float(t["prize_total"]) / len(valid), 2) if valid else 0
            for e in valid:
                db.execute("INSERT INTO tournament_winners(tournament_id,entry_id,prize_share,label) VALUES (?,?,?,'Vencedor')", (tournament_id, e["id"], share))
            db.execute("UPDATE tournaments SET status='finalizado',registration_open=0,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,))
            flash(f"Resultado publicado: {len(valid)} vencedor(es).", "success")
    else:
        db.execute("UPDATE tournaments SET status='andamento',completed_at='',updated_at=CURRENT_TIMESTAMP WHERE id=?", (tournament_id,)); flash("Vencedores removidos.", "success")
    db.commit()
    return redirect(url_for("admin_tournament", tournament_id=tournament_id))


@app.post("/admin/avatars/refresh-all")
@admin_required
def admin_refresh_all_avatars():
    require_csrf()
    db = get_db()
    rows = db.execute("SELECT * FROM players WHERE aomstats_url<>''").fetchall()
    updated = failed = 0
    for p in rows:
        try:
            info = fetch_aomstats(p["aomstats_url"])
            avatar_url = info.get("avatar_url", "") or p["avatar_url"] or ""
            avatar_file = p["avatar_file"] or ""
            if not avatar_file and avatar_url and not _is_steam_avatar_url(avatar_url):
                avatar_file = cache_remote_avatar(avatar_url, p["aomstats_profile_id"]) or ""
            db.execute(
                """UPDATE players SET nickname=?,elo_1v1=?,elo_team=?,
                   elo_verified=?,avatar_url=?,avatar_file=?,
                   normal_wins=?,normal_losses=?,normal_games=?,normal_win_rate=?,
                   normal_level=?,normal_level_label=?,normal_stats_available=?,
                   normal_stats_updated_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    info["nickname"],info.get("elo_1v1"),info.get("elo_team"),
                    1 if (info.get("elo_1v1") is not None or info.get("elo_team") is not None) else p["elo_verified"],
                    avatar_url,avatar_file,
                    info.get("normal_wins",0),info.get("normal_losses",0),info.get("normal_games",0),
                    info.get("normal_win_rate",0),info.get("normal_level",1),
                    info.get("normal_level_label","Novato"),info.get("normal_stats_available",0),
                    p["id"]
                )
            )
            updated += 1
        except Exception:
            failed += 1
    db.commit()
    flash(
        f"Perfis atualizados: {updated}. Falhas: {failed}. Elo, partidas normais e nível sincronizados.",
        "success" if updated else "error"
    )
    return redirect(url_for("admin"))


@app.get("/admin/torneio/<int:tournament_id>/export.csv")
@admin_required
def admin_export(tournament_id):
    t=get_tournament(tournament_id)
    if not t: abort(404)
    entries=get_entries(tournament_id,include_removed=True); output=io.StringIO(); writer=csv.writer(output,delimiter=";")
    writer.writerow(["Ordem","Entrada/Equipe","Status","Jogador","Função","Discord","AoMStats","Elo"])
    for e in entries:
        if e["player_id"]:
            writer.writerow([e["registration_order"],e["display_name"],e["status"],e["nickname"],"",e["discord"],e["aomstats_url"],display_elo(e,t)])
        else:
            for m in e["members"]:
                writer.writerow([e["registration_order"],e["display_name"],e["status"],m["nickname"],m["role"],m["discord"],m["aomstats_url"],display_elo(m,t)])
    data=io.BytesIO(output.getvalue().encode("utf-8-sig"));data.seek(0)
    return send_file(data,as_attachment=True,download_name=f"{t['slug']}_chamas_flamejantes.csv",mimetype="text/csv")




@app.get("/comunidade")
def community_page():
    ranking = community_ranking()
    return render_template(
        "community.html",
        ranking=ranking,
        best=ranking[0] if ranking else None,
        worst=ranking[-1] if ranking else None
    )




@app.post("/admin/change-password")
@admin_required
def admin_change_password():
    require_csrf()
    db = get_db()
    admin_row = db.execute(
        "SELECT * FROM admins WHERE id=?",
        (session["admin_id"],)
    ).fetchone()

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not admin_row or not check_password_hash(admin_row["password_hash"], old_password):
        flash("Senha atual incorreta.", "error")
    elif len(new_password) < 8:
        flash("A nova senha deve ter pelo menos 8 caracteres.", "error")
    elif new_password != confirm_password:
        flash("As novas senhas não coincidem.", "error")
    else:
        db.execute(
            """UPDATE admins
               SET password_hash=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                generate_password_hash(new_password),
                admin_row["id"]
            )
        )
        db.commit()
        flash("Senha alterada com sucesso.", "success")

    return redirect(url_for("admin"))


@app.post("/admin/patrocinadores/adicionar")
@admin_required
def admin_sponsor_add():
    require_csrf()

    raw_url = (request.form.get("aomstats_url") or "").strip()
    if not raw_url:
        flash("Informe o perfil do AoMStats do patrocinador.", "error")
        return redirect(url_for("admin"))

    profile_url, profile_id = normalize_profile_url(raw_url)
    if not profile_url:
        flash("Link do AoMStats inválido.", "error")
        return redirect(url_for("admin"))

    website = (request.form.get("website") or "").strip()
    if website and not re.match(r"^https?://", website, re.I):
        website = "https://" + website

    try:
        info = fetch_aomstats(profile_url)
        nickname = (info.get("nickname") or request.form.get("name") or "").strip()
        avatar_url = _normalize_external_image_url(info.get("avatar_url", ""))
        if not nickname:
            raise ValueError("Não consegui identificar o nome do patrocinador.")

        upload = request.files.get("avatar")
        manual_file = save_uploaded_avatar(upload, f"sponsor_{profile_id}") if upload and upload.filename else ""
        cached_file = ""
        if not manual_file and avatar_url and not _is_steam_avatar_url(avatar_url):
            cached_file = cache_remote_avatar(avatar_url, profile_id)

        db = get_db()
        existing = db.execute(
            "SELECT * FROM sponsors WHERE aomstats_profile_id=?",
            (profile_id,)
        ).fetchone()

        if existing:
            old_file = existing["avatar_file"] or ""
            final_file = old_file
            if manual_file:
                remove_local_avatar(old_file)
                final_file = manual_file
            elif not old_file and cached_file:
                final_file = cached_file
            db.execute(
                """UPDATE sponsors SET name=?,website=?,aomstats_url=?,avatar_url=?,
                   avatar_file=?,is_active=1,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    nickname[:120], website[:500], profile_url,
                    avatar_url or existing["avatar_url"] or "",
                    final_file, existing["id"]
                )
            )
            action = "atualizado"
        else:
            order_no = db.execute(
                "SELECT COALESCE(MAX(display_order),0)+1 n FROM sponsors"
            ).fetchone()["n"]
            db.execute(
                """INSERT INTO sponsors
                   (name,website,aomstats_url,aomstats_profile_id,avatar_url,avatar_file,
                    display_order,is_active)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (
                    nickname[:120], website[:500], profile_url, profile_id,
                    avatar_url, manual_file or cached_file, order_no
                )
            )
            action = "adicionado"

        db.commit()
        flash(
            f"Patrocinador {nickname} {action}. Se uma foto manual foi enviada, ela terá prioridade.",
            "success"
        )
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        flash("Não consegui consultar esse patrocinador no AoMStats agora.", "error")

    return redirect(url_for("admin"))


@app.post("/admin/patrocinadores/<int:sponsor_id>/atualizar")
@admin_required
def admin_sponsor_refresh(sponsor_id):
    require_csrf()
    db = get_db()
    sponsor = db.execute("SELECT * FROM sponsors WHERE id=?", (sponsor_id,)).fetchone()
    if not sponsor:
        abort(404)
    if not sponsor["aomstats_url"]:
        flash("Esse patrocinador não possui perfil AoMStats cadastrado.", "error")
        return redirect(url_for("admin"))

    try:
        info = fetch_aomstats(sponsor["aomstats_url"])
        nickname = (info.get("nickname") or sponsor["name"]).strip()
        avatar_url = _normalize_external_image_url(info.get("avatar_url", ""))
        old_file = sponsor["avatar_file"] or ""
        avatar_file = old_file
        # Foto manual existente não é apagada por uma sincronização.
        if not old_file and avatar_url and not _is_steam_avatar_url(avatar_url):
            avatar_file = cache_remote_avatar(
                avatar_url,
                sponsor["aomstats_profile_id"] or str(sponsor_id)
            ) or old_file

        db.execute(
            """UPDATE sponsors SET
               name=?, avatar_url=?, avatar_file=?,
               updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (nickname[:120], avatar_url, avatar_file, sponsor_id)
        )
        db.commit()
        flash(f"Patrocinador {nickname} sincronizado novamente pelo AoMStats.", "success")
    except Exception:
        flash("Não foi possível atualizar esse patrocinador agora.", "error")

    return redirect(url_for("admin"))


@app.post("/admin/patrocinadores/<int:sponsor_id>/remover")
@admin_required
def admin_sponsor_remove(sponsor_id):
    require_csrf()
    db = get_db()
    db.execute("DELETE FROM sponsors WHERE id=?", (sponsor_id,))
    db.commit()
    flash("Patrocinador removido.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/comunidade/adicionar")
@admin_required
def admin_community_add():
    require_csrf()
    fake_tournament = {"elo_mode": "1v1"}
    try:
        raw_url = (request.form.get("aomstats_url") or "").strip()
        if not raw_url:
            raise ValueError("Informe o perfil do AoMStats do jogador.")

        player_id = upsert_public_player(
            raw_url,
            request.form.get("nickname", ""),
            request.form.get("elo", ""),
            request.form.get("discord", ""),
            fake_tournament,
            upload=request.files.get("avatar"),
            quote=request.form.get("quote", "")
        )

        db = get_db()
        player = db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
        if not player:
            raise ValueError("Não foi possível localizar o jogador.")

        # Elo oficial do AoMStats; se não existir, 0 significa SEM ELO.
        community_elo = int(player["elo_1v1"] or 0)

        db.execute(
            """INSERT INTO community_members(player_id,community_elo,notes)
               VALUES (?,?,?)
               ON CONFLICT(player_id) DO UPDATE SET
                   community_elo=excluded.community_elo,
                   notes=excluded.notes,
                   updated_at=CURRENT_TIMESTAMP""",
            (player_id, community_elo, (request.form.get("notes") or "")[:500])
        )
        db.commit()

        elo_text = f"{community_elo} de Elo" if community_elo > 0 else "SEM ELO"
        normal_text = (
            f"{player['normal_wins']}V/{player['normal_losses']}D • "
            f"Nível {player['normal_level']} ({player['normal_level_label']})"
            if player["normal_stats_available"]
            else "partidas normais ainda não disponíveis"
        )
        flash(
            f"{player['nickname']} cadastrado: {elo_text}. Normais: {normal_text}.",
            "success"
        )
    except (ValueError, sqlite3.IntegrityError) as exc:
        flash(str(exc) if str(exc) else "Não foi possível cadastrar pelo AoMStats.", "error")
    return redirect(url_for("admin"))




@app.post("/admin/comunidade/<int:member_id>/perfil")
@admin_required
def admin_community_profile_edit(member_id):
    require_csrf()
    db = get_db()
    row = db.execute(
        """SELECT cm.id community_member_id,p.*
           FROM community_members cm
           JOIN players p ON p.id=cm.player_id
           WHERE cm.id=?""",
        (member_id,)
    ).fetchone()
    if not row:
        abort(404)

    quote = (request.form.get("quote") or "").strip()[:220]
    avatar_file = row["avatar_file"] or ""

    if request.form.get("use_aom_avatar"):
        remove_local_avatar(avatar_file)
        avatar_file = ""

    upload = request.files.get("avatar")
    if upload and upload.filename:
        try:
            new_file = save_uploaded_avatar(upload, row["aomstats_profile_id"])
            remove_local_avatar(avatar_file)
            avatar_file = new_file
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin"))

    db.execute(
        """UPDATE players
           SET quote=?,avatar_file=?,updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (quote, avatar_file, row["player_id"])
    )
    db.commit()
    flash(f"Foto e frase de {row['nickname']} atualizadas.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/comunidade/<int:member_id>/atualizar")
@admin_required
def admin_community_refresh(member_id):
    require_csrf()
    db = get_db()
    row = db.execute(
        """SELECT cm.id community_member_id,p.*
           FROM community_members cm JOIN players p ON p.id=cm.player_id
           WHERE cm.id=?""",
        (member_id,)
    ).fetchone()
    if not row or not row["aomstats_url"]:
        flash("Participante da comunidade sem AoMStats válido.", "error")
        return redirect(url_for("admin"))

    try:
        info = fetch_aomstats(row["aomstats_url"])
        remote = info.get("avatar_url", "") or row["avatar_url"] or ""
        # Foto manual existente é preservada.
        local = row["avatar_file"] or ""
        cached = ""
        if not local and remote and not _is_steam_avatar_url(remote):
            cached = cache_remote_avatar(remote, row["aomstats_profile_id"])
        local = local or cached

        db.execute(
            """UPDATE players SET nickname=?,elo_1v1=?,elo_team=?,elo_verified=?,
               avatar_url=?,avatar_file=?,
               normal_wins=?,normal_losses=?,normal_games=?,normal_win_rate=?,
               normal_level=?,normal_level_label=?,normal_stats_available=?,
               normal_stats_updated_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                info["nickname"], info.get("elo_1v1"), info.get("elo_team"),
                1 if info.get("elo_1v1") is not None else row["elo_verified"],
                remote, local,
                info.get("normal_wins",0), info.get("normal_losses",0), info.get("normal_games",0),
                info.get("normal_win_rate",0), info.get("normal_level",1),
                info.get("normal_level_label","Novato"), info.get("normal_stats_available",0),
                row["player_id"],
            )
        )
        db.execute(
            "UPDATE community_members SET community_elo=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(info.get("elo_1v1") or 0), member_id)
        )
        db.commit()
        flash("Elo, partidas normais, nível e perfil atualizados pelo AoMStats.", "success")
    except Exception:
        flash("Não foi possível atualizar o AoMStats agora.", "error")
    return redirect(url_for("admin"))


@app.post("/admin/comunidade/<int:member_id>/elo")
@admin_required
def admin_community_elo(member_id):
    require_csrf()
    try:
        elo = int(request.form.get("elo", 0))
        if not 0 <= elo <= 5000:
            raise ValueError
    except Exception:
        flash("Elo inválido.", "error")
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("UPDATE community_members SET community_elo=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (elo, member_id))
    db.commit()
    flash("Elo da comunidade atualizado.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/comunidade/<int:member_id>/remover")
@admin_required
def admin_community_remove(member_id):
    require_csrf()
    db = get_db()
    db.execute("DELETE FROM community_members WHERE id=?", (member_id,))
    db.commit()
    flash("Participante removido do ranking da comunidade.", "success")
    return redirect(url_for("admin"))




# =====================================================================
# V10.2 — ADMIN MAPAS / DUELOS / GRUPOS OFICIAIS
# =====================================================================

@app.get("/admin/mapas")
@admin_required
def admin_maps():
    return render_template("admin_maps.html", maps=maps_list(active_only=False), categories=MAP_CATEGORIES)


@app.post("/admin/mapas/adicionar")
@admin_required
def admin_map_add():
    require_csrf()
    name = (request.form.get("name") or "").strip()[:120]
    creator = (request.form.get("creator") or "").strip()[:100]
    category = (request.form.get("category") or "Outro").strip()
    description = (request.form.get("description") or "").strip()[:1200]
    if not name:
        flash("Informe o nome do mapa.", "error")
        return redirect(url_for("admin_maps"))
    if category not in MAP_CATEGORIES:
        category = "Outro"

    map_upload = request.files.get("map_file")
    image_upload = request.files.get("image_file")
    storage_key = secrets.token_hex(5)

    try:
        map_filename = save_map_file(map_upload, storage_key)
        image_filename = save_map_image(image_upload, storage_key) if image_upload and image_upload.filename else ""
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin_maps"))

    db = get_db()
    try:
        db.execute(
            """INSERT INTO custom_maps
               (name,creator,category,description,image_file,map_file,original_filename,is_active)
               VALUES (?,?,?,?,?,?,?,1)""",
            (
                name, creator, category, description, image_filename, map_filename,
                (map_upload.filename or name)[:180]
            )
        )
        db.commit()
    except Exception:
        remove_map_storage(map_filename, image=False)
        remove_map_storage(image_filename, image=True)
        raise

    flash(f"Mapa '{name}' publicado.", "success")
    return redirect(url_for("admin_maps"))


@app.post("/admin/mapas/<int:map_id>/editar")
@admin_required
def admin_map_edit(map_id):
    require_csrf()
    db = get_db()
    item = db.execute("SELECT * FROM custom_maps WHERE id=?", (map_id,)).fetchone()
    if not item:
        abort(404)
    category = (request.form.get("category") or item["category"]).strip()
    if category not in MAP_CATEGORIES:
        category = "Outro"

    image_file = item["image_file"] or ""
    new_image = request.files.get("image_file")
    if new_image and new_image.filename:
        try:
            replacement = save_map_image(new_image, str(map_id))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_maps"))
        remove_map_storage(image_file, image=True)
        image_file = replacement

    db.execute(
        """UPDATE custom_maps SET
           name=?,creator=?,category=?,description=?,image_file=?,is_active=?,
           updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (
            (request.form.get("name") or item["name"])[:120],
            (request.form.get("creator") or "")[:100],
            category,
            (request.form.get("description") or "")[:1200],
            image_file,
            1 if request.form.get("is_active") else 0,
            map_id,
        )
    )
    db.commit()
    flash("Mapa atualizado.", "success")
    return redirect(url_for("admin_maps"))


@app.post("/admin/mapas/<int:map_id>/excluir")
@admin_required
def admin_map_delete(map_id):
    require_csrf()
    db = get_db()
    item = db.execute("SELECT * FROM custom_maps WHERE id=?", (map_id,)).fetchone()
    if not item:
        abort(404)
    remove_map_storage(item["map_file"], image=False)
    remove_map_storage(item["image_file"], image=True)
    db.execute("DELETE FROM custom_maps WHERE id=?", (map_id,))
    db.commit()
    flash("Mapa excluído.", "success")
    return redirect(url_for("admin_maps"))


@app.post("/admin/grupos")
@admin_required
def admin_groups_update():
    require_csrf()
    db = get_db()
    db.execute(
        """INSERT INTO community_links(id,whatsapp,discord,telegram,updated_at)
           VALUES (1,?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(id) DO UPDATE SET
             whatsapp=excluded.whatsapp,
             discord=excluded.discord,
             telegram=excluded.telegram,
             updated_at=CURRENT_TIMESTAMP""",
        (
            valid_public_url(request.form.get("whatsapp", "")),
            valid_public_url(request.form.get("discord", "")),
            valid_public_url(request.form.get("telegram", "")),
        )
    )
    db.commit()
    flash("Links oficiais atualizados.", "success")
    return redirect(url_for("admin"))


@app.get("/admin/duelos")
@admin_required
def admin_duels():
    all_rows = get_db().execute(
        """SELECT d.*,
                  p1.nickname player1_name,p1.avatar_url player1_avatar_url,p1.avatar_file player1_avatar_file,p1.aomstats_url player1_aomstats,
                  p2.nickname player2_name,p2.avatar_url player2_avatar_url,p2.avatar_file player2_avatar_file,p2.aomstats_url player2_aomstats,
                  pw.nickname winner_name
           FROM duels d
           JOIN players p1 ON p1.id=d.player1_id
           JOIN players p2 ON p2.id=d.player2_id
           LEFT JOIN players pw ON pw.id=d.winner_id
           ORDER BY CASE d.status WHEN 'pending' THEN 0 WHEN 'active' THEN 1 WHEN 'finished' THEN 2 ELSE 3 END,
                    d.id DESC"""
    ).fetchall()
    return render_template("admin_duels.html", duels=all_rows, ranking=duel_ranking())


@app.post("/admin/duelos/<int:duel_id>/aceitar")
@admin_required
def admin_duel_accept(duel_id):
    require_csrf()
    db = get_db()
    duel = db.execute("SELECT * FROM duels WHERE id=?", (duel_id,)).fetchone()
    if not duel:
        abort(404)
    if duel["status"] != "pending":
        flash("Esse duelo não está aguardando aprovação.", "error")
        return redirect(url_for("admin_duels"))

    other = db.execute(
        "SELECT id FROM duels WHERE status='active' AND id<>? LIMIT 1",
        (duel_id,)
    ).fetchone()
    if other:
        flash("Já existe outro duelo em curso.", "error")
        return redirect(url_for("admin_duels"))

    db.execute(
        "UPDATE duels SET status='active',accepted_at=CURRENT_TIMESTAMP WHERE id=?",
        (duel_id,)
    )
    db.commit()
    flash("Duelo aprovado. Agora está EM CURSO.", "success")
    return redirect(url_for("admin_duels"))


@app.post("/admin/duelos/<int:duel_id>/recusar")
@admin_required
def admin_duel_reject(duel_id):
    require_csrf()
    db = get_db()
    duel = db.execute("SELECT * FROM duels WHERE id=?", (duel_id,)).fetchone()
    if not duel:
        abort(404)
    if duel["status"] not in ("pending", "active"):
        flash("Esse duelo já foi encerrado.", "error")
        return redirect(url_for("admin_duels"))
    db.execute(
        """UPDATE duels SET status='rejected',
           admin_notes=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
        ((request.form.get("admin_notes") or "")[:500], duel_id)
    )
    db.commit()
    flash("Duelo recusado/cancelado. A área de duelo está disponível novamente.", "success")
    return redirect(url_for("admin_duels"))


@app.post("/admin/duelos/<int:duel_id>/vencedor")
@admin_required
def admin_duel_winner(duel_id):
    require_csrf()
    db = get_db()
    duel = db.execute("SELECT * FROM duels WHERE id=?", (duel_id,)).fetchone()
    if not duel:
        abort(404)
    if duel["status"] != "active":
        flash("Primeiro aprove o duelo para colocá-lo em curso.", "error")
        return redirect(url_for("admin_duels"))

    try:
        winner_id = int(request.form.get("winner_id", 0))
    except Exception:
        winner_id = 0
    if winner_id not in (duel["player1_id"], duel["player2_id"]):
        flash("Escolha um dos dois jogadores como vencedor.", "error")
        return redirect(url_for("admin_duels"))

    db.execute(
        """UPDATE duels SET status='finished',winner_id=?,
           admin_notes=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
        (winner_id, (request.form.get("admin_notes") or "")[:500], duel_id)
    )
    db.commit()
    winner = db.execute("SELECT nickname FROM players WHERE id=?", (winner_id,)).fetchone()
    flash(f"Duelo finalizado. Vencedor: {winner['nickname']}.", "success")
    return redirect(url_for("admin_duels"))


@app.get("/admin/backup.sqlite")
@admin_required
def admin_backup():
    return send_file(DB_PATH,as_attachment=True,download_name="chamas_flamejantes_v6_backup.sqlite")


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "10.2-mestre-x1",
        "database": str(DB_PATH.name),
        "persistent_storage": storage_is_persistent(),
        "railway": RUNNING_ON_RAILWAY,
        "tournaments": len(all_tournaments()),
        "community": len(community_ranking()),
        "maps": len(maps_list(active_only=True)),
        "duels_finished": len(duel_history(9999)),
        "duel_open": bool(duel_open()),
    }


if __name__ == "__main__":
    prepare_persistent_storage()
    init_db()
    migrate_v6_db()
    ensure_default_admin()
    print("\n" + "=" * 68)
    print(" 🔥 CHAMAS FLAMEJANTES V10.2 — MESTRE DO X1 + MAPAS PRO")
    print(" Site:   http://127.0.0.1:5000")
    print(" Painel: http://127.0.0.1:5000/admin")
    print(" Admin padrão: yukinochannyan")
    print(" Senha padrão: yukinochannyan60")
    print(" Torneios: ilimitados | FFA | FWG | 1v1 | 2x2 | MD3 1x1/2x2/3x3")
    print("=" * 68 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
