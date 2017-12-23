import sys
from PyQt5.QtWidgets import (QMainWindow, QAction, qApp, QApplication, QVBoxLayout,
                             QFileDialog, QErrorMessage, QHBoxLayout, QLabel, QWidget)
from PyQt5.QtGui import QPainter, QFont, QColor, QPixmap, QPen, QIcon, QImage
from PyQt5.QtCore import Qt
import reader


class ReaderWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.picture = None
        self.picture_path = None
        self.picture_widget = None
        self.central_widget = None
        self.initUI()

    def initUI(self):
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+C')
        exit_action.triggered.connect(qApp.quit)

        open_action = QAction('&Open', self)
        open_action.setStatusTip('Open file')
        open_action.triggered.connect(self.openFileNameDialog)

        info_action = QAction('&File information', self)
        info_action.setStatusTip('Get file information')
        info_action.triggered.connect(self.display_info)

        self.statusBar()
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(open_action)
        file_menu.addAction(exit_action)

        info_menu = menu_bar.addMenu('&Info')
        info_menu.addAction(info_action)

        self.setGeometry(300, 300, 900, 600)
        self.setWindowTitle('Reader')

        self.default_picture()  # TODO: delete (TEMP DEFAULT)

    def openFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "QFileDialog.getOpenFileName()", "",
                                                  "All Files (*);;PNG Files (*.png)", options=options)

        if fileName:
            try:
                self.picture = reader.Reader().open(fileName).get_picture()
                self.picture_path = fileName
            except TypeError:
                error_dialog = QErrorMessage(self)
                error_dialog.setWindowTitle('Error')
                error_dialog.showMessage('File seems to be not in PNG format or file has been corrupted')
            self.display_picture()

    def display_picture(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)  # refresh central widget

        self.hbox, self.vbox = QHBoxLayout(), QVBoxLayout()  # create layout

        self.picture_widget = PictureWidget(self.picture, self.picture_path, self)

        self.hbox.addStretch(1)
        self.hbox.addWidget(self.picture_widget)  # add picture on layout
        self.hbox.addStretch(1)

        self.vbox.addLayout(self.hbox)
        self.centralWidget().setLayout(self.vbox)  # set layout on central widget

    def display_info(self):
        if self.picture is None:
            error_dialog = QErrorMessage(self)
            error_dialog.setWindowTitle('Error')
            error_dialog.showMessage('Please, select the file')
            return

        info = InfoWidget(self.picture, self)
        info.show()

    def default_picture(self):  # TODO: delete (TEMP)
        self.picture = reader.Reader().open('pics/400x400.png').get_picture()
        self.display_picture()


class InfoWidget(QMainWindow):
    def __init__(self, picture, parent=None):
        super().__init__(parent)
        self.picture = picture
        self.text = ''
        self.initUI()

    def initUI(self):
        self.format_text()

        self.setGeometry(300, 300, 300, 200)
        self.setWindowTitle('Information')

    def format_text(self):
        self.text += 'Name: {}\n'.format(self.picture.name)
        self.text += 'Dimensions: {}x{}\n'.format(self.picture.width, self.picture.height)
        self.text += 'Bit depth: {}\n'.format(self.picture.bit_depth)
        self.text += 'Sample depth: {}\n'.format(self.picture.sample_depth)
        self.text += 'Pixel type: {}\n'.format(self.picture.type_of_pixel)
        self.text += 'Alpha: {}\n'.format(self.picture.alpha_channel)
        # self.text += 'Compression: {}\n'.format(self.picture.compression_method)
        # self.text += 'Filter: {}\n'.format(self.picture.filter_method)
        # self.text += 'Interlace: {}\n'.format(self.picture.interlace_method)
        if self.picture.last_modification_time:
            self.text += 'Last modification time: {}\n'.format(self.picture.last_modification_time)
        if self.picture.text_info:
            self.text += 'Integrated text: {}\n'.format(self.picture.text_info)

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        self.drawWidget(event, qp)
        qp.end()

    def drawWidget(self, event, qp):
        qp.setPen(QColor(0, 0, 0))
        qp.setFont(QFont('Serif', 10, QFont.Light))
        qp.drawText(event.rect(), Qt.AlignCenter, self.text)


class PictureWidget(QWidget):
    def __init__(self, picture, path, parent=None):
        super().__init__(parent)
        self.qimage = None
        self.pixmap = None
        self.picture = picture
        self.picture_path = path
        self.initUI()

    def initUI(self):
        # self.qimage = QImage(self.picture._temp_output_stream, self.picture.width, self.picture.height, QImage.Format_RGB888)
        #
        # hbox = QHBoxLayout(self)
        #
        # lbl = QLabel(self)
        # lbl.setPixmap(QPixmap.fromImage(self.qimage))  # create qpixmap from qimage

        hbox = QHBoxLayout(self)
        # пока что открываем картинку через PyQt5,
        # т.к. нужно додумать как из байт сформировать пиксели (снять фильтрацию).
        # все нужная информация о картинке прочитана и сохранена в picture.
        self.pixmap = QPixmap(self.picture_path)
        lbl = QLabel(self)
        lbl.setPixmap(self.pixmap)

        hbox.addWidget(lbl)
        self.setLayout(hbox)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ReaderWidget()
    ex.show()
    sys.exit(app.exec_())
