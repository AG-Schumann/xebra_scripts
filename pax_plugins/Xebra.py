from pymongo import MongoClient
import numpy as np
import tqdm
import os

from pax import plugin, units, FolderIO, units
from pax.datastructure import Event, Pulse, EventProxy

class XebraEventbuilder(plugin.InputPlugin):

    do_output_check = False

    def startup(self):
        self.client = MongoClient(self.config['mongo_uri'])
        self.rundoc = self.client['runs']['xebra'].find_one({'name' : self.config['input_name']})
        self.dataset_name = self.config['input_name']
        self.collection_name = self.rundoc['data'][0]['collection']
        if self.collection_name not in self.client['data'].list_collection_names():
            raise ValueError('Can\'t find a collection for a run named %s' % self.config['input_name'])
        self.collection = self.client['data'][self.collection_name]
        self.run_start_time = self.rundoc['start'].timestamp() * units.s

    def shutdown(self):
        self.client.close()

    def get_events(self):
        self.log.info('Prepping eventbuilder...')
        for index in self.collection.index_information():
            if index[:4] == 'time':
                break
        else:
            self.log.info('Some fool didn\'t index their collection correctly, '
                'so we have to do it here. This might take a while. Go get a coffee')
            self.collection.create_index('time')
        num_pulses = self.collection.count_documents({})
        window_length = self.config['trigger_window']
        empty_time = self.config['empty_time']
        dead_time = self.config['dead_time']
        max_length = self.config['max_event_length']
        threshold = self.config['threshold']
        dt = self.config['sample_duration']

        build_event = False
        in_event = False
        event_start_time = 0
        event_end_time = 0
        event_number = 0
        last_i_in_window = 0
        pulse_buffer = []

        projection = {'time' : 1, '_id' : 0}
        sort = [('time', 1)]
        next_print_statement = num_pulses//10

        self.log.info('Starting')

        for i, row in enumerate(self.collection.find({},projection=projection,sort=sort)):
            this_pulse_time = row['time']*dt
            pulse_buffer.append(this_pulse_time)
            # pulses in buffer = i - last_i_in_window + 1
            # window length = this_pulse_time - buffer[0]

            if i - last_i_in_window + 1 > threshold:
                if in_event:
                    if this_pulse_time - event_start_time >= max_length or \
                            this_pulse_time - previous_pulse_time > empty_time:
                        event_end_time = previous_pulse_time
                        build_event = True
                        in_event = False
                    else:  # not too long
                        pass
                else:  # not in event
                    if this_pulse_time - event_end_time < dead_time:  # too soon since last event
                        while last_i_in_window < i and \
                                this_pulse_time - pulse_buffer[0] > window_length:
                            pulse_buffer = pulse_buffer[1:]
                            last_i_in_window += 1
                    else:  # not too soon, start event
                        event_start_time = pulse_buffer[0]
                        in_event = True
            else:  # below threshold
                if in_event:
                    if this_pulse_time - event_start_time >= max_length or \
                            this_pulse_time - previous_pulse_time > empty_time:
                        event_end_time = previous_pulse_time
                        build_event = True
                        in_event = False
                    else:  # below threshold, not too long, continue event
                        pass
                else:  # not in event
                    while last_i_in_window < i and \
                            this_pulse_time - pulse_buffer[0] > window_length:
                        pulse_buffer = pulse_buffer[1:]
                        last_i_in_window += 1

            if build_event:
                yield EventProxy(event_number = event_number,
                        data = (event_start_time, event_end_time, self.run_start_time,
                            self.collection_name),
                        block_id = -1)
                event_number += 1
                build_event = False
                while last_i_in_window < i and \
                        this_pulse_time - pulse_buffer[0] > window_length:
                    pulse_buffer = pulse_buffer[1:]
                    last_i_in_window += 1
            previous_pulse_time = this_pulse_time

            if i > next_print_statement:
                self.log.info('Processed %i%% of pulses' % (100*i/num_pulses))
                next_print_statement += num_pulses//10


class XebraEventbuilderDecoder(plugin.TransformPlugin):
    do_input_check = False

    def startup(self):
        self.client = MongoClient(self.config['mongo_uri'])
        self.db = self.client['data']

    def shutdown(self):
        self.client.close()

    def get_pulses(self, collection_name, t_start, t_end):
        """
        Gets pulses with for the event with pulses between t_start and t_end
        Returns [pulses], first_pulse_time
        """

        sd = self.config['sample_duration']
        pulses = []
        collection = self.db[collection_name]
        query = {'time' : {'$gte' : t_start/self.config['sample_duration'],
                           '$lte' : t_end/self.config['sample_duration']}}
        projection = {'channel' : 1, 'time' : 1, 'data' : 1, '_id' : 0}
        sort = [('time', 1)]
        first_pulse_time = 0
        for row in collection.find(filter=query, projection=projection, sort=sort):
            this_pulse_time = row['time']
            if first_pulse_time == 0:
                first_pulse_time = this_pulse_time
            wf = np.fromstring(row['data'], dtype=np.uint16)
            pulses.append(Pulse(left = int(this_pulse_time - first_pulse_time),
                                raw_data = wf,
                                channel = row['channel'],
                                do_it_fast = True))
        return pulses, first_pulse_time*self.config['sample_duration']

    def transform_event(self, event_proxy):
        t_start, t_end, run_start, collection_name = event_proxy.data
        pulses, start = self.get_pulses(collection_name, t_start, t_end)
        event_start = run_start + start
        event = Event(n_channels = 8,
                      start_time = int(event_start),
                      length = max([p.right for p in pulses])+1,
                      sample_duration = self.config['sample_duration'],
                      event_number = event_proxy.event_number,
                      dataset_name = '',
                      block_id = event_proxy.block_id)
        event.pulses = pulses

        return event
