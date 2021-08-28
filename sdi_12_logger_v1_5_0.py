#!/usr/local/opt/python-3.5.1/bin/python3.5
# SDI-12 Sensor Data Logger Copyright Dr. John Liu 2017-11-06
# 2017-11-06 Updated telemetry code to upload to thingspeak.com from data.sparkfun.com.
# 2017-06-23 Added exception handling in case the SDI-12 + GPS USB adapter doesn't return any data (no GPS lock).
#            Added serial port and file closing in ctrl + C handler.
# 2017-02-02 Added multiple-sensor support. Just type in multiple sensor addresses when asked for addresses.
#            Changed sdi_12_address into regular string from byte string. I found out that byte strings when iterated over becomes integers.
#            It's easy to cast each single character string into byte string with .encode() when needed as address.
#            Removed specific analog input code and added the adapter address to the address string instead.
# 2016-11-12 Added support for analog inputs
# 2016-07-01 Added .strip() to remove \r from input files typed in windows
# Added Ctrl-C handler
# Added sort of serial port placing FTDI at item 0 if it exists

import os # For running command line commands
import time # For delaying in seconds
import datetime # For finding system's real time
import serial.tools.list_ports # For listing available serial ports
import serial # For serial communication
import re # For regular expression support 
import platform # For detecting operating system flavor
import urllib.parse # For encoding data to be url safe.
import signal # For trapping ctrl-c or SIGINT
import sys # For exiting program with exit code

def SIGINT_handler(signal, frame):
    ser.close()
    data_file.close()
    print('Quitting program!')
    sys.exit(0)
signal.signal(signal.SIGINT, SIGINT_handler)

channelID = "359964"
api_key = "GTOEBKK8ZQHI1V1B"
curl_command_format='curl "https://api.thingspeak.com/update/?api_key=%s%s"' # This is the cURL upload command to thingspeak.com
unit_id=platform.node() # Use computer name as unit_id. For a raspberry pi, change its name from raspberrypi to something else to avoid confusion
curl_exists=False # The code will test whether cURL exists. If it exists, it will be used to upload data.
adapter_sdi_12_address='z'
no_data=False # This is the flag to break out of the inner loops and continue the next data point loop in case no data is received from a sensor such as the GPS.

if (os.system('curl -V')==0):
    curl_exists=True

print('+-'*40)
print('SDI-12 Sensor and Analog Sensor Python Data Logger with Telemetry V1.5.0')
print('Designed for Dr. Liu\'s family of SDI-12 USB adapters (standard,analog,GPS)\n\tDr. John Liu Saint Cloud MN USA 2017-11-06\n\t\tFree software GNU GPL V3.0')
print('\nCompatible with Windows, GNU/Linux, Mac OSX, and Raspberry PI')
print('\nThis program requires Python 3.4, Pyserial 3.0, and cURL (data upload)')
print('\nData is logged to YYYYMMDD.CVS in the Python code\'s folder')
print('\nVisit https://thingspeak.com/channels/%s to inspect or retrive data' %(channelID))
# print('\nIf multiple people are running this code, they are distinguished by unit_id, although all raspberry pis have the same "raspberrypi" unit_id.')
print ('\nFor assistance with customization, telemetry etc., contact Dr. Liu.\n\thttps://liudr.wordpress.com/gadget/sdi-12-usb-adapter/')
print('+-'*40)

ports=[]
VID_FTDI=0x0403;

a=serial.tools.list_ports.comports()
for w in a:
    ports.append((w.vid,w.device))

ports.sort(key= lambda ports: ports[1])

print('\nDetected the following serial ports:')
i=0
for w in ports:
    print('%d)\t%s\t(USB VID=%04X)' %(i, w[1], w[0] if (type(w[0]) is int) else 0))
    i=i+1
total_ports=i # now i= total ports

user_port_selection=input('\nSelect port from list (0,1,2...). SDI-12 adapter has USB VID=0403:')
if (int(user_port_selection)>=total_ports):
    exit(1) # port selection out of range

ser=serial.Serial(port=(ports[int(user_port_selection)])[1],baudrate=9600,timeout=10)
time.sleep(2.5) # delay for arduino bootloader and the 1 second delay of the adapter.

total_data_count=int(input('Total number of data points:'))
delay_between_pts=int(input('Delay between data points (second):'))

print('Time stamps are generated with:\n0) GMT/UTC\n1) Local\n')
time_zone_choice=int(input('Select time zone.'))

if time_zone_choice==0:
    now=datetime.datetime.utcnow() # use UTC time instead of local time
elif time_zone_choice==1:
    now=datetime.datetime.now() # use local time, not recommended for multiple data loggers in different time zones
    
data_file_name="%04d%02d%02d.csv" %(now.year,now.month,now.day)
data_file = open(data_file_name, 'a') # open yyyymmdd.csv for appending

sdi_12_address=''
user_sdi_12_address=input('Enter all SDI-12 sensor addresses, such as 1234:')
user_sdi_12_address=user_sdi_12_address.strip() # Remove any \r from an input file typed in windows
analog_inputs=input('Collect analog inputs (requires SDI12-USB + Analog adapter)? (Y/N)')
analog_inputs=(analog_inputs.strip()).capitalize() # Remove any \r from an input file typed in windows and capitalize answer

for an_address in user_sdi_12_address:
    if ((an_address>='0') and (an_address<='9')) or ((an_address>='A') and (an_address<='Z')) or ((an_address>='a') and (an_address<='z')):
        print("Using address:",an_address);
        sdi_12_address=sdi_12_address+an_address
    else:
        print('Invalid address:',an_address)

if analog_inputs=='Y':
    sdi_12_address=sdi_12_address+adapter_sdi_12_address
if len(sdi_12_address)==0:
    sdi_12_address=adapter_sdi_12_address # Use default address

for an_address in sdi_12_address:
    ser.write(an_address.encode()+b'I!')
    sdi_12_line=ser.readline()
    print('Sensor address:',an_address,' Sensor info:',sdi_12_line.decode('utf-8').strip())

print('Saving to %s' %data_file_name)

for j in range(total_data_count):
    i=0 # This counts to 6 to truncate all data to the 6 values set up in sparkfun's phant server upload.
    value_str='' # This stores &value0=xxx&value1=xxx&value2=xxx&value3=xxx&value4=xxx&value5=xxx and is only reset after all sensors are read.
    if time_zone_choice==0:
        now=datetime.datetime.utcnow()
    elif time_zone_choice==1:
        now=datetime.datetime.now()
    output_str="%04d/%02d/%02d %02d:%02d:%02d%s" %(now.year,now.month,now.day,now.hour,now.minute,now.second,' GMT' if time_zone_choice==0 else '') # formatting date and time
    for an_address in sdi_12_address:
        ser.write(an_address.encode()+b'M!'); # start the SDI-12 sensor measurement
        # print(an_address.encode()+b'M!'); # start the SDI-12 sensor measurement
        sdi_12_line=ser.readline()
        # print(sdi_12_line)
        sdi_12_line=sdi_12_line[:-2] # remove \r and \n since [0-9]$ has trouble with \r
        m=re.search(b'[0-9]$',sdi_12_line) # having trouble with the \r
        total_returned_values=int(m.group(0)) # find how many values are returned
        sdi_12_line=ser.readline() # read the service request line
        ser.write(an_address.encode()+b'D0!') # request data
        # print(an_address.encode()+b'D0!') # request data
        sdi_12_line=ser.readline() # read the data line
        # print(sdi_12_line)
        sdi_12_line=sdi_12_line[1:-2] # remove address, \r and \n since [0-9]$ has trouble with \r

        values=[] # clear before each sensor
        for iterator in range(total_returned_values): # extract the returned values from SDI-12 sensor and append to values[]
            m=re.search(b'[+-][0-9.]+',sdi_12_line) # match a number string
            try: # if values found is less than values indicated by return from M, report no data found. This is a simple solution to GPS sensors before they acquire lock. For sensors that have lots of values to return, you need to find a better solution.
                values.append(float(m.group(0))) # convert into a number
                sdi_12_line=sdi_12_line[len(m.group(0)):]
            except AttributeError:
                print("No data received from sensor at address %c\n" %(an_address))
                time.sleep(delay_between_pts)
                no_data=True
                break
        if (no_data==True):
            break;
        
        output_str=output_str+','+an_address

        for value_i in values:
            output_str=output_str+",%s" %(value_i) # Output returned values
            if (i<6):
                value_str=value_str+"&field%d=%s" %(i+1,value_i) # format values for posting. Field starts with field1, not field0.
                i=i+1
    if (no_data==True):
        no_data=False
        continue;
    while (i<6): # Pad with zeros in case we don't have 6 fields. This is only necessary for certain servers.
        value_str=value_str+"&field%d=0" %(i+1) # format values for posting. Field starts with field1, not field0.
        i=i+1
  
    print(output_str)
    output_str=output_str+'\n'
    data_file.write(output_str)
    if (curl_exists==True):
        curl_command=curl_command_format %(api_key,value_str) # Format cURL command
        print(curl_command) # Debug information
        print(os.system(curl_command)) # Send data to data.sparkfun.com using cURL
        
    values=[] # clear values for the next iteration, 3.2.3 doesn't support clear as 3.4.3 and 3.5.1 does
    data_file.flush() # make sure data is written to the disk so stopping the scrit with ctrl - C will not cause data loss
    time.sleep(delay_between_pts)
ser.close()
data_file.close()




