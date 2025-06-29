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
import schedule # Đảm bảo đã cài đặt: pip install schedule
from telebot.apihelper import ApiException
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler # Đảm bảo đã cài đặt: pip install APScheduler
from apscheduler.triggers.cron import CronTrigger

# =====================--------------(TOKEN BOT)--------------=====================
# THAY THẾ CÁC TOKEN NÀY BẰNG TOKEN THỰC TẾ CỦA BẠN
# LƯU Ý: Lỗi 401 Unauthorized thường do TOKEN SAI hoặc HẾT HẠN.
# VUI LÒNG KIỂM TRA LẠI TẤT CẢ CÁC TOKEN TỪ BOTFATHER ĐỂ ĐẢM BẢO CHÍNH XÁC.
API_BOT = '7324552224:AAGcEd3dg5OZuIs0bJF6QFfa4B3lgNq2rh8' # Bot chính (dùng cho lệnh /congtien và thông báo riêng cho admin)
API_BOT2 = '7975395053:AAE6xhLQ-y6BJTlvrNgWjOOWSnZMZ40AxTw' # Bot phòng game Tài Xỉu
API_BOT3 = '8027877843:AAG1z9OcCkdz8jcT3KnWuKi6BCZvlJhxu2s' # Bot thông báo (có thể không cần nếu chỉ gửi riêng admin)

# Khởi tạo các bot
bot = telebot.TeleBot(API_BOT, parse_mode='HTML') # Thiết lập parse_mode mặc định là HTML
bot2 = telebot.TeleBot(API_BOT2, parse_mode='HTML') # Thiết lập parse_mode mặc định là HTML
bot3 = telebot.TeleBot(API_BOT3, parse_mode='HTML') # Thiết lập parse_mode mặc định là HTML

# =====================--------------(Cấu hình Admin và Nhóm)--------------=====================
ADMIN_ID = 6915752059 # THAY THẾ BẰNG ID TELEGRAM CỦA ADMIN
# LƯU Ý: Lỗi "chat not found" thường do ID nhóm sai hoặc bot không có quyền admin trong nhóm.
# HÃY ĐẢM BẢO BOT ĐƯỢC THÊM VÀO NHÓM VÀ ĐƯỢC CẤP QUYỀN ADMIN ĐẦY ĐỦ.
GAME_ROOM_ID = -1002781947864 # ID nhóm phòng game Tài Xỉu
RESULT_CHANNEL_ID = -1002781947864 # ID nhóm/kênh thông báo kết quả phòng game (có thể trùng GAME_ROOM_ID hoặc là kênh riêng)

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
    try:
        with open("sodu.txt", "w") as f:
            for user_id, balance in user_balance.items():
                f.write(f"{user_id} {int(balance)}\n") # Lưu dưới dạng số nguyên
    except Exception as e:
        print(f"Lỗi khi lưu số dư vào file: {e}")

def load_balance_from_file():
    """Tải số dư của người dùng từ file sodu.txt"""
    global user_balance
    if not os.path.exists("sodu.txt"):
        try:
            open("sodu.txt", "a").close() # Tạo file nếu chưa tồn tại
        except Exception as e:
            print(f"Lỗi khi tạo file sodu.txt: {e}")
            return
            
    try:
        with open("sodu.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        user_id, balance_str = line.split()
                        user_balance[int(user_id)] = int(float(balance_str)) # Đảm bảo là số nguyên
                    except ValueError:
                        print(f"Lỗi đọc dòng trong sodu.txt: '{line}' - định dạng không hợp lệ.")
    except Exception as e:
        print(f"Lỗi khi tải số dư từ file: {e}")

# Tải số dư khi bot khởi động
load_balance_from_file()

# Đăng ký hàm save_balance_to_file để chạy khi script kết thúc
atexit.register(save_balance_to_file)

# =====================--------------(Quản lý Phiên Game)--------------=====================

def save_session_to_file():
    """Lưu số phiên hiện tại vào file phien.txt"""
    try:
        with open("phien.txt", "w") as file:
            file.write(str(current_session))
    except Exception as e:
        print(f"Lỗi khi lưu số phiên vào file: {e}")

def load_session_from_file():
    """Tải số phiên hiện tại từ file phien.txt"""
    global current_session
    if not os.path.exists("phien.txt"):
        try:
            open("phien.txt", "a").close() # Tạo file nếu chưa tồn tại
        except Exception as e:
            print(f"Lỗi khi tạo file phien.txt: {e}")
            current_session = 1
            return
            
    try:
        with open("phien.txt", "r") as file:
            content = file.read().strip()
            if content:
                current_session = int(content)
            else:
                current_session = 1
                save_session_to_file()
    except ValueError:
        print("Nội dung file phien.txt không hợp lệ. Đặt lại phiên = 1.")
        current_session = 1 # Reset nếu nội dung file không hợp lệ
        save_session_to_file()
    except Exception as e:
        print(f"Lỗi khi tải số phiên từ file: {e}")
        current_session = 1 # Đảm bảo có giá trị mặc định nếu có lỗi
        save_session_to_file()


def save_session_history_to_file():
    """Lưu lịch sử 10 phiên gần nhất vào file matphien.txt"""
    try:
        last_10_sessions = session_results[-10:]
        display_last_10 = " ".join(
            ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])
        with open("matphien.txt", "w", encoding='utf-8') as file:
            file.write(display_last_10)
    except Exception as e:
        print(f"Lỗi khi lưu lịch sử phiên vào file: {e}")

def load_session_history_from_file():
    """Tải lịch sử phiên từ file matphien.txt"""
    global session_results
    if not os.path.exists("matphien.txt"):
        try:
            open("matphien.txt", "a", encoding='utf-8').close() # Tạo file nếu chưa có
        except Exception as e:
            print(f"Lỗi khi tạo file matphien.txt: {e}")
            session_results = []
            return

    try:
        with open("matphien.txt", "r", encoding='utf-8') as file:
            session_history_str = file.read().strip()
            if session_history_str:
                session_history = session_history_str.split()
                session_results = [
                    'T' if s == '🔵' else 'X'
                    for s in session_history
                ]
            else:
                session_results = []
    except Exception as e:
        print(f"Lỗi khi tải lịch sử phiên từ file: {e}")
        session_results = [] # Đảm bảo session_results là một list rỗng nếu có lỗi

# Tải dữ liệu phiên khi bot khởi động
load_session_from_file()
load_session_history_from_file()

# =====================--------------(Hàm hỗ trợ Game)--------------=====================

def send_dice_room_reply(chat_id):
    """Gửi xúc xắc và trả về giá trị"""
    try:
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

def escape_html(text):
    """Thoát các ký tự đặc biệt trong HTML"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def confirm_bet(user_id, bet_type, bet_amount, original_message_id, is_anonymous=False):
    """Xác nhận và xử lý đặt cược của người chơi"""
    global current_session
    global user_balance

    if user_balance.get(user_id, 0) < bet_amount:
        if is_anonymous:
            bot2.send_message(GAME_ROOM_ID, f"❌ (Ẩn Danh) Không đủ số dư để đặt cược.")
        else:
            encoded_user_id = f"***{str(user_id)[-4:]}"
            bot2.send_message(GAME_ROOM_ID, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.", reply_to_message_id=original_message_id)
        return False

    if user_id not in user_bets:
        user_bets[user_id] = {'T': 0, 'X': 0}

    opposite_bet_type = 'T' if bet_type.upper() == 'X' else 'X'
    if user_bets[user_id][opposite_bet_type] > 0:
        bot2.send_message(GAME_ROOM_ID, "❌ Không được cược cả hai bên trong một phiên.", reply_to_message_id=original_message_id)
        return False

    user_bets[user_id][bet_type.upper()] += bet_amount
    user_balance[user_id] -= bet_amount
    save_balance_to_file()

    encoded_user_id = f"***{str(user_id)[-4:]}"
    remaining_balance = user_balance[user_id]

    if is_anonymous:
        confirmation_message = (
            f"🏮 <b>Đặt thành công kỳ XX #{current_session}</b>\n"
            f"Lệnh {bet_type}\n"
            f"Số tiền cược: <code>{int(bet_amount):,}</code>\n"
            f"Người cược: <code>(Ẩn Danh)</code>"
        )
        bot2.send_message(GAME_ROOM_ID, confirmation_message)
    else:
        confirmation_message = (
            f"🏮 <b>Đặt thành công kỳ #{current_session}</b>\n"
            f"Lệnh {bet_type}\n"
            f"Số tiền cược: <code>{int(bet_amount):,}</code>\n"
            f"Người cược: <code>({encoded_user_id})</code>"
        )
        bot2.send_message(GAME_ROOM_ID, confirmation_message, reply_to_message_id=original_message_id)

    confirmation_message_private = (
        f"🏮 <b>Bạn đặt thành công kỳ XX #{current_session}</b>\n"
        f"Lệnh: {bet_type} - {int(bet_amount):,}\n"
        f"Số dư còn lại: {int(remaining_balance):,}"
    )
    try:
        bot.send_message(chat_id=user_id, text=confirmation_message_private)
    except ApiException as e:
        print(f"Không thể gửi tin nhắn xác nhận riêng cho người dùng {user_id}: {e}")

    return True

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
        print(f"Lỗi API khi bật quyền nhắn tin trong nhóm {GAME_ROOM_ID}: {e}. Đảm bảo bot là admin.")
    except Exception as e:
        print(f"Lỗi không xác định khi bật quyền nhắn tin: {e}")

def turn_off_group_chat():
    """Tắt quyền gửi tin nhắn trong nhóm game"""
    permissions = ChatPermissions(can_send_messages=False)
    try:
        bot2.set_chat_permissions(GAME_ROOM_ID, permissions)
    except ApiException as e:
        print(f"Lỗi API khi tắt quyền nhắn tin trong nhóm {GAME_ROOM_ID}: {e}. Đảm bảo bot là admin.")
    except Exception as e:
        print(f"Lỗi không xác định khi tắt quyền nhắn tin: {e}")

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
    
    # Gửi thông báo bắt đầu phiên cược (sử dụng HTML)
    try:
        bot2.send_message(
            GAME_ROOM_ID,
            f"<blockquote><b>Mời Bạn Đặt Cược Phiên #{current_session}</b></blockquote>\n\n"
            f"&#x25CF; <b>Cách Chơi</b>: <code>T [số tiền]</code> hoặc <code>X [số tiền]</code>\n"
            f"&#x25CF; <b>Ví Dụ</b>: <code>T 10000</code> &amp; <code>X 10000</code>\n\n"
            f"&#x25CF; <b>Trả thưởng</b> cho người thắng <b>x1.95</b>\n"
            f"&#x25CF; <b>Chỉ được cược 1 mặt</b> trong phiên\n"
            f"&#x25CF; <b>Min cược</b>: 3.000 VNĐ - <b>Max cược</b>: 300.000 VNĐ\n\n"
            f"&#x25CF; Bắt đầu cược thời gian [<b>90s</b>]\n"
            f"😘 <b>Mời các đại gia ra tay cược mạnh nhé!</b>",
            parse_mode='HTML' # Rõ ràng chỉ định parse_mode
        )
    except ApiException as e:
        print(f"Lỗi gửi tin nhắn bắt đầu game: {e}")
        return # Thoát nếu không gửi được tin nhắn

    # Thời gian chờ và cập nhật tổng cược
    time.sleep(30) # 60s còn lại
    update_bet_summary("60s")

    time.sleep(30) # 30s còn lại
    update_bet_summary("30s")

    time.sleep(20) # 10s còn lại
    update_bet_summary("10s")

    time.sleep(10) # Hết thời gian cược
    update_bet_summary("Hết giờ", final=True)

    turn_off_group_chat() # Tắt nhận cược
    accepting_bets = False
    time.sleep(3) # Đợi một chút trước khi tung xúc xắc

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            f"<b>Bắt đầu tung xúc xắc phiên #{current_session}</b>", parse_mode='HTML')
        time.sleep(2)

        dice_results = []
        for _ in range(3):
            dice_value = send_dice_room_reply(GAME_ROOM_ID)
            if dice_value is None:
                print("Không thể lấy giá trị xúc xắc. Bỏ qua phiên này.")
                # Gửi thông báo lỗi nếu không tung được xúc xắc
                bot2.send_message(GAME_ROOM_ID, "⚠️ Lỗi hệ thống, không thể tung xúc xắc. Phiên này bị hủy.")
                return 
            dice_results.append(dice_value)
            time.sleep(1) # Đợi một chút giữa mỗi lần tung

        dice_sum = sum(dice_results)
        game_result_type = check_result(dice_sum)
        game_result_text = check_result_text(dice_sum)

        session_results.append(game_result_type)
        if len(session_results) > 10:
            session_results.pop(0) # Giữ lại 10 phiên gần nhất

        save_session_history_to_file()

        total_bet_T = sum([b['T'] for b in user_bets.values() if 'T' in b]) # Đảm bảo kiểm tra key
        total_bet_X = sum([b['X'] for b in user_bets.values() if 'X' in b]) # Đảm bảo kiểm tra key
        
        # GỬI KẾT QUẢ RIÊNG CHO ADMIN TRƯỚC KHI CÔNG KHAI
        admin_private_message = (
            f"🎲 <b>KẾT QUẢ RIÊNG CHO ADMIN</b> 🎲\n"
            f"Phiên #{current_session}\n"
            f"Xúc xắc: {dice_results} (Tổng: {dice_sum})\n"
            f"Kết quả: <b>{game_result_text}</b>\n"
            f"Loại: {'🔵 Tài' if game_result_type == 'T' else '🔴 Xỉu'}\n"
            f"----------------------------------------\n"
            f"Tổng cược Tài: {int(total_bet_T):,} VNĐ\n"
            f"Tổng cược Xỉu: {int(total_bet_X):,} VNĐ\n"
        )
        bot.send_message(ADMIN_ID, admin_private_message, parse_mode='HTML')
        time.sleep(2) # Đợi một chút trước khi công khai

        send_game_result_and_process_winnings(dice_results, dice_sum, game_result_type)

    except Exception as e:
        print(f"Lỗi trong quá trình chạy game: {e}")
        traceback.print_exc()

def update_bet_summary(time_label, final=False):
    """Cập nhật và gửi tổng cược hiện tại"""
    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets if 'T' in user_bets[user_id]])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets if 'X' in user_bets[user_id]])
    total_bet_TAI_users = sum([1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU_users = sum([1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    time_status_str = f"⏰ Còn {time_label} để cược phiên #{current_session}" if not final else f"⏰ Hết thời gian phiên #{current_session}"

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            (
                f"<b>{time_status_str}</b>\n"
                f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
                f"🔵 <b>TÀI</b>: <code>{int(total_bet_T):,}</code>\n"
                f"\n"
                f"🔴 <b>XỈU</b>: <code>{int(total_bet_X):,}</code>\n\n"
                f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
                f"👁‍🗨 <b>TÀI</b>: <code>{int(total_bet_TAI_users):,}</code> Người cược.\n"
                f"\n"
                f"👁‍🗨 <b>XỈU</b>: <code>{int(total_bet_XIU_users):,}</code> Người cược.\n\n"
            ),
            parse_mode='HTML'
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

    users_who_bet = list(user_bets.keys()) # Lấy danh sách người dùng đã cược trong phiên
    
    # Xử lý thắng/thua cho từng người chơi
    for user_id in users_who_bet:
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
                    f"🔹️ Phiên XX#{current_session} Bạn Đã Thắng\n"
                    f"Số tiền thắng: <b>{int(user_win_amount):,}</b>\n"
                    f"Số dư mới: <b>{int(balance):,}</b>"
                )
            elif user_lose_amount > 0:
                message_text = (
                    f"🔹️ Phiên XX#{current_session} Bạn Đã Thua\n"
                    f"Số tiền thua: <b>{int(user_lose_amount):,}</b>\n"
                    f"Số dư mới: <b>{int(balance):,}</b>"
                )
            else: # Không thắng không thua (ví dụ không cược)
                continue 

            try:
                bot.send_message(chat_id=user_id, text=message_text, parse_mode='HTML')
            except ApiException as e:
                print(f"Không thể gửi tin nhắn kết quả riêng cho người dùng {user_id}: {e}")
            except Exception as e:
                print(f"Lỗi không xác định khi gửi tin nhắn kết quả cho {user_id}: {e}")

    save_balance_to_file() # Lưu lại số dư sau khi cập nhật tất cả

    sorted_user_winnings = sorted(user_winnings_dict.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = ""
    if sorted_user_winnings:
        leaderboard_message = "\n".join([
            f"&#x2503;{i+1} - <code>{str(uid)[-4:]}</code> - <code>{int(winnings):,}</code>"
            for i, (uid, winnings) in enumerate(sorted_user_winnings[:10])
        ])
    else:
        leaderboard_message = "&#x2503; Không có người thắng trong phiên này."

    time.sleep(4)
    keyboard = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(text="Kết Quả TX [ Room ]", url="https://t.me/kqtxroomluxury") 
    keyboard.add(url_button)
    
    result_message_to_group = (
        f"<b>🌸 Kết Quả Xúc Xắc Phiên #{current_session}</b>\n"
        f"&#x250F;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2513;\n"
        f"&#x2503;  {escape_html(' '.join(map(str, dice_results)))}  ({dice_sum})  {game_result_text} {last_1_session_display}\n"
        f"&#x2503;\n"
        f"&#x2503; &#x1F50E; Tổng Thắng: <code>{int(total_winnings):,}</code>\n"
        f"&#x2503;\n"
        f"&#x2503; &#x1F50E; Tổng Thua: <code>{int(total_losses):,}</code>\n"
        f"&#x2503;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;\n"
        f"&#x2503; &#x1F3C6; Top Bảng Xếp Hạng #{current_session}\n"
        f"&#x2503; TOP - ID - Tổng thắng\n"
        f"{leaderboard_message}\n"
        f"&#x2517;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x2501;&#x251B;\n"
        f"Lịch Sử Phiên Gần Nhất\n\n"
        f"{display_last_10}\n\n"
        f"      🔵  Tài       |      🔴   XỈU\n"
    )

    try:
        bot2.send_message(
            GAME_ROOM_ID,
            result_message_to_group,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except ApiException as e:
        print(f"Lỗi gửi tin nhắn kết quả đến nhóm game {GAME_ROOM_ID}: {e}")

    # Gửi kết quả công khai ra nhóm kết quả nếu có
    if RESULT_CHANNEL_ID and RESULT_CHANNEL_ID != GAME_ROOM_ID:
        try:
            bot3.send_message(RESULT_CHANNEL_ID, result_message_to_group, parse_mode='HTML', reply_markup=keyboard)
        except ApiException as e:
            print(f"Lỗi gửi tin nhắn kết quả đến kênh kết quả {RESULT_CHANNEL_ID}: {e}")

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
            bot.reply_to(message, "⚠️ Cú pháp không hợp lệ. Vui lòng nhập đúng: <code>/congtien [ID người chơi] [số tiền]</code>", parse_mode='HTML')
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

        bot.reply_to(message, f"✅ Đã cộng thành công <b>{amount:,} VNĐ</b> vào tài khoản của ID <b>{target_user_id}</b>.", parse_mode='HTML')
        
        new_balance = user_balance[target_user_id]
        try:
            bot.send_message(
                target_user_id, 
                f"🎉 <b>Bạn vừa được cộng {amount:,} VNĐ vào tài khoản.</b>\n"
                f"Số dư hiện tại của bạn: <b>{new_balance:,} VNĐ</b>", 
                parse_mode='HTML'
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
    if not accepting_bets:
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            time.sleep(0.05) # Độ trễ nhỏ
            return # Dừng xử lý nếu không chấp nhận cược
        except ApiException as e:
            if "message to delete not found" in str(e): # Tin nhắn đã bị xóa
                pass
            else:
                print(f"Lỗi khi xóa tin nhắn khi hết thời gian cược: {e}")
        except Exception as e:
            print(f"Lỗi không xác định khi xóa tin nhắn: {e}")
        return 

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
            else: # Tin nhắn có 2 phần nhưng không phải T/X
                try:
                    bot2.delete_message(message.chat.id, message.message_id)
                    time.sleep(0.05)
                except ApiException as e:
                    if "message to delete not found" in str(e): pass
                    else: print(f"Lỗi khi xóa tin nhắn không hợp lệ (format): {e}")
        else: # Tin nhắn không có 2 phần
            try:
                bot2.delete_message(message.chat.id, message.message_id)
                time.sleep(0.05)
            except ApiException as e:
                if "message to delete not found" in str(e): pass
                else: print(f"Lỗi khi xóa tin nhắn không hợp lệ (số từ): {e}")
    else: # Tin nhắn không có text (ví dụ: ảnh, sticker)
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            time.sleep(0.05)
        except ApiException as e:
            if "message to delete not found" in str(e): pass
            else: print(f"Lỗi khi xóa tin nhắn không hợp lệ (không text): {e}")


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
    while True: # Vòng lặp vô hạn để tự động khởi động lại polling khi có lỗi
        try:
            bot_info = bot_instance.get_me()
            print(f"Đang khởi động bot: @{bot_info.username}")
            bot_instance.polling(none_stop=True, interval=0, timeout=30)
        except ApiException as e:
            # Xử lý các lỗi API cụ thể
            if e.result_json and e.result_json.get('error_code') == 401:
                print(f"Lỗi Unauthorized (401) cho bot @{bot_info.username}. Vui lòng kiểm tra lại token!")
            else:
                print(f"Lỗi API khi polling bot @{bot_info.username}: {e}. Thử lại sau 5 giây...")
            traceback.print_exc() # In đầy đủ lỗi để dễ debug
            time.sleep(5) 
        except Exception as e:
            print(f"Lỗi không xác định khi polling bot @{bot_info.username}: {e}. Thử lại sau 5 giây...")
            traceback.print_exc()
            time.sleep(5) 

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

