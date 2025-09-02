from datetime import datetime

class PortfolioManager:
    def __init__(self):
        self.stocks = []
        self.allocations = []
        self.shares = []
        self.total_investment = 0
        self.initial_prices = []
        self.purchase_dates = []
        self.description = ""

    def initialize_portfolio(self, total_investment, stocks, allocations, prices, purchase_prices=None, purchase_dates=None):
        if total_investment <= 0:
            raise ValueError("Investment must be positive.")
        if not stocks:
            raise ValueError("No stocks entered.")
        if len(allocations) != len(stocks):
            raise ValueError("Number of percentages must match number of stocks.")
        if abs(sum(allocations) - 100) > 0.01:
            raise ValueError("Percentages must sum to 100.")
        if any(p <= 0 for p in allocations):
            raise ValueError("Percentages must be positive.")

        self.total_investment = total_investment
        self.stocks = stocks
        self.allocations = allocations
        self.shares = []
        self.initial_prices = []
        self.purchase_dates = []

        for i, (ticker, perc) in enumerate(zip(stocks, allocations)):
            # Prefer manual purchase price if given
            manual_price = None if purchase_prices is None else purchase_prices[i]
            price = manual_price if manual_price not in (None, "", 0) else prices.get(ticker)

            if price is None:
                raise ValueError(f"Could not fetch price for {ticker}. Please enter a purchase price.")

            investment = (perc / 100) * self.total_investment
            shares = investment / float(price)

            self.shares.append(shares)
            self.initial_prices.append(float(price))

            # Preserve the provided purchase date if supplied. If no date is
            # given (None or empty string), store an empty string instead of
            # defaulting to today. This allows users to leave the date
            # unspecified until an actual purchase is made.
            if purchase_dates and purchase_dates[i]:
                self.purchase_dates.append(purchase_dates[i])
            else:
                # Use an empty string to indicate no purchase date has been set
                self.purchase_dates.append("")

    def add_stock(self, ticker, perc, shares, purchase_price, purchase_date):
        if ticker not in self.stocks:
            self.stocks.append(ticker)
            self.allocations.append(float(perc))
            self.shares.append(shares)
            self.initial_prices.append(float(purchase_price))
            self.purchase_dates.append(purchase_date if purchase_date else datetime.now().strftime('%Y-%m-%d'))

    def calculate_totals(self, current_prices):
        total_pl = 0
        total_value = 0
        for ticker, shares, initial_price in zip(self.stocks, self.shares, self.initial_prices):
            current_price = current_prices.get(ticker, initial_price)
            current_price = float(current_price) if current_price is not None else (float(initial_price) if initial_price is not None else 0.0)
            total_pl += (current_price - initial_price) * shares
            total_value += current_price * shares
        return total_pl, total_value

    def get_portfolio_data(self):
        return self.stocks, self.allocations, self.shares, self.initial_prices, self.purchase_dates

    def delete_stock(self, index: int) -> None:
        """Delete a stock and its associated data from the portfolio.

        Parameters
        ----------
        index : int
            Zero-based index of the stock to delete.

        Raises
        ------
        IndexError
            If the index is out of range.
        """
        if index < 0 or index >= len(self.stocks):
            raise IndexError("Invalid stock index")
        # Remove stock and associated data
        del self.stocks[index]
        del self.allocations[index]
        del self.shares[index]
        del self.initial_prices[index]
        del self.purchase_dates[index]
