from pymongo import MongoClient
from pymongo.son_manipulator import ObjectId
from datetime import datetime
import os


with MongoClient(os.environ['DOBERMAN_URI']) as client:
    sensor_names = client['xebra_settings']['sensors'].distinct('name')
    print('Available sensors:')
    print(' | '.join(sensor_names))
    sensor = ''
    while sensor not in sensor_names:
        sensor = input('Name: ')
        if sensor not in sensor_names:
            print('Invalid sensor name')
    print('Available readings:')
    print('Name | description')
    for reading in client['xebra_settings']['readings'].find({'sensor' : sensor}):
        print(f'{reading["name"]} | {reading["description"]}')
    reading_names = client['xebra_settings']['readings'].distinct('name', {'sensor' : sensor})
    reading_name = ''
    while reading_name not in reading_names:
        reading_name = input('Reading name: ')
        if reading_name not in reading_names:
            print('Invalid reading name')

    # note that mongo is timezone-aware
    start_time = datetime.datetime(start_time_here)
    #end_time = datetime.datetime(end_time_here)
    query = {'_id' : {'$gte' : ObjectId.from_datetime(start_time)},
             reading_name : {'$exists' : 1}}
    if end_time:
        query['_id'].update({'$lte' : ObjectId.from_datetime(end_time)})

    for row in client['xebra_data'][sensor].find(query):
        # this gives you a datetime instance:
        timestamp = row['_id'].generation_time
        # alternately, for the underlying unix timestamp:
        timestamp = int(str(row['_id'])[:8],16)

        value = row[reading_name]
