"""
Bot Doctor - Meta-Diagnostic System
Analyzes the bot's own logs and execution patterns to generate health reports.
Acts as a 'Source of Truth' for debugging and improvement.
"""

import time
import os
import re
import json
import logging
import numpy as np
from collections import deque, Counter
from threading import Thread
from datetime import datetime

logger = logging.getLogger("BotDoctor")

class BotDoctor:
    def __init__(self, log_files=['bot.log', 'bot_trace.log'], report_file='bot_health_report.md'):
        self.log_files = log_files
        self.report_file = report_file
        self.running = False
        
        # Knowledge Base
        self.error_counts = Counter()
        self.state_transitions = deque(maxlen=1000)
        self.api_latency = deque(maxlen=1000)
        self.trade_attempts = 0
        self.trade_successes = 0
        self.last_log_pos = {f: 0 for f in log_files}
        
        # Patterns
        self.patterns = {
            'api_error': re.compile(r'Request exception|Connection closed|timeout|502|500'),
            'logic_error': re.compile(r'AttributeError|TypeError|KeyError|ValueError'),
            'trade_attempt': re.compile(r'Attempting bet|Placing'),
            'trade_success': re.compile(r'Bet Success|SUCCESS'),
            'state_change': re.compile(r'State change: (.*) -> (.*)'), # hypothetical format
            'latency': re.compile(r'took ([\d\.]+)s')
        }

    def start(self):
        self.running = True
        Thread(target=self._monitor_loop, daemon=True, name="DoctorThread").start()
        logger.info("Bot Doctor started. Monitoring vitals.")

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        while self.running:
            self._analyze_logs()
            self._generate_report()
            time.sleep(10) # Update report every 10s

    def _analyze_logs(self):
        for log_file in self.log_files:
            if not os.path.exists(log_file): continue
            
            try:
                with open(log_file, 'r') as f:
                    f.seek(self.last_log_pos[log_file])
                    lines = f.readlines()
                    self.last_log_pos[log_file] = f.tell()
                    
                    for line in lines:
                        self._process_line(line)
            except Exception as e:
                pass # Don't crash the doctor

    def _process_line(self, line):
        # 1. Error Tracking
        if "ERROR" in line:
            # Extract basic error message
            parts = line.split("ERROR")
            if len(parts) > 1:
                msg = parts[1].strip()[:50] # Group similar errors
                self.error_counts[msg] += 1

        # 2. Pattern Matching
        if self.patterns['api_error'].search(line):
            self.error_counts['API_Instability'] += 1
            
        if self.patterns['logic_error'].search(line):
            self.error_counts['Code_Logic_Bug'] += 1
            
        if self.patterns['trade_attempt'].search(line):
            self.trade_attempts += 1
            
        if self.patterns['trade_success'].search(line):
            self.trade_successes += 1

    def _generate_report(self):
        """Generates a Markdown report for the Developer/LLM"""
        
        # Calculations
        success_rate = (self.trade_successes / self.trade_attempts * 100) if self.trade_attempts > 0 else 0
        
        # Top Errors
        top_errors = self.error_counts.most_common(5)
        
        # Report Content
        report = f"""# Bot Health Report (Auto-Generated)
**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. Vitals
- **Status:** Running
- **Uptime:** (Derived from logs)
- **Trade Attempts:** {self.trade_attempts}
- **Success Rate:** {success_rate:.1f}%

## 2. Diagnosis (The "Doctor's Note")
"""
        
        # Diagnostic Logic
        if self.error_counts['Code_Logic_Bug'] > 0:
            report += "🚨 **CRITICAL:** Logic errors detected. Check logs for Attribute/Type errors immediately.\n"
        elif self.error_counts['API_Instability'] > 10:
            report += "⚠️ **WARNING:** High rate of API failures. Network or Rate Limit issue.\n"
        elif self.trade_attempts > 0 and success_rate < 50:
            report += "⚠️ **WARNING:** Low trade execution success. Check Order Placement logic or Budget.\n"
        else:
            report += "✅ **HEALTHY:** System operating within normal parameters.\n"

        report += "\n## 3. Top Errors\n"
        if top_errors:
            for err, count in top_errors:
                report += f"- `{err}`: {count} times\n"
        else:
            report += "No errors recorded yet.\n"

        report += "\n## 4. Recommendations\n"
        if success_rate == 0 and self.trade_attempts > 5:
            report += "- Investigate `create_market_buy_order` fallback logic.\n"
            report += "- Check `bot_trace.log` for specific `OrderArgs` exceptions.\n"
        
        if self.error_counts['API_Instability'] > 20:
            report += "- Consider increasing retry backoff in `market_15m.py`.\n"

        # Write to file
        with open(self.report_file, 'w') as f:
            f.write(report)
