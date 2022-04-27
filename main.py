import network
import time
import sys
import dht
import ds1302
import ntptime
import os
import utime
import urequests
from machine import Pin
from machine import RTC

# CONFIG
REQUEST_URL = 'http://20.121.244.198:8086/write?db=hackaton'  # InfluxDB URL
DEVICE_ID = 1                                               # ID OF ESP DEVICE

# SETUP
sensor = dht.DHT11(Pin(5))                                  # DHT11 sensor
ds = ds1302.DS1302(Pin(18), Pin(19), Pin(21))               # DS1302 module - CLK D18, DAT D19, RST D21
rtc = RTC()                                                 # Internal RTC module

wlan = network.WLAN(network.STA_IF)                         # create station interface
wlan.active(True)                                           # activate wlan interface

def read_and_post_data():
    # prepare data with post timestamps
    data_file = open("data.txt", "r")
    timestamp = 946684800 + utime.time()
    index = 0
    lines = data_file.readlines()
    timestamped_post_data = ""
    for line in lines:
        timestamp = timestamp + index
        timestamp_string = str(timestamp)+'000000000'
        timestamped_line = line.strip('\n')+" "+timestamp_string+'\n'
        timestamped_post_data = timestamped_post_data + timestamped_line
        index = index + 1
    data_file.close()
    # POST
    try:
        print("Trying to send data to InfluxDB.")
        #print(timestamped_post_data)
        urequests.post(REQUEST_URL, headers={"content-type": "text/plain"}, data=timestamped_post_data)
    except:
        print("Unable to post data to InfluxDB. Will try again in 30 minutes.")
    else:
        print("Data send successfully!")
        os.remove("data.txt")

# WIFI CONNECTION
if not wlan.isconnected():
    SSID = ""
    PASS = ""
    try:
        wifi_config = open("wifi-config.txt", "r")
        login_data = wifi_config.read().split(';')
        SSID = login_data[0]
        PASS = login_data[1]
        wifi_config.close()
    except:
        print('Please enter the SSID and password of a WiFi access point.')
        SSID = input('SSID:')
        PASS = input('PASS:')
        print('Connecting to network...')
        wifi_config = open("wifi-config.txt", "w")
        wifi_config.write(SSID+';'+PASS)
        wifi_config.close()
    wlan.connect(SSID, PASS)
    while not wlan.isconnected():
        time.sleep(0.1)
        # TODO watchdog - request SSID and password again in case of bad login
print('NETWORK CONFIG:\n', wlan.ifconfig())

# TIME SYNCHRONIZATION
ntptime.settime()
ds.date_time(rtc.datetime())
print('{:02d}:{:02d}:{:02d} {:02d}.{:02d}.{}'.format(ds.hour(), ds.minute(), ds.second(), ds.day(), ds.month(), ds.year()))

next_post_timestamp = 0
post_ready = True

# COLLECT AND SEND DATA IF CONNECTED
while True:
    if post_ready == False:
        if 946684800 + utime.time() > next_post_timestamp:
            post_ready = True
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        temp_f = temp * (9/5) + 32.0
        print('Temperature: %3.1f C' %temp)
        print('Temperature: %3.1f F' %temp_f)
        print('Humidity: %3.1f %%' %hum)
        utc_timestamp = 946684800 + utime.time()
    except OSError as e:
        print('Failed to read sensor.')
    # write measurement to file
    data_file = open("data.txt", "a")
    utc_timestamp_string = str(utc_timestamp)+'000000000'
    data_string = 'sensors,device_id={} temperature={},humidity={},measurement_timestamp={}\n'.format(DEVICE_ID, temp, hum, utc_timestamp_string)
    data_file.write(data_string)
    data_file.close()
    # if connected send data
    if wlan.isconnected() and post_ready:
        utc_timestamp_post = 946684800 + utime.time()
        read_and_post_data()
        next_post_timestamp = utc_timestamp_post + 1800
        post_ready = False
    time.sleep(300)