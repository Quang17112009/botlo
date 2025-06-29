import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters
import random
import hashlib
import asyncio
import os 

# Import database utilities (Đảm bảo bạn đã có file database.py và cài đặt SQLAlchemy)
from database import get_session, User, GameState, get_or_create_user, get_game_state, update_game_state

# --- Cấu hình Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Cấu hình Bot ---
TELEGRAM_BOT_TOKEN = "7757369765:AAGNKUk80xeBAPXXZRTXySjQ0DPZXjzsueU"  # TOKEN BOT CỦA BẠN
ADMIN_IDS = [6915752059]  # ID TELEGRAM CỦA ADMIN

# --- Biến toàn cục (Với DB, các biến này chỉ còn lưu trạng thái tạm thời) ---
current_bets = {}  # {user_id: {'type': 'tai/xiu', 'amount': 10000, 'username': '...'}
last_dice_roll_info = {}  # Lưu thông tin kết quả phiên cuối cùng để admin xem

# --- Cấu hình Jackpot ---
JACKPOT_MIN_RESET_VALUE = 1000000000000000000000000000000000000000000000000000  # Giá trị Jackpot sau khi nổ
JACKPOT_CONTRIBUTION_RATE = 0.005  # 0.5% của tổng tiền cược sẽ vào Jackpot

# --- Hàm tiện ích ---
def is_admin(user_id):
    """Kiểm tra xem người dùng có phải admin không."""
    return user_id in ADMIN_IDS

def generate_dice_roll():
    """Tạo 3 viên xúc xắc ngẫu nhiên."""
    return [random.randint(1, 6) for _ in range(3)]

def calculate_result(dice_roll):
    """Tính tổng và xác định Tài/Xỉu."""
    total = sum(dice_roll)
    if 3 <= total <= 10:
        return "XỈU", total
    elif 11 <= total <= 18:
        return "TÀI", total
    else:
        return "LỖI", total # Trường hợp không mong muốn

def generate_md5(session_id, random_string, dice_values):
    """Tạo MD5 minh bạch từ chuỗi xác minh."""
    combined_string = f"#{session_id} {random_string} {'-'.join(map(str, dice_values))}"
    return hashlib.md5(combined_string.encode('utf-8')).hexdigest()

def get_current_pattern():
    """Tạo cầu hiện tại (ví dụ tĩnh, cần DB để làm động)."""
    return "⚫️⚫️⚪️⚪️⚪️⚪️⚫️⚫️⚫️⚫️" 

# --- Lệnh Khởi động Bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Lấy hoặc tạo user từ DB
    user_db = get_or_create_user(user.id, user.first_name)
    
    await update.message.reply_html(
        rf"Chào mừng {user.mention_html()}! Tôi là bot cược Tài Xỉu. "
        rf"Hãy thêm tôi vào nhóm của bạn để bắt đầu chơi. "
        rf"Bạn có thể kiểm tra số dư với lệnh /check.",
    )

# --- Lệnh Kiểm tra Số dư ---
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    user_db = get_or_create_user(user_id, username) # Đảm bảo user có trong DB
    await update.message.reply_text(f"💰 Số dư hiện tại của bạn: {user_db.balance:,} VNĐ")

# --- Lệnh Đặt cược (/tai, /xiu) ---
async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_type: str) -> None:
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ có thể sử dụng trong nhóm chat.")
        return

    game_state = get_game_state()
    if not bool(game_state.session_is_active): # Convert từ int (DB) sang bool
        await update.message.reply_text("Hiện không phải thời gian đặt cược. Vui lòng chờ phiên mới bắt đầu.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            f"⚠️ Cú pháp sai!\nDùng /{bet_type} [số tiền/all]\nVí dụ: /{bet_type} all hoặc /{bet_type} 5000"
        )
        return

    user_id = update.effective_user.id
    username = update.effective_user.first_name

    session = get_session()
    user_db = session.query(User).filter_by(id=user_id).first()
    if not user_db:
        # Nếu user chưa có trong DB, tạo mới.
        # Lý tưởng là get_or_create_user đã được gọi ở start hoặc check, nhưng phòng trường hợp.
        user_db = get_or_create_user(user_id, username)
        # Vì get_or_create_user tạo session riêng và commit, ta cần fetch lại trong session hiện tại nếu muốn dùng.
        # Hoặc đơn giản là thêm vào session hiện tại và commit sau.
        session.add(user_db) 
        session.commit() # Commit user mới trước khi tiếp tục
        user_db = session.query(User).filter_by(id=user_id).first() # Fetch lại user trong session này

    bet_amount_str = args[0]
    try:
        if bet_amount_str.lower() == 'all':
            bet_amount = user_db.balance
        else:
            bet_amount = int(bet_amount_str)
        
        if bet_amount <= 0:
            await update.message.reply_text("Số tiền cược phải lớn hơn 0.")
            session.close()
            return

        if bet_amount > user_db.balance:
            await update.message.reply_text(f"Bạn không đủ số dư. Số dư hiện tại: {user_db.balance:,} VNĐ")
            session.close()
            return
        
        # Lưu cược của người dùng cho phiên hiện tại vào biến toàn cục (không phải DB)
        current_bets[user_id] = {'type': bet_type, 'amount': bet_amount, 'username': username}
        user_db.balance -= bet_amount  # Trừ tiền ngay khi đặt cược
        session.commit()  # Lưu thay đổi số dư vào DB

        await update.message.reply_text(
            f"🔵 ĐÃ CƯỢC THÀNH CÔNG 🔵\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔢 Số tiền: {bet_amount:,} VNĐ\n"
            f"🎯 Cược vào: {bet_type.upper()}\n"
            f"💰 Số dư còn lại: {user_db.balance:,} VNĐ\n\n"
            f"📊 Cầu hiện tại: {get_current_pattern()}"
        )

    except ValueError:
        await update.message.reply_text("Số tiền không hợp lệ. Vui lòng nhập số hoặc 'all'.")
    finally:
        session.close() # Đảm bảo session luôn được đóng

async def cmd_tai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await place_bet(update, context, "TÀI")

async def cmd_xiu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await place_bet(update, context, "XỈU")

# --- Hàm thông báo đếm ngược ---
async def countdown_notification(context: ContextTypes.DEFAULT_TYPE):
    remaining_time = context.job.data['time']
    chat_id = context.job.chat_id
    session_id = context.job.data['session_id']

    if remaining_time == 10:
        await context.bot.send_message(chat_id=chat_id, text=f"⏱️ Phiên #{session_id} còn 10 giây để đặt cược!")
    elif remaining_time == 3:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Phiên #{session_id} còn 3 giây cuối cùng! NHANH TAY LÊN!")

# --- Lệnh ADMIN: Mở phiên mới (chỉ trong nhóm) ---
async def open_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bạn không có quyền sử dụng lệnh này.")
        return
    
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm.")
        return
    
    game_state = get_game_state()
    if bool(game_state.session_is_active): # Convert từ int (DB) sang bool
        await update.message.reply_text(f"Phiên #{game_state.current_session_id} đang hoạt động. Vui lòng kết thúc phiên trước bằng lệnh /stop.")
        return

    game_state.current_session_id += 1
    game_state.session_is_active = 1 # True (lưu int vào DB)
    game_state.active_group_chat_id = update.effective_chat.id
    update_game_state(game_state) # Lưu trạng thái mới vào DB

    global current_bets # Vẫn cần để reset cược trong bộ nhớ cho phiên mới
    current_bets = {}

    await update.message.reply_html(
        f"🎰 PHIÊN #{game_state.current_session_id} BẮT ĐẦU 🎰\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 Cầu hiện tại: {get_current_pattern()}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Thời gian đặt cược: 30 giây\n"
        f"💰 Lệnh cược:\n"
        f"/tai [số tiền/all] - Cược Tài (11-18)\n"
        f"/xiu [số tiền/all] - Cược Xỉu (3-10)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 Chế độ: MD5 Minh Bạch\n"
        f"🎰 Jackpot: {game_state.jackpot_amount:,} VNĐ" 
    )
    
    # Hẹn giờ tự động kết thúc phiên sau 30 giây
    context.job_queue.run_once(auto_end_session, 30, chat_id=update.effective_chat.id, name=f"end_session_{game_state.current_session_id}")

    # Lên lịch thông báo đếm ngược
    context.job_queue.run_once(countdown_notification, 20, chat_id=update.effective_chat.id, 
                               name=f"countdown_10s_{game_state.current_session_id}", 
                               data={'time': 10, 'session_id': game_state.current_session_id})
    
    context.job_queue.run_once(countdown_notification, 27, chat_id=update.effective_chat.id, 
                               name=f"countdown_3s_{game_state.current_session_id}", 
                               data={'time': 3, 'session_id': game_state.current_session_id})


# --- Hàm kết thúc phiên và trả kết quả ---
async def end_session(update: Update, context: ContextTypes.DEFAULT_TYPE, dice_override=None, target_chat_id=None) -> None:
    # Lấy trạng thái game từ DB
    game_state = get_game_state() # Lấy trạng thái game mới nhất từ DB
    
    chat_id = target_chat_id if target_chat_id else (context.job.chat_id if context.job else update.effective_chat.id)
    
    # Kiểm tra xem có phiên nào đang hoạt động không
    if not bool(game_state.session_is_active) and not dice_override: 
        if update and update.effective_chat.type != "private": 
            await update.message.reply_text("Không có phiên nào đang hoạt động để kết thúc.")
        return
    
    # Hủy các job đếm ngược còn lại nếu có
    for job in context.job_queue.get_jobs_by_name(f"countdown_10s_{game_state.current_session_id}"):
        job.schedule_removal()
    for job in context.job_queue.get_jobs_by_name(f"countdown_3s_{game_state.current_session_id}"):
        job.schedule_removal()

    # Cập nhật trạng thái phiên trong DB
    game_state.session_is_active = 0 # False (lưu int vào DB)
    update_game_state(game_state) # Lưu trạng thái mới vào DB
    
    dice_values = dice_override if dice_override else generate_dice_roll()
    result_type, total = calculate_result(dice_values)
    
    random_string = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=10))
    md5_hash = generate_md5(game_state.current_session_id, random_string, dice_values)
    verification_code = f"#{game_state.current_session_id} {random_string} {'-'.join(map(str, dice_values))}"

    total_bet_amount = sum(bet['amount'] for bet in current_bets.values())
    total_win_amount = 0
    winners_list = []
    jackpot_winner_info = None
    
    # Mở session DB để cập nhật Jackpot và balance user
    session = get_session()
    
    # Tích lũy Jackpot từ tổng cược
    game_state.jackpot_amount += int(total_bet_amount * JACKPOT_CONTRIBUTION_RATE)

    # Xử lý thắng thua
    for user_id, bet_info in current_bets.items():
        user_db = session.query(User).filter_by(id=user_id).first() # Lấy user từ DB
        if user_db and bet_info['type'].upper() == result_type:
            win_amount = bet_info['amount'] * 2 # Thắng gấp đôi tiền cược
            user_db.balance += win_amount
            total_win_amount += bet_info['amount'] # Tổng tiền cược thắng (phần gốc)
            winners_list.append(f"🏆 {bet_info['username']}: +{bet_info['amount']:,} VNĐ")
    
    # Hiển thị Jackpot khi nổ (ví dụ 3 con 6 hoặc 3 con 1)
    jackpot_status = ""
    if dice_values == [6, 6, 6] or dice_values == [1, 1, 1]:
        if current_bets:
            last_bettor_id = list(current_bets.keys())[-1] 
            jackpot_winner_db = session.query(User).filter_by(id=last_bettor_id).first()
            if jackpot_winner_db:
                jackpot_winner_db.balance += game_state.jackpot_amount # Cộng Jackpot vào số dư
                jackpot_status = f"\n🎉 NỔ JACKPOT! 🎉\nNgười thắng Jackpot: {jackpot_winner_db.username}\nSố tiền Jackpot: {game_state.jackpot_amount:,} VNĐ"
                game_state.jackpot_amount = JACKPOT_MIN_RESET_VALUE # Reset Jackpot sau khi nổ
            else: # Điều này không nên xảy ra nếu user được tạo khi đặt cược
                jackpot_status = "\n⚠️ NỔ JACKPOT nhưng không tìm thấy thông tin người đặt cược để nhận thưởng! Jackpot sẽ được reset."
                game_state.jackpot_amount = JACKPOT_MIN_RESET_VALUE # Vẫn reset Jackpot
        else:
            jackpot_status = "\n⚠️ NỔ JACKPOT nhưng không có người đặt cược để nhận thưởng! Jackpot sẽ được reset."
            game_state.jackpot_amount = JACKPOT_MIN_RESET_VALUE # Vẫn reset Jackpot

    # Lưu thay đổi Jackpot và balance user vào DB
    session.commit()
    session.close()

    # Cập nhật trạng thái game state sau khi xử lý Jackpot
    update_game_state(game_state) # Lưu GameState cuối cùng vào DB

    # Lưu thông tin phiên cuối cùng để admin bot riêng có thể truy cập
    global last_dice_roll_info
    last_dice_roll_info = {
        'dice': dice_values,
        'result_type': result_type,
        'total': total,
        'md5': md5_hash,
        'verification_code': verification_code,
        'total_bet_amount': total_bet_amount,
        'total_win_amount': total_win_amount,
        'winners_list': winners_list,
        'jackpot_status': jackpot_status,
        'session_id': game_state.current_session_id # Lấy từ DB
    }

    message_text = (
        f"🎯 PHIÊN #{game_state.current_session_id} KẾT THÚC 🎯\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎲 Xúc xắc: {', '.join(map(str, dice_values))} = {total}\n"
        f"🔮 Kết quả: 🎲 {result_type}\n\n"
        f"🔐 MD5 Minh bạch:\n{md5_hash}\n\n"
        f"🔎 Mã xác minh:\n{verification_code}\n\n"
        f"✅ Xác minh: Mã hóa mã trên bằng MD5 sẽ ra kết quả trùng khớp với MD5 đã công bố.\n\n"
        f"📊 Tổng cược: {total_bet_amount:,} VNĐ\n"
        f"💰 Tổng thưởng: {total_win_amount:,} VNĐ\n\n"
        f"🎉 Người thắng:\n" + ("\n".join(winners_list) if winners_list else "Không có người thắng trong phiên này.") + jackpot_status +
        f"\n\n📊 Cầu hiện tại: {get_current_pattern()}"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=message_text)

    # Sau khi kết thúc, clear cược cho phiên tiếp theo
    global current_bets
    current_bets = {}

# Hàm được gọi tự động bởi job_queue
async def auto_end_session(context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state()
    # Dừng job hiện tại để tránh chạy lại
    # Đảm bảo current_session_id được cập nhật trước khi hủy job
    for job in context.job_queue.get_jobs_by_name(f"end_session_{game_state.current_session_id}"):
        job.schedule_removal()
    
    # Gửi tin nhắn kết thúc phiên tới chat_id của job
    await end_session(None, context, target_chat_id=context.job.chat_id)

# Lệnh admin để tự kết thúc phiên thủ công trong nhóm (thay vì đợi hẹn giờ)
async def admin_end_session_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bạn không có quyền sử dụng lệnh này.")
        return
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm.")
        return
    
    game_state = get_game_state()
    # Hủy job tự động kết thúc nếu có
    for job in context.job_queue.get_jobs_by_name(f"end_session_{game_state.current_session_id}"):
        job.schedule_removal()

    await end_session(update, context, target_chat_id=update.effective_chat.id)

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Can thiệp kết quả và kết thúc phiên ---
async def admin_override_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return
    
    args = context.args
    if len(args) < 4:
        await update.message.reply_text("Cú pháp: /setdice [chat_id_nhóm] [số_1] [số_2] [số_3]\nVí dụ: /setdice -100123456789 6 4 1")
        return
    
    try:
        target_chat_id = int(args[0])
        dice_values = [int(arg) for arg in args[1:4]]
        
        if not all(1 <= d <= 6 for d in dice_values):
            raise ValueError("Xúc xắc phải là số từ 1 đến 6.")
        
        game_state = get_game_state()
        if not bool(game_state.session_is_active) or game_state.active_group_chat_id != target_chat_id:
            await update.message.reply_text(f"Hiện không có phiên nào đang hoạt động trong nhóm ID {target_chat_id} này.")
            return

        # Hủy job tự động kết thúc nếu có
        for job in context.job_queue.get_jobs_by_name(f"end_session_{game_state.current_session_id}"):
            job.schedule_removal()
        
        # Hủy các job đếm ngược
        for job in context.job_queue.get_jobs_by_name(f"countdown_10s_{game_state.current_session_id}"):
            job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"countdown_3s_{game_state.current_session_id}"):
            job.schedule_removal()

        dummy_context = ContextTypes.DEFAULT_TYPE(bot=context.bot, args=context.args, chat_data=context.chat_data, user_data=context.user_data)
        # Giả lập job cho end_session biết chat_id
        dummy_context.job = type('Job', (object,), {'chat_id': target_chat_id, 'name': 'admin_manual_end_session'})()
        
        await end_session(None, dummy_context, dice_override=dice_values, target_chat_id=target_chat_id)
        await update.message.reply_text(f"Đã can thiệp kết quả phiên #{game_state.current_session_id} trong nhóm {target_chat_id} với xúc xắc: {', '.join(map(str, dice_values))}")

    except ValueError as e:
        await update.message.reply_text(f"Lỗi: {e}\nCú pháp: /setdice [chat_id_nhóm] [số_1] [số_2] [số_3]")
    except Exception as e:
        await update.message.reply_text(f"Có lỗi xảy ra: {e}")

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Xem thông tin phiên cuối cùng ---
async def admin_last_session_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return
    
    global last_dice_roll_info # Khai báo global
    if not last_dice_roll_info:
        await update.message.reply_text("Chưa có thông tin về phiên cuối cùng.")
        return

    info = last_dice_roll_info
    message_text = (
        f"--- THÔNG TIN PHIÊN CUỐI CÙNG #{info['session_id']} ---\n"
        f"🎲 Xúc xắc: {', '.join(map(str, info['dice']))} = {info['total']}\n"
        f"🔮 Kết quả: 🎲 {info['result_type']}\n"
        f"🔐 MD5: {info['md5']}\n"
        f"🔎 Mã xác minh: {info['verification_code']}\n"
        f"📊 Tổng cược: {info['total_bet_amount']:,} VNĐ\n"
        f"💰 Tổng thưởng: {info['total_win_amount']:,} VNĐ\n"
        f"🎉 Người thắng:\n" + ("\n".join(info['winners_list']) if info['winners_list'] else "Không có người thắng trong phiên này.") + info['jackpot_status']
    )
    await update.message.reply_text(message_text)

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Cộng tiền cho user ---
async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Cú pháp: /addmoney [user_id] [số tiền]")
        return
    try:
        target_user_id = int(args[0])
        amount = int(args[1])
        if amount <= 0:
            await update.message.reply_text("Số tiền phải lớn hơn 0.")
            return

        session = get_session()
        user_db = session.query(User).filter_by(id=target_user_id).first()
        if not user_db:
            # Tạo user nếu chưa có, với username mặc định
            user_db = User(id=target_user_id, username=f"User_{target_user_id}") 
            session.add(user_db)
            session.commit()
            user_db = session.query(User).filter_by(id=target_user_id).first() # Lấy lại để cập nhật
        
        user_db.balance += amount
        session.commit()
        session.close()

        await update.message.reply_text(
            f"Đã cộng {amount:,} VNĐ vào tài khoản người dùng ID: {target_user_id}.\n"
            f"Số dư hiện tại của họ: {user_db.balance:,} VNĐ"
        )
    except ValueError:
        await update.message.reply_text("ID người dùng hoặc số tiền không hợp lệ.")
    finally:
        session.close()

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Trừ tiền của user ---
async def admin_remove_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Cú pháp: /removemoney [user_id] [số tiền]")
        return
    try:
        target_user_id = int(args[0])
        amount = int(args[1])
        if amount <= 0:
            await update.message.reply_text("Số tiền phải lớn hơn 0.")
            return

        session = get_session()
        user_db = session.query(User).filter_by(id=target_user_id).first()
        if not user_db:
            await update.message.reply_text(f"Không tìm thấy người dùng với ID: {target_user_id}.")
            session.close()
            return

        if user_db.balance < amount:
            await update.message.reply_text(f"Người dùng ID {target_user_id} không đủ số dư để trừ (còn {user_db.balance:,} VNĐ).")
            session.close()
            return

        user_db.balance -= amount
        session.commit()
        session.close()
        
        await update.message.reply_text(
            f"Đã trừ {amount:,} VNĐ khỏi tài khoản người dùng ID: {target_user_id}.\n"
            f"Số dư hiện tại của họ: {user_db.balance:,} VNĐ"
        )
    except ValueError:
        await update.message.reply_text("ID người dùng hoặc số tiền không hợp lệ.")
    finally:
        session.close()

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Chỉnh Jackpot ---
async def admin_set_jackpot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Cú pháp: /setjackpot [số tiền]\nVí dụ: /setjackpot 1000000000000")
        return
    try:
        new_jackpot_value = int(args[0])
        if new_jackpot_value < 0:
            await update.message.reply_text("Số tiền Jackpot không thể âm.")
            return
        
        game_state = get_game_state()
        game_state.jackpot_amount = new_jackpot_value
        update_game_state(game_state)

        await update.message.reply_text(f"Jackpot đã được đặt thành: {game_state.jackpot_amount:,} VNĐ")
    except ValueError:
        await update.message.reply_text("Số tiền Jackpot không hợp lệ.")

# --- Lệnh Người dùng: Bảng xếp hạng (/top) ---
async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session()
    # Sắp xếp người chơi theo số dư giảm dần
    sorted_users = session.query(User).order_by(User.balance.desc()).limit(5).all()
    session.close()
    
    if not sorted_users:
        await update.message.reply_text("Chưa có dữ liệu người chơi để xếp hạng.")
        return
    
    top_message = "🏆 BẢNG XẾP HẠNG NGƯỜI CHƠI 🏆\n━━━━━━━━━━━━━━━━\n"
    for i, user_db in enumerate(sorted_users):
        top_message += f"{i+1}. {user_db.username}: {user_db.balance:,} VNĐ\n"
    
    await update.message.reply_text(top_message)

# --- Lệnh Người dùng: Xem Jackpot (/jackpot) ---
async def view_jackpot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_state = get_game_state()
    await update.message.reply_text(f"💰 TIỀN HŨ JACKPOT HIỆN TẠI: {game_state.jackpot_amount:,} VNĐ")

# --- Lệnh Người dùng: Chế độ thường (/taixiu) ---
async def taixiu_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    info_text = """
🎲 CHẾ ĐỘ TÀI XỈU THƯỜNG 🎲
━━━━━━━━━━━━━━━━
• Đặt cược vào TÀI (tổng 11-18) hoặc XỈU (tổng 3-10).
• Có cơ hội nổ JACKPOT khi ra 3 con 1 hoặc 3 con 6.
• Lệnh đặt cược:
  • /tai [số tiền/all]
  • /xiu [số tiền/all]
"""
    await update.message.reply_text(info_text)

# --- Lệnh Người dùng: Chế độ MD5 minh bạch (/taixiumd5) ---
async def taixiumd5_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    info_text = """
💡 CHẾ ĐỘ MD5 MINH BẠCH 💡
━━━━━━━━━━━━━━━━
• Kết quả mỗi phiên được tạo ra dựa trên một chuỗi ngẫu nhiên và ID phiên, sau đó được mã hóa bằng MD5.
• Mã MD5 được công bố TRƯỚC KHI mở bát, đảm bảo tính công bằng.
• Sau khi phiên kết thúc, bot sẽ công bố mã xác minh đầy đủ (ID phiên + chuỗi ngẫu nhiên + kết quả xúc xắc). Bạn có thể tự mã hóa mã xác minh bằng MD5 để kiểm tra trùng khớp với mã đã công bố.
• Lệnh đặt cược:
  • /tai [số tiền/all]
  • /xiu [số tiền/all]
"""
    await update.message.reply_text(info_text)

# --- Lệnh Người dùng: Chuyển tiền (/chuyen) ---
async def transfer_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Cú pháp: /chuyen [ID người nhận] [số tiền]")
        return
    
    sender_id = update.effective_user.id
    sender_username = update.effective_user.first_name

    session = get_session()
    sender_user_db = session.query(User).filter_by(id=sender_id).first()
    if not sender_user_db:
        sender_user_db = get_or_create_user(sender_id, sender_username)
        session.add(sender_user_db) # Re-add for this session
        session.commit() # Commit new user
        sender_user_db = session.query(User).filter_by(id=sender_id).first() # Fetch again

    try:
        receiver_id = int(args[0])
        amount = int(args[1])

        if amount <= 0:
            await update.message.reply_text("Số tiền chuyển phải lớn hơn 0.")
            session.close()
            return

        if sender_id == receiver_id:
            await update.message.reply_text("Bạn không thể tự chuyển tiền cho chính mình.")
            session.close()
            return

        if sender_user_db.balance < amount:
            await update.message.reply_text(f"Bạn không đủ số dư để chuyển. Số dư hiện tại: {sender_user_db.balance:,} VNĐ")
            session.close()
            return
        
        receiver_user_db = session.query(User).filter_by(id=receiver_id).first()
        if not receiver_user_db:
            receiver_user_db = User(id=receiver_id, username=f"User_{receiver_id}")
            session.add(receiver_user_db)
            session.commit() # Commit new receiver user
            receiver_user_db = session.query(User).filter_by(id=receiver_id).first() # Fetch again
        
        sender_user_db.balance -= amount
        receiver_user_db.balance += amount
        session.commit() # Lưu thay đổi
        session.close()

        await update.message.reply_text(
            f"✅ GIAO DỊCH THÀNH CÔNG ✅\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Người chuyển: {sender_username}\n"
            f"Người nhận (ID): {receiver_id}\n"
            f"Số tiền: {amount:,} VNĐ\n"
            f"Số dư của bạn: {sender_user_db.balance:,} VNĐ"
        )
        try:
            receiver_username = receiver_user_db.username if receiver_user_db.username else f"User_{receiver_id}"
            await context.bot.send_message(
                chat_id=receiver_id, 
                text=f"Bạn vừa nhận được {amount:,} VNĐ từ {sender_username}.\nSố dư hiện tại của bạn: {receiver_user_db.balance:,} VNĐ"
            )
        except Exception as e:
            logger.warning(f"Không thể gửi thông báo chuyển tiền đến người nhận {receiver_id}: {e}")

    except ValueError:
        await update.message.reply_text("ID người nhận hoặc số tiền không hợp lệ. Vui lòng nhập số.")
    finally:
        session.close()

# --- Lệnh /help (Người dùng) ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
✨ ♦️ SUNWIN CASINO - HƯỚNG DẪN SỬ DỤNG ♦️ ✨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎲 TÀI XỈU ONLINE - UY TÍN HÀNG ĐẦU 🎲
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 LỆNH CƠ BẢN:
• /start - Bắt đầu tương tác với bot và xem hướng dẫn cơ bản
• /help - Xem hướng dẫn chi tiết các lệnh
• /check - Kiểm tra số dư hiện tại của bạn
• /top - Bảng xếp hạng người chơi
• /jackpot - Xem tiền hũ Jackpot hiện tại

🎯 LỆNH CHƠI:
• /taixiu - Chế độ thường (có JACKPOT)
• /taixiumd5 - Chế độ MD5 minh bạch
• /tai [số tiền/all] - Cược TÀI (11-18)
• /xiu [số tiền/all] - Cược XỈU (3-10)

🔧 LỆNH ADMIN:
(Chỉ admin mới sử dụng được và một số lệnh chỉ dùng trong chat riêng với bot)
• /newgame - Mở phiên mới (trong nhóm)
• /stop - Dừng trò chơi (trong nhóm)
• /addmoney [id] [số tiền] - Nạp tiền cho người dùng (chat riêng)
• /removemoney [id] [số tiền] - Trừ tiền của người dùng (chat riêng)
• /chuyen [id] [số tiền] - Chuyển tiền cho người dùng khác (chỉ người dùng, không phải admin)
• /setdice [chat_id_nhóm] [s1] [s2] [s3] - Can thiệp kết quả xúc xắc (chat riêng)
• /lastgame - Xem thông tin phiên cuối cùng (chat riêng)
• /setjackpot [số tiền] - Đặt lại giá trị Jackpot (chat riêng)
"""
    await update.message.reply_text(help_text)

# --- Main function để chạy bot ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Khởi tạo một số dữ liệu ban đầu cho admin để test, đảm bảo có trong DB
    for admin_id in ADMIN_IDS:
        session = get_session()
        admin_user = session.query(User).filter_by(id=admin_id).first()
        if not admin_user:
            admin_user = User(id=admin_id, username=f"Admin_{admin_id}", balance=999999999999999999) # Admin có nhiều tiền hơn
            session.add(admin_user)
            session.commit()
        session.close()
    
    # Khởi tạo GameState ban đầu nếu chưa có
    get_game_state()

    # Handlers cho người dùng (trong nhóm và riêng tư)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command)) 
    application.add_handler(CommandHandler("check", check_balance)) 
    application.add_handler(CommandHandler("top", top_players)) 
    application.add_handler(CommandHandler("jackpot", view_jackpot)) 
    application.add_handler(CommandHandler("taixiu", taixiu_info)) 
    application.add_handler(CommandHandler("taixiumd5", taixiumd5_info)) 
    application.add_handler(CommandHandler("chuyen", transfer_money)) 

    # Handlers cho lệnh đặt cược (chỉ trong nhóm)
    application.add_handler(CommandHandler("tai", cmd_tai, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("xiu", cmd_xiu, filters=filters.ChatType.GROUPS))

    # Handlers cho ADMIN (trong nhóm)
    application.add_handler(CommandHandler("newgame", open_new_game, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("stop", admin_end_session_manual, filters=filters.ChatType.GROUPS))
    
    # Handlers cho ADMIN (trong chat riêng với bot)
    application.add_handler(CommandHandler("setdice", admin_override_dice, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("addmoney", admin_add_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("removemoney", admin_remove_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("lastgame", admin_last_session_info, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("setjackpot", admin_set_jackpot, filters=filters.ChatType.PRIVATE))

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Error running bot: {e}")


if __name__ == "__main__":
    main()
