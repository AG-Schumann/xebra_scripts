import numpy as np
import h5py
import os
import tqdm

def get_events(filename):
    """
    Generator to get events from a pax processed HDF5 file.
    v1.0.0
    
    ==========
    Parameters
    
    filename:
        full path to the file you want to load
       
    =======
    Yields
    
    event:
        dictionary with fields as described in the pax Event class documentation:
        key | value:
        event_number | int
        start_time | int
        stop_time | int
        interactions | list of all interactions
        peaks | list of all peaks
        s1s | list of all s1s (sorted by area, descending)
        s2s | list of all s2s (sorted by area, descending)
    """

    if not os.path.exists(filename):
        raise ValueError('Can\'t find a file named %s' % filename)

    with h5py.File(filename, 'r') as f:
        ias = f['Interaction']
        ia_i_min, ia_i_max = 0,0

        peaks = f['Peak']
        peak_i_min, peak_i_max = 0,0
        peak_dtype = peaks.dtype
        for ev in tqdm.tqdm(f['Event']):
            event = {}
            event['number'] = ev['event_number']
            event['start_time'] = ev['start_time']
            event['stop_time'] = ev['stop_time']
            ias_this_event = ev['n_interactions']
            peaks_this_event = ev['n_peaks']

            ia_i_min = ia_i_max
            ia_i_max = ia_i_min + ias_this_event
            event['interactions'] = ias[ia_i_min:ia_i_max]

            peak_i_min = peak_i_max
            peak_i_max = peak_i_min + peaks_this_event
            event['peaks'] = peaks[peak_i_min:peak_i_max]

            s1s = np.array([p for p in event['peaks'] if p['type'] == b's1'], dtype=peak_dtype)
            s2s = np.array([p for p in event['peaks'] if p['type'] == b's2'], dtype=peak_dtype)

            event['s1s'] = np.flipud(np.sort(s1s, order='area', kind='heapsort'))
            event['s2s'] = np.flipud(np.sort(s2s, order='area', kind='heapsort'))

            yield event

