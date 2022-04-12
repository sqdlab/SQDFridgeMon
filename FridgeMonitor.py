import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import os
import json
import pkg_resources
import numpy as np
from FridgeParsers.ParserBluFors import ParserBluFors

class FridgeMonitor:
    def __init__(self, config_file_name='config.json'):
        data = None
        if os.path.isfile(config_file_name):
            with open(config_file_name) as json_file:
                data = json.load(json_file)
        assert not data is None, "Failed to load the configuration file!"
        self._recipients = data['Recipients']
        self._FromEmail = data['FromEmail']
        self._UserName = data['UserName']
        self._Password = data['Password']
        self._SMTP = data['SMTP']
        self._Port = data['Port']
        self._UseTLS = data['UseTLS']
        #
        self._FridgeName = data['FridgeName']
        self._AcceptableRanges = data['AcceptableParameterRanges']
        #
        fridge_log_type = data['FridgeType']
        fridge_log_location = data['FridgeLogLocation']
        assert fridge_log_type == 'BluFors' or fridge_log_type == 'Oxford', "Fridge type must be BluFors or Oxford"
        fridge_config_path = pkg_resources.resource_filename('FridgeConfigs', '')
        fridge_config_path = fridge_config_path.replace('\\','/')+'/'
        if fridge_log_type == 'BluFors':
            self._fridge_parser = ParserBluFors(fridge_config_path + 'BluFors.json', fridge_log_location)

    def send_email(self, subject, message_text):
        msg = MIMEText(message_text)
        sender = self._FromEmail
        recipients = self._recipients
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ", ".join(recipients)

        server = smtplib.SMTP(self._SMTP,self._Port)
        server.starttls()
        server.login(self._UserName,self._Password)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()    

    def run(self):
        while(True):
            bad_message = ''
            cur_param_vals = self._fridge_parser.ParseLatestParameters()
            for cur_param in self._AcceptableRanges:
                assert cur_param in cur_param_vals, f"Parameter {cur_param} not in the configuration. Check the spelling perhaps?"
                cur_val = cur_param_vals[cur_param]
                if not np.isnan(cur_val):
                    if cur_val < self._AcceptableRanges[cur_param][0]:
                        bad_message += f'{cur_param} is below the acceptable range at: {cur_val}\n'
                    if cur_val > self._AcceptableRanges[cur_param][1]:
                        bad_message += f'{cur_param} is above the acceptable range at: {cur_val}\n'
            if bad_message != '':
                bad_message += '\nAll parameters:\n'
                for cur_param in cur_param_vals:
                    bad_message += f'\t{cur_param}: {cur_param_vals[cur_param]}\n'
                self.send_email(f'{self._FridgeName} ALERT!', bad_message)
                print(bad_message)
                break

