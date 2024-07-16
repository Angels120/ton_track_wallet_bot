import requests
import json
import time
import re
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, KeyboardButton, ReplyKeyboardMarkup, BotCommand
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from bs4 import BeautifulSoup
from collections import Counter
import struct
import base64

# TELEGRAM_BOT_TOKEN = '7020905024:AAE3zL6JSQlEgi5jRJZLTpFTsozvAoMkHbo'
TELEGRAM_BOT_TOKEN = '6533247407:AAEvW7gW_3LhINMiacNEVq5E41bLx4p113A'
# TELEGRAM_BOT_TOKEN = '7375760689:AAGQkMozY42mSz7ZUdI6BpePp0VyO8A8LMA'
# YOUR_TELEGRAM_USER_ID = 7314466396
YOUR_TELEGRAM_USER_ID = 5099082627

# Replace with your actual API key
api_key = '8cca03a2e544d87b519bf869291e497c4d81bf78cb0f0a7f04d4936eef5f8470'
ADD_WALLET_ADDRESS, WALLET_LIST, SETTINGS, WALLET_NAME, BROADCAST, ADD_BUTTONS, ADD_QUE = range(7)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_last_transaction(wallet_address):
    url = f"https://toncenter.com/api/v2/getTransactions?address={wallet_address}&limit=1&to_lt=0&archival=false&api_key={api_key}"
    response = requests.get(url)
    # data = json.loads(response.text)
    data = response.json()
    return data.get('result', [])[0] if data.get('ok') and len(data["result"]) != 0 else None

def get_ton_price():
    try:
        url = "https://tonapi.io/v2/rates?tokens=ton&currencies=usd"
        response = requests.get(url)
        # data = json.loads(response.text)
        if response.status_code == 200:
            data = response.json()
            return data.get('rates', {}).get('TON', {}).get('prices', {}).get('USD', 0)
        else :
            return 0
    except Exception as e:
        return 0

def add_buttons(update : Update, context: CallbackContext):
    if(update.message.text == 'empty'):
        update.message.reply_text("Please input message with photo")
        return BROADCAST
    text = update.message.text.split(',')
    button_name = text[0]
    button_link = text[1]
    context.user_data['buttons'].append({'button_name' : button_name, 'button_link': button_link})
    print("buttons", context.user_data['buttons'])
    update.message.reply_text("Do you want to another button? If yes, type add, else empty")
    return ADD_QUE
def add_que(update: Update, context: CallbackContext):
    text = update.message.text
    if(text == "add"):
        return ADD_BUTTONS
    elif(text == "empty"):
        update.message.reply_text("Please input message with photo")
        return BROADCAST

def getAllUsers():
    users = []
    with open("watched_wallets.txt", "r") as f:
        for line in f:
            wallet_info = line.strip().split(',')
            users.append(f"{wallet_info[1]}")
    print("users: ", list(set(users)))
    return list(set(users))

def send_announcement(update: Update, context: CallbackContext):
    print("sending message")
    photo_file = update.message.photo[-1].get_file()
    if photo_file:
        photo_url = photo_file.file_id
    print(photo_url)
    owner_id = update.message.from_user.id  # Owner's user ID (for demonstration purposes)
    allowed_owner_id = YOUR_TELEGRAM_USER_ID  # Replace with your actual Telegram user ID

    if owner_id != allowed_owner_id:
        update.message.reply_text('You are not authorized to send announcements.')
        return
    customButtons = context.user_data['buttons']
    print("custome buttons : ", customButtons)
    users = getAllUsers()
    # Define the announcement details
    announcement_text = update.message.caption
    # photo_url = 'https://img.icons8.com/papercut/60/communication.png'  # Replace with your photo URL
    buttons = []
    for button in customButtons:
        # json_button = json.loads(button)
        buttons.append([InlineKeyboardButton(button["button_name"].strip(), url = button["button_link"].strip())])
    # buttons = [
    #     [InlineKeyboardButton("Learn More", url='https://example.com/learn-more')],
    #     [InlineKeyboardButton("Visit Website", url='https://example.com')],
    # ]
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        for user in users:
            print()
            context.bot.send_photo(
                chat_id=user,
                photo=photo_url,
                caption=announcement_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.warning(f"Failed to send message to {owner_id}: {e}")
    context.user_data['buttons'] = []
    return ConversationHandler.END

def get_top_wallet_addresses(top_n=5):
    with open("watched_wallets.txt", 'r') as file:
        lines = file.readlines()
    wallet_addresses = []
    for line in lines:
        parts = line.strip().split(',')
        wallet_addresses.append(parts[0])
    address_counts = Counter(wallet_addresses)
    return address_counts.most_common(top_n)
def getContractAddress(raw_address):
    endpoint = 'https://toncenter.com/api/v3/addressBook'

    # Construct the request URL
    url = f'{endpoint}?address={raw_address}&api_key={api_key}'

    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if f'{raw_address}' in data:
            return data[f'{raw_address}']['user_friendly']
        else:
            # raise Exception(f"Error in response: {data}")
            return ""
    else:
        # raise Exception(f"Failed to fetch address information: {response.status_code}")
        return ""
def format_transaction_message(transaction, ton_price , user_id, wallet_name, wallet_address):
    try:
        address = transaction.get('address', {}).get('account_address', 'Unknown')
        transaction_id = transaction.get('transaction_id', {}).get('hash', 'Unknown')
        # getmsg = requests.get(f"https://tonapi.io/v2/accounts/{wallet_address}/events?limit=2").json()
        out_msgs = transaction.get('out_msgs', [])
        raw_address = ""
        contract_address = ""
        if out_msgs:
            value_ton = int(out_msgs[0].get('value', 0)) / 10**9
            # if getmsg.get("events", []) and getmsg["events"][0].get("actions", []) and getmsg["events"][0]["actions"][0].get("JettonTransfer", {}).get("jetton", {}).get("name", ""):
            #     token_name = getmsg["events"][0]["actions"][0]["JettonTransfer"]["jetton"]["name"]
            #     raw_address = getmsg["events"][0]["actions"][0]["JettonTransfer"]["jetton"]["address"]
            #     print("address: ", raw_address)
            # else:
            #     print("error failed fetch token name")
        else:
            return "yok"
        # if(raw_address != ""):
        #     contract_address = getContractAddress(raw_address)
        # print("contract address: ", contract_address)
        value_usd = value_ton * ton_price
        limit = getLimit(user_id)
        print(limit)
        if float(limit) > value_usd:
            return "yok"
        alert_text = "⚠️ <u><b>New Transaction Alert</b></u> ⚠️"
        link = f"https://tonscan.org/tx/{transaction_id}"
        
        if value_usd > 2000:
            alert_text += "\n\n🐳 Whale Alert 🐳"
        message = f"{alert_text}\n\nA new Transaction detected on {address}\n\n♻️ <a href='{link}'>Tonscan</a> with a value of {value_ton} TON (${value_usd:.2f})\n\nPowered By @resistanceCatTon -"
        # message = f"{alert_text}\n\n🔍 Wallet Address: \n <code>{address}</code>-({wallet_name})\n 🔄  Tonscan Transaction : {value_ton} TON (${value_usd:.2f})\n 📈 Token Name : {token_name}\n 📝 Contract Address: <code>{contract_address}</code>\n\n Powered By @resistanceCatTon -"
        return message
    except Exception as e:
        print("error", e)
        return "yok"

def kontrolswap(transaction, wallet_address, ton_price, user_id, wallet_name):
    try:
        if not transaction:
            return "yok"
        out_msgs = transaction.get('out_msgs', [])
        if out_msgs:
            print("outmsg: ", out_msgs)
            value_ton = int(out_msgs[0].get('value', 0)) / 10**9
            # if getmsg.get("events", []) and getmsg["events"][0].get("actions", []) and getmsg["events"][0]["actions"][0].get("JettonTransfer", {}).get("jetton", {}).get("name", ""):
            #     token_name = getmsg["events"][0]["actions"][0]["JettonTransfer"]["jetton"]["name"]
            #     raw_address = getmsg["events"][0]["actions"][0]["JettonTransfer"]["jetton"]["address"]
            #     print("address: ", raw_address)
            # else:
            #     print("error failed fetch token name")
        else:
            return "yok"
        raw_address = ""
        contract_address = ""
        getmsg = requests.get(f"https://tonapi.io/v2/accounts/{wallet_address}/events?limit=2").json()
        if getmsg.get("events", []) and getmsg["events"][0].get("actions", []) and getmsg["events"][0]["actions"][0].get("simple_preview", {}).get("description", ""):
            if getmsg["events"][0]["actions"][0]["simple_preview"]["name"] == "Swap Tokens":
                token_name = ""
                if getmsg.get("events", []) and getmsg["events"][0].get("actions", []) and getmsg["events"][0]["actions"][0].get("JettonSwap", {}).get("jetton_master_out", {}).get("name", ""):
                    token_name = getmsg["events"][0]["actions"][0]["JettonSwap"]["jetton_master_out"]["name"]
                    raw_address = getmsg["events"][0]["actions"][0]["JettonSwap"]["jetton_master_out"]["address"]
                    print("address: ", raw_address)
                else:
                    print("error failed fetch token name")
                    return "yok"
                if(raw_address != ""):
                    contract_address = getContractAddress(raw_address)
                print("contract address: ", contract_address)
                value_usd = value_ton * ton_price
                limit = getLimit(user_id)
                print(limit)
                if float(limit) > value_usd:
                    return "yok"
                description = getmsg["events"][0]["actions"][0]["simple_preview"]["description"]
                sayı = int(re.search(r'\b\d+\b', description).group())  # Dizeyi sayıya dönüştür
                emoji = ""
                if sayı < 30:
                    emoji = "🦐"
                elif 30 < sayı < 100:
                    emoji = "🐟"
                elif sayı > 100:
                    emoji = "🦧"
                elif sayı > 600:
                    emoji = "🐋"

                new_description = f"{description} {emoji} "
                message = f"💹 <u><b>New Swap Alert</b></u> 💹\n\n 🔍 Wallet Address: \n <code>{wallet_address}</code>-({wallet_name})\n\n\n🔄  Tonscan Transaction : {value_ton} TON (${value_usd:.2f})<br> 📈 Token Name : {token_name}<br> 📝 Contract Address: <code>{contract_address}</code><br><br> Powered By @resistanceCatTon -"
                return message
            else:
                return "yok"
        else:
            return "yok"
    except Exception as e:
        print("error", e)
        return "yok"

def send_telegram_notification(message, user_id):
    try:
        keyboard = {
            'inline_keyboard': [
                [{'text': 'Promote your token', 'url': 'https://t.me/RECA_Support'}]
            ]
        }

        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        # keyboardMarkup = InlineKeyboardMarkup(keyboard)
        payload = {'chat_id': user_id, 'text': message, 'parse_mode': 'HTML', 'reply_markup': json.dumps(keyboard)}
        response = requests.post(url, json=payload)
        print(response)
        return response.ok
    except Exception as e:
        print(f"An error occurred while sending Telegram notification: {e}")
        return False

def add_wallet(wallet_address, user_id , wallet_name):
    with open("watched_wallets.txt", "a") as f:
        f.write(f"{wallet_address},{user_id},{wallet_name}\n")

def addSetting(user_id, limit):
    with open("settings.txt", "r") as f:
        lines = f.readlines()
        filtered_lines = []
        for line in lines:
            try:
                if not re.search(str(user_id), str(line)):
                    filtered_lines.append(line)
            except Exception as e:
                print(f"An error occurred while processing line: {line}. Error: {e}")
        filtered_lines.append(f"{user_id},{limit}\n")
    with open("settings.txt", "w") as file:
        for wline in filtered_lines:
            file.write(wline)
        

def getLimit(user_id):
    with open("settings.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().split(',')
            if int(parts[0]) == user_id:
                return parts[1]
    return "0"





def get_user_for_wallet(wallet_address):
    with open("watched_wallets.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().split(',')
            if parts[0] == wallet_address:
                return parts[1] 
    return None

def remove_wallet(wallet_address):
    with open("watched_wallets.txt", "r") as f:
        lines = f.readlines()
    with open("watched_wallets.txt", "w") as f:
        for line in lines:
            if line.strip().split(',')[0] != wallet_address:
                f.write(line)

def display_wallets(userid):
    user_wallets = []
    with open("watched_wallets.txt", "r") as f:
        for line in f:
            wallet_info = line.strip().split(',')
            if wallet_info[1] == str(userid): 
                user_wallets.append(f"{wallet_info[0]} Name : ({wallet_info[2]})")
    return user_wallets

def is_address_valid(address: str) -> bool:
    try:
        address_regex = r'^[\S]{48}$'
        return re.match(address_regex, address) is not None
    except Exception as e:
        return False


def start(update: Update, context: CallbackContext):
    userid = update.message.chat_id
    wallets = display_wallets(userid)
    wallet_length = len(wallets)
    context.user_data['buttons'] = []
    message = """
<b><u>Welcome to "TON Whale Tracker"  - a product of @resistanceCatTon Ecosystem ! </u></b>

🐳 Add the wallets you want to track and get notified on all their token transactions. 

🤫 Track Alpha Wallets with our "<b>Most Tracked Wallets</b>" feature. 

💪 Say goodbye to missing out on insider tokens! Track TON WHALE wallets and see what they're buying before anyone else. 

📢 Book ad slots now and get your token’s ad featured in every single transaction notification for all users of our bot!

📝 Type /start to get started. <b>Happy Tracking</b> future Whales 🐳
    """
    keyboard = [
        [InlineKeyboardButton("➕ Add", callback_data='add'), InlineKeyboardButton(f"👛 Wallets({wallet_length}/3)", callback_data='wallet')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🤖 Support", callback_data='support')],
        [InlineKeyboardButton("📈 Most Tracked Wallets", callback_data='top')],
        [InlineKeyboardButton("🛎 Book Ad Slots", url='https://t.me/RECA_Support')],
    ]


    if(userid == YOUR_TELEGRAM_USER_ID):
        keyboard.append([InlineKeyboardButton("🔈 Send to All", callback_data='broadcast')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    # context.bot.send_message(chat_id=update.message.chat_id, text=message)
    update.message.reply_photo(photo="https://www.dropbox.com/scl/fi/cm8o459ydk8y43dstivar/Reca_photo.jpg?rlkey=n40jvmanrrurfthm0g409ysqv&st=1xyksnzq&dl=0", caption=message, reply_markup=reply_markup, parse_mode='HTML')
    # update.message.reply_text(message, reply_markup=reply_markup)
    # custom_keyboard = [
    #     [KeyboardButton("/add"), KeyboardButton("/help")],
    #     [KeyboardButton("/info")]
    # ]
    # reply_markup = ReplyKeyboardMarkup(custom_keyboard)

    # update.message.reply_text('Please choose:', reply_markup=reply_markup)

def button(update : Update, context : CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if query.data == 'add':
        # add(update, context)
        query.message.reply_text('Please provide a wallet address to add.')
        
        return ADD_WALLET_ADDRESS
    elif query.data == 'wallet':
        # query.message.reply_text("Wallet list")
        list_wallets(query, context)
    elif query.data == 'support':
        query.message.reply_text(text="Help command executed!")
    elif query.data == 'current_setting':
        current_setting = getLimit(query.message.chat_id)
        query.message.reply_text(text=f"current limit is {current_setting}$.")
    elif query.data == 'change_setting':
        query.message.reply_text('Please specify the dollar amount for which you want to receive transaction notifications from your tracked wallet. For example, if you set the limit to $1000, you will only be notified of transactions exceeding $1000.')
        return SETTINGS
    elif query.data == 'settings':
        settings_button = [
            [InlineKeyboardButton("Current Settins", callback_data="current_setting"),InlineKeyboardButton("Change", callback_data="change_setting")]
            ]
        reply_markup = InlineKeyboardMarkup(settings_button)
        query.message.reply_text("Limit Setting", reply_markup=reply_markup)
    elif query.data == 'broadcast':
        query.message.reply_text('Do you want to add buttons with message? If yes, please input button name and link. eg:"add, https://example.com". Else please input empty.')
        return ADD_BUTTONS
    elif query.data == 'top':
        getTop5(query, context)

def handle_callback_start(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    # Call the start function directly
    start(query, context)
    return ConversationHandler.END

def handle_address(update, context):
    userid = update.message.chat_id
    wallets = display_wallets(userid)
    wallet_length = len(wallets)
    if(wallet_length < 3):

        if(is_address_valid(update.message.text) != True):
            update.message.reply_text("Please enter valid address")
            return ADD_WALLET_ADDRESS
        context.user_data['wallet_address'] = update.message.text
        
        update.message.reply_text("please enter the wallet name")
        return WALLET_NAME
    else : 
        update.message.reply_text("The max number of wallets is 3")
        return ConversationHandler.END

def handle_walletName(update, context):
    wallet_name = update.message.text
    wallet_address = context.user_data.get('wallet_address')
    user_id = update.message.chat_id
    add_wallet(wallet_address, user_id, wallet_name)
    message = f'Added {wallet_address} to the list of watched wallets with name {wallet_name}.'
    # context.bot.send_message(chat_id=update.message.chat_id, text=message)
    update.message.reply_text(message)
    return ConversationHandler.END


def add(update : Update, context : CallbackContext):
    if len(context.args) < 1:
        context.bot.send_message(chat_id=update.message.chat_id, text="Please provide a wallet address to add.")
        return

    wallet_address = context.args[0]
    wallet_name = context.args[1] if len(context.args) > 1 else "belirtilmedi"

    user_id = update.message.chat_id  
    add_wallet(wallet_address, user_id, wallet_name)
    message = f'Added {wallet_address} to the list of watched wallets with name {wallet_name}.'
    context.bot.send_message(chat_id=update.message.chat_id, text=message)

def settings(update, context):
    limit = update.message.text
    user_id = update.message.chat_id
    if limit.isdigit():  # Check if the message contains only digits
        addSetting(user_id, limit)
        message = f'Limit set to {limit}$ . From now on, only transactions above {limit}$ will be notified. Happy tracking!'
        # context.bot.send_message(chat_id=update.message.chat_id, text=message)
        update.message.reply_text(message)
        return ConversationHandler.END
    else:
        update.message.reply_text('Please send a valid number.')
        return SETTINGS
    

def remove(update, context):
    if len(context.args) < 1:
        context.bot.send_message(chat_id=update.message.chat_id, text="Please provide a wallet address to remove.\nUsage: /remove 0:123456789abcdef")
        return

    wallet_address = context.args[0]
    remove_wallet(wallet_address)
    message = f'Removed {wallet_address} from the list of watched wallets.'
    context.bot.send_message(chat_id=update.message.chat_id, text=message)

def getTop5(update: Update, context: CallbackContext):
    top_addresses = get_top_wallet_addresses()
    message = "🐳 <b><u>MOST TRACKED WALLETS</u></b> 🐳 \n\n"
    i = 0
    for address, count in top_addresses:
        i += 1
        text = "Users" if(count > 1) else "User"
        message += f"<b>{i}. Address:</b> <code>{address}</code>\n <b>Tracked By</b> {count} {text}\n\n"
        print(f"Address: {address} - Used {count} times.")
    update.message.reply_text(text=message, parse_mode='HTML')

def list_wallets(update, context):
    userid = update.message.chat_id
    print(userid)
    wallets = display_wallets(userid)  
    if wallets:
        message = "The following wallets are currently being monitored\n"
        message += "\n".join(wallets)
        context.bot.send_message(chat_id=update.message.chat_id, text=message)
    else:
        message = "There are no wallets currently being monitored."
        context.bot.send_message(chat_id=update.message.chat_id, text=message)


def whale_tracker(update, context):
    message = "🐳 Whale Tracker feature is coming soon! 🐋"
    context.bot.send_message(chat_id=update.message.chat_id, text=message)

def reca(update, context):
    message = """
😻 Telegram - @resistanceCatTon
😽 Twitter - https://x.com/ResistanceCat
🐳 Coingecko - https://www.coingecko.com/en/coins/the-resistance-cat
💪 [Buy](https://t.me/stonks_sniper_bot?start=321781bbbefd7c99a7fa1e0c7cfd0704)
"""
    context.bot.send_message(chat_id=update.message.chat_id, text=message, parse_mode='Markdown')

def load_last_transaction_ids():
    try:
        with open('last_transaction_ids.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_last_transaction_ids(last_transaction_ids):
    with open('last_transaction_ids.json', 'w') as file:
        json.dump(last_transaction_ids, file)

def load_last_swap_ids():
    try:
        with open('last_swap_ids.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_last_swap_ids(last_swap_ids):
    print("saving swap id")
    with open('last_swap_ids.json', 'w') as file:
        json.dump(last_swap_ids, file)

def getwallets():
    wallets = []
    try:
        with open("watched_wallets.txt", "r") as f:
            for line in f:
                wallet_info = line.strip().split(',')
                wallets.append((wallet_info[0], wallet_info[1], wallet_info[2]))
    except Exception as e:
        print(f"An error occurred while reading watched wallets: {e}")
    return wallets



def monitor_transactions():
    while True:
        last_transaction_ids = load_last_transaction_ids()
        last_swap_ids = load_last_swap_ids()
        wallets = getwallets()
        for wallet_info in wallets:
            wallet_address, user_id, wallet_name = wallet_info
            print(wallet_address, user_id, wallet_name)
            last_transaction_id = last_transaction_ids.get(wallet_address, "")
            last_swap_id = last_swap_ids.get(wallet_address, "")
            transaction = get_last_transaction(wallet_address)
            # print(transaction)
            # print(wallet_address, ": ", transaction['transaction_id']['hash'], " :", last_transaction_id, ": ", last_swap_id)
            ton_price = get_ton_price()
            # if transaction and transaction['transaction_id']['hash'] != last_transaction_id:
            #     print("transaction alert", last_transaction_id, transaction['transaction_id']['hash'])
            #     if user_id:
            #         user_message = format_transaction_message(transaction, ton_price , user_id, wallet_name, wallet_address)
            #         print("transaction: ", user_message)
            #         if user_message == "yok":
            #             print("not transaction")
            #         elif send_telegram_notification(user_message, user_id):
            #             print("Telegram notification sent successfully.")
            #         else:
            #             print("Failed to send Telegram notification.")
            #     last_transaction_ids[wallet_address] = transaction['transaction_id']['hash']
            #     save_last_transaction_ids(last_transaction_ids)
            if transaction and transaction['transaction_id']['hash'] != last_swap_id:
                
                print("swap alert")
                msg = kontrolswap(transaction, wallet_address, ton_price, user_id, wallet_name)
                print("swap :", msg)
                if msg == "yok":
                    print("not swap")
                    continue
                if send_telegram_notification(msg, user_id):
                    print("Telegram notification sent successfully.")
                else:
                    print("Failed to send Telegram notification.")
                last_swap_ids[wallet_address] = transaction['transaction_id']['hash']
                save_last_swap_ids(last_swap_ids)
            time.sleep(2)
        time.sleep(2)

def set_bot_commands(updater):
    commands = [
        BotCommand("start", "Start interacting with the bot"),
        BotCommand("list", "Get wallet list"),
        BotCommand("whale_tracker", "whale_tracker"),
        BotCommand("reca", "reca"),
        BotCommand("top", "Most tracked wallets"),
        # Add more commands as needed
    ]
    updater.bot.set_my_commands(commands)

updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
set_bot_commands(updater)
start_handler = CommandHandler('start', start)
add_handler = CommandHandler('add', add)
remove_handler = CommandHandler('remove', remove)
list_handler = CommandHandler('list', list_wallets)
whale_tracker_handler = CommandHandler('whale_tracker', whale_tracker)
reca_handler = CommandHandler('reca', reca)
get_top_wallet_handler = CommandHandler('top', getTop5)

conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            ADD_WALLET_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, handle_address),
                ],
            WALLET_LIST : [MessageHandler(Filters.text & ~Filters.command, list_wallets)],
            WALLET_NAME : [MessageHandler(Filters.text & ~Filters.command, handle_walletName)],
            SETTINGS : [MessageHandler(Filters.text & ~Filters.command, settings)],
            ADD_BUTTONS: [MessageHandler(Filters.text & ~Filters.command, add_buttons)],
            ADD_QUE: [MessageHandler(Filters.text & ~Filters.command, add_que)],
            BROADCAST : [MessageHandler(Filters.all, send_announcement)]
        },
        fallbacks=[start_handler, get_top_wallet_handler, add_handler,remove_handler,list_handler,whale_tracker_handler,reca_handler],
        allow_reentry=True,
    )

dispatcher.add_handler(start_handler)
# dispatcher.add_handler(CallbackQueryHandler(button))
# dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_address))
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(get_top_wallet_handler)
dispatcher.add_handler(add_handler)
dispatcher.add_handler(remove_handler)
dispatcher.add_handler(list_handler)
dispatcher.add_handler(whale_tracker_handler)
dispatcher.add_handler(reca_handler)

updater.start_polling()
print("Telegram bot started.")
monitor_transactions()
