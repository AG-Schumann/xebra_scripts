import glob
import os

import numpy as np
import numba

import strax
export, __all__ = strax.exporter()

# V/adc * (sec/sample) * (1/resistance) * (1/electron charge)
adc_to_e = (2.25/2**14) * (1e-9) * (1/50) * (1/1.602e-19)

to_pe = np.ones(7)*adc_to_e/6e6


@export
@strax.takes_config(
    strax.Option('input_dir', type=str, track=False,
                 help='The directory with the data'),
)
class RecordReader(strax.Plugin):
    """
    Reads records in from disk
    """
    provides = 'raw_records'
    depends_on = tuple()
    dtype = strax.record_dtype()
    rechunk_on_save = False

    def source_finished(self):
        return True

    def is_ready(self, chunk_i):
        try:
            self._chunk_path(chunk_i)
        except ValueError:
            return False
        else:
            return True

    def _load_chunk(self, fp):
        records = strax.load_file(fp,
                                  'blosc',
                                  strax.record_dtype())
        records = strax.sort_by_time(records)
        return records

    def _chunk_path(self, chunk_i):
        fp = os.path.join(self.config['input_dir'], f'{chunk_i:06d}')
        if not os.path.exists(fp):
            raise ValueError(f"Can't find chunk {chunk_i:06d} in {self.config['input_dir']}")
        return fp

    def compute(self, chunk_i):
        fp = self._chunk_path(chunk_i)
        records = self._load_chunk(fp)

        strax.baseline(records)
        strax.integrate(records)

        if len(records):
            timespan_sec = (records[-1]['time'] - records[0]['time']) / 1e9
            print(f'{chunk_i}: read {records.nbytes/1e6:.2f} MB '
                  f'({len(records)} records, '
                  f'{timespan_sec:.2f} live seconds)')
        else:
            print(f'{chunk_i}: read an empty chunk!')

        return records


@export
class Records(strax.Plugin):
    """
    Shamelessly stolen from straxen
    """
    __version__ = '0.0.2'

    depends_on = ('raw_records',)
    data_kind = 'records'   # TODO: indicate cuts have been done?
    compressor = 'zstd'
    parallel = True
    rechunk_on_save = False
    dtype = strax.record_dtype()

    def compute(self, raw_records):
        # Remove records from channels for which the gain is unknown
        r = raw_records[raw_records['channel'] < len(to_pe)]

        hits = strax.find_hits(r)
        strax.cut_outside_hits(r, hits)
        return r


@export
@strax.takes_config(
    strax.Option('diagnose_sorting', track=False, default=False,
                 help="Enable runtime checks for sorting and disjointness"))
class Peaks(strax.Plugin):
    """
    Stolen from straxen, extended marginally
    """
    depends_on = ('records',)
    data_kind = 'peaks'
    parallel = True
    rechunk_on_save = True
    dtype = strax.peak_dtype(n_channels=len(to_pe))

    def compute(self, records):
        r = records
        hits = strax.find_hits(r)       # TODO: Duplicate work
        hits = strax.sort_by_time(hits)

        peaks = strax.find_peaks(hits, to_pe,
                                 result_dtype=self.dtype)
        strax.sum_waveform(peaks, r, to_pe)

        peaks = strax.split_peaks(peaks, r, to_pe)

        strax.compute_widths(peaks)

        if self.config['diagnose_sorting']:
            assert np.diff(r['time']).min() >= 0, "Records not sorted"
            assert np.diff(hits['time']).min() >= 0, "Hits not sorted"
            assert np.all(peaks['time'][1:]
                          >= strax.endtime(peaks)[:-1]), "Peaks not disjoint"

        return peaks


@export
@strax.takes_config(
    strax.Option('top_pmts', track=False, default=list(range(1,7+1)),
                 type=list, help="Which PMTs are in the top array"))
class PeakBasics(strax.Plugin):
    """
    Stolen from straxen, extended with risetime. Also replaces
    aft for nonphysical peaks with nan.
    """
    __version__ = "0.0.1"
    parallel = True
    depends_on = ('peaks',)
    dtype = [
        (('Start time of the peak (ns since unix epoch)',
          'time'), np.int64),
        (('End time of the peak (ns since unix epoch)',
          'endtime'), np.int64),
        (('Peak integral in PE',
            'area'), np.float32),
        (('Number of PMTs contributing to the peak',
            'n_channels'), np.int16),
        (('PMT number which contributes the most PE',
            'max_pmt'), np.int16),
        (('Area of signal in the largest-contributing PMT (PE)',
            'max_pmt_area'), np.int32),
        (('Width (in ns) of the central 50% area of the peak',
            'range_50p_area'), np.float32),
        (('Fraction of area seen by the top array',
            'area_fraction_top'), np.float32),
        (('Length of the peak waveform in samples',
          'length'), np.int32),
        (('Time resolution of the peak waveform in ns',
          'dt'), np.int16),
    ]

    def compute(self, peaks):
        p = peaks
        r = np.zeros(len(p), self.dtype)
        for q in 'time length dt area'.split():
            r[q] = p[q]
        r['endtime'] = p['time'] + p['dt'] * p['length']
        r['n_channels'] = (p['area_per_channel'] > 0).sum(axis=1)
        r['range_50p_area'] = p['width'][:, 5]
        r['max_pmt'] = np.argmax(p['area_per_channel'], axis=1)
        r['max_pmt_area'] = np.max(p['area_per_channel'], axis=1)

        area_top = (p['area_per_channel'][:, self.config['top_pmts']]
                    * to_pe[self.config['top_pmts']].reshape(1, -1)).sum(axis=1)
        m = p['area'] > 0
        r['area_fraction_top'][m] = area_top[m]/p['area'][m]
        r['area_fraction_top'][~m] = np.nan * np.ones((~m).sum())
        return r


@export
@strax.takes_config(
    strax.Option('top_pmts', track=False, default=list(range(1,7+1)),
                 type=list, help="Which PMTs are in the top array"),
    strax.Option('min_reconstruction_area',
                 help='Skip reconstruction if area (PE) is less than this',
                 default=10)
)
class PeakPositions(strax.Plugin):
    """
    I actually wrote this
    Version 0.0.1: weighted sum
    Version 0.0.2: hopefully LRF or better
    """
    __version__ = "0.0.1"
    dtype = [('x', np.float32,
              'Reconstructed S2 X position (cm), uncorrected'),
             ('y', np.float32,
              'Reconstructed S2 Y position (cm), uncorrected')]
    depends_on = ('peaks',)

    parallel = False

    pmt_locations = np.zeros((7,2))  # top only

    transfer_mask = np.arange(7)  # s2-top-channel to pmt-location

    def setup(self):

        self.pmt_mask = to_pe[:self.config['top_pmts']] > 0
        pmt_angles = np.linspace(0, 2*np.pi, 6, endpoint=False)
        angle_offset = -2*np.pi/3  # position of PMT1
        pmt_angles = pmt_offset - pmt_angles
        pmt_radius = 30  # mm
        self.pmt_positions = np.column((np.cos(pmt_angles), np.sin(pmt_angles)))* pmt_radius
        self.pmt_positions = np.append(self.pmt_positions, [[0,0]])

    def compute(self, peaks):
        # Keep large peaks only
        results = np.nan * np.zeros(len(peaks), dtype=self.dtype)
        peak_mask = peaks['area'] > self.config['min_reconstruction_area']
        p = peaks['area_per_channel'][peak_mask, self.transfer_mask]
        r = np.nan * np.zeros(len(p), self.dtype)

        if len(p) == 0:
            # Nothing to do, and .predict crashes on empty arrays
            return dict(x=np.zeros(0, dtype=np.float32),
                        y=np.zeros(0, dtype=np.float32))

        results[peak_mask] = self.weighted_sum(p, self.pmt_positions, r)

        return dict(x=results[:, 0], y=results[:, 1])

    @staticmethod
    @numba.jit(nopython=True, nogil=True, cache=True)
    def weighted_sum(area_by_channel, location_by_channel, results):
        for row_i, row in enumerate(area_by_channel):
            results[row_i] = tuple(np.average(location_by_channel, weights = row, axis=0))
        return results


@export
@strax.takes_config(
    strax.Option('s1_max_width', default=150,
                 help="Maximum (IQR) width of S1s"),
    strax.Option('s1_min_n_channels', default=1,
                 help="Minimum number of PMTs that must contribute to a S1"),
    strax.Option('s2_min_area', default=10,
                 help="Minimum area (PE) for S2s"),
    strax.Option('s2_min_width', default=200,
                 help="Minimum width for S2s"))
class PeakClassification(strax.Plugin):
    __version__ = '0.0.1'
    depends_on = ('peak_basics',)
    dtype = [
        ('type', np.int8, 'Classification of the peak.')]
    parallel = True

    def compute(self, peaks):
        p = peaks
        r = np.zeros(len(p), dtype=self.dtype)

        is_s1 = p['n_channels'] > self.config['s1_min_n_channels']
        is_s1 &= p['range_50p_area'] < self.config['s1_max_width']
        r['type'][is_s1] = 1

        is_s2 = p['area'] > self.config['s2_min_area']
        is_s2 &= p['range_50p_area'] > self.config['s2_min_width']
        r['type'][is_s2] = 2

        return r


@strax.takes_config(
    strax.Option('min_area_fraction', default=0.5,
                 help='The area of competing peaks must be at least '
                      'this fraction of that of the considered peak'),
    strax.Option('nearby_window', default=int(1e7),
                 help='Peaks starting within this time window (on either side)'
                      'in ns count as nearby.'),
)
class NCompeting(strax.OverlapWindowPlugin):
    depends_on = ('peak_basics',)
    dtype = [
        ('n_competing', np.int32,
            'Number of nearby larger or slightly smaller peaks')]

    def get_window_size(self):
        return 2 * self.config['nearby_window']

    def compute(self, peaks):
        return dict(n_competing=self.find_n_competing(
            peaks,
            window=self.config['nearby_window'],
            fraction=self.config['min_area_fraction']))

    @staticmethod
    @numba.jit(nopython=True, nogil=True, cache=True)
    def find_n_competing(peaks, window, fraction):
        n = len(peaks)
        t = peaks['time']
        a = peaks['area']
        results = np.zeros(n, dtype=np.int32)

        left_i = 0
        right_i = 0
        for i, peak in enumerate(peaks):
            while t[left_i] + window < t[i] and left_i < n - 1:
                left_i += 1
            while t[right_i] - window < t[i] and right_i < n - 1:
                right_i += 1
            results[i] = np.sum(a[left_i:right_i + 1] > a[i] * fraction)

        return results - 1


@export
@strax.takes_config(
    strax.Option('trigger_min_area', default=100,
                 help='Peaks must have more area (PE) than this to '
                      'cause events'),
    strax.Option('trigger_max_competing', default=7,
                 help='Peaks must have FEWER nearby larger or slightly smaller'
                      ' peaks to cause events'),
    strax.Option('left_event_extension', default=int(1e4),
                 help='Extend events this many ns to the left from each '
                      'triggering peak'),
    strax.Option('right_event_extension', default=int(1e4),
                 help='Extend events this many ns to the right from each '
                      'triggering peak'),
    strax.Option('max_event_duration', default=int(1e5),
                 help='Events longer than this are forcefully ended, '
                      'triggers in the truncated part are lost!'),
)
class Events(strax.OverlapWindowPlugin):
    depends_on = ['peak_basics', 'n_competing']
    data_kind = 'events'
    dtype = [
        ('event_number', np.int64, 'Event number in this dataset'),
        ('time', np.int64, 'Event start time in ns since the unix epoch'),
        ('endtime', np.int64, 'Event end time in ns since the unix epoch')]
    events_seen = 0

    def get_window_size(self):
        return (2 * self.config['left_event_extension'] +
                self.config['right_event_extension'])

    def compute(self, peaks):
        le = self.config['left_event_extension']
        re = self.config['right_event_extension']

        triggers = peaks[
            (peaks['area'] > self.config['trigger_min_area'])
            & (peaks['n_competing'] <= self.config['trigger_max_competing'])]

        # Join nearby triggers
        t0, t1 = self.find_peak_groups(
            triggers,
            gap_threshold=le + re + 1,
            left_extension=le,
            right_extension=re,
            max_duration=self.config['max_event_duration'])

        result = np.zeros(len(t0), self.dtype)
        result['time'] = t0
        result['endtime'] = t1
        result['event_number'] = np.arange(len(result)) + self.events_seen

        self.events_seen += len(result)

        return result
        # TODO: someday investigate if/why loopplugin doesn't give
        # anything if events do not contain peaks..

    @staticmethod
    def find_peak_groups(peaks, gap_threshold,
                         left_extension=0, right_extension=0,
                         max_duration=int(1e9)):
        """Return boundaries of groups of peaks separated by gap_threshold,
        extended left and right.
        :param peaks: Peaks to group
        :param gap_threshold: Minimum gap between peaks
        :param left_extension: Extend groups by this many ns left
        :param right_extension: " " right
        :param max_duration: Maximum group duration. See strax.find_peaks for
        what happens if this is exceeded
        :return: time, endtime arrays of group boundaries
        """
        # Mock up a "hits" array so we can just use the existing peakfinder
        # It doesn't work on raw peaks, since they might have different dts
        # TODO: is there no cleaner way?
        fake_hits = np.zeros(len(peaks), dtype=strax.hit_dtype)
        fake_hits['dt'] = 1
        fake_hits['time'] = peaks['time']
        # TODO: could this cause int overrun nonsense anywhere?
        fake_hits['length'] = peaks['endtime'] - peaks['time']
        fake_peaks = strax.find_peaks(
            fake_hits, to_pe=np.zeros(1),
            gap_threshold=gap_threshold,
            left_extension=left_extension, right_extension=right_extension,
            min_hits=1, min_area=0,
            max_duration=max_duration)
        return fake_peaks['time'], strax.endtime(fake_peaks)


@export
class EventBasics(strax.LoopPlugin):
    __version__ = '0.0.1'
    depends_on = ('events',
                  'peak_basics', 'peak_classification',
                  'peak_positions', 'n_competing')

    def infer_dtype(self):
        dtype = [(('Number of peaks in the event',
                   'n_peaks'), np.int32),
                 (('Drift time between main S1 and S2 in ns',
                   'drift_time'), np.int64)]
        for i in [1, 2]:
            dtype += [((f'Main S{i} peak index',
                        f's{i}_index'), np.int32),
                      ((f'Main S{i} area (PE), uncorrected',
                        f's{i}_area'), np.float32),
                      ((f'Main S{i} area fraction top',
                        f's{i}_area_fraction_top'), np.float32),
                      ((f'Main S{i} width (ns, 50% area)',
                        f's{i}_range_50p_area'), np.float32),
                      ((f'Main S{i} number of competing peaks',
                        f's{i}_n_competing'), np.int32)]
        dtype += [(f'x_s2', np.float32,
                   f'Main S2 reconstructed X position (cm), uncorrected',),
                  (f'y_s2', np.float32,
                   f'Main S2 reconstructed Y position (cm), uncorrected',)]
        return dtype

    def compute_loop(self, event, peaks):
        result = dict(n_peaks=len(peaks))
        if not len(peaks):
            return result

        main_s = dict()
        for s_i in [2, 1]:
            s_mask = peaks['type'] == s_i

            # For determining the main S1, remove all peaks
            # after the main S2 (if there was one)
            # This is why S2 finding happened first
            if s_i == 1 and result[f's2_index'] != -1:
                s_mask &= peaks['time'] < main_s[2]['time']

            ss = peaks[s_mask]
            s_indices = np.arange(len(peaks))[s_mask]

            if not len(ss):
                result[f's{s_i}_index'] = -1
                continue

            main_i = np.argmax(ss['area'])
            result[f's{s_i}_index'] = s_indices[main_i]
            s = main_s[s_i] = ss[main_i]

            for prop in ['area', 'area_fraction_top',
                         'range_50p_area', 'n_competing']:
                result[f's{s_i}_{prop}'] = s[prop]
            if s_i == 2:
                for q in 'xy':
                    result[f'{q}_s2'] = s[q]

        # Compute a drift time only if we have a valid S1-S2 pairs
        if len(main_s) == 2:
            result['drift_time'] = main_s[2]['time'] - main_s[1]['time']

        return result


@export
@strax.takes_config(
    strax.Option(
        name='electron_drift_velocity',
        help='Vertical electron drift velocity in cm/ns (1e4 m/ms)',
        default=1.3325e-4
    ),
)
class EventPositions(strax.Plugin):
    depends_on = ('event_basics',)
    dtype = [
        ('x', np.float32,
         'Interaction x-position, field-distortion corrected (cm)'),
        ('y', np.float32,
         'Interaction y-position, field-distortion corrected (cm)'),
        ('z', np.float32,
         'Interaction z-position, field-distortion corrected (cm)'),
        ('r', np.float32,
         'Interaction radial position, field-distortion corrected (cm)'),
        ('z_naive', np.float32,
         'Interaction z-position using mean drift velocity only (cm)'),
        ('r_naive', np.float32,
         'Interaction r-position using observed S2 positions directly (cm)'),
        ('theta', np.float32,
         'Interaction angular position (radians)')]

    def compute(self, events):
        z_obs = - self.config['electron_drift_velocity'] * events['drift_time']

        orig_pos = np.vstack([events['x_s2'], events['y_s2'], z_obs]).T
        r_obs = np.linalg.norm(orig_pos[:, :2], axis=1)

        result = dict(x=orig_pos[:, 0] * scale,
                      y=orig_pos[:, 1] * scale,
                      z=z_obs,
                      r_naive=r_obs,
                      theta=np.arctan2(orig_pos[:, 1], orig_pos[:, 0]))

        return result


@strax.takes_config(
    strax.Option(
        'electron_lifetime',
        help="Electron lifetime (ns)",
        default=40000)
)
class CorrectedAreas(strax.Plugin):
    depends_on = ['event_basics', 'event_positions']
    dtype = [('cs1', np.float32, 'Corrected S1 area (PE)'),
             ('cs2', np.float32, 'Corrected S2 area (PE)')]

    def setup(self):
        self.s1_map = InterpolatingMap(
            get_resource(self.config['s1_relative_lce_map']))
        self.s2_map = InterpolatingMap(
            get_resource(self.config['s2_relative_lce_map']))

    def compute(self, events):
        event_positions = np.vstack([events['x'], events['y'], events['z']]).T
        s2_positions = np.vstack([events['x_s2'], events['y_s2']]).T
        lifetime_corr = np.exp(
            events['drift_time'] / self.config['electron_lifetime'])

        return dict(
            cs1=events['s1_area'] / self.s1_map(event_positions),
            cs2=events['s2_area'] * lifetime_corr / self.s2_map(s2_positions))


@strax.takes_config(
    strax.Option(
        'g1',
        help="S1 gain in PE / photons produced",
        default=0.1),
    strax.Option(
        'g2',
        help="S2 gain in PE / electrons produced",
        default=30),
    strax.Option(
        'lxe_w',
        help="LXe work function in quanta/eV",
        default=13.7e-3),
)
class EnergyEstimates(strax.Plugin):
    depends_on = ['corrected_areas']
    dtype = [
        ('e_light', np.float32, 'Energy in light signal (keV)'),
        ('e_charge', np.float32, 'Energy in charge signal (keV)'),
        ('e_ces', np.float32, 'Energy estimate (keV_ee)')]

    def compute(self, events):
        w = self.config['lxe_w']
        el = w * events['cs1'] / self.config['g1']
        ec = w * events['cs2'] / self.config['g2']
        return dict(e_light=el,
                    e_charge=ec)


class EventInfo(strax.MergeOnlyPlugin):
    depends_on = ['events',
                  'event_basics', 'event_positions', 'corrected_areas',
                  'energy_estimates']
    save_when = strax.SaveWhen.ALWAYS
