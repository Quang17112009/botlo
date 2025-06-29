from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/taixiu.db")

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(String)
    balance = Column(BigInteger, default=100000)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', balance={self.balance})>"

class GameState(Base):
    __tablename__ = 'game_state'
    id = Column(Integer, primary_key=True)
    current_session_id = Column(Integer, default=1748324)
    session_is_active = Column(Integer, default=0)
    # Đã giảm giá trị Jackpot xuống một số lớn nhưng nằm trong giới hạn của SQLite (ví dụ: 1 triệu tỷ)
    jackpot_amount = Column(BigInteger, default=1_000_000_000_000_000) # 1 triệu tỷ (1 quadrillion)
    active_group_chat_id = Column(BigInteger, nullable=True)

    def __repr__(self):
        return f"<GameState(id={self.id}, session={self.current_session_id}, active={self.session_is_active})>"

engine = create_engine(DATABASE_URL)

os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def get_session():
    return Session()

def get_or_create_user(user_id, username):
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id, username=username)
            session.add(user)
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return user

def get_game_state():
    session = get_session()
    try:
        state = session.query(GameState).first()
        if not state:
            state = GameState()
            session.add(state)
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return state

def update_game_state(new_state):
    session = get_session()
    try:
        state = session.query(GameState).first()
        if state:
            state.current_session_id = new_state.current_session_id
            state.session_is_active = new_state.session_is_active
            state.jackpot_amount = new_state.jackpot_amount
            state.active_group_chat_id = new_state.active_group_chat_id
        else:
            session.add(new_state)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

