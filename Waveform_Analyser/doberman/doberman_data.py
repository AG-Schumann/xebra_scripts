#!/usr/bin/env python3

from pymongo import MongoClient
import json
from datetime import datetime
import argparse

def main():
    client = MongoClient('mongodb://webapp:doberman@127.0.0.1:13178')
    controllers = client['settings']['controllers'].distinct('name')
    parser = argparse.ArgumentParser()
    parser.add_argument('--controller',type=str,required=True,options=controllers
                        help='Which controller to get data for')
    parser.add_argument('--index', type=int, default=-1,
                        help='Which data index to load')
    parser.add_argument('--start-date', type=str, required=True,
            help='Start time for the data, format YYYY-MM-DD_HH:MM:SS')
    parser.add_argument('--end-date', type=str, default='None',
            help='End time for the data, format YYYY-MM-DD_HH:MM:SS')
    args = parser.parse_args()

    if args.index == -1:
        print('You didn\'t specify an index of data to load. Here are your options:')
        desc = client['settings']['controllers'].find_one({'name' : args.controller})['descrtiption']
        for v in enumerate(desc):
            print('%i: %s' % v)
        while True:
            try:
                args.index = int(input('>>> '))
            except ValueError:
                print('Invalid input!')
            else:
                break
    try:
        datetime_format = '%Y-%m-%d_%H:%M:%S'
        start_time = datetime.strptime(parser.start_date, datetime_format)
        cuts = {'when' : {'$gte' : start_time}}
        if parser.end_date != 'None':
            end_time = datetime.strptime(parser.end_date, datetime_format)
            cuts['when'].update({'$lte' : end_time})
    except ValueError:
        print('Invalid date format!')
        client.close()
        return

    when = []
    values = []
    print('Extracting data from the database...')
    for row in client['data'][args.controller].find(cuts):
        when.append(row['when'].timestamp())
        values.append(row['data'][args.index])

    client.close()

    with open('%s_data.json' % args.controller, 'w') as f:
        print('Saving to \'%s_data.json\'' % args.controller)
        json.dump({'when' : when, 'data' : data}, f)

    return

if __name__ == '__main__':
    main()
