import tkinter as tk
from tkinter import filedialog, Menu, PhotoImage
import tkinter.ttk as ttk  # Import ttk for Combobox
import vlc
import yt_dlp
import time
import logging
import sys

class VideoPlayer:
    def __init__(self, root):
        # Initialize the logger
        self.setup_logger()

        self.root = root
        self.root.title("Video Player")
        self.root.geometry("800x600")

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

        # Video frame for embedding video in Tkinter
        self.video_frame = tk.Canvas(self.root, bg='black')
        self.video_frame.pack(fill=tk.BOTH, expand=1)

        # Video position slider frame
        self.slider_frame = tk.Frame(self.root)
        self.slider_frame.pack(fill=tk.X, padx=10, pady=5)

        # Position slider
        self.video_slider = tk.Scale(self.slider_frame, from_=0, to=100, orient="horizontal",
                                     command=self.on_slider_release)
        self.video_slider.pack(side=tk.LEFT, fill=tk.X, expand=1)

        # Timestamp label
        self.timestamp_label = tk.Label(self.slider_frame, text="00:00/00:00")
        self.timestamp_label.pack(side=tk.RIGHT)

        # Control buttons frame
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

        # Handling application close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Update slider and timestamp
        self.update_slider()

        # Mute state
        self.is_muted = False

    def setup_logger(self):
        # Create a logger
        logging.basicConfig(filename="video_player.log",
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            level=logging.DEBUG)

        # Redirect stdout and stderr to the logger
        sys.stdout = LoggerWriter(logging.info)
        sys.stderr = LoggerWriter(logging.error)

        # Override the exception hook
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        logging.critical("Uncaught exception",
                         exc_info=(exc_type, exc_value, exc_traceback))

    def open_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.play_local_video(file_path)

    def play_local_video(self, path):
        try:
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.player.set_hwnd(self.video_frame.winfo_id())  # Embed in canvas
            self.player.play()
        except Exception as e:
            logging.error(f"Error playing local video: {e}")

    def play_youtube_video(self, event=None):
        url = self.url_entry.get()
        if url:
            try:
                # Use yt-dlp to extract video information
                ydl_opts = {'format': 'best'}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    video_url = info_dict['url']

                # Play the extracted video URL with VLC
                media = self.instance.media_new(video_url)
                self.player.set_media(media)
                self.player.set_hwnd(self.video_frame.winfo_id())  # Embed in canvas
                self.player.play()

            except Exception as e:
                logging.error(f"Error playing YouTube video: {e}")

    def stop_video(self):
        self.player.stop()

    def pause_video(self):
        self.player.pause()

    def play_video(self):
        self.player.play()

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

    def set_volume(self, val):
        if not self.is_muted:
            try:
                volume = int(float(val))
                self.player.audio_set_volume(volume)
            except Exception as e:
                logging.error(f"Error setting volume: {e}")

    def toggle_mute(self):
        try:
            if self.is_muted:
                self.player.audio_set_mute(False)
                self.mute_button.config(image=self.volume_icon)
                self.is_muted = False
                # Restore the volume
                self.set_volume(self.volume_slider.get())
            else:
                self.player.audio_set_mute(True)
                self.mute_button.config(image=self.mute_icon)
                self.is_muted = True
        except Exception as e:
            logging.error(f"Error toggling mute: {e}")

    def update_slider(self):
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
        except Exception as e:
            logging.error(f"Error updating slider: {e}")

        # Update every second
        self.root.after(1000, self.update_slider)

    def format_time(self, seconds):
        return time.strftime("%H:%M:%S", time.gmtime(seconds))

    def change_speed(self, event):
        try:
            # Extract the speed multiplier from the dropdown text (e.g., '0.5x' -> 0.5)
            speed = float(self.speed_var.get().replace('x', ''))
            self.player.set_rate(speed)
        except Exception as e:
            logging.error(f"Error changing playback speed: {e}")

    def on_closing(self):
        try:
            # Explicitly delete images to avoid __del__ errors
            del self.rewind_icon
            del self.stop_icon
            del self.play_icon
            del self.pause_icon
            del self.fast_forward_icon
            del self.volume_icon
            del self.mute_icon

            # Stop the player before closing the app
            self.player.stop()

            # Destroy the main window
            self.root.destroy()
        except Exception as e:
            logging.error(f"Error on closing application: {e}")


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
