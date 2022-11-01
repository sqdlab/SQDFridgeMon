from turtle import pen
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtUiTools import QUiLoader
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys  # We need sys so that we can pass argv to QApplication
import numpy as np
from multiprocessing.pool import ThreadPool
import pyqtgraph.exporters as pgExp

from functools import partial

import sqlite3
import os
import datetime
import json
import time


class DataExtractor:
    def __init__(self, data_thread_pool, dbFile, params_to_record):
        self.data_thread_pool = data_thread_pool
        self.isFetching = False
        self.async_result = None
        self.dbFile = dbFile
        self.params_to_record = params_to_record
    
    def fetch_data(self, timeFrame):
        self.isFetching = True
        self.async_result = self.data_thread_pool.apply_async(self._get_current_data, (timeFrame,)) # tuple of args

    def _get_current_data(self, timeFrame):
        # file_name = os.path.basename(self.dbFile)[:-3]
        db = sqlite3.connect(self.dbFile)
        cur = db.cursor()

        cur.execute('SELECT name from sqlite_master where type= "table"')

        ret_vals = {}
        for cur_table in self.params_to_record:
            cur.execute('SELECT time, value FROM {0} WHERE time >= {1} and time <= {2};'.format(cur_table, timeFrame[0], timeFrame[1]))
            ret_vals[cur_table] = np.array(cur.fetchall())
        
        db.close()

        return ret_vals


    def data_ready(self):
        if self.async_result:
            return self.async_result.ready()
        else:
            return False

    def get_data(self):
        while not self.async_result.ready():
            pass
        self.isFetching = False
        ret_val = self.async_result.get()
        self.async_result = None
        return ret_val


class MainWindow:
    def __init__(self, app, win):

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        win.frmPlots.setLayout(self.layout)

        self.win = win
        self.app = app
        self.data_extractor = None

        with open('configDash.json') as json_file:
            self.confs_all = json.load(json_file)

        self.fridges = [x for x in self.confs_all.keys()]
        self.win.cmbx_fridge.addItems(self.fridges)
        self.win.cmbx_fridge.currentIndexChanged.connect(partial(self._event_cmbx_fridge_changed) )
        self.win.cmbx_fridge.setCurrentIndex(0)

        self.cur_confs = self.confs_all[self.fridges[0]]
        self.data_thread_pool = ThreadPool(processes=2)
        self.data_extractor = DataExtractor(self.data_thread_pool, '', [])
        self._get_db_filepath()
        self.retake_data = False
        self.setup_axes()
        self.data_extractor.params_to_record = self.plot_and_datalines.keys()

        self.time_ranges = [("Last 10 minutes", datetime.timedelta(minutes=-10)),
                            ("Last 1 hour", datetime.timedelta(hours=-1)),
                            ("Last 12 hours", datetime.timedelta(hours=-12)),
                            ("Last 24 hours", datetime.timedelta(days=-1)),
                            ("Last 2 days", datetime.timedelta(days=-2)),
                            ("Last week", datetime.timedelta(weeks=-1)),
                            ("Last month", datetime.timedelta(days=-30)),
                            ("Last 6 months", datetime.timedelta(days=-6 * 30)),    #Banker's definition
                            ("Last year", datetime.timedelta(days=-365)),           #Banker's definition
                            ("Custom", None)]
        self.win.cmbx_time_range.addItems([x[0] for x in self.time_ranges])
        self.win.cmbx_time_range.currentIndexChanged.connect(partial(self._event_cmbx_time_range_changed) )

        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def setup_axes(self):
        hour = [1,2,3,4,5,6,7,8,9,10]
        temperature = [30,32,34,32,33,31,29,32,35,45]
        for i in reversed(range(self.layout.count())): 
            self.layout.itemAt(i).widget().setParent(None)
        self.plot_and_datalines = {}
        for cur_conf in self.cur_confs['Display Config']:
            plot_layout_widget = pg.GraphicsLayoutWidget()#LB1.setObjectName('LABEL_1')
            plot_layout_widget.setParent(self.win.frmPlots)
            self.layout.addWidget(plot_layout_widget)

            confs = self.cur_confs['Display Config'][cur_conf]
            cm = pg.colormap.get('CET-D1') # prepare a linear color map https://colorcet.holoviz.org/
            for m, cur_conf in enumerate(confs):
                cur_plot = plot_layout_widget.addPlot(row=m, col=0)
                axis = pg.DateAxisItem()
                cur_plot.setAxisItems({'bottom':axis})
                cur_plot.setTitle(self.param_titles[cur_conf[0]]['label'])
                pen = cm.getPen( span=(cur_conf[1], cur_conf[2]) )
                data_line = cur_plot.plot(hour, temperature, pen=pen)
                self.plot_and_datalines[cur_conf[0]] = (cur_plot, data_line)
                if m > 0:
                    cur_plot.setXLink(self.plot_and_datalines[confs[0][0]][0])

    def _datetime_to_unix(self, objDateTime):
        return int(time.mktime(objDateTime.timetuple()))

    def _get_db_filepath(self):
        dbLoc = self.cur_confs['DB Filepath'] #'R:/EQUS-SQDLab/FridgeLogs/BluForsLD.db'
        with open(dbLoc[:-2] + 'json') as json_file:
            self.param_titles = json.load(json_file)
        self.data_extractor.dbFile = dbLoc
        self.retake_data = True
        self.setup_axes()

    def _event_cmbx_time_range_changed(self, idx):
        if idx == len(self.time_ranges) - 1:
            self.win.dte_start.setEnabled(True)
            self.win.dte_end.setEnabled(True)
        else:
            self.win.dte_start.setEnabled(False)
            self.win.dte_end.setEnabled(False)
    def _event_cmbx_fridge_changed(self, idx):
        self.cur_confs = self.confs_all[self.fridges[idx]]
        self._get_db_filepath()

    def _get_time_range(self):
        cur_ind = self.win.cmbx_time_range.currentIndex()
        if cur_ind == len(self.time_ranges) - 1:
            cur_range = (self.win.dte_start.dateTime().toPython(), self.win.dte_end.dateTime().toPython())
        else:
            cur_range = (datetime.datetime.now() + self.time_ranges[cur_ind][1], datetime.datetime.now())
        return (self._datetime_to_unix(cur_range[0]), self._datetime_to_unix(cur_range[1]))

    def update_plot_data(self):
        if self.data_extractor.data_ready():
            data = self.data_extractor.get_data()
            if not self.retake_data:
                for cur_table in data:
                    if data[cur_table].size == 0:
                        continue
                    self.plot_and_datalines[cur_table][1].setData(data[cur_table][:,0], data[cur_table][:,1])
                    self.plot_and_datalines[cur_table][0].setTitle(self.param_titles[cur_table]['label'] + f" {data[cur_table][-1,1]}{self.param_titles[cur_table]['unit'].replace('Â','')}")
            else:
                self.retake_data = False
                self.data_extractor.params_to_record = self.plot_and_datalines.keys()

        if not self.data_extractor.isFetching:
            self.data_extractor.fetch_data(self._get_time_range())


class UiLoader(QUiLoader):
    def createWidget(self, className, parent=None, name=""):
        # if className == "GraphicsLayoutWidget":
        #     self.plot_layout_widget = pg.GraphicsLayoutWidget(parent=parent)
        #     return self.plot_layout_widget
        return super().createWidget(className, parent, name)

def mainwindow_setup(w):
    w.setWindowTitle("Fridge Viewer")

def main():
    loader = UiLoader()
    app = QtWidgets.QApplication(sys.argv)
    window = loader.load("mainDash.ui", None)
    main_win = MainWindow(app, window)
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
