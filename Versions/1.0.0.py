import sys
import os
import cv2
import yaml
from PyQt5 import QtCore, QtGui, QtWidgets

# Set folders and tile size
IMAGE_FOLDER = "_Combined"
THUMB_FOLDER = "_Thumbs"
TILE_HEIGHT = 512  # Maximum height per tile
CHAPTERS_FILE = "Chapters.txt"
SCROLL_AMOUNT = 75
AUTO_NEXT = False

stream = open("config.yaml", 'r')
dictionary = yaml.safe_load(stream)
for key, value in dictionary.items():
    if key == "Thumbnails":
        THUMB_FOLDER = str(value)
    elif key == "Chapters":
        IMAGE_FOLDER = str(value)
    elif key == "ScrollAmount":
        SCROLL_AMOUNT = int(value)
    elif key == "Chapters.txt":
        CHAPTERS_FILE = str(value)
    elif key == "AutoNext":
        AUTO_NEXT = bool(value)
    print (key + ": " + str(value))
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
class ImageLoader(QtCore.QObject):
    finished = QtCore.pyqtSignal(list, str)  # emits list of tiles (QPixmaps) and chapter name

    def __init__(self, image_file, available_width, parent=None):
        super().__init__(parent)
        self.image_file = image_file
        self.available_width = available_width

    @QtCore.pyqtSlot()
    def run(self):
        # Load the image with OpenCV
        image_path = os.path.join(IMAGE_FOLDER, self.image_file)
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            print("Failed to load image:", self.image_file)
            self.finished.emit([], self.image_file)
            return

        # Convert from BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize the image to fit the available width
        h, w, _ = img.shape
        ratio = self.available_width / w
        new_width = self.available_width
        new_height = int(h * ratio)
        resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)

        # Split the resized image into vertical tiles
        tiles = []
        for i in range(0, new_height, TILE_HEIGHT):
            tile_img = resized_img[i:min(i + TILE_HEIGHT, new_height), :]
            tile_h, tile_w, _ = tile_img.shape
            bytes_per_line = 3 * tile_w
            qimg = QtGui.QImage(tile_img.data, tile_w, tile_h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qimg)
            tiles.append(pixmap)
        self.finished.emit(tiles, self.image_file)

class MangaReader(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manga Reader")
        self.resize(655, 980)
        self.setWindowIcon(QtGui.QIcon(resource_path("B-MR.ico")))
        # Get sorted list of image files
        self.image_files = sorted([f for f in os.listdir(IMAGE_FOLDER)
                                   if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        self.current_index = 0
        self.loadingNext = False  # Flag to prevent multiple auto-advances

        # Main widget and layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Top navigation widget with chapter label and buttons
        nav_widget = QtWidgets.QWidget()
        nav_layout = QtWidgets.QHBoxLayout(nav_widget)
        self.chapter_label = QtWidgets.QLabel("")
        nav_layout.addWidget(self.chapter_label)
        btn_prev = QtWidgets.QPushButton("Previous")
        btn_prev.clicked.connect(self.previous_image)
        nav_layout.addWidget(btn_prev)
        btn_next = QtWidgets.QPushButton("Next")
        btn_next.clicked.connect(self.next_image)
        nav_layout.addWidget(btn_next)
        btn_select = QtWidgets.QPushButton("Select Chapter")
        btn_select.clicked.connect(self.open_chapter_selection)
        nav_layout.addWidget(btn_select)
        main_layout.addWidget(nav_widget)

        # Scroll area to hold image tiles
        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.verticalScrollBar().setSingleStep(SCROLL_AMOUNT)
        self.scrollArea.setWidgetResizable(True)
        main_layout.addWidget(self.scrollArea)
        self.image_container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.image_container)
        self.vbox.setSpacing(0)  # Remove spacing between tiles
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setAlignment(QtCore.Qt.AlignTop)
        self.scrollArea.setWidget(self.image_container)

        # Connect the vertical scroll bar to auto-advance when scrolled to the bottom
        self.scrollArea.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)

        # To keep reference to the loader thread
        self.loader_thread = None

        if self.image_files:
            self.load_image(self.image_files[self.current_index])

    def load_image(self, image_file):
        # Clear previous tiles from the layout
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Get available width from the scroll area viewport
        available_width = self.scrollArea.viewport().width() - 20

        # Update chapter label (you could enhance this to show the chapter title if available)
        self.chapter_label.setText(f"Viewing: {image_file}")

        # Create a thread and worker to load the image in the background
        self.loader_thread = QtCore.QThread()
        self.worker = ImageLoader(image_file, available_width)
        self.worker.moveToThread(self.loader_thread)
        self.loader_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_image_loaded)
        self.worker.finished.connect(self.loader_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        self.loader_thread.start()

    @QtCore.pyqtSlot(list, str)
    def on_image_loaded(self, tiles, chapter_name):
        # Add each tile as a QLabel in the vertical layout
        for pixmap in tiles:
            label = QtWidgets.QLabel()
            label.setPixmap(pixmap)
            label.setStyleSheet("padding: 0px; margin: 0px; border: none;")
            label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self.vbox.addWidget(label, 0, QtCore.Qt.AlignTop)
        if AUTO_NEXT == False:
            # Add a large "NEXT" button at the bottom of the page
            next_button = QtWidgets.QPushButton("NEXT")
            next_button.setFixedHeight(100)
            next_button.setStyleSheet("font-size: 24px;")
            next_button.clicked.connect(self.next_image)
            self.vbox.addWidget(next_button)
            # Optionally add a stretch so the button is always visible at the bottom
        self.vbox.addStretch(1)
        self.loadingNext = False  # Reset flag after loading a new chapter

    def next_image(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image(self.image_files[self.current_index])

    def previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image(self.image_files[self.current_index])

    def on_scroll_changed(self, value):
        scrollbar = self.scrollArea.verticalScrollBar()
        if AUTO_NEXT == True:
            if value == scrollbar.maximum() and self.current_index < len(self.image_files) - 1 and not self.loadingNext:
                self.loadingNext = True
                self.next_image()

    def open_chapter_selection(self):
        dialog = ChapterSelectionDialog(self.image_files, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            index = dialog.get_selected_index()
            if index is not None:
                self.current_index = index
                self.load_image(self.image_files[self.current_index])

class ChapterSelectionDialog(QtWidgets.QDialog):
    def __init__(self, image_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Chapter")
        self.resize(600, 400)
        self.image_files = image_files
        self.selected_index = None
        self.setWindowIcon(QtGui.QIcon(resource_path("B-MR.ico")))

        layout = QtWidgets.QVBoxLayout(self)
        self.listWidget = QtWidgets.QListWidget()
        layout.addWidget(self.listWidget)

        # Read Chapters.txt if it exists
        if os.path.exists(CHAPTERS_FILE):
            try:
                with open(CHAPTERS_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print("Error reading Chapters.txt:", e)
                lines = []
        else:
            lines = []

        # Collect entries from Chapters.txt.
        # Distinguish between season headers and episode entries.
        entries = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Season"):
                # Season header entry
                entries.append((stripped, False))
            elif " - " in stripped:
                # Episode entry, add indentation for clarity.
                entries.append(("    " + stripped, True))
            # else ignore unexpected lines

        # Count total episode entries (excluding season headers)
        total_episodes = sum(1 for text, is_episode in entries if is_episode)

        # Process the entries and compute a thumbnail index for each episode.
        episode_counter = 0  # 0-index for episodes only
        for text, is_episode in entries:
            item = QtWidgets.QListWidgetItem(text)
            if is_episode:
                # Compute thumbnail index using linear interpolation.
                if total_episodes > 1:
                    thumb_index = round(episode_counter * (len(self.image_files) - 1) / (total_episodes - 1))
                else:
                    thumb_index = 0
                item.setData(QtCore.Qt.UserRole, thumb_index)

                # Try to load the thumbnail for this computed index.
                if thumb_index < len(self.image_files):
                    thumb_path = os.path.join(THUMB_FOLDER, self.image_files[thumb_index])
                    if os.path.exists(thumb_path):
                        thumb_img = cv2.imread(thumb_path, cv2.IMREAD_COLOR)
                        if thumb_img is not None:
                            thumb_img = cv2.cvtColor(thumb_img, cv2.COLOR_BGR2RGB)
                            h, w, _ = thumb_img.shape
                            scale = min(150 / w, 150 / h)
                            new_w = int(w * scale)
                            new_h = int(h * scale)
                            thumb_img = cv2.resize(thumb_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                            bytes_per_line = 3 * new_w
                            qimg = QtGui.QImage(thumb_img.data, new_w, new_h, bytes_per_line, QtGui.QImage.Format_RGB888)
                            pixmap = QtGui.QPixmap.fromImage(qimg)
                            item.setIcon(QtGui.QIcon(pixmap))
                episode_counter += 1
            else:
                # For season headers, disable selection.
                item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.listWidget.addItem(item)

        # Fallback: If no episode entries were loaded, list image files (with thumbnails) as before.
        if total_episodes == 0:
            for idx, file in enumerate(self.image_files):
                item = QtWidgets.QListWidgetItem(file)
                thumb_path = os.path.join(THUMB_FOLDER, file)
                if os.path.exists(thumb_path):
                    thumb_img = cv2.imread(thumb_path, cv2.IMREAD_COLOR)
                    if thumb_img is not None:
                        thumb_img = cv2.cvtColor(thumb_img, cv2.COLOR_BGR2RGB)
                        h, w, _ = thumb_img.shape
                        scale = min(150 / w, 150 / h)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        thumb_img = cv2.resize(thumb_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                        bytes_per_line = 3 * new_w
                        qimg = QtGui.QImage(thumb_img.data, new_w, new_h, bytes_per_line, QtGui.QImage.Format_RGB888)
                        pixmap = QtGui.QPixmap.fromImage(qimg)
                        item.setIcon(QtGui.QIcon(pixmap))
                item.setData(QtCore.Qt.UserRole, idx)
                self.listWidget.addItem(item)

        # OK and Cancel buttons
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def accept(self):
        selected_items = self.listWidget.selectedItems()
        for item in selected_items:
            data = item.data(QtCore.Qt.UserRole)
            if data is not None:
                self.selected_index = data
                break
        super().accept()

    def get_selected_index(self):
        return self.selected_index



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MangaReader()
    window.show()
    sys.exit(app.exec_())
