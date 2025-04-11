from datetime import datetime, timedelta

import pyqtgraph as pg

import pytz

UNIX_EPOCH_naive = datetime(1970, 1, 1, 0, 0)  # offset-naive datetime
UNIX_EPOCH_offset_aware = datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc)  # offset-aware datetime
UNIX_EPOCH = UNIX_EPOCH_naive

TS_MULT_us = 1e6


def now_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    return int((datetime.now() - epoch).total_seconds() * ts_mult)


def min_h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    if datetime.now().minute < 30:
        return int((datetime.now().replace(second=0, microsecond=0, minute=0) - epoch).total_seconds() * ts_mult)
    else:
        return int((datetime.now().replace(second=0, microsecond=0, minute=30) - epoch).total_seconds() * ts_mult)


def max_h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    if datetime.now().minute < 30:
        print((datetime.now().replace(second=59, microsecond=0, minute=59) - epoch))
        print(int((datetime.now().replace(second=59, microsecond=0, minute=59) - epoch).total_seconds() * ts_mult))
        return int((datetime.now().replace(second=59, microsecond=0, minute=59) - epoch).total_seconds() * ts_mult)
    else:
        return int((datetime.now().replace(second=0, microsecond=0, minute=30) + timedelta(hours=1)
                    - epoch).total_seconds() * ts_mult)


def min_12h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    if datetime.now().hour < 12:
        return int(
            (datetime.now().replace(second=0, microsecond=0, minute=0, hour=0) - epoch).total_seconds() * ts_mult)
    else:
        return int(
            (datetime.now().replace(second=0, microsecond=0, minute=0, hour=12) - epoch).total_seconds() * ts_mult)


def max_12h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    if datetime.now().hour < 12:
        return int(
            (datetime.now().replace(second=59, microsecond=0, minute=59, hour=11) - epoch).total_seconds() * ts_mult)
    else:
        return int(
            (datetime.now().replace(second=59, microsecond=0, minute=59, hour=23) - epoch).total_seconds() * ts_mult)


def min_24h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    return int((datetime.now().replace(second=0, microsecond=0, minute=0, hour=0) - epoch).total_seconds() * ts_mult)


def max_24h_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    return int((datetime.now().replace(second=59, microsecond=0, minute=59, hour=23) - epoch).total_seconds() * ts_mult)


def int2dt(ts, ts_mult=TS_MULT_us):
    return datetime.utcfromtimestamp(float(ts) / ts_mult)


class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int2dt(value).strftime("%H:%M") for value in values]


class ParameterPlot(pg.PlotItem):
    def __init__(self, parent=None, name=None, labels=None, title=None,
                 viewBox=None, axisItems=None, enableMenu=True, period=None):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.plot()
        self.y = []
        self.x = []
        self.spacing = 0
        self.changed = False
        self.period = period
        if period == "1 ч":
            self.first = min_h_timestamp()
            self.last = max_h_timestamp()
            self.spacing = 900 * TS_MULT_us
        elif period == "12 ч":
            self.first = min_12h_timestamp()
            self.last = max_12h_timestamp()
            self.spacing = 10800 * TS_MULT_us
        else:
            self.first = min_24h_timestamp()
            self.last = max_24h_timestamp()
            self.spacing = 21600 * TS_MULT_us

    def update(self, conc, period):
        self.clear()
        self.y.append(conc)
        self.x.append(now_timestamp())
        if self.x[-1] >= self.last:
            if period == "1 ч":
                self.first = min_h_timestamp()
                self.last = max_h_timestamp()
                self.spacing = 900 * TS_MULT_us
            elif period == "12 ч":
                self.first = min_12h_timestamp()
                self.last = max_12h_timestamp()
                self.spacing = 10800 * TS_MULT_us
            else:
                self.first = min_24h_timestamp()
                self.last = max_24h_timestamp()
                self.spacing = 21600 * TS_MULT_us
            self.changed = False
            self.x = self.x[:-1]
            self.y = self.y[:-1]
        param_data = pg.PlotDataItem(list(self.x), list(self.y), pen=None, symbol='o', symbolSize=6)
        if not self.changed:
            date_axis = TimeAxisItem(orientation='bottom')
            self.setAxisItems(axisItems={'bottom': date_axis})
            self.setXRange(self.first, self.last)
            self.changed = True
            date_axis.setStyle(autoExpandTextSpace=True)
            date_axis.setTickSpacing(levels=[(self.spacing, 0)])
        self.addItem(param_data)
