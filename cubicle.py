import cv2
import customtkinter as ctk
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO
import pyautogui
import os
import subprocess
from datetime import datetime
import time
import requests  # NEW: For Cloud Hook
import sqlite3   # NEW: For Data Layer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class OpticGridApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OpticGrid | Sentient Workspace v7.0")
        self.geometry("1280x720")

        # --- AI & Liveness Tools ---
        self.face_detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(base_options=python.BaseOptions(model_asset_path='blaze_face_short_range.tflite'))
        )
        self.phone_model = YOLO('yolov8n.pt')
        self.webcam = cv2.VideoCapture(0)
        
        # State Variables
        self.prev_frame = None
        self.slacker_score = 0
        self.frame_skip = 0
        self.is_shaming = False
        self.phone_strike_count = 0 
        self.last_phone_warning = 0
        self.current_active_app = ""

        # --- NEW: Cloud Hook Configuration ---
        # PASTE YOUR DISCORD WEBHOOK URL HERE
        self.webhook_url = "https://discord.com/api/webhooks/1497097860787867700/iPW1kschFdDxirkY5XtSReMcyZFtV3cet8XL4ku_zzLYRuGzEb578Arx4Wy7mvI_NgBe"

        # --- NEW: Data Layer Configuration ---
        self.conn = sqlite3.connect('opticgrid.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS focus_log
                             (timestamp TEXT, slacker_score INTEGER, active_app TEXT)''')
        self.conn.commit()
        self.last_db_log_time = time.time()

        # --- UI LAYOUT (3 Columns) ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Panel (Telemetry)
        self.left_panel = ctk.CTkFrame(self, fg_color="#1a1b26", corner_radius=15)
        self.left_panel.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.logo = ctk.CTkLabel(self.left_panel, text="OpticGrid", font=ctk.CTkFont(family="Helvetica", size=28, weight="bold"), text_color="#00f2fe")
        self.logo.pack(pady=(30, 5))
        self.version = ctk.CTkLabel(self.left_panel, text="BUILD 7.0 // DATA LAYER", font=ctk.CTkFont(size=10, weight="bold"), text_color="#565f89")
        self.version.pack(pady=(0, 40))
        self.score_title = ctk.CTkLabel(self.left_panel, text="SLACKER SCORE", font=ctk.CTkFont(size=14, weight="bold"), text_color="#a9b1d6")
        self.score_title.pack()
        self.score_label = ctk.CTkLabel(self.left_panel, text="0", font=ctk.CTkFont(family="Courier", size=65, weight="bold"), text_color="#4facfe")
        self.score_label.pack(pady=(0, 30))
        self.status_frame = ctk.CTkFrame(self.left_panel, fg_color="#24283b", corner_radius=10)
        self.status_frame.pack(fill="x", padx=20, pady=10)
        self.status_label = ctk.CTkLabel(self.status_frame, text="● SYSTEM ACTIVE", text_color="#9ece6a", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_label.pack(pady=15)

        # Center Panel (Vision Feed)
        self.center_panel = ctk.CTkFrame(self, fg_color="#16161e", corner_radius=15)
        self.center_panel.grid(row=0, column=1, padx=0, pady=15, sticky="nsew")
        self.video_label = ctk.CTkLabel(self.center_panel, text="")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Right Panel (Audit Log)
        self.right_panel = ctk.CTkFrame(self, fg_color="#1a1b26", corner_radius=15)
        self.right_panel.grid(row=0, column=2, padx=15, pady=15, sticky="nsew")
        self.log_title = ctk.CTkLabel(self.right_panel, text="LIVE AUDIT LOG", font=ctk.CTkFont(size=14, weight="bold"), text_color="#a9b1d6")
        self.log_title.pack(pady=(30, 10))
        self.info_box = ctk.CTkTextbox(self.right_panel, fg_color="#24283b", text_color="#c0caf5", font=ctk.CTkFont(family="Courier", size=12), corner_radius=10)
        self.info_box.pack(expand=True, fill="both", padx=15, pady=(0, 20))
        
        self.log_event("SYSTEM INITIALIZED", "CORE")
        self.update_frame()

    def get_active_app(self):
        try:
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return "Permission Denied"
            return result.stdout.strip()
        except Exception:
            return "App Fetch Error"

    def log_event(self, message, category="EVENT"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.info_box.insert("0.0", f"[{timestamp}] [{category}]\n{message}\n\n")

    def update_frame(self):
        success, frame = self.webcam.read()
        if success:
            self.frame_skip += 1
            frame_display = cv2.flip(frame, 1)
            current_time = time.time()
            
            # --- 0. APP TRACKING (Every ~1 sec) ---
            if self.frame_skip % 30 == 0:
                app_name = self.get_active_app()
                if app_name and app_name != self.current_active_app:
                    self.current_active_app = app_name
                    self.log_event(f"Focused: {app_name}", "APP")

            # --- RAPID DATA LOGGING (Every 2 seconds) ---
            if current_time - self.last_db_log_time >= 2:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.cursor.execute("INSERT INTO focus_log VALUES (?, ?, ?)", 
                                   (ts, int(self.slacker_score), self.current_active_app))
                self.conn.commit()
                #self.log_event("Data synced to SQLite DB.", "DATA")
                self.last_db_log_time = current_time

            # --- 1. LIVENESS ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            movement_detected = False
            if self.prev_frame is not None:
                diff = cv2.absdiff(self.prev_frame, gray)
                thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
                movement = thresh.sum() / 255
                if movement > 200: movement_detected = True
            self.prev_frame = gray

            # --- 2. AI LOGIC ---
            if self.frame_skip % 10 == 0 and not self.is_shaming:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                face_result = self.face_detector.detect(mp_image)
                faces_count = len(face_result.detections) if face_result.detections else 0
                face_present = faces_count > 0
                
                is_looking_away = False
                if face_present:
                    keypoints = face_result.detections[0].keypoints
                    if len(keypoints) >= 3:
                        rx, lx, nx = keypoints[0].x, keypoints[1].x, keypoints[2].x
                        dist_r, dist_l = abs(nx - rx), abs(nx - lx)
                        if dist_r > 0 and dist_l > 0:
                            if max(dist_r, dist_l) / min(dist_r, dist_l) > 3.5:
                                is_looking_away = True

                phone_result = self.phone_model(frame, verbose=False, conf=0.25)
                has_phone = any(int(box.cls[0]) == 67 for r in phone_result for box in r.boxes)

                # --- 3. DECISION ENGINE ---
                if faces_count > 1:
                    self.status_label.configure(text="● THREAT DETECTED", text_color="#f7768e")
                    os.system("pmset displaysleepnow")
                
                # --- INSTANT PHONE WARDEN ---
                elif has_phone:
                    # If it sees a phone, strike instantly (with a 5-second voice cooldown)
                    if current_time - self.last_phone_warning > 5: 
                        self.slacker_score = min(100, self.slacker_score + 40)
                        self.status_label.configure(text="● PHONE DETECTED", text_color="#e0af68")
                        os.system("say 'Device detected. Put it away.' &") # '&' runs voice in background
                        self.last_phone_warning = current_time
                        
                # --- SLACKER SCORING ---
                if is_looking_away:
                    self.slacker_score = min(100, self.slacker_score + 15)
                    self.status_label.configure(text="● NOT ENGAGED", text_color="#ff9e64")
                    
                elif not face_present and not movement_detected and not has_phone:
                    self.slacker_score = min(100, self.slacker_score + 25)
                    self.status_label.configure(text="● STATUS: AFK", text_color="#7aa2f7")
                    
                elif face_present or movement_detected:
                    self.slacker_score = max(0, self.slacker_score - 10)
                    if not has_phone:
                        self.status_label.configure(text="● SYSTEM ACTIVE", text_color="#9ece6a")

                # --- UI COLOR UPDATES ---
                self.score_label.configure(text=f"{int(self.slacker_score)}")
                if self.slacker_score > 75: 
                    self.score_label.configure(text_color="#f7768e")
                elif self.slacker_score > 40: 
                    self.score_label.configure(text_color="#e0af68")
                else: 
                    self.score_label.configure(text_color="#4facfe")

            # --- SHAME TRIGGER ---
            if self.slacker_score >= 100 and not self.is_shaming:
                self.trigger_shame()

            img_pil = Image.fromarray(cv2.cvtColor(frame_display, cv2.COLOR_BGR2RGB))
            ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(640, 480))
            self.video_label.configure(image=ctk_img)

        self.after(10, self.update_frame)

    def trigger_shame(self):
        # --- NEW: Force log the 100 to the database before resetting ---
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO focus_log VALUES (?, ?, ?)", 
                           (ts, 100, self.current_active_app if self.current_active_app else "Unknown"))
        self.conn.commit()

        # Existing shame logic
        self.is_shaming = True
        self.slacker_score = 0
        self.status_label.configure(text="● SHAME PROTOCOL", text_color="#f7768e")
        self.log_event("Shame Protocol engaged.", "ALERT")
        os.system("say 'Focus lost. Social protocol engaged.' &")
        
        # --- CLOUD HOOK TRIGGER ---
        if "YOUR_DISCORD" not in self.webhook_url:
            app_used = self.current_active_app if self.current_active_app else "Unknown"
            payload = {
                "content": f"🚨 **OpticGrid Alert:** Raffi failed the focus test!\nLast seen looking at: `{app_used}`"
            }
            try:
                requests.post(self.webhook_url, json=payload)
                self.log_event("Sent alert to Discord.", "CLOUD")
            except Exception as e:
                self.log_event("Failed to connect to Discord.", "CLOUD")

        self.after(15000, self.reset_shame)

    def reset_shame(self):
        self.is_shaming = False
        self.status_label.configure(text="● SYSTEM ACTIVE", text_color="#9ece6a")

if __name__ == "__main__":
    app = OpticGridApp()
    app.mainloop()