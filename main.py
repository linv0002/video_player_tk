import tkinter as tk
from tkinter import filedialog, Menu, PhotoImage, messagebox
import tkinter.ttk as ttk
import vlc
import yt_dlp
import time
import logging
import sys
import os
from PIL import ImageGrab
import json
import hashlib
import threading
from googleapiclient.discovery import build
import credentials

class VideoPlayer:
    def __init__(self, root):
        # Initialize the logger
        self.setup_logger()

        self.root = root
        self.root.title("Video Player")
        self.root.geometry("800x600")

        # set youtube api key
        self.youtube_api_key = credentials.youTubeKey
        self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)

        self.search_type_var = tk.StringVar(value="video")
        self.number_of_videos_var = tk.IntVar(value=10)

        # Initialize cache warning elements to None
        self.cache_warning_frame = None
        self.cache_warning_label = None
        self.clear_cache_button = None

        # Initialize attributes that will be used in load_config
        self.playlist_width = 300  # Width of the playlist panel
        self.min_width = 800  # Minimum width for the window without playlist
        self.playlist_dir = os.path.join(os.getcwd(), "playlists")  # Default playlist directory
        self.last_opened_dir = os.path.expanduser("~")  # Default to home directory initially
        self.cache_dir = os.path.join(os.getcwd(), "cache")  # Cache directory

        self.screenshot_dir = None  # To store the screenshot path from the config
        # Load configurations from config.json
        self.load_config()

        self.playlist_width = 300  # Width of the playlist panel
        self.min_width = 800  # Minimum width for the window without playlist
        self.playlist_dir = os.path.join(os.getcwd(), "playlists")  # Default playlist directory
        self.last_opened_dir = os.path.expanduser("~")  # Default to home directory initially
        self.cache_dir = os.path.join(os.getcwd(), "cache")  # Cache directory

        # Create playlist and cache directories if they don't exist
        if not os.path.exists(self.playlist_dir):
            os.makedirs(self.playlist_dir)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        # VLC player instance
        self.instance = vlc.Instance('--no-video-title-show', '--vout=opengl', '--quiet')
        self.player = self.instance.media_player_new()

        # Create a menu bar
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Local File", command=self.open_file)

        # Main Video and Playlist Frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=1)

        # Video Frame
        self.video_frame = tk.Frame(self.main_frame)
        self.video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        self.canvas = tk.Canvas(self.video_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=1)

        # Video position slider frame
        self.slider_frame = tk.Frame(self.video_frame)
        self.slider_frame.pack(fill=tk.X, padx=10, pady=5)

        # Position slider
        self.video_slider = tk.Scale(self.slider_frame, from_=0, to=100, orient="horizontal",
                                     command=self.on_slider_release)
        self.video_slider.pack(side=tk.LEFT, fill=tk.X, expand=1)

        # Timestamp label
        self.timestamp_label = tk.Label(self.slider_frame, text="00:00/00:00")
        self.timestamp_label.pack(side=tk.RIGHT)

        # Controls Frame
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(pady=10, fill=tk.X)

        # Left frame for play controls
        self.left_control_frame = tk.Frame(self.control_frame)
        self.left_control_frame.pack(side=tk.LEFT)

        # Right frame for mute and volume controls
        self.right_control_frame = tk.Frame(self.control_frame)
        self.right_control_frame.pack(side=tk.RIGHT)

        # Load icons and keep strong references to prevent garbage collection
        self.rewind_icon = PhotoImage(file="rewind.png")
        self.stop_icon = PhotoImage(file="stop.png")
        self.play_icon = PhotoImage(file="play.png")
        self.pause_icon = PhotoImage(file="pause.png")
        self.fast_forward_icon = PhotoImage(file="fast_forward.png")
        self.volume_icon = PhotoImage(file="volume.png")
        self.mute_icon = PhotoImage(file="mute.png")

        # Play, pause, stop, fast forward, rewind buttons with icons
        self.rewind_button = tk.Button(self.left_control_frame, image=self.rewind_icon,
                                       command=lambda: self.seek_video(-10))
        self.rewind_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.left_control_frame, image=self.stop_icon, command=self.stop_video)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.play_button = tk.Button(self.left_control_frame, image=self.play_icon, command=self.play_video)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.pause_button = tk.Button(self.left_control_frame, image=self.pause_icon, command=self.pause_video)
        self.pause_button.pack(side=tk.LEFT, padx=5)

        self.fast_forward_button = tk.Button(self.left_control_frame, image=self.fast_forward_icon,
                                             command=lambda: self.seek_video(10))
        self.fast_forward_button.pack(side=tk.LEFT, padx=5)

        # Playback Speed Control (Dropdown)
        self.speed_label = tk.Label(self.control_frame, text="Speed:")
        self.speed_label.pack(side=tk.LEFT, padx=(5, 0))

        self.speed_var = tk.StringVar()
        self.speed_dropdown = ttk.Combobox(self.control_frame, textvariable=self.speed_var, state="readonly")
        self.speed_dropdown['values'] = ('0.5x', '0.75x', '1x', '1.25x', '1.5x', '2x')
        self.speed_dropdown.current(2)  # Default to 1x speed
        self.speed_dropdown.pack(side=tk.LEFT, padx=(0, 5))
        self.speed_dropdown.bind("<<ComboboxSelected>>", self.change_speed)

        # Mute/Unmute button on the far right
        self.mute_button = tk.Button(self.right_control_frame, image=self.volume_icon, command=self.toggle_mute)
        self.mute_button.pack(side=tk.LEFT, padx=5)

        # Volume control slider to the right of the mute button
        self.volume_slider = tk.Scale(self.right_control_frame, from_=0, to=100, orient="horizontal",
                                      command=self.set_volume)
        self.volume_slider.set(50)  # Set initial volume to 50%
        self.volume_slider.pack(side=tk.LEFT, padx=5)

        # YouTube URL entry bar (on its own line)
        self.url_frame = tk.Frame(self.root)
        self.url_frame.pack(fill=tk.X, padx=10, pady=5)
        url_label = tk.Label(self.url_frame, text="YouTube URL:")
        url_label.pack(side=tk.LEFT)
        self.url_entry = tk.Entry(self.url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=1)
        self.url_entry.bind("<Return>", self.play_youtube_video)

        # search button
        self.search_icon = PhotoImage(file="search_icon.png")  # Load your search icon image
        self.search_button = tk.Button(self.url_frame, image=self.search_icon, command=self.open_search_window)
        self.search_button.pack(side=tk.LEFT, padx=5)  # Add a small padding for spacing

        # Cache checkbox
        self.cache_var = tk.IntVar(value=1)  # Default to caching enabled
        self.cache_checkbox = tk.Checkbutton(self.url_frame, text="Cache Video", variable=self.cache_var)
        self.cache_checkbox.pack(side=tk.LEFT, padx=10)

        # Cache warning and clear button (initially hidden)
        self.cache_warning_frame = None
        self.cache_warning_label = None
        self.clear_cache_button = None

        # Playlist Frame (initially hidden)
        self.playlist_frame = tk.Frame(self.main_frame, width=self.playlist_width)

        self.playlist_scrollbar_y = tk.Scrollbar(self.playlist_frame, orient=tk.VERTICAL)
        self.playlist_scrollbar_x = tk.Scrollbar(self.playlist_frame, orient=tk.HORIZONTAL)
        self.playlist_listbox = tk.Listbox(self.playlist_frame, yscrollcommand=self.playlist_scrollbar_y.set,
                                           xscrollcommand=self.playlist_scrollbar_x.set, width=50, height=20)
        self.playlist_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.playlist_scrollbar_y.config(command=self.playlist_listbox.yview)
        self.playlist_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.playlist_scrollbar_x.config(command=self.playlist_listbox.xview)
        self.playlist_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind double-click and Enter key events to play the selected item in the playlist
        self.playlist_listbox.bind("<Double-1>", self.on_playlist_select)
        self.playlist_listbox.bind("<Return>", self.on_playlist_select)

        # Bind mouse wheel for scrolling
        self.playlist_listbox.bind("<MouseWheel>", self.scroll_playlist)

        # Playlist controls organized on separate lines
        self.playlist_control_frame = tk.Frame(self.playlist_frame)
        self.playlist_control_frame.pack(side=tk.BOTTOM)

        self.add_local_button = tk.Button(self.playlist_control_frame, text="Add Local", command=self.add_local_to_playlist)
        self.add_local_button.grid(row=0, column=0, padx=5, pady=2)

        self.add_youtube_button = tk.Button(self.playlist_control_frame, text="Add YouTube", command=self.add_youtube_to_playlist)
        self.add_youtube_button.grid(row=0, column=1, padx=5, pady=2)

        self.load_playlist_button = tk.Button(self.playlist_control_frame, text="Load Playlist",
                                              command=self.load_playlist if self.cache_var.get() == 0 else self.load_playlist_cached)
        self.load_playlist_button.grid(row=1, column=0, padx=5, pady=2)

        self.save_playlist_button = tk.Button(self.playlist_control_frame, text="Save Playlist", command=self.save_playlist)
        self.save_playlist_button.grid(row=1, column=1, padx=5, pady=2)

        self.remove_button = tk.Button(self.playlist_control_frame, text="Remove", command=self.remove_from_playlist)
        self.remove_button.grid(row=2, column=0, padx=5, pady=2)

        self.edit_playlist_button = tk.Button(self.playlist_control_frame, text="Edit Playlist", command=self.edit_playlist)
        self.edit_playlist_button.grid(row=2, column=1, padx=5, pady=2)

        self.clear_playlist_button = tk.Button(self.playlist_control_frame, text="Clear Playlist",
                                               command=self.clear_playlist)
        self.clear_playlist_button.grid(row=3, column=0, padx=5, pady=2)

        self.delete_playlist_button = tk.Button(self.playlist_control_frame, text="Delete Playlist",
                                                command=self.delete_playlist)
        self.delete_playlist_button.grid(row=3, column=1, padx=5, pady=2)

        # Checkbox to show/hide playlist
        self.show_playlist_var = tk.IntVar(value=0)
        self.show_playlist_checkbox = tk.Checkbutton(self.control_frame, text="Show Playlist",
                                                     variable=self.show_playlist_var, command=self.toggle_playlist)
        self.show_playlist_checkbox.pack(side=tk.LEFT, padx=5)

        # Handling application close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Update slider and timestamp
        self.update_slider()

        # Mute state
        self.is_muted = False

        # Playlist data
        self.playlist = []

        self.is_fullscreen = False  # Track fullscreen state
        self.stored_geometry = None  # To store window size
        self.playlist_visible = False  # To store playlist visibility state
        self.menubar = menubar  # Store the menu bar for easy restoration

        # Create a new Options menu
        self.options_menu = Menu(self.root, tearoff=0)
        menubar.add_cascade(label="Options", menu=self.options_menu)

        # Add Toggle Fullscreen to the Options menu with (F11) as a reminder
        self.options_menu.add_command(label="Toggle Fullscreen (F11)", command=self.toggle_fullscreen)

        # Bind the F11 key to toggle fullscreen
        self.root.bind("<F11>", self.toggle_fullscreen)

        # Create the screenshot directory if it doesn't exist
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

        # Add the screenshot option to the "Options" menu
        self.options_menu.add_command(label="Screenshot (F10)", command=self.capture_screenshot)

        # Bind the F10 key to capture a screenshot
        self.root.bind("<F10>", self.capture_screenshot)

        self.loop_start = None  # Stores the start time of the loop
        self.loop_end = None  # Stores the end time of the loop
        self.loop_enabled = False  # Tracks whether looping is enabled

        # Manually track the positions of the loop-related menu items
        self.loop_start_index = self.options_menu.index("end") + 1  # Store the next available index
        self.options_menu.add_command(label="Set Loop Start", command=self.set_loop_start)

        self.loop_end_index = self.options_menu.index("end") + 1  # Track the next index
        self.options_menu.add_command(label="Set Loop End", command=self.set_loop_end)

        self.toggle_loop_index = self.options_menu.index("end") + 1  # Track the next index
        self.options_menu.add_command(label="Toggle Loop (off)", command=self.toggle_loop)

        # Check cache size on startup
        self.check_cache_size()  # Ensure this is called to check cache size immediately

    def setup_logger(self):
        # Create a logger
        log_file = "video_player.log"

        # Set up the file handler with write mode ('w')
        handler = logging.FileHandler(log_file, mode='w')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        # Add the handler to the root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Redirect stdout and stderr to the logger
        sys.stdout = LoggerWriter(logger.info)
        sys.stderr = LoggerWriter(logger.error)

        # Override the exception hook
        sys.excepthook = self.handle_exception

    def format_loop_time(self, time_in_seconds):
        """Helper function to format time in mm:ss."""
        mins, secs = divmod(int(time_in_seconds), 60)
        return f"{mins}:{secs:02d}"

    def set_loop_start(self):
        """Set the start point of the loop."""
        self.loop_start = self.player.get_time() / 1000  # Get current time in seconds
        logging.info(f"Loop start set at {self.loop_start} seconds")
        self.update_menu_labels()

    def set_loop_end(self):
        """Set the end point of the loop."""
        self.loop_end = self.player.get_time() / 1000  # Get current time in seconds
        logging.info(f"Loop end set at {self.loop_end} seconds")
        self.update_menu_labels()

    def toggle_loop(self):
        """Enable or disable video looping."""
        self.loop_enabled = not self.loop_enabled
        logging.info(f"Looping {'enabled' if self.loop_enabled else 'disabled'}")
        self.update_menu_labels()

    def update_menu_labels(self):
        """Update the labels of the loop menu items to show current start, end times and loop status."""
        # Update Loop Start menu item
        if self.loop_start is not None:
            start_time_str = self.format_loop_time(self.loop_start)
            self.options_menu.entryconfig(self.loop_start_index, label=f"Set Loop Start ({start_time_str})")
        else:
            self.options_menu.entryconfig(self.loop_start_index, label="Set Loop Start")

        # Update Loop End menu item
        if self.loop_end is not None:
            end_time_str = self.format_loop_time(self.loop_end)
            self.options_menu.entryconfig(self.loop_end_index, label=f"Set Loop End ({end_time_str})")
        else:
            self.options_menu.entryconfig(self.loop_end_index, label="Set Loop End")

        # Update Toggle Loop menu item
        loop_state = "on" if self.loop_enabled else "off"
        self.options_menu.entryconfig(self.toggle_loop_index, label=f"Toggle Loop ({loop_state})")

    def capture_screenshot(self, event=None):
        """Capture a screenshot of the video canvas."""
        try:
            # Define the screenshot file name
            screenshot_name = f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
            screenshot_path = os.path.join(self.screenshot_dir, screenshot_name)

            # Get the canvas (video area) position and dimensions
            x0 = self.canvas.winfo_rootx()
            y0 = self.canvas.winfo_rooty()
            x1 = x0 + self.canvas.winfo_width()
            y1 = y0 + self.canvas.winfo_height()

            # Capture the canvas (video screen) using ImageGrab
            ImageGrab.grab(bbox=(x0, y0, x1, y1)).save(screenshot_path)

            logging.info(f"Screenshot saved at {screenshot_path}")

        except Exception as e:
            logging.error(f"Error capturing screenshot: {e}")

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen  # Toggle state

        if self.is_fullscreen:
            # Store the current window geometry before going fullscreen
            self.stored_geometry = self.root.geometry()

            # Store playlist visibility state
            self.playlist_visible = self.show_playlist_var.get()

            # Remove the menu bar
            self.root.config(menu="")

            # Hide controls, YouTube URL, cache warning, and playlist
            self.control_frame.pack_forget()  # Hide controls frame
            self.slider_frame.pack_forget()  # Hide slider frame
            self.url_frame.pack_forget()  # Hide YouTube URL entry frame
            if self.cache_warning_frame:
                self.cache_warning_frame.pack_forget()  # Hide cache warning frame
            if self.playlist_visible:
                self.playlist_frame.pack_forget()  # Hide playlist if visible

            # Make the canvas take up the full screen
            self.canvas.pack(fill=tk.BOTH, expand=1)  # Canvas fills the entire window
            self.root.attributes("-fullscreen", True)

        else:
            # Exit fullscreen and restore original window geometry and visibility settings
            self.root.attributes("-fullscreen", False)

            # Restore the menu bar
            self.root.config(menu=self.menubar)

            # Restore the window geometry to its previous size
            if self.stored_geometry:
                self.root.geometry(self.stored_geometry)

            # Restore controls, YouTube URL, cache warning, and playlist
            self.canvas.pack_forget()  # Remove fullscreen canvas
            self.canvas.pack(fill=tk.BOTH, expand=1)  # Repack canvas to normal
            self.slider_frame.pack(fill=tk.X, padx=10, pady=5)  # Show slider
            self.control_frame.pack(pady=10, fill=tk.X)  # Show controls
            self.url_frame.pack(fill=tk.X, padx=10, pady=5)  # Show YouTube URL entry frame
            if self.cache_warning_frame:
                self.cache_warning_frame.pack(fill=tk.X, padx=10, pady=5)  # Show cache warning frame
            if self.playlist_visible:
                self.playlist_frame.pack(side=tk.RIGHT, fill=tk.Y)  # Show playlist if it was visible

    def load_config(self):
        """Load configuration from config.json."""
        try:
            config_path = os.path.abspath("config.json")
            with open(config_path, "r") as f:
                config = json.load(f)
                self.default_playlist_path = config.get("default_playlist_path", self.playlist_dir)
                self.screenshot_dir = config.get("default_screenshot_path", "screenshots")
                self.max_cache_size_mb = config.get("max_cache_size_mb", 500)
        except FileNotFoundError:
            logging.error("Config file not found, using default values.")
            self.screenshot_dir = "screenshots"
        except Exception as e:
            logging.error(f"Unexpected error loading config: {e}")
            self.screenshot_dir = "screenshots"

        except FileNotFoundError:
            logging.error(f"Config file not found: {config_path}, using default values.")
            self.max_cache_size_mb = 500
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from config file: {e}, using default values.")
            self.max_cache_size_mb = 500
        except Exception as e:
            logging.error(f"Unexpected error loading config: {e}, using default values.")
            self.max_cache_size_mb = 500

    def check_cache_size(self):
        """Check the cache size and display a warning if it exceeds the max size."""
        cache_size_mb = self.get_cache_size_mb()
        logging.info(f"Current cache size: {cache_size_mb:.2f} MB")

        # Debugging: Print the values being compared
        print(f"Max cache size (from config): {self.max_cache_size_mb} MB")
        print(f"Current cache size: {cache_size_mb} MB")

        # Correct comparison to check if cache size exceeds the limit
        if cache_size_mb > self.max_cache_size_mb:
            self.show_cache_warning(cache_size_mb)
        else:
            # If the cache size is within limits, remove the warning if it exists
            self.remove_cache_warning()

    def get_cache_size_mb(self):
        """Calculate the total cache size in MB."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)

    def show_cache_warning(self, cache_size_mb):
        """Display a warning about the cache size and add a button to clear the cache."""
        if not self.cache_warning_frame:
            self.cache_warning_frame = tk.Frame(self.root)
            self.cache_warning_frame.pack(fill=tk.X, padx=10, pady=5)

            self.cache_warning_label = tk.Label(self.cache_warning_frame,
                                                text=f"Cache Warning: Current cache size is {cache_size_mb:.2f} MB.")
            self.cache_warning_label.pack(side=tk.LEFT)

            self.clear_cache_button = tk.Button(self.cache_warning_frame, text="Clear Cache", command=self.clear_cache)
            self.clear_cache_button.pack(side=tk.LEFT, padx=10)

    def clear_cache(self):
        """Clear the cache directory and remove the warning."""
        try:
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)
            logging.info("Cache cleared.")
            self.remove_cache_warning()
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")

    def remove_cache_warning(self):
        """Remove the cache warning and clear cache button."""
        if self.cache_warning_frame:
            self.cache_warning_frame.destroy()
            self.cache_warning_frame = None
            self.cache_warning_label = None
            self.clear_cache_button = None

            # No need to manually adjust the window size
            # self.root.update_idletasks() # Optional: Force update of the layout to reflect the removed widgets

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        logging.critical("Uncaught exception",
                         exc_info=(exc_type, exc_value, exc_traceback))

    def open_file(self):
        file_path = filedialog.askopenfilename(initialdir=self.last_opened_dir)
        if file_path:
            self.play_local_video(file_path)
            self.add_to_playlist(file_path, "")  # Automatically add to playlist with empty description
            self.last_opened_dir = os.path.dirname(file_path)

    def play_local_video(self, path):
        try:
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.player.set_hwnd(self.canvas.winfo_id())  # Embed in canvas
            self.player.play()
        except Exception as e:
            logging.error(f"Error playing local video: {e}")

    def play_video(self):
        self.player.play()

    def pause_video(self):
        self.player.pause()

    def stop_video(self):
        self.player.stop()

    def seek_video(self, seconds):
        try:
            current_time = self.player.get_time() / 1000
            new_time = current_time + seconds
            self.player.set_time(int(new_time * 1000))
        except Exception as e:
            logging.error(f"Error seeking video: {e}")

    def set_position(self, val):
        try:
            position = float(val) / 100
            self.player.set_position(position)
        except Exception as e:
            logging.error(f"Error setting video position: {e}")

    def on_slider_release(self, val):
        self.set_position(val)
        self.player.play()

    def format_time(self, seconds):
        return time.strftime("%H:%M:%S", time.gmtime(seconds))

    def change_speed(self, event):
        try:
            # Extract the speed multiplier from the dropdown text (e.g., '0.5x' -> 0.5)
            speed = float(self.speed_var.get().replace('x', ''))
            self.player.set_rate(speed)
        except Exception as e:
            logging.error(f"Error changing playback speed: {e}")

    def toggle_mute(self):
        if self.is_muted:
            self.player.audio_set_mute(False)
            self.mute_button.config(image=self.volume_icon)
            self.is_muted = False
        else:
            self.player.audio_set_mute(True)
            self.mute_button.config(image=self.mute_icon)
            self.is_muted = True

    def set_volume(self, val):
        if not self.is_muted:
            volume = int(float(val))
            self.player.audio_set_volume(volume)

    def scroll_playlist(self, event):
        if event.delta:
            self.playlist_listbox.yview_scroll(int(-1*(event.delta/120)), "units")
        else:
            self.playlist_listbox.yview_scroll(int(event.num == 5) - int(event.num == 4), "units")

    def toggle_playlist(self):
        if self.show_playlist_var.get():
            self.playlist_frame.pack(side=tk.RIGHT, fill=tk.Y)
            new_width = self.min_width + self.playlist_width
        else:
            self.playlist_frame.pack_forget()
            new_width = self.min_width

        # Repack the main frame and controls frame in the correct order
        self.root.geometry(f"{new_width}x{self.root.winfo_height()}")
        self.main_frame.pack(fill=tk.BOTH, expand=1)
        self.control_frame.pack(pady=10, fill=tk.X)

    def play_youtube_video(self, event=None):
        if self.cache_var.get() == 1:
            self.play_youtube_video_cached(event)
        else:
            self.play_youtube_video_noncached(event)

    def play_youtube_video_noncached(self, event=None):
        url = self.url_entry.get()
        if url:
            try:
                ydl_opts = {'extract_flat': False, 'force_generic_extractor': False}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)

                    if 'entries' in info_dict:
                        # It's a playlist, add all videos to the existing playlist
                        initial_playlist_size = self.playlist_listbox.size()

                        for entry in info_dict['entries']:
                            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                            video_title = entry['title']

                            # Check if the video is cached
                            video_hash = hashlib.md5(video_url.encode()).hexdigest()
                            cache_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")

                            if os.path.exists(cache_path):
                                # If cached, play from cache
                                logging.info(f"Playing cached video: {cache_path}")
                                self.add_to_playlist(cache_path, video_title)
                            else:
                                # Otherwise, add the video URL to the playlist for streaming
                                self.add_to_playlist(video_url, video_title)

                        # Automatically play the first video from the newly added playlist
                        self.playlist_listbox.selection_clear(0, tk.END)  # Clear any previous selection
                        self.playlist_listbox.selection_set(initial_playlist_size)  # Select the first newly added item
                        self.playlist_listbox.activate(initial_playlist_size)
                        self.play_selected_item_noncached()  # Play the selected item

                    else:
                        # It's a single video, check if it's cached
                        video_hash = hashlib.md5(url.encode()).hexdigest()
                        cache_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")

                        if os.path.exists(cache_path):
                            # If cached, play from cache
                            logging.info(f"Playing cached video: {cache_path}")
                            self.play_local_video(cache_path)
                        else:
                            # Otherwise, stream it directly
                            video_url = info_dict['url']
                            media = self.instance.media_new(video_url)
                            self.player.set_media(media)
                            self.player.set_hwnd(self.canvas.winfo_id())  # Embed in canvas
                            self.player.play()

                        # Add to playlist only if played from URL entry
                        if event:
                            self.add_to_playlist(url, info_dict.get('title', ''))

            except Exception as e:
                logging.error(f"Error playing YouTube video: {e}")

    def play_youtube_video_cached(self, event=None):
        url = self.url_entry.get()
        if url:
            try:
                ydl_opts = {
                    'extract_flat': True,  # Only extract metadata, not actual video
                    'force_generic_extractor': False
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)

                    if 'entries' in info_dict:
                        # It's a playlist
                        initial_playlist_size = self.playlist_listbox.size()
                        first_video_played = False

                        for i, entry in enumerate(info_dict['entries']):
                            # Ensure only video entries are processed
                            if entry.get('_type') == 'url':
                                video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                                video_title = entry['title']
                                video_hash = hashlib.md5(video_url.encode()).hexdigest()
                                cache_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")

                                # Always add to the application's playlist
                                self.add_to_playlist(video_url, video_title)

                                if i == 0:
                                    # Check if the first video is cached and play it immediately
                                    if os.path.exists(cache_path):
                                        logging.info(f"Playing cached video: {cache_path}")
                                        self.play_local_video(cache_path)
                                        first_video_played = True
                                    else:
                                        logging.info(f"Downloading first video: {video_url}")
                                        self.download_and_play_first_video(video_url, cache_path)
                                else:
                                    # For subsequent videos, download if not cached
                                    if not os.path.exists(cache_path):
                                        threading.Thread(target=self.download_video,
                                                         args=(video_url, cache_path)).start()

                        if first_video_played:
                            return

                    else:
                        # Single video handling
                        video_hash = hashlib.md5(url.encode()).hexdigest()
                        cache_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")

                        if os.path.exists(cache_path):
                            logging.info(f"Playing cached single video: {cache_path}")
                            self.play_local_video(cache_path)
                        else:
                            self.download_and_play_first_video(url, cache_path)

                        # Ensure single video is added to playlist
                        video_title = info_dict.get('title', url)
                        self.add_to_playlist(url, video_title)

            except Exception as e:
                logging.error(f"Error playing YouTube video: {e}")

    def download_and_play_first_video(self, video_url, cache_path):
        """Download the first video and play it immediately if not cached, otherwise play from cache."""
        try:
            if os.path.exists(cache_path):
                logging.info(f"Playing cached video: {cache_path}")
                self.play_local_video(cache_path)
            else:
                logging.info(f"Downloading video: {video_url}")
                ydl_opts_video = {'format': 'best', 'outtmpl': cache_path}

                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl_video:
                    ydl_video.download([video_url])

                self.play_local_video(cache_path)

        except Exception as e:
            logging.error(f"Error downloading or playing the first video: {e}")
            messagebox.showerror("Error", "Failed to download or play video.")

    def download_video(self, video_url, cache_path):
        """Download subsequent videos to the cache directory in the background."""
        try:
            if not os.path.exists(cache_path):
                logging.info(f"Downloading video in background: {video_url}")
                ydl_opts_video = {'format': 'best', 'outtmpl': cache_path}

                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl_video:
                    ydl_video.download([video_url])
                    logging.info(f"Background video download completed: {video_url}")
            else:
                logging.info(f"Video already in cache: {cache_path}")

        except Exception as e:
            logging.error(f"Error downloading video in background: {e}")

    def get_cached_video_path(self, url):
        """Return the path to the cached video if it exists, else None."""
        video_hash = hashlib.md5(url.encode()).hexdigest()
        cached_video_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")
        return cached_video_path if os.path.exists(cached_video_path) else None

    def add_local_to_playlist(self):
        file_path = filedialog.askopenfilename(initialdir=self.last_opened_dir)
        if file_path:
            self.add_to_playlist(file_path, "")
            self.last_opened_dir = os.path.dirname(file_path)

    def add_youtube_to_playlist(self):
        url = self.url_entry.get()
        if url:
            self.add_to_playlist(url, "")

    def add_to_playlist(self, url, description):
        # Check for duplicates
        if not any(item["url"] == url for item in self.playlist):
            self.playlist.append({"url": url, "description": description})
            display_text = description if description else url
            self.playlist_listbox.insert(tk.END, display_text)

    def load_playlist(self):
        playlist_file = filedialog.askopenfilename(initialdir=self.playlist_dir,
                                                   title="Select Playlist",
                                                   filetypes=(("JSON Files", "*.json"), ("All Files", "*.*")))
        if playlist_file:
            with open(playlist_file, 'r') as file:
                self.playlist = json.load(file)
                self.playlist_listbox.delete(0, tk.END)
                for item in self.playlist:
                    display_text = item["description"] if item["description"] else item["url"]
                    self.playlist_listbox.insert(tk.END, display_text)

                # Automatically play the first video in the playlist if it exists
                if self.playlist:
                    self.playlist_listbox.selection_set(0)  # Select the first item
                    self.playlist_listbox.activate(0)
                    self.play_selected_item_noncached()  # Play the first video using non-cached logic

    def load_playlist_cached(self):
        playlist_file = filedialog.askopenfilename(initialdir=self.playlist_dir,
                                                   title="Select Playlist",
                                                   filetypes=(("JSON Files", "*.json"), ("All Files", "*.*")))
        if playlist_file:
            with open(playlist_file, 'r') as file:
                self.playlist = json.load(file)
                self.playlist_listbox.delete(0, tk.END)
                for item in self.playlist:
                    display_text = item["description"] if item["description"] else item["url"]
                    self.playlist_listbox.insert(tk.END, display_text)

                # Automatically play the first video in the playlist if it exists
                if self.playlist:
                    self.playlist_listbox.selection_set(0)  # Select the first item
                    self.playlist_listbox.activate(0)
                    self.play_selected_item_cached()  # Play the selected item

    def save_playlist(self):
        playlist_file = filedialog.asksaveasfilename(initialdir=self.playlist_dir,
                                                     title="Save Playlist",
                                                     defaultextension=".json",
                                                     filetypes=(("JSON Files", "*.json"), ("All Files", "*.*")))
        if playlist_file:
            with open(playlist_file, 'w') as file:
                json.dump(self.playlist, file, indent=4)

    def clear_playlist(self):
        self.playlist_listbox.delete(0, tk.END)  # Clear the listbox
        self.playlist = []  # Clear the underlying playlist list

    def delete_playlist(self):
        playlist_file = filedialog.askopenfilename(initialdir=self.playlist_dir,
                                                   title="Delete Playlist",
                                                   filetypes=(("JSON Files", "*.json"), ("All Files", "*.*")))
        if playlist_file:
            try:
                os.remove(playlist_file)
                messagebox.showinfo("Deleted", "Playlist deleted successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete playlist: {e}")

    def remove_from_playlist(self):
        selected = self.playlist_listbox.curselection()
        if selected:
            del self.playlist[selected[0]]
            self.playlist_listbox.delete(selected)

    def play_selected_item_noncached(self, event=None):
        selected_index = self.playlist_listbox.curselection()
        if selected_index:
            selected_item = self.playlist[selected_index[0]]
            url = selected_item["url"]

            # Check if the video is in the cache
            video_path = self.get_cached_video_path(url)
            if video_path:
                # Play from cache
                self.play_local_video(video_path)
            else:
                # Stream the video if not in the cache
                if url.startswith("http"):
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, url)
                    self.stream_video(url)  # Stream the video directly
                else:
                    self.play_local_video(url)

    def stream_video(self, url):
        try:
            ydl_opts = {'extract_flat': False, 'force_generic_extractor': False}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_url = info_dict['url']
                media = self.instance.media_new(video_url)
                self.player.set_media(media)
                self.player.set_hwnd(self.canvas.winfo_id())  # Embed in canvas
                self.player.play()
        except Exception as e:
            logging.error(f"Error streaming video: {e}")

    def play_selected_item_cached(self, event=None):
        selected_index = self.playlist_listbox.curselection()
        if selected_index:
            selected_item = self.playlist[selected_index[0]]
            url = selected_item["url"]

            if url.startswith("http"):  # It's a YouTube video
                video_hash = hashlib.md5(url.encode()).hexdigest()
                cached_video_path = os.path.join(self.cache_dir, f"{video_hash}.mp4")

                if os.path.exists(cached_video_path):
                    logging.info(f"Playing cached video: {cached_video_path}")
                    self.play_local_video(cached_video_path)
                else:
                    logging.info(f"Video not cached, downloading: {url}")
                    # Download the video and play it
                    self.download_and_play_first_video(url, cached_video_path)
            else:
                # It's a local file, play it directly
                logging.info(f"Playing local video: {url}")
                self.play_local_video(url)

    def on_playlist_select(self, event=None):
        if self.cache_var.get():
            self.play_selected_item_cached(event)
        else:
            self.play_selected_item_noncached(event)

    def on_video_end(self):
        current_index = self.playlist_listbox.curselection()
        if current_index:
            next_index = current_index[0] + 1
            if next_index < self.playlist_listbox.size():
                self.playlist_listbox.selection_clear(0, tk.END)
                self.playlist_listbox.selection_set(next_index)
                self.playlist_listbox.activate(next_index)

                # Check if cache is enabled and play the next video accordingly
                if self.cache_var.get():
                    self.play_selected_item_cached()
                else:
                    self.play_selected_item_noncached()
            else:
                self.stop_video()  # Stop the video if no more videos in the playlist
        else:
            self.stop_video()

    def update_slider(self):
        """Update the video slider and handle looping."""
        try:
            if self.player.is_playing():
                # Update the slider without calling the command function
                self.video_slider.config(command="")
                position = self.player.get_position() * 100
                self.video_slider.set(position)
                self.video_slider.config(command=self.on_slider_release)

                # Update the timestamp
                current_time = self.player.get_time() / 1000
                total_time = self.player.get_length() / 1000
                self.timestamp_label.config(text=f"{self.format_time(current_time)}/{self.format_time(total_time)}")

                # Handle loop logic
                if self.loop_enabled and self.loop_start is not None and self.loop_end is not None:
                    if current_time >= self.loop_end:
                        logging.info(f"Looping back to {self.loop_start} seconds")
                        self.player.set_time(int(self.loop_start * 1000))  # Seek to start of loop

                # Check if the video has finished playing
                if abs(current_time - total_time) < 1:
                    self.on_video_end()

        except Exception as e:
            logging.error(f"Error updating slider: {e}")

        # Update every second
        self.root.after(1000, self.update_slider)

    def edit_playlist(self):
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Playlist")

        edit_listbox = tk.Listbox(edit_window, width=50, height=20)
        edit_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        for item in self.playlist:
            display_text = item["description"] if item["description"] else item["url"]
            edit_listbox.insert(tk.END, display_text)

        scrollbar_y = tk.Scrollbar(edit_window, orient=tk.VERTICAL, command=edit_listbox.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        edit_listbox.config(yscrollcommand=scrollbar_y.set)

        scrollbar_x = tk.Scrollbar(edit_window, orient=tk.HORIZONTAL, command=edit_listbox.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        edit_listbox.config(xscrollcommand=scrollbar_x.set)

        controls_frame = tk.Frame(edit_window)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y)

        def move_up():
            selected = edit_listbox.curselection()
            if selected:
                index = selected[0]
                if index > 0:
                    # Swap the items in the playlist list
                    self.playlist[index], self.playlist[index - 1] = self.playlist[index - 1], self.playlist[index]

                    # Refresh the listbox
                    edit_listbox.delete(0, tk.END)
                    for item in self.playlist:
                        display_text = item["description"] if item["description"] else item["url"]
                        edit_listbox.insert(tk.END, display_text)

                    # Maintain selection
                    edit_listbox.selection_set(index - 1)

        def move_down():
            selected = edit_listbox.curselection()
            if selected:
                index = selected[0]
                if index < len(self.playlist) - 1:
                    # Swap the items in the playlist list
                    self.playlist[index], self.playlist[index + 1] = self.playlist[index + 1], self.playlist[index]

                    # Refresh the listbox
                    edit_listbox.delete(0, tk.END)
                    for item in self.playlist:
                        display_text = item["description"] if item["description"] else item["url"]
                        edit_listbox.insert(tk.END, display_text)

                    # Maintain selection
                    edit_listbox.selection_set(index + 1)

        def delete_item():
            selected = edit_listbox.curselection()
            if selected:
                index = selected[0]
                del self.playlist[index]
                edit_listbox.delete(index)

        def update_description():
            selected = edit_listbox.curselection()
            if selected:
                index = selected[0]
                new_description = description_entry.get()
                self.playlist[index]["description"] = new_description

                # Update the listbox to reflect the new description
                edit_listbox.delete(index)
                display_text = new_description if new_description else self.playlist[index]["url"]
                edit_listbox.insert(index, display_text)

        move_up_button = tk.Button(controls_frame, text="Move Up", command=move_up)
        move_up_button.pack(padx=5, pady=5)

        move_down_button = tk.Button(controls_frame, text="Move Down", command=move_down)
        move_down_button.pack(padx=5, pady=5)

        delete_button = tk.Button(controls_frame, text="Delete", command=delete_item)
        delete_button.pack(padx=5, pady=5)

        description_label = tk.Label(controls_frame, text="Description:")
        description_label.pack(padx=5, pady=5)

        description_entry = tk.Entry(controls_frame)
        description_entry.pack(padx=5, pady=5)

        update_button = tk.Button(controls_frame, text="Update Description", command=update_description)
        update_button.pack(padx=5, pady=5)

        close_button = tk.Button(controls_frame, text="Close",
                                 command=lambda: [self.refresh_playlist(), edit_window.destroy()])
        close_button.pack(padx=5, pady=5)

    def refresh_playlist(self):
        """Refresh the main playlist listbox to reflect any changes."""
        self.playlist_listbox.delete(0, tk.END)
        for item in self.playlist:
            display_text = item["description"] if item["description"] else item["url"]
            self.playlist_listbox.insert(tk.END, display_text)

    def open_search_window(self):
        # Create a new top-level window for search
        search_window = tk.Toplevel(self.root)
        search_window.title("YouTube Search")
        search_window.geometry("600x600")  # Set the window size appropriately

        # Section 1: Search Label and Entry
        search_label = tk.Label(search_window, text="Search YouTube:")
        search_label.pack(anchor="w", pady=10, padx=10)

        search_entry = tk.Entry(search_window, width=50)
        search_entry.pack(pady=5, padx=10, fill=tk.X)

        # Bind the Enter key to execute the search when pressed
        search_entry.bind("<Return>", lambda event: self.search_youtube(search_entry.get(), results_listbox))

        # Search Button
        search_button = tk.Button(search_window, text="Search",
                                  command=lambda: self.search_youtube(search_entry.get(), results_listbox))
        search_button.pack(pady=5, padx=10)

        # Section 2: Favorites Dropdown
        favorites_label = tk.Label(search_window, text="Favorites:")
        favorites_label.pack(anchor="w", pady=5, padx=10)

        self.favorites_var = tk.StringVar(search_window)
        favorites_dropdown = ttk.Combobox(search_window, textvariable=self.favorites_var, state="readonly", width=50)
        self.update_favorites_dropdown(favorites_dropdown)
        favorites_dropdown.pack(pady=5, padx=10, fill=tk.X)

        # Bind the selection event to load the favorite
        favorites_dropdown.bind("<<ComboboxSelected>>",
                                lambda event: self.load_favorite(favorites_dropdown, search_entry, results_listbox))

        # Section 3: Favorites Buttons
        favorites_buttons_frame = tk.Frame(search_window)
        favorites_buttons_frame.pack(pady=5, padx=10, fill=tk.X)

        add_to_favorites_button = tk.Button(favorites_buttons_frame, text="Add to Favorites",
                                            command=lambda: self.add_to_favorites(search_entry.get()))
        add_to_favorites_button.pack(side=tk.LEFT, padx=5)

        edit_favorites_button = tk.Button(favorites_buttons_frame, text="Edit Favorites", command=self.edit_favorites)
        edit_favorites_button.pack(side=tk.LEFT, padx=5)

        # Section 4: Search Type (Video or Playlist)
        search_type_frame = tk.Frame(search_window)
        search_type_frame.pack(pady=5, padx=10, fill=tk.X)

        video_radio = tk.Radiobutton(search_type_frame, text="Videos", variable=self.search_type_var, value="video")
        playlist_radio = tk.Radiobutton(search_type_frame, text="Playlists", variable=self.search_type_var,
                                        value="playlist")

        video_radio.pack(side=tk.LEFT)
        playlist_radio.pack(side=tk.LEFT)

        # Section 5: Number of Results Dropdown
        number_of_videos_label = tk.Label(search_window, text="Number of Results:")
        number_of_videos_label.pack(anchor="w", pady=5, padx=10)

        number_of_videos_dropdown = ttk.Combobox(search_window, textvariable=self.number_of_videos_var,
                                                 state="readonly")
        number_of_videos_dropdown['values'] = (5, 10, 15, 20, 25)
        number_of_videos_dropdown.pack(pady=5, padx=10, fill=tk.X)

        # Section 6: Results Listbox with Scrollbars
        results_frame = tk.Frame(search_window)
        results_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        results_listbox = tk.Listbox(results_frame, width=80, height=15, selectmode=tk.EXTENDED)
        results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_y = tk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_listbox.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        scrollbar_x = tk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=results_listbox.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        results_listbox.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Section 7: Add to Playlist Button
        add_to_playlist_button = tk.Button(search_window, text="Add to Playlist",
                                           command=lambda: self.add_search_result_to_playlist(results_listbox))
        add_to_playlist_button.pack(pady=5, padx=10, anchor="center")

        print("Search window layout completed.")  # Debugging line to ensure the function completes

    def update_favorites_dropdown(self, dropdown):
        """Updates the favorites dropdown with the latest list of favorite searches."""
        favorites = self.load_favorites()
        favorite_titles = [f"{fav['description']} ({fav['type']})" for fav in favorites]
        dropdown['values'] = favorite_titles
        if favorite_titles:
            dropdown.current(0)  # Set the first favorite as the default selected value

    def load_favorite(self, dropdown, search_entry, results_listbox):
        """Loads the selected favorite search into the search bar and automatically executes the search."""
        selected_index = dropdown.current()
        favorites = self.load_favorites()

        if selected_index >= 0 and selected_index < len(favorites):
            selected_favorite = favorites[selected_index]

            # Load the favorite's search query into the search bar
            search_entry.delete(0, tk.END)
            search_entry.insert(0, selected_favorite['search'])

            # Set the search type (video or playlist)
            self.search_type_var.set(selected_favorite['type'])

            # Automatically execute the search
            self.search_youtube(selected_favorite['search'], results_listbox)
        else:
            print("No valid favorite selected.")

    def search_youtube(self, query, results_listbox):
        results_listbox.delete(0, tk.END)

        # Get the number of results and search type (video or playlist)
        max_results = self.number_of_videos_var.get()
        search_type = self.search_type_var.get()

        # Use the YouTube API to search for videos or playlists
        search_response = self.youtube.search().list(
            q=query,
            part='snippet',
            maxResults=max_results,
            type=search_type
        ).execute()

        search_results = []
        for item in search_response.get('items', []):
            item_id = item['id']['videoId'] if search_type == "video" else item['id']['playlistId']
            item_title = item['snippet']['title']
            item_url = f"https://www.youtube.com/{'watch?v=' if search_type == 'video' else 'playlist?list='}{item_id}"
            search_results.append({"title": item_title, "url": item_url})

        for result in search_results:
            results_listbox.insert(tk.END, f"{result['title']} ({result['url']})")

        results_listbox.results = search_results

    def is_video_downloadable(self, url):
        ydl_opts = {'quiet': True}  # Suppress output
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', None)
                if formats:
                    # Filter for formats that have both video and audio
                    downloadable_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
                    return bool(downloadable_formats)  # Return True if downloadable formats exist
        except Exception as e:
            print(f"Failed to check downloadability for {url}: {e}")
        return False

    def add_search_result_to_playlist(self, results_listbox):
        selected_indices = results_listbox.curselection()
        if selected_indices:
            for index in selected_indices:
                selected_result = results_listbox.results[index]
                if self.search_type_var.get() == "video":
                    if self.is_video_downloadable(selected_result['url']):
                        self.add_to_playlist(selected_result['url'], selected_result['title'])
                    else:
                        messagebox.showwarning("Download Error", f"'{selected_result['title']}' is not downloadable.")
                elif self.search_type_var.get() == "playlist":
                    # Directly handle the playlist URL as if it was entered in the YouTube URL box
                    self.handle_playlist_url(selected_result['url'])

    def load_favorites(self):
        """Load favorites from a JSON file."""
        try:
            with open("favorites.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_favorites(self, favorites):
        """Save favorites to a JSON file."""
        with open("favorites.json", "w") as f:
            json.dump(favorites, f, indent=4)

    def add_to_favorites(self, search_query):
        if not search_query.strip():
            messagebox.showwarning("Warning", "Search query cannot be empty.")
            return

        description = search_query  # Use the search query as the default description; can be updated in the edit window
        search_type = self.search_type_var.get()

        # Load existing favorites
        favorites = self.load_favorites()

        # Add the new favorite to the list
        favorites.append({
            "description": description,
            "search": search_query,
            "type": search_type
        })

        # Save the updated favorites
        self.save_favorites(favorites)

        messagebox.showinfo("Success", "Search added to favorites.")

    def edit_favorites(self):
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Favorites")

        # Create a temporary copy of the favorites list
        temp_favorites = self.load_favorites()

        # Create a frame to hold the grid
        grid_frame = tk.Frame(edit_window)
        grid_frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)

        # Headers
        tk.Label(grid_frame, text="Description", width=25).grid(row=0, column=0, padx=5, pady=5)
        tk.Label(grid_frame, text="Query", width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(grid_frame, text="Type", width=10).grid(row=0, column=2, padx=5, pady=5)

        # Create a list of entries for editing
        description_entries = []
        query_entries = []
        type_vars = []

        def update_temp_favorite(index):
            """Updates the temporary list based on the content of the entries."""
            new_description = description_entries[index].get()
            new_query = query_entries[index].get()
            new_type = type_vars[index].get()
            temp_favorites[index] = {"description": new_description, "search": new_query, "type": new_type}

        # Populate the grid with favorites
        for i, fav in enumerate(temp_favorites):
            # Description entry
            description_entry = tk.Entry(grid_frame, width=25)
            description_entry.grid(row=i + 1, column=0, padx=5, pady=5)
            description_entry.insert(0, fav["description"])
            description_entry.bind("<Return>", lambda event, idx=i: update_temp_favorite(idx))
            description_entries.append(description_entry)

            # Query entry
            query_entry = tk.Entry(grid_frame, width=50)
            query_entry.grid(row=i + 1, column=1, padx=5, pady=5)
            query_entry.insert(0, fav["search"])
            query_entry.bind("<Return>", lambda event, idx=i: update_temp_favorite(idx))
            query_entries.append(query_entry)

            # Type radio buttons
            type_var = tk.StringVar(value=fav["type"])
            video_radio = tk.Radiobutton(grid_frame, text="Video", variable=type_var, value="video")
            playlist_radio = tk.Radiobutton(grid_frame, text="Playlist", variable=type_var, value="playlist")
            video_radio.grid(row=i + 1, column=2, sticky="w")
            playlist_radio.grid(row=i + 1, column=2, sticky="e")
            type_vars.append(type_var)

        def save_and_close():
            # Save the temporary favorites list to the original file
            self.save_favorites(temp_favorites)
            # Update the favorites dropdown with the new list
            self.update_favorites_dropdown(self.favorites_var)
            edit_window.destroy()

        # Buttons for controlling the list
        control_frame = tk.Frame(edit_window)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        move_up_button = tk.Button(control_frame, text="Move Up",
                                   command=lambda: move_up(description_entries, query_entries, type_vars, grid_frame))
        move_up_button.pack(side=tk.LEFT, padx=5, pady=5)

        move_down_button = tk.Button(control_frame, text="Move Down",
                                     command=lambda: move_down(description_entries, query_entries, type_vars,
                                                               grid_frame))
        move_down_button.pack(side=tk.LEFT, padx=5, pady=5)

        delete_button = tk.Button(control_frame, text="Delete",
                                  command=lambda: delete_item(description_entries, query_entries, type_vars,
                                                              grid_frame))
        delete_button.pack(side=tk.LEFT, padx=5, pady=5)

        update_button = tk.Button(control_frame, text="Update",
                                  command=lambda: [update_temp_favorite(i) for i in range(len(temp_favorites))])
        update_button.pack(side=tk.LEFT, padx=5, pady=5)

        close_button = tk.Button(control_frame, text="Close", command=save_and_close)
        close_button.pack(side=tk.RIGHT, padx=5, pady=5)

        def move_up(entries_desc, entries_query, type_vars, frame):
            selected = grid_frame.focus_get().grid_info()['row'] - 1
            if selected > 0:
                temp_favorites[selected], temp_favorites[selected - 1] = temp_favorites[selected - 1], temp_favorites[
                    selected]
                update_grid(frame, entries_desc, entries_query, type_vars)

        def move_down(entries_desc, entries_query, type_vars, frame):
            selected = grid_frame.focus_get().grid_info()['row'] - 1
            if selected < len(temp_favorites) - 1:
                temp_favorites[selected], temp_favorites[selected + 1] = temp_favorites[selected + 1], temp_favorites[
                    selected]
                update_grid(frame, entries_desc, entries_query, type_vars)

        def delete_item(entries_desc, entries_query, type_vars, frame):
            selected = grid_frame.focus_get().grid_info()['row'] - 1
            del temp_favorites[selected]
            update_grid(frame, entries_desc, entries_query, type_vars)

        def update_grid(frame, entries_desc, entries_query, type_vars):
            """Repopulate the grid with updated favorites."""
            for widget in frame.winfo_children():
                widget.destroy()
            # Recreate the grid with updated data
            tk.Label(frame, text="Description", width=25).grid(row=0, column=0, padx=5, pady=5)
            tk.Label(frame, text="Query", width=50).grid(row=0, column=1, padx=5, pady=5)
            tk.Label(frame, text="Type", width=10).grid(row=0, column=2, padx=5, pady=5)

            for i, fav in enumerate(temp_favorites):
                # Description entry
                description_entry = tk.Entry(frame, width=25)
                description_entry.grid(row=i + 1, column=0, padx=5, pady=5)
                description_entry.insert(0, fav["description"])
                description_entry.bind("<Return>", lambda event, idx=i: update_temp_favorite(idx))
                description_entries[i] = description_entry

                # Query entry
                query_entry = tk.Entry(frame, width=50)
                query_entry.grid(row=i + 1, column=1, padx=5, pady=5)
                query_entry.insert(0, fav["search"])
                query_entry.bind("<Return>", lambda event, idx=i: update_temp_favorite(idx))
                query_entries[i] = query_entry

                # Type radio buttons
                type_var = tk.StringVar(value=fav["type"])
                video_radio = tk.Radiobutton(frame, text="Video", variable=type_var, value="video")
                playlist_radio = tk.Radiobutton(frame, text="Playlist", variable=type_var, value="playlist")
                video_radio.grid(row=i + 1, column=2, sticky="w")
                playlist_radio.grid(row=i + 1, column=2, sticky="e")
                type_vars[i] = type_var

        # Handle the window close event to ensure no changes are saved if the user closes the window
        edit_window.protocol("WM_DELETE_WINDOW", lambda: edit_window.destroy())

    def handle_playlist_url(self, url):
        """Handles a YouTube playlist URL by invoking the existing logic for YouTube URL input."""
        # Clear the URL entry box and insert the playlist URL
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, url)

        # Trigger the existing logic to handle this URL, respecting the cached option
        if self.cache_var.get() == 1:
            self.play_youtube_video_cached()
        else:
            self.play_youtube_video_noncached()

    def on_closing(self):
        try:
            # Stop the player before closing the app
            if self.player.is_playing():
                self.player.stop()

            # Explicitly destroy widgets that use images
            self.rewind_button.destroy()
            self.stop_button.destroy()
            self.play_button.destroy()
            self.pause_button.destroy()
            self.fast_forward_button.destroy()
            self.mute_button.destroy()

            # Remove references to icons to allow for garbage collection
            self.rewind_icon = None
            self.stop_icon = None
            self.play_icon = None
            self.pause_icon = None
            self.fast_forward_icon = None
            self.volume_icon = None
            self.mute_icon = None

            # Temporarily suppress stderr to avoid Tkinter __del__ errors
            sys.stderr = open(os.devnull, 'w')

            # Destroy the main window
            self.root.destroy()

            # Restore stderr
            sys.stderr.close()
            sys.stderr = sys.__stderr__

        except Exception as e:
            logging.error(f"Error on closing application: {e}")

        # Call the garbage collector explicitly (optional but recommended)
        import gc
        gc.collect()


class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        # Prevent writing empty lines
        if message.strip():
            self.level(message.strip())

    def flush(self):
        pass


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayer(root)
    root.mainloop()
