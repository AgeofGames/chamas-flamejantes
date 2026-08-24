import os
import sys

from app import (
    RUNNING_ON_RAILWAY,
    RAILWAY_VOLUME_PATH,
    DB_PATH,
    UPLOAD_DIR,
    MAPS_DIR,
    prepare_persistent_storage,
    init_db,
    migrate_v6_db,
    ensure_default_admin,
)

# Segurança: no Railway não deixa o site iniciar com SQLite temporário.
if RUNNING_ON_RAILWAY and not RAILWAY_VOLUME_PATH:
    print("=" * 72, flush=True)
    print("ERRO: O CHAMAS FLAMEJANTES precisa de um Railway Volume.", flush=True)
    print("Adicione um Volume ao serviço com Mount Path: /app/persistent", flush=True)
    print("Depois faça Redeploy. Isso impede perda do SQLite e das fotos.", flush=True)
    print("=" * 72, flush=True)
    sys.exit(2)

prepare_persistent_storage()
init_db()
migrate_v6_db()
ensure_default_admin()

port = os.environ.get("PORT", "8080")

print("=" * 72, flush=True)
print("CHAMAS FLAMEJANTES V10.2 - MESTRE DO X1 + MAPAS PRO", flush=True)
print(f"Banco: {DB_PATH}", flush=True)
print(f"Uploads: {UPLOAD_DIR}", flush=True)
print(f"Mapas: {MAPS_DIR}", flush=True)
print(f"Volume persistente: {'SIM' if RAILWAY_VOLUME_PATH else 'NAO (modo local)'}", flush=True)
print("=" * 72, flush=True)

# 1 worker é proposital: o banco é SQLite.
# Threads atendem várias requisições, preservando um único processo gravador.
os.execvp(
    "gunicorn",
    [
        "gunicorn",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "1",
        "--threads", "8",
        "--timeout", "120",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "app:app",
    ],
)
