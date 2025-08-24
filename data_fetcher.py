import requests
from datetime import datetime, timedelta
import time

# Custom error to indicate an API rate limit has been hit. When this error
# is raised, callers should avoid immediate retries because further calls
# will not succeed until the rate limit resets.
class RateLimitError(Exception):
    pass

class DataFetcher:
    def __init__(self):
        self.cached_prices = {}
        self.company_cache = {}
        self.last_api_call = None
        self.api_call_count = 0
        self.daily_call_count = 0
        self.last_reset_date = datetime.now().date()
        
        # Alpha Vantage API Key (get your free key at https://www.alphavantage.co/support/#api-key)
        self.alpha_vantage_key = "T0KV693NC9RHEWSI"  # Replace with your key
        
        # Alternative: Finnhub API Key (get at https://finnhub.io/register)
        self.finnhub_key = "d2ifc9pr01qgfkrm3cv0d2ifc9pr01qgfkrm3cvg"  # Replace with your key
        
        # Choose your preferred API
        self.api_provider = "alpha_vantage"  # or "finnhub" or "yfinance"

        # Order of providers to attempt when fetching prices. When a rate
        # limit is encountered or a provider returns no data, the fetcher will
        # try the next provider in this list. Providers listed here must
        # correspond to methods ``_get_alpha_vantage_price``,
        # ``_get_finnhub_price``, or ``_get_yfinance_price``.
        # Prioritise Finnhub first (higher rate limit) then fall back to
        # Alpha Vantage only if Finnhub is unavailable or returns no data.
        self.provider_order = ["finnhub", "alpha_vantage"]

        # Track when each provider becomes available again after a rate limit is
        # encountered. Each entry maps a provider name to a datetime. If the
        # current time is earlier than the stored timestamp, the provider will
        # be skipped. When a rate limit error is detected for a provider, its
        # cooldown is set to now + provider_cooldown_seconds.
        self.provider_cooldowns: dict[str, datetime] = {
            provider: datetime.min for provider in self.provider_order
        }

        # Default cooldown duration (in seconds) after a provider signals a rate
        # limit. This can be adjusted to suit the API’s documented limits.
        self.provider_cooldown_seconds: int = 300  # 5 minutes

        # We no longer maintain a hard-coded mapping of tickers to company names.
        # If company names are required without an API lookup, they should be
        # supplied in the portfolio configuration JSON instead.

    def _check_rate_limits(self):
        """Ensure we don't exceed API rate limits.

        This function enforces per‑minute call limits by sleeping when
        necessary. For Alpha Vantage, it also raises a ``RateLimitError`` if
        the daily quota has been exhausted so callers can fall back to other
        providers. Otherwise, no exception is raised.
        """
        now = datetime.now()
        
        # Reset daily counter if it's a new day
        if now.date() != self.last_reset_date:
            self.daily_call_count = 0
            self.last_reset_date = now.date()
        
        if self.api_provider == "alpha_vantage":
            # Alpha Vantage: 5 requests per minute (one every 12 seconds), 25 per day
            if self.daily_call_count >= 25:
                # Raise a specific error so callers can fall back to other providers
                raise RateLimitError("Alpha Vantage daily API limit reached (25 calls)")

            if self.last_api_call:
                time_since_last = (now - self.last_api_call).total_seconds()
                # Enforce the per-minute limit via sleep
                if time_since_last < 12:
                    time.sleep(12 - time_since_last)
        
        elif self.api_provider == "finnhub":
            # Finnhub: 60 requests per minute (one per second)
            if self.last_api_call:
                time_since_last = (now - self.last_api_call).total_seconds()
                if time_since_last < 1:
                    time.sleep(1 - time_since_last)

    def get_current_prices(self, tickers):
        """
        Fetch the current prices for a list of tickers.

        This method attempts to retrieve prices from the configured API provider.
        If a call fails, it will retry up to two additional times with a short
        delay between attempts. After three failed attempts, the method falls
        back to returning any cached price for the ticker.

        Parameters
        ----------
        tickers : iterable of str
            Stock ticker symbols to fetch prices for.

        Returns
        -------
        dict
            A mapping of ticker symbols to their latest price. If a price could
            not be fetched and no cached value exists, the ticker will map to
            ``None``.
        """
        prices: dict[str, float | None] = {}

        for ticker in tickers:
            start = time.perf_counter()
            price: float | None = None

            # Attempt to fetch the price from each configured provider in order.
            for provider in self.provider_order:
                # Skip providers that are in cooldown due to a recent rate limit
                cooldown_until = self.provider_cooldowns.get(provider, datetime.min)
                if datetime.now() < cooldown_until:
                    continue

                old_provider = self.api_provider
                # Temporarily switch the active provider so rate limits are
                # checked against the correct service.
                
                self.api_provider = provider
                try:
                    if provider == "alpha_vantage":
                        price = self._get_alpha_vantage_price(ticker)
                    elif provider == "finnhub":
                        price = self._get_finnhub_price(ticker)
                    elif provider == "yfinance":
                        price = self._get_yfinance_price(ticker)
                    else:
                        price = None

                    # If a valid price was returned, stop checking other providers
                    if price is not None:
                        break
                except RateLimitError as e:
                    # Log the rate limiting message. Do not retry this provider
                    # immediately; instead, set a cooldown before trying it again.
                    print(f"Rate limit reached for {ticker} via {provider}: {e}")
                    price = None
                    # Set cooldown for this provider
                    self.provider_cooldowns[provider] = datetime.now() + timedelta(seconds=self.provider_cooldown_seconds)
                    # Continue to next provider
                except Exception as e:
                    # Log other errors for debugging and move on to the next provider
                    # Detect Too Many Requests in yfinance errors and set a cooldown
                    if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                        print(f"Rate limit reached for {ticker} via {provider}: {e}")
                        self.provider_cooldowns[provider] = datetime.now() + timedelta(seconds=self.provider_cooldown_seconds)
                    else:
                        print(f"Error fetching {ticker} via {provider}: {e}")
                    price = None
                    # Continue to next provider
                finally:
                    # Restore the original provider setting
                    self.api_provider = old_provider

            if price is not None:
                prices[ticker] = float(price)
                self.cached_prices[ticker] = float(price)
                tp = time.perf_counter() - start
                print(f"Fetched {ticker}: ${price:.2f} in {tp:.1f} seconds")
            else:
                # Use cached price if available; otherwise None
                cached = self.cached_prices.get(ticker)
                prices[ticker] = cached
                # Only log when a cached price is available. If there is no
                # cached value, remain silent to avoid spamming the log.
                if cached is not None:
                    print(f"Using cached price for {ticker}: ${cached:.2f}")

        return prices

    def _get_alpha_vantage_price(self, ticker):
        """Get real-time price from Alpha Vantage"""
        # Enforce rate limits. If the daily limit is reached, this call will
        # raise a RateLimitError, which should propagate to the caller so
        # they can fall back to another provider.
        self._check_rate_limits()
        try:
            # Use GLOBAL_QUOTE for real-time price
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": ticker.upper(),
                "apikey": self.alpha_vantage_key,
            }

            response = requests.get(url, params=params)
            self.last_api_call = datetime.now()
            self.daily_call_count += 1

            data = response.json()

            if "Global Quote" in data and "05. price" in data["Global Quote"]:
                return float(data["Global Quote"]["05. price"])
            elif "Note" in data:
                # If the API returns a note about rate limiting or other
                # conditions, return ``None`` quietly so the caller can
                # interpret this as a non-fatal failure and try another
                # provider or fallback to cached data.
                return None
            else:
                # In cases where the response does not match the expected format,
                # return ``None`` quietly.
                return None

        except RateLimitError:
            # Bubble up RateLimitError so that it can be handled by the caller.
            raise
        except Exception as e:
            # Log other exceptions (e.g., network errors) and return None.
            print(f"Alpha Vantage error for {ticker}: {e}")
            return None

    def _get_finnhub_price(self, ticker):
        """Get real-time price from Finnhub"""
        # Enforce rate limits. Finnhub does not have a daily limit, so
        # ``_check_rate_limits`` will only sleep as necessary. Any
        # RateLimitError raised here would bubble up and be handled by the caller.
        self._check_rate_limits()
        try:
            url = "https://finnhub.io/api/v1/quote"
            params = {
                "symbol": ticker.upper(),
                "token": self.finnhub_key,
            }

            response = requests.get(url, params=params)
            self.last_api_call = datetime.now()

            data = response.json()

            if "c" in data and data["c"] > 0:  # 'c' is current price
                return float(data["c"])
            else:
                # Quietly return None when no price is available.
                return None

        except RateLimitError:
            # Propagate RateLimitError to the caller
            raise
        except Exception as e:
            print(f"Finnhub error for {ticker}: {e}")
            return None

    def _get_yfinance_price(self, ticker):
        """Get price using yfinance (no API key needed)"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker.upper())
            info = stock.info
            
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            
            if price:
                return float(price)
            else:
                # Fallback: get the last close from history
                hist = stock.history(period="1d")
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
                return None
                
        except Exception as e:
            print(f"yfinance error for {ticker}: {e}")
            return None

    def get_company_name(self, ticker):
        """
        Get a company name for the provided ticker, using multiple providers
        according to the configured ``provider_order``. This method first
        checks the cache; if the name is missing or equal to the ticker, it
        attempts to fetch the name from each provider in order. If a provider
        signals a rate limit, that provider will be skipped until its cooldown
        expires. If all providers fail or only return the ticker as the name,
        the ticker itself will be used as a fallback. The result is cached.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol for which to fetch the company name.

        Returns
        -------
        str
            The company name, or the ticker if no name could be fetched.
        """
        ticker = ticker.upper()
        # Return cached name if available
        cached = self.company_cache.get(ticker)
        if cached:
            return cached

        name: str | None = None
        for provider in self.provider_order:
            # Skip providers in cooldown (rate limited)
            cooldown_until = self.provider_cooldowns.get(provider, datetime.min)
            if datetime.now() < cooldown_until:
                continue
            # Temporarily switch provider for rate limit checks
            old_provider = self.api_provider
            self.api_provider = provider
            try:
                if provider == "alpha_vantage":
                    candidate = self._fetch_alpha_vantage_name(ticker)
                elif provider == "finnhub":
                    candidate = self._fetch_finnhub_name(ticker)
                elif provider == "yfinance":
                    candidate = self._fetch_yfinance_name(ticker)
                else:
                    candidate = None
                # If a valid name is returned and it's not just the ticker,
                # use it and stop trying further providers
                if candidate and candidate.upper() != ticker:
                    name = candidate
                    break
                # Otherwise continue to next provider
            except RateLimitError as e:
                # When rate limit is hit, set cooldown for this provider and
                # continue to the next provider
                print(f"Rate limit reached for {ticker} name via {provider}: {e}")
                self.provider_cooldowns[provider] = datetime.now() + timedelta(seconds=self.provider_cooldown_seconds)
                continue
            except Exception as e:
                # Log other errors silently and try the next provider
                # Note: yfinance may raise exceptions if ticker is invalid
                print(f"Error fetching company name for {ticker} via {provider}: {e}")
                candidate = None
            finally:
                # Restore the original provider
                self.api_provider = old_provider

            # If we got a candidate (even equal to ticker), set name to it so
            # that the fallback will have a value if no provider returns a
            # better name.
            if name is None and candidate:
                name = candidate

        # If no provider returned a name, use the ticker itself
        if not name:
            name = ticker

        # Cache and return the name
        self.company_cache[ticker] = name
        return name

    # Helper methods to fetch names from specific providers
    def _fetch_alpha_vantage_name(self, ticker: str) -> str | None:
        """Fetch company name from Alpha Vantage's OVERVIEW endpoint."""
        # Use local provider state for rate limit enforcement
        # Note: self.api_provider should already be set to 'alpha_vantage'
        self._check_rate_limits()
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "OVERVIEW",
            "symbol": ticker.upper(),
            "apikey": self.alpha_vantage_key
        }
        response = requests.get(url, params=params)
        self.last_api_call = datetime.now()
        self.daily_call_count += 1
        data = response.json()
        return data.get("Name") or None

    def _fetch_finnhub_name(self, ticker: str) -> str | None:
        """Fetch company name from Finnhub's profile endpoint."""
        self._check_rate_limits()
        url = "https://finnhub.io/api/v1/stock/profile2"
        params = {
            "symbol": ticker.upper(),
            "token": self.finnhub_key
        }
        response = requests.get(url, params=params)
        self.last_api_call = datetime.now()
        data = response.json()
        return data.get("name") or None

    def _fetch_yfinance_name(self, ticker: str) -> str | None:
        """Fetch company name using yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            return None
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        return info.get("longName") or info.get("shortName") or None

# Example usage and setup instructions
"""
SETUP INSTRUCTIONS:

1. Choose your preferred API provider:
   - Alpha Vantage: Best for free tier with good limits
   - Finnhub: Good alternative with more generous rate limits
   - yfinance: No API key needed but less reliable

2. Get your FREE API key:
   - Alpha Vantage: https://www.alphavantage.co/support/#api-key
   - Finnhub: https://finnhub.io/register

3. Install required packages:
   pip install requests retrying
   
   For yfinance option:
   pip install yfinance

4. Replace the API keys in the __init__ method with your actual keys

5. Set self.api_provider to your preferred service

The fetcher will automatically handle rate limits and cache prices to avoid
exceeding API limits. Hourly updates work perfectly within free tier limits!
"""