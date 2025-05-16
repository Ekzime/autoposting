from contextlib import contextmanager
from sqlalchemy.orm import Session
from database.models import engine



@contextmanager
def session_scope():
    """
    Провайдер сессий для работы с базой данных.
    """
    session = Session(engine)
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


