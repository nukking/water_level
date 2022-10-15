import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import requests

# 텔레그램 채널 url
telegram_url = 'https://api.telegram.org/bot5370584924:AAHUC-AwSEyzlnlcWVAgZ-TpVkDwRPMoiDA/sendmessage?chat_id=-1001556285353&text='

# send telegram message
def send_telegram_message(message : str):
    try:
        requests.get(telegram_url+message)
    except:
        print('telegram error')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = requests.get('http://localhost:8000/statuses')
    text1 = '오류발생'
    if r.status_code == 200:
        status1 = r.json()['switch1'].upper()
        status2 = r.json()['switch2'].upper()
        water_level_1 = r.json()['water_level_1']
        water_level_2 = r.json()['water_level_2']
        text1 = f'[강동 수위 모니터 현재 상태]\n출입구 아래 펌프 : {status1}, 수위 : {water_level_1}\n주방 아래 펌프 : {status2}, 수위 : {water_level_2}'
        #send_telegram_message(message = text1)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text1)

async def turnon1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-on/0").json())

async def turnon2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-on/1").json())

async def turnoff1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-off/0").json())

async def turnoff2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-off/1").json())

async def test1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='출입구 아래 점검 시작!')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-check/0").text.replace('"', '',2))

async def test2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='주방 아래 점검 시작!')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=requests.get("http://localhost:8000/switch-check/1").text.replace('"', '',2))

if __name__ == '__main__':
    application = ApplicationBuilder().token('5370584924:AAHUC-AwSEyzlnlcWVAgZ-TpVkDwRPMoiDA').build()
    
    status_handler = CommandHandler('status', status)
    turnon1_handler = CommandHandler('turnon1', turnon1)
    turnon2_handler = CommandHandler('turnon2', turnon2)
    turnoff1_handler = CommandHandler('turnoff1', turnoff1)
    turnoff2_handler = CommandHandler('turnoff2', turnoff2)
    test1_handler = CommandHandler('test1', test1)
    test2_handler = CommandHandler('test2', test2)
    
    application.add_handler(status_handler)
    application.add_handler(turnon1_handler)
    application.add_handler(turnon2_handler)
    application.add_handler(turnoff1_handler)
    application.add_handler(turnoff2_handler)
    application.add_handler(test1_handler)
    application.add_handler(test2_handler)
    
    application.run_polling()