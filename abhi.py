import telebot
from telebot import types
import requests
import json
import sqlite3
import datetime
import time
import random
import string
import base64
from dateutil.relativedelta import relativedelta

# ================== CONFIGURATION ==================
BOT_TOKEN = "8307595740:AAEZgus4FlnTGIfue8l8GKaas6RLuC5zSZk"

# 🔴 YAHAN APNE AUR APNE PARTNERS KE TELEGRAM USER IDs DAALEIN 🔴
ADMIN_IDS = [6900460993] 

ADMIN_USERNAME = "@darkvex_enthem"
CHANNEL_USERNAME = "@osint_rto"
CHANNEL_LINK = "https://t.me/osint_rto"
QR_MESSAGE_ID = 2 # Aapke channel me QR code wale message ka ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ================== PLANS CONFIGURATION ==================
PLANS = {
    "basic": {"name": "Basic — ₹20", "credits": 5, "price": 20, "type": "credits"},
    "popular": {"name": "Popular — ₹100", "credits": 20, "price": 100, "type": "credits"},
    "good": {"name": "Good Deal — ₹225", "credits": 50, "price": 225, "type": "credits"},
    "great": {"name": "Great Value — ₹450", "credits": 100, "price": 450, "type": "credits"},
    "1m": {"name": "1 Month Premium — ₹1999", "credits": "Unlimited", "price": 1999, "type": "premium_1m"},
    "life": {"name": "Lifetime Premium — ₹4999", "credits": "Unlimited", "price": 4999, "type": "premium_life"}
}

# ================== DATABASE SETUP ==================
conn = sqlite3.connect('rto_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        credits INTEGER,
        is_premium INTEGER,
        premium_expiry TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_key TEXT,
        status TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        api_type TEXT,
        query TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY,
        credits INTEGER,
        status TEXT DEFAULT 'active'
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS redeemed_users (
        user_id INTEGER,
        code TEXT
    )
''')
conn.commit()

# ================== DB HELPERS ==================
def log_search(user_id, api_type, query):
    cursor.execute("INSERT INTO search_history (user_id, api_type, query) VALUES (?, ?, ?)", (user_id, api_type, query))
    conn.commit()

def register_user(user_id, username, referrer_id=None):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, credits, is_premium, premium_expiry) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, username, 5, 0, ""))
        conn.commit()
        if referrer_id and referrer_id != user_id:
            cursor.execute("UPDATE users SET credits = credits + 3 WHERE user_id=?", (referrer_id,))
            conn.commit()
            try: bot.send_message(referrer_id, f"🎉 <b>REFERRAL SUCCESSFUL!</b>\nEk naye user ne join kiya hai. <b>+3 Credits</b> added!")
            except: pass

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def check_premium_status(user_id):
    user = get_user(user_id)
    if user and user[3] == 1:
        expiry = user[4]
        if expiry == "Lifetime": return True
        try:
            if datetime.date.today() <= datetime.datetime.strptime(expiry, "%Y-%m-%d").date(): return True
            cursor.execute("UPDATE users SET is_premium=0, premium_expiry='' WHERE user_id=?", (user_id,))
            conn.commit()
        except: return False
    return False

def refund_credits(user_id, amount):
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=? AND is_premium=0", (amount, user_id))
    conn.commit()

# ================== ADVANCED SILENT RETRY SYSTEM (5 RETRIES) ==================
def fetch_with_retry(url, method="GET", payload=None, headers=None, retries=5, timeout=60, return_type="json"):
    for attempt in range(retries):
        try:
            if method == "POST":
                response = requests.post(url, data=json.dumps(payload) if payload else None, headers=headers, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, timeout=timeout)
            
            # Agar API Server down ho (5xx error) to silent retry karega
            if response.status_code >= 500 and attempt < retries - 1:
                time.sleep(2)
                continue

            # Return as requested (JSON dictionary or Raw Response Object)
            if return_type == "json":
                return response.json()
            return response
            
        except Exception as e:
            if attempt == retries - 1:
                raise e # 5th attempt ke baad hi error throw karega
            time.sleep(2) # 2 seconds wait for next silent retry

# ================== UI MENUS ==================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🚘 RC Search", "📱 Number to Vehicle")
    markup.add("📞 Number to Info", "📄 RC PDF")
    markup.add("🪪 DL PDF", "🛡️ Insurance PDF")
    markup.add("💳 Buy Credits", "🎁 Redeem Code")
    markup.add("🔗 Refer & Earn", "👤 My Profile")
    if user_id in ADMIN_IDS:
        markup.add("🛡️ Admin Panel")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Add Credits", "➖ Cut Credits")
    markup.add("💎 Make Premium", "🚫 Remove Premium")
    markup.add("🎁 Global Gift", "🧨 Global Deduct")
    markup.add("🎟️ Gen Redeem Code", "🔍 User Search")
    markup.add("📊 Bot Stats", "📈 API Stats")
    markup.add("📋 User List", "📢 Broadcast")
    markup.add("🏓 Ping", "🔙 Back to Main")
    return markup

USER_MENU_OPTIONS = ["🚘 RC Search", "📱 Number to Vehicle", "📞 Number to Info", "📄 RC PDF", "🪪 DL PDF", "🛡️ Insurance PDF", "💳 Buy Credits", "🎁 Redeem Code", "🔗 Refer & Earn", "👤 My Profile", "🔙 Back to Main"]
ADMIN_MENU_OPTIONS = ["🛡️ Admin Panel", "➕ Add Credits", "➖ Cut Credits", "💎 Make Premium", "🚫 Remove Premium", "🎁 Global Gift", "🧨 Global Deduct", "🎟️ Gen Redeem Code", "🔍 User Search", "📢 Broadcast", "📊 Bot Stats", "📈 API Stats", "📋 User List", "🏓 Ping"]

# ================== CHECKS & VALIDATIONS ==================
def check_join(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def force_join_message(message):
    m = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("📢 JOIN CHANNEL", url=CHANNEL_LINK)
    btn2 = types.InlineKeyboardButton("✅ VERIFY", callback_data="verify_join")
    m.add(btn1, btn2)
    bot.reply_to(message, "⚠️ <b>ACCESS DENIED!</b>\nPehle channel join karein, fir <b>'Verify'</b> par click karein.", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    if check_join(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ <b>Verified Successfully!</b>\nWelcome to the Main Menu.", reply_markup=main_menu(call.from_user.id))
    else:
        bot.answer_callback_query(call.id, "⚠️ Aapne abhi tak channel join nahi kiya hai!", show_alert=True)

def check_credits(message, required_credits):
    user_id = message.from_user.id
    user = get_user(user_id)
    if check_premium_status(user_id): return True 
    if user[2] >= required_credits: return True
    bot.reply_to(message, f"❌ <b>INSUFFICIENT CREDITS!</b>\n💳 Your Credits: {user[2]}\n📉 Required: {required_credits}\n\nPlease click <b>💳 Buy Credits</b> or <b>🔗 Refer & Earn</b>.")
    return False

# ================== MENU HANDLERS ==================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    register_user(message.from_user.id, message.from_user.username, referrer_id)
    
    if not check_join(message.from_user.id):
        force_join_message(message)
        return

    welcome_msg = f"👑 <b>WELCOME TO ABHI VIP BOT</b> 👑\n━━━━━━━━━━━━━━━━━━━━\nHello {message.from_user.first_name}! Use the menu below to navigate."
    bot.reply_to(message, welcome_msg, reply_markup=main_menu(message.from_user.id))

@bot.message_handler(func=lambda message: message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS)
def handle_menu(message):
    if not check_join(message.from_user.id):
        force_join_message(message)
        return
        
    text = message.text
    user_id = message.from_user.id

    if text == "🔙 Back to Main":
        bot.reply_to(message, "🏠 Main Menu", reply_markup=main_menu(user_id))

    elif text == "👤 My Profile":
        user = get_user(user_id)
        status = f"💎 Premium (Valid till: {user[4]})" if check_premium_status(user_id) else "🆓 Free User"
        cursor.execute("SELECT COUNT(*) FROM search_history WHERE user_id=?", (user_id,))
        total_searches = cursor.fetchone()[0]
        bot.reply_to(message, f"👤 <b>YOUR PROFILE</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 <b>ID:</b> <code>{user_id}</code>\n💳 <b>Credits:</b> {user[2]}\n🏷️ <b>Status:</b> {status}\n🔍 <b>Total Searches:</b> {total_searches}")

    elif text == "🔗 Refer & Earn":
        bot_info = bot.get_me()
        bot.reply_to(message, f"🔗 <b>REFER & EARN SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━\n🎁 <b>New User Gets:</b> 5 Credits\n🎁 <b>You Earn:</b> 3 Credits (Per invite)\n\n👇 <b>Aapka Link:</b>\n<code>https://t.me/{bot_info.username}?start={user_id}</code>")

    elif text == "💳 Buy Credits":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, plan in PLANS.items(): markup.add(types.InlineKeyboardButton(f"💎 {plan['name']} → {plan['credits']} Cr", callback_data=f"buy_{key}"))
        bot.reply_to(message, "💳 <b>SELECT A PLAN TO BUY</b>\n━━━━━━━━━━━━━━━━━━━━", reply_markup=markup)

    elif text == "🛡️ Insurance PDF":
        m = types.InlineKeyboardMarkup()
        admin_link = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
        m.add(types.InlineKeyboardButton("👨‍💻 Connect Admin", url=admin_link))
        bot.reply_to(message, "🛡️ <b>Insurance PDF Facility</b>\n━━━━━━━━━━━━━━━━━━━━\nInsurance PDF nikalwane ke liye kripya direct Admin se contact karein.", reply_markup=m)

    elif text == "🎁 Redeem Code":
        msg = bot.reply_to(message, "🎁 <b>Redeem Code</b>\nKripya apna redeem code yahan bhejein:")
        bot.register_next_step_handler(msg, process_redeem_code)

    elif text == "🚘 RC Search":
        msg = bot.reply_to(message, "🚘 <b>RC Search (Cost: 5 Cr)</b>\nEnter Vehicle Number (e.g., DL9C0001):")
        bot.register_next_step_handler(msg, process_rc)

    elif text == "📱 Number to Vehicle":
        msg = bot.reply_to(message, "📱 <b>Number to Vehicle (Cost: 10 Cr)</b>\nEnter Mobile Number:")
        bot.register_next_step_handler(msg, process_mobile)
        
    elif text == "📞 Number to Info":
        msg = bot.reply_to(message, "📞 <b>Number to Info (Cost: 2 Cr)</b>\nEnter Mobile Number:")
        bot.register_next_step_handler(msg, process_number_info)

    elif text == "📄 RC PDF":
        msg = bot.reply_to(message, "📄 <b>RC PDF Generate (Cost: 70 Cr)</b>\nEnter Vehicle Number (e.g., DL9C0001):")
        bot.register_next_step_handler(msg, process_rc_pdf)

    elif text == "🪪 DL PDF":
        msg = bot.reply_to(message, "🪪 <b>DL PDF Generate (Cost: 70 Cr)</b>\n👇 Pehle apna <b>Driving License Number</b> likhein:")
        bot.register_next_step_handler(msg, process_dl_pdf_step1)

    # ---------- ADMIN BUTTONS ----------
    elif text == "🛡️ Admin Panel" and user_id in ADMIN_IDS:
        bot.reply_to(message, "🛡️ <b>WELCOME TO ADMIN PANEL</b>\nSelect an option below:", reply_markup=admin_menu())

    elif text == "📊 Bot Stats" and user_id in ADMIN_IDS:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
        premium_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status='approved'")
        total_sales = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM search_history")
        total_api = cursor.fetchone()[0]
        
        stat_msg = f"📊 <b>BOT STATISTICS</b>\n━━━━━━━━━━━━━━━━━━━━\n👥 <b>Total Users:</b> {total_users}\n💎 <b>Premium Users:</b> {premium_users}\n💰 <b>Approved Sales:</b> {total_sales}\n🌐 <b>Total API Calls:</b> {total_api}\n━━━━━━━━━━━━━━━━━━━━"
        bot.reply_to(message, stat_msg)

    elif text == "📈 API Stats" and user_id in ADMIN_IDS:
        cursor.execute("SELECT api_type, COUNT(*) FROM search_history GROUP BY api_type")
        stats = cursor.fetchall()
        ans = "📈 <b>API USAGE STATS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        if not stats: ans += "No API calls yet."
        for row in stats:
            ans += f"🔸 <b>{row[0]}:</b> {row[1]} calls\n"
        bot.reply_to(message, ans)

    elif text == "🔍 User Search" and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, "🔍 <b>User Search</b>\nUser ki Telegram ID (User ID) bhejein:")
        bot.register_next_step_handler(msg, process_user_search)

    elif text == "🎟️ Gen Redeem Code" and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, "🎟️ <b>Generate Redeem Code</b>\nKitne credits ka code banana hai? (Number likhein):")
        bot.register_next_step_handler(msg, process_generate_code)

    elif text == "🎁 Global Gift" and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, "🎁 <b>Global Gift</b>\nSabhi users ko kitne credits dene hain? (Number likhein):")
        bot.register_next_step_handler(msg, process_global_gift)

    elif text == "🧨 Global Deduct" and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, "🧨 <b>Global Deduct</b>\nSabhi users ke kitne credits kaatne hain? (Number likhein):")
        bot.register_next_step_handler(msg, process_global_deduct)

    elif text == "📋 User List" and user_id in ADMIN_IDS:
        cursor.execute("SELECT user_id, username, credits, is_premium FROM users ORDER BY user_id DESC LIMIT 15")
        users = cursor.fetchall()
        list_msg = "📋 <b>RECENT 15 USERS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for u in users:
            status = "💎" if u[3] == 1 else "🆓"
            uname = u[1] if u[1] else "No Username"
            list_msg += f"👤 <code>{u[0]}</code> | @{uname} | Cr: {u[2]} | {status}\n"
        bot.reply_to(message, list_msg)

    elif text == "🏓 Ping" and user_id in ADMIN_IDS:
        start = time.time()
        bot.get_me()
        end = time.time()
        ping_time = round((end - start) * 1000)
        bot.reply_to(message, f"🏓 <b>PONG!</b>\n━━━━━━━━━━━━━━━━━━━━\n🤖 <b>Bot Status:</b> Online ✅\n⚡ <b>Response Time:</b> {ping_time}ms\n💾 <b>Database:</b> Connected")

    elif text in ["➕ Add Credits", "➖ Cut Credits", "💎 Make Premium", "🚫 Remove Premium"] and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, f"{text}\n\n👉 Enter <b>UserID</b> aur <b>Amount</b> (Space de kar).\n<i>Example: 123456789 50</i>\n(Premium ke liye sirf UserID likhein)")
        bot.register_next_step_handler(msg, process_admin_action, text)

    elif text == "📢 Broadcast" and user_id in ADMIN_IDS:
        msg = bot.reply_to(message, "📢 Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, process_broadcast)


# ================== REDEEM & USER SEARCH FLOWS ==================
def process_redeem_code(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    code = message.text.strip()
    user_id = message.from_user.id
    
    cursor.execute("SELECT * FROM redeem_codes WHERE code=? AND status='active'", (code,))
    db_code = cursor.fetchone()
    
    if not db_code:
        bot.reply_to(message, "❌ <b>Invalid ya Expired Code!</b>")
        return
        
    cursor.execute("SELECT * FROM redeemed_users WHERE user_id=? AND code=?", (user_id, code))
    if cursor.fetchone():
        bot.reply_to(message, "⚠️ Aap ye code pehle hi use kar chuke hain.")
        return
        
    credits_amt = db_code[1]
    cursor.execute("INSERT INTO redeemed_users (user_id, code) VALUES (?, ?)", (user_id, code))
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (credits_amt, user_id))
    cursor.execute("UPDATE redeem_codes SET status='used' WHERE code=?", (code,))
    conn.commit()
    
    bot.reply_to(message, f"🎉 <b>BINGO!</b>\nAapko successfully <b>{credits_amt} Credits</b> mil gaye hain.")

def process_generate_code(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    try:
        credits_amt = int(message.text)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        cursor.execute("INSERT INTO redeem_codes (code, credits) VALUES (?, ?)", (code, credits_amt))
        conn.commit()
        bot.reply_to(message, f"✅ <b>Code Generated!</b>\n\n🎟️ <b>Code:</b> <code>{code}</code>\n💳 <b>Credits:</b> {credits_amt}\n(Single use for one user)")
    except:
        bot.reply_to(message, "⚠️ Error! Kripya sirf number bhejein.")

def process_global_gift(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    try:
        amt = int(message.text)
        cursor.execute("UPDATE users SET credits = credits + ?", (amt,))
        conn.commit()
        bot.reply_to(message, f"✅ Sabhi users ko {amt} credits bhej diye gaye hain!")
    except:
        bot.reply_to(message, "⚠️ Error! Number daalein.")

def process_global_deduct(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    try:
        amt = int(message.text)
        cursor.execute("UPDATE users SET credits = CASE WHEN credits - ? < 0 THEN 0 ELSE credits - ? END", (amt, amt))
        conn.commit()
        bot.reply_to(message, f"🧨 Sabhi users ke account se {amt} credits kaat liye gaye hain!")
    except:
        bot.reply_to(message, "⚠️ Error! Number daalein.")

def process_user_search(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    try:
        target_id = int(message.text)
        user = get_user(target_id)
        if not user:
            bot.reply_to(message, "❌ User database mein nahi mila.")
            return
            
        status = f"💎 Premium (Till: {user[4]})" if user[3] == 1 else "🆓 Free User"
        uname = f"@{user[1]}" if user[1] else "No Username"
        
        cursor.execute("SELECT COUNT(*) FROM search_history WHERE user_id=?", (target_id,))
        total_searches = cursor.fetchone()[0]
        
        cursor.execute("SELECT api_type, query, timestamp FROM search_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (target_id,))
        history = cursor.fetchall()
        
        ans = f"🔍 <b>USER REPORT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        ans += f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        ans += f"👤 <b>Username:</b> {uname}\n"
        ans += f"💳 <b>Credits:</b> {user[2]}\n"
        ans += f"🏷️ <b>Status:</b> {status}\n"
        ans += f"📈 <b>Total API Calls:</b> {total_searches}\n\n"
        
        ans += "🕒 <b>LAST 5 SEARCHES:</b>\n"
        if history:
            for row in history:
                ans += f"🔸 <b>{row[0]}</b> - <code>{row[1]}</code>\n"
        else:
            ans += "<i>No recent searches.</i>"
            
        bot.reply_to(message, ans)
    except:
        bot.reply_to(message, "⚠️ Invalid User ID.")

# ================== ADMIN FLOWS ==================
def process_admin_action(message, action_type):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    try:
        args = message.text.split()
        target_id = int(args[0])
        amt = int(args[1]) if len(args) > 1 else 0

        if action_type == "➕ Add Credits":
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amt, target_id))
            bot.reply_to(message, f"✅ Added {amt} credits to {target_id}")
        elif action_type == "➖ Cut Credits":
            cursor.execute("UPDATE users SET credits = credits - ? WHERE user_id=?", (amt, target_id))
            bot.reply_to(message, f"✅ Removed {amt} credits from {target_id}")
        elif action_type == "💎 Make Premium":
            cursor.execute("UPDATE users SET is_premium=1, premium_expiry='Lifetime' WHERE user_id=?", (target_id,))
            bot.reply_to(message, f"💎 {target_id} is now Lifetime Premium!")
        elif action_type == "🚫 Remove Premium":
            cursor.execute("UPDATE users SET is_premium=0, premium_expiry='' WHERE user_id=?", (target_id,))
            bot.reply_to(message, f"🚫 Premium removed for {target_id}")
        conn.commit()
    except: bot.reply_to(message, "⚠️ Error! Format sahi nahi hai.")

def process_broadcast(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    cursor.execute("SELECT user_id FROM users")
    bot.reply_to(message, "⏳ Broadcasting started...")
    sent = 0
    for u in cursor.fetchall():
        try: bot.send_message(u[0], f"📢 <b>ADMIN ANNOUNCEMENT</b>\n━━━━━━━━━━━━━━\n{message.text}"); sent += 1
        except: pass
    bot.reply_to(message, f"✅ Broadcast finished! Sent to {sent} users.")

# ================== PAYMENT FLOWS ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_plan_selection(call):
    plan_key = call.data.split('_')[1]
    plan = PLANS[plan_key]
    try:
        bot.copy_message(call.message.chat.id, CHANNEL_USERNAME, QR_MESSAGE_ID)
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("Paid ✅", callback_data=f"paid_{plan_key}"), types.InlineKeyboardButton("Cancel ❌", callback_data="cancel_pay"))
        bot.send_message(call.message.chat.id, f"💳 <b>{plan['name']}</b>\n👆 <b>Scan and pay ₹{plan['price']}</b>.", reply_markup=m)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: bot.answer_callback_query(call.id, "Error fetching QR!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_pay")
def cancel_payment(call): bot.edit_message_text("❌ Payment Cancelled.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def handle_paid(call):
    msg = bot.edit_message_text("📸 <b>Send Payment Screenshot now.</b>", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, process_screenshot, call.data.split('_')[1])

def process_screenshot(message, plan_key):
    if message.text in USER_MENU_OPTIONS: handle_menu(message); return
    if not message.photo:
        msg = bot.reply_to(message, "⚠️ Send a valid photo/screenshot.")
        bot.register_next_step_handler(msg, process_screenshot, plan_key); return

    plan = PLANS[plan_key]
    cursor.execute("INSERT INTO payments (user_id, plan_key, status) VALUES (?, ?, 'pending')", (message.from_user.id, plan_key))
    payment_id = cursor.lastrowid
    conn.commit()
    
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("Approve ✅", callback_data=f"approve_{payment_id}"), types.InlineKeyboardButton("Decline ❌", callback_data=f"decline_{payment_id}"))
    txt = f"🚨 <b>PAYMENT</b> 🚨\n👤 <b>User:</b> {message.from_user.first_name} (<code>{message.from_user.id}</code>)\n💳 <b>Plan:</b> {plan['name']}"
    for admin_id in ADMIN_IDS:
        try: bot.send_photo(admin_id, message.photo[-1].file_id, caption=txt, reply_markup=m)
        except: pass
    bot.reply_to(message, "⏳ <b>Sent to Admins!</b> Wait for approval.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('decline_'))
def admin_payment_action(call):
    if call.from_user.id not in ADMIN_IDS: return
    action, payment_id = call.data.split('_')
    cursor.execute("SELECT status, user_id, plan_key FROM payments WHERE id=?", (payment_id,))
    payment = cursor.fetchone()
    if not payment or payment[0] != 'pending': return bot.answer_callback_query(call.id, "⚠️ Already processed!", show_alert=True)
        
    target_id, plan = payment[1], PLANS[payment[2]]

    if action == "approve":
        if plan['type'] == "credits": cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (plan['credits'], target_id))
        elif plan['type'] == "premium_1m":
            expiry = (datetime.date.today() + relativedelta(months=1)).strftime("%Y-%m-%d")
            cursor.execute("UPDATE users SET is_premium = 1, premium_expiry = ? WHERE user_id=?", (expiry, target_id))
        elif plan['type'] == "premium_life": cursor.execute("UPDATE users SET is_premium = 1, premium_expiry = 'Lifetime' WHERE user_id=?", (target_id,))
            
        cursor.execute("UPDATE payments SET status = 'approved' WHERE id=?", (payment_id,))
        conn.commit()
        try: bot.send_message(target_id, f"🎉 <b>APPROVED!</b> Plan <b>{plan['name']}</b> activated.")
        except: pass
        bot.edit_message_caption(f"{call.message.caption}\n\n✅ <b>APPROVED</b>", call.message.chat.id, call.message.message_id)
    else:
        cursor.execute("UPDATE payments SET status = 'declined' WHERE id=?", (payment_id,))
        conn.commit()
        try: bot.send_message(target_id, f"❌ <b>DECLINED</b> for <b>{plan['name']}</b>.")
        except: pass
        bot.edit_message_caption(f"{call.message.caption}\n\n❌ <b>DECLINED</b>", call.message.chat.id, call.message.message_id)


# ================== API SEARCH FLOWS ==================
def process_rc(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    if not check_credits(message, 5): return
    
    vehicle_no = message.text.upper().replace(" ", "")
    status_msg = bot.reply_to(message, "⏳ <i>Fetching Premium RC Report... (-5 Credits)</i>")
    
    cursor.execute("UPDATE users SET credits = credits - 5 WHERE user_id=? AND is_premium=0", (message.from_user.id,))
    conn.commit()

    url = "mainapi="
    payload = {"api_key": "key", "vehicle_number": vehicle_no}
    headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", 'Content-Type': "application/json"}

    try:
        raw_data = fetch_with_retry(url, method="POST", payload=payload, headers=headers, retries=5, timeout=60, return_type="json")
        
        data = {}
        if isinstance(raw_data, dict):
            if "result" in raw_data and isinstance(raw_data["result"], dict) and "data" in raw_data["result"]:
                data = raw_data["result"]["data"]
            elif "data" in raw_data:
                data = raw_data["data"]
        
        if data and isinstance(data, dict) and len(data.keys()) > 2:
            log_search(message.from_user.id, "RC Search", vehicle_no)
            
            # Fetching updated user details to show correct balance
            current_user = get_user(message.from_user.id)
            if current_user[3] == 1:
                deducted_text = "0 Credits deducted (Admin ♾️)" if message.from_user.id in ADMIN_IDS else "0 Credits deducted (Premium ♾️)"
                balance_text = "Unlimited ♾️ credits"
            else:
                deducted_text = "5 Credits deducted"
                balance_text = f"{current_user[2]} credits"

            year_str = f"{data.get('Manufacture Month', '')}/{data.get('Manufacture Year', 'N/A')}".strip('/')
            
            # 🔴 NEW RC FORMAT 🔴
            ans = f"""🚗 <b>VEHICLE DETAILS</b> 🚗
════════════════════════════════════════

🔍 <b>REGISTRATION DETAILS</b>
🔍 Registration Number: <code>{data.get("Registration Number", "N/A")}</code>
🏛️ RTO Code: <code>{data.get("Office Code", "N/A")}</code>
🏙️ RTO Location: <code>{data.get("Registration Authority", "N/A")}</code>
📅 Registration Date: <code>{data.get("Registration Date", "N/A")}</code>
📊 Status: <code>ACTIVE</code>
📦 Year: <code>{year_str}</code>
⛽ Fuel: <code>{data.get("Fuel Type", "N/A")}</code>
🔧 Body Type: <code>{data.get("Body Type", "N/A")}</code>
🏷️ Category: <code>{data.get("Vehicle Category", "N/A")}</code>
🚙 Class: <code>{data.get("Vehicle Class", "N/A")}</code>
⚙️ Cubic Capacity: <code>{data.get("Cubic Capacity", "N/A")}</code>
⚖️ Unladen Wt: <code>{data.get("Unladen Weight", "N/A")}</code>

👤 <b>OWNER DETAILS</b>
📱 Mobile Number: <code>{data.get("Owner Mobile", "N/A")}</code> ✅
👤 Owner Name: <code>{data.get("Owner Name", "N/A")}</code>
🔢 Owner Serial: <code>{data.get("Owner ID", "N/A")}</code>
📍 Permanent Address: <code>{data.get("Permanent Address", "N/A")}</code>
📍 Correspondence Address: <code>{data.get("Present Address", "N/A")}</code>

🚘 <b>VEHICLE INFORMATION</b>
🔢 Engine Number: <code>{data.get("Engine Number", "N/A")}</code>
🔩 Chassis Number: <code>{data.get("Chassis Number", "N/A")}</code>
🏭 Maker: <code>{data.get("Maker Name", "N/A")}</code>
🚘 Model: <code>{data.get("Model Name", "N/A")}</code>
🎨 Color: <code>{data.get("Color", "N/A")}</code>
💺 Seating Capacity: <code>{data.get("Seating Capacity", "N/A")}</code>
💨 Emission Norms: <code>{data.get("Emission Norms", "N/A")}</code>

🏦 <b>FINANCE, DEALER & FITNESS</b>
💳 Financer: <code>{data.get("Hypothecation Bank", "N/A")}</code>
🏢 Dealer Name: <code>{data.get("Dealer Name", "N/A")}</code>
💵 Sale Amount: <code>₹{data.get("Vehicle Sale Amount", "N/A")}</code>
📅 Fitness/Expiry: <code>{data.get("Registration Validity", "N/A")}</code>

🛡️ <b>INSURANCE & PUCC</b>
🏢 Ins Company: <code>{data.get("Insurance Company", "N/A")}</code>
📜 Ins Policy: <code>{data.get("Insurance Policy Number", "N/A")}</code>
⏳ Ins Expiry: <code>{data.get("Insurance Validity", "N/A")}</code>
💨 PUCC Number: <code>{data.get("PUCC Number", "N/A")}</code>
⏳ PUCC Expiry: <code>{data.get("PUCC Upto", "N/A")}</code>

⚠️ <b>VALIDATION STATUS</b>
📊 Status: <code>SUCCESS</code>
🔎 Mismatch Fields: <code>NONE</code>

🌟 Premium Balance Remaining: ₹0

════════════════════════════════════════

📉 {deducted_text}
💰 Balance: {balance_text}"""
            
            if len(ans) > 4000:
                bot.edit_message_text(ans[:4000], message.chat.id, status_msg.message_id)
                bot.send_message(message.chat.id, ans[4000:8000])
            else:
                bot.edit_message_text(ans, message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ No valid data found in API. (Refunded)", message.chat.id, status_msg.message_id)
            refund_credits(message.from_user.id, 5)
    except Exception as e:
        bot.edit_message_text(f"❌ Server Error or Timeout! (Refunded)\nError: {e}", message.chat.id, status_msg.message_id)
        refund_credits(message.from_user.id, 5)

def process_mobile(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    if not check_credits(message, 10): return
    
    mobile_no = ''.join(char for char in message.text if char.isdigit())
    if len(mobile_no) >= 10:
        mobile_no = mobile_no[-10:]
    else:
        bot.reply_to(message, "❌ Invalid Mobile Number! Please enter a 10-digit number.")
        return

    status_msg = bot.reply_to(message, "⏳ <i>Scanning Vehicles... (-10 Credits)</i>")
    cursor.execute("UPDATE users SET credits = credits - 10 WHERE user_id=? AND is_premium=0", (message.from_user.id,))
    conn.commit()

    try:
        url = f"v_apI={mobile_no}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        resp = fetch_with_retry(url, method="GET", headers=headers, retries=5, timeout=60, return_type="json")
        
        if resp and resp.get("status") == 200 and "data" in resp.get("data", {}):
            vehicles = resp["data"]["data"]
            if not vehicles:
                bot.edit_message_text("❌ No vehicles linked to this number. (Refunded)", message.chat.id, status_msg.message_id)
                refund_credits(message.from_user.id, 10); return
            
            log_search(message.from_user.id, "Number To Vehicle", mobile_no)
            ans = f"📱 <b>LINKED VEHICLES REPORT</b>\n📞 <b>Target:</b> <code>{mobile_no}</code>\n━━━━━━━━━━━━━━━━━━━━\n"
            
            for idx, v in enumerate(vehicles, 1): 
                ans += f"🚙 <b>VEHICLE {idx}</b>\n"
                for key, value in v.items():
                    if value and str(value).strip().lower() not in ["null", "none", ""]:
                        clean_key = key.replace("_", " ").title()
                        ans += f"🔸 <b>{clean_key}:</b> <code>{value}</code>\n"
                ans += "╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌\n"

            ans += f"━━━━━━━━━━━━━━━━━━━━\n💎 <i>Powered by {ADMIN_USERNAME}</i>"
            if len(ans) > 4000:
                bot.edit_message_text(ans[:4000], message.chat.id, status_msg.message_id)
                bot.send_message(message.chat.id, ans[4000:8000])
            else:
                bot.edit_message_text(ans, message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ Failed to fetch from API. (Refunded)", message.chat.id, status_msg.message_id)
            refund_credits(message.from_user.id, 10)
    except Exception as e:
        bot.edit_message_text("❌ Server Error or Timeout! (Refunded)", message.chat.id, status_msg.message_id)
        refund_credits(message.from_user.id, 10)

def process_number_info(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    if not check_credits(message, 2): return
    
    mobile_no = ''.join(char for char in message.text if char.isdigit())
    if len(mobile_no) >= 10:
        mobile_no = mobile_no[-10:]
    else:
        bot.reply_to(message, "❌ Invalid Mobile Number! Please enter a 10-digit number.")
        return

    status_msg = bot.reply_to(message, "⏳ <i>Fetching Number Info... (-2 Credits)</i>")
    cursor.execute("UPDATE users SET credits = credits - 2 WHERE user_id=? AND is_premium=0", (message.from_user.id,))
    conn.commit()

    try:
        url = f"num_apI={mobile_no}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        resp = fetch_with_retry(url, method="GET", headers=headers, retries=5, timeout=60, return_type="json")
        
        if not isinstance(resp, dict):
             bot.edit_message_text("❌ API returned invalid format. (Refunded)", message.chat.id, status_msg.message_id)
             refund_credits(message.from_user.id, 2); return

        data_block = resp.get("result", {}).get("data", {}) if "result" in resp else resp.get("data", resp)

        if isinstance(data_block, dict):
            main_records = data_block.get("main_records", [])
            alt_records = data_block.get("alternative_records", [])
            
            if not main_records and not alt_records:
                bot.edit_message_text("❌ No records found in API response. (Refunded)", message.chat.id, status_msg.message_id)
                refund_credits(message.from_user.id, 2); return

            log_search(message.from_user.id, "Number To Info", mobile_no)
            ans = f"📞 <b>PREMIUM NUMBER INFO</b>\n━━━━━━━━━━━━━━━━━━━━\n📱 <b>Target:</b> <code>{mobile_no}</code>\n\n"
            
            if main_records:
                ans += "<b>📌 MAIN RECORD DETAILS</b>\n"
                for idx, m in enumerate(main_records, 1):
                    ans += "👤 <b>Personal Info:</b>\n"
                    ans += f"🔸 Name: <code>{m.get('full_name', 'N/A')}</code>\n"
                    
                    filtered_m = {k: v for k, v in m.items() if k not in ['full_name', 'the_name_of_the_father', 'document_number'] and v}
                    
                    if filtered_m:
                        ans += "\n🏠 <b>Location & Other Info:</b>\n"
                        for k, v in filtered_m.items():
                             ans += f"🔸 {k.replace('_', ' ').title()}: <code>{v}</code>\n"
                    ans += "╌╌╌╌╌╌╌╌╌╌╌╌╌╌\n"

            ans += f"━━━━━━━━━━━━━━━━━━━━\n💎 <i>Powered by {ADMIN_USERNAME}</i>"
            if len(ans) > 4000:
                bot.edit_message_text(ans[:4000], message.chat.id, status_msg.message_id)
                bot.send_message(message.chat.id, ans[4000:8000])
            else:
                bot.edit_message_text(ans, message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ API Format unrecognized. (Refunded)", message.chat.id, status_msg.message_id)
            refund_credits(message.from_user.id, 2)
            
    except Exception as e:
        bot.edit_message_text("❌ Server Timeout or Error! (Refunded)", message.chat.id, status_msg.message_id)
        refund_credits(message.from_user.id, 2)

def process_rc_pdf(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    if not check_credits(message, 70): return

    vehicle_no = message.text.upper().replace(" ", "")
    status_msg = bot.reply_to(message, "⏳ <i>Generating RC PDF... (-70 Credits)</i>")

    cursor.execute("UPDATE users SET credits = credits - 70 WHERE user_id=? AND is_premium=0", (message.from_user.id,))
    conn.commit()

    try:
        url = f"pdf_apI={vehicle_no}"
        response = fetch_with_retry(url, method="GET", retries=5, timeout=60, return_type="response")
        
        if response.status_code == 200 and len(response.content) > 1000:
            log_search(message.from_user.id, "RC PDF", vehicle_no)
            bot.send_document(
                message.chat.id, 
                ('RC_Report.pdf', response.content), 
                caption=f"📄 <b>RC PDF Downloaded</b>\n🚘 <b>Vehicle:</b> <code>{vehicle_no}</code>\n💎 <i>Powered by {ADMIN_USERNAME}</i>"
            )
            bot.delete_message(message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ Failed to generate RC PDF. File might not exist. (Refunded)", message.chat.id, status_msg.message_id)
            refund_credits(message.from_user.id, 70)
    except Exception as e:
        bot.edit_message_text("❌ Server Error or Timeout! (Refunded)", message.chat.id, status_msg.message_id)
        refund_credits(message.from_user.id, 70)

def process_dl_pdf_step1(message):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    dl_number = message.text.upper().replace(" ", "")
    
    msg = bot.reply_to(message, "📅 Ab apni <b>Date of Birth (DOB)</b> bhejein.\n⚠️ <i>Format DD-MM-YYYY (e.g. 15-08-1995) hona chahiye.</i>")
    bot.register_next_step_handler(msg, process_dl_pdf_step2, dl_number)

def process_dl_pdf_step2(message, dl_number):
    if message.text in USER_MENU_OPTIONS + ADMIN_MENU_OPTIONS: handle_menu(message); return
    if not check_credits(message, 70): return

    dob = message.text.strip()
    status_msg = bot.reply_to(message, "⏳ <i>Generating DL PDF... (-70 Credits)</i>")

    cursor.execute("UPDATE users SET credits = credits - 70 WHERE user_id=? AND is_premium=0", (message.from_user.id,))
    conn.commit()

    url = "dlapi"
    
    payload = {
        "api_key": "key",
        "dl_number": dl_number.strip(),
        "dob": dob.strip()
    }
    
    headers = {
        'User-Agent': "Mozilla/5.0", 
        'Content-Type': "application/json"
    }

    try:
        response = fetch_with_retry(url, method="POST", payload=payload, headers=headers, retries=3, timeout=30, return_type="response")
        
        # Checking if the response is actually a PDF
        if response and 'application/pdf' in response.headers.get('Content-Type', '').lower():
            log_search(message.from_user.id, "DL PDF", f"{dl_number} ({dob})")
            
            bot.send_document(
                message.chat.id, 
                ('DL_Report.pdf', response.content), 
                caption=f"🪪 <b>DL PDF Downloaded</b>\n🪪 <b>DL:</b> <code>{dl_number}</code>\n💎 <i>Powered by {ADMIN_USERNAME}</i>"
            )
            bot.delete_message(message.chat.id, status_msg.message_id)
            
        else:
            # Handling API error JSON messages if not a PDF
            err_text = "Unknown Error"
            if response:
                try:
                    error_data = response.json()
                    err_text = error_data.get("error", response.text[:50])
                except ValueError:
                    err_text = response.text[:50]
            
            bot.edit_message_text(f"❌ Failed to generate PDF!\nReason: {err_text} (Refunded)", message.chat.id, status_msg.message_id)
            refund_credits(message.from_user.id, 70)
            
    except Exception as e:
        bot.edit_message_text(f"❌ Server Timeout or Error: {str(e)[:50]} (Refunded)", message.chat.id, status_msg.message_id)
        refund_credits(message.from_user.id, 70)

# ================== BOT RUN ==================
if __name__ == "__main__":
    print("🤖 VIP Business Bot is Running (RC & DL PDF Credits updated to 70)...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)