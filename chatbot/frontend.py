import customtkinter as ctk
import random
import json
import speech_recognition as sr
import pyttsx3
from tkinter import scrolledtext
import os
from PIL import Image
import threading
import requests
import queue
from chatbot_config import API_KEY

# --- THEME COLORS ---
DARK_BG = "#23272F"
LIGHT_BG = "#F4F6FA"
ACCENT = "#5DADE2"
TEXT_DARK = "#23272F"
TEXT_LIGHT = "#F4F6FA"
GRAY = "#A7B1C2"

# --- App Setup ---
ctk.set_appearance_mode("dark")
app = ctk.CTk()
app.title("NeoLearner Bot")
app.iconbitmap("chatbot.ico")
app.geometry("700x450")

# --- TTS Engine ---
engine = pyttsx3.init()
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)
tts_queue = queue.Queue()
tts_greeting_done = False

def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:
            tts_queue.task_done()
            break
        engine.say(text)
        engine.runAndWait()
        tts_queue.task_done()

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def speak(text, force=False):
    global tts_greeting_done
    if force or not tts_greeting_done:
        tts_queue.put(text)
        tts_greeting_done = True

# --- Bot Responses ---
bot_responses = [
    "Hello! How can I assist you?",
    "I'm here to help! Tell me what you need.",
    "That's interesting! Can you elaborate?",
    "I'm not sure, but I can try to find out.",
    "Can you provide more details?",
    "Let me think... 🤔"
]

# --- Chat History (Thread-Safe) ---
CHAT_HISTORY_FILE = "chat_history.json"
user_name = None
user_profile_pic_path = "profile.png"
chat_history_enabled = True
chat_history_lock = threading.Lock()

# Only save user/bot chat messages, not sidebar/help/settings/dashboard
CHAT_MESSAGE_HEADINGS = ["ALPHA", "INFORMATION"]  # Only these headings are considered real chat

def save_chat_history():
    if not chat_history_enabled:
        return
    # Only save if the first line is 'CHATS' (i.e., main chat view)
    if chat_text.get("1.0", "2.0").strip().upper() != "CHATS":
        return
    # Only save lines that are actual chat messages (with allowed headings)
    chat_data = chat_text.get("1.0", "end").strip().split("\n")
    filtered_lines = []
    for line in chat_data:
        # Only save lines that look like chat messages: '> sender: message' and sender is not ALPHA for headings
        if line.startswith("> "):
            # Optionally, you can further filter by sender if needed
            filtered_lines.append(line)
    with chat_history_lock:
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump({"history": "\n".join(filtered_lines)}, f)

def load_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        with chat_history_lock:
            with open(CHAT_HISTORY_FILE, "r") as f:
                data = json.load(f)
                return data.get("history", "")
    return ""

previous_chat_content = None  # To store current chat before showing history

def show_chat_history():
    global previous_chat_content
    # If help is showing, don't save it as previous chat content
    if chat_text.get("1.0", "2.0").strip().upper() == "HELP":
        previous_chat_content = None
    else:
        previous_chat_content = chat_text.get("1.0", "end-1c")
    history = load_chat_history()
    chat_text.config(state="normal")
    chat_text.delete("1.0", "end")
    chat_text.insert("1.0", "HISTORY\n", "history_heading")
    chat_text.insert("end", history if history else "No chat history found.")
    chat_text.config(state="disabled")
    chat_text.tag_configure("history_heading", font=("Segoe UI", 15, "bold"), foreground=ACCENT)
    set_main_buttons_visibility(show=False)
    back_to_chat_button.configure(text="Back to Chats")
    back_to_chat_button.pack(side="left", padx=10, pady=5)
    set_button_texts()

def back_to_chat():
    global previous_chat_content
    chat_text.config(state="normal")
    chat_text.delete("1.0", "end")
    chat_text.insert("1.0", "CHATS\n", "chats_heading")
    if previous_chat_content:
        chat_text.insert("end", previous_chat_content)
    chat_text.config(state="disabled")
    chat_text.tag_configure("chats_heading", font=("Segoe UI", 15, "bold"), foreground=ACCENT)
    set_main_buttons_visibility(show=True)
    back_to_chat_button.pack_forget()
    set_button_texts()

# --- Utility: Sidebar/Icon/Button Creation (DRY) ---
def load_icon(path, size=(30, 30)):
    try:
        return ctk.CTkImage(light_image=Image.open(path), size=size)
    except Exception as e:
        print(f"Icon load error: {path} - {e}")
        return None

def style_sidebar_button(btn):
    btn.configure(
        width=38, height=38, fg_color="#20232A", hover_color="#31343C",
        border_width=0, corner_radius=16, text_color=GRAY,
        font=("Segoe UI", 12, "bold"), cursor="hand2", anchor="center"
    )

def create_sidebar_button(parent, icon, command, pady):
    btn = ctk.CTkButton(parent, image=icon, text="", command=command)
    style_sidebar_button(btn)
    btn.pack(pady=pady)
    return btn

def set_main_buttons_visibility(show=True):
    if show:
        send_button.pack(side="left", padx=10, pady=5)
        voice_button.pack(side="right", padx=10, pady=5)
        history_button.pack(side="left", padx=10, pady=5)
    else:
        send_button.pack_forget()
        voice_button.pack_forget()
        history_button.pack_forget()

def set_button_texts():
    send_button.configure(text="SEND")
    history_button.configure(text="Show History")
    voice_button.configure(text="Speak")

# --- Sidebar & Icons ---
icons = {name: load_icon(f"{name}.png") for name in [
    "profile", "home", "chat", "settings", "clearchats", "theme", "help", "exit"
]}

sidebar = ctk.CTkFrame(app, width=60, height=450, fg_color="#181A20", border_width=0)
sidebar.pack(side="left", fill="y")

# --- Sidebar Button Commands ---
def show_profile():
    show_message("NeoLearner", f"User Name: {user_name if user_name else 'Not Set'}", heading="PROFILE")

def show_new_chat():
    global previous_chat_content
    previous_chat_content = None
    chat_text.config(state="normal")
    chat_text.delete("1.0", "end")
    chat_text.insert("1.0", "CHATS\n", ("chats_heading",))
    chat_text.config(state="disabled")
    chat_text.tag_configure("chats_heading", font=("Segoe UI", 15, "bold"), foreground=ACCENT)
    set_main_buttons_visibility(show=True)
    back_to_chat_button.pack_forget()

# --- Settings/Help Implementation ---
settings_window = None

def show_settings():
    global settings_window
    if settings_window and settings_window.winfo_exists():
        settings_window.lift()
        return
    settings_window = ctk.CTkToplevel(app)
    settings_window.title("Settings")
    settings_window.geometry("350x250")
    settings_window.resizable(False, False)
    settings_window.grab_set()
    settings_window.focus()

    # Set settings window icon to the same as the sidebar settings icon
    try:
        settings_window.iconbitmap("settings.ico" if os.path.exists("settings.ico") else "settings.png")
    except Exception:
        pass

    # Theme toggle
    theme_label = ctk.CTkLabel(settings_window, text="Theme:", font=("Segoe UI", 13, "bold"))
    theme_label.pack(pady=(20, 5))
    theme_btn = ctk.CTkButton(settings_window, text="Toggle Dark/Light", command=toggle_theme)
    theme_btn.pack(pady=5)

    # Font size
    font_label = ctk.CTkLabel(settings_window, text="Font Size:", font=("Segoe UI", 13, "bold"))
    font_label.pack(pady=(20, 5))
    font_slider = ctk.CTkSlider(settings_window, from_=10, to=22, number_of_steps=12, orientation="horizontal")
    font_slider.set(font_size)
    font_slider.pack(pady=5)
    def on_font_slider(val):
        global font_size
        font_size = int(float(val))
        apply_font_size()
    font_slider.configure(command=on_font_slider)

    # History toggle
    def toggle_history():
        global chat_history_enabled
        chat_history_enabled = not chat_history_enabled
        history_btn.configure(text="ON" if chat_history_enabled else "OFF")
    history_label = ctk.CTkLabel(settings_window, text="Chat History:", font=("Segoe UI", 13, "bold"))
    history_label.pack(pady=(20, 5))
    history_btn = ctk.CTkButton(settings_window, text="ON" if chat_history_enabled else "OFF", command=toggle_history)
    history_btn.pack(pady=5)

    # --- Custom Panel: Notifications & Language (as info, not interactive) ---
    info_frame = ctk.CTkFrame(settings_window, fg_color="#23272F")
    info_frame.pack(fill="x", padx=18, pady=(10, 8))
    info_text = (
        "\U0001F527 Welcome to Settings!\n"
        "Please choose your preferences below:\n\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\U0001F514 1. Notifications Settings:\n"
        "Would you like to turn notifications ON or OFF?\n\n"
        "\u27A1 Type:\n"
        "- `on` to enable notifications\n"
        "- `off` to disable notifications\n\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\U0001F310 2. Language Settings:\n"
        "Please select your preferred language:\n\n"
        "1\u20E3 English  \n2\u20E3 Urdu  \n3\u20E3 Roman Urdu  \n\n"
        "\u27A1 Type the number or name of the language.\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\U0001F4AC Example:\n> on  \n> 2"
    )
    info_label = ctk.CTkLabel(info_frame, text=info_text, font=("Segoe UI", 11), justify="left", anchor="w")
    info_label.pack(fill="x", padx=4, pady=4)

    # --- Language Selection Dropdown ---
    global selected_language
    language_label = ctk.CTkLabel(settings_window, text="Chatbot Language:", font=("Segoe UI", 13, "bold"))
    language_label.pack(pady=(20, 5))
    language_options = ["English", "Urdu", "Roman Urdu"]
    if 'selected_language' not in globals():
        selected_language = language_options[0]
    def on_language_select(choice):
        global selected_language
        selected_language = choice
    language_menu = ctk.CTkOptionMenu(settings_window, values=language_options, command=on_language_select)
    language_menu.set(selected_language)
    language_menu.pack(pady=5)

    # Close button
    close_btn = ctk.CTkButton(settings_window, text="Close", command=settings_window.destroy)
    close_btn.pack(pady=(20, 10))

def show_help():
    help_text = (
        "\U0001F4D6 Getting Started\n"
        "Welcome! This chatbot is here to help you with your internet service. Just type your question or command to begin.\n"
        "For example:\n"
        "- Check my package\n"
        "- Register a complaint\n"
        "- Balance check\n"
        "- Show my bill\n"
        "\n"
        "\U0001F4A1 What Can I Ask?\n"
        "You can use the chatbot for things like:\n"
        "- Get package information\n"
        "- Register a complaint\n"
        "- Check your balance or bill\n"
        "- Find customer care contact details\n"
        "- Check internet speed or usage\n"
        "- Request a new connection\n"
        "\n"
        "\u2328\uFE0F Common Commands\n"
        "- Check package – View your current internet or mobile package details\n"
        "- Register complaint – Report a problem with your service\n"
        "- Check balance – See your current balance or bill\n"
        "- Contact support – Get customer care contact info\n"
        "- Start again – Restart the chat\n"
        "- Help – Show this help panel\n"
        "\n"
        "\U0001F527 Troubleshooting\n"
        "- Bot not replying?\n"
        "  • Check your internet connection\n"
        "  • Type 'Start again' to restart the chat\n"
        "- Bot misunderstood your question?\n"
        "  • Use short, clear phrases\n"
        "  • Example: 'Check balance'\n"
        "\n"
        "\U0001F4DE Contact Support\n"
        "- WhatsApp: 0311-7007004\n"
        "- Email: arifanis306@gmail.com\n"
        "- To talk to a human agent, type: Talk to agent\n"
        "\n"
        "\U0001F512 Safety Tips\n"
        "- Never share your password or OTP\n"
        "- Keep your personal information private\n"
        "- If you need a record, take a screenshot (chat history may not be saved)\n"
    )
    chat_text.config(state="normal")
    chat_text.delete("1.0", "end")
    chat_text.insert("1.0", "HELP PANEL\n", ("help_heading_tag",))
    chat_text.insert("end", help_text)
    chat_text.config(state="disabled")
    chat_text.tag_configure("help_heading_tag", font=("Segoe UI", 15, "bold"), foreground=ACCENT)
    set_main_buttons_visibility(show=False)
    back_to_chat_button.configure(text="Back to Chats")
    back_to_chat_button.pack(side="left", padx=10, pady=5)

# --- Sidebar Buttons ---
profile_button = create_sidebar_button(sidebar, icons["profile"], show_profile, (18, 6))
home_button = create_sidebar_button(sidebar, icons["home"], lambda: show_dashboard(), 6)
chat_button = create_sidebar_button(sidebar, icons["chat"], show_new_chat, 6)
settings_button = create_sidebar_button(sidebar, icons["settings"], show_settings, 6)
help_button = create_sidebar_button(sidebar, icons["help"], show_help, 6)
exit_button = create_sidebar_button(sidebar, icons["exit"], app.quit, (6, 18))

# --- Main Chat Area ---
chat_frame = ctk.CTkFrame(app, fg_color=DARK_BG, border_width=0)
chat_frame.pack(pady=10, padx=20, fill="both", expand=True)

chat_text = scrolledtext.ScrolledText(chat_frame, wrap="word", bg=DARK_BG, fg=LIGHT_BG,
                                      font=("Segoe UI", 13), state="normal", height=15, insertbackground=ACCENT, selectbackground=ACCENT)
chat_text.pack(padx=10, pady=10, fill="both", expand=True)
chat_text.insert("1.0", "CHATS\n", "chats_heading")
chat_text.tag_configure("chats_heading", font=("Segoe UI", 15, "bold"), foreground=ACCENT)
chat_text.config(state="disabled")

# --- Main Chat Controls ---
user_input = ctk.CTkEntry(chat_frame, width=400, font=("Segoe UI", 13))
user_input.pack(padx=10, pady=(0, 10), fill="x")

button_frame = ctk.CTkFrame(chat_frame, fg_color=DARK_BG)
button_frame.pack(fill="x", padx=10, pady=(0, 10))

send_button = ctk.CTkButton(button_frame, text="SEND", font=("Segoe UI", 10, "bold"), fg_color=ACCENT, text_color=LIGHT_BG, width=70, height=28)
send_button.pack(side="left", padx=6, pady=3)

voice_button = ctk.CTkButton(button_frame, text="Speak", font=("Segoe UI", 10, "bold"), fg_color=ACCENT, text_color=LIGHT_BG, width=70, height=28)
voice_button.pack(side="right", padx=6, pady=3)

history_button = ctk.CTkButton(button_frame, text="Show History", font=("Segoe UI", 10, "bold"), fg_color=ACCENT, text_color=LIGHT_BG, width=90, height=28)
history_button.pack(side="left", padx=6, pady=3)

back_to_chat_button = ctk.CTkButton(button_frame, text="Back to Chats", command=back_to_chat, font=("Segoe UI", 12, "bold"), fg_color=ACCENT, text_color=LIGHT_BG)
back_to_chat_button.pack_forget()

# Add Upload Picture button next to Speak button
from tkinter import filedialog, messagebox, Toplevel, Label
from PIL import Image, ImageTk
import base64
import io

def upload_picture():
    filetypes = [
        ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
        ("All files", "*.*")
    ]
    filepath = filedialog.askopenfilename(
        title="Select a picture to upload",
        filetypes=filetypes
    )
    if filepath:
        try:
            # Open and read the image as binary
            with open(filepath, "rb") as img_file:
                img_bytes = img_file.read()
            # Optionally, encode to base64 if you want to send to backend
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            # Remove filename from chat, just show image in chat area
            # Display image in chat interface (below the last message)
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((200, 200))
            img_tk = ImageTk.PhotoImage(img)
            # Insert image into chat_text widget
            chat_text.config(state="normal")
            chat_text.image_create("end", image=img_tk)
            chat_text.insert("end", "\n")
            chat_text.image_ref = getattr(chat_text, 'image_ref', [])
            chat_text.image_ref.append(img_tk)  # Prevent garbage collection
            chat_text.config(state="disabled")
            chat_text.yview("end")
            # Optionally, you can send img_b64 to backend here
        except Exception as e:
            messagebox.showerror("Upload Error", f"Failed to upload image: {e}")
    else:
        messagebox.showinfo("Upload", "No picture selected.")

upload_button = ctk.CTkButton(button_frame, text="Upload Picture", font=("Segoe UI", 10, "bold"), fg_color=ACCENT, text_color=LIGHT_BG, width=110, height=28, command=upload_picture)
upload_button.pack(side="right", padx=6, pady=3)

# --- Dashboard ---
dash_frame = ctk.CTkFrame(app, fg_color=DARK_BG)
dash_label = ctk.CTkLabel(dash_frame, text="Welcome to NeoLearner Bot Dashboard!", font=("Segoe UI", 16, "bold"), text_color=ACCENT)
dash_label.pack(pady=20)
dash_recent_label = ctk.CTkLabel(dash_frame, text="", font=("Segoe UI", 12), text_color=LIGHT_BG)
dash_recent_label.pack(pady=10)

def load_recent_summary():
    history = load_chat_history()
    if history:
        lines = history.split('\n')[-5:]
        dash_recent_label.configure(text="Recent Activity:\n" + "\n".join(lines))
    else:
        dash_recent_label.configure(text="No recent activity.")

def show_dashboard():
    global previous_chat_content
    previous_chat_content = None
    chat_text.config(state="normal")
    chat_text.delete("1.0", "end")
    chat_text.insert("1.0", "DASHBOARD\n", ("dashboard_heading",))
    chat_text.insert("end", "Welcome to NeoLearner Bot!\n\n", ("dashboard_welcome",))
    history = load_chat_history()
    if history:
        lines = history.split('\n')
        user_lines = [line for line in lines if line.strip().startswith('>') and (': ' in line) and not line.strip().startswith('> ALPHA:')]
        user_lines = user_lines[-5:]
        if user_lines:
            chat_text.insert("end", "Recent Activity:\n", ("dashboard_section",))
            for line in user_lines:
                msg = line.split(':', 1)[-1].strip()
                chat_text.insert("end", f"- {msg}\n")
        else:
            chat_text.insert("end", "No recent user activity found.")
    else:
        chat_text.insert("end", "No recent activity found.")
    chat_text.config(state="disabled")
    chat_text.tag_configure("dashboard_heading", font=("Segoe UI", 16, "bold"), foreground=ACCENT)
    chat_text.tag_configure("dashboard_welcome", font=("Segoe UI", 13, "italic"), foreground=ACCENT)
    chat_text.tag_configure("dashboard_section", font=("Segoe UI", 14, "bold"), foreground=ACCENT)
    set_main_buttons_visibility(show=False)
    back_to_chat_button.configure(text="Back to Chats")
    back_to_chat_button.pack(side="left", padx=10, pady=5)

# --- Message Display (Single Definition, Bold Sender) ---
def show_message(sender, message, heading=None):
    chat_text.config(state="normal")
    if heading:
        # Replace ALPHA heading with NeoLearner
        heading = heading.replace("ALPHA", "NeoLearner")
    # Sender name bold, message normal
    chat_text.insert("end", f"{heading}\n", ("heading_tag",)) if heading else None
    chat_text.insert("end", f"> ", ("sender_tag",))
    chat_text.insert("end", f"{sender}", ("sender_bold",))
    chat_text.insert("end", f": {message}\n")
    chat_text.config(state="disabled")
    chat_text.yview("end")
    app.after(10, save_chat_history)
    chat_text.tag_configure("heading_tag", font=("Segoe UI", 16, "bold"), foreground=ACCENT)
    chat_text.tag_configure("sender_bold", font=("Segoe UI", 13, "bold"), foreground=ACCENT)
    chat_text.tag_configure("sender_tag", font=("Segoe UI", 13, "bold"), foreground=GRAY)

# --- Message Sending ---
def send_message():
    global user_name
    user_text = user_input.get().strip()
    user_input.delete(0, "end")
    if not user_name:
        if user_text:
            user_name = user_text
            welcome_message = f"Nice to meet you, {user_name}! How can I help you today?"
            show_message("NeoLearner", welcome_message, heading="NeoLearner")
            speak(welcome_message, force=True)
            return
        else:
            show_message("NeoLearner", "Please enter your name first.", heading="NeoLearner")
            return
    if user_text:
        show_message(user_name, user_text, heading=user_name)
        bot_reply = get_bot_reply_from_api(user_text)
        if any(word in user_text.lower() for word in ["search", "find", "look up", "khoj", "talash", "maloomat"]):
            show_message("NeoLearner", bot_reply, heading="INFORMATION")
        else:
            show_message("NeoLearner", bot_reply, heading="NeoLearner")

API_URL = "https://api.groq.com/openai/v1/chat/completions"
API_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_bot_reply_from_api(user_message):
    if not API_KEY:
        return "API key not set. Please set GROQ_API_KEY environment variable."
    try:
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }
        response = requests.post(
            API_URL,
            headers=API_HEADERS,
            json=payload
        )
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"API error: {response.status_code}: {response.text}"
    except Exception as e:
        return f"API request failed: {e}"

# --- Voice Input ---
def get_voice_input():
    if not user_name:
        show_message("NeoLearner", "Please enter your name first.")
        return
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        show_message("NeoLearner", "Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
        try:
            user_text = recognizer.recognize_google(audio)
            user_input.delete(0, "end")
            user_input.insert(0, user_text)
            send_message()
        except sr.UnknownValueError:
            show_message("NeoLearner", "Sorry, I didn't catch that.")
        except sr.RequestError:
            show_message("NeoLearner", "Network error, please try again.")

# --- Theme/Font Update ---
def update_theme_colors():
    mode = ctk.get_appearance_mode()
    if mode == "Dark":
        bg, fg, accent, sidebar_fg, sidebar_btn_fg, sidebar_btn_hover, text_color = (
            DARK_BG, LIGHT_BG, ACCENT, "#181A20", "#20232A", "#31343C", TEXT_LIGHT)
        chat_text_fg = LIGHT_BG  # White text in dark mode
        user_input_text_color = "#F4F6FA"  # Light (white) text for typing area
    else:
        bg, fg, accent, sidebar_fg, sidebar_btn_fg, sidebar_btn_hover, text_color = (
            LIGHT_BG, TEXT_DARK, ACCENT, "#F4F6FA", "#E3E6ED", "#D0D3DB", TEXT_DARK)
        chat_text_fg = TEXT_DARK  # Black text in light mode
        user_input_text_color = "#23272F"  # Dark (black) text for typing area
    app.configure(fg_color=bg)
    sidebar.configure(fg_color=sidebar_fg)
    chat_frame.configure(fg_color=bg)
    chat_text.configure(bg=bg, fg=chat_text_fg, insertbackground=accent, selectbackground=accent)
    user_input.configure(fg_color=fg, border_color=accent, text_color=user_input_text_color)
    # Force update for CTkEntry internal widget (tk.Entry) as fallback
    if hasattr(user_input, 'entry'):
        try:
            user_input.entry.configure(fg=user_input_text_color, insertbackground=accent)
        except Exception:
            pass
    button_frame.configure(fg_color=bg)
    send_button.configure(fg_color=accent, text_color=text_color)
    history_button.configure(fg_color=accent, text_color=text_color)
    voice_button.configure(fg_color=accent, text_color=text_color)
    back_to_chat_button.configure(fg_color=accent, text_color=text_color)
    for btn in [profile_button, home_button, chat_button, settings_button, help_button, exit_button]:
        btn.configure(fg_color=sidebar_btn_fg, hover_color=sidebar_btn_hover, text_color=GRAY)
    dash_frame.configure(fg_color=bg)
    dash_label.configure(text_color=accent)
    dash_recent_label.configure(text_color=fg)

def toggle_theme():
    current_mode = ctk.get_appearance_mode()
    ctk.set_appearance_mode("light" if current_mode == "Dark" else "dark")
    update_theme_colors()

font_size = 13

def apply_font_size():
    chat_text.configure(font=("Segoe UI", font_size))
    dash_label.configure(font=("Segoe UI", 16, "bold"))
    dash_recent_label.configure(font=("Segoe UI", 12))
    user_input.configure(font=("Segoe UI", 13))
    send_button.configure(font=("Segoe UI", 12, "bold"))
    history_button.configure(font=("Segoe UI", 12))
    voice_button.configure(font=("Segoe UI", 12))
    back_to_chat_button.configure(font=("Segoe UI", 12))
    chat_text.tag_configure("chats_heading", font=("Segoe UI", font_size + 2, "bold"))
    chat_text.tag_configure("dashboard_heading", font=("Segoe UI", font_size + 3, "bold"))
    chat_text.tag_configure("dashboard_welcome", font=("Segoe UI", font_size, "italic"))
    chat_text.tag_configure("dashboard_section", font=("Segoe UI", font_size + 1, "bold"))
    chat_text.tag_configure("history_heading", font=("Segoe UI", font_size + 2, "bold"))
    chat_text.tag_configure("help_heading_tag", font=("Segoe UI", font_size + 2, "bold"))
    chat_text.tag_configure("heading_tag", font=("Segoe UI", font_size + 3, "bold"))
    chat_text.tag_configure("sender_bold", font=("Segoe UI", font_size, "bold"))
    chat_text.tag_configure("sender_tag", font=("Segoe UI", font_size, "bold"))

# --- Bindings ---
send_button.configure(command=send_message)
voice_button.configure(command=get_voice_input)
history_button.configure(command=show_chat_history)

# Bind Enter key to send message
user_input.bind("<Return>", lambda event: (send_message(), "break"))

# --- Main Loop ---
if __name__ == "__main__":
    app.mainloop()