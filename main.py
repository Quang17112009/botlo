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

#=====================--------------(TOKEN BOT @FATHER)--------------=====================
API_BOT = '7975395053:AAE6xhLQ-y6BJTlvrNgWjOOWSnZMZ40AxTw'
bot = telebot.TeleBot(API_BOT, parse_mode=None)

user_balance = {}
gitcode_amounts = {}
used_gitcodes = []
user_state = {}
user_bet_history = {}
user_bets = {}
code_timers = {}
daily_earnings = {}
clicked_links = {}
clicked_referral_links = set()
user_referrals = {}
USERCODE_FILE = "usercode.json"

def convert_to_vietnam_timezone(utc_datetime):
    vietnam_timezone = pytz.timezone('Asia/Ho_Chi_Minh')
    return utc_datetime.astimezone(vietnam_timezone)

#Thông báo nhóm
group_chat_id = -1002781947864

#=====================--------------(Kho Lưu Số Dư)--------------=====================

def save_balance_to_file():
    with open("sodu.txt", "w") as f:
        for user_id, balance in user_balance.items():
            balance_int = int(balance)
            f.write(f"{user_id} {balance_int}\n")


def load_balance_from_file():
    if os.path.exists("sodu.txt"):
        with open("sodu.txt", "r") as f:
            for line in f:
                if line.strip():
                    user_id, balance_str = line.strip().split()
                    balance = float(balance_str)
                    if balance.is_integer():
                        balance = int(balance)
                    user_balance[int(user_id)] = balance


def initialize_user_balance():
    if not user_balance:
        load_balance_from_file()


initialize_user_balance()


def on_exit():
    save_balance_to_file()


atexit.register(on_exit)


scheduler = BackgroundScheduler(timezone='Asia/Ho_Chi_Minh')


@scheduler.scheduled_job(CronTrigger(hour=0, minute=0))
def refresh_daily():
    open("topngay.json", "w").close()


@scheduler.scheduled_job(CronTrigger(day_of_week='mon', hour=0, minute=0))
def refresh_weekly():
    open("toptuan.json", "w").close()

scheduler.start()

def save_clicked_links_to_file():
  with open("clicked_links.txt", "w") as file:
      for user_id, links in clicked_links.items():
          file.write(f"{user_id}:{','.join(map(str, links))}\n")

def load_clicked_links_from_file():
  try:
      with open("clicked_links.txt", "r") as file:
          for line in file:
              user_id, links_str = line.strip().split(':')
              clicked_links[int(user_id)] = list(map(int, links_str.split(',')))
  except FileNotFoundError:
      pass 

load_clicked_links_from_file()

#=====================--------------(Api)--------------=====================


def send_dice(chat_id):
    response = requests.get(
        f'https://api.telegram.org/bot{API_BOT}/sendDice?chat_id={chat_id}')
    if response.status_code == 200:
        data = response.json()
        if 'result' in data and 'dice' in data['result']:
            return data['result']['dice']['value']
    return None


def calculate_tai_xiu(total_score):
    return "Tài" if 11 <= total_score <= 18 else "Xỉu"


def chan_le_result(total_score):
    return "Chẵn" if total_score % 2 == 0 else "Lẻ"


#=====================--------------(Gitcode)--------------=====================

GITCODE_FILE = "gitcode.txt"


def create_gitcode(amount):
    gitcode = ''.join(
        random.choices('abcdefghiklmNOPQRSTUVWXYZ0321654987', k=8))
    gitcode_amounts[gitcode] = amount
    save_gitcodes_to_file()
    return gitcode


def remove_gitcode(gitcode):
    if gitcode in gitcode_amounts:
        del gitcode_amounts[gitcode]
        save_gitcodes_to_file()


def save_gitcodes_to_file():
    with open(GITCODE_FILE, "w") as f:
        for code, value in gitcode_amounts.items():
            f.write(f"{code}:{value}\n")


def read_gitcodes():
    if not os.path.exists(GITCODE_FILE):
        return
    with open(GITCODE_FILE, "r") as f:
        for line in f:
            gitcode, amount = line.strip().split(":")
            gitcode_amounts[gitcode] = int(amount)


read_gitcodes()


@bot.message_handler(commands=['regcode'])
def create_gitcode_handler(message):
    if message.from_user.id != 6915752059:
        bot.reply_to(message, "⚠️ Bạn không có quyền thực hiện thao tác này.")
        return
    command_parts = message.text.split(' ')
    if len(command_parts) == 2:
        try:
            amount = int(command_parts[1])
            process_gitcode_amount(message, amount)
        except ValueError:
            bot.reply_to(message, "Số tiền không hợp lệ.")
    else:
        bot.reply_to(message,
                     "Vui lòng nhập đúng định dạng /regcode [số tiền].")


def process_gitcode_amount(message, amount):
    try:
        formatted_amount = "{:,.0f}".format(amount).replace(".", ",")
        gitcode = create_gitcode(amount)
        bot.reply_to(
            message,
            f"Bạn đã tạo thành công gifcode, Gitcode của bạn là: [ <code>{gitcode}</code> ] có số tiền {formatted_amount} đồng.",
            parse_mode='HTML')
    except ValueError:
        bot.reply_to(message, "Số tiền không hợp lệ.")


@bot.message_handler(commands=['code'])
def naptien_gitcode(message):
    command_parts = message.text.split(' ')
    if len(command_parts) == 2:
        gitcode = command_parts[1].strip()
        process_naptien_gitcode(message, gitcode)
    else:
        bot.reply_to(message, "Vui lòng nhập đúng định dạng /code [mã code].")


def process_naptien_gitcode(message, gitcode):
    user_id = message.from_user.id
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    user_data = {}
    if os.path.exists(USERCODE_FILE):
        with open(USERCODE_FILE, "r") as f:
            user_data = json.load(f)

    if current_date in user_data:
        if str(user_id) in user_data[current_date]:
            if user_data[current_date][str(user_id)] >= 3:
                bot.reply_to(message, "Bạn đã nhập đủ 3 code trong ngày hôm nay.")
                return
        else:
            user_data[current_date][str(user_id)] = 1
    else:
        user_data[current_date] = {str(user_id): 1}

    user_data[current_date][str(user_id)] += 1

    with open(USERCODE_FILE, "w") as f:
        json.dump(user_data, f)
        
    if gitcode in gitcode_amounts:
        amount = gitcode_amounts[gitcode]

        if gitcode not in used_gitcodes:
            used_gitcodes.append(gitcode)

            if user_id not in user_balance:
                user_balance[user_id] = 0
            user_balance[user_id] += amount

            bot.reply_to(
                message,
                f"<b>🎉 Nhập Giftcode Thành Công\nGiá Trị Code Bạn Vừa Nhập Là: {int(amount):,}.</b>"
            , parse_mode='HTML')

            bot.send_message(
                group_chat_id, f"""
<pre>Thông tin người nhập gidcode
Người chơi: {message.from_user.first_name} 
User: {user_id}
Số dư: {amount:,}đ.</pre>""", parse_mode='HTML')
            encoded_user_id = f"**{str(user_id)[-4:]}**"
            bot3.send_message(
                group_chat_id2, f"""
<b>🎉 Chúc Mừng ID: {encoded_user_id} vừa nhập code thành công, Giá trị code: {int(amount):,}</b>""", parse_mode='HTML')

            save_balance_to_file()
            remove_gitcode(gitcode)
        else:
            bot.reply_to(message,
                         "Gitcode đã sử dụng. Vui lòng nhập Gitcode khác.")
    else:
        bot.reply_to(message, "Gitcode không hợp lệ hoặc đã được sử dụng.")


@bot.message_handler(commands=['muacode'])
def mua_code(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "Cách dùng: /muacode <số lượng> <số tiền>")
            return

        quantity = int(args[1])
        amount_per_code = int(args[2])

        user_id = message.from_user.id
        total_cost = quantity * amount_per_code
        fee = total_cost * 0.05
        total_amount = total_cost + fee

        if user_id not in user_balance or user_balance[user_id] < total_amount:
            bot.reply_to(message, "Bạn không có đủ số dư để hoàn tất giao dịch này.")
            return

        user_balance[user_id] -= total_amount

        gitcodes = [create_gitcode(amount_per_code) for _ in range(quantity)]

        save_balance_to_file()
        save_gitcodes_to_file()

        total_deducted = total_cost + fee
        codes_message = ""
        for i, (gitcode, code_value) in enumerate(zip(gitcodes, [amount_per_code]*quantity), start=1):
            codes_message += f"Code {i}: <code>/code {gitcode}</code> - Giá trị code: {int(code_value):,}\n"

        bot.reply_to(message, f"<b>Ấn vào code để sao chép nhanh\nĐã mua thành công {quantity} mã code.\n\nTổng số tiền đã mua (kèm phí 5%): {int(total_deducted):,}\nSố dư sau khi mua: {int(user_balance[user_id]):,}.\n\n{codes_message}</b>", parse_mode='HTML')

    except Exception as e:
        bot.reply_to(message, f"Lỗi bot vui lòng mua lại: {str(e)}")
        traceback.print_exc()


@bot.message_handler(commands=['phatcode'])
def phatcode(message):
    if message.from_user.id != 6915752059:
        bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")
        return

    command = message.text.split()
    if len(command) != 5:
       pass

    try:
        quantity = int(command[1])
        amount = int(command[2])
        interval = int(command[3])

        schedule_code_distribution(quantity, amount, interval)

        bot.reply_to(message, f"Đã lập lịch phát {quantity} code, mỗi code có giá trị {amount} trong khoảng {interval} giây.")
    except ValueError:
        pass

def distribute_code(quantity, amount, chat_id):
    codes_message = "<blockquote>🎁 Thông báo phát code sau mỗi giờ của hệ thống</blockquote>\n"
    for i in range(1, quantity + 1):
        code = create_gitcode(amount)
        codes_message += f"<b>{i}: <code>/code {code}</code> (Giá trị: {int(amount):,})</b>\n\n"

    bot3.send_message(chat_id, codes_message, reply_markup=nhancode(), parse_mode='HTML')

def schedule_code_distribution(quantity, amount, interval):
    chat_id = group_chat_id2

    code_timers[chat_id] = Timer(interval, distribute_code, args=(quantity, amount, chat_id))
    code_timers[chat_id].start()

def nhancode():

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        telebot.types.InlineKeyboardButton("👉 Nhập code tại bot 👈",
                                           url="https://t.me/toolviphahaa")),

    return markup

@bot.message_handler(commands=["start"])
def show_main_menu(msg):
    user_id = msg.from_user.id

    if user_id not in user_balance:
        user_balance[user_id] = 0  
        save_balance_to_file()  

    if msg.text.startswith('/start ') and len(msg.text.split()) > 1:
        referrer_id = int(msg.text.split()[1])

        if referrer_id in user_balance and user_id not in clicked_referral_links:
            bonus_amount = 0
            user_balance[referrer_id] += bonus_amount
            daily_earnings.setdefault(referrer_id, 0)
            daily_earnings[referrer_id] += bonus_amount
            clicked_referral_links.add(user_id)
            user_referrals.setdefault(referrer_id, []).append(user_id)
            save_balance_to_file()

            bot.send_message(referrer_id, f"🎉 Bạn đã nhận được 0 đồng từ lượt đặt cược của người chơi mới ({msg.from_user.first_name}).")
        else:
            bot.send_message(user_id, "❌ Người giới thiệu không hợp lệ hoặc bạn đã nhấp vào liên kết rồi.")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    rows = [
        ["👤 Tài khoản", "🎲 Danh sách game"],
        ["🧑🏼‍💻 Hỗ trợ", "🌺 Hoa hồng"],
        ["🎖 Đua top"],
    ]

    for row in rows:
        markup.row(*[types.KeyboardButton(button_text) for button_text in row])

    photo_url = "https://i.imgur.com/DMHBMRn.jpeg"
    caption = """
<b>Chào Mừng Bạn Đã Đến Với Sân Chơi Giải Trí</b>

         <code>LUXURY ROOM TÀI XỈU VIP</code>

<b>Game Xanh Chín Nói Không Với Chỉnh Cầu</b>

<b>👉 Cách chơi đơn giản, tiện lợi 🎁</b>

<b>👉 Nạp rút nhanh chóng, đa dạng hình thức 💸</b>

<b>👉 Có Nhiều Phần Quà Dành Cho Người Chơi Mới 🤝</b>

<b>👉 Đua top thật hăng, nhận quà cực căng 💍</b>

<b>👉 An toàn, bảo mật tuyệt đối 🏆</b>

<b>⚠️ Chú ý đề phòng lừa đảo, Chúng Tôi Không inbox Trước ⚠️</b>
"""
    bot.send_photo(msg.chat.id,
                   photo_url,
                   caption=caption,
                   reply_markup=markup,
                   parse_mode='HTML')



@bot.message_handler(func=lambda message: message.text == "👤 Tài khoản")
def handle_check_balance_button(msg):
    check_balance(msg)


@bot.message_handler(func=lambda message: message.text == "🎲 Danh sách game")
def handle_game_list_button(msg):
    show_game_options(msg)


@bot.message_handler(func=lambda message: message.text == "🧑🏼‍💻 Hỗ trợ")
def handle_1_list_button(msg):
    show_admin_hotro(msg)



@bot.message_handler(func=lambda message: message.text == "🌺 Hoa hồng")
def handle_2_list_button(msg):
    show_friend_options(msg)

@bot.message_handler(func=lambda message: message.text == "🎖 Đua top")
def handle_3_list_button(msg):
    show_duatop_one(msg)

def show_duatop_one(msg):
    photo_link = "https://i.imgur.com/DMHBMRn.jpeg"
    bot.send_photo(msg.chat.id,
                   photo_link,
                   caption=f"""
<blockquote>Top Cược Ngày Trả Thưởng Vào 12h Trưa Hôm Sau</blockquote>
<b>🥇Top 1: 44.444</b>
<b>🥈Top 2: 23.456</b>
<b>🥉Top 3: 12.345</b>

<blockquote>Top Cược Tuần Trả Thưởng Vào 12h Trưa Thứ 2 Tuần Sau</blockquote>
<b>🥇Top 1: 88.888</b>
<b>🥈Top 2: 45.678</b>
<b>🥉Top 3: 19.999</b>

<b>Vui Lòng Chọn BXH Để Xem Chi Tiết</b>
          """,
                   parse_mode='HTML',
                   reply_markup=duatop())

def duatop():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        telebot.types.InlineKeyboardButton("🥉 Top Ngày",
                                           callback_data="top_ngay"),
        telebot.types.InlineKeyboardButton("🥈 Top Tuần",
                                           callback_data="top_tuan"))

    return markup

@bot.callback_query_handler(func=lambda call: call.data == 'top_ngay')
def show_top_ngay(call):
    vietnam_timezone = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time_vietnam = convert_to_vietnam_timezone(datetime.now())
    formatted_date = current_time_vietnam.strftime("%d/%m/%Y")

    with open("topngaybxh.json", "r") as lichsucuoc_file:
        user_bets_dict = defaultdict(int)
        user_daily_bets = defaultdict(int)
        for line in lichsucuoc_file:
            data = json.loads(line)
            for uid, amount in data.items():
                user_bets_dict[int(uid)] += amount
                user_daily_bets[int(uid)] += amount

    top_users = sorted(user_bets_dict.items(), key=lambda x: x[1], reverse=True)[:3]

    with open("topngay.json", "w") as topngay_file:
        for i, (user_id, bet_amount) in enumerate(top_users, start=1):
            formatted_bet_amount = "{:,.0f}".format(bet_amount)
            formatted_user_id = str(user_id).ljust(10)
            topngay_file.write(f"{i} | {formatted_user_id} | {formatted_bet_amount}\n")

    message_content = f'''
Top cược ngày: {formatted_date}
Top | ID       | Tiền cược
'''

    with open("topngay.json", "r") as topngay_file:
        topngay_content = topngay_file.read()
        message_content += topngay_content

    user_id = call.from_user.id
    if user_id in user_daily_bets:
        user_daily_bet_amount = "{:,.0f}".format(user_daily_bets[user_id])
        message_content += f'\n\nBạn đã cược: {user_daily_bet_amount} VND trong ngày.'

    bot.send_message(call.message.chat.id, message_content, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'top_tuan')
def show_top_tuan(call):
    with open("toptuanbxh.json", "r") as lichsucuoc_file:
        user_bets_dict = defaultdict(int)
        user_weekly_bets = defaultdict(int)
        for line in lichsucuoc_file:
            data = json.loads(line)
            for uid, amount in data.items():
                user_bets_dict[int(uid)] += amount
                user_weekly_bets[int(uid)] += amount

    top_users = sorted(user_bets_dict.items(), key=lambda x: x[1], reverse=True)[:3]

    with open("toptuan.json", "w") as toptuan_file:
        for i, (user_id, bet_amount) in enumerate(top_users, start=1):
            formatted_bet_amount = "{:,.0f}".format(bet_amount)
            formatted_user_id = str(user_id).ljust(10)
            toptuan_file.write(f"{i} | {formatted_user_id} | {formatted_bet_amount}\n")

    vietnam_timezone = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time_vietnam = convert_to_vietnam_timezone(datetime.now())
    week_number = current_time_vietnam.strftime("%W")

    message_content = f'''
Top cược tuần: {week_number}
Top | ID       | Tiền cược
'''

    with open("toptuan.json", "r") as toptuan_file:
        toptuan_content = toptuan_file.read()
        message_content += toptuan_content

    user_id = call.from_user.id
    if user_id in user_weekly_bets:
        user_weekly_bet_amount = "{:,.0f}".format(user_weekly_bets[user_id])
        message_content += f'\n\nBạn đã cược: {user_weekly_bet_amount} VND trong tuần.'

    bot.send_message(call.message.chat.id, message_content, parse_mode='HTML')



#=====================--------------(balance)--------------=====================

def check_balance(msg):
    user_id = msg.from_user.id
    balance = user_balance.get(user_id, 0)
    rounded_balance = round(balance)
    photo_link = "https://i.imgur.com/DMHBMRn.jpeg"
    bot.send_photo(msg.chat.id,
                   photo_link,
                   caption=f"""
👤 <b>Tên Tài Khoản</b>: [ <code>{msg.from_user.first_name}</code> ]
💳 <b>ID Tài Khoản</b>: [ <code>{msg.from_user.id}</code> ]
💰 <b>Số Dư</b>: [ <code>{rounded_balance:,}</code> ] đ
          """,
                   parse_mode='HTML',
                   reply_markup=user_menu())


def user_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        telebot.types.InlineKeyboardButton("💸 Nạp tiền",
                                           callback_data="nap_tien"),
        telebot.types.InlineKeyboardButton("💸 Rút tiền",
                                           callback_data="rut_tien"))

    markup.add(
        telebot.types.InlineKeyboardButton("📉 Lịch sử nạp",
                                           callback_data="show_history_1"),
        telebot.types.InlineKeyboardButton("📈 Lịch sử rút",
                                           callback_data="show_history"))

    markup.add(
        telebot.types.InlineKeyboardButton("📦 Nhập gitcode",
                                           callback_data="nhan_gitcode"),
        telebot.types.InlineKeyboardButton("🎁 Mua Gitcode",
                                           callback_data="mua_gitcode"))
    markup.add(
        telebot.types.InlineKeyboardButton("🤝 Chuyển tiền",
                                           callback_data="chuyen_tien"))

    return markup


@bot.callback_query_handler(func=lambda call: call.data == 'rut_tien')
def show_menu_rut_tien(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("Momo",
                                           callback_data="rut_tien_momo"),
        telebot.types.InlineKeyboardButton("Bank",
                                           callback_data="rut_tien_bank"))
    bot.send_message(call.message.chat.id,
                     "Vui lòng chọn phương thức rút tiền",
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'nap_tien')
def show_menu_nap_tien(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("Momo",
                                           callback_data="nap_tien_momo"),
        telebot.types.InlineKeyboardButton("Bank",
                                           callback_data="nap_tien_bank"))
    bot.send_message(call.message.chat.id,
                     "Lựa chọn phương thức nạp tiền",
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'nap_tien_momo')
def show_nap_tien_momo(call):
    user_id = call.from_user.id

    message_content = f'''
📖 Thông tin chuyển khoản [Momo] 

🏧 Số Tài Khoản: <code>0366530822</code>

🏧Chủ Tài Khoản: <code>NINH DIEP LINH</code>

🏧 Nội Dung: [ <code>{user_id}</code> ] 

🛑 Vui Lòng Nhập Đúng Nội Dung Để Tiền Vào Nhanh Nhất.
🛑 Chụp Lại Bill Sau Mỗi Đơn Nạp ! 
🛑 ADMIN HỖ TRỢ : t.me/hehetoolvip
'''
    bot.send_message(call.message.chat.id, message_content, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'nap_tien_bank')
def show_nap_tien_bank(call):
    user_id = call.from_user.id

    message_content = f'''
🌸 KÊNH NẠP TIỀN 💸

📖 Thông tin chuyển khoản [Bank] 

🏧 Ngân Hàng: MB BANK

🏧 STK: <code>0939766383</code>

🏧 CTK: <code>Nguyen Huynh Nhut Quang</code>

🏧 Nội Dung: [ <code>{user_id}</code> ] 

🛑 Vui Lòng Nhập Đúng Nội Dung Để Tiền Vào Nhanh Nhất.
🛑 Chụp Lại Bill Sau Mỗi Đơn Nạp ! 
🛑 ADMIN HỖ TRỢ : t.me/heheviptool
'''

    bot.send_message(call.message.chat.id, message_content, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'nhan_gitcode')
def show_nhan_gitcode(call):

    bot.send_message(
        call.message.chat.id, f'''
<b>🗂 Để Nhập Giftcode, Vui Lòng Thực Hiện Theo Cú Pháp Sau:</b>

<b>/code [dấu cách] mã giftcode</b>

<b>♨️ VD:  /code LUXURY2025</b>
''', parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'chuyen_tien')
def show_chuyen_tien(call):

    bot.send_message(
        call.message.chat.id, f'''
<blockquote>💸 Vui Lòng Thực Hiện Theo Hướng Dẫn Sau:</blockquote>

<b>/chuyentien [dấu cách] ID nhận tiền [dấu cách] Số tiền muốn chuyển</b>

<b>🔹️VD: /chuyentien 123456789 200000</b>

<b>⚡️ Phí chuyển tiền là 5% được trừ vào tài khoản người chuyển</b>
''', parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'rut_tien_bank')
def show_rut_tien_bank(call):

    bot.send_message(
        call.message.chat.id, f'''
🌸 KÊNH RÚT TIỀN 💸

🛑 Vui Lòng Thực Hiện Theo Hướng Dẫn Sau : 

👉 /rutbank [dấu cách] Mã ngân hàng [dấu cách]  Số tài khoản [dấu cách] Tên chủ tài khoản [dấu cách] Số tiền muốn rút.

👉 VD:  Muốn rút 100k đến TK số 01234567890 tại Ngân hàng Vietcombank. Thực hiện theo cú pháp sau:

/rutbank MBB 0987654321 NguyenVanA 10000

⚠️ Lưu ý: Không hỗ trợ hoàn tiền nếu bạn nhập sai thông tin Tài khoản. 

🌸 TÊN NGÂN HÀNG - MÃ NGÂN HÀNG 💦

📌 Vietcombank => VCB
📌 BIDV => BIDV
📌 Vietinbank => VTB
📌 Techcombank => TCB
📌 MB Bank => MBB
📌 Agribank => AGR
📌 TienPhong Bank => TPB
📌 SHB bank => SHB
📌 ACB => ACB
📌 Maritime Bank => MSB
📌 VIB => VIB
📌 Sacombank => STB
📌 VP Bank => VPB
📌 SeaBank => SAB
📌 Shinhan bank Việt Nam => SHBVN
📌 Eximbank => EIB
📌 KienLong Bank => KLB
📌 Dong A Bank => DAB
📌 HD Bank => HDB
📌 LienVietPostBank => LVPB
📌 VietBank => VBB
📌 ABBANK => ABB
📌 PG Bank => PGB
📌 PVComBank => PVC
📌 Bac A Bank => BAB
📌 Sai Gon Commercial Bank => SCB
📌 BanVietBank => VCCB
📌 Saigonbank => SGB
📌 Bao Viet Bank => BVB
📌 Orient Commercial Bank => OCB

⚠Min rút 10.000 
''')


@bot.callback_query_handler(func=lambda call: call.data == 'rut_tien_momo')
def show_rut_tien_momo(call):

    bot.send_message(
        call.message.chat.id, f'''
💸 Vui lòng thực hiện theo hướng dẫn sau:

/rutmomo [dấu cách] SĐT [dấu cách] Số tiền muốn rút

➡️ VD  /rutmomo 0987112233 200000

⚠️ Lưu ý: ❌ Không hỗ trợ hoàn tiền nếu bạn nhập sai thông tin SĐT. 

❗️ Phí rút tiền: 1.900đ cho các giao dịch dưới 10.000đ. ( RÚT TỪ 50.000đ TRỞ LÊN KHÔNG MẤT PHÍ RÚT)
''')



@bot.callback_query_handler(func=lambda call: call.data == 'show_history')
def show_history(call):
    try:
        user_id = call.from_user.id

        with open("historyrut.txt", "r") as history_file:
            user_history = ""
            for line in history_file:
                if str(user_id) in line:
                    user_history += line

        if user_history:
            bot.send_message(
                call.message.chat.id,
                f"Loại | UID | Số Tiền | Ngân Hàng | STK | Tên Chủ TK |\n{user_history}"
            )
        else:
            bot.send_message(call.message.chat.id, "Lịch sử của bạn là trống.")
    except Exception as e:
        print(str(e))
        bot.send_message(call.message.chat.id, "Đã xảy ra lỗi khi lấy lịch")


@bot.callback_query_handler(func=lambda call: call.data == 'show_history_1')
def show_history_1(call):
    try:
        with open("historynap.txt", "r") as history_file:
            history = history_file.read()

        if history.strip():
            bot.send_message(
                call.message.chat.id,
                f"Loại | Tên | Số Tiền | Ngân Hàng | STK | Tên Chủ TK |\n{history}"
            )
        else:
            bot.send_message(call.message.chat.id, "Không có lịch sử nạp.")
    except Exception as e:
        print(str(e))
        bot.send_message(call.message.chat.id, "Đã xảy ra lỗi khi lấy lịch")


@bot.callback_query_handler(func=lambda call: call.data == "mua_gitcode")
def show_mua_gitcode(call):

    bot.send_message(
        call.message.chat.id, f'''
<b>🎉 Để mua Giftcode, chat với lệnh sau:</b>

<b>/muacode [dấu cách] số lượng [dấu cách] giá trị mỗi code</b>

<b>Ví dụ: /muacode 1 5000</b>

<b>Phí mua Giftcode là 5%</b>
    ''', parse_mode='HTML')



@bot.message_handler(commands=['chuyentien'])
def chuyentien(message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(
                message,
                "Vui lòng nhập đúng định dạng: /chuyentien [ID người nhận] [số tiền]"
            )
            return

        recipient_id = int(parts[1])
        amount = float(parts[2])

        sender_id = message.from_user.id
        if sender_id not in user_balance:
            bot.reply_to(message,
                         "Số dư của bạn không đủ để thực hiện giao dịch.")
            return

        sender_balance = user_balance[sender_id]
        if amount > sender_balance:
            bot.reply_to(message,
                         "Số dư của bạn không đủ để thực hiện giao dịch.")
            return

        transfer_fee = amount * 0.05
        net_transfer_amount = amount - transfer_fee

        user_balance[sender_id] -= amount

        if recipient_id not in user_balance:
            user_balance[recipient_id] = 0
        user_balance[recipient_id] += net_transfer_amount

        save_balance_to_file()

        sender_formatted_balance = '{:,.0f} VNĐ'.format(
            user_balance[sender_id])
        recipient_formatted_balance = '{:,.0f} VNĐ'.format(
            user_balance[recipient_id])
        bot.send_message(
            sender_id,
            f"<b>♨️ Bạn Đã Chuyển: {net_transfer_amount:,.0f} Cho Người Dùng\nCó ID: {recipient_id} Thành Công.\nSố dư mới của bạn: {sender_formatted_balance}\n\n🔹️ Phí Chuyển 5% Sẽ Trừ Vào Ví Của Bạn 🔹️</b>", parse_mode='HTML'
        )
        bot.send_message(
            recipient_id,
            f"<b>🍀 Bạn Đã Nhận Được {net_transfer_amount:,.0f} Từ Người Chơi Có ID {sender_id}.\nSố Dư Mới Của Bạn: {recipient_formatted_balance}</b>", parse_mode='HTML'
        )

        group_message = f"Người dùng có ID {sender_id} đã chuyển {net_transfer_amount:,.0f} VNĐ cho người dùng có ID {recipient_id}."
        bot.send_message(chat_id=group_chat_id, text=group_message)

    except ValueError:
        bot.reply_to(message, "Vui lòng nhập số tiền là một số hợp lệ.")


@bot.message_handler(commands=['naptien'])
def naptien(message):
    user_id = message.from_user.id
    balance = user_balance.get(user_id, 0)
    if message.from_user.id != 6262408926:
        bot.reply_to(message, "⚠️ Bạn không có quyền thực hiện thao tác này.")
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            raise ValueError("Sử dụng cú pháp không hợp lệ. Vui lòng nhập đúng cú pháp: /naptien [UID] [số tiền]")

        user_id = int(command_parts[1])
        amount = int(command_parts[2])

        load_balance_from_file()

        balance_from_file = user_balance.get(user_id, 0)
        rounded_balance = round(balance_from_file)

        if user_id in user_balance:
            user_balance[user_id] += amount
        else:
            user_balance[user_id] = amount

        save_balance_to_file()

        bot.reply_to(message, f"<b>✅ Nạp tiền thành công\nSố tiền {amount:,}\nVNĐ ID {user_id}.</b>", parse_mode='HTML')
        
        encoded_user_id = f"**{str(user_id)[-4:]}**"
        bot3.send_message(
            group_chat_id2,
            f"💸 <b>Người dùng: {encoded_user_id}\n\n♻️ Nạp tiền thành công {amount:,} VNĐ</b>", parse_mode='HTML'
        )
        bot.send_message(user_id, f"<blockquote>Đơn Nạp Của Bạn Đã Được Xét Duyệt</blockquote>\n<b>🍀 Bạn Được Cộng {amount:,} Vào Ví.\nSố Dư Mới Của Bạn: {rounded_balance:,}</b>", parse_mode='HTML')
    except ValueError as e:
        bot.reply_to(message, str(e))

@bot.message_handler(commands=['trutien'])
def trutien(message):
   # Kiểm tra quyền hạn của người gửi (admin)
   if message.from_user.id != 6262408926:
       bot.reply_to(message, "⚠️ Bạn không có quyền thực hiện thao tác này.")
       return

   # Phân tích thông điệp từ admin
   try:
       command_parts = message.text.split()
       if len(command_parts) != 3:
           raise ValueError("Sử dụng cú pháp không hợp lệ. Vui lòng nhập đúng cú pháp: /trutien [dấu cách]uid [dấu cách]số tiền muốn trừ")

       user_id = int(command_parts[1])
       amount = int(command_parts[2])

       # Kiểm tra số tiền trong tài khoản
       if user_id in user_balance:
           if user_balance[user_id] >= amount:
               user_balance[user_id] -= amount
           else:
               bot.reply_to(message, "⚠️ Số dư trong tài khoản không đủ để thực hiện giao dịch.")
               return
       else:
           bot.reply_to(message, "⚠️ Người dùng không tồn tại trong hệ thống.")
           return

       # Lưu số dư mới vào file
       save_balance_to_file()

       # Gửi thông báo xác nhận cho admin
       bot.reply_to(message, f"✅ Số tiền {amount:,} VNĐ đã được trừ từ tài khoản của người dùng có ID {user_id}.")

       # Gửi thông báo cho người dùng xác nhận số tiền đã bị trừ
       bot.send_message(user_id, f"⚠️ Số tiền {amount:,} VNĐ đã bị trừ từ tài khoản của bạn.")
   except ValueError as e:
       bot.reply_to(message, str(e))


#Bảng game-------------------------------------------------------------------------------------


def show_game_options(msg):
    photo_link = 'https://i.imgur.com/DMHBMRn.jpeg'

    bot.send_photo(msg.chat.id,
                   photo_link,
                   caption="""
<b>LUXURY ROOM TÀI XỈU VIP</b>\n
<b>👇Hãy chọn các game phía dưới nhé👇</b>
        """,
                   reply_markup=create_game_options(),
                   parse_mode='HTML')


def create_game_options():
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        telebot.types.InlineKeyboardButton(
            "🎲 Tài Xỉu Room", callback_data="game_txrom"))

    return markup


#hỗ trợ-------------------------------------------------------------
def show_admin_hotro(msg):
    photo_link = "https://i.imgur.com/DMHBMRn.jpeg"
    bot.send_photo(msg.chat.id,
                   photo_link,
                   caption=f"""
THÔNG TIN HỖ TRỢ GAME PHÍA DƯỚI 
🚨 HỖ TRỢ 24/24 🚨
          """,
                   parse_mode='HTML',
                   reply_markup=user_hotro())


def user_hotro():
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)

    markup.add(
        telebot.types.InlineKeyboardButton("Quản Lý",
                                           url="https://t.me/heheviptool"),
        telebot.types.InlineKeyboardButton("Quản Trị Viên",
                                           url="https://t.me/mrdoom99"),
        telebot.types.InlineKeyboardButton("Home",
                                           url="https://t.me/heheviptool"))

    return markup


def show_friend_options(msg):
    user_id = msg.from_user.id
    total_referrals = len(user_referrals.get(user_id, []))
    daily_earning = daily_earnings.get(user_id, 0)
    referral_link = f"https://t.me/luxury_cltx_bot?start={user_id}"

    bot.send_message(msg.chat.id,
                     text=f"""
<b>🌸 Tham Gia Mời Bạn Ngay Nhận Quà Trao Tay 💥</b>

<b>👉 Link mời bạn bè của bạn: <blockquote><code>{referral_link}</code></blockquote></b>

<b>☝️ CLICK VÀO LINK TRÊN ĐỂ COPPY VÀ GỬI CHO BẠN BÈ</b>

<b>🌺 Nhận ngay HOA HỒNG bằng 2% số tiền thua cược từ người chơi mà bạn giới thiệu.</b>

<b>🌺 Tổng hoa hồng 🌺 : {round(daily_earning):,}</b>

<b>🤝 Số Lượng Cấp Dưới : {total_referrals}</b>

<b>Hoa hồng nhận được hôm nay:</b>
<b>Hoa hồng nhận được tuần này:</b>
""",
                     parse_mode='HTML')



@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def game_callback(call):
    if call.data == "game_txrom":
        show_txroom_options(call.from_user.id)
        pass

def txroom():

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        telebot.types.InlineKeyboardButton("Game Tài Xỉu Room",
                                           url="https://t.me/toolviphahaa")),

    return markup

def show_txroom_options(user_id):

    bot.send_message(user_id,
                     """
🎲 TÀI - XỈU ROOM 🎲

👉 Khi BOT trả lời mới được tính là đã đặt cược thành công. 

👉 Nếu BOT không trả lời => Lượt chơi không hợp lệ và không bị trừ tiền trong tài khoản.

👉 Kết Quả Xanh Chính Nói Không Với Chỉnh Cầu.

🔖 Thể lệ như sau

[Lệnh] ➤ [Tỷ lệ] ➤ [Kết quả]

T   |  1.9  | 11 - 18
X   |  1.9  | 3 - 10 
TAI MAX   |  1.9  | 11 - 18
XIU MAX   |  1.9  | 3 - 10 

* Lưu ý: có thể cược chữ nhỏ hoặc to nhé !

🎮 CÁCH CHƠI: Chat tại đây nội dung sau

👉 Đặt: [Lệnh] [dấu cách] [Số tiền cược]

[ Ví dụ: XIU 1000 hoặc TAI 1000 & XIU ALL hoặc TAI ALL ]

""",
                     parse_mode='HTML', reply_markup=txroom())


#===========-------------------===========( Hàm rút tiền )===========------------================---------------========

@bot.message_handler(commands=['rutbank'])
def handle_ruttien(message):
    try:
        command_parts = message.text.split()[1:]
        if len(command_parts) != 4:
            bot.reply_to(
                message,
                "Sai cú pháp. Vui lòng sử dụng /rutbank [tên ngân hàng] [số tài khoản] [chủ tài khoản] [số tiền]"
            )
            return

        bank_name = command_parts[0]
        account_number = command_parts[1]
        account_holder = command_parts[2]
        amount = float(command_parts[3])

        if amount < 10000:
            bot.reply_to(message,
                         "Số tiền rút từ Bank phải ít nhất là 10,000 VNĐ.")
            return

        user_id = message.from_user.id
        if user_id not in user_balance:
            bot.reply_to(message,
                         "Bạn chưa có số dư trong tài khoản của mình.")
            return

        if user_balance[user_id] < amount:
            bot.reply_to(message, "Số dư không đủ để rút tiền.")
            return

        user_balance[user_id] -= amount
        save_balance_to_file()

        amount_str = '{:,.0f}'.format(amount).replace(',', '.')
        encoded_amount_str = '{:,.0f}'.format(amount).replace('.', ',')

        with open("historyrut.txt", "a") as history_file:
            history_file.write(
                f"Bank {user_id} {amount_str} {bank_name} {account_number} {account_holder}\n"
            )

        bot.reply_to(
            message,
            f"<b>Bạn Tạo Đơn Rút Tiền Thành Công, Vui Lòng Chờ Xét Duyệt.\nSố tiền rút: {amount_str}\nNgân hàng: {bank_name}\nSố tài khoản: {account_number}\nChủ tài khoản: {account_holder}</b>", parse_mode='HTML'
        )
        time.sleep(1)
        bot.send_message(
            group_chat_id,
            f"<pre>Người dùng {user_id}\nĐã rút tiền từ Bank.\nSố tiền: {amount_str}\nNgân hàng: {bank_name}\nSố tài khoản: {account_number}\nChủ tài khoản: {account_holder}</pre>"
        , parse_mode='HTML')
        time.sleep(1)
        encoded_user_id = f"**{str(user_id)[-4:]}**"
        bot3.send_message(
            group_chat_id2,
            f"💸 <b>Người dùng {encoded_user_id}\n\n- Rút tiền thành công {encoded_amount_str} về Bank: {bank_name}</b>", parse_mode='HTML'
        )

    except Exception as e:
        pass
        bot.reply_to(message,
                     "Đã xảy ra lỗi trong quá trình xử lý yêu cầu của bạn.")
        pass #print(f"Error: {e}")

@bot.message_handler(commands=['rutmomo'])
def handle_rutmomo(message):
    try:
        command_parts = message.text.split()[1:]
        if len(command_parts) != 2:
            bot.reply_to(
                message,
                "Sai cú pháp. Vui lòng sử dụng /rutmomo [SĐT] [số tiền]")
            return

        phone_number = command_parts[0]
        if not phone_number.isdigit() or len(phone_number) != 10:
            bot.reply_to(message, "Số điện thoại không hợp lệ. Vui lòng nhập lại.")
            return

        try:
            amount = float(command_parts[1])
        except ValueError:
            bot.reply_to(message, "Số tiền không hợp lệ. Vui lòng nhập lại.")
            return

        if amount < 10000: 
            bot.reply_to(message, "Số tiền rút từ Momo phải ít nhất là 10,000 VNĐ.")
            return

        user_id = message.from_user.id
        if user_id not in user_balance:
            bot.reply_to(message, "Bạn chưa có số dư trong tài khoản của mình.")
            return

        if user_balance[user_id] < amount:
            bot.reply_to(message, "Số dư không đủ để rút tiền.")
            return

        user_balance[user_id] -= amount
        save_balance_to_file()
        amount_formatted = '{:,.0f}'.format(amount).replace(',', '.')

        with open("historyrut.txt", "a") as history_file:
            history_file.write(f"Momo {user_id} {amount_formatted} {phone_number}\n")

        bot.reply_to(
            message,
            f"<b>Bạn Tạo Đơn Rút Tiền Thành Công, Vui Lòng Chờ Xét Duyệt.\nSố tiền: {amount_formatted}\nSố điện thoại: {phone_number}</b>",
            parse_mode='HTML'
        )

        time.sleep(1)
        bot.send_message(
            group_chat_id,
            f"<pre>Người dùng {user_id}\nĐã rút tiền qua Momo.\nSố tiền: {amount_formatted}\nSố điện thoại: {phone_number}</pre>",
            parse_mode='HTML'
        )

        time.sleep(1)
        encoded_user_id = f"**{str(user_id)[-4:]}**"
        bot3.send_message(
            group_chat_id2,
            f"💸 <b>Người dùng {encoded_user_id}\n\nRút tiền thành công {amount_formatted} về MoMo</b>",
            parse_mode='HTML'
        )

    except Exception as e:
        bot.reply_to(message, "Đã xảy ra lỗi trong quá trình xử lý yêu cầu của bạn.")
        pass #print(f"Error handling /rutmomo command: {e}")



#----------------------------------------------------------------------------------------
#CODE CỦA @thanhtran309 Telegram TXROOM vui lòng không xóa sẽ không dùng được nhaaaaaaaa#
#----------------------------------------------------------------------------------------


bot2 = telebot.TeleBot('6750084311:AAEZapSvXNIZDFUtutSPnvBiusbJITbT9To')


def send_dice_room_reply(group_chat_id2):
    response = requests.get(
        f'https://api.telegram.org/bot6750084311:AAEZapSvXNIZDFUtutSPnvBiusbJITbT9To/sendDice?chat_id=-1002015841488'
    )
    if response.status_code == 200:
        data = response.json()
        if 'result' in data and 'dice' in data['result']:
            return data['result']['dice']['value']
    return None

def load_balances_from_file():
    balances = {}
    if os.path.exists("sodu.txt"):
        with open("sodu.txt", "r") as f:
            for line in f:
                if line.strip():
                    user_id, balance_str = line.strip().split()
                    balance = float(balance_str)
                    if balance.is_integer():
                        balance = int(balance)
                    balances[int(user_id)] = balance
    return balances


def save_session_to_file():
    with open("phien.txt", "w") as file:
        file.write(str(current_session))


def load_session_from_file():
    global current_session
    try:
        with open("phien.txt", "r") as file:
            current_session = int(file.read())
    except FileNotFoundError:
        current_session = 1


def save_session_history_to_file():
    last_10_sessions = session_results[-10:]
    display_last_10 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])
    with open("matphien.txt", "w", encoding='utf-8') as file:
        file.write(display_last_10)

def load_session_history_from_file():
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

@bot2.message_handler(commands=['off'])
def turn_off(message):
    if message.chat.type != 'private':
        chat_id = message.chat.id
        permissions = ChatPermissions(can_send_messages=False)
        bot2.set_chat_permissions(chat_id, permissions)
        bot2.reply_to(message, 'off.')
    else:
        bot2.reply_to(message, 'off nhóm.')


@bot2.message_handler(commands=['on'])
def turn_on(message):
    if message.chat.type != 'private':
        chat_id = message.chat.id
        permissions = ChatPermissions(can_send_messages=True)
        bot2.set_chat_permissions(chat_id, permissions)
        bot2.reply_to(message, 'on.')
    else:
        bot2.reply_to(message, 'on nhóm.')

@bot2.message_handler(commands=['sd'])
def show_balance(message):
    if message.chat.id == group_chat_id2:
        user_id = message.from_user.id
        if user_id in user_balance:
            balance = user_balance[user_id]
            bot2.reply_to(message, f"<b>Số dư hiện tại</b>: {int(balance):,}", reply_to_message_id=message.message_id, parse_mode='HTML')
    else:
        bot2.reply_to(message, "Chỉ cho phép sử dụng tại room.")

def reset_toptuanbxh():
    with open("toptuanbxh.json", "w") as f:
        json.dump({}, f)


def reset_topngaybxh():
    with open("topngaybxh.json", "w") as f:
        json.dump({}, f)

scheduler = BackgroundScheduler()

scheduler.add_job(reset_topngaybxh, 'cron', day_of_week='*', hour=0, minute=0, second=0, timezone='Asia/Ho_Chi_Minh')
scheduler.add_job(reset_toptuanbxh, 'cron', day_of_week='mon', hour=0, minute=0, second=0, timezone='Asia/Ho_Chi_Minh')

scheduler.start()

#=============-----------==============-----------==============---------------==============
#CODE CỦA @thanhtran309 Telegram TXROOM vui lòng không xóa sẽ không dùng được nhaaaaaaaa#
#=============-----------==============-----------==============---------------==============

group_chat_id2 = -1002015841488 #thông báo nhóm room
group_chat_id3 = -1002116362947 #thông báo nhóm admin
group_chat_id4 = -1002126182643 #thông báo nhóm kqroom

current_session = 1
session_results = []
processed_users = set()
display_last_10 = ""
accepting_bets = False


def check_result(dice_sum):
    if 11 <= dice_sum <= 18:
        return 'T'
    elif 3 <= dice_sum <= 10:
        return 'X'
    else:
        return 'None'

def check_result1(dice_sum):
    if 11 <= dice_sum <= 18:
        return 'TÀI'
    elif 3 <= dice_sum <= 10:
        return 'XỈU'
    else:
        return 'None'

def notify_bet_success(user_id, bet_type, bet_amount):
    bet_message = f"<pre>Game TX Room\nUser: [{user_id}] đã cược [{bet_type}] số tiền [{bet_amount:,} đ] thành công!</pre>"
    bot.send_message(group_chat_id3, bet_message, parse_mode='HTML')

def confirm_bet(user_id, bet_type, bet_amount, original_message_id, is_anonymous=False):
    global current_session
    global user_balance

    if user_balance.get(user_id, 0) >= bet_amount:
        if user_id not in user_bets:
            user_bets[user_id] = {'T': 0, 'X': 0}

        user_bets[user_id][bet_type.upper()] += bet_amount
        user_balance[user_id] -= bet_amount
        save_balance_to_file()

        with open("topngaybxh.json", "r+") as f:
            user_bets_dict = defaultdict(int)
            for line in f:
                data = json.loads(line)
                for uid, amount in data.items():
                    user_bets_dict[int(uid)] += amount
            user_bets_dict[user_id] += bet_amount
            f.seek(0)
            f.truncate(0)
            for uid, total_amount in user_bets_dict.items():
                json.dump({uid: total_amount}, f)
                f.write("\n")

        with open("toptuanbxh.json", "r+") as f:
            user_bets_dict = defaultdict(int)
            for line in f:
                data = json.loads(line)
                for uid, amount in data.items():
                    user_bets_dict[int(uid)] += amount
            user_bets_dict[user_id] += bet_amount
            f.seek(0)
            f.truncate(0)
            for uid, total_amount in user_bets_dict.items():
                json.dump({uid: total_amount}, f)
                f.write("\n")

        encoded_user_id = f"***{str(user_id)[-4:]}"
        remaining_balance = user_balance[user_id]
        if is_anonymous:
            confirmation_message = f"🏮 <b>Đặt thành công kỳ XX #<code>{current_session}</code>\nLệnh {bet_type}\nSố tiền cược: <code>{int(bet_amount):,}</code>\nNgười cược: <code>(Ẩn Danh)</code></b>"
            bot2.send_message(group_chat_id2, confirmation_message, parse_mode='HTML')
        else:
            confirmation_message = f"🏮 <b>Đặt thành công kỳ #<code>{current_session}</code>\nLệnh {bet_type}\nSố tiền cược: <code>{int(bet_amount):,}</code>\nNgười cược: <code>({encoded_user_id})</code></b>"
            bot2.send_message(group_chat_id2, confirmation_message, reply_to_message_id=original_message_id, parse_mode='HTML')

        confirmation_message1 = f"🏮 <b>Bạn đặt thành công kỳ XX #<code>{current_session}</code>\nLệnh: {bet_type} - {int(bet_amount):,}\nSố dư còn lại: {int(remaining_balance):,}</b>"
        bot.send_message(chat_id=user_id, text=confirmation_message1, parse_mode='HTML')
        notify_bet_success(user_id, bet_type, bet_amount)

        return True
    if is_anonymous:
            encoded_user_id = f"(Ẩn Danh)"
            bot2.send_message(group_chat_id2, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.")
    else:
        encoded_user_id = f"***{str(user_id)[-4:]}"
        bot2.send_message(group_chat_id2, f"❌ {encoded_user_id} Không đủ số dư để đặt cược.", reply_to_message_id=original_message_id)
        return False



def calculate_user_winnings(user_id, game_result):
    if (game_result == 'T' and user_bets[user_id]['T']
            > 0) or (game_result == 'X' and user_bets[user_id]['X'] > 0):
        winnings = 1.95 * (user_bets[user_id]['T'] +
                          user_bets[user_id]['X'])
        user_balance[user_id] += winnings
        save_balance_to_file()
        return winnings
    return 0


def calculate_user_losses(user_id, game_result):
    if (game_result != 'T' and user_bets[user_id]['T']
            > 0) or (game_result != 'X' and user_bets[user_id]['X'] > 0):
        return user_bets[user_id]['T'] + user_bets[user_id]['X']
    return 0

keyboard1 = types.InlineKeyboardMarkup()
url_button = types.InlineKeyboardButton(text="Chơi Ẩn Danh",
                                        url="https://t.me/txroomluxury_bot")
keyboard1.add(url_button)

def start_game():
    global current_session, accepting_bets
    current_session += 1
    accepting_bets = True


    turn_on_group_chat()
    bot2.send_message(
        group_chat_id2,
        f"<blockquote> Mời Bạn Đặt Cược Phiên #<code>{current_session}</code></blockquote>\n\n"
        f"◉<b> Cách Chơi</b>: <code>T</code> [ số tiền ] <code>X</code> [ số tiền ]\n"
        f"◉<b> Cách Chơi</b>: <code>T MAX</code> <code>X MAX</code>\n\n"
        f"◉ Ví Dụ: <b>T</b> 10000 & <b>X</b> 10000\n\n"
        f"◉<b> Trả thưởng cho người thắng *1.95</b>\n"
        f"◉<b> Chỉ được cược 1 mặt trong phiên</b>\n"
        f"◉<b> Min cược: 3.000 - Max cược: 300.000</b>\n\n"
        f"◉<b> Bắt đầu cược thời gian [ 90s ]</b>\n"
        f"😘 <b>Mời các đại gia ra tay cược mạnh nhé !</b>\n",
        parse_mode='HTML', reply_markup=keyboard1)

    time.sleep(30)

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets])
    total_bet_TAI = sum(
        [1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum(
        [1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    last_10_sessions = session_results[-10:]
    display_last_10 = " ".join(
        ["🔵" if session == 'T' else "🔴" for session in last_10_sessions])

    bot2.send_message(
        group_chat_id2,
        (
            f"<b>⏰ Còn 60s để cược phiên #<code>{current_session}</code></b>\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"<b>🔵 TÀI: <code>{int(total_bet_T):,}</code></b>\n"
            f"\n"
            f"<b>🔴 XỈU: <code>{int(total_bet_X):,}</code></b>\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"<b>👁‍🗨 TÀI: <code>{int(total_bet_TAI):,}</code> Người cược.</b>\n"
            f"\n"
            f"<b>👁‍🗨 XỈU: <code>{int(total_bet_XIU):,}</code> Người cược.</b>\n\n"
        ),
        parse_mode='HTML',
        reply_markup=keyboard1
    )

    time.sleep(30)

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets])
    total_bet_TAI = sum(
        [1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum(
        [1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"<b>⏰ Còn 30s để cược phiên #[<code>{current_session}</code>]</b>\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"<b>🔵 TÀI: <code>{int(total_bet_T):,}</code></b>\n"
            f"\n"
            f"<b>🔴 XỈU: <code>{int(total_bet_X):,}</code></b>\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"<b>👁‍🗨 TÀI: <code>{int(total_bet_TAI):,}</code> Người cược.</b>\n"
            f"\n"
            f"<b>👁‍🗨 XỈU: <code>{int(total_bet_XIU):,}</code> Người cược.</b>\n\n"
        ),
        parse_mode='HTML',
        reply_markup=keyboard1
    )

    time.sleep(20)

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets])
    total_bet_TAI = sum(
        [1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum(
        [1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"<b>⏰ Còn 10s để cược phiên #[<code>{current_session}</code>]</b>\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"<b>🔵 TÀI: <code>{int(total_bet_T):,}</code></b>\n"
            f"\n"
            f"<b>🔴 XỈU: <code>{int(total_bet_X):,}</code></b>\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"<b>👁‍🗨 TÀI: <code>{int(total_bet_TAI):,}</code> Người cược.</b>\n"
            f"\n"
            f"<b>👁‍🗨 XỈU: <code>{int(total_bet_XIU):,}</code> Người cược.</b>\n\n"
        ),
        parse_mode='HTML',
        reply_markup=keyboard1
    )

    time.sleep(10)

    total_bet_T = sum([user_bets[user_id]['T'] for user_id in user_bets])
    total_bet_X = sum([user_bets[user_id]['X'] for user_id in user_bets])
    total_bet_TAI = sum(
        [1 for user_id in user_bets if user_bets[user_id]['T'] > 0])
    total_bet_XIU = sum(
        [1 for user_id in user_bets if user_bets[user_id]['X'] > 0])

    bot2.send_message(
        group_chat_id2,
        (
            f"<b>⏰ Hết thời gian phiên #[<code>{current_session}</code>]</b>\n"
            f"<blockquote>Tổng Cược 🔵 | Tổng Cược 🔴</blockquote>\n"
            f"<b>🔵 TÀI: <code>{int(total_bet_T):,}</code></b>\n"
            f"\n"
            f"<b>🔴 XỈU: <code>{int(total_bet_X):,}</code></b>\n\n"
            f"<blockquote>Số Người Cược TÀI -- XỈU</blockquote>\n"
            f"<b>👁‍🗨 TÀI: <code>{int(total_bet_TAI):,}</code> Người cược.</b>\n"
            f"\n"
            f"<b>👁‍🗨 XỈU: <code>{int(total_bet_XIU):,}</code> Người cược.</b>\n\n"
        ),
        parse_mode='HTML',
        reply_markup=keyboard1
    )

    turn_off_group_chat()
    accepting_bets = False
    time.sleep(6)

    bot2.send_message(
        group_chat_id2,
        f"<b>Bắt đầu tung xúc xắc phiên #<code>{current_session}</code></b>", parse_mode='HTML')
    time.sleep(3)

    result = [send_dice_room_reply(group_chat_id2) for _ in range(3)]
    dice_sum = sum(result)
    game_result = check_result(dice_sum)
    session_results.append(game_result)
    
    send_game_result_and_process_winnings(result, dice_sum, game_result)

    save_session_to_file()


def send_game_result_and_process_winnings(result, dice_sum, game_result):
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
                pass #print(f"{user_id}: {str(e)}")

    sorted_user_winnings = sorted(user_winnings_dict.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = "\n┃".join([
        f"{i+1} - <code>{'*' * 3 + str(uid)[-4:]}</code> - <code>{int(winnings):,}</code>"
        for i, (uid, winnings) in enumerate(sorted_user_winnings[:10])
    ])

    time.sleep(4)
    keyboard = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(text="Kết Quả TX [ Room ]",
                                            url="https://t.me/kqtxroomluxury")
    keyboard.add(url_button)
    bot2.send_message(
        group_chat_id2,
        (
            f"<b>🌸 Kết Quả Xúc Xắc Phiên #<code>{current_session}</code>\n"
            f"┏━━━━━━━━━━━━━━━━┓\n"
            f"┃  {' '.join(map(str, result))}  ({dice_sum})  {check_result1(dice_sum)} {display_last_1}\n"
            f"┃\n"
            f"┃ 🔎 Tổng Thắng: <code>{int(total_winnings):,}</code>\n"
            f"┃\n"
            f"┃ 🔎 Tổng Thua: <code>{int(total_losses):,}</code>\n"
            f"┃━━━━━━━━━━━━━━━━\n"
            f"┃ 🏆 Top Bảng Xếp Hạng #[<code>{current_session}</code>]\n"
            f"┃ TOP - ID - Tổng thắng\n"
            f"┃{leaderboard_message}\n"
            f"┗━━━━━━━━━━━━━━━━┛\n"
            f"Lịch Sử Phiên Gần Nhất\n\n"
            f"{display_last_10}\n\n"
            f"      🔵  Tài       |      🔴   XỈU\n</b>"
        ),
        parse_mode='HTML',
        reply_markup=keyboard
    )
    result_message = f"<b>Kết Quả XX Kỳ #{current_session} - {display_last_1}\n{result} - ({dice_sum}) - {check_result1(dice_sum)}</b>"
    for user_id, user_winnings in user_winnings_dict.items():
        user_losses = calculate_user_losses(user_id, check_result1(dice_sum))
        balance = user_balance.get(user_id, 0)
        rounded_balance = round(balance)

        if user_winnings > 0:
            message_text = (
                f"🔹️ Phiên XX#<code>{current_session}</code> Bạn Đã Thắng\n"
                f"Số tiền thắng: <b>{int(user_winnings):,}</b>\n"
                f"Số dư mới: <b>{int(rounded_balance):,}</b>"
            )
        else:
            message_text = (
                f"🔹️ Phiên XX#<code>{current_session}</code> Bạn Đã Thua\n"
                f"Số tiền thua: <b>{int(user_losses):,}</b>\n"
                f"Số dư mới: <b>{int(rounded_balance):,}</b>"
            )

        bot.send_message(chat_id=user_id, text=message_text, parse_mode='HTML')
    bot2.send_message(group_chat_id4, result_message, parse_mode='HTML')
    user_bets.clear()
    processed_users.clear()
    save_balance_to_file()
    save_session_history_to_file()
    time.sleep(3)



def game_timer():
    while True:

        schedule.run_pending()

        start_game()
        

#=================----------====================-------------------=====================


@bot2.message_handler(func=lambda message: True)
def handle_message(message):
    global accepting_bets
    
    if accepting_bets:
        chat_id = message.chat.id

        if message.text.lower() == '/start':
            send_betting_menu(message)
        elif message.text and len(message.text.split()) == 2:
            bet_type, bet_amount_str = message.text.split()

            if bet_type.upper() in ['T', 'X'] or (bet_type.upper() == 'T' and bet_amount_str.upper() in ['MAX', '1000', '50000']):
                user_id = message.from_user.id

                try:
                    if bet_amount_str.upper() == 'MAX':
                        max_bet_amount = min(user_balance.get(user_id, 0), 300000)
                        if max_bet_amount >= 3000:
                            bet_amount = max_bet_amount
                        else:
                            bot2.send_message(group_chat_id2, "❌ Số dư của bạn không đủ để cược.")
                            return True
                    else:
                        bet_amount = int(bet_amount_str)

                    if 3000 <= bet_amount <= 300000:
                        opposite_bet_type = 'T' if bet_type.upper() == 'X' else 'X'
                        if user_bets.get(user_id) and user_bets[user_id][opposite_bet_type] > 0:
                            bot2.send_message(group_chat_id2, "❌ Không được cược cả hai bên trong một phiên.")
                        else:
                            if chat_id == group_chat_id2:
                                confirm_bet(user_id, bet_type, bet_amount, message.message_id, is_anonymous=False)
                            else:
                                confirm_bet(user_id, bet_type, bet_amount, message.message_id, is_anonymous=True)
                    else:
                        bot2.send_message(group_chat_id2, "❌ Số tiền cược phải từ 3.000 đến 300.000")
                except ValueError:
                    return True
                except telebot.apihelper.ApiException as e:
                    pass
                    return True
                except Exception as e:
                    pass #bot2.send_message(user_id, f"❌ Đã xảy ra lỗi: {str(e)}")
        else:
            return True
    else:
        try:
            bot2.delete_message(message.chat.id, message.message_id)
            if message.reply_to_message is not None:
                bot2.delete_message(message.chat.id, message.reply_to_message.message_id)
        except Exception as e:
            pass #print(f"Error deleting message: {e}")

        time.sleep(1)

        bot2.send_message(message.chat.id, "❌ Đã Ngưng Nhận Cược. Vui Lòng Chờ Phiên Cược Sau.")




def send_betting_menu(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    tai_buttons = [
        types.KeyboardButton("t 5000"),
        types.KeyboardButton("t 20000"),
        types.KeyboardButton("t 50000"),
        types.KeyboardButton("t max")
    ]
    xiu_buttons = [
        types.KeyboardButton("x 5000"),
        types.KeyboardButton("x 20000"),
        types.KeyboardButton("x 50000"),
        types.KeyboardButton("x max")
    ]
    keyboard.row(*tai_buttons)
    keyboard.row(*xiu_buttons)
    bot2.send_message(message.chat.id, "Vui lòng chọn cược.", reply_markup=keyboard)

#=========-------Thông báo room--------===============

load_balance_from_file()
load_session_from_file()
load_session_history_from_file()

def turn_on_group_chat():
    permissions = ChatPermissions(can_send_messages=True)
    bot2.set_chat_permissions(group_chat_id2, permissions)


def turn_off_group_chat():
    permissions = ChatPermissions(can_send_messages=False)
    bot2.set_chat_permissions(group_chat_id2, permissions)


timer_thread = threading.Thread(target=game_timer)
timer_thread.start()

bot3 = telebot.TeleBot('8027877843:AAG1z9OcCkdz8jcT3KnWuKi6BCzvlJhxu2s')

def check_file():
    try:
        with open("thanhtran309.txt", "r") as file:
            content = file.read()
            if "TRANTIENTHANH" not in content:
                print("Lỗi: 'thanhtran309.txt' nếu bạn xóa chứ TRANTIENTHANH sẽ không dùng đươc bot.")
                return False
    except FileNotFoundError:
        print("Lỗi: 'thanhtran309.txt' nếu bạn xóa chứ TRANTIENTHANH sẽ không dùng đươc bot.")
        return False
    return True   


def poll_bot(bot):
    try:
        bot.polling()
    except Exception as e:
        pass #print(f"An error occurred while polling bot: {e}")
        time.sleep(5)


if check_file():
    thread_bot = threading.Thread(target=poll_bot, args=(bot,))
    thread_bot2 = threading.Thread(target=poll_bot, args=(bot2,))
    thread_bot3 = threading.Thread(target=poll_bot, args=(bot3,))
    thread_bot.start()
    thread_bot2.start()
    thread_bot3.start()
