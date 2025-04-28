import serial
import time
import csv
import os
import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

def open_serial_connection(port):
    ser = serial.Serial(f'COM{port}', 9600, timeout=1)
    ser.flush()
    return ser

def get_weight(ser):
    ser.write(b'\x4F\x38\r\n')
    start_time = time.time()
    while time.time() - start_time < 2:
        line = ser.readline().decode('utf-8').rstrip()
        if line.startswith('+'):
            weight_data = line.split()
            return float(weight_data[1])
    return None

class BalanceLoggerApp:
    def __init__(self, root):
        self.upload_to_github = False
        self.repo_path = os.path.dirname(os.path.abspath(__file__))  # Assume repo is same as script folder
        
        self.root = root
        self.root.title("Balance Logger")

        # --- Title Banner
        title_label = ttk.Label(root, text="Balance Logger", font=("Segoe UI", 20, "bold"), bootstyle="primary")
        title_label.pack(pady=(10, 20))

        # --- Main frame
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        # --- Input section
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=X, pady=5)

        ttk.Label(input_frame, text="Number of balances (max 8):").grid(row=0, column=0, sticky=E, padx=5, pady=5)
        self.num_balances_var = ttk.IntVar(value=1)
        self.num_balances_var.trace_add("write", lambda *args: self.setup_balances())
        ttk.Entry(input_frame, textvariable=self.num_balances_var, width=5).grid(row=0, column=1, sticky=W, pady=5)

        self.balance_frame = ttk.Frame(main_frame)
        self.balance_frame.pack(fill=X, pady=10)

        ttk.Label(input_frame, text="Frequency (seconds):").grid(row=1, column=0, sticky=E, padx=5, pady=5)
        self.freq_var = ttk.IntVar(value=10)
        ttk.Entry(input_frame, textvariable=self.freq_var, width=10).grid(row=1, column=1, sticky=W, pady=5)

        ttk.Label(input_frame, text="Filename:").grid(row=2, column=0, sticky=E, padx=5, pady=5)
        self.filename_var = ttk.StringVar(value="test_run")
        ttk.Entry(input_frame, textvariable=self.filename_var, width=20).grid(row=2, column=1, sticky=W, pady=5)

        ttk.Label(input_frame, text="Save Folder (optional):").grid(row=3, column=0, sticky=E, padx=5, pady=5)
        self.folder_var = ttk.StringVar()
        ttk.Entry(input_frame, textvariable=self.folder_var, width=20).grid(row=3, column=1, sticky=W, pady=5)
        ttk.Button(input_frame, text="Browse", command=self.browse_folder).grid(row=3, column=2, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 20))

        self.upload_button = ttk.Button(button_frame, text="Upload to GitHub", command=self.enable_github_upload, bootstyle="info")
        self.upload_button.pack(side=LEFT, padx=10)

        self.start_button = ttk.Button(button_frame, text="Start Measurements", command=self.start_measurements, bootstyle="success")
        self.start_button.pack(side=LEFT, padx=10)

        self.stop_button = ttk.Button(button_frame, text="Stop and Exit", command=self.stop_measurements, bootstyle="danger")
        self.stop_button.pack(side=LEFT, padx=10)

        # --- Log output
        self.log = ttk.ScrolledText(main_frame, width=80, height=20, font=("Consolas", 10))
        self.log.pack(fill=BOTH, expand=True)

        self.ser_objects = []
        self.running = False

        self.setup_balances()  # <-- Add this here!

    def stop_measurements(self):
        self.running = False
        self.log_message("Stopping measurements...")
        # Wait a little for the measuring thread to properly finish
        self.root.after(1000, self.root.destroy)

    def enable_github_upload(self):
        self.upload_to_github = True
        self.log_message("Upload to GitHub enabled.")

    def browse_folder(self):
        folder_selected = ttk.filedialog.askdirectory()
        if folder_selected:
            self.folder_var.set(folder_selected)

    def setup_balances(self):
        for widget in self.balance_frame.winfo_children():
            widget.destroy()

        self.port_vars = []
        self.name_vars = []

        for i in range(self.num_balances_var.get()):
            ttk.Label(self.balance_frame, text=f"COM Port for Balance {i+1}:").grid(row=i, column=0, sticky=E, padx=5, pady=2)
            port_var = ttk.StringVar()
            ttk.Entry(self.balance_frame, textvariable=port_var, width=10).grid(row=i, column=1, sticky=W, padx=5)

            ttk.Label(self.balance_frame, text="Name (optional):").grid(row=i, column=2, sticky=E, padx=5, pady=2)
            name_var = ttk.StringVar()
            ttk.Entry(self.balance_frame, textvariable=name_var, width=15).grid(row=i, column=3, sticky=W, padx=5)

            self.port_vars.append(port_var)
            self.name_vars.append(name_var)

    def log_message(self, message):
        self.log.configure(state='normal')
        self.log.insert('end', f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log.see('end')
        self.log.configure(state='disabled')

    def start_measurements(self):
        if self.running:
            ttk.messagebox.showinfo("Already running", "Measurements are already running.")
            return

        self.running = True
        threading.Thread(target=self.measure_loop, daemon=True).start()

    def git_push(self):
        try:
            subprocess.run(["git", "-C", self.repo_path, "add", "."], check=True)
            subprocess.run(["git", "-C", self.repo_path, "commit", "-m", "Update CSV automatically"], check=True)
            subprocess.run(["git", "-C", self.repo_path, "push"], check=True)
            self.log_message("Pushed updated CSV to GitHub.")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Git push failed: {e}")

    def measure_loop(self):
        try:
            num_balances = self.num_balances_var.get()
            frequency = self.freq_var.get()
            filename = self.filename_var.get().strip()
            custom_folder = self.folder_var.get().strip()

            if not filename or " " in filename:
                self.log_message("Invalid filename. No spaces allowed.")
                self.running = False
                return

            # Save folder setup
            if not custom_folder:
                base_folder = os.path.dirname(os.path.abspath(__file__))
                data_folder = os.path.join(base_folder, 'data')
            else:
                data_folder = custom_folder

            os.makedirs(data_folder, exist_ok=True)
            filepath = os.path.join(data_folder, f"{filename}.csv")
            self.log_message(f"Saving CSV to: {filepath}")

            # COM ports and balance names
            com_ports = [p.get() for p in self.port_vars]
            balance_names = [n.get() if n.get().strip() else f"COM{p.get()}" for p, n in zip(self.port_vars, self.name_vars)]

            fieldnames = ['Timestamp'] + [f'{name}_Weight' for name in balance_names]

            # Open serial ports
            self.ser_objects = []
            for port in com_ports:
                self.ser_objects.append(open_serial_connection(port))

            # Write CSV header
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

            self.log_message("Starting measurements...")

            while self.running:
                print_data = {"Timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}
                for i, ser in enumerate(self.ser_objects):
                    weight = get_weight(ser)
                    print_data[f'{balance_names[i]}_Weight'] = weight
                    self.log_message(f"Measured {balance_names[i]}: {weight}")

                with open(filepath, 'a', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writerow(print_data)

                # === AFTER writing new row, check if we need to upload ===
                if self.upload_to_github:
                    self.git_push()

                time.sleep(frequency)


        except Exception as e:
            self.log_message(f"Error: {str(e)}")
        finally:
            for ser in self.ser_objects:
                try:
                    ser.close()
                except:
                    pass
            self.running = False

if __name__ == "__main__":
    app = ttk.Window(themename="flatly")
    BalanceLoggerApp(app)
    app.mainloop()
