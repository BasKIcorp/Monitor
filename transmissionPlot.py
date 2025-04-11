import pyqtgraph as pg


class TransmissionPlot(pg.PlotItem):

    def __init__(self, parent=None, name=None, labels=None, title='Спектр поглощения',
                 viewBox=None, axisItems=None, enableMenu=True):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.addLegend()
        self.showGrid(x=True, y=True, alpha=1)
        self.intensity_plot = self.plot()
        self.getAxis("left").setTextPen("black")
        self.getAxis("bottom").setTextPen("black")

    def update(self, x, y):
        self.clear()
        intensity_data = pg.PlotDataItem(x, y, pen=(2, 80, 158))
        self.addItem(intensity_data)
