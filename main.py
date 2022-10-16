from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import RPi.GPIO as GPIO
import requests
import serial
from datetime import datetime, timedelta
from mysql.connector import pooling
import time

# mariadb pool init
pool = pooling.MySQLConnectionPool(pool_name = "mypool",
                                    pool_size = 20,
                                    pool_reset_session = True,
                                    host = 'localhost',
                                    database = 'water',
                                    user = 'gangdong',
                                    password = 'gangdong')

# 데이터 입력
def save_pump_logs(site : str, event : str, user_id : str):
    con = pool.get_connection()
    try:
        cursor_event = con.cursor()
        insert_data = [{'event_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'site': site,'event': event}]
        insert_pump_logs_sql = "insert into pump_logs (event_time, site, event) values (%(event_time)s, %(site)s, %(event)s);"
        cursor_event.executemany(insert_pump_logs_sql, insert_data)
        con.commit()
        cursor_event.close()
    finally:
        con.close()

def save_water_logs(v1 : int, v2 : int, status1 : int, status2 : int, v1_high : int,v1_low : int, v2_high : int, v2_low : int):
    con = pool.get_connection()
    try:
        cursor_log = con.cursor()
        insert_data = [{'v1': v1, 'v2': v2, 'status1':status1, 'status2':status2,'v1_high': v1_high, 'v1_low': v1_low, 'v2_high': v2_high, 'v2_low': v2_low}]
        insert_water_level_sql = "insert into water_level3 (v1,v2,status1, status2,v1_high,v1_low,v2_high,v2_low) values ( %(v1)s, %(v2)s, %(status1)s, %(status2)s, %(v1_high)s, %(v1_low)s, %(v2_high)s, %(v2_low)s);"
        cursor_log.executemany(insert_water_level_sql, insert_data)
        con.commit()
        cursor_log.close()
    finally:
        con.close()

# 텔레그램 채널 url
telegram_url = 'https://api.telegram.org/bot5370584924:AAHUC-AwSEyzlnlcWVAgZ-TpVkDwRPMoiDA/sendmessage?chat_id=-1001556285353&text='

# send telegram message
def send_telegram_message(message : str):
    try:
        requests.get(f'{telegram_url}{message}')
    except:
        print('telegram error')

# app init
app = FastAPI()

# GPIO settings, init
GPIO.setmode(GPIO.BCM)                      # GPIO 핀들의 번호를 지정하는 규칙 설정
GPIO.setwarnings(False)                     # warning off
app.pin = [25,24]                           # 컨트롤 핀번호
app.site_name = ['출입구 아래','주방 아래']      # 사이트 명
GPIO.setup(app.pin[0], GPIO.OUT)
GPIO.setup(app.pin[1], GPIO.OUT)
GPIO.output(app.pin[0], GPIO.LOW)
GPIO.output(app.pin[1], GPIO.LOW) 

# config
app.on_count_limit = 120    # on 이후로 제한수치 이상 루프 돌면 강제 종료
app.on_value = [180,130]    # 스위치 on 되는 default 수치
app.off_value = [90,70]     # 스위치 off 되는 default 수치
app.limit_count = 2         # 1회성 수치에 동작 방지를 위한 연속 수치도달 카운터, 변수값만큼 반복 시 스위치 온/오프
app.test_start_limit = [110,90] # 점검 시작 가능 수위 
app.test_sleep_seconds = [8,11]  # 점검 시 펌프 가동 시간 초

# variable init
app.status = ['off','off']      # 모터 상태 변수 on/off
app.status_num = [0,0]          # 모터 상태 변수 1/0
app.on_count = [0,0]            # 스위치 온 이후 몇회 반복인지 확인 변수
app.water_level = [0,0]         # 현재 수위 변수
app.none_count = [0,0]          # 수위 확인 값이 None/에러 으로 1회성 동작으로 인한 연속 도달 확인 변수 
app.high_limit_count = [0,0]    # 1회성 수치에 동작 방지를 위한 제한 수위 연속 도달 횟수 변수_위
app.low_limit_count = [0,0]     # 1회성 수치에 동작 방지를 위한 제한 수위 연속 도달 횟수 변수_아래

# usuful variables
app.last_on_time = [None,None]
app.last_off_time = [None,None]

# serial port init
app.ser = serial.Serial('/dev/ttyUSB0', 57600, timeout = 1)
app.ser.flush()

# CORS settings, 모두 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_water_level(site_index : int = 2):
    return app.water_level[site_index]

def get_average_water_level(site_index : int = 2, second : int = 1):
    count = 0
    water_level = 0
    while(second > count):
        water_level = water_level + get_water_level(site_index)
        time.sleep(1)
        count = count + 1
    return int(water_level/second)

def monitor():
    # limit value set
    vv1_high = 190
    vv1_low = 60
    vv2_high = 180
    vv2_low = 60
    v1 = None
    v2 = None
    # 커서 획득
    con = pool.get_connection()
    try:
        cursor = con.cursor()
        # 데이터 조회
        select_sql = "select max(date_l) mm, round(avg(v1)) v1, round(avg(v2)) v2 from water_level3 where date_l > date_sub(now(), interval 10 second)"
        cursor.execute(select_sql)
        result = cursor.fetchall()
        if(len(result) > 0):
            for data in result:
                if(data[0] == None):
                    send_telegram_message(message = f'[E1] : 센싱값 저장 오류, wl1:{app.water_level[0]}, wl2:{app.water_level[1]}')
                else:
                    v1 = data[1]
                    v2 = data[2]
        else:
            send_telegram_message(message = f'[E1] : 센싱값 저장 오류, wl1:{app.water_level[0]}, wl2:{app.water_level[1]}')
        cursor.close()
    finally:
        con.close()
    if(v1 > vv1_high or app.water_level[0] > vv1_high):
        send_telegram_message(message = f'[E2] : 출입구 아래 수위 높음, v1:{v1}, wl1:{app.water_level[0]}')
        switch_on(user_id = 'AI', site_index = 0, message = '')
    if(v1 < vv1_low or app.water_level[0] < vv1_low):
        send_telegram_message(message = f'[E3] : 출입구 아래 수위 낮음, v1:{v1}, wl1:{app.water_level[0]}')
        switch_off(user_id = 'AI', site_index = 0, message = '')
    if(v2 > vv2_high or app.water_level[1] > vv2_high):
        send_telegram_message(message = f'[E2] : 주방 아래 수위 높음, v2:{v2}, wl2:{app.water_level[1]}')
        switch_on(user_id = 'AI', site_index = 1, message = '')
    if(v2 < vv2_low or app.water_level[1] < vv2_low):
        send_telegram_message(message = f'[E3] : 주방 아래 수위 낮음, v2:{v2}, wl2:{app.water_level[1]}')
        switch_off(user_id = 'AI', site_index = 1, message = '')

def sensing():
    if app.ser.in_waiting > 0:
        line = app.ser.readline().decode('utf-8').rstrip()
        sensor = line.split(',')
        app.status_num[0] = 1 if GPIO.input(app.pin[0]) == GPIO.HIGH else 0
        app.status_num[1] = 1 if GPIO.input(app.pin[1]) == GPIO.HIGH else 0
        print(f'sensing : {line}, {app.status_num[0]}, {app.status_num[1]}, {app.status[0]}, {app.status[1]}')
        app.water_level[0] = int(sensor[0])
        app.water_level[1] = int(sensor[1])
        save_water_logs(int(sensor[0]),int(sensor[1]),app.status_num[0],app.status_num[1],app.on_value[0],app.off_value[0],app.on_value[1],app.off_value[1])

def control(site : str = '0'):
    site_index = int(site) - 1
    water_level = app.water_level[site_index]
    if(app.status[site_index] == 'off'):
        if GPIO.input(app.pin[site_index]) == GPIO.HIGH:
            print(f'control{site_index} status changed on - status not matched')
            app.status[site_index] = 'on'
    if(app.status[site_index] == 'on'):
        app.on_count[site_index] += 1
        if(app.on_count[1] > app.on_count_limit):
            app.status[site_index] = 'off'
            switch_off(user_id = 'AI', site_index = site_index, message = ', 시간제한')
            print(f'control{site_index} turned off - time limit')
            app.on_count[site_index] = 0
            return
        else:
            if(water_level <= app.off_value[site_index]):
                app.low_limit_count[site_index] += 1
                if(app.low_limit_count[site_index] > app.limit_count):
                    app.status[site_index] = 'off'
                    switch_off(user_id = 'AI', site_index = site_index, message = f', 현재수위 {water_level}')
                    print(f'control{site_index} turned off - low water level')
                    app.low_limit_count[site_index] = 0
            else:
                if(app.low_limit_count[1] > 0):
                    app.low_limit_count[site_index] = 0
            return
    else:
        if(app.on_count[site_index] > 0 ):
            app.on_count[site_index] = 0
        if(water_level >= app.on_value[site_index]):
            app.high_limit_count[site_index] += 1
            if(app.high_limit_count[site_index] > app.limit_count):
                app.status[site_index] = 'on'
                switch_on(user_id = 'AI', site_index = site_index, message = f', 현재수위 {water_level}')
                print(f'control{site_index} turned on - high water level')
                app.high_limit_count[site_index] = 0
        else:
            if(app.high_limit_count[site_index] > 0):
                app.high_limit_count[site_index] = 0
        return
def daily_check():
    switch_check(site_index = 0)
    switch_check(site_index = 1)

def tests():
    send_telegram_message(message = 'test!!')

# scheduler settings
app.scheduler = AsyncIOScheduler({'apscheduler.job_defaults.max_instances': 5})
app.scheduler.add_job(sensing, 'interval', seconds = 0.5)
app.scheduler.add_job(monitor, 'interval', seconds = 20)
app.scheduler.add_job(control, 'interval', seconds = 1, args = ('1'))
app.scheduler.add_job(control, 'interval', seconds = 1, args = ('2'))
app.scheduler.add_job(daily_check, 'cron', hour='6', minute='0')
app.scheduler.start()

# web services
@app.get("/")
def read_root():
    return 'Hello World'

@app.get("/switch-on/{site_index}")
def switch_on(site_index : int = 2, user_id : str = 'AI', message : str = ''):
    is_possible = False
    site_pin = app.pin[site_index]
    site_name = app.site_name[site_index]
    water_level = app.water_level[site_index]

    if(app.water_level[site_index] > app.off_value[site_index]):
        is_possible = True

    if(len(str(site_pin)) > 0):
        #현재 수위가 OFF 기준보다 낮으면 실행 불가
        if(is_possible):
            GPIO.output(site_pin, GPIO.HIGH)
            save_pump_logs(site = str(site_index+1), event = 'on', user_id = user_id)
            if(message == ''):
                message  = f', 현재수위 {water_level}'
            if(user_id != 'AI'):
                send_telegram_message(message = f'[{site_name}] 펌프 ON({user_id}{message})')
        else:
            if(user_id != 'AI'):
                send_telegram_message(message = f'[{site_name}] 펌프 ON 불가 - 수위가 낮음')
            return {"message": 'switch OFF'}
    app.status[site_index] = 'on'
    app.last_on_time[site_index] = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

    return {"site": str(site_index), "switch": 'on'}

@app.get("/switch-off/{site_index}")
def switch_off(site_index : int = 2, user_id : str = 'AI', message : str = ''):
    is_possible = False
    site_pin = app.pin[site_index]
    site_name = app.site_name[site_index]
    water_level = app.water_level[site_index]

    if(len(str(site_pin)) > 0):
        if GPIO.input(site_pin) == GPIO.HIGH:
            GPIO.output(site_pin, GPIO.LOW)
            save_pump_logs(site = str(site_index+1), event = 'off', user_id = user_id)
            if(message == ''):
                message  = f', 현재수위 {water_level}'
            if(user_id != 'AI'):
                send_telegram_message(message = f'[{site_name}] 펌프 OFF({user_id}{message})')
        else:
            GPIO.output(site_pin, GPIO.LOW)
            send_telegram_message(message = f'[{site_name}] 펌프 OFF 불가(현재 OFF)')
            return {"message": 'switch OFF'}
    app.status[site_index] = 'off'
    app.last_off_time[site_index] = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
    return {"site": str(site_index), "switch": 'off'}

@app.get("/switch-check/{site_index}")
def switch_check(site_index : int = 2, user_id : str = 'AI', message : str = ''):
    start_level = get_average_water_level(site_index = site_index, second = 4)
    if start_level > app.test_start_limit[site_index]:
        switch_on(user_id = user_id, site_index = site_index, message = message)
        time.sleep(app.test_sleep_seconds[site_index])
        switch_off(user_id = user_id, site_index = site_index, message = message)
        pump_stop_level = get_average_water_level(site_index = site_index, second = 4)
        time.sleep(5)
        end_level = get_average_water_level(site_index = site_index, second = 4)
        message = f'[점검 결과] 시작 : {start_level}, 중지 : {pump_stop_level}, 종료 : {end_level}'
    else:
        message = f'수위 기준 이하 : {start_level}'
    send_telegram_message(message = f'[{app.site_name[site_index]}]\n{message}')
    return message

@app.get("/statuses")
def get_statuses():
    s0 = 'on' if GPIO.input(app.pin[0]) == GPIO.HIGH else 'off'
    s1 = 'on' if GPIO.input(app.pin[1]) == GPIO.HIGH else 'off'
    return {"switch1" : s0, "switch2" : s1, "water_level_1" : app.water_level[0] , "water_level_2" : app.water_level[1]}

@app.get("/last_on_time/{site_index}")
def get_last_on_time(site_index : int):
    return app.last_on_time[site_index]

@app.get("/last_off_time/{site_index}")
def get_last_off_time(site_index : int):
    return app.last_off_time[site_index]

@app.get("/set_on/{site_index}/{high}")
def set_on(site_index: int, high: int):
    app.on_value[site_index] = high        # 스위치 on 되는 수치
    return {"on_value[0]" : app.on_value[0], "on_value[1]" : app.on_value[1]}

@app.get("/set_off/{site_index}/{low}")
def set_off(site_index: int, low: int):
    app.off_value[site_index] = low        # 스위치 off 되는 수치
    return {"off_value[0]" : app.off_value[0], "off_value[1]" : app.off_value[1]}
