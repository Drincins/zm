# core/db.py
# Настройка подключения к БД и фабрики сессий

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models.base import Base  # общий Base + импорт моделей внутри base.py

# URL можно переопределить через переменную окружения DATABASE_URL
# пример: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1212@localhost:5432/ZM")

# Engine с pre_ping (лечит обрывы соединений) и future API
engine = create_engine(
    DATABASE_URL,
    echo=False,            # включай True, если нужно видеть SQL в логах
    pool_pre_ping=True,    # проверка коннекта из пула
    future=True,
)

# Фабрика сессий: безопасные флаги
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

def init_db() -> None:
    """
    Создаёт недостающие таблицы согласно Base.metadata.
    Base у нас подтягивает все модели через db_models/base.py.
    """
    Base.metadata.create_all(bind=engine)
