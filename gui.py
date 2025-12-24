#import necessary libraries
import sys
import os

from ctypes import windll, wintypes


#pyside6 stuff
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QStyle, QToolButton, QButtonGroup, QMessageBox,
    QCheckBox, QFileDialog, QVBoxLayout, QHBoxLayout, QProgressBar, QTabWidget, QTextEdit, QMainWindow
)
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QSize, Slot

#other py scripts
from dlsingle import download_video
from dlplaylist import download_playlist
from dl_large_playlist import download_playlist as download_large_playlist

#libraries for the server which listens for input from the browser extension
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

#update check lib
import urllib.request


#ico path:
def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, relative_path)

#prevent previous server instances from blocking connection
class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

#COLOR SCHEME
YOUTUBE_BG = "#ecd6b8"
YOUTUBE_SURFACE = "#FFFFFF"
YOUTUBE_RED = "#c9c9c9"
TEXT_MUTED = "#ef2a34"
BORDER_COLOR = "#341b0e"
WINDOW_CONTROL_BG = "#341b0e"
WINDOW_CONTROL_HOVER = "#341b0e"
CLOSE_HOVER = "#c42b1c"
DLBUTT = "#341b0e"

#THE SERVER - this function allows the browser extension to make requests outside of the browser (to the crateplug standalone)
class ExtensionRequestHandler(BaseHTTPRequestHandler):
    gui_instance = None

    def _set_cors_headers(self): #defining CORS
        self.send_header("Access-Control-Allow-Origin", "*") #allow any website/extension to make requests to this server
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS") #server accepts post and options requests
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    #pre flight check
    def do_OPTIONS(self): 
        self.send_response(200) #response of 200 = good to go
        self._set_cors_headers()
        self.end_headers()

    #the real deal
    def do_POST(self):
        if self.path != "/download": #check for download path
            self.send_response(404) #error if not dl path
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0)) #this tells python exactly how much data to read
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) #convert to python dictionary
            url = data.get("url") #extract url

            if url and ExtensionRequestHandler.gui_instance: #if there's a url and the GUI is open
                ExtensionRequestHandler.gui_instance.external_url_received.emit(url) #send the url to the GUI input

            self.send_response(200) #tells browser the url was received succesfully
            self._set_cors_headers() 
            self.end_headers()

        except Exception: #response for if it doesn't work
            self.send_response(400)
            self._set_cors_headers()
            self.end_headers()


#this is the download worker class
#runs downloads in the background with a separate worker thread - avoid freezing GUI
class DownloadWorker(QThread):
    
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

#runs when the workers is created and receives the input to the GUI
    def __init__(self, url, output_dir, mode):
        super().__init__() #initialize the Qthread base class to separate downloads and processing of (GUI) code
        self.url = url 
        self.output_dir = output_dir
        self.mode = mode

    #this is what runs in a background thread - pretty self explanatory
    def run(self):
        try:
            if self.mode == "large_playlist":
                download_large_playlist(self.url, self.output_dir, self.status.emit)

            elif self.mode == "playlist":
                download_playlist(self.url, self.output_dir, self.status.emit)

            else:
                download_video(self.url, self.output_dir, self.status.emit)

            self.finished.emit() #signals for succesful DL
        except Exception as e:
            self.error.emit(str(e))



# MAIN GUI
class DownloaderGUI(QMainWindow): #main widget
    external_url_received = Signal(str)
    def __init__(self): #runs when window is created
        super().__init__() #initialize qwidget
        self.setFixedSize(400, 450) #MAIN WINDOW SIZE
        self.settings = QSettings("crateplug", "downloader") #tells windows where to look for saved settings
        self.setObjectName("root")
        self.worker = None
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.is_downloading = False

    # brwser EXTwension listening server: this jawn right here below:

        ExtensionRequestHandler.gui_instance = self #this injects the GUI instance into the HTTP request handler (this is why the gui_instance variable  is defined before)

        def start_server():
            server = ReusableHTTPServer(("127.0.0.1", 48721), ExtensionRequestHandler) #create reusable HTTP server on port 48721
            server.serve_forever()

        threading.Thread(target=start_server, daemon=True).start()

#initialize UI
        self.setup_ui()
        self.load_settings()
        self.external_url_received.connect(self.handle_external_url) #ensures external urls are always run on the GUI thread
        self.apply_style()
        self.check_for_updates()

        #update checkerrrrr - insane that this takes so much code.. fuck makin gui
    def get_local_version(self):
        try:
            with open(resource_path("version.txt"), "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "unknown"


    def get_remote_version(self):
        try:
            url = "https://raw.githubusercontent.com/becksosa/crateplug/refs/heads/main/version.txt"
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            return None


    def check_for_updates(self):
        local_version = self.get_local_version()
        remote_version = self.get_remote_version()

        if not remote_version:
            return

        if local_version != remote_version:
            self.show_update_popup(local_version, remote_version)


    def show_update_popup(self, local, remote):
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Available")
        msg.setText(
            f"A new version of crateplug is available.\n\n"
            f"Installed: {local}\n"
            f"Latest: {remote}\n\n"
            "Do you want to download the update?"
        )

        msg.setIcon(QMessageBox.Information)

        download_btn = msg.addButton("Download", QMessageBox.AcceptRole)
        download_btn.setCursor(Qt.PointingHandCursor)
        later_btn = msg.addButton("Later", QMessageBox.RejectRole)
        later_btn.setCursor(Qt.PointingHandCursor)

        msg.exec()

        if msg.clickedButton() == download_btn:
            import webbrowser
            webbrowser.open("https://github.com/becksosa/crateplug/releases")




#set our settings (allows saved config for the folder)
    def load_settings(self):
        saved_path = self.settings.value(
            "download_folder",
            os.path.join(os.path.expanduser("~"), "Downloads")
        )
        self.path_input.setText(saved_path)


    # enable window dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(
                self.pos()
                + event.globalPosition().toPoint()
                - self.drag_pos
            )
            self.drag_pos = event.globalPosition().toPoint()
 
#browser extension url
    def handle_external_url(self, url):
        if self.is_downloading:
            return
        self.url_input.setText(url)
        self.start_download()

    #check 4 valid url - this runs before anything even gets sent to yt-dlp so we dont start trying to download bullshit requests if we know it wont work preemptively
    def is_valid_youtube_url(self, url):
        return "youtube.com" in url or "youtu.be" in url
    
    def is_valid_download_path(self, path):
        if not path:
            return False, "download path is empty"

        if not os.path.exists(path):
            return False, "download path does not exist"

        if not os.path.isdir(path):
            return False, "download path is not a folder"

        if not os.access(path, os.W_OK):
            return False, "no write permission for download path"

        return True, None


#this is the receiver for the output text box
    def append_output(self, text):
        self.output_box.clear()    
        self.output_box.setText(text)

#vertical layout, stack top to bottom
    def setup_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        main = QVBoxLayout(central)

        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
    
        # WINDOW CONTROLS (TOP RIGHT)
        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 6, 6, 0)
        controls_layout.setSpacing(6)

        controls_layout.addStretch()

        btn_min = QToolButton()
        btn_close = QToolButton()

        style = self.style()
        btn_min.setIcon(style.standardIcon(QStyle.SP_TitleBarMinButton))
        btn_close.setIcon(style.standardIcon(QStyle.SP_TitleBarCloseButton))

        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)

        btn_min.setFixedSize(24, 20)
        btn_close.setFixedSize(24, 20)

        controls_layout.addWidget(btn_min)
        controls_layout.addWidget(btn_close)
        main.addWidget(controls)

#content wrap
        content_wrap = QWidget(self)
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(12, 3, 12, 10)  
        content_layout.setSpacing(0)

        main.addWidget(content_wrap)


#container
        container = QWidget()
        container.setObjectName("container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container.setAttribute(Qt.WA_StyledBackground, True)
        content_layout.addWidget(container)

        # LOGO
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setContentsMargins(0, 18, 0, 0)
        pixmap = QPixmap(resource_path("logo.png"))
        logo.setPixmap(
            pixmap.scaledToWidth(
            300,  #  increase width here
            Qt.SmoothTransformation
        )
)
        container_layout.addWidget(logo) #adds logo to layout

        # CONTENT WRAPPER (everything except controls)
        content = QWidget(container)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(25, 14, 25, 14)  # left/right padding
        content_layout.setSpacing(12)

        container_layout.addWidget(content)



        # URL INPUT
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Input YouTube URL")
        content_layout.addWidget(self.url_input)

        # PATH INPUT
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(os.path.join(os.path.expanduser("~"), "Downloads"))

        browse_btn = QPushButton()
        style = self.style()
        browse_btn.setIcon(style.standardIcon(QStyle.SP_DirIcon))
        browse_btn.setIconSize(QSize(24, 24))
        browse_btn.setFixedSize(36, 36)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self.browse_folder)
        browse_btn.setObjectName("browseButton")

        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        content_layout.addLayout(path_layout)

        # CHECKBOX(es)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(20)
        
        small_font = QFont("IBM Plex Sans", 9)

        self.playlist_checkbox = QCheckBox("Playlist mode")
        self.playlist_checkbox.setCursor(Qt.PointingHandCursor)
        self.large_playlist_checkbox = QCheckBox("Large playlist mode")
        self.large_playlist_checkbox.setCursor(Qt.PointingHandCursor)
        self.playlist_checkbox.setFont(small_font)
        self.large_playlist_checkbox.setFont(small_font)


        #force one box checked at a time
        self.playlist_checkbox.toggled.connect(
            lambda checked: checked and self.large_playlist_checkbox.setChecked(False)
        )

        self.large_playlist_checkbox.toggled.connect(
            lambda checked: checked and self.playlist_checkbox.setChecked(False)
        )

        checkbox_layout.addWidget(self.playlist_checkbox)
        checkbox_layout.addWidget(self.large_playlist_checkbox)

        checkbox_layout.addStretch()  # pushes the jawns above to da left - only 1 check now but i left it like this in case we add another

        content_layout.addLayout(checkbox_layout)


        # DOWNLOAD BUTTON
        self.download_btn = QPushButton("Download MP3")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(self.download_btn)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(260)
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        progress_wrap = QWidget()
        progress_layout = QHBoxLayout(progress_wrap)
        progress_layout.setContentsMargins(0, 0, 0, 0)  
        progress_layout.addStretch()
        progress_wrap.setFixedHeight(14)  
        progress_layout.addWidget(self.progress)
        progress_layout.addStretch()

        content_layout.addWidget(progress_wrap)


        # OUutput text box
        self.output_box = QLabel("")
        self.output_box.setFixedHeight(28)
        self.output_box.setAlignment(Qt.AlignCenter)
        self.output_box.setWordWrap(True)
        content_layout.addWidget(self.output_box)
        content_layout.addSpacing(8)
        self.output_box.setObjectName("outputBox")

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(20)  # space between links

        footer_layout.addStretch()

        discord_link = QLabel(
            '<a style="color:#D9D9C3;" href="https://discord.gg/WMTvJRDKw2">'
            'Discord</a>'
        )
        discord_link.setOpenExternalLinks(True)
        discord_link.setCursor(Qt.PointingHandCursor)

        docs_link = QLabel(
            '<a style="color:#D9D9C3;" href="http://raw.githubusercontent.com/becksosa/crateplug/main/crateplug%20user%20manual.pdf">'
            'User Manual</a>'
        )
        docs_link.setOpenExternalLinks(True)
        docs_link.setCursor(Qt.PointingHandCursor)

        footer_layout.addWidget(discord_link)
        footer_layout.addWidget(docs_link)

        footer_layout.addStretch()

        main.addWidget(footer)



        main.addStretch()


#browse for and open file picker window
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.path_input.setText(folder)
            self.settings.setValue("download_folder", folder)

#trigget download when button clicked
    #get url and output dir
    def start_download(self):
        if self.is_downloading:
            return
        
        url = self.url_input.text().strip()
        output_dir = self.path_input.text().strip()


        if not url or not output_dir:
            return

        valid, error = self.is_valid_download_path(output_dir)
        if not valid:
            self.output_box.clear()
            self.append_output(f"invalid download path: {error}")
            return



        if not self.is_valid_youtube_url(url):
            self.output_box.clear()
            self.append_output("invalid url")
            return
            self.output_box.clear()

        # UI state
        self.is_downloading = True
        self.download_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate mode

        # Start worker - for separate dl
        if self.large_playlist_checkbox.isChecked():
            mode = "large_playlist"
        elif self.playlist_checkbox.isChecked():
            mode = "playlist"
        else:
            mode = "single"

        self.worker = DownloadWorker(
            url,
            output_dir,
            mode,
        )

        self.worker.finished.connect(self.download_finished)
        self.worker.error.connect(self.download_error)
        self.worker.status.connect(self.append_output)
        self.worker.start()
#signal for finished
    def download_finished(self):
        self.is_downloading = False
        self.progress.setRange(0, 1)
        self.progress.setVisible(False)
        self.download_btn.setEnabled(True)
# signal for error
    def download_error(self, message):
        print("Error:", message)
        self.is_downloading = False
        self.download_finished()

    def apply_style(self):
        bg_path = resource_path("bg.jpg").replace("\\", "/")
        self.setStyleSheet(f"""


#root {{
    background-image: url({bg_path});
    border: 1px solid #3e3e3e;
}}


#container {{
    background-color: {YOUTUBE_BG};
    border: 2px solid {BORDER_COLOR};    
    border-radius: 6px;
}}

#browseButton {{
    background-color: {YOUTUBE_SURFACE};
    border: 1px solid {BORDER_COLOR};
    color: {BORDER_COLOR};
}}


QLineEdit {{
    background-color: {YOUTUBE_SURFACE};
    border: 1px solid {BORDER_COLOR};
    color: #000000;
    padding: 8px;
    border-radius: 2px;
}}

QLineEdit:focus {{
    border: 1px solid {DLBUTT};
}}

QPushButton {{
    background-color: {DLBUTT};
    border: 1px solid #000000;
    color: #000000;
    color: #ffffff;   
    font-size: 13px;   
    font-weight: bold;   
    padding: 10px;
    border-radius: 2px;
}}

QToolButton {{
    background-color: #D4D4D4;
    border: none;
    border-radius: 3px;
}}

QToolButton:hover {{
    background-color: #A1A1A1;
}}

QCheckBox {{
    color: #000000;
}}

QProgressBar {{
    background-color: {YOUTUBE_SURFACE};
    border-radius: 6px;
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: {YOUTUBE_RED};
    border-radius: 6px;
}}

#outputBox {{
    background-color: transparent;
    color: #000000;
    font-size: 9pt;
}}


""")


if __name__ == "__main__":
    APP_ID = "com.crateplug.downloader"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv) #start gui engine
    app.setApplicationName("crateplug")
    app.setApplicationDisplayName("crateplug")
    app.setWindowIcon(QIcon(resource_path("icon.ico")))

    app.setFont(QFont("IBM Plex Sans", 10))

    window = DownloaderGUI() #create window
    window.setWindowIcon(QIcon(resource_path("icon.ico")))
    window.show() #show dat mf
    sys.exit(app.exec()) #close that mf cleanly when its done
