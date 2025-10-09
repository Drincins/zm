from pathlib import Path
import os

# Directories for import workflow
BASE_DIR = Path(__file__).resolve().parent

NEW_DIR = os.getenv("BANK_NEW_DIR", str(BASE_DIR / "data" / "bank_statements" / "new"))
ARCHIVE_DIR = os.getenv("BANK_ARCHIVE_DIR", str(BASE_DIR / "data" / "bank_statements" / "archiv"))

# Backups
DB_BACKUP_DIR = os.getenv("DB_BACKUP_DIR", str(BASE_DIR / "data" / "backups"))
