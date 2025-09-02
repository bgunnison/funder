import csv
import json
import os
from datetime import datetime

class PortfolioLogger:
    def __init__(self, csv_file="portfolio_log.csv", config_file="portfolio_config.json", totals_csv_file="portfolio_totals_log.csv"):
        self.csv_file = csv_file
        self.config_file = config_file
        self.totals_csv_file = totals_csv_file
        self.init_csv()
        self.init_totals_csv()

    def init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "% Invested", "Sym", "Name", "Shares Owned", "Purchase Price", "Current Price", "Profit/Loss", "Date Purchased", "Days Owned", "Portfolio Value"])

    def init_totals_csv(self):
        if not os.path.exists(self.totals_csv_file):
            with open(self.totals_csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Total P/L", "Total Value"])

    def log_portfolio(self, timestamp, ticker, perc, name, shares, purchase_price, current_price, pl, purchase_date, days_owned, portfolio_value):
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, perc, ticker, name, f"{shares:.2f}", f"{purchase_price:.2f}", f"{current_price:.2f}", f"{pl:.2f}", purchase_date, days_owned, f"{portfolio_value:.2f}"])

    def log_totals(self, timestamp, total_pl, total_value):
        with open(self.totals_csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, f"{total_pl:.2f}", f"{total_value:.2f}"])

    def save_portfolio(self, total_investment, stocks, allocations, shares, initial_prices, purchase_dates, company_names=None, description=None):
        """
        Persist the current portfolio configuration to a JSON file. In addition to
        the standard fields, an optional list of company names may be provided.
        When present, the list should be the same length as the list of stocks
        and will be stored under the key ``company_names``.

        Parameters
        ----------
        total_investment : float
            Total amount invested across all stocks.
        stocks : list[str]
            List of ticker symbols.
        allocations : list[float]
            Percentage allocations for each stock.
        shares : list[float]
            Number of shares owned for each stock.
        initial_prices : list[float]
            Purchase price for each stock.
        purchase_dates : list[str]
            Date each stock was purchased.
        company_names : list[str], optional
            List of company names corresponding to each ticker. If omitted or
            ``None``, this key will be excluded from the saved JSON.
        """
        config = {
            "total_investment": total_investment,
            "stocks": stocks,
            "allocations": allocations,
            "shares": shares,
            "initial_prices": initial_prices,
            "purchase_dates": purchase_dates
        }
        if company_names is not None:
            config["company_names"] = company_names
        if description is not None:
            config["description"] = description
        # Create a .bak backup of the existing JSON before writing
        try:
            if os.path.exists(self.config_file):
                import shutil
                shutil.copy2(self.config_file, self.config_file + ".bak")
        except Exception:
            # Non-fatal if backup fails
            pass
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)

    def load_portfolio(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return None
