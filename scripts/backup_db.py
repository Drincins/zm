import os
import subprocess
from datetime import datetime
from pathlib import Path


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is not set")

    backup_dir = Path(os.getenv("DB_BACKUP_DIR", "data/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = backup_dir / f"zm_backup_{ts}.sql"

    # Require pg_dump in PATH
    cmd = [
        "pg_dump",
        "--no-owner",
        "--format=plain",
        "--file", str(out),
        db_url,
    ]
    try:
        subprocess.check_call(cmd)
        print(f"Backup created: {out}")
    except FileNotFoundError:
        raise SystemExit("pg_dump not found. Install PostgreSQL client and add to PATH.")
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Backup failed: {e}")


if __name__ == "__main__":
    main()

