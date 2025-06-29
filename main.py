import telebot
from telebot.types import ChatPermissions
import requests
import random
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta, date
import time
import atexit
from telebot import TeleBot, types
import pytz
import threading
from threading import Timer
import json
import re
import traceback
import schedule
from telebot.apihelper import ApiException
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# =====================--------------(TOKEN BOT)--------------=====================
# THAY THẾ CÁC TOKEN NÀY BẰNG TOKEN THỰC TẾ CỦA BẠN
API_BOT = '7324552224:AAGcEd3dg5OZuIs0bJF6QFfa4B3lgNq2rh8' # Bot chính (dùng cho lệnh /congtien và thông báo riêng cho admin)
API_BOT2 = '7975395053:AAE6xhLQ-y6BJTlvrNgWjOOWSnZMZ40AxTw' # Bot phòng game Tài Xỉu
API_BOT3 = '8027877843:AAG1z9OcCkdz8jcT3KnWuKi6BCZvlJhxu2s' # Bot thông báo (có thể không cần nếu chỉ gửi riêng admin)

bot = telebot.TeleBot(API_BOT) # parse_mode=None là mặc định, có thể bỏ
bot2 = telebot.TeleBot(API_BOT2)
bot3 = telebot.TeleBot(API_BOT3) # Giữ lại nếu bạn muốn bot3 vẫn gửi thông báo công khai

# =====================--------------(Cấu hình Admin và Nhóm)--------------=====================
ADMIN_ID = 6915752059 # THAY THẾ BẰNG ID TELEGRAM CỦA ADMIN
# Dưới đây là các ID nhóm chat. Mình đặt chúng giống nhau dựa trên ví dụ của bạn.
# Nếu bạn có các nhóm khác nhau, hãy thay đổi ID cho phù hợp.
GAME_ROOM_ID = -1002781947864 # ID nhóm phòng game Tài Xỉu
RESULT_CHANNEL_ID = -1002781947864 # ID nhóm thông báo kết quả phòng game (có thể là kênh hoặc nhóm khác)

# =====================--------------(Biến toàn cục)--------------=====================
user_balance = {}
user_bets = {} # Lưu trữ cược của người chơi trong phiên hiện tại
current_session = 1
session_results = [] # Lịch sử kết quả các phiên (chỉ giữ 10 phiên gần nhất)
processed_users = set() # Theo dõi người chơi đã được xử lý thắng/thua trong phiên
accepting_bets = False # Trạng thái cho phép đặt cược

# =====================--------------(Kho Lưu Số Dư)--------------=====================

def save_balance_to_file():
    """Lưu số dư của người dùng vào file sodu.txt"""
    with open("sodu.txt", "w") as f:
        for user_id, balance in user_balance.items():
            f.write(f"{user_id} {int(balance)}\n") # Lưu dưới dạng số nguyên

def load_balance_from_file():
    """Tải số dư của người dùng từ file sodu.txt"""
    if os.path.exists("sodu.txt"):
        with open("sodu.txt", "r") as f:
            for line in f:
                if line.strip():
                    try:
                        user_id, balance_str = line.strip().split()
                        user_balance[int(user_id)] = int(float(balance_str)) # Đảm bảo là số nguyên
                    except ValueError:
                        print(f"Lỗi đọc dòng trong sodu.txt: {line.strip()}")
    else:
        open("sodu.txt", "a").close() # Tạo file nếu chưa tồn tại

# Tải số dư khi bot khởi động
load_balance_from_file()

# Đăng ký hàm save_balance_to_file để chạy khi script kết thúc
atexit.register(save_balance_to_file)

# =====================--------------(Quản lý Phiên Game)--------------=====================

def save_session_to_file():
    """Lưu số phiên hiện tại vào file phien.txt"""
    with open("phien.txt", "w") as file:
        file.write(str(current_session))

def load_session_from_file():
    """Tải số phiên hiện tại từ file phien.txt"""
    global current_session
    try:
        with open("phien.txt", "r") as file:
            current_session = int(file.read().strip())
    except FileNotFoundError:
        current_session = 1
        save_session_to_file() # Tạo file nếu chưa có
    except ValueError:
        current_session = 1 # Reset nếu nội dung file không hợp lệ
        save_session_to_file()

def save_session_history_to_file():
    """Lưu lịch sử 10 phiên gần nhất vào file matphien.txt"""
    last_10_sessions = session_results[-10:]
    display_last_10 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])
    with open("matphien.txt", "w", encoding='utf-8') as file:
        file.write(display_last_10)

def load_session_history_from_file():
    """Tải lịch sử phiên từ file matphien.txt"""
    global session_results
    try:
        if os.path.exists("matphien.txt"):
            with open("matphien.txt", "r", encoding='utf-8') as file:
                session_history_str = file.read().strip()
                if session_history_str:
                    session_history = session_history_str.split()
                    session_results = [
                        'T' if session == '🔵' else 'X'
                        for session in session_history
                    ]
                else:
                    session_results = []
        else:
            session_results = []
            save_session_history_to_file() # Tạo file nếu chưa có
    except Exception as e:
        print(f"Lỗi khi tải lịch sử phiên: {e}")
        session_results = [] # Đảm bảo session_results là một list rỗng nếu có lỗi

# Tải dữ liệu phiên khi bot khởi động
load_session_from_file()
load_session_history_from_file()

# =====================--------------(Hàm hỗ trợ Game)--------------=====================

def send_dice_room_reply(chat_id):
    """Gửi xúc xắc và trả về giá trị"""
    try:
        # Sử dụng bot2 để gửi xúc xắc trong phòng game
        message = bot2.send_dice(chat_id=chat_id, emoji="🎲")
        return message.dice.value
    except ApiException as e:
        print(f"Lỗi API khi gửi xúc xắc: {e}")
        return None
    except Exception as e:
        print(f"Lỗi không xác định khi gửi xúc xắc: {e}")
        return None

def check_result(dice_sum):
    """Kiểm tra kết quả Tài/Xỉu từ tổng điểm xúc xắc"""
    if 11 <= dice_sum <= 18:
        return 'T' # Tài
    elif 3 <= dice_sum <= 10:
        return 'X' # Xỉu
    return 'None' # Trường hợp không thể xảy ra với 3 xúc xắc

def check_result_text(dice_sum):
    """Trả về chuỗi 'TÀI' hoặc 'XỈU'"""
    if 11 <= dice_sum <= 18:
        return 'TÀI'
    elif 3 <= dice_sum <= 10:
        return 'XỈU'
    return 'Không xác định'

def confirm_bet(user_id, bet_type, bet_amount, original_message_id, is_anonymous=False):
    """Xác nhận và xử lý đặt cược của người chơi"""
    global current_session
    global user_balance

    if user_balance.get(user_id, 0) >= bet_amount:
        if user_id not in user_bets:
            user_bets[user_id] = {'T': 0, 'X': 0}

        # Kiểm tra xem người chơi đã cược mặt đối diện chưa
        opposite_bet_type = 'T' if bet_type.upper() == 'X' else 'X'
        if user_bets[user_id][opposite_bet_type] > 0:
            try:
                bot2.send_message(GAME_ROOM_ID, "❌ Không được cược cả hai bên trong một phiên.", reply_to_message_id=original_message_id)
            except ApiException as e:
                print(f"Lỗi gửi tin nhắn đến nhóm: {e}")
            return False

        user_bets[user_id][bet_type.upper()] += bet_amount
        user_balance[user_id] -= bet_amount
        save_balance_to_file()

        encoded_user_id = f"***{str(user_id)[-4:]}"
        remaining_balance = user_balance[user_id]

        if is_anonymous:
            confirmation_message = f"🏮 **Đặt thành công kỳ XX #`{current_session}`\nLệnh {bet_type}\nSố tiền cược: `{int(bet_amount):,}`\nNgười cược: `(Ẩn Danh)`**"
            bot2.send_message(GAME_ROOM_ID, confirmation_message, parse_mode='Markdown')
        else:
            confirmation_message = f"🏮 **Đặt thành công kỳ #`{current_session}`\nLệnh {bet_type}\nSố tiền cược: `{int(bet_amount):,}`\nNgười cược: `({encoded_user_id})`**"
            bot2.send_message(GAME_ROOM_ID, confirmation_message, reply_to_message_id=original_message_id, parse_mode='Markdown')

        confirmation_message1 = f"🏮 **Bạn đặt thành công kỳ XX #`{current_session}`\nLệnh: {bet_type} - {int(bet_amount):,}\nSố dư còn lại: {int(remaining_balance):,}**"
        try:
            bot.send_message(chat_id=user_id, text=confirmation_message1, parse_mode='Markdown')
        except ApiException as e:
            print(f"Không thể gửi tin nhắn xác nhận cho người dùng {user_id}: {e}")

        return True
    else:
        if is_anonymous:
            encoded_user_id = f"(Ẩn Danh)"
            bot2.send_message(GAME_ROOM_ID, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.")
        else:
            encoded_user_id = f"***{str(user_id)[-4:]}"
            bot2.send_message(GAME_ROOM_ID, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.", reply_to_message_id=original_message_id)
        return False

def calculate_user_winnings(user_id, game_result):
    """Tính toán tiền thắng cho người chơi"""
    winnings = 0
    if user_id in user_bets:
        if game_result == 'T' and user_bets[user_id]['T'] > 0:
            winnings = 1.95 * user_bets[user_id]['T']
        elif game_result == 'X' and user_bets[user_id]['X'] > 0:
            winnings = 1.95 * user_bets[user_id]['X']
    user_balance[user_id] = user_balance.get(user_id, 0) + winnings
    return winnings

def calculate_user_losses(user_id, game_result):
    """Tính toán tiền thua cho người chơi"""
    losses = 0
    if user_id in user_bets:
        if game_result == 'T' and user_bets[user_id]['X'] > 0: # Cược X thua nếu ra T
            losses = user_bets[user_id]['X']
        elif game_result == 'X' and user_bets[user_id]['T'] > 0: # Cược T thua nếu ra X
            losses = user_bets[user_id]['T']
    return losses

def turn_on_group_chat():
    """Bật quyền gửi tin nhắn trong nhóm game"""
    permissions = ChatPermissions(can_send_messages=True)
    try:
        bot2.set_chat_permissions(GAME_ROOM_ID, permissions)
    except ApiException as e:
        print(f"Lỗi khi bật quyền nhắn tin: {e}")

def turn_off_group_chat():
    """Tắt quyền gửi tin nhắn trong nhóm game"""
    permissions = ChatPermissions(can_send_messages=False)
    try:
        bot2.set_chat_permissions(GAME_ROOM_ID, permissions)
    except ApiException as e:
        print(f"Lỗi khi tắt quyền nhắn tin: {e}")

# =====================--------------(Luồng Game)--------------=====================

def start_game():
    """Bắt đầu một phiên game mới"""
    global current_session, accepting_bets, user_bets, processed_users
    
    # Reset dữ liệu cho phiên mới
    user_bets.clear()
    processed_users.clear()

    current_session += 1
    save_session_to_file() # Lưu số phiên ngay lập tức

    accepting_bets = True

    turn_on_group_chat()
    
    # Gửi thông báo bắt đầu phiên cược
    try:
        bot2.send_message(
            GAME_ROOM_ID,
            f"<blockquote> Mời Bạn Đặt Cược Phiên #`{current_session}`</blockquote>\n\n"
            f"◉** Cách Chơi**: `T` [ số tiền ] `X` [ số tiền ]\n"
            f"◉** Cách Chơi**: `T MAX` `X MAX`\n\n"
            f"◉ Ví Dụ: **T** 10000 & **X** 10000\n\n"
            f"◉** Trả thưởng cho người thắng *1.95**\n"
            f"◉** Chỉ được cược 1 mặt trong phiên**\n"
            f"◉** Min cược: 3.000 - Max cược: 300.000**\n\n"
            f"◉** Bắt đầu cược thời gian [ 90s ]**\n"
            f"😘 **Mời các đại gia ra tay cược mạnh nhé !**\n",
            parse_mode='Markdown'
        )
    except ApiException as e:
        print(f"Lỗi gửi tin nhắn bắt đầu game: {e}")
        return # Thoát nếu không gửi được tin nhắn

    # Thời gian chờ và cập nhật tổng cược
    time.sleep(30) # 60s còn lại
    update_bet_summary()

    time.sleep(30) # 30s còn lại
    update_bet_summary()

    time.sleep(20) # 10s còn lại
    update_bet_summary()

    time.sleep(10) # Hết thời gian cược
    update_bet_summary(final=True)

    turn_off_group_chat() # Tắt nhận cược
    accepting_bets = False
    time.sleep(3) # Đợi một chút trước khi tung xúc xắc

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            f"**Bắt đầu tung xúc xắc phiên #`{current_session}`**", parse_mode='Markdown')
        time.sleep(2)

        dice_results = []
        for _ in range(3):
            dice_value = send_dice_room_reply(GAME_ROOM_ID)
            if dice_value is None:
                print("Không thể lấy giá trị xúc xắc. Bỏ qua phiên này.")
                return # Thoát nếu không tung được xúc xắc
            dice_results.append(dice_value)
            time.sleep(1) # Đợi một chút giữa mỗi lần tung

        dice_sum = sum(dice_results)
        game_result_type = check_result(dice_sum)
        game_result_text = check_result_text(dice_sum)

        session_results.append(game_result_type)
        if len(session_results) > 10:
            session_results.pop(0) # Giữ lại 10 phiên gần nhất

        save_session_history_to_file()

        total_bet_T = sum([b['T'] for b in user_bets.values()])
        total_bet_X = sum([b['X'] for b in user_bets.values()])
        
        # GỬI KẾT QUẢ RIÊNG CHO ADMIN TRƯỚC KHI CÔNG KHAI
        admin_private_message = (
            f"🎲 **KẾT QUẢ RIÊNG CHO ADMIN** 🎲\n"
            f"Phiên #`{current_session}`\n"
            f"Xúc xắc: {dice_results} (Tổng: {dice_sum})\n"
            f"Kết quả: **{game_result_text}**\n"
            f"Loại: {'🔵 Tài' if game_result_type == 'T' else '🔴 Xỉu'}\n"
            f"----------------------------------------\n"
            f"Tổng cược Tài: {int(total_bet_T):,} VNĐ\n"
            f"Tổng cược Xỉu: {int(total_bet_X):,} VNĐ\n"
        )
        bot.send_message(ADMIN_ID, admin_private_message, parse_mode='Markdown')
        time.sleep(2) # Đợi một chút trước khi công khai

        send_game_result_and_process_winnings(dice_results, dice_sum, game_result_type)

    except Exception as e:
        print(f"Lỗi trong quá trình chạy game: {e}")
        traceback.print_exc()

def update_bet_summary(final=False):
    """Cập nhật và gửi tổng cược hiện tại"""
    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI_users = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU_users = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    time_remaining_str = ""
    if not final:
        if accepting_bets: # Kiểm tra accepting_bets để tránh lỗi nếu hàm được gọi sau khi đã tắt
             # Thời gian này chỉ là ước lượng, không chính xác theo thời gian thực của phiên game
            time_remaining_str = "**⏰ Còn xx giây để cược phiên #`{current_session}`**\n" # Cập nhật thủ công hoặc tính toán chính xác hơn nếu có đồng hồ đếm ngược
    else:
        time_remaining_str = f"**⏰ Hết thời gian phiên #[`{current_session}`]**\n"

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            (
                time_remaining_str +
                f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
                f"**🔵 TÀI: `{int(total_bet_T):,}`**\n"
                f"\n"
                f"**🔴 XỈU: `{int(total_bet_X):,}`**\n\n"
                f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
                f"**👁‍🗨 TÀI: `{int(total_bet_TAI_users):,}` Người cược.**\n"
                f"\n"
                f"**👁‍🗨 XỈN: `{int(total_bet_XIU_users):,}` Người cược.**\n\n"
            ),
            parse_mode='Markdown'
        )
    except ApiException as e:
        print(f"Lỗi gửi tin nhắn tổng cược: {e}")

def send_game_result_and_process_winnings(dice_results, dice_sum, game_result_type):
    """Gửi kết quả game và xử lý tiền thắng/thua"""
    global current_session, user_balance, user_bets, processed_users
    
    last_10_sessions = session_results[-10:]
    display_last_10 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])
    last_1_session_display = "🔵" if game_result_type == 'T' else "🔴"
    game_result_text = check_result_text(dice_sum)

    total_winnings = 0
    total_losses = 0
    user_winnings_dict = {}

    users_to_process = list(user_bets.keys()) # Lấy danh sách người dùng đã cược trong phiên
    
    # Xử lý thắng/thua cho từng người chơi
    for user_id in users_to_process:
        if user_id not in processed_users: # Đảm bảo chỉ xử lý một lần
            user_win_amount = calculate_user_winnings(user_id, game_result_type)
            user_lose_amount = calculate_user_losses(user_id, game_result_type)
            
            total_winnings += user_win_amount
            total_losses += user_lose_amount
            processed_users.add(user_id) # Đánh dấu đã xử lý
            
            if user_win_amount > 0:
                user_winnings_dict[user_id] = user_win_amount
            
            # Gửi thông báo riêng cho từng người chơi
            balance = user_balance.get(user_id, 0)
            message_text = ""
            if user_win_amount > 0:
                message_text = (
                    f"🔹️ Phiên XX#`{current_session}` Bạn Đã Thắng\n"
                    f"Số tiền thắng: **{int(user_win_amount):,}**\n"
                    f"Số dư mới: **{int(balance):,}**"
                )
            elif user_lose_amount > 0:
                message_text = (
                    f"🔹️ Phiên XX#`{current_session}` Bạn Đã Thua\n"
                    f"Số tiền thua: **{int(user_lose_amount):,}**\n"
                    f"Số dư mới: **{int(balance):,}**"
                )
            else: # Không thắng không thua (ví dụ không cược hoặc cược hòa)
                continue 

            try:
                bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
            except ApiException as e:
                print(f"Không thể gửi tin nhắn kết quả cho người dùng {user_id}: {e}")
            except Exception as e:
                print(f"Lỗi khi gửi tin nhắn kết quả cho {user_id}: {e}")

    save_balance_to_file() # Lưu lại số dư sau khi cập nhật tất cả

    sorted_user_winnings = sorted(user_winnings_dict.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = ""
    if sorted_user_winnings:
        leaderboard_message = "\n".join([
            f"┃{i+1} - `{str(uid)[-4:]}` - `{int(winnings):,}`"
            for i, (uid, winnings) in enumerate(sorted_user_winnings[:10])
        ])
    else:
        leaderboard_message = "┃ Không có người thắng trong phiên này."

    time.sleep(4)
    keyboard = types.InlineKeyboardMarkup()
    # Thay đổi URL này nếu bạn có kênh kết quả riêng
    url_button = types.InlineKeyboardButton(text="Kết Quả TX [ Room ]", url="https://t.me/kqtxroomluxury") 
    keyboard.add(url_button)
    
    result_message_to_group = (
        f"**🌸 Kết Quả Xúc Xắc Phiên #`{current_session}`\n"
        f"┏━━━━━━━━━━━━━━━━┓\n"
        f"┃  {' '.join(map(str, dice_results))}  ({dice_sum})  {game_result_text} {last_1_session_display}\n"
        f"┃\n"
        f"┃ 🔎 Tổng Thắng: `{int(total_winnings):,}`\n"
        f"┃\n"
        f"┃ 🔎 Tổng Thua: `{int(total_losses):,}`\n"
        f"┃━━━━━━━━━━━━━━━━\n"
        f"┃ 🏆 Top Bảng Xếp Hạng #[`{current_session}`]\n"
        f"┃ TOP - ID - Tổng thắng\n"
        f"{leaderboard_message}\n"
        f"┗━━━━━━━━━━━━━━━━┛\n"
        f"Lịch Sử Phiên Gần Nhất\n\n"
        f"{display_last_10}\n\n"
        f"      🔵  Tài       |      🔴   XỈU\n**"
    )

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            result_message_to_group,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    except ApiException as e:
        print(f"Lỗi gửi tin nhắn kết quả đến nhóm game: {e}")

    # Gửi kết quả công khai ra nhóm kết quả nếu có
    if RESULT_CHANNEL_ID and RESULT_CHANNEL_ID != GAME_ROOM_ID:
        try:
            bot3.send_message(RESULT_CHANNEL_ID, result_message_to_group, parse_mode='Markdown', reply_markup=keyboard)
        except ApiException as e:
            print(f"Lỗi gửi tin nhắn kết quả đến kênh kết quả: {e}")

    # user_bets.clear() # Xóa cược của phiên hiện tại - đã được clear ở đầu start_game()
    # processed_users.clear() # Đã được clear ở đầu start_game()
    time.sleep(3)

def game_timer():
    """Luồng chạy game Tài Xỉu tự động"""
    while True:
        try:
            start_game()
        except Exception as e:
            print(f"Lỗi xảy ra trong luồng game_timer: {e}")
            traceback.print_exc()
        time.sleep(5) # Khoảng thời gian chờ giữa các phiên

# =====================--------------(Lệnh Admin)--------------=====================

@bot.message_handler(commands=['congtien'])
def congtien(message):
    """Lệnh admin để cộng tiền cho người chơi"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⚠️ Bạn không có quyền thực hiện thao tác này.")
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            bot.reply_to(message, "⚠️ Cú pháp không hợp lệ. Vui lòng nhập đúng: `/congtien [ID người chơi] [số tiền]`", parse_mode='Markdown')
            return

        target_user_id = int(command_parts[1])
        amount = int(command_parts[2])

        if amount <= 0:
            bot.reply_to(message, "⚠️ Số tiền cộng phải lớn hơn 0.")
            return

        load_balance_from_file() # Tải số dư mới nhất

        if target_user_id not in user_balance:
            user_balance[target_user_id] = 0
        user_balance[target_user_id] += amount

        save_balance_to_file() # Lưu số dư đã cập nhật

        bot.reply_to(message, f"✅ Đã cộng thành công **{amount:,} VNĐ** vào tài khoản của ID **{target_user_id}**.", parse_mode='Markdown')
        
        new_balance = user_balance[target_user_id]
        try:
            bot.send_message(
                target_user_id, 
                f"🎉 **Bạn vừa được cộng {amount:,} VNĐ vào tài khoản.\nSố dư hiện tại của bạn: {new_balance:,} VNĐ**", 
                parse_mode='Markdown'
            )
        except ApiException as e:
            print(f"Không thể gửi tin nhắn cho người dùng {target_user_id} (có thể do người dùng chặn bot): {e}")
            bot.reply_to(message, f"⚠️ Đã cộng tiền nhưng không thể gửi thông báo cho người dùng {target_user_id} (có thể do người dùng chặn bot).")
        except Exception as e:
            print(f"Lỗi không xác định khi gửi tin nhắn cho người dùng {target_user_id}: {e}")
            bot.reply_to(message, f"⚠️ Đã cộng tiền nhưng gặp lỗi khi gửi thông báo cho người dùng {target_user_id}.")


    except ValueError:
        bot.reply_to(message, "⚠️ Số ID người chơi hoặc số tiền không hợp lệ. Vui lòng nhập số nguyên.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Đã xảy ra lỗi: {str(e)}")
        traceback.print_exc()

# =====================--------------(Xử lý tin nhắn trong nhóm game)--------------=====================

@bot2.message_handler(func=lambda message: True)
def handle_message_in_gameroom(message):
    """Xử lý tin nhắn trong nhóm game (chủ yếu là đặt cược)"""
    # Chỉ xử lý tin nhắn trong nhóm game đã định cấu hình
    if message.chat.id != GAME_ROOM_ID:
        return

    # Luôn cố gắng xóa tin nhắn không phải lệnh cược ngay lập tức
    # Điều này giúp giữ cho cuộc trò chuyện sạch sẽ
    if not accepting_bets:
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            # Thêm độ trễ nhỏ để tránh bị giới hạn tốc độ API
            time.sleep(0.1) 
            return # Dừng xử lý nếu không chấp nhận cược
        except ApiException as e:
            # Lỗi 400 Bad Request thường do tin nhắn đã bị xóa hoặc không tồn tại
            if "Bad Request: message to delete not found" in str(e):
                pass
            else:
                print(f"Lỗi khi xóa tin nhắn khi hết thời gian cược: {e}")
        except Exception as e:
            print(f"Lỗi không xác định khi xóa tin nhắn: {e}")
        return # Dừng xử lý nếu không chấp nhận cược

    # Nếu đang chấp nhận cược
    if message.text:
        command_parts = message.text.split()
        if len(command_parts) == 2:
            bet_type = command_parts[0].upper()
            bet_amount_str = command_parts[1]

            if bet_type in ['T', 'X']:
                user_id = message.from_user.id
                
                load_balance_from_file() # Tải số dư mới nhất

                try:
                    if bet_amount_str.upper() == 'MAX':
                        # Cược tối đa là số dư hiện có hoặc 300.000, lấy giá trị nhỏ hơn
                        max_possible_bet = min(user_balance.get(user_id, 0), 300000)
                        if max_possible_bet >= 3000:
                            bet_amount = max_possible_bet
                        else:
                            bot2.send_message(GAME_ROOM_ID, "❌ Số dư của bạn không đủ để cược tối thiểu (3.000 VNĐ).", reply_to_message_id=message.message_id)
                            return
                    else:
                        bet_amount = int(bet_amount_str)

                    if 3000 <= bet_amount <= 300000:
                        confirm_bet(user_id, bet_type, bet_amount, message.message_id, is_anonymous=False)
                    else:
                        bot2.send_message(GAME_ROOM_ID, "❌ Số tiền cược phải từ 3.000 đến 300.000.", reply_to_message_id=message.message_id)
                except ValueError:
                    bot2.send_message(GAME_ROOM_ID, "❌ Số tiền cược không hợp lệ.", reply_to_message_id=message.message_id)
                except ApiException as e:
                    print(f"Lỗi API Telegram khi xử lý cược: {e}")
                except Exception as e:
                    print(f"Lỗi không xác định khi xử lý cược: {e}")
            else:
                # Xóa tin nhắn không phải lệnh T/X nhưng vẫn trong lúc nhận cược
                try:
                    bot2.delete_message(message.chat.id, message.message_id)
                    time.sleep(0.1)
                except ApiException as e:
                    if "Bad Request: message to delete not found" in str(e):
                        pass
                    else:
                        print(f"Lỗi khi xóa tin nhắn không hợp lệ: {e}")
        else:
            # Xóa tin nhắn không phải lệnh cược hợp lệ (ví dụ: quá nhiều từ)
            try:
                bot2.delete_message(message.chat.id, message.message_id)
                time.sleep(0.1)
            except ApiException as e:
                if "Bad Request: message to delete not found" in str(e):
                    pass
                else:
                    print(f"Lỗi khi xóa tin nhắn không hợp lệ: {e}")
    else:
        # Xóa tin nhắn không có text (ví dụ: ảnh, sticker) trong lúc nhận cược
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            time.sleep(0.1)
        except ApiException as e:
            if "Bad Request: message to delete not found" in str(e):
                pass
            else:
                print(f"Lỗi khi xóa tin nhắn không hợp lệ: {e}")


# =====================--------------(Kiểm tra file)--------------=====================
def check_file():
    """Kiểm tra sự tồn tại và nội dung của file thanhtran309.txt"""
    try:
        if not os.path.exists("thanhtran309.txt"):
            print("Lỗi: 'thanhtran309.txt' không tìm thấy. Bot sẽ không chạy.")
            return False
        
        with open("thanhtran309.txt", "r") as file:
            content = file.read()
            if "TRANTIENTHANH" not in content:
                print("Lỗi: 'thanhtran309.txt' thiếu chuỗi 'TRANTIENTHANH'. Bot sẽ không chạy.")
                return False
    except Exception as e:
        print(f"Lỗi khi kiểm tra file 'thanhtran309.txt': {e}. Bot sẽ không chạy.")
        return False
    return True   

# =====================--------------(Khởi chạy Bot)--------------=====================
def poll_bot(bot_instance):
    """Hàm để chạy polling cho từng bot trong một luồng riêng"""
    try:
        bot_info = bot_instance.get_me()
        print(f"Đang khởi động bot: @{bot_info.username}")
        bot_instance.polling(none_stop=True, interval=0, timeout=30)
    except Exception as e:
        print(f"Lỗi khi polling bot: {e}. Thử lại sau 5 giây...")
        time.sleep(5) # Đợi trước khi thử lại
        poll_bot(bot_instance) # Gọi lại chính nó để thử lại

if check_file():
    # Khởi tạo và chạy các luồng cho từng bot
    # Đảm bảo mỗi bot được polling trên một luồng riêng
    threading.Thread(target=poll_bot, args=(bot,)).start()
    threading.Thread(target=poll_bot, args=(bot2,)).start()
    threading.Thread(target=poll_bot, args=(bot3,)).start()

    # Khởi chạy luồng game timer
    timer_thread = threading.Thread(target=game_timer)
    timer_thread.daemon = True # Đặt daemon True để luồng này tự kết thúc khi chương trình chính kết thúc
    timer_thread.start()
    print("Bot đã khởi động và đang chạy...")
else:
    print("Bot không thể khởi động do lỗi kiểm tra file.")

