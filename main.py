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
API_BOT3 = '8027877843:AAG1z9OcCkdz8jcT3KnWuKi6BCzvlJhxu2s'

Use this token to access the HTTP API:
8027877843:AAG1z9OcCkdz8jcT3KnWuKi6BCzvlJhxu2s
Keep your token secure and store it safely, it can be used by anyone to control your bot.

For a description of the Bot API, see this page: https://core.telegram.org/bots/api' # Bot thông báo (có thể không cần nếu chỉ gửi riêng admin)

bot = telebot.TeleBot(API_BOT, parse_mode=None)
bot2 = telebot.TeleBot(API_BOT2)
bot3 = telebot.TeleBot(API_BOT3) # Giữ lại nếu bạn muốn bot3 vẫn gửi thông báo công khai

# =====================--------------(Cấu hình Admin và Nhóm)--------------=====================
ADMIN_ID = 6915752059 # THAY THẾ BẰNG ID TELEGRAM CỦA ADMIN
group_chat_id = -1002781947864 # ID nhóm thông báo chung (nếu có)
group_chat_id2 = -1002781947864 # ID nhóm phòng game Tài Xỉu
group_chat_id4 = -1002781947864 # ID nhóm thông báo kết quả phòng game (nếu có)

# =====================--------------(Biến toàn cục)--------------=====================
user_balance = {}
user_bets = {} # Lưu trữ cược của người chơi trong phiên hiện tại
current_session = 1
session_results = [] # Lịch sử kết quả các phiên
processed_users = set() # Theo dõi người chơi đã được xử lý thắng/thua trong phiên
accepting_bets = False # Trạng thái cho phép đặt cược

# =====================--------------(Kho Lưu Số Dư)--------------=====================

def save_balance_to_file():
    """Lưu số dư của người dùng vào file sodu.txt"""
    with open("sodu.txt", "w") as f:
        for user_id, balance in user_balance.items():
            balance_int = int(balance)
            f.write(f"{user_id} {balance_int}\n")

def load_balance_from_file():
    """Tải số dư của người dùng từ file sodu.txt"""
    if os.path.exists("sodu.txt"):
        with open("sodu.txt", "r") as f:
            for line in f:
                if line.strip():
                    try:
                        user_id, balance_str = line.strip().split()
                        balance = float(balance_str)
                        if balance.is_integer():
                            balance = int(balance)
                        user_balance[int(user_id)] = balance
                    except ValueError:
                        print(f"Lỗi đọc dòng trong sodu.txt: {line.strip()}")
    else:
        # Tạo file nếu chưa tồn tại
        open("sodu.txt", "a").close()

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
            current_session = int(file.read())
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
        with open("matphien.txt", "r", encoding='utf-8') as file:
            session_history = file.read().split()
            session_results = [
                'T' if session == '🔵' else 'X'
                for session in session_history
            ]
    except FileNotFoundError:
        session_results = []
        save_session_history_to_file() # Tạo file nếu chưa có

# Tải dữ liệu phiên khi bot khởi động
load_session_from_file()
load_session_history_from_file()

# =====================--------------(Hàm hỗ trợ Game)--------------=====================

def send_dice_room_reply(chat_id):
    """Gửi xúc xắc và trả về giá trị"""
    response = requests.get(
        f'https://api.telegram.org/bot{API_BOT2}/sendDice?chat_id={chat_id}'
    )
    if response.status_code == 200:
        data = response.json()
        if 'result' in data and 'dice' in data['result']:
            return data['result']['dice']['value']
    return None

def check_result(dice_sum):
    """Kiểm tra kết quả Tài/Xỉu từ tổng điểm xúc xắc"""
    if 11 <= dice_sum <= 18:
        return 'T' # Tài
    elif 3 <= dice_sum <= 10:
        return 'X' # Xỉu
    return 'None'

def check_result1(dice_sum):
    """Trả về chuỗi 'TÀI' hoặc 'XỈU'"""
    if 11 <= dice_sum <= 18:
        return 'TÀI'
    elif 3 <= dice_sum <= 10:
        return 'XỈU'
    return 'None'

def confirm_bet(user_id, bet_type, bet_amount, original_message_id, is_anonymous=False):
    """Xác nhận và xử lý đặt cược của người chơi"""
    global current_session
    global user_balance

    if user_balance.get(user_id, 0) >= bet_amount:
        if user_id not in user_bets:
            user_bets[user_id] = {'T': 0, 'X': 0}

        user_bets[user_id][bet_type.upper()] += bet_amount
        user_balance[user_id] -= bet_amount
        save_balance_to_file()

        encoded_user_id = f"***{str(user_id)[-4:]}"
        remaining_balance = user_balance[user_id]

        if is_anonymous:
            confirmation_message = f"🏮 **Đặt thành công kỳ XX #`{current_session}`\nLệnh {bet_type}\nSố tiền cược: `{int(bet_amount):,}`\nNgười cược: `(Ẩn Danh)`**"
            bot2.send_message(group_chat_id2, confirmation_message, parse_mode='Markdown')
        else:
            confirmation_message = f"🏮 **Đặt thành công kỳ #`{current_session}`\nLệnh {bet_type}\nSố tiền cược: `{int(bet_amount):,}`\nNgười cược: `({encoded_user_id})`**"
            bot2.send_message(group_chat_id2, confirmation_message, reply_to_message_id=original_message_id, parse_mode='Markdown')

        confirmation_message1 = f"🏮 **Bạn đặt thành công kỳ XX #`{current_session}`\nLệnh: {bet_type} - {int(bet_amount):,}\nSố dư còn lại: {int(remaining_balance):,}**"
        bot.send_message(chat_id=user_id, text=confirmation_message1, parse_mode='Markdown')

        # Thông báo cho admin về cược của người chơi (tùy chọn, có thể bỏ nếu admin không muốn)
        # bot.send_message(ADMIN_ID, f"Người chơi {user_id} đã cược {bet_amount:,} {bet_type} trong phiên {current_session}.", parse_mode='Markdown')

        return True
    else:
        if is_anonymous:
            encoded_user_id = f"(Ẩn Danh)"
            bot2.send_message(group_chat_id2, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.")
        else:
            encoded_user_id = f"***{str(user_id)[-4:]}"
            bot2.send_message(group_chat_id2, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.", reply_to_message_id=original_message_id)
        return False

def calculate_user_winnings(user_id, game_result):
    """Tính toán tiền thắng cho người chơi"""
    if (game_result == 'T' and user_bets[user_id]['T'] > 0) or \
       (game_result == 'X' and user_bets[user_id]['X'] > 0):
        winnings = 1.95 * (user_bets[user_id]['T'] + user_bets[user_id]['X'])
        user_balance[user_id] += winnings
        save_balance_to_file()
        return winnings
    return 0

def calculate_user_losses(user_id, game_result):
    """Tính toán tiền thua cho người chơi"""
    # Nếu kết quả không khớp với cược của người chơi, họ thua toàn bộ số tiền cược
    if (game_result != 'T' and user_bets[user_id]['T'] > 0) or \
       (game_result != 'X' and user_bets[user_id]['X'] > 0):
        return user_bets[user_id]['T'] + user_bets[user_id]['X']
    return 0

def turn_on_group_chat():
    """Bật quyền gửi tin nhắn trong nhóm game"""
    permissions = ChatPermissions(can_send_messages=True)
    try:
        bot2.set_chat_permissions(group_chat_id2, permissions)
    except ApiException as e:
        print(f"Lỗi khi bật quyền nhắn tin: {e}")

def turn_off_group_chat():
    """Tắt quyền gửi tin nhắn trong nhóm game"""
    permissions = ChatPermissions(can_send_messages=False)
    try:
        bot2.set_chat_permissions(group_chat_id2, permissions)
    except ApiException as e:
        print(f"Lỗi khi tắt quyền nhắn tin: {e}")

# =====================--------------(Luồng Game)--------------=====================

def start_game():
    """Bắt đầu một phiên game mới"""
    global current_session, accepting_bets
    current_session += 1
    accepting_bets = True

    turn_on_group_chat()
    bot2.send_message(
        group_chat_id2,
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

    time.sleep(30) # 60s còn lại

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"**⏰ Còn 60s để cược phiên #`{current_session}`**\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"**🔵 TÀI: `{int(total_bet_T):,}`**\n"
            f"\n"
            f"**🔴 XỈU: `{int(total_bet_X):,}`**\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"**👁‍🗨 TÀI: `{int(total_bet_TAI):,}` Người cược.**\n"
            f"\n"
            f"**👁‍🗨 XỈU: `{int(total_bet_XIU):,}` Người cược.**\n\n"
        ),
        parse_mode='Markdown'
    )

    time.sleep(30) # 30s còn lại

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"**⏰ Còn 30s để cược phiên #[`{current_session}`]**\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"**🔵 TÀI: `{int(total_bet_T):,}`**\n"
            f"\n"
            f"**🔴 XỈU: `{int(total_bet_X):,}`**\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"**👁‍🗨 TÀI: `{int(total_bet_TAI):,}` Người cược.**\n"
            f"\n"
            f"**👁‍🗨 XỈU: `{int(total_bet_XIU):,}` Người cược.**\n\n"
        ),
        parse_mode='Markdown'
    )

    time.sleep(20) # 10s còn lại

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"**⏰ Còn 10s để cược phiên #[`{current_session}`]**\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"**🔵 TÀI: `{int(total_bet_T):,}`**\n"
            f"\n"
            f"**🔴 XỈU: `{int(total_bet_X):,}`**\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"**👁‍🗨 TÀI: `{int(total_bet_TAI):,}` Người cược.**\n"
            f"\n"
            f"**👁‍🗨 XỈU: `{int(total_bet_XIU):,}` Người cược.**\n\n"
        ),
        parse_mode='Markdown'
    )

    time.sleep(10) # Hết thời gian cược

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"**⏰ Hết thời gian phiên #[`{current_session}`]**\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"**🔵 TÀI: `{int(total_bet_T):,}`**\n"
            f"\n"
            f"**🔴 XỈU: `{int(total_bet_X):,}`**\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"**👁‍🗨 TÀI: `{int(total_bet_TAI):,}` Người cược.**\n"
            f"\n"
            f"**👁‍🗨 XỈU: `{int(total_bet_XIU):,}` Người cược.**\n\n"
        ),
        parse_mode='Markdown'
    )

    turn_off_group_chat() # Tắt nhận cược
    accepting_bets = False
    time.sleep(6)

    bot2.send_message(
        group_chat_id2,
        f"**Bắt đầu tung xúc xắc phiên #`{current_session}`**", parse_mode='Markdown')
    time.sleep(3)

    result = [send_dice_room_reply(group_chat_id2) for _ in range(3)]
    dice_sum = sum(result)
    game_result = check_result(dice_sum)
    session_results.append(game_result)
    
    # GỬI KẾT QUẢ RIÊNG CHO ADMIN TRƯỚC KHI CÔNG KHAI
    admin_private_message = (
        f"🎲 **KẾT QUẢ RIÊNG CHO ADMIN** 🎲\n"
        f"Phiên #`{current_session}`\n"
        f"Xúc xắc: {result} (Tổng: {dice_sum})\n"
        f"Kết quả: **{check_result1(dice_sum)}**\n"
        f"Loại: {'🔵 Tài' if game_result == 'T' else '🔴 Xỉu'}\n"
        f"----------------------------------------\n"
        f"Tổng cược Tài: {int(total_bet_T):,} VNĐ\n"
        f"Tổng cược Xỉu: {int(total_bet_X):,} VNĐ\n"
    )
    bot.send_message(ADMIN_ID, admin_private_message, parse_mode='Markdown')
    time.sleep(2) # Đợi một chút trước khi công khai

    send_game_result_and_process_winnings(result, dice_sum, game_result, total_bet_T, total_bet_X)

    save_session_to_file()

def send_game_result_and_process_winnings(result, dice_sum, game_result, total_bet_T, total_bet_X):
    """Gửi kết quả game và xử lý tiền thắng/thua"""
    global current_session
    last_10_sessions = session_results[-10:]
    display_last_10 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])
    last_1_sessions = session_results[-1:]
    display_last_1 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_1_sessions])

    total_winnings = 0
    total_losses = 0
    user_winnings_dict = {}

    for user_id in user_bets:
        if user_id not in processed_users:
            try:
                user_winnings = calculate_user_winnings(user_id, game_result)
                user_losses = calculate_user_losses(user_id, game_result)
                total_winnings += user_winnings
                total_losses += user_losses
                processed_users.add(user_id)
                user_winnings_dict[user_id] = user_winnings
            except Exception as e:
                print(f"Lỗi xử lý tiền thắng/thua cho user {user_id}: {e}")

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
    url_button = types.InlineKeyboardButton(text="Kết Quả TX [ Room ]",
                                            url="https://t.me/kqtxroomluxury") # Thay link nếu có
    keyboard.add(url_button)
    bot2.send_message(
        group_chat_id2,
        (
            f"**🌸 Kết Quả Xúc Xắc Phiên #`{current_session}`\n"
            f"┏━━━━━━━━━━━━━━━━┓\n"
            f"┃  {' '.join(map(str, result))}  ({dice_sum})  {check_result1(dice_sum)} {display_last_1}\n"
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
        ),
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    # Gửi kết quả công khai ra nhóm kết quả nếu có
    # bot3.send_message(group_chat_id4, result_message, parse_mode='HTML') # Bỏ comment nếu muốn dùng bot3

    # Gửi thông báo riêng cho từng người chơi
    for user_id, user_winnings in user_winnings_dict.items():
        user_losses = calculate_user_losses(user_id, game_result) # Cần tính lại losses nếu user_winnings_dict chỉ chứa người thắng
        balance = user_balance.get(user_id, 0)
        rounded_balance = round(balance)

        if user_winnings > 0:
            message_text = (
                f"🔹️ Phiên XX#`{current_session}` Bạn Đã Thắng\n"
                f"Số tiền thắng: **{int(user_winnings):,}**\n"
                f"Số dư mới: **{int(rounded_balance):,}**"
            )
        elif user_losses > 0: # Chỉ gửi tin thua nếu thực sự có thua
            message_text = (
                f"🔹️ Phiên XX#`{current_session}` Bạn Đã Thua\n"
                f"Số tiền thua: **{int(user_losses):,}**\n"
                f"Số dư mới: **{int(rounded_balance):,}**"
            )
        else: # Trường hợp không thắng không thua (ví dụ không cược)
            continue # Bỏ qua không gửi tin nhắn

        try:
            bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
        except Exception as e:
            print(f"Không thể gửi tin nhắn kết quả cho người dùng {user_id}: {e}")

    user_bets.clear() # Xóa cược của phiên hiện tại
    processed_users.clear()
    save_balance_to_file()
    save_session_history_to_file()
    time.sleep(3)

def game_timer():
    """Luồng chạy game Tài Xỉu tự động"""
    while True:
        start_game()
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
        except Exception as e:
            print(f"Không thể gửi tin nhắn cho người dùng {target_user_id}: {e}")
            bot.reply_to(message, f"⚠️ Đã cộng tiền nhưng không thể gửi thông báo cho người dùng {target_user_id} (có thể do người dùng chặn bot).")

    except ValueError:
        bot.reply_to(message, "⚠️ Số ID người chơi hoặc số tiền không hợp lệ. Vui lòng nhập số nguyên.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Đã xảy ra lỗi: {str(e)}")
        traceback.print_exc()

# =====================--------------(Xử lý tin nhắn trong nhóm game)--------------=====================

@bot2.message_handler(func=lambda message: True)
def handle_message_in_gameroom(message):
    """Xử lý tin nhắn trong nhóm game (chủ yếu là đặt cược)"""
    global accepting_bets
    
    if accepting_bets:
        chat_id = message.chat.id
        
        # Xử lý lệnh đặt cược
        if message.text and len(message.text.split()) == 2:
            bet_type, bet_amount_str = message.text.split()

            if bet_type.upper() in ['T', 'X']:
                user_id = message.from_user.id
                
                # Load balance để đảm bảo số dư mới nhất
                load_balance_from_file()

                try:
                    if bet_amount_str.upper() == 'MAX':
                        max_bet_amount = min(user_balance.get(user_id, 0), 300000)
                        if max_bet_amount >= 3000:
                            bet_amount = max_bet_amount
                        else:
                            bot2.send_message(group_chat_id2, "❌ Số dư của bạn không đủ để cược tối thiểu (3.000 VNĐ).", reply_to_message_id=message.message_id)
                            return
                    else:
                        bet_amount = int(bet_amount_str)

                    if 3000 <= bet_amount <= 300000:
                        # Kiểm tra xem người chơi đã cược mặt đối diện chưa
                        opposite_bet_type = 'T' if bet_type.upper() == 'X' else 'X'
                        if user_bets.get(user_id) and user_bets[user_id][opposite_bet_type] > 0:
                            bot2.send_message(group_chat_id2, "❌ Không được cược cả hai bên trong một phiên.", reply_to_message_id=message.message_id)
                        else:
                            # Xác nhận cược (luôn là không ẩn danh trong nhóm game)
                            confirm_bet(user_id, bet_type, bet_amount, message.message_id, is_anonymous=False)
                    else:
                        bot2.send_message(group_chat_id2, "❌ Số tiền cược phải từ 3.000 đến 300.000.", reply_to_message_id=message.message_id)
                except ValueError:
                    # Nếu số tiền không phải số hợp lệ
                    bot2.send_message(group_chat_id2, "❌ Số tiền cược không hợp lệ.", reply_to_message_id=message.message_id)
                except ApiException as e:
                    print(f"Lỗi API Telegram khi xử lý cược: {e}")
                except Exception as e:
                    print(f"Lỗi không xác định khi xử lý cược: {e}")
        # Xóa tin nhắn không phải lệnh cược hoặc tin nhắn khi hết thời gian cược
        else:
            try:
                bot2.delete_message(message.chat.id, message.message_id)
                # if message.reply_to_message is not None: # Có thể xóa cả tin nhắn trả lời nếu muốn
                #     bot2.delete_message(message.chat.id, message.reply_to_message.message_id)
            except Exception as e:
                print(f"Lỗi khi xóa tin nhắn trong nhóm game: {e}")
    else: # Khi không chấp nhận cược
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            # if message.reply_to_message is not None:
            #     bot2.delete_message(message.chat.id, message.reply_to_message.message_id)
        except Exception as e:
            print(f"Lỗi khi xóa tin nhắn khi hết thời gian cược: {e}")

        time.sleep(1)
        # Chỉ gửi thông báo này nếu tin nhắn không phải là lệnh cược hợp lệ
        if message.text and not (message.text.split()[0].upper() in ['T', 'X'] and len(message.text.split()) == 2):
            bot2.send_message(message.chat.id, "❌ Đã Ngưng Nhận Cược. Vui Lòng Chờ Phiên Cược Sau.")


# =====================--------------(Kiểm tra file)--------------=====================
def check_file():
    """Kiểm tra sự tồn tại và nội dung của file thanhtran309.txt"""
    try:
        with open("thanhtran309.txt", "r") as file:
            content = file.read()
            if "TRANTIENTHANH" not in content:
                print("Lỗi: 'thanhtran309.txt' thiếu chuỗi 'TRANTIENTHANH'. Bot sẽ không chạy.")
                return False
    except FileNotFoundError:
        print("Lỗi: 'thanhtran309.txt' không tìm thấy. Bot sẽ không chạy.")
        return False
    return True   

# =====================--------------(Khởi chạy Bot)--------------=====================
def poll_bot(bot_instance):
    """Hàm để chạy polling cho từng bot trong một luồng riêng"""
    try:
        print(f"Đang khởi động bot: {bot_instance.get_me().username}")
        bot_instance.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Lỗi khi polling bot {bot_instance.get_me().username}: {e}")
        time.sleep(5) # Đợi trước khi thử lại

if check_file():
    # Khởi tạo và chạy các luồng cho từng bot
    thread_bot = threading.Thread(target=poll_bot, args=(bot,))
    thread_bot2 = threading.Thread(target=poll_bot, args=(bot2,))
    thread_bot3 = threading.Thread(target=poll_bot, args=(bot3,)) # Có thể bỏ nếu không dùng bot3

    thread_bot.start()
    thread_bot2.start()
    thread_bot3.start() # Bắt đầu luồng bot3

    # Khởi chạy luồng game timer
    timer_thread = threading.Thread(target=game_timer)
    timer_thread.start()
    print("Bot đã khởi động và đang chạy...")
else:
    print("Bot không thể khởi động do lỗi kiểm tra file.")

