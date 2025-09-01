import queue
import tkinter as tk
from tkinter import messagebox
import schedule
import time
import threading
from datetime import datetime
from gui import StockPortfolioGUI
from portfolio_manager import PortfolioManager
from data_fetcher import DataFetcher
from logger import PortfolioLogger
from plotter import PLPlotter

class StockPortfolioTracker:
    def __init__(self):
        print("Initializing Stock Portfolio Tracker...")
        
        # Initialize components first
        self.root = tk.Tk()
        self.portfolio = PortfolioManager()
        self.fetcher = DataFetcher()
        self.logger = PortfolioLogger()
        self.running = False
        self.gui_update_queue = queue.Queue()
        # Prevent concurrent updates
        self._updating = False
        self._update_lock = threading.Lock()
        # Track scheduled GUI callbacks and closing state to avoid Tk errors on exit
        self._after_id = None
        self._closing = False
        # Intercept window close to cancel scheduled callbacks cleanly
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Create GUI
        print("Creating GUI...")
        self.gui = StockPortfolioGUI(
            self.root,
            self.add_stock,
            self.load_portfolio,
            self.on_stock_data_change,
            self.delete_stock_row,
            self.plot_pl,
            self.update_now,
        )
        
        # Removed the explicit "Initialize/Update Portfolio" button. The application now
        # automatically loads the saved portfolio (if available) and begins hourly
        # updates on startup. Any manual initialization can still be triggered
        # programmatically via `initialize_portfolio_button_click` if needed.
        
        # Start GUI update processing
        self._after_id = self.root.after(100, self.process_gui_queue)
        
        # Show initial message via queued logger (thread-safe)
        self._log("Application started. Loading saved portfolio if available...\n")

        print("GUI created successfully")

        # Automatically load the saved portfolio (if any) on startup
        try:
            self.load_portfolio()
            # After loading the portfolio, trigger an immediate update to fetch current prices
            if self.portfolio.stocks:
                # Start the hourly scheduling if not already running
                if not self.running:
                    self._start_tracking_threads()
                # Perform an immediate update in a background thread to avoid blocking the GUI
                threading.Thread(target=self.update_portfolio, daemon=True).start()
        except Exception as e:
            # Log any errors during startup loading but continue execution
            self._log(f"Error loading saved portfolio on startup: {e}\n")

    def plot_pl(self):
        plotter = PLPlotter(self.root, self.logger.totals_csv_file, self.logger.csv_file, self.portfolio.stocks)
        plotter.plot()

    def update_now(self):
        # Do nothing if an update is already running
        if self._updating:
            self._log("Update already in progress. Please wait...\n")
            return
        try:
            threading.Thread(target=self.update_portfolio, daemon=True).start()
        except Exception as e:
            self._log(f"Error starting update: {e}\n")

    def initialize_portfolio_button_click(self):
        """Handle initialize button click"""
        try:
            self._log("Initializing portfolio...\n")
            self.initialize_portfolio()
            
            # Start tracking after initialization
            if not self.running:
                self._start_tracking_threads()
                self._log("Started automatic hourly updates.\n")
            else:
                # Trigger immediate update
                threading.Thread(target=self.update_portfolio, daemon=True).start()
                
        except Exception as e:
            self._log(f"Error initializing: {e}\n")
            messagebox.showerror("Error", f"Failed to initialize: {e}")

    def add_stock(self, ticker, perc, shares, purchase_price, current_price, company_name):
        try:
            self.portfolio.add_stock(ticker, perc, shares, purchase_price, datetime.now().strftime('%Y-%m-%d'))
            self.logger.log_portfolio(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ticker, perc, company_name, shares, purchase_price, current_price,
                (float(current_price) - float(purchase_price)) * shares,
                datetime.now().strftime('%Y-%m-%d'),
                0,
                self.portfolio.calculate_totals(self.fetcher.get_current_prices(self.portfolio.stocks))[1]
            )
            self._log(f"Added {ticker} to portfolio.\n")
        except Exception as e:
            self._log(f"Error adding stock: {e}\n")
            messagebox.showerror("Error", f"Error adding stock: {e}")

    def load_portfolio(self):
        try:
            self._log("Loading saved portfolio...\n")
            config = self.logger.load_portfolio()
            
            if config:
                self.portfolio.total_investment = config["total_investment"]
                self.portfolio.stocks = config["stocks"]
                self.portfolio.allocations = config["allocations"]
                self.portfolio.shares = config["shares"]
                self.portfolio.initial_prices = config["initial_prices"]
                self.portfolio.purchase_dates = config.get("purchase_dates", [datetime.now().strftime('%Y-%m-%d')] * len(self.portfolio.stocks))

                # Load any saved company names from the config and populate
                # the fetcher's cache. This avoids re-querying the API on
                # startup.
                company_names = config.get("company_names")
                if company_names and len(company_names) == len(self.portfolio.stocks):
                    for ticker, name in zip(self.portfolio.stocks, company_names):
                        if name:
                            self.fetcher.company_cache[ticker] = name

                # If any ticker is missing a company name (i.e., not in the
                # cache or equal to the ticker symbol), attempt to fetch it
                # from the API and update both the cache and the JSON file. This
                # ensures that names are stored in the JSON for future
                # sessions and displayed in the UI.
                updated_names = False
                fetched_names: list[str] = []
                for ticker in self.portfolio.stocks:
                    cached_name = self.fetcher.company_cache.get(ticker)
                    # Determine if we need to fetch the name: either there's
                    # no cached value or it's identical to the ticker.
                    if not cached_name or cached_name.upper() == ticker.upper():
                        try:
                            name = self.fetcher.get_company_name(ticker)
                        except Exception:
                            name = ticker
                        # Update the cache regardless of whether the call
                        # succeeded. Use the ticker as a fallback.
                        self.fetcher.company_cache[ticker] = name
                        fetched_names.append(name)
                        # Mark as updated if a new name is obtained
                        if name.upper() != ticker.upper():
                            updated_names = True
                    else:
                        fetched_names.append(cached_name)

                # Persist newly fetched company names to the JSON configuration
                # to avoid repeated API calls on future launches. Only save if
                # at least one name differs from its ticker.
                if updated_names:
                    try:
                        self.logger.save_portfolio(
                            self.portfolio.total_investment,
                            self.portfolio.stocks,
                            self.portfolio.allocations,
                            self.portfolio.shares,
                            self.portfolio.initial_prices,
                            self.portfolio.purchase_dates,
                            company_names=fetched_names,
                        )
                    except Exception as e:
                        # Log but don't interrupt the loading process
                        self._log(f"Warning: could not save updated company names: {e}\n")

                self.gui.entry_investment.delete(0, tk.END)
                self.gui.entry_investment.insert(0, str(self.portfolio.total_investment))
                self.gui.clear_rows()

                # Show saved data immediately with cached prices
                for ticker, perc, shares, initial_price, pdate in zip(
                    self.portfolio.stocks, self.portfolio.allocations, self.portfolio.shares,
                    self.portfolio.initial_prices, self.portfolio.purchase_dates
                ):
                    company_name = self.fetcher.company_cache.get(ticker, ticker)
                    self.gui.add_stock_row(ticker, perc, shares, initial_price, initial_price, pdate, company_name)

                # Start an asynchronous process to fetch and populate missing
                # company names without blocking the GUI. This will update the
                # UI and save the names to the JSON file once retrieved.
                def fetch_missing_names_on_load():
                    updated_names = False
                    new_names: list[str] = []
                    for idx, ticker in enumerate(self.portfolio.stocks):
                        cached_name = self.fetcher.company_cache.get(ticker)
                        if not cached_name or cached_name.upper() == ticker.upper():
                            # Log that we are fetching the name
                            self.gui_update_queue.put({
                                'type': 'log_message',
                                'message': f'Fetching company name for {ticker}...\n'
                            })
                            try:
                                name = self.fetcher.get_company_name(ticker)
                            except Exception as e:
                                name = ticker
                            self.fetcher.company_cache[ticker] = name
                            new_names.append(name)
                            # Update the UI with the fetched name
                            self.gui_update_queue.put({
                                'type': 'company_name_update',
                                'row_index': idx,
                                'company_name': name
                            })
                            self.gui_update_queue.put({
                                'type': 'log_message',
                                'message': f'Retrieved company name for {ticker}: {name}\n'
                            })
                            if name.upper() != ticker.upper():
                                updated_names = True
                        else:
                            new_names.append(cached_name)

                    if updated_names:
                        try:
                            self.logger.save_portfolio(
                                self.portfolio.total_investment,
                                self.portfolio.stocks,
                                self.portfolio.allocations,
                                self.portfolio.shares,
                                self.portfolio.initial_prices,
                                self.portfolio.purchase_dates,
                                company_names=new_names,
                            )
                        except Exception as e:
                            self.gui_update_queue.put({
                                'type': 'log_message',
                                'message': f'Warning: could not save updated company names: {e}\n'
                            })

                threading.Thread(target=fetch_missing_names_on_load, daemon=True).start()

                self._log(f"Loaded {len(self.portfolio.stocks)} stocks. Hourly updates will run automatically.\n")

                # Start tracking if not already running
                if not self.running:
                    self._start_tracking_threads()
                    
            else:
                self._log("No saved portfolio found.\n")
                
        except Exception as e:
            self._log(f"Failed to load portfolio: {e}\n")
            messagebox.showerror("Error", f"Failed to load portfolio: {e}")

    def initialize_portfolio(self):
        try:
            total_investment = float(self.gui.entry_investment.get())
            stocks, allocations, purchase_prices, purchase_dates = [], [], [], []
            

            # Each row in the GUI now contains 10 columns:
            # 0: Row number (readonly), 1: % invested, 2: ticker, 3: company name,
            # 4: shares owned (readonly), 5: purchase price, 6: current price
            # (readonly), 7: profit/loss (readonly), 8: purchase date, 9: days
            # owned (readonly). Use the correct indices when reading inputs.
            for row in self.gui.entry_rows:
                # Percentage invested (column 1)
                perc = row[1].get()
                # Ticker symbol (column 2)
                ticker = row[2].get().replace(" ", "").upper()
                # Purchase price (column 5)
                pprice = row[5].get()
                # Purchase date (column 8)
                pdate = row[8].get()
                
                if not ticker or not perc:
                    continue  # Skip empty rows
                    
                stocks.append(ticker)
                allocations.append(float(perc))
                purchase_prices.append(float(pprice) if pprice else None)
                # Preserve the purchase date if provided; otherwise store an
                # empty string to indicate that no purchase date has been set
                purchase_dates.append(pdate if pdate else "")

            if not stocks:
                raise ValueError("No stocks entered. Add at least one stock.")

            self._log(f"Fetching prices for {len(stocks)} stocks...\n")
            
            # Fetch prices in background
            def fetch_and_init():
                try:
                    prices = self.fetcher.get_current_prices(stocks)
                    
                    self.portfolio.initialize_portfolio(
                        total_investment, stocks, allocations, prices, purchase_prices, purchase_dates
                    )

                    # Fetch company names once for each ticker. These names will
                    # be saved into the portfolio configuration so they persist
                    # across sessions and avoid repeated API calls on load.
                    company_names = []
                    for ticker in stocks:
                        name = self.fetcher.get_company_name(ticker)
                        company_names.append(name)

                    # Save portfolio along with company names to the JSON config
                    self.logger.save_portfolio(
                        self.portfolio.total_investment,
                        self.portfolio.stocks,
                        self.portfolio.allocations,
                        self.portfolio.shares,
                        self.portfolio.initial_prices,
                        self.portfolio.purchase_dates,
                        company_names=company_names
                    )
                    
                    # Update GUI with fetched company names
                    for i, (ticker, company_name) in enumerate(zip(stocks, company_names)):
                        if company_name and company_name != ticker:
                            self.gui_update_queue.put({
                                'type': 'company_name_update',
                                'row_index': i,
                                'company_name': company_name
                            })
                    
                    self._log("Portfolio initialized successfully!\n")
                    
                    # Trigger immediate update
                    self.update_portfolio()
                    
                except Exception as e:
                    self._log(f"Error during initialization: {e}\n")
            
            threading.Thread(target=fetch_and_init, daemon=True).start()
            
        except ValueError as e:
            self._log(f"Input error: {e}\n")
            messagebox.showerror("Error", str(e))
        except Exception as e:
            self._log(f"Error: {e}\n")
            messagebox.showerror("Error", f"An error occurred: {e}")

    def update_portfolio(self):
        if self._closing:
            return
        if not self.portfolio.stocks:
            self._log("No stocks to update.\n")
            return

        # Acquire non-blocking lock to prevent concurrent updates
        if not self._update_lock.acquire(blocking=False):
            self._log("Update already in progress. Skipping.\n")
            return
        self._updating = True
        # Notify GUI to show spinner
        try:
            self.gui_update_queue.put({'type': 'update_status', 'updating': True})
        except Exception:
            pass

        self._log(f"Updating prices at {datetime.now().strftime('%H:%M:%S')}...\n")

        try:
            prices = self.fetcher.get_current_prices(self.portfolio.stocks)
            
            if not prices:
                self._log("No prices fetched.\n")
                return
                
            # Update each stock row
            for i, (ticker, shares, initial_price, pdate) in enumerate(zip(
                self.portfolio.stocks, self.portfolio.shares,
                self.portfolio.initial_prices, self.portfolio.purchase_dates
            )):
                current_price = prices.get(ticker)
                if current_price is None:
                    continue
                    
                initial_price = float(initial_price) if initial_price else 0.0
                current_price = float(current_price)
                shares = float(shares) if shares else 0.0
                
                pl = (current_price - initial_price) * shares
                
                # Compute days owned only if a purchase date is provided; otherwise leave blank
                if pdate and str(pdate).strip():
                    try:
                        days_owned = (datetime.now() - datetime.strptime(str(pdate), '%Y-%m-%d')).days
                    except Exception:
                        days_owned = ""
                else:
                    days_owned = ""
                
                self.gui_update_queue.put({
                    'type': 'stock_row_update',
                    'row_index': i,
                    'current_price': current_price,
                    'pl': pl,
                    'days_owned': days_owned
                })
            
            # Calculate and update totals
            total_pl, total_value = self.portfolio.calculate_totals(prices)
            self.gui_update_queue.put({
                'type': 'total_update',
                'total_pl': total_pl,
                'total_value': total_value,
                'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # Log totals
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logger.log_totals(ts, total_pl, total_value)

            # Also log per‑stock snapshot so the plotter has data to draw
            try:
                for i, (ticker, shares, initial_price, pdate) in enumerate(
                    zip(self.portfolio.stocks, self.portfolio.shares, self.portfolio.initial_prices, self.portfolio.purchase_dates)
                ):
                    current_price = prices.get(ticker)
                    if current_price is None:
                        continue
                    allocation = 0.0
                    try:
                        allocation = float(self.portfolio.allocations[i]) if i < len(self.portfolio.allocations) else 0.0
                    except Exception:
                        allocation = 0.0
                    try:
                        name = self.fetcher.company_cache.get(ticker, ticker)
                    except Exception:
                        name = ticker
                    try:
                        shares_f = float(shares) if shares else 0.0
                        init_price_f = float(initial_price) if initial_price else 0.0
                        curr_price_f = float(current_price)
                        pl_val = (curr_price_f - init_price_f) * shares_f
                    except Exception:
                        shares_f = 0.0
                        init_price_f = float(initial_price) if initial_price else 0.0
                        curr_price_f = float(current_price) if current_price is not None else 0.0
                        pl_val = 0.0
                    # Days owned (string or number)
                    if pdate and str(pdate).strip():
                        try:
                            days_owned = (datetime.now() - datetime.strptime(str(pdate), '%Y-%m-%d')).days
                        except Exception:
                            days_owned = ""
                    else:
                        days_owned = ""
                    # Write row to CSV
                    self.logger.log_portfolio(
                        ts,
                        ticker,
                        allocation,
                        name,
                        shares_f,
                        init_price_f,
                        curr_price_f,
                        pl_val,
                        pdate if pdate else "",
                        days_owned,
                        total_value,
                    )
            except Exception as e:
                self._log(f"Logging error: {e}\n")
            
            self._log(f"Update complete. Total value: ${total_value:,.2f}\n")
            
        except Exception as e:
            self._log(f"Update error: {e}\n")
        finally:
            # Always release lock/state
            try:
                self._updating = False
                self._update_lock.release()
            except Exception:
                pass
            # Notify GUI to hide spinner
            try:
                self.gui_update_queue.put({'type': 'update_status', 'updating': False})
            except Exception:
                pass

    def run_schedule(self):
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                print(f"Schedule error: {e}")
                time.sleep(60)

    def _start_tracking_threads(self):
        if not self.running:
            self.running = True
            schedule.every(1).hours.do(self.update_portfolio)
            
            # Start scheduler thread
            scheduler_thread = threading.Thread(target=self.run_schedule, daemon=True)
            scheduler_thread.start()
            
            self._log("Started hourly update schedule.\n")

    def on_stock_data_change(self, row_index, field_name, new_value):
        try:
            # Ensure portfolio arrays are long enough for this row
            target_len = row_index + 1
            while len(self.portfolio.stocks) < target_len:
                self.portfolio.stocks.append("")
            while len(self.portfolio.allocations) < target_len:
                self.portfolio.allocations.append(0.0)
            while len(self.portfolio.shares) < target_len:
                self.portfolio.shares.append(0.0)
            while len(self.portfolio.initial_prices) < target_len:
                self.portfolio.initial_prices.append(0.0)
            while len(self.portfolio.purchase_dates) < target_len:
                self.portfolio.purchase_dates.append("")
                
            if field_name == "purchase_price":
                # Treat the purchase price as the total amount spent to acquire
                # the current number of shares. Update the per‑share initial
                # price accordingly. If the field is blank, do nothing.
                if new_value.strip() == "":
                    # No update if the field is cleared
                    pass
                else:
                    try:
                        total_cost = float(new_value)
                    except ValueError:
                        self._log(f"Invalid purchase price entered for row {row_index + 1}. Please enter a numeric value.\n")
                        return
                    shares = self.portfolio.shares[row_index] if row_index < len(self.portfolio.shares) else 0
                    # If shares are available, compute the per‑share cost. If
                    # shares are zero, simply set the initial price equal to
                    # the total cost as a fallback.
                    if shares and shares > 0:
                        self.portfolio.initial_prices[row_index] = total_cost / shares
                    else:
                        self.portfolio.initial_prices[row_index] = total_cost
                    # Recalculate allocation based on the new total cost
                    if self.portfolio.total_investment > 0:
                        self.portfolio.allocations[row_index] = (shares * self.portfolio.initial_prices[row_index]) / self.portfolio.total_investment * 100
                
            elif field_name == "purchase_date":
                # Allow clearing the purchase date. Only validate the format if
                # the field is not empty. If the user clears the date, store
                # an empty string and set days owned to blank.
                if new_value.strip():
                    # Validate the entered date format
                    datetime.strptime(new_value, '%Y-%m-%d')
                    self.portfolio.purchase_dates[row_index] = new_value
                else:
                    # Store blank date to indicate no purchase date set
                    self.portfolio.purchase_dates[row_index] = ""
                
            elif field_name == "perc_invested":
                self.portfolio.allocations[row_index] = float(new_value)
                # Recalculate shares
                investment_for_stock = (float(new_value) / 100) * self.portfolio.total_investment
                if self.portfolio.initial_prices[row_index]:
                    self.portfolio.shares[row_index] = investment_for_stock / self.portfolio.initial_prices[row_index]
                    
            elif field_name == "ticker":
                self.portfolio.stocks[row_index] = new_value.upper()
                # Fetch company name in background
                threading.Thread(
                    target=lambda: self.update_company_name(row_index, new_value.upper()),
                    daemon=True
                ).start()

            elif field_name == "shares_owned":
                # When the user edits the number of shares, update the
                # portfolio's share count and adjust the per‑share initial
                # price so that the total cost remains constant. If the
                # existing total cost is unknown (e.g., initial price is 0),
                # simply update the shares. Also update the allocation based
                # on the new share count.
                try:
                    if new_value.strip() == "":
                        # Blank input: do not update
                        pass
                    else:
                        new_shares = float(new_value)
                        if new_shares < 0:
                            raise ValueError("Shares cannot be negative")
                        # Retrieve the old share count
                        old_shares = self.portfolio.shares[row_index] if row_index < len(self.portfolio.shares) else 0
                        old_initial_price = self.portfolio.initial_prices[row_index] if row_index < len(self.portfolio.initial_prices) else 0
                        # Compute the total cost based on old values
                        total_cost = old_initial_price * old_shares
                        # Update the share count
                        self.portfolio.shares[row_index] = new_shares
                        # If we have an existing total cost and new shares is
                        # non‑zero, adjust the per‑share price so the total
                        # cost remains the same
                        if new_shares > 0 and total_cost > 0:
                            self.portfolio.initial_prices[row_index] = total_cost / new_shares
                        # Update allocation to reflect new investment proportion
                        if self.portfolio.total_investment > 0:
                            self.portfolio.allocations[row_index] = (new_shares * self.portfolio.initial_prices[row_index]) / self.portfolio.total_investment * 100
                except ValueError as e:
                    self._log(f"Invalid shares entered for row {row_index + 1}: {e}\n")
                    return

            # Save changes
            self.logger.save_portfolio(
                self.portfolio.total_investment, self.portfolio.stocks, self.portfolio.allocations,
                self.portfolio.shares, self.portfolio.initial_prices, self.portfolio.purchase_dates
            )

            # Immediately recompute and update the profit/loss and days owned for
            # the modified row. This ensures that changes to shares or
            # purchase price are reflected in the UI without waiting for the
            # next price fetch.
            try:
                # Safely extract the current price from the UI
                row_widgets = self.gui.entry_rows[row_index]
                cp_str = row_widgets[6].get()  # current price column
                current_price_val = float(cp_str) if cp_str not in ("", None) else 0.0
            except Exception:
                current_price_val = 0.0
            # Compute profit/loss using total cost (shares * initial price)
            shares_val = self.portfolio.shares[row_index]
            initial_price = self.portfolio.initial_prices[row_index]
            profit_loss = (current_price_val - initial_price) * shares_val if shares_val else 0.0
            # Compute days owned based on purchase date if available
            pdate = self.portfolio.purchase_dates[row_index] if row_index < len(self.portfolio.purchase_dates) else ""
            if pdate and str(pdate).strip():
                try:
                    days_owned = (datetime.now() - datetime.strptime(str(pdate), '%Y-%m-%d')).days
                except Exception:
                    days_owned = ""
            else:
                days_owned = ""
            # Send update to GUI via queue
            self.gui_update_queue.put({
                'type': 'stock_row_update',
                'row_index': row_index,
                'current_price': current_price_val,
                'pl': profit_loss,
                'days_owned': days_owned
            })

            self._log(f"Updated {field_name} for row {row_index + 1}\n")
            
        except ValueError as e:
            self._log(f"Invalid input: {e}\n")
        except Exception as e:
            self._log(f"Update error: {e}\n")

    def delete_stock_row(self, row_index: int) -> None:
        """Delete a stock row from the portfolio and update the GUI and saved config.

        Parameters
        ----------
        row_index : int
            Zero-based index of the row to delete. Provided by the GUI layer.
        """
        try:
            # Ensure index is valid
            if row_index < 0 or row_index >= len(self.portfolio.stocks):
                raise IndexError("Invalid row index")
            ticker = self.portfolio.stocks[row_index]
            # Remove from the portfolio data structures
            self.portfolio.delete_stock(row_index)
            # Update the GUI to remove the row and reindex subsequent rows
            self.gui.delete_row_from_ui(row_index)
            # Save the updated portfolio. Include existing company names from the cache.
            company_names = [self.fetcher.company_cache.get(t, t) for t in self.portfolio.stocks]
            self.logger.save_portfolio(
                self.portfolio.total_investment,
                self.portfolio.stocks,
                self.portfolio.allocations,
                self.portfolio.shares,
                self.portfolio.initial_prices,
                self.portfolio.purchase_dates,
                company_names=company_names,
            )
            self._log(f"Deleted row {row_index + 1} ({ticker})\n")
        except Exception as e:
            self._log(f"Error deleting row: {e}\n")
            messagebox.showerror("Error", f"Error deleting row: {e}")

    def update_company_name(self, row_index, ticker):
        try:
            company_name = self.fetcher.get_company_name(ticker)
            self.gui_update_queue.put({
                'type': 'company_name_update',
                'row_index': row_index,
                'company_name': company_name
            })
        except Exception as e:
            print(f"Error updating company name: {e}")

    def process_gui_queue(self):
        # If the window is closing or destroyed, stop processing
        if self._closing or not self.root.winfo_exists():
            return
        try:
            while True:
                update = self.gui_update_queue.get_nowait()
                
                if update['type'] == 'stock_row_update':
                    row_index = update['row_index']
                    if row_index < len(self.gui.entry_rows):
                        row = self.gui.entry_rows[row_index]
                        try:
                            # Column indices have shifted due to the row number column.
                            # Current price is at index 6, P/L at index 7, Days owned at index 9.
                            # Update current price
                            if row[6].winfo_exists():
                                row[6].config(state='normal')
                                row[6].delete(0, tk.END)
                                row[6].insert(0, f"{update['current_price']:.2f}")
                                row[6].config(state='readonly')
                            # Update P/L and color-code cell (green positive, red negative)
                            if row[7].winfo_exists():
                                row[7].config(state='normal')
                                row[7].delete(0, tk.END)
                                row[7].insert(0, f"{update['pl']:.2f}")
                                # Apply background based on value
                                try:
                                    pl_val = float(update['pl'])
                                    if pl_val > 0:
                                        row[7].configure(readonlybackground="#c8e6c9")  # light green
                                    elif pl_val < 0:
                                        row[7].configure(readonlybackground="#ffcdd2")  # light red/pink
                                    else:
                                        row[7].configure(readonlybackground="#f0f0f0")  # neutral
                                except Exception:
                                    pass
                                row[7].config(state='readonly')
                            # Update days owned
                            if row[9].winfo_exists():
                                row[9].config(state='normal')
                                row[9].delete(0, tk.END)
                                row[9].insert(0, str(update['days_owned']))
                                row[9].config(state='readonly')
                        except tk.TclError:
                            # Widgets may have been destroyed during shutdown; ignore
                            pass
                        
                elif update['type'] == 'total_update':
                    try:
                        self.gui.update_totals(
                            update['total_pl'],
                            update['total_value'],
                            update['current_time']
                        )
                    except tk.TclError:
                        pass
                    
                elif update['type'] == 'update_status':
                    try:
                        self.gui.set_updating(bool(update.get('updating')))
                    except tk.TclError:
                        pass
                    
                elif update['type'] == 'company_name_update':
                    row_index = update['row_index']
                    if row_index < len(self.gui.entry_rows):
                        row = self.gui.entry_rows[row_index]
                        try:
                            # Company name is now at index 3 due to the row number column
                            if row[3].winfo_exists():
                                row[3].config(state='normal')
                                row[3].delete(0, tk.END)
                                row[3].insert(0, update['company_name'])
                                row[3].config(state='readonly')
                        except tk.TclError:
                            pass

                elif update['type'] == 'log_message':
                    # Append the log message to the output text box. Doing
                    # this through the queue ensures that GUI updates occur
                    # on the main thread.
                    try:
                        if (
                            not self._closing and
                            getattr(self, 'gui', None) is not None and
                            getattr(self.gui, 'text_output', None) is not None and
                            self.gui.text_output.winfo_exists()
                        ):
                            self.gui.text_output.insert(tk.END, update['message'])
                    except tk.TclError:
                        pass
                        
        except queue.Empty:
            pass
        finally:
            # Reschedule only if still active
            if not self._closing and self.root.winfo_exists():
                try:
                    self._after_id = self.root.after(100, self.process_gui_queue)
                except tk.TclError:
                    # Root may be in the process of closing; ignore
                    pass

    def _on_close(self):
        # Prevent further scheduling and cancel any pending after callbacks
        self._closing = True
        # Stop schedule loop and clear jobs
        try:
            self.running = False
            schedule.clear()
        except Exception:
            pass
        try:
            if self._after_id is not None:
                self.root.after_cancel(self._after_id)
        except tk.TclError:
            pass
        # Optionally stop background threads here if needed
        try:
            self.root.destroy()
        except Exception:
            pass

    def _log(self, message: str):
        """Thread-safe log to the GUI text box via queue. No-op when closing."""
        try:
            if self._closing:
                return
            # If GUI exists, enqueue; else print fallback
            if self.root and self.root.winfo_exists():
                self.gui_update_queue.put({'type': 'log_message', 'message': message})
            else:
                print(message, end="")
        except Exception:
            # As a last resort, print to console
            try:
                print(message, end="")
            except Exception:
                pass

    def run(self):
        print("Starting main GUI loop...")
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"GUI error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    try:
        print("Starting application...")
        app = StockPortfolioTracker()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
