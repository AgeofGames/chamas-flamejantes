import sqlite3
from pathlib import Path
DB = Path(__file__).parent / "data" / "tournament.sqlite"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
print("Banco:", DB)
print("\nTORNEIOS:")
for r in con.execute("SELECT id,name,mode_key,format_type,team_size,best_of,max_entries,status,registration_open FROM tournaments ORDER BY status,display_order,id"):
    c = con.execute("SELECT COUNT(*) FROM tournament_entries WHERE tournament_id=? AND status IN ('inscrito','confirmado')", (r['id'],)).fetchone()[0]
    md3 = " | MD3" if r['best_of'] == 3 else ""
    print(f"- #{r['id']} {r['name']} | modo={r['mode_key']} | equipe={r['team_size']} | inscritos={c}/{r['max_entries']} | {r['status']}{md3}")
print("\nJogadores globais:", con.execute("SELECT COUNT(*) FROM players").fetchone()[0])
print("Confrontos salvos:", con.execute("SELECT COUNT(*) FROM matches").fetchone()[0])
print("Torneios finalizados:", con.execute("SELECT COUNT(*) FROM tournaments WHERE status='finalizado'").fetchone()[0])
input("\nPressione ENTER para sair...")
