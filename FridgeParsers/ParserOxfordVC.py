from .ParserGeneral import ParserGeneral
import json
import os
import numpy as np

class ParserOxfordVC(ParserGeneral):
    def __init__(self, config_file, log_directory):
        self._log_dir = log_directory
        self._log_dir = self._log_dir.replace('\\','/')
        if self._log_dir[-1] != '/':
            self._log_dir = self._log_dir + '/'

        #Get configuration data - value for a key is given as the data entry title when parsing the vcl file
        with open(config_file) as json_file:
            self.translation_table = json.load(json_file)

    def _parse_with_numpy(self, filename, MAX_CHANNELS_COUNT = 52):
        #Code adapted from: https://github.com/StSav012/VeriCold_log_parser
        def _parse(file_handle):
            file_handle.seek(0x1800 + 32)
            titles = [file_handle.read(32).strip(b'\0').decode('ascii') for _ in range(MAX_CHANNELS_COUNT - 1)]
            titles = list(filter(None, titles))
            file_handle.seek(0x3000)
            # noinspection PyTypeChecker
            dt = np.dtype(np.float64).newbyteorder('<')
            data = np.frombuffer(file_handle.read(), dtype=dt)
            i = 0
            data_item_size = None
            while i < data.size:
                if data_item_size is None:
                    data_item_size = int(round(data[i] / dt.itemsize))
                elif int(round(data[i] / dt.itemsize)) != data_item_size:
                    raise RuntimeError('Inconsistent data: some records are faulty')
                i += int(round(data[i] / dt.itemsize))
            return titles, data.reshape((data_item_size, -1), order='F')[1:(len(titles) + 1)]

        with open(filename, 'rb') as f_in:
            return _parse(f_in)

    def ParseLatestParameters(self):
        #Get log folders present
        cur_files = [self._log_dir + name for name in os.listdir(self._log_dir) if name.endswith('.vcl')]
        cur_files = sorted(cur_files)
        #
        #Read latest log-file set
        cur_file = cur_files[-1]
        try:
            data = self._parse_with_numpy(cur_file)
            #
            ret_dict = {}
            titles = data[0]
            for cur_label in self.translation_table:
                cur_data_title = self.translation_table[cur_label]
                if cur_data_title in titles:
                    data_ind = titles.index(cur_data_title)
                    ret_dict[cur_label] = data[1][data_ind,-1]
        except:
            #If there's an error in parsing, just fill in a bunch of NaNs...
            for cur_label in self.translation_table:
                ret_dict[cur_label] = np.nan
        return ret_dict
