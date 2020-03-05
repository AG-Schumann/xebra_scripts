from influxdb import InfluxDBClient
import re

"""
Code snippet to read out data from InfluxDB as it is used by Doberman 5 + Greyhound

"""

datetime_regex = '\d{4}-(0\d|1[012])-([0-2]\d|3[01])T([01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?Z'
db = 'xebra'
client = InfluxDBClient(host='192.168.131.2', port=8086, database=db)
latest_values = {}
measurements = [d['name'] for d in client.get_list_measurements()]
print('Available measurements: ')
print('|'.join(measurements))
measurement = ''
while measurement not in measurements:
    measurement = input('Select measurement: ')
    if measurement not in measurements:
        print('Invalid measurement name')
print('Available readings: ')
resultset = list(client.query(f'SHOW FIELD KEYS ON {db} FROM {measurement}').get_points())
readings = [rs['fieldKey'] for rs in resultset]
print('|'.join(readings))
reading = ''
while reading not in readings:
    reading = input('Select reading: ')
    if reading not in readings:
        print('Invalid reading name')
start = ''
while re.fullmatch(datetime_regex, start) == None:
    start = input('Start (format: YYYY-MM-DDTHH:MM:SSZ): ')
    if re.fullmatch(datetime_regex, start) == None:
        print('Invalid datetime format')
end = ''
while re.fullmatch(datetime_regex, end) == None:
    end = input('End (format: YYYY-MM-DDTHH:MM:SSZ): ')
    if re.fullmatch(datetime_regex, end) == None:
        print('Invalid datetime format')
resultset = list(client.query(f'SELECT {reading} FROM {measurement} WHERE time >= \'{start}\' AND time <= \'{end}\'').get_points())
times = []
values = []
for entry in resultset:
    times.append(entry['time'])
    values.append(entry[reading])

print(times)
print(values)


