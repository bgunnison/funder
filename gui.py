import tkinter as tk
from tkinter import messagebox
from datetime import datetime

class StockPortfolioGUI:
    def __init__(self, root, add_stock_callback, load_portfolio_callback, on_stock_data_change_callback, delete_row_callback, plot_pl_callback):
        self.root = root
        self.root.title("AI Infrastructure Stock Portfolio Tracker")
        self.root.configure(bg="#f0f0f0")

        self.entry_rows = []
        self.add_stock_callback = add_stock_callback
        self.load_portfolio_callback = load_portfolio_callback
        self.on_stock_data_change_callback = on_stock_data_change_callback
        self.delete_row_callback = delete_row_callback
        self.plot_pl_callback = plot_pl_callback

        # Fonts
        self.font_label = ("Segoe UI", 10)
        self.font_button = ("Segoe UI", 10, "bold")
        self.font_header = ("Segoe UI", 10, "bold")

        # Pastel colors to rotate per stock row (matches button theme)
        self.row_colors = [
            "#c8e6c9",  # light green
            "#bbdefb",  # light blue
            "#ffcdd2",  # light pink
            "#ffecb3",  # light amber
            "#e1bee7",  # light purple
        ]

        self._create_widgets()

    def _create_widgets(self):
        self._create_input_frame()
        self._create_table_frame()
        self._create_buttons()
        self._create_output_text()

    def _create_input_frame(self):
        self.frame_input = tk.Frame(self.root, bg="#f0f0f0", relief=tk.RAISED, borderwidth=1)
        self.frame_input.pack(anchor="w", pady=10, padx=10, fill="x")

        self.label_investment = tk.Label(self.frame_input, text="Total Investment ($):", bg="#f0f0f0", font=self.font_label)
        self.label_investment.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_investment = tk.Entry(self.frame_input, font=self.font_label)
        self.entry_investment.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.entry_investment.insert(0, "100000")

        self.label_last_update = tk.Label(self.frame_input, text="Last Updated:", bg="#f0f0f0", font=self.font_label)
        self.label_last_update.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.entry_last_update = tk.Entry(self.frame_input, width=20, font=self.font_label)
        self.entry_last_update.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.entry_last_update.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        self.label_total_pl = tk.Label(self.frame_input, text="Total P/L ($):", bg="#f0f0f0", font=self.font_label)
        self.label_total_pl.grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.entry_total_pl = tk.Entry(self.frame_input, width=20, font=self.font_label)
        self.entry_total_pl.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self.entry_total_pl.config(state='readonly')

    def _create_table_frame(self):
        self.frame_table = tk.Frame(self.root, bg="#ffffff", relief=tk.SUNKEN, borderwidth=1)
        self.frame_table.pack(pady=10, padx=10, fill="both", expand=True)

        headers = ["Row #", "% Invested", "Sym", "Name", "Shares Owned", "Purchase Price",
                   "Current Price", "Profit/Loss", "Date Purchased", "Days Owned"]
        for col, header in enumerate(headers):
            tk.Label(self.frame_table, text=header, font=self.font_header, bg="#e0e0e0").grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

    def _create_buttons(self):
        button_frame = tk.Frame(self.root, bg="#f0f0f0")
        button_frame.pack(pady=5, padx=10, fill="x")

        self.button_add_row = tk.Button(button_frame, text="Add Stock Row", command=self.add_stock_row, font=self.font_button, bg="#c8e6c9", fg="#000000")
        self.button_add_row.pack(side=tk.LEFT, padx=5)

        self.button_load = tk.Button(button_frame, text="Load Saved Portfolio", command=self.load_portfolio_callback, font=self.font_button, bg="#bbdefb", fg="#000000")
        self.button_load.pack(side=tk.LEFT, padx=5)

        self.button_plot = tk.Button(button_frame, text="Plot P/L", command=self.plot_pl_callback, font=self.font_button, bg="#ffcdd2", fg="#000000")
        self.button_plot.pack(side=tk.LEFT, padx=5)

        delete_frame = tk.Frame(button_frame, bg="#f0f0f0")
        delete_frame.pack(side=tk.RIGHT, padx=5)

        self.button_delete_row = tk.Button(delete_frame, text="Delete Row", command=self._on_delete_row, font=self.font_button, bg="#ffab91", fg="#000000")
        self.button_delete_row.pack(side=tk.LEFT)

        self.entry_delete_row = tk.Entry(delete_frame, width=5, font=self.font_label)
        self.entry_delete_row.pack(side=tk.LEFT, padx=5)

    def _create_output_text(self):
        self.text_output = tk.Text(self.root, height=5, width=90, font=self.font_label, relief=tk.SUNKEN, borderwidth=1)
        self.text_output.pack(pady=10, padx=10, fill="x")

    def add_stock_row(self, ticker="", perc="", shares=0, purchase_price="", current_price=0, purchase_date=None, company_name="-"):
        row_num = len(self.entry_rows) + 1
        row_entries = []
        # Choose a pastel background color for this row's symbol field only
        symbol_bg = self.row_colors[(row_num - 1) % len(self.row_colors)]

        def create_editable_entry(column, initial_text, width, field_name, bg=None):
            str_var = tk.StringVar(value=str(initial_text))
            entry_kwargs = {
                'width': width,
                'textvariable': str_var,
                'font': self.font_label,
                'fg': '#000000',
            }
            if bg:
                entry_kwargs['bg'] = bg
                entry_kwargs['disabledbackground'] = bg
            else:
                entry_kwargs['bg'] = '#ffffff'
            entry = tk.Entry(self.frame_table, **entry_kwargs)
            entry.grid(row=row_num, column=column, padx=5, pady=2, sticky="nsew")
            # Use dynamic row resolution so callbacks stay correct after deletions/reordering
            str_var.trace_add(
                "write",
                lambda name, index, mode, sv=str_var, col=column, ent=entry: self._on_entry_change_dynamic(sv, col, ent)
            )
            return entry, str_var

        def create_readonly_entry(column, text, width):
            entry = tk.Entry(self.frame_table, width=width, font=self.font_label, bg="#f0f0f0", fg="#000000")
            entry.grid(row=row_num, column=column, padx=5, pady=2, sticky="nsew")
            entry.insert(0, text)
            entry.config(state='readonly')
            return entry

        # Row number (readonly label)
        row_entries.append(create_readonly_entry(0, str(row_num), 5))

        # % Invested (editable) now at column 1
        perc_entry, perc_str_var = create_editable_entry(1, str(perc), 10, "perc_invested")
        row_entries.append(perc_entry)

        # Sym (editable) now at column 2
        ticker_entry, ticker_str_var = create_editable_entry(2, ticker, 10, "ticker", bg=symbol_bg)
        row_entries.append(ticker_entry)

        # Name (readonly) now at column 3
        row_entries.append(create_readonly_entry(3, company_name, 20))

        # Shares Owned (editable) now at column 4
        shares_entry, shares_str_var = create_editable_entry(4, str(shares), 12, "shares_owned")
        row_entries.append(shares_entry)

        # Purchase Price (editable) now at column 5
        pprice_entry, pprice_str_var = create_editable_entry(5, str(purchase_price), 15, "purchase_price")
        row_entries.append(pprice_entry)

        # Current Price (editable - for testing) now at column 6
        current_price_entry, current_price_str_var = create_editable_entry(6, f"{current_price:.2f}", 15, "current_price_debug")
        row_entries.append(current_price_entry)

        # Profit/Loss (readonly) now at column 7
        row_entries.append(create_readonly_entry(7, f"{(float(current_price) - float(purchase_price or 0)) * shares:.2f}", 15))
        
        # Date Purchased (editable) now at column 8
        if not purchase_date:
            purchase_date_str = ""
        else:
            purchase_date_str = purchase_date
        pdate_entry, pdate_str_var = create_editable_entry(8, purchase_date_str, 15, "purchase_date")
        row_entries.append(pdate_entry)

        # Days Owned (readonly) now at column 9
        days_owned_value: str
        if purchase_date_str:
            try:
                days_owned = (datetime.now() - datetime.strptime(purchase_date_str, '%Y-%m-%d')).days
                days_owned_value = str(days_owned)
            except Exception:
                days_owned_value = ""
        else:
            days_owned_value = ""
        row_entries.append(create_readonly_entry(9, days_owned_value, 12))

        self.entry_rows.append(row_entries)
        # Ensure symbol colors are consistent after adding
        self._recolor_symbol_column()

    def _on_entry_change(self, str_var, col, row_num):
        field_map = {
            1: "perc_invested",
            2: "ticker",
            4: "shares_owned",
            5: "purchase_price",
            8: "purchase_date"
        }
        field_name = field_map.get(col)
        if field_name and self.on_stock_data_change_callback:
            new_value = str_var.get()
            self.on_stock_data_change_callback(row_num - 1, field_name, new_value)

    def _on_entry_change_dynamic(self, str_var, col, entry_widget):
        """Resolve row index from the widget's current grid position.
        This keeps callbacks accurate after row deletions/reindexing.
        """
        try:
            info = entry_widget.grid_info()
            # Grid rows are 1-based in our table (row 0 is header)
            current_row = int(info.get('row', 1)) - 1
        except Exception:
            current_row = 0
        field_map = {
            1: "perc_invested",
            2: "ticker",
            4: "shares_owned",
            5: "purchase_price",
            8: "purchase_date"
        }
        field_name = field_map.get(col)
        if field_name and self.on_stock_data_change_callback:
            new_value = str_var.get()
            self.on_stock_data_change_callback(current_row, field_name, new_value)

    def clear_rows(self):
        for row in self.entry_rows:
            for widget in row:
                widget.destroy()
        self.entry_rows = []

    def delete_row_from_ui(self, index: int) -> None:
        if index < 0 or index >= len(self.entry_rows):
            return
        row_widgets = self.entry_rows.pop(index)
        for widget in row_widgets:
            widget.destroy()
        for i, row in enumerate(self.entry_rows):
            for col_idx, widget in enumerate(row):
                widget.grid_configure(row=i + 1)
                if col_idx == 0:
                    widget.config(state='normal')
                    widget.delete(0, tk.END)
                    widget.insert(0, str(i + 1))
                    widget.config(state='readonly')
        # Recolor the symbol column to match new ordering
        self._recolor_symbol_column()

    def _on_delete_row(self):
        row_str = self.entry_delete_row.get().strip()
        if not row_str:
            messagebox.showerror("Error", "Please enter a row number to delete.")
            return
        try:
            row_index = int(row_str) - 1
        except ValueError:
            messagebox.showerror("Error", "Invalid row number. Please enter a numeric value.")
            return
        if row_index < 0 or row_index >= len(self.entry_rows):
            messagebox.showerror("Error", "Row number out of range.")
            return
        if self.delete_row_callback:
            self.delete_row_callback(row_index)
        self.entry_delete_row.delete(0, tk.END)

    def update_totals(self, total_pl, total_value, current_time):
        self.root.title(f"AI Stock Portfolio Tracker - Total Value: ${total_value:,.2f}")
        self.entry_last_update.config(state='normal')
        self.entry_last_update.delete(0, tk.END)
        self.entry_last_update.insert(0, current_time)
        self.entry_last_update.config(state='readonly')
        self.entry_total_pl.config(state='normal')
        self.entry_total_pl.delete(0, tk.END)
        self.entry_total_pl.insert(0, f"{total_pl:,.2f}")
        self.entry_total_pl.config(state='readonly')

    def _recolor_symbol_column(self) -> None:
        """Apply rotating pastel background to only the Sym (ticker) column.
        Keeps other columns unchanged and updates colors after add/delete.
        """
        try:
            for i, row in enumerate(self.entry_rows):
                color = self.row_colors[i % len(self.row_colors)]
                if len(row) > 2:
                    sym_entry = row[2]
                    try:
                        sym_entry.configure(bg=color)
                    except Exception:
                        pass
        except Exception:
            pass
