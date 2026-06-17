import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from qt_material import apply_stylesheet

from ui.image_browser import ImageBrowser
from utils.helpers import resource_path


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        apply_stylesheet(app, theme='light_teal_500.xml')

        with open(resource_path("style.qss"), "r") as f:
            app.setStyleSheet(app.styleSheet() + f.read())

        viewer = ImageBrowser()
        viewer.setWindowIcon(QIcon(resource_path('ui_icons/icon.png')))
        viewer.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Press Enter to close...")