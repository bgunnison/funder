import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import csv

class PLPlotter:
    def __init__(self, root, totals_csv_file, csv_file, stocks):
        self.root = root
        self.totals_csv_file = totals_csv_file
        self.csv_file = csv_file
        self.stocks = stocks

    def plot(self):
        try:
            timestamps = []
            pls = []
            
            # Start P/L at 0
            pls.append(0.0)
            # Use a dummy timestamp for the initial 0 value
            with open(self.totals_csv_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                first_row = next(reader, None)
                if first_row:
                    timestamps.append(datetime.strptime(first_row[0], '%Y-%m-%d %H:%M:%S'))
                else:
                    timestamps.append(datetime.now())

            with open(self.totals_csv_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    timestamps.append(datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'))
                    pls.append(float(row[1]))

            if len(pls) <= 1:
                messagebox.showinfo("No Data", "No P/L data to plot.")
                return

            plot_window = tk.Toplevel(self.root)
            plot_window.title("P/L Over Time")

            button_frame = tk.Frame(plot_window)
            button_frame.pack(fill=tk.X)

            for stock in self.stocks:
                button = tk.Button(button_frame, text=stock, command=lambda s=stock: self.plot_stock_pl(s))
                button.pack(side=tk.LEFT, padx=5, pady=5)

            fig = plt.figure(figsize=(10, 6))
            plt.plot(timestamps, pls, marker='o')
            plt.xlabel("Date from inception")
            plt.ylabel("Profit/Loss ($)")
            plt.title("Portfolio P/L Over Time")
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=plot_window)
            canvas.draw()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        except FileNotFoundError:
            messagebox.showerror("Error", "P/L log file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to plot P/L: {e}")

    def plot_stock_pl(self, ticker):
        try:
            timestamps = []
            pls = []

            with open(self.csv_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if row[2] == ticker:
                        timestamps.append(datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'))
                        pls.append(float(row[7]))

            if not timestamps:
                messagebox.showinfo("No Data", f"No P/L data to plot for {ticker}.")
                return

            plot_window = tk.Toplevel(self.root)
            plot_window.title(f"P/L Over Time for {ticker}")

            fig = plt.figure(figsize=(10, 6))
            plt.plot(timestamps, pls, marker='o')
            plt.xlabel("Date from inception")
            plt.ylabel("Profit/Loss ($)")
            plt.title(f"Portfolio P/L Over Time for {ticker}")
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=plot_window)
            canvas.draw()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        except FileNotFoundError:
            messagebox.showerror("Error", "P/L log file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to plot P/L for {ticker}: {e}")