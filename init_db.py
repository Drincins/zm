from core.db import init_db, engine

if __name__ == "__main__":
    print("🔍 Подключение к базе:", engine.url.database)
    init_db()
    print("✅ Таблицы созданы")
