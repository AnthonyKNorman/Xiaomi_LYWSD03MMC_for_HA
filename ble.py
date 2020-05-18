from ubluetooth import BLE, UUID, FLAG_NOTIFY, FLAG_READ, FLAG_WRITE
from micropython import const
from utime import sleep
from binascii import unhexlify
import array
import micropython
import machine, ntptime

micropython.alloc_emergency_exception_buf(100)

_IRQ_CENTRAL_CONNECT                 = const(1 << 0)
_IRQ_CENTRAL_DISCONNECT              = const(1 << 1)
_IRQ_GATTS_WRITE                     = const(1 << 2)
_IRQ_GATTS_READ_REQUEST              = const(1 << 3)
_IRQ_SCAN_RESULT                     = const(1 << 4)
_IRQ_SCAN_COMPLETE                   = const(1 << 5)
_IRQ_PERIPHERAL_CONNECT              = const(1 << 6)
_IRQ_PERIPHERAL_DISCONNECT           = const(1 << 7)
_IRQ_GATTC_SERVICE_RESULT            = const(1 << 8)
_IRQ_GATTC_CHARACTERISTIC_RESULT     = const(1 << 9)
_IRQ_GATTC_DESCRIPTOR_RESULT         = const(1 << 10)
_IRQ_GATTC_READ_RESULT               = const(1 << 11)
_IRQ_GATTC_WRITE_STATUS              = const(1 << 12)
_IRQ_GATTC_NOTIFY                    = const(1 << 13)
_IRQ_GATTC_INDICATE                  = const(1 << 14)
_ARRAYSIZE = const(20)
    
    

def prettify(mac_string):
    return ':'.join('{:2x}'.format(b) for b in mac_string)

def timestamp(type='timestamp'):
    yy,mm,dd,dy,hh,MM,ss,ms= machine.RTC().datetime()
    if type == 'day': 
        return dd
    else:
        return '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(yy,mm,dd,hh,MM,ss)

def debug(message, fname = 'ble.log'):
    f = open(fname,'a')
    f.write(timestamp() + ' ' + message +'\n')
    f.close()
    print(message)
    
class ble:
    def __init__(self):
        debug("Initialising")
        self.bt = BLE()
        self.bt.irq(handler=self.bt_irq)
        print ('waiting to set BLE active')
        self.bt.active(True)

        self.addresses=[]
        for i in range (_ARRAYSIZE):
            self.addresses.append((100, b'AAAAAA','name'))
        self.conn_handle = 0
        self.connected = False
        self.write_flag = False
        self.read_flag = False
        self.notify = False
        self.index = 0
        self.scan = False
        self.notify_data = bytearray(30)
        self.address = bytearray(6)
        self.char_data = bytearray(30)
        self.temp = 0
        self.humidity = 0
        self.battery = 0
        self.voltage = 0

    def get_name(self, i):
        print('\r\n--------------------------------------------')
        print(self.type, prettify(self.address))
        if self.connect():
            sleep(1)
            if(self.read_data(0x0003)):
                try:
                    self.name = self.char_data.decode("utf-8")
                    self.name = self.name[:self.name.find('\x00')]  # drop trailing zeroes
                    print ('self.name',self.name, ' length', len(self.name))
                except Exception as e:
                    debug('Error: Setup ' + str(e))
              
                print ('Got', self.name )
            self.disconnect()
    
    def setup(self):
        # start device scan
        self.scan = False
        self.index = 0
        print('start scan')
        # Scan for 60s (at 100% duty cycle)
        try:
            self.bt.gap_scan(60000, 30000, 30000)
        except Exception as e:
            debug('Error: Scan ' + str(e))
            
        while not self.scan:
            pass    

        # perform a scan to identify all the devices
        for i in range(len(self.addresses)):
            self.type, self.address, self.name = self.addresses[i]
            if self.type < 100:
                self.get_name(i)
                print ('Name:',self.name)
                if self.name != 'name':
                    self.addresses[i] = (self.type, self.address, self.name)
                sleep(1)
            else:
                self.addresses = self.addresses[:i]            # truncate self.addresses
                break
                
    # Bluetooth Interrupt Handler
    def bt_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            # A single scan result.
            addr_type, addr, connectable, rssi, adv_data = data
            if addr_type == 0:
                print ('address type = {}, address = {}'.format(addr_type, prettify(addr)))
                if (addr_type, bytes(addr), 'name') not in self.addresses:
                    self.addresses[self.index] = (addr_type, bytes(addr), 'name')
                    self.index += 1
                
        elif event == _IRQ_SCAN_COMPLETE:
            # Scan duration finished or manually stopped.
            print('scan complete')
            self.scan = True
            
        elif event == _IRQ_PERIPHERAL_CONNECT:
            print('IRQ peripheral connect')
            self.conn_handle, _, _, = data
            self.connected = True
            
        if event == _IRQ_CENTRAL_CONNECT:
            # A central has self.connected to this peripheral.
            self.conn_handle, addr_type, addr = data
            print('A central has self.connected to this peripheral.', self.conn_handle, addr_type, addr)

        elif event == _IRQ_CENTRAL_DISCONNECT:
            # A central has disself.connected from this peripheral.
            self.conn_handle, addr_type, addr = data
            print('A central has disself.connected from this peripheral.', self.conn_handle, addr_type, addr)
            
        elif event == _IRQ_GATTS_WRITE:
            # A central has written to this characteristic or descriptor.
            self.conn_handle, attr_handle = data
            print ('A central has written to this characteristic or descriptor.', con_handle, attr_handle)

        elif event == _IRQ_GATTS_READ_REQUEST:
            # A central has issued a read. Note: this is a hard IRQ.
            # Return None to deny the read.
            # Note: This event is not supported on ESP32.
            self.conn_handle, attr_handle = data
            
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # connected peripheral has disself.connected.
            self.conn_handle, addr_type, addr = data
            print('connected peripheral has disconnected.', self.conn_handle, addr_type, prettify(addr))
            self.connected = False
            # print ('Set connect flag', self.connected)
            
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Called for each service found by gattc_discover_services().
            self.conn_handle, start_handle, end_handle, uuid = data
            print('Called for each service found by gattc_discover_services().', self.conn_handle, start_handle, end_handle, uuid)
            
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Called for each characteristic found by gattc_discover_services().
            self.conn_handle, def_handle, value_handle, properties, uuid = data
            print('Called for each characteristic found by gattc_discover_services().', self.conn_handle, def_handle, value_handle, properties, uuid)
            # print('Value handle {:02x}'.format(value_handle))
            # characteristics[self.index] = value_handle
            # self.index += 1
            
        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Called for each descriptor found by gattc_discover_descriptors().
            conn_handle, dsc_handle, uuid = data
            print('Called for each descriptor found by gattc_discover_descriptors().', conn_handle, dsc_handle, uuid)

        elif event == _IRQ_GATTC_READ_RESULT:
            # A gattc_read() has completed.
            conn_handle, value_handle, char_data = data
            print('A gattc_read() has completed.', conn_handle, value_handle, char_data)

            for b in range(len(char_data)):
                self.char_data[b] = char_data[b]
                
            self.read_flag = True

        elif event == _IRQ_GATTC_WRITE_STATUS:
            # A gattc_write() has completed.
            self.conn_handle, value_handle, status = data
            print('A gattc_write() has completed - status.', self.conn_handle, value_handle, status)
            self.write_flag = True
            
        elif event == _IRQ_GATTC_NOTIFY:
            # A peripheral has sent a notify request.
            self.conn_handle, value_handle, notify_data = data
            print('A peripheral has sent a notify request.', self.conn_handle, value_handle, notify_data)
            for b in range(len(notify_data)):
                self.notify_data[b] = notify_data[b]
            
            self.notify = True
            
        elif event == _IRQ_GATTC_INDICATE:
            # A peripheral has sent an indicate request.
            self.conn_handle, value_handle, self.notify_data = data        
            print('A peripheral has sent an indicate request.', self.conn_handle, value_handle, self.notify_data)
            
    def connect(self, type=0):
        # connect to the device at self.address
        count = 0
        while not self.connected:                                   # loop until connection successful
            print('Trying to connect to', prettify(self.address))
            try:
                conn = self.bt.gap_connect(type,self.address)           # try to connect
            except Exception as e:
                debug('Error: Connect ' + str(e))
            
            print('self.connected', self.connected)
            count += 1
            if count > 60: return False
            sleep(1)
        return True
        
    def read_data(self, value_handle):
        self.read_flag = False
       
        print('Reading Data')
        try:
            self.bt.gattc_read(self.conn_handle, value_handle)
        except Exception as e:
            debug('Error: Read ' + str(e))
            return False
            
        # returns false on timeout
        timer = 0
        while not self.read_flag:
            print ('.',end='')
            print(self.read_flag)
            sleep(1)
            timer += 1
            if timer > 60:
                return False
        return True
            
        
    def disconnect(self):
        try:
            conn = self.bt.gap_disconnect(self.conn_handle)
        except Exception as e:
            debug('Error: Disconnect ' + str(e))


        # returns false on timeout
        timer = 0
        while self.connected:
            print ('.',end='')
            sleep(1)
            timer += 1
            if timer > 60:
                return False
        return True


    def write_data(self, value_handle, data):
        self.write_flag = False
        
        # Checking for connection before write
        self.connect()
        try:
            self.bt.gattc_write(self.conn_handle, value_handle, data, 1)
        except Exception as e:
            debug('Error: Write ' + str(e))
            return False
            
        # returns false on timeout
        timer = 0
        while not self.write_flag:
            print ('.',end='')
            sleep(1)
            timer += 1
            if timer > 60:
                return False
        return True


    def get_reading(self):
        self.connect()
        
        #enable notifications of Temperature, Humidity and Battery voltage
        data = b'\x01\x00'
        value_handle = 0x0038
        if (self.write_data(value_handle, data)):
            print ('write ok')
        else:
            print('write failed')
        
        # enable energy saving
        data = b'\xf4\x01\x00'
        value_handle = 0x0046
        if(self.write_data(value_handle, data)):
            print ('write ok')
        else:
            print('write failed')
 
        
        # wait for a notification
        self.notify = False
        timer = 0
        while not self.notify:
            print ('.',end='')
            sleep(1)
            timer += 1
            if timer > 60:
                self.disconnect()
                return False
     
        print ('Data received')
        self.temp = int.from_bytes(self.notify_data[0:2],'little')/100
        self.humidity = int.from_bytes(self.notify_data[2:3],'little')
        self.voltage = int.from_bytes(self.notify_data[3:5],'little')/1000
        self.batteryLevel = min(int(round((self.voltage - 2.1),2) * 100), 100) #3.1 or above --> 100% 2.1 --> 0 %
        self.disconnect()
        return True







