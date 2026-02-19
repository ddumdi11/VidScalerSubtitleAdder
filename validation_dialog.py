"""
Validation Dialog - Zeigt Übersetzungs-Validierungsergebnisse an
und lässt den User entscheiden, ob fortgefahren werden soll.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
import threading

from subtitle_validator import ValidationResult


class ValidationDialog:
    """Dialog der Validierungsprobleme anzeigt und auf User-Entscheidung wartet.

    Wird vom Hauptthread via root.after() aufgerufen.
    Der Hintergrund-Thread wartet via threading.Event auf die Antwort.
    """

    def __init__(self, root: tk.Tk, result: ValidationResult):
        self.root = root
        self.result = result
        self.user_choice: Optional[str] = None  # "proceed" oder "abort"
        self.event = threading.Event()

    def show(self):
        """Zeigt den Dialog an (muss im Hauptthread aufgerufen werden)."""
        self.dialog = tk.Toplevel(self.root)
        self.dialog.title("Übersetzungs-Prüfung")
        self.dialog.geometry("520x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.root)
        self.dialog.grab_set()

        # Dialog zentrieren
        self.dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 520) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Schließen = Abbrechen
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_abort)

        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Titel
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text="Übersetzungs-Qualitätsprüfung",
                  font=("Arial", 14, "bold")).pack(anchor=tk.W)

        # Kurzinfo-Zeile
        summary = (
            f"{self.result.empty_count} von {self.result.total_count} Segmenten "
            f"ohne Übersetzung ({self.result.empty_percentage:.1f}%)"
        )
        if self.result.drift_amount > 0:
            summary += f"  |  Drift: ~{self.result.drift_amount} Segmente verschoben"

        ttk.Label(main_frame, text=summary, foreground="red",
                  font=("Arial", 10)).pack(anchor=tk.W, pady=(0, 10))

        # Details (scrollbar Text-Widget)
        detail_frame = ttk.LabelFrame(main_frame, text="Details", padding="5")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=10, width=55,
                              font=("Consolas", 9), state=tk.NORMAL)
        detail_text.insert(tk.END, self.result.details)
        detail_text.config(state=tk.DISABLED)

        detail_scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL,
                                         command=detail_text.yview)
        detail_text.configure(yscrollcommand=detail_scrollbar.set)

        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        # Abbrechen-Button (links, prominent)
        abort_btn = ttk.Button(button_frame, text="Abbrechen - nicht einbrennen",
                               command=self._on_abort)
        abort_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Trotzdem-Button (rechts, weniger prominent)
        proceed_btn = ttk.Button(button_frame, text="Trotzdem einbrennen",
                                 command=self._on_proceed)
        proceed_btn.pack(side=tk.RIGHT)

        # Focus auf Abbrechen (sicherer Default)
        abort_btn.focus_set()

        # Enter = Abbrechen, Escape = Abbrechen
        self.dialog.bind("<Return>", lambda e: self._on_abort())
        self.dialog.bind("<Escape>", lambda e: self._on_abort())

    def _on_proceed(self):
        """User wählt 'Trotzdem einbrennen'."""
        self.user_choice = "proceed"
        self.dialog.destroy()
        self.event.set()

    def _on_abort(self):
        """User wählt 'Abbrechen'."""
        self.user_choice = "abort"
        self.dialog.destroy()
        self.event.set()

    def wait_for_choice(self, timeout: float = 300.0) -> str:
        """Wartet auf die User-Entscheidung (aus dem Hintergrund-Thread aufrufen).

        Returns:
            "proceed" oder "abort"
        """
        self.event.wait(timeout=timeout)
        return self.user_choice or "abort"
