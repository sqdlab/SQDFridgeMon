from . ParserGeneral import ParserGeneral
import json
import os
import numpy as np

class ParserBluFors(ParserGeneral):
    def __init__(self, config_file, log_directory):
        self._log_dir = log_directory
        self._log_dir = self._log_dir.replace('\\','/')
        if self._log_dir[-1] != '/':
            self._log_dir = self._log_dir + '/'

        #Get configuration data - value for a key is given as: [file-name, label, offset to value]
        #For example, ["Status", "cpatempwi", 1] implies the label "cpatempwi" with the value being
        #the index right after in the comma separated file...
        with open(config_file) as json_file:
            data = json.load(json_file)
        
        self._files_to_scan = {}
        for cur_key in data:
            cur_file_name = data[cur_key][0]
            if not cur_file_name in self._files_to_scan:
                self._files_to_scan[cur_file_name] = []
            self._files_to_scan[cur_file_name] += [[cur_key] + data[cur_key][1:]]

    def ParseLatestParameters(self):
        #Get log folders present
        cur_dirs = [self._log_dir + name for name in os.listdir(self._log_dir) if os.path.isdir(self._log_dir + name)]
        cur_dirs = sorted(cur_dirs)
        #
        #Select latest log-file set
        cur_dir = cur_dirs[-1]
        cur_log_files = os.listdir(cur_dir)
        #
        ret_dict = {}
        for cur_file_name in self._files_to_scan:
            cur_file = [file_name for file_name in cur_log_files if file_name.startswith(cur_file_name)]
            #Check if file exists in directory - otherwise, just fill the parameters with NaNs...
            if len(cur_file) > 0:
                cur_file = cur_dir + '/' + cur_file[0]
                with open(cur_file, 'r') as f:
                    last_line = f.read().splitlines()[-1]
                last_entries = last_line.split(',')
                for cur_param in self._files_to_scan[cur_file_name]:
                    if cur_param[1] in last_entries:
                        #The value is in the index of the label cur_param[1] offset by cur_param[2]
                        ret_dict[cur_param[0]] = float(last_entries[last_entries.index(cur_param[1])+cur_param[2]])
                    else:
                        ret_dict[cur_param[0]] = np.nan
            else:
                for cur_param in self._files_to_scan[cur_file_name]:
                    ret_dict[cur_param[0]] = np.nan
        return ret_dict
