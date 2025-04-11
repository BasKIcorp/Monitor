import pyqtgraph as pg


class IntensityPlot(pg.PlotItem):

    def __init__(self, parent=None, name=None, labels=None, title='Спектр интенсивности',
                 viewBox=None, axisItems=None, enableMenu=True):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.showGrid(x=True, y=True, alpha=1)
        self.plot()
        self.getAxis("left").setTextPen("black")
        self.getAxis("bottom").setTextPen("black")
        self.transmission_data1 = None
        self.transmission_data2 = None

    def update(self, x, y, y2):
        self.clear()
        color1 = (158, 2, 2)
        color2 = (48, 133, 30)
        self.addLegend(brush="white", labelTextColor="black", pen="black")
        self.transmission_data1 = pg.PlotDataItem(x, y, pen=color1, name="Текущий спектр", width=4)
        self.transmission_data2 = pg.PlotDataItem(x, y2, pen=color2, name="Спектр пустой кюветы", width=4)
        self.addItem(self.transmission_data1)
        self.addItem(self.transmission_data2)



