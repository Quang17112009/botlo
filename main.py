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
TELEGRAM_BOT_TOKEN = "7757369765:AAGNKUk80xeBAPXXZRTXySjQ0DPZXjzsueU"  # <-- Thay thế bằng Token Bot của bạn
ADMIN_IDS = [6915752059]  # <-- Thay thế bằng ID Telegram của admin, ví dụ: [123456789]

# --- Biến toàn cục (dữ liệu sẽ mất khi bot khởi động lại) ---
users_data = {}  # {user_id: {'balance': 10000000, 'username': 'Nguyen Van A'}}
current_bets = {}  # {user_id: {'type': 'tai/xiu', 'amount': 10000}}
current_session_id = 1748325
session_is_active = False # Trạng thái phiên, chỉ cho phép cược khi True
last_dice_roll_info = {} # Lưu thông tin kết quả phiên cuối cùng

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
    return "⚫️⚫️⚪️⚪️⚪️⚪️⚫️⚫️⚫️⚫️" # Đây chỉ là ví dụ tĩnh

# --- Lệnh Khởi động Bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in users_data:
        users_data[user.id] = {'balance': 10000000, 'username': user.first_name} # Khởi tạo 10 triệu VNĐ
    
    # Chỉ gửi tin nhắn chào mừng
    await update.message.reply_html(
        rf"Chào mừng {user.mention_html()}! Tôi là bot cược Tài Xỉu. Hãy dùng tôi trong một nhóm nhé, hoặc kiểm tra số dư với /balance.",
    )

# --- Lệnh Kiểm tra Số dư ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users_data:
        users_data[user_id] = {'balance': 10000000, 'username': update.effective_user.first_name}
    
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
        users_data[user_id] = {'balance': 10000000, 'username': username} # Khởi tạo nếu chưa có
    
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
    
    global session_is_active, current_session_id, current_bets
    if session_is_active:
        await update.message.reply_text(f"Phiên #{current_session_id} đang hoạt động. Vui lòng kết thúc phiên trước.")
        return

    current_session_id += 1
    session_is_active = True
    current_bets = {} # Reset cược cho phiên mới

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
        f"🎰 Jackpot: {200000000000000000000000000000000000040013701100431380020:,} VNĐ" # Jackpot tĩnh cho ví dụ
    )
    # Hẹn giờ tự động kết thúc phiên sau 30 giây (có thể điều chỉnh)
    context.job_queue.run_once(auto_end_session, 30, chat_id=update.effective_chat.id, name=f"end_session_{current_session_id}")


# --- Lệnh ADMIN: Kết thúc phiên và trả kết quả (chỉ trong nhóm) ---
# Hàm này có thể được gọi tự động hoặc bằng lệnh admin_end_session
async def end_session(update: Update, context: ContextTypes.DEFAULT_TYPE, dice_override=None) -> None:
    # `update` có thể là None nếu gọi từ job_queue, nên cần chat_id và message_id
    chat_id = context.job.chat_id if context.job else update.effective_chat.id
    
    global session_is_active, last_dice_roll_info
    if not session_is_active:
        if update: # Chỉ trả lời nếu có update (gọi thủ công)
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
    
    # Xử lý thắng thua
    for user_id, bet_info in current_bets.items():
        if bet_info['type'].upper() == result_type:
            win_amount = bet_info['amount'] * 2 # Thắng gấp đôi tiền cược
            users_data[user_id]['balance'] += win_amount
            total_win_amount += bet_info['amount'] # Tổng tiền cược thắng
            winners_list.append(f"🏆 {bet_info['username']} +{bet_info['amount']:,} VNĐ")
    
    # Hiển thị Jackpot khi nổ (ví dụ 3 con 6 hoặc 3 con 1)
    jackpot_status = ""
    if dice_values == [6, 6, 6] or dice_values == [1, 1, 1]:
        jackpot_status = f"\n🎉 NỔ JACKPOT! 🎉\nSố tiền Jackpot: {200000000000000000000000000000000000040013701100431380020:,} VNĐ"
        # Cần thêm logic để chọn người thắng Jackpot và phân phối tiền

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
        f"🎉 Người thắng:\n" + "\n".join(winners_list) + jackpot_status +
        f"\n\n📊 Cầu hiện tại: {get_current_pattern()}"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=message_text)

    # Sau khi kết thúc, clear cược cho phiên tiếp theo
    global current_bets
    current_bets = {}

# Hàm được gọi tự động bởi job_queue
async def auto_end_session(context: ContextTypes.DEFAULT_TYPE):
    await end_session(None, context) # Truyền None cho update vì không có update từ người dùng

# Lệnh admin để tự kết thúc phiên thủ công trong nhóm (thay vì đợi hẹn giờ)
async def admin_end_session_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bạn không có quyền sử dụng lệnh này.")
        return
    if update.effective_chat.type == "private":
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm.")
        return
    await end_session(update, context)

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Can thiệp kết quả ---
async def admin_override_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return
    
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Cú pháp: /admintung [số_1] [số_2] [số_3] (ví dụ: /admintung 6 6 6)")
        return
    
    try:
        dice_values = [int(arg) for arg in args]
        if not all(1 <= d <= 6 for d in dice_values):
            raise ValueError
        
        # Để can thiệp, admin sẽ tung xúc xắc và kết thúc phiên trong nhóm chat
        # Cần biết chat_id của nhóm mà phiên đang diễn ra
        # Đây là ví dụ đơn giản, bạn cần cơ chế để bot biết chat_id của nhóm đang hoạt động
        # VD: group_chat_id = -100xxxxxxxxxx
        # Nếu bot chỉ hoạt động trong 1 nhóm duy nhất, có thể hardcode chat_id đó.
        # Hoặc admin có thể gửi lệnh /adminphienmoi trong nhóm trước để bot lưu chat_id.

        # Giả định bot biết chat_id của nhóm đang chơi
        # Tạm thời lấy chat_id từ update nếu admin gõ lệnh này trong 1 nhóm
        # Nếu admin gõ trong private chat, bạn cần 1 cơ chế để xác định nhóm nào đang hoạt động
        # Ví dụ: group_chat_id = some_group_chat_id_stored_previously
        
        # Để đơn giản, giả sử admin dùng lệnh này trong nhóm
        # Nếu admin dùng trong chat riêng, thì sẽ cần một biến lưu chat_id của nhóm đang chơi
        # ví dụ: active_group_chat_id = -100123456789 (lấy từ update khi người dùng gõ /admin_start_session)
        # For now, let's just use the current chat if it's a group, else notify admin.
        if context.args and len(context.args) == 4: # admintung [chat_id] [d1] [d2] [d3]
             target_chat_id = int(context.args[0])
             dice_values = [int(arg) for arg in context.args[1:]]
        else: # admintung [d1] [d2] [d3]
            if update.effective_chat.type == "private":
                await update.message.reply_text("Để tung xúc xắc cho nhóm, bạn cần chỉ định chat_id của nhóm. Ví dụ: /admintung -123456789 6 4 1")
                return
            target_chat_id = update.effective_chat.id

        # Kiểm tra nếu phiên đang hoạt động trong nhóm đó
        if not session_is_active:
             await update.message.reply_text("Không có phiên nào đang hoạt động trong nhóm.")
             return

        # Tạo một context ảo cho hàm end_session
        dummy_context = ContextTypes.DEFAULT_TYPE(bot=context.bot, args=context.args, chat_data=context.chat_data, user_data=context.user_data)
        # Giả lập job cho end_session biết chat_id
        dummy_context.job = type('Job', (object,), {'chat_id': target_chat_id, 'name': 'admin_manual_end_session'})()
        
        await end_session(None, dummy_context, dice_override=dice_values)
        await update.message.reply_text(f"Đã can thiệp kết quả phiên #{current_session_id} với xúc xắc: {', '.join(map(str, dice_values))}")

    except ValueError:
        await update.message.reply_text("Lỗi: Xúc xắc phải là số từ 1 đến 6. Cú pháp: /admintung [số_1] [số_2] [số_3]")


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
        f"🎉 Người thắng:\n" + "\n".join(info['winners_list']) + info['jackpot_status']
    )
    await update.message.reply_text(message_text)

# --- Lệnh ADMIN (TRÊN BOT RIÊNG): Cộng tiền cho user ---
async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id) or update.effective_chat.type != "private":
        await update.message.reply_text("Lệnh này chỉ dành cho Admin và chỉ sử dụng trong chat riêng với bot.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Cú pháp: /adminaddxu [user_id] [số tiền]")
        return
    try:
        target_user_id = int(args[0])
        amount = int(args[1])
        if amount <= 0:
            await update.message.reply_text("Số tiền phải lớn hơn 0.")
            return

        if target_user_id not in users_data:
            # Nếu người dùng chưa từng tương tác, khởi tạo số dư và tên (nếu có thể lấy được)
            users_data[target_user_id] = {'balance': 0, 'username': f"Người dùng {target_user_id}"} 
            # Để lấy username chính xác, bot phải từng nhìn thấy user đó trong nhóm hoặc chat riêng
        
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
        await update.message.reply_text("Cú pháp: /adminrmvxu [user_id] [số tiền]")
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


# --- Main function để chạy bot ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers cho người dùng (trong nhóm)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("tai", cmd_tai))
    application.add_handler(CommandHandler("xiu", cmd_xiu))

    # Handlers cho ADMIN (trong nhóm)
    application.add_handler(CommandHandler("adminphienmoi", admin_start_session, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("adminendphien", admin_end_session_manual, filters=filters.ChatType.GROUPS))
    
    # Handlers cho ADMIN (trong chat riêng với bot)
    application.add_handler(CommandHandler("admintung", admin_override_dice, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("adminaddxu", admin_add_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("adminrmvxu", admin_remove_balance, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("adminlastsession", admin_last_session_info, filters=filters.ChatType.PRIVATE))


    # Chạy bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Khởi tạo một số dữ liệu ban đầu cho admin để test
    for admin_id in ADMIN_IDS:
        if admin_id not in users_data:
            users_data[admin_id] = {'balance': 9999999999999, 'username': f"Admin_{admin_id}"}
    main()

