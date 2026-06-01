"""Recall fixture: a God Class mixing DB + email + UI concerns across 11 methods.

This is the exact case the external critique flagged: a class that clearly
violates SRP but slips past GodClassDetector because the method-count threshold
is `max_methods + 5` (=15). Eleven cohesion-less methods should still be a God
Class. Expected to MISS today — documents the item-3 gap as a measured number.
"""


class AccountManager:  # EXPECT: GodClass
    def __init__(self):
        self.db_conn = None
        self.smtp_host = None
        self.ui_theme = None
        self.cache = {}

    def open_db(self):
        self.db_conn = "connected"

    def query_user(self, uid):
        return f"SELECT * FROM users WHERE id={uid}"

    def save_user(self, user):
        self.db_conn = "wrote"

    def send_welcome_email(self, addr):
        self.smtp_host = "smtp.example.com"

    def send_reset_email(self, addr):
        self.smtp_host = "smtp.example.com"

    def render_dashboard(self):
        return f"<html theme={self.ui_theme}>"

    def render_profile(self):
        return f"<div theme={self.ui_theme}>"

    def set_theme(self, theme):
        self.ui_theme = theme

    def warm_cache(self, key, value):
        self.cache[key] = value

    def evict_cache(self, key):
        self.cache.pop(key, None)

    def export_report(self):
        return "report.csv"
