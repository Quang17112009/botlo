from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Đường dẫn đến file database SQLite
# Nếu triển khai trên Render, hãy đảm bảo thư mục data/ có thể ghi được
# Hoặc lưu database file ở một thư mục khác nếu Render khuyến nghị
# Mặc định: 'sqlite:///data/taixiu.db'
# Để dùng biến môi trường từ Render: os.environ.get("DATABASE_URL", "sqlite:///data/taixiu.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/taixiu.db")

# Khởi tạo Base cho declarative models
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, autoincrement=False) # Telegram user_id can be large
    username = Column(String)
    balance = Column(BigInteger, default=100000) # Sử dụng BigInteger cho số dư lớn để tránh tràn số

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', balance={self.balance})>"

class GameState(Base):
    __tablename__ = 'game_state'
    id = Column(Integer, primary_key=True) # Chỉ có một hàng duy nhất cho trạng thái game
    current_session_id = Column(Integer, default=1748324)
    session_is_active = Column(Integer, default=0) # 0 for False, 1 for True
    # Đặt giá trị mặc định Jackpot lớn để thể hiện tính "khủng"
    jackpot_amount = Column(BigInteger, default=100000000000000000000000000000000000040013701100431380020) 
    active_group_chat_id = Column(BigInteger, nullable=True) # ID nhóm đang chơi

    def __repr__(self):
        return f"<GameState(id={self.id}, session={self.current_session_id}, active={self.session_is_active})>"

# Connect to the database
engine = create_engine(DATABASE_URL)

# Tạo bảng nếu chưa tồn tại
# Đảm bảo thư mục 'data' tồn tại nếu bạn dùng đường dẫn 'sqlite:///data/taixiu.db'
os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
Base.metadata.create_all(engine) 

Session = sessionmaker(bind=engine)

def get_session():
    """Tạo và trả về một SQLAlchemy Session."""
    return Session()

def get_or_create_user(user_id, username):
    """Lấy hoặc tạo người dùng từ cơ sở dữ liệu."""
    session = get_session()
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        user = User(id=user_id, username=username)
        session.add(user)
        session.commit()
    session.close() # Quan trọng: Luôn đóng session
    return user

def get_game_state():
    """Lấy trạng thái trò chơi hiện tại từ cơ sở dữ liệu. Tạo nếu chưa có."""
    session = get_session()
    state = session.query(GameState).first()
    if not state:
        state = GameState()
        session.add(state)
        session.commit()
    session.close() # Quan trọng: Luôn đóng session
    return state

def update_game_state(new_state):
    """Cập nhật trạng thái trò chơi vào cơ sở dữ liệu."""
    session = get_session()
    state = session.query(GameState).first() # Lấy bản ghi duy nhất
    if state:
        state.current_session_id = new_state.current_session_id
        state.session_is_active = new_state.session_is_active
        state.jackpot_amount = new_state.jackpot_amount
        state.active_group_chat_id = new_state.active_group_chat_id
    else:
        session.add(new_state) # Trường hợp rất hiếm, chỉ khi chưa có bản ghi nào
    session.commit()
    session.close() # Quan trọng: Luôn đóng session

