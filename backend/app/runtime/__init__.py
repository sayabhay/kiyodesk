"""Trading Runtime — orchestrates the complete trading lifecycle.

The Runtime is the ONLY component allowed to connect:
    Market Data → Strategy Engine → Trade Opportunities → Trade Journal

The Scheduler remains focused solely on data collection.
"""
