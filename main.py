import tkinter as tk
from tkinter import filedialog, Menu, PhotoImage, messagebox
import tkinter.ttk as ttk  # Import ttk for Combobox
import vlc
import yt_dlp
import time
import logging
import sys
import os
import json
import hashlib
import threading

class VideoPlayer:
    def __init__(self, root):
        # Initialize the logger
        self.setup_logger()

        self.root = root
        self.root.title("Video Player")
        self.root.geometry("800x600")

        self.playlist_width = 300  # Width of the playlist panel
        self.min_width = 800  # Minimum width for the window without playlist
        self.playlist_dir = os.path.join(os.getcwd(), "playlists")  # Default playlist directory
        self.cache_dir = os.path.join(os.getcwd(), "cache")  # Cache directory
        self.last_opened_dir = os.path.expanduser("~")  # Default to home directory initially

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

        # Cache checkbox
        self.cache_var = tk.IntVar(value=1)  # Default to caching enabled
        self.cache_checkbox = tk.Checkbutton(self.url_frame, text="Cache Video", variable=self.cache_var)
        self.cache_checkbox.pack(side=tk.LEFT, padx=10)

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
        self.playlist_listbox.bind("<Double-1>", self.play_selected_item)
        self.playlist_listbox.bind("<Return>", self.play_selected_item)

        # Bind mouse wheel for scrolling
        self.playlist_listbox.bind("<MouseWheel>", self.scroll_playlist)

        # Playlist controls organized on separate lines
        self.playlist_control_frame = tk.Frame(self.playlist_frame)
        self.playlist_control_frame.pack(side=tk.BOTTOM)

        self.add_local_button = tk.Button(self.playlist_control_frame, text="Add Local", command=self.add_local_to_playlist)
        self.add_local_button.grid(row=0, column=0, padx=5, pady=2)

        self.add_youtube_button = tk.Button(self.playlist_control_frame, text="Add YouTube", command=self.add_youtube_to_playlist)
        self.add_youtube_button.grid(row=0, column=1, padx=5, pady=2)

        self.load_playlist_button = tk.Button(self.playlist_control_frame, text="Load Playlist", command=self.load_playlist)
        self.load_playlist_button.grid(row=1, column=0, padx=5, pady=2)

        self.save_playlist_button = tk.Button(self.playlist_control_frame, text="Save Playlist", command=self.save_playlist)
        self.save_playlist_button.grid(row=1, column=1, padx=5, pady=2)

        self.remove_button = tk.Button(self.playlist_control_frame, text="Remove", command=self.remove_from_playlist)
        self.remove_button.grid(row=2, column=0, padx=5, pady=2)

        self.edit_playlist_button = tk.Button(self.playlist_control_frame, text="Edit Playlist", command=self.edit_playlist)
        self.edit_playlist_button.grid(row=2, column=1, padx=5, pady=2)

        self.delete_playlist_button = tk.Button(self.playlist_control_frame, text="Delete Playlist", command=self.delete_playlist)
        self.delete_playlist_button.grid(row=3, column=0, padx=5, pady=2)

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

    def play_youtube_video(self, event=None, add_to_playlist=True):
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
                                    threading.Thread(target=self.download_video, args=(video_url, cache_path)).start()

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

                        if add_to_playlist:
                            video_title = info_dict.get('title', url)
                            self.add_to_playlist(url, video_title)

            except Exception as e:
                logging.error(f"Error playing YouTube video: {e}")

    def download_and_play_first_video(self, video_url, cache_path):
        """Download the first video and play it immediately if not cached, otherwise play from cache."""
        try:
            if cache_path and os.path.exists(cache_path):
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

    def download_video(self, video_url, cache_path):
        """Download subsequent videos to the cache directory in the background."""
        try:
            if not os.path.exists(cache_path):
                logging.info(f"Downloading video in background: {video_url}")
                ydl_opts_video = {'format': 'best', 'outtmpl': cache_path}

                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl_video:
                    ydl_video.download([video_url])
                    logging.info(f"Background video download completed: {video_url}")

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
                    self.play_selected_item()  # Play the selected item

    def save_playlist(self):
        playlist_file = filedialog.asksaveasfilename(initialdir=self.playlist_dir,
                                                     title="Save Playlist",
                                                     defaultextension=".json",
                                                     filetypes=(("JSON Files", "*.json"), ("All Files", "*.*")))
        if playlist_file:
            with open(playlist_file, 'w') as file:
                json.dump(self.playlist, file, indent=4)

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

    def play_selected_item(self, event=None):
        selected_index = self.playlist_listbox.curselection()
        if selected_index:
            selected_item = self.playlist[selected_index[0]]
            url = selected_item["url"]

            # Check if the video is already cached
            video_path = self.get_cached_video_path(url)

            if video_path:
                # Play from the cached file
                self.play_local_video(video_path)
            elif url.startswith("http"):
                # If not cached, stream or download from the URL
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, url)
                self.play_youtube_video(event=None, add_to_playlist=False)  # Prevent adding to playlist again
            else:
                self.play_local_video(url)

    def on_video_end(self):
        current_index = self.playlist_listbox.curselection()
        if current_index:
            next_index = current_index[0] + 1
            if next_index < self.playlist_listbox.size():
                self.playlist_listbox.selection_clear(0, tk.END)
                self.playlist_listbox.selection_set(next_index)
                self.playlist_listbox.activate(next_index)
                self.play_selected_item()
            else:
                self.stop_video()  # Stop the video if no more videos in the playlist
        else:
            self.stop_video()

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

                # Check if the video has finished playing
                if abs(current_time - total_time) < 1:  # Check if current_time is close to total_time
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
