import logging
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import hashlib
import asyncio

# --- Cấu hình Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Cấu hình Bot ---
TELEGRAM_BOT_TOKEN = "7757369765:AAGNKUk80xeBAPXXZRTXySjQ0DPZXjzsueU"  # <-- TOKEN BOT CỦA BẠN
ADMIN_IDS = [6915752059]  # <-- ID TELEGRAM CỦA ADMIN

# --- Biến toàn cục (DỮ LIỆU NÀY SẼ MẤT KHI BOT KHỞI ĐỘNG LẠI!) ---
users_data = {}  # {user_id: {'balance': 100000, 'username': 'Nguyen Van A'}}
current_bets = {}  # {user_id: {'type': 'tai/xiu', 'amount': 10000, 'username': '...'}
current_session_id = 1748324 # Bắt đầu từ 1748324 như trong ví dụ của bạn
session_is_active = False # Trạng thái phiên, chỉ cho phép cược khi True
last_dice_roll_info = {} # Lưu thông tin kết quả phiên cuối cùng để admin xem
active_group_chat_id = None # Lưu chat_id của nhóm đang chơi để admin có thể can thiệp từ chat riêng

# --- Cấu hình Jackpot ---
JACKPOT_AMOUNT = 200000000000000000000000000000000000040013701100431380020 # Giá trị Jackpot khởi tạo
JACKPOT_MIN_RESET_VALUE = 1000000000000000000000000000000000000000000000000000 # Giá trị Jackpot sau khi nổ
JACKPOT_CONTRIBUTION_RATE = 0.005 # 0.5% của tổng tiền cược sẽ vào Jackpot

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
    if user.id not in users_data:
        users_data[user.id] = {'balance': 100000, 'username': user.first_name} # Số dư mặc định 100000
    
    await update.message.reply_html(
        rf"Chào mừng {user.mention_html()}! Tôi là bot cược Tài Xỉu. "
        rf"Hãy thêm tôi vào nhóm của bạn để bắt đầu chơi. "
        rf"Bạn có thể kiểm tra số dư với lệnh /balance.",
    )

# --- Lệnh Kiểm tra Số dư ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users_data:
        users_data[user_id] = {'balance': 100000, 'username': update.effective_user.first_name} # Số dư mặc định 100000
    
    await update.message.reply_text(f"💰 Số dư hiện tại của bạn: {users_data[user_id]['balance']:,} VNĐ")

# --- Lệnh Đặt cược (/tai, /xiu) ---
async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_type: str) -> None:
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ có thể sử dụng trong nhóm chat.")
        return

    global session_is_active
    if not session_is_active:
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

    if user_id not in users_data:
        users_data[user_id] = {'balance': 100000, 'username': username} # Số dư mặc định 100000
    
    bet_amount_str = args[0]
    try:
        if bet_amount_str.lower() == 'all':
            bet_amount = users_data[user_id]['balance']
        else:
            bet_amount = int(bet_amount_str)
        
        if bet_amount <= 0:
            await update.message.reply_text("Số tiền cược phải lớn hơn 0.")
            return

        if bet_amount > users_data[user_id]['balance']:
            await update.message.reply_text(f"Bạn không đủ số dư. Số dư hiện tại: {users_data[user_id]['balance']:,} VNĐ")
            return
        
        # Lưu cược của người dùng cho phiên hiện tại
        current_bets[user_id] = {'type': bet_type, 'amount': bet_amount, 'username': username}
        users_data[user_id]['balance'] -= bet_amount # Trừ tiền ngay khi đặt cược

        await update.message.reply_text(
            f"🔵 ĐÃ CƯỢC THÀNH CÔNG 🔵\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔢 Số tiền: {bet_amount:,} VNĐ\n"
            f"🎯 Cược vào: {bet_type.upper()}\n"
            f"💰 Số dư còn lại: {users_data[user_id]['balance']:,} VNĐ\n\n"
            f"📊 Cầu hiện tại: {get_current_pattern()}"
        )

    except ValueError:
        await update.message.reply_text("Số tiền không hợp lệ. Vui lòng nhập số hoặc 'all'.")

async def cmd_tai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await place_bet(update, context, "TÀI")

async def cmd_xiu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await place_bet(update, context, "XỈU")

# --- Lệnh ADMIN: Bắt đầu phiên mới (chỉ trong nhóm) ---
async def admin_start_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bạn không có quyền sử dụng lệnh này.")
        return
    
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm.")
        return
    
    global session_is_active, current_session_id, current_bets, active_group_chat_id
    if session_is_active:
        await update.message.reply_text(f"Phiên #{current_session_id} đang hoạt động. Vui lòng kết thúc phiên trước.")
        return

    current_session_id += 1
    session_is_active = True
    current_bets = {} # Reset cược cho phiên mới
    active_group_chat_id = update.effective_chat.id # Lưu chat_id của nhóm đang chơi

    await update.message.reply_text(
        f"🎰 PHIÊN #{current_session_id} BẮT ĐẦU 🎰\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 Cầu hiện tại: {get_current_pattern()}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Thời gian đặt cược: 30 giây\n"
        f"💰 Lệnh cược:\n"
        f"/tai [số tiền/all] - Cược Tài (11-18)\n"
        f"/xiu [số tiền/all] - Cược Xỉu (3-10)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 Chế độ: MD5 Minh Bạch\n"
        f"🎰 Jackpot: {JACKPOT_AMOUNT:,} VNĐ" 
    )
    # Hẹn giờ tự động kết thúc phiên sau 30 giây (có thể điều chỉnh)
    context.job_queue.run_once(auto_end_session, 30, chat_id=update.effective_chat.id, name=f"end_session_{current_session_id}")


# --- Hàm kết thúc phiên và trả kết quả ---
async def end_session(update: Update, context: ContextTypes.DEFAULT_TYPE, dice_override=None, target_chat_id=None) -> None:
    # Lấy chat_id để gửi tin nhắn, ưu tiên target_chat_id nếu được cung cấp
    chat_id = target_chat_id if target_chat_id else (context.job.chat_id if context.job else update.effective_chat.id)
    
    # Khai báo global ở đầu hàm, trước bất kỳ lần truy cập nào đến biến này
    global session_is_active, last_dice_roll_info, current_bets, JACKPOT_AMOUNT 
    
    # Kiểm tra xem có phiên nào đang hoạt động không
    if not session_is_active and not dice_override: # Nếu không có phiên và không phải là lệnh can thiệp
        if update and update.effective_chat.type != "private": # Chỉ trả lời nếu có update và không phải từ chat riêng admin
            await update.message.reply_text("Không có phiên nào đang hoạt động để kết thúc.")
        return
    
    session_is_active = False # Kết thúc phiên
    
    dice_values = dice_override if dice_override else generate_dice_roll()
    result_type, total = calculate_result(dice_values)
    
    random_string = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=10))
    md5_hash = generate_md5(current_session_id, random_string, dice_values)
    verification_code = f"#{current_session_id} {random_string} {'-'.join(map(str, dice_values))}"

    total_bet_amount = sum(bet['amount'] for bet in current_bets.values())
    total_win_amount = 0
    winners_list = []
    jackpot_winner_info = None
    
    # Tích lũy Jackpot từ tổng cược
    JACKPOT_AMOUNT += int(total_bet_amount * JACKPOT_CONTRIBUTION_RATE)

    # Xử lý thắng thua
    for user_id, bet_info in current_bets.items():
        if bet_info['type'].upper() == result_type:
            win_amount = bet_info['amount'] * 2 # Thắng gấp đôi tiền cược
            users_data[user_id]['balance'] += win_amount
            total_win_amount += bet_info['amount'] # Tổng tiền cược thắng (phần gốc)
            winners_list.append(f"🏆 {bet_info['username']} +{bet_info['amount']:,} VNĐ")
    
    # Hiển thị Jackpot khi nổ (ví dụ 3 con 6 hoặc 3 con 1)
    jackpot_status = ""
    if dice_values == [6, 6, 6] or dice_values == [1, 1, 1]:
        # Chọn người thắng Jackpot: người cuối cùng đặt cược trong phiên
        if current_bets:
            # Lấy key (user_id) cuối cùng trong dictionary (python 3.7+ đảm bảo thứ tự chèn)
            last_bettor_id = list(current_bets.keys())[-1] 
            jackpot_winner_info = users_data[last_bettor_id]
            users_data[last_bettor_id]['balance'] += JACKPOT_AMOUNT # Cộng Jackpot vào số dư
            jackpot_status = f"\n🎉 NỔ JACKPOT! 🎉\nNgười thắng Jackpot: {jackpot_winner_info['username']}\nSố tiền Jackpot: {JACKPOT_AMOUNT:,} VNĐ"
            JACKPOT_AMOUNT = JACKPOT_MIN_RESET_VALUE # Reset Jackpot sau khi nổ
        else:
            jackpot_status = "\n⚠️ NỔ JACKPOT nhưng không có người đặt cược để nhận thưởng! Jackpot sẽ được reset."
            JACKPOT_AMOUNT = JACKPOT_MIN_RESET_VALUE # Vẫn reset Jackpot

    # Lưu thông tin phiên cuối cùng để admin bot riêng có thể truy cập
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
        'session_id': current_session_id
    }

    message_text = (
        f"🎯 PHIÊN #{current_session_id} KẾT THÚC 🎯\n"
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
    current_bets = {}

# Hàm được gọi tự động bởi job_queue
async def auto_end_session(context: ContextTypes.DEFAULT_TYPE):
    # Dừng job hiện tại để tránh chạy lại
    for job in context.job_queue.get_jobs_by_name(f"end_session_{current_session_id}"):
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
    
    # Hủy job tự động kết thúc nếu có
    for job in context.job_queue.get_jobs_by_name(f"end_session_{current_session_id}"):
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
        
        global session_is_active
        if not session_is_active or active_group_chat_id != target_chat_id:
            await update.message.reply_text(f"Hiện không có phiên nào đang hoạt động trong nhóm ID {target_chat_id} này.")
            return

        # Hủy job tự động kết thúc nếu có
        for job in context.job_queue.get_jobs_by_name(f"end_session_{current_session_id}"):
            job.schedule_removal()

        # Tạo một context ảo cho hàm end_session
        dummy_context = ContextTypes.DEFAULT_TYPE(bot=context.bot, args=context.args, chat_data=context.chat_data, user_data=context.user_data)
        # Giả lập job cho end_session biết chat_id
        dummy_context.job = type('Job', (object,), {'chat_id': target_chat_id, 'name': 'admin_manual_end_session'})()
        
        await end_session(None, dummy_context, dice_override=dice_values, target_chat_id=target_chat_id)
        await update.message.reply_text(f"Đã can thiệp kết quả phiên #{current_session_id} trong nhóm {target_chat_id} với xúc xắc: {', '.join(map(str, dice_values))}")

    except ValueError as e:
        await update.message.reply_text(f"Lỗi: {e}\nCú pháp: /setdice [chat_id_nhóm] [số_1] [số_2] [số_3]")
    except Exception as e:
        await update.message.reply_text(f"Có lỗi xảy ra: {e}")

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Xem thông tin phiên cuối cùng ---
async def admin_last_session_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return
    
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

        if target_user_id not in users_data:
            users_data[target_user_id] = {'balance': 100000, 'username': f"User_{target_user_id}"} # Khởi tạo với 100000
        
        users_data[target_user_id]['balance'] += amount
        await update.message.reply_text(
            f"Đã cộng {amount:,} VNĐ vào tài khoản người dùng ID: {target_user_id}.\n"
            f"Số dư hiện tại của họ: {users_data[target_user_id]['balance']:,} VNĐ"
        )
    except ValueError:
        await update.message.reply_text("ID người dùng hoặc số tiền không hợp lệ.")

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

        if target_user_id not in users_data:
            await update.message.reply_text(f"Không tìm thấy người dùng với ID: {target_user_id}.")
            return

        if users_data[target_user_id]['balance'] < amount:
            await update.message.reply_text(f"Người dùng ID {target_user_id} không đủ số dư để trừ (còn {users_data[target_user_id]['balance']:,} VNĐ).")
            return

        users_data[target_user_id]['balance'] -= amount
        await update.message.reply_text(
            f"Đã trừ {amount:,} VNĐ khỏi tài khoản người dùng ID: {target_user_id}.\n"
            f"Số dư hiện tại của họ: {users_data[target_user_id]['balance']:,} VNĐ"
        )
    except ValueError:
        await update.message.reply_text("ID người dùng hoặc số tiền không hợp lệ.")

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
        
        global JACKPOT_AMOUNT
        JACKPOT_AMOUNT = new_jackpot_value
        await update.message.reply_text(f"Jackpot đã được đặt thành: {JACKPOT_AMOUNT:,} VNĐ")
    except ValueError:
        await update.message.reply_text("Số tiền Jackpot không hợp lệ.")


# --- Main function để chạy bot ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers cho người dùng (trong nhóm)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("tai", cmd_tai, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("xiu", cmd_xiu, filters=filters.ChatType.GROUPS))

    # Handlers cho ADMIN (trong nhóm) - Dễ nhớ hơn
    application.add_handler(CommandHandler("newgame", admin_start_session, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("endgame", admin_end_session_manual, filters=filters.ChatType.GROUPS))
    
    # Handlers cho ADMIN (trong chat riêng với bot) - Dễ nhớ hơn
    application.add_handler(CommandHandler("setdice", admin_override_dice, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("addmoney", admin_add_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("removemoney", admin_remove_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("lastgame", admin_last_session_info, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("setjackpot", admin_set_jackpot, filters=filters.ChatType.PRIVATE))


    # Chạy bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Khởi tạo một số dữ liệu ban đầu cho admin để test
    for admin_id in ADMIN_IDS:
        if admin_id not in users_data:
            users_data[admin_id] = {'balance': 999999999999999999, 'username': f"Admin_{admin_id}"} # Admin có nhiều tiền hơn
    main()

