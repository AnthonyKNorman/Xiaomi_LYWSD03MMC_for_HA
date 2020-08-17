import utime as time
from umqtt.simple import MQTTClient
import ubinascii
import machine
import micropython
import network
import esp
esp.osdebug(None)
import gc
gc.collect()
import ble, ntptime
import uos

ssid = 'FARLEIGH'
password = 'MK4Lxq7aiuuU'
mqtt_server = '192.168.0.99'
#EXAMPLE IP ADDRESS
#mqtt_server = '192.168.1.144'
client_id = ubinascii.hexlify(machine.unique_id())
topic_pub = b'espble'

def connect():
  global client_id, mqtt_server, topic_sub
  client = MQTTClient(client_id, mqtt_server)
  client.connect()
  print('Connected to {} MQTT broker'.format(mqtt_server))
  return client

def restart_and_reconnect():
  print('Failed to connect to MQTT broker. Reconnecting...')
  time.sleep(10)
  machine.reset()

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

try:
    ntptime.settime()
    print (ble.timestamp())
except Exception as e:
    ble.debug('Error: ntptime settime ' + str(e))

try:
  client = connect()
except OSError as e:
  restart_and_reconnect()

myBLE = ble.ble()
myBLE.setup()

print ('Found:')
for a in myBLE.addresses:
    type, address, name = a
    ble.debug ('Found Address: {} Name: {}'.format(ble.prettify(address),name))
    
    
def cleanup():
    dir = uos.listdir()
    for f in dir:
        print(f)
        try:
            year = int(f[:4])
            month = int(f[4:6])
            mday = int(f[6:8])
            print (year, month, mday)
            filedate = time.mktime( (year, month, mday, 0, 0, 0, 0, 0))
            year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
            two_days_ago = time.mktime((year, month, mday-2, 0, 0, 0, 0, 0))
            print(filedate, two_days_ago)
            if filedate < two_days_ago:
                uos.remove(f)
            
            
        except Exception as e:
            print ('cleanup', str(e))
            pass

lastday = 0
while True:
    # update the RTC once a day
    today = ble.timestamp('day')
    if today != lastday:
        try:
            ntptime.settime()
            lastday = today
            ble.debug('Time set from server')
        except Exception as e:
            ble.debug('Error: ntptime ' + str(e))

    # cleanup filesystem
    cleanup()
    
    # cycle through the captured addresses
    for a in myBLE.addresses:       
        type, myBLE.address, name = a
        # if this is a LYWSD03MMC'
        if name == 'LYWSD03MMC':
            # if we are successful reading the values
            print ('\r\n----------------------------------------------------------')
            if(myBLE.get_reading()):
                message = '{"temperature": "' + str(myBLE.temp) + '", '
                message = message + '"humidity": "' + str(myBLE.humidity) + '", '
                message = message + '"batt": "' + str(myBLE.batteryLevel) + '", '
                message = message + '"voltage": "' + str(myBLE.voltage) + '"}'
                print (message)
                topic = topic_pub + '/' + ''.join('{:02x}'.format(b) for b in myBLE.address)
                print (topic)
                try:
                    client.publish(topic, message)
                except Exception as e:
                    ble.debug('Publish ' + str(e))
                    try:
                        client.disconnect()
                        client = connect()
                    except OSError as e:
                        restart_and_reconnect()

    # wait a minute for the next one
    time.sleep(60)

