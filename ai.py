import json
import os
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import urllib.request
import urllib.error

CONFIG_FILE = "portfolio_config.json"


def _load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_config(cfg: dict):
    try:
        # Backup existing JSON to .bak before writing
        if os.path.exists(CONFIG_FILE):
            import shutil
            try:
                shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".bak")
            except Exception:
                pass
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        # Best effort only
        print(f"Warning: failed to save {CONFIG_FILE}: {e}")


class StockAIWindow:
    """A small UI to store a per‑ticker prompt and show the last AI answer.

    Reads/writes the following keys in portfolio_config.json:
    - openai_api_key: string
    - ai_prompts: { TICKER: prompt }
    - ai_answers: { TICKER: { text, timestamp } }
    """

    def __init__(self, parent, ticker: str):
        self.parent = parent
        self.ticker = (ticker or "").strip().upper()
        self.cfg = _load_config()

        ai_prompts = self.cfg.get("ai_prompts", {}) or {}
        ai_answers = self.cfg.get("ai_answers", {}) or {}
        self.prompt = ai_prompts.get(self.ticker, "")
        last = ai_answers.get(self.ticker) or {}
        self.last_answer = last.get("text", "")
        self.last_time = last.get("timestamp", "")

        self._build_ui()

    def _build_ui(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title(f"AI: {self.ticker}")
        try:
            self.win.configure(bg="#f0f0f0")
        except Exception:
            pass
        self.win.transient(self.parent)
        self.win.grab_set()

        # Prompt area
        tk.Label(self.win, text=f"Prompt for {self.ticker}", bg="#f0f0f0").pack(anchor="w", padx=10, pady=(10, 4))
        self.txt_prompt = tk.Text(self.win, height=5, width=80, wrap="word")
        self.txt_prompt.pack(fill="x", padx=10)
        if self.prompt:
            self.txt_prompt.insert("1.0", self.prompt)

        # Controls
        ctrl = tk.Frame(self.win, bg="#f0f0f0")
        ctrl.pack(fill="x", padx=10, pady=6)

        self.btn_ask = tk.Button(ctrl, text="Ask AI", command=self.ask_ai, bg="#c8e6c9")
        self.btn_ask.pack(side=tk.RIGHT)

        self.btn_save = tk.Button(ctrl, text="Save Prompt", command=self.save_prompt, bg="#bbdefb")
        self.btn_save.pack(side=tk.RIGHT, padx=6)

        # Answer area
        tk.Label(self.win, text="Answer", bg="#f0f0f0").pack(anchor="w", padx=10, pady=(6, 4))
        self.txt_answer = tk.Text(self.win, height=16, width=80, wrap="word")
        self.txt_answer.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        if self.last_answer:
            hdr = f"Last updated: {self.last_time}\n\n" if self.last_time else ""
            self.txt_answer.insert("1.0", hdr + self.last_answer)
        else:
            self.txt_answer.insert("1.0", "No answer yet. Enter a prompt and click Ask AI.")
        self.txt_answer.config(state='normal')

    def save_prompt(self):
        try:
            self.prompt = self.txt_prompt.get("1.0", "end").strip()
            cfg = _load_config()
            prompts = cfg.get("ai_prompts", {}) or {}
            if self.prompt:
                prompts[self.ticker] = self.prompt
            else:
                # Remove empty prompts to keep file tidy
                if self.ticker in prompts:
                    prompts.pop(self.ticker, None)
            cfg["ai_prompts"] = prompts
            _save_config(cfg)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save prompt: {e}")

    def ask_ai(self):
        # Persist the prompt before asking
        self.save_prompt()

        # Prepare UI state
        try:
            self.btn_ask.config(state='disabled')
        except Exception:
            pass
        self.txt_answer.config(state='normal')
        self.txt_answer.delete("1.0", "end")
        self.txt_answer.insert("1.0", "Requesting AI analysis...\n")

        self.win.after(50, self._do_request)

    def _do_request(self):
        cfg = _load_config()
        key = (cfg.get("openai_api_key") or "").strip()
        if not key:
            self._show_missing_key_help()
            return

        prompt = (self.prompt or self.txt_prompt.get("1.0", "end")).strip()
        if not prompt:
            self.txt_answer.delete("1.0", "end")
            self.txt_answer.insert("1.0", "Please enter a prompt, then click Ask AI.")
            try:
                self.btn_ask.config(state='normal')
            except Exception:
                pass
            return

        # Compose a simple system+user prompt
        system_msg = {
            "role": "system",
            "content": "You are a helpful portfolio analysis assistant. Be concise and actionable."
        }
        user_msg = {"role": "user", "content": f"Ticker: {self.ticker}\nInstruction: {prompt}"}

        data = {
            "model": "gpt-4o-mini",
            "messages": [system_msg, user_msg],
            "temperature": 0.2,
            "max_tokens": 500,
        }

        req = urllib.request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                payload = json.loads(body.decode("utf-8"))
                text = (
                    payload.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not text:
                    raise ValueError("Empty response from API")
        except urllib.error.HTTPError as e:
            try:
                err = e.read().decode("utf-8")
            except Exception:
                err = str(e)
            text = f"API error: {e.code}\n{err}"
        except Exception as e:
            text = f"Request failed: {e}"

        # Update UI and persist answer
        self.txt_answer.config(state='normal')
        self.txt_answer.delete("1.0", "end")
        self.txt_answer.insert("1.0", text)
        try:
            self.btn_ask.config(state='normal')
        except Exception:
            pass

        try:
            cfg = _load_config()
            answers = cfg.get("ai_answers", {}) or {}
            answers[self.ticker] = {
                "text": text,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            cfg["ai_answers"] = answers
            _save_config(cfg)
        except Exception:
            pass

    def _show_missing_key_help(self):
        help_text = (
            "No OpenAI API key found in portfolio_config.json under the key 'openai_api_key'.\n\n"
            "To enable AI answers:\n"
            "1) Create an API key at https://platform.openai.com/api-keys\n"
            "2) Open portfolio_config.json and add:\n"
            "   \"openai_api_key\": \"YOUR_KEY_HERE\"\n"
            "3) Save the file and click Ask AI again.\n"
        )
        self.txt_answer.config(state='normal')
        self.txt_answer.delete("1.0", "end")
        self.txt_answer.insert("1.0", help_text)
        try:
            self.btn_ask.config(state='normal')
        except Exception:
            pass


def open_stock_ai_window(parent, ticker: str):
    try:
        StockAIWindow(parent, ticker)
    except Exception as e:
        try:
            messagebox.showerror("Error", f"Failed to open AI window: {e}")
        except Exception:
            print(f"Failed to open AI window: {e}")
