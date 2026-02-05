import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import threading, queue, time, math
import cv2, numpy as np
import mss
import win32api, win32con
from pynput import mouse
from ultralytics import YOLO

# =========================
# Config CS2
# =========================
class Config:
    SCREEN_W, SCREEN_H = 1920, 1080
    CAP_W, CAP_H = 160, 200       # plus large pour CS2
    crosshairX, crosshairY = CAP_W//2, CAP_H//2
    RADIUS = 80                   # FOV par défaut CS2
    SENSITIVITY = 1.0             # sensibilité CS2
    movementSteps = 5
    MovementCoefficientX = 0.8
    MovementCoefficientY = 0.65
    delay = 0.007
    RUNNING = True
    ENABLED = True
    AUTO_SHOOT = False
    TARGET_PART = "Head"
    DEADZONE = 3                  # plus stable
config = Config()

# =========================
# Queues et stats
# =========================
frame_q = queue.Queue(maxsize=5)
result_q = queue.Queue(maxsize=5)
stats = {"fps":0,"latency_ms":0}

# =========================
# Inference Thread
# =========================
class InferenceThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.model = None
        self.locked_id = None
        self.last_results = []

    def load_model(self,path):
        ext = Path(path).suffix
        if ext==".pt":
            self.model = YOLO(path)
        elif ext==".onnx":
            self.model = YOLO(path, task="detect")
        else:
            raise ValueError("Unsupported model format")

    def predict_frame(self,frame):
        if not self.model:
            return []
        start=time.time()
        results=self.model.predict(source=frame, conf=0.5, classes=[0], verbose=False, max_det=10)
        boxes = []
        for b in results[0].boxes.xyxy:
            x1,y1,x2,y2 = b.tolist()
            boxes.append([x1,y1,x2,y2,id(b)])
        self.last_results = boxes
        result_q.put((frame, boxes))
        stats["latency_ms"] = (time.time()-start)*1000
        return boxes

    def run(self):
        while config.RUNNING:
            if not frame_q.empty():
                frame = frame_q.get()
                self.predict_frame(frame)
            else:
                time.sleep(0.001)

# =========================
# Pointer Controller
# =========================
def pointer_controller(infer: InferenceThread):
    prev_pos = None
    while config.RUNNING:
        if not config.ENABLED:
            time.sleep(0.01)
            continue
        try:
            _, boxes = result_q.get_nowait()
        except queue.Empty:
            time.sleep(0.005)
            continue

        cx, cy = config.crosshairX, config.crosshairY
        target = None

        if infer.locked_id is not None:
            for b in boxes:
                x1,y1,x2,y2,tid=b
                if tid==infer.locked_id:
                    target = b
                    break

        if target is None and boxes:
            best_dist = float('inf')
            for b in boxes:
                x1,y1,x2,y2,tid=b
                tx = (x1+x2)/2
                ty = y1 + (y2-y1)*(0.25 if config.TARGET_PART=="Head" else 0.5)
                dist = math.hypot(tx-cx, ty-cy)
                if dist < best_dist and dist <= config.RADIUS:
                    best_dist = dist
                    target = b
            if target:
                infer.locked_id = target[4]

        if target:
            x1,y1,x2,y2,tid=target
            ty = y1 + (y2-y1)*(0.25 if config.TARGET_PART=="Head" else 0.5)
            tx = (x1+x2)/2
            moveX = tx - cx
            moveY = ty - cy
            distance = math.hypot(moveX, moveY)

            speed = 1.0
            if prev_pos:
                px, py = prev_pos
                speed = max(1.0, math.hypot(tx-px, ty-py)/5)
            prev_pos = (tx, ty)
            dynamic_deadzone = config.DEADZONE * speed

            if distance > dynamic_deadzone:
                steps = max(1, int(config.movementSteps * min(5, distance/50)))
                dx_step = moveX * config.MovementCoefficientX / steps
                dy_step = moveY * config.MovementCoefficientY / steps
                for _ in range(steps):
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE,int(dx_step),int(dy_step),0,0)
                    time.sleep(config.delay)

            if config.AUTO_SHOOT:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
                time.sleep(0.01)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0,0,0)

        time.sleep(0.003)

# =========================
# Mouse Listener (clic droit lock)
# =========================
def mouse_listener(infer: InferenceThread):
    def on_click(x,y,button,pressed):
        if button==mouse.Button.right and pressed:
            if infer.locked_id is None:
                try:
                    _, boxes = result_q.get_nowait()
                    if boxes:
                        cx,cy=config.CAP_W//2,config.CAP_H//2
                        best=None
                        best_dist=1e9
                        for b in boxes:
                            x1,y1,x2,y2,tid=b
                            tx = (x1+x2)/2
                            ty = y1 + (y2-y1)*0.5
                            dist = math.hypot(tx-cx,ty-cy)
                            if dist<best_dist:
                                best_dist=dist
                                best=tid
                        if best:
                            infer.locked_id = best
                            print(f"Locked on ID: {infer.locked_id}")
                except queue.Empty:
                    pass
            else:
                infer.locked_id = None
                print("Unlocked target")
    listener = mouse.Listener(on_click=on_click)
    listener.start()

# =========================
# Overlay CS2
# =========================
def create_overlay_thread(infer: InferenceThread):
    overlay=tk.Toplevel()
    cx=config.SCREEN_W//2
    cy=config.SCREEN_H//2
    overlay.geometry(f"{config.CAP_W}x{config.CAP_H}+{cx-config.CAP_W//2}+{cy-config.CAP_H//2}")
    overlay.overrideredirect(True)
    overlay.attributes("-topmost", True)
    overlay.attributes("-transparentcolor", "black")
    overlay.lift()
    overlay.attributes("-topmost", True)

    canvas = tk.Canvas(overlay,width=config.CAP_W,height=config.CAP_H,bg="black",bd=0,highlightthickness=0)
    canvas.pack()

    fov_circle = canvas.create_oval(config.CAP_W//2-config.RADIUS,config.CAP_H//2-config.RADIUS,
                                    config.CAP_W//2+config.RADIUS,config.CAP_H//2+config.RADIUS,
                                    outline="green")
    lock_circle = canvas.create_oval(0,0,0,0,outline="red")

    def update_overlay():
        canvas.coords(fov_circle,
                      config.CAP_W//2-config.RADIUS,config.CAP_H//2-config.RADIUS,
                      config.CAP_W//2+config.RADIUS,config.CAP_H//2+config.RADIUS)
        try:
            _, boxes = result_q.get_nowait()
            locked_box=None
            for b in boxes:
                if b[4]==infer.locked_id:
                    locked_box=b
                    break
            if locked_box:
                x1,y1,x2,y2,_=locked_box
                canvas.coords(lock_circle,x1,y1,x2,y2)
            else:
                canvas.coords(lock_circle,0,0,0,0)
        except queue.Empty:
            canvas.coords(lock_circle,0,0,0,0)
        overlay.after(30,update_overlay)

    update_overlay()
    return overlay

# =========================
# GUI CS2
# =========================
class App:
    def __init__(self, root, infer: InferenceThread):
        self.root=root
        self.infer=infer
        root.title("CS2 Pointer Assist v4")
        root.geometry("400x600")
        self.build()
        self.update_stats()

    def build(self):
        frm = ttk.Frame(self.root,padding=10)
        frm.pack(fill=tk.BOTH,expand=True)
        ttk.Label(frm,text="Model").pack(anchor="w")
        ttk.Button(frm,text="Load YOLO Model",command=self.load_model).pack(fill="x")
        self.lbl_model=ttk.Label(frm,text="None")
        self.lbl_model.pack(anchor="w",pady=(0,10))

        ttk.Label(frm,text="Resolution Preset").pack(anchor="w")
        self.res_var=tk.StringVar(value="1080p")
        res_combo=ttk.Combobox(frm,textvariable=self.res_var,values=["720p","1080p","1440p","Custom"],state="readonly")
        res_combo.pack(fill="x")
        res_combo.bind("<<ComboboxSelected>>",self.set_resolution)

        ttk.Label(frm,text="Custom Width").pack(anchor="w")
        self.custom_w=ttk.Entry(frm)
        self.custom_w.insert(0,str(config.SCREEN_W))
        self.custom_w.pack(fill="x")
        ttk.Label(frm,text="Custom Height").pack(anchor="w")
        self.custom_h=ttk.Entry(frm)
        self.custom_h.insert(0,str(config.SCREEN_H))
        self.custom_h.pack(fill="x")

        ttk.Label(frm,text="Sensitivity").pack(anchor="w")
        self.sens=ttk.Scale(frm,from_=0.5,to=2,value=config.SENSITIVITY,command=lambda v:setattr(config,'SENSITIVITY',float(v)))
        self.sens.pack(fill="x")
        ttk.Label(frm,text="FOV Radius").pack(anchor="w")
        self.rad=ttk.Scale(frm,from_=20,to=120,value=config.RADIUS,command=lambda v:setattr(config,'RADIUS',int(float(v))))
        self.rad.pack(fill="x")

        ttk.Label(frm,text="Target Part").pack(anchor="w")
        self.part_var=tk.StringVar(value=config.TARGET_PART)
        part_combo=ttk.Combobox(frm,textvariable=self.part_var,values=["Head","Body"],state="readonly")
        part_combo.pack(fill="x")
        part_combo.bind("<<ComboboxSelected>>",self.set_target_part)

        self.auto_var=tk.BooleanVar(value=config.AUTO_SHOOT)
        ttk.Checkbutton(frm,text="Auto Shoot",variable=self.auto_var,command=self.toggle_auto_shoot).pack(fill="x",pady=5)

        self.toggle=ttk.Button(frm,text="Disable",command=self.toggle_enable)
        self.toggle.pack(fill="x",pady=5)

        ttk.Separator(frm).pack(fill="x",pady=10)
        self.lbl_fps=ttk.Label(frm,text="FPS: 0")
        self.lbl_fps.pack(anchor="w")
        self.lbl_lat=ttk.Label(frm,text="Latency: 0 ms")
        self.lbl_lat.pack(anchor="w")

        ttk.Button(frm,text="Quit",command=self.quit).pack(side=tk.BOTTOM,fill="x")
        tk.Button(self.root,text="Show YOLO View",command=self.show_yolo_view).pack(pady=5)

    def show_yolo_view(self):
        def update():
            if not frame_q.empty():
                frame=frame_q.get()
                boxes=self.infer.last_results
                for box in boxes:
                    x1,y1,x2,y2,_=box
                    color=(0,0,255)
                    cv2.rectangle(frame,(int(x1),int(y1)),(int(x2),int(y2)),color,2)
                cv2.imshow("YOLO View",frame)
            if config.RUNNING:
                self.root.after(30,update)
        update()

    def load_model(self):
        path=filedialog.askopenfilename(title="Select YOLO model",filetypes=[("YOLO",".pt .onnx")])
        if path:
            self.infer.load_model(path)
            self.lbl_model.config(text=Path(path).name)

    def toggle_enable(self):
        config.ENABLED = not config.ENABLED
        self.toggle.config(text="Enable" if not config.ENABLED else "Disable")

    def toggle_auto_shoot(self):
        config.AUTO_SHOOT=self.auto_var.get()

    def set_target_part(self,_):
        config.TARGET_PART=self.part_var.get()

    def set_resolution(self,_):
        preset=self.res_var.get()
        if preset=="720p":
            config.SCREEN_W,config.SCREEN_H=1280,720
        elif preset=="1080p":
            config.SCREEN_W,config.SCREEN_H=1920,1080
        elif preset=="1440p":
            config.SCREEN_W,config.SCREEN_H=2560,1440
        elif preset=="Custom":
            try:
                config.SCREEN_W=int(self.custom_w.get())
                config.SCREEN_H=int(self.custom_h.get())
            except:
                pass

    def update_stats(self):
        self.lbl_fps.config(text=f"FPS: {stats['fps']:.1f}")
        self.lbl_lat.config(text=f"Latency: {stats['latency_ms']:.1f} ms")
        self.root.after(200,self.update_stats)

    def quit(self):
        config.RUNNING=False
        self.root.destroy()

# =========================
# Main CS2
# =========================
def main():
    sct = mss.mss()
    inf = InferenceThread()
    inf.start()

    # Threads en arrière-plan
    threading.Thread(target=pointer_controller, args=(inf,), daemon=True).start()
    threading.Thread(target=mouse_listener, args=(inf,), daemon=True).start()

    # Tkinter GUI dans le main thread
    root = tk.Tk()
    app = App(root, inf)  # toutes les variables Tkinter ici

    # Overlay aussi depuis main thread
    overlay = create_overlay_thread(inf)

    # Capture MSS avec after()
    def capture_frame():
        if config.RUNNING:
            cx = config.SCREEN_W // 2
            cy = config.SCREEN_H // 2
            region = {"left": cx - config.CAP_W // 2,
                      "top": cy - config.CAP_H // 2,
                      "width": config.CAP_W,
                      "height": config.CAP_H}
            frame = np.array(sct.grab(region))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if not frame_q.full():
                frame_q.put(frame)
            root.after(1, capture_frame)

    root.after(1, capture_frame)
    root.mainloop()
    config.RUNNING = False
    cv2.destroyAllWindows()

if __name__=="__main__":
    main()
