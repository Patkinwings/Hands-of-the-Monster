from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                          QHBoxLayout, QPushButton, QTableWidget, 
                          QTableWidgetItem, QFileDialog, QStatusBar, QLabel, QGridLayout,
                          QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from pathlib import Path
import re
from collections import defaultdict
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import sqlite3
from scaling_utils import apply_scaling, get_scale_level, abbreviate_text
import math
import os
import xml.etree.ElementTree as ET


class PlayerType:
    TAG = "Tight Aggressive"
    LAG = "Loose Aggressive" 
    NIT = "Nit"
    FISH = "Fish"
    MANIAC = "Maniac"
    UNKNOWN = "Unknown"
    INITIAL = "In"

class PlayerColors:
    TAG = QColor(144, 238, 144)  # Light green
    LAG = QColor(255, 165, 0)    # Orange
    NIT = QColor(135, 206, 235)  # Sky blue 
    FISH = QColor(255, 99, 71)   # Red
    MANIAC = QColor(186, 85, 211) # Purple
    UNKNOWN = QColor(169, 169, 169) # Gray
    INITIAL = QColor(200, 200, 200) # Light gray

class PokerHandHistoryWatcher(FileSystemEventHandler):
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.last_processed = {}
        self.last_file_sizes = {}
        
    def on_modified(self, event):
        if not event.is_directory:
            if self.analyzer.current_poker_site in ["PokerStars", "888poker"] and event.src_path.endswith('.txt'):
                # Give more time for 888poker to finish writing
                time.sleep(0.3)
                self.process_text_file(event.src_path)
            elif self.analyzer.current_poker_site == "Red Star Poker" and event.src_path.endswith('.xml'):
                # Give more time for Red Star Poker to finish writing
                time.sleep(0.3)
                self.process_xml_file(event.src_path)
    
    def process_text_file(self, file_path):
        try:
            current_size = os.path.getsize(file_path)
            last_size = self.last_file_sizes.get(file_path, 0)
            
            # Reset position if file size decreased (new file or truncated)
            if current_size < last_size:
                self.last_processed[file_path] = 0
                print(f"File size decreased, resetting position: {file_path}")
            
            self.last_file_sizes[file_path] = current_size
            
            with open(file_path, 'r', encoding='utf-8') as file:
                file.seek(self.last_processed.get(file_path, 0))
                new_content = file.read()
                self.last_processed[file_path] = file.tell()
                if new_content:
                    print(f"Processing {len(new_content)} bytes of new content")
                    self.analyzer.process_new_hands(new_content)
                else:
                    print(f"No new content in {file_path}")
        except Exception as e:
            print(f"Error processing file {file_path}: {str(e)}")
            # If there was an error, try reading the whole file next time
            self.last_processed[file_path] = 0
            
    def process_xml_file(self, file_path):
        try:
            current_size = os.path.getsize(file_path)
            last_size = self.last_file_sizes.get(file_path, 0)
            
            # Reset position for XML files if size decreased
            if current_size < last_size:
                self.last_processed[file_path] = 0
                print(f"XML file size decreased, resetting: {file_path}")
            
            self.last_file_sizes[file_path] = current_size
            
            # For XML, we need to read the whole file and check if it's new content
            with open(file_path, 'r', encoding='utf-8') as file:
                xml_content = file.read()
                
            # Check if we've processed this exact content before
            if file_path not in self.last_processed or xml_content != self.last_processed.get(file_path):
                print(f"Processing new XML content from {file_path}")
                self.analyzer.process_new_hands(xml_content)
                self.last_processed[file_path] = xml_content
            else:
                print(f"No new content in XML file {file_path}")
                
        except Exception as e:
            print(f"Error processing XML file {file_path}: {str(e)}")
            self.last_processed[file_path] = 0

class LiveHandHistoryAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Poker Hand History Analyzer")
        self.setGeometry(100, 100, 1200, 800)
        self.setMaximumSize(850, 850)
        
        self.db_path = Path.home() / "poker_stats.db"
        self.initialize_database()
        
        app = QApplication.instance()
        if app and not app.style().objectName() == 'Fusion':
            app.setStyle('Fusion')
            
        self.apply_dark_theme()
        
        # Track selected poker site
        self.current_poker_site = "PokerStars"  # Default site
        
        # Initialize stats dictionaries with default values
        self.player_stats = defaultdict(lambda: {
            'total_hands': 0,
            'vpip_hands': 0,
            'pfr_hands': 0,
            'total_actions': 0,
            'bets': 0,
            'raises': 0,
            'calls': 0,
            'checks': 0,
            'threebets': 0,
            'threebet_opportunities': 0,
            'faced_3bet': 0,
            'folded_to_3bet': 0,
            'cbets': 0,
            'cbet_opportunities': 0,
            'player_type': PlayerType.UNKNOWN,
            'position': None
        })
        
        self.current_players = set()
        self.session_stats = defaultdict(lambda: {
            'total_hands': 0,
            'vpip_hands': 0,
            'pfr_hands': 0,
            'total_actions': 0,
            'bets': 0,
            'raises': 0,
            'calls': 0,
            'checks': 0,
            'threebets': 0,
            'threebet_opportunities': 0,
            'faced_3bet': 0,
            'folded_to_3bet': 0,
            'cbets': 0,
            'cbet_opportunities': 0,
            'player_type': PlayerType.UNKNOWN,
            'position': None
        })
        
        try:
            self.setup_ui()
            self.setup_file_watcher()
            self.refresh_timer = QTimer()
            self.refresh_timer.timeout.connect(self.refresh_stats)
            self.refresh_timer.start(5000)
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            
    def apply_dark_theme(self):
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(palette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(palette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(palette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(palette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(palette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(palette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(palette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(palette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(palette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(palette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(palette.ColorRole.HighlightedText, QColor(0, 0, 0))
        self.setPalette(palette)

    def initialize_database(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_name TEXT PRIMARY KEY,
                    total_hands INTEGER,
                    vpip_hands INTEGER,
                    pfr_hands INTEGER,
                    total_actions INTEGER,
                    bets INTEGER,
                    raises INTEGER,
                    calls INTEGER,
                    checks INTEGER,
                    threebets INTEGER,
                    threebet_opportunities INTEGER,
                    faced_3bet INTEGER,
                    folded_to_3bet INTEGER,
                    cbets INTEGER,
                    cbet_opportunities INTEGER,
                    player_type TEXT,
                    last_position TEXT
                )
            ''')
            conn.commit()
                
    def poker_site_changed(self, site_name):
        self.current_poker_site = site_name
        self.status_bar.showMessage(f"Selected poker site: {site_name}")
        # Clear any existing data when switching sites
        self.stats_table.setRowCount(0)
        self.current_players = set()
        self.session_stats = defaultdict(lambda: {
            'total_hands': 0,
            'vpip_hands': 0,
            'pfr_hands': 0,
            'total_actions': 0,
            'bets': 0,
            'raises': 0,
            'calls': 0,
            'checks': 0,
            'threebets': 0,
            'threebet_opportunities': 0,
            'faced_3bet': 0,
            'folded_to_3bet': 0,
            'cbets': 0,
            'cbet_opportunities': 0,
            'player_type': PlayerType.UNKNOWN,
            'position': None
        })
        
        # Reset watcher when changing sites
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        
        self.setup_file_watcher()
    

    def is_player_active(self, hand_lines, player):
        # For RedStar XML format
        if self.current_poker_site == "Red Star Poker":
            for player_element in hand_lines:
                if player_element.get('name') == player:
                    # Player is active if they have chips and seat is listed
                    return player_element.get('chips') is not None and player_element.get('seat') is not None
            return False
        
        # For text-based formats
        for line in hand_lines:
            if player in line:
                if "sitting out" in line or "is sitting out" in line:
                    return False
                if (self.current_poker_site == "PokerStars" and "in chips" in line and "Seat" in line) or \
                (self.current_poker_site == "888poker" and "Seat" in line and player in line and "(" in line):
                    return True
        return False

    def load_player_stats(self, player_name):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM player_stats WHERE player_name = ?', (player_name,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'total_hands': row[1] or 0,
                    'vpip_hands': row[2] or 0,
                    'pfr_hands': row[3] or 0,
                    'total_actions': row[4] or 0,
                    'bets': row[5] or 0,
                    'raises': row[6] or 0,
                    'calls': row[7] or 0,
                    'checks': row[8] or 0,
                    'threebets': row[9] or 0,
                    'threebet_opportunities': row[10] or 0,
                    'faced_3bet': row[11] or 0,
                    'folded_to_3bet': row[12] or 0,
                    'cbets': row[13] or 0,
                    'cbet_opportunities': row[14] or 0,
                    'player_type': row[15] or PlayerType.UNKNOWN,
                    'position': row[16]
                }
            return None

    
    def save_player_stats(self, player_name, stats):
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO player_stats (
                    player_name, total_hands, vpip_hands, pfr_hands,
                    total_actions, bets, raises, calls, checks,
                    threebets, threebet_opportunities, faced_3bet,
                    folded_to_3bet, cbets, cbet_opportunities,
                    player_type, last_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_name,
                stats['total_hands'],
                stats['vpip_hands'],
                stats['pfr_hands'],
                stats['total_actions'],
                stats['bets'],
                stats['raises'],
                stats['calls'],
                stats['checks'],
                stats['threebets'],
                stats['threebet_opportunities'],
                stats['faced_3bet'],
                stats['folded_to_3bet'],
                stats['cbets'],
                stats['cbet_opportunities'],
                str(stats['player_type']),
                stats['position']
            ))
            conn.commit()
          
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Site selection group
        site_selection_layout = QHBoxLayout()
        site_label = QLabel("Poker Site:")
        site_label.setStyleSheet("color: white;")
        
        self.site_combo = QComboBox()
        self.site_combo.addItems(["PokerStars", "888poker", "Red Star Poker"])
        self.site_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                padding: 5px;
            }
            QComboBox:drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #3d3d3d;
            }
        """)
        self.site_combo.currentTextChanged.connect(self.poker_site_changed)
        
        site_selection_layout.addWidget(site_label)
        site_selection_layout.addWidget(self.site_combo)
        site_selection_layout.addStretch()
        
        layout.addLayout(site_selection_layout)
        
        self.stats_table = QTableWidget()
        self.setup_table()
        layout.addWidget(self.stats_table)
        
        button_layout = QHBoxLayout()
        
        select_folder_button = QPushButton("Select History Folder")
        select_folder_button.clicked.connect(self.select_history_folder)
        button_layout.addWidget(select_folder_button)
        
        refresh_button = QPushButton("Refresh Stats")
        refresh_button.clicked.connect(self.refresh_stats)
        button_layout.addWidget(refresh_button)
        
        layout.addLayout(button_layout)

    def setup_table(self):
        headers = ["Player", "Type", "Hands", "VPIP%", "PFR%", "AF", "3Bet%", "F3B%", "CBet%"]
        self.stats_table.setColumnCount(len(headers))
        self.stats_table.setHorizontalHeaderLabels(headers)
        self.stats_table.horizontalHeader().setStretchLastSection(False)
        
        # Add these lines
        self.stats_table.verticalHeader().setDefaultSectionSize(50)  # Increase row height
        self.stats_table.horizontalHeader().setDefaultSectionSize(100)  # Increase column width
        self.stats_table.setTextElideMode(Qt.TextElideMode.ElideNone)

    def get_range_distance(self, value, range_tuple):
        min_val, max_val = range_tuple
        if value < min_val:
            return min_val - value
        elif value > max_val:
            return value - max_val
        return 0  # value is within range

    def get_adjusted_profiles(self, total_hands):
        # Base profiles - keeping the same ranges
        base_profiles = {
            PlayerType.TAG: {
                'vpip': (20, 26), 
                'pfr': (16, 22), 
                'af': (2.0, 3.0), 
                'threeb': (6, 9)
            },
            PlayerType.LAG: {
                'vpip': (28, 35), 
                'pfr': (22, 28), 
                'af': (2.5, 3.5), 
                'threeb': (9, 13)
            },
            PlayerType.NIT: {
                'vpip': (12, 16), 
                'pfr': (8, 12), 
                'af': (1.2, 1.8), 
                'threeb': (2, 4)
            },
            PlayerType.FISH: {
                'vpip': (35, 50), 
                'pfr': (12, 18), 
                'af': (0.8, 1.2), 
                'threeb': (2, 5)
            },
            PlayerType.MANIAC: {
                'vpip': (40, 60), 
                'pfr': (30, 45), 
                'af': (3.5, 5.0), 
                'threeb': (15, 25)
            }
        }

        # New dynamic adjustments per stat type
        adjustments = {
            'vpip': max(0.02, 0.4 * (math.log(20) / math.log(max(20, total_hands)))),  
            'pfr': max(0.02, 0.45 * (math.log(20) / math.log(max(20, total_hands)))),  
            'af': max(0.02, 0.6 * (math.log(20) / math.log(max(20, total_hands)))),    
            'threeb': max(0.03, 0.7 * (math.log(20) / math.log(max(20, total_hands)))) 
        }

        adjusted_profiles = {}
        for ptype, profile in base_profiles.items():
            adjusted_profiles[ptype] = {}
            for stat, (min_val, max_val) in profile.items():
                margin = adjustments[stat]
                range_size = max_val - min_val
                adjustment = range_size * margin
                adjusted_profiles[ptype][stat] = (
                    max(0, min_val - adjustment),
                    max_val + adjustment
                )

        return adjusted_profiles

    def determine_player_type(self, stats):
        if stats['total_hands'] < 10:
            return PlayerType.UNKNOWN

        try:
            # Calculate core stats
            vpip = (stats['vpip_hands'] / stats['total_hands']) * 100
            pfr = (stats['pfr_hands'] / stats['total_hands']) * 100
            af = (stats['bets'] + stats['raises']) / max(1, (stats['calls'] + stats['checks']))
            threeb = (stats['threebets'] / max(1, stats['threebet_opportunities'])) * 100

            # Get profiles adjusted for sample size
            profiles = self.get_adjusted_profiles(stats['total_hands'])

            # Different weights for different stats
            weights = {'vpip': 1.0, 'pfr': 1.0, 'af': 0.7, 'threeb': 0.5}
            player_stats = {'vpip': vpip, 'pfr': pfr, 'af': af, 'threeb': threeb}

            # Calculate distance to each profile
            distances = {}
            for ptype, profile in profiles.items():
                distance = 0
                for stat, value in player_stats.items():
                    diff = self.get_range_distance(value, profile[stat])
                    distance += diff * weights[stat]
                distances[ptype] = distance

            # Return INITIAL for very small samples
            if stats['total_hands'] < 20:
                return PlayerType.INITIAL

            # Find closest match
            best_match = min(distances.items(), key=lambda x: x[1])
            
            # If the distance is too large, return UNKNOWN
            if best_match[1] > 30:
                if stats['total_hands'] < 100:
                    return PlayerType.INITIAL
                return PlayerType.UNKNOWN

            return best_match[0]

        except ZeroDivisionError:
            return PlayerType.UNKNOWN

    def get_color_for_type(self, player_type):
        color_map = {
            PlayerType.TAG: PlayerColors.TAG,
            PlayerType.LAG: PlayerColors.LAG,
            PlayerType.NIT: PlayerColors.NIT,
            PlayerType.FISH: PlayerColors.FISH,
            PlayerType.MANIAC: PlayerColors.MANIAC,
            PlayerType.UNKNOWN: PlayerColors.UNKNOWN,
            PlayerType.INITIAL: PlayerColors.INITIAL
        }
        return color_map.get(player_type, PlayerColors.UNKNOWN)

    def setup_file_watcher(self):
        try:
            if self.current_poker_site == "PokerStars":
                default_path = Path.home() / "AppData" / "Local" / "PokerStars" / "HandHistory"
            elif self.current_poker_site == "888poker":
                default_path = Path.home() / "Documents" / "888poker" / "HandHistory"
            else:  # Red Star Poker
                default_path = Path.home() / "AppData" / "Local" / "Red Star Poker" / "data"
                
            if not default_path.exists():
                default_path.mkdir(parents=True, exist_ok=True)
                
            if not default_path.is_dir():
                self.select_history_folder()
            else:
                self.history_path = default_path
                self.start_watching()
                
        except (PermissionError, OSError) as e:
            print(f"Error accessing default path: {str(e)}")
            self.select_history_folder()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        current_scale = get_scale_level(self.width())
        apply_scaling(self.stats_table, current_scale)
            
    def start_watching(self):
        self.observer = Observer()
        self.event_handler = PokerHandHistoryWatcher(self)
        
        # For Red Star Poker, we need to monitor both tables and tournaments folders
        if self.current_poker_site == "Red Star Poker":
            # Main folder watcher
            self.observer.schedule(self.event_handler, str(self.history_path), recursive=False)
            
            # Tables folder
            tables_path = self.history_path / "Tables"
            if tables_path.exists() and tables_path.is_dir():
                self.observer.schedule(self.event_handler, str(tables_path), recursive=True)
            else:
                tables_path.mkdir(exist_ok=True)
                self.observer.schedule(self.event_handler, str(tables_path), recursive=True)
                
            # Tournaments folder
            tournaments_path = self.history_path / "Tournaments"
            if tournaments_path.exists() and tournaments_path.is_dir():
                self.observer.schedule(self.event_handler, str(tournaments_path), recursive=True)
            else:
                tournaments_path.mkdir(exist_ok=True)
                self.observer.schedule(self.event_handler, str(tournaments_path), recursive=True)
                
            self.status_bar.showMessage(f"Monitoring: {self.history_path} (Tables and Tournaments folders)")
        else:
            # For PokerStars and 888poker, just monitor the single directory
            self.observer.schedule(self.event_handler, str(self.history_path), recursive=True)
            self.status_bar.showMessage(f"Monitoring: {self.history_path} ({self.current_poker_site})")
            
        self.observer.start()
        
    def select_history_folder(self):
        if self.current_poker_site == "Red Star Poker":
            folder = QFileDialog.getExistingDirectory(self, "Select Red Star Poker Data Folder (containing Tables and Tournaments)")
        else:
            folder = QFileDialog.getExistingDirectory(self, f"Select {self.current_poker_site} Hand History Folder")
            
        if folder:
            self.history_path = Path(folder)
            if hasattr(self, 'observer'):
                self.observer.stop()
                self.observer.join()
            self.start_watching()
            
    def process_new_hands(self, content):
        if self.current_poker_site == "Red Star Poker":
            self.process_redstar_xml(content)
        else:
            self.process_text_hands(content)
            
    def process_text_hands(self, content):
        MAX_HAND_LINES = 200  # Reasonable max for a single hand
        current_hand = []
        for line in content.splitlines():
            if len(line.strip()) == 0:  # Skip empty lines
                continue
            
            # Detect start of hand based on site format
            is_new_hand = False
            if self.current_poker_site == "PokerStars" and "PokerStars Hand #" in line:
                is_new_hand = True
            elif self.current_poker_site == "888poker" and ("888poker Hand History for Game" in line or 
                                                        "#Game No :" in line):
                is_new_hand = True
                
            if is_new_hand:
                if current_hand:
                    if len(current_hand) < MAX_HAND_LINES:  # Validate hand size
                        self.process_hand(current_hand)
                    current_hand = [line]
                else:
                    current_hand = [line]
            else:
                current_hand.append(line)
                
        if current_hand and len(current_hand) < MAX_HAND_LINES:
            self.process_hand(current_hand)
            
    def process_redstar_xml(self, content):
        try:
            # Parse XML content
            root = ET.fromstring(content)
            
            # Process each game element (hand) in the session
            for game_element in root.findall('.//game'):
                self.process_hand(game_element)
                
        except ET.ParseError as e:
            print(f"XML parsing error: {str(e)}")
        except Exception as e:
            print(f"Error processing Red Star XML: {str(e)}")

    def parse_table_info(self, hand_lines):
        if self.current_poker_site == "PokerStars":
            return self.parse_pokerstars_table_info(hand_lines)
        elif self.current_poker_site == "888poker":
            return self.parse_888poker_table_info(hand_lines)
        else:  # Red Star Poker
            return self.parse_redstar_table_info(hand_lines)
            
    def parse_pokerstars_table_info(self, hand_lines):
        print("\n=== NEW HAND (PokerStars) ===")
        print("Parsing table info...")
        
        table_info = {
            'max_seats': 9,
            'reported_button': None,
            'actual_button': None,
            'active_players': [],
            'sb_player': None,
            'bb_player': None,
            'seat_sequence': []
        }
        
        # First build ordered seat sequence and active players
        for line in hand_lines:
            if "Table '" in line:
                if "-max" in line:
                    max_seats = int(line.split("-max")[0].split()[-1])
                    table_info['max_seats'] = max_seats
                    print(f"Table type: {max_seats}-max")
                    
            if "Seat " in line and "in chips" in line:
                seat_match = re.search(r"Seat (\d): (.*?) \(", line)
                if seat_match and "sitting out" not in line:
                    seat = int(seat_match.group(1))
                    name = seat_match.group(2)
                    table_info['seat_sequence'].append(seat)
                    table_info['active_players'].append({
                        'seat': seat,
                        'name': name
                    })
                    print(f"Active player: {name} in seat {seat}")
        
        # Sort seat sequence
        table_info['seat_sequence'].sort()
        
        # Get reported button and calculate actual button
        for line in hand_lines:
            if "is the button" in line:
                match = re.search(r"Seat #(\d)", line)
                if match:
                    print("\n=== BUTTON POSITION DEBUG ===")
                    reported_button = int(match.group(1))
                    table_info['reported_button'] = reported_button
                    print(f"Hand history reports button in seat: {reported_button}")
                    print(f"That seat is occupied by: {[p['name'] for p in table_info['active_players'] if p['seat'] == reported_button][0]}")
                    
                    # Get next player's seat for actual button
                    sorted_seats = table_info['seat_sequence']
                    current_idx = sorted_seats.index(reported_button)
                    actual_button_idx = (current_idx + 1) % len(sorted_seats)
                    actual_button_seat = sorted_seats[actual_button_idx]
                    
                    table_info['actual_button'] = actual_button_seat
                    actual_button_player = next(p['name'] for p in table_info['active_players'] if p['seat'] == actual_button_seat)
                    print(f"Actual button seat is: {actual_button_seat}")
                    print(f"Actual button player is: {actual_button_player}")
        
        # Get blind posters
        for line in hand_lines:
            if "posts small blind" in line:
                player = line.split(":")[0].strip()
                table_info['sb_player'] = player
            elif "posts big blind" in line:
                player = line.split(":")[0].strip() 
                table_info['bb_player'] = player
                
        return table_info
        
    def parse_888poker_table_info(self, hand_lines):
        print("\n=== NEW HAND (888poker) ===")
        print("Parsing table info...")
        
        table_info = {
            'max_seats': 9,
            'reported_button': None,
            'actual_button': None,
            'active_players': [],
            'sb_player': None,
            'bb_player': None,
            'seat_sequence': []
        }
        
        # Parse max seats
        for line in hand_lines:
            if "Max" in line and "Table" in line:
                max_seats_match = re.search(r'Table .* (\d+) Max', line)
                if max_seats_match:
                    table_info['max_seats'] = int(max_seats_match.group(1))
                    print(f"Table type: {table_info['max_seats']}-max")
        
        # Parse active players and seats
        for line in hand_lines:
            if "Seat " in line and "(" in line and ")" in line and not "posts" in line:
                seat_match = re.search(r"Seat (\d+): (\S+) \(\s*([\d,]+)\s*\)", line)
                if seat_match:
                    seat = int(seat_match.group(1))
                    name = seat_match.group(2)
                    table_info['seat_sequence'].append(seat)
                    table_info['active_players'].append({
                        'seat': seat,
                        'name': name
                    })
                    print(f"Active player: {name} in seat {seat}")
        
        # Sort seat sequence
        table_info['seat_sequence'].sort()
        
        # Parse button position
        for line in hand_lines:
            if "is the button" in line:
                match = re.search(r"Seat (\d+) is the button", line)
                if match:
                    print("\n=== BUTTON POSITION DEBUG ===")
                    reported_button = int(match.group(1))
                    table_info['reported_button'] = reported_button
                    table_info['actual_button'] = reported_button  # For 888poker, these are the same
                    print(f"Button is in seat: {reported_button}")
                    if table_info['active_players']:
                        button_player = next((p['name'] for p in table_info['active_players'] if p['seat'] == reported_button), None)
                        if button_player:
                            print(f"Button player is: {button_player}")
        
        # Parse blinds
        for line in hand_lines:
            if "posts small blind" in line:
                player = line.split("posts small blind")[0].strip()
                table_info['sb_player'] = player
                print(f"SB player: {player}")
            elif "posts big blind" in line:
                player = line.split("posts big blind")[0].strip()
                table_info['bb_player'] = player
                print(f"BB player: {player}")
                
        return table_info

    def parse_redstar_table_info(self, hand_element):
        print("\n=== NEW HAND (Red Star Poker) ===")
        print("Parsing table info...")
        
        table_info = {
            'max_seats': 9,
            'reported_button': None,
            'actual_button': None,
            'active_players': [],
            'sb_player': None,
            'bb_player': None,
            'seat_sequence': []
        }
        
        # Get general information
        general_element = hand_element.find('general')
        if general_element is not None:
            # Find max seats based on players
            players_element = general_element.find('players')
            if players_element is not None:
                players = players_element.findall('player')
                # Find max seat value to determine table size
                all_seats = [int(p.get('seat', '0')) for p in players]
                if all_seats:
                    max_seat = max(all_seats)
                    table_info['max_seats'] = min(10, max_seat)  # Cap at 10
                    print(f"Table type: {table_info['max_seats']}-max")
                    
                # Get active players
                for player in players:
                    seat = int(player.get('seat', '0'))
                    name = player.get('name', '')
                    dealer = player.get('dealer', '0')
                    
                    if seat > 0 and name:
                        table_info['seat_sequence'].append(seat)
                        table_info['active_players'].append({
                            'seat': seat,
                            'name': name
                        })
                        
                        # Find dealer
                        if dealer == '1':
                            table_info['reported_button'] = seat
                            table_info['actual_button'] = seat  # For Red Star, these are the same
                            print(f"Button player is: {name} in seat {seat}")
                            
                        print(f"Active player: {name} in seat {seat}")
        
        # Sort seat sequence
        table_info['seat_sequence'].sort()
        
        # Find blinds from first round
        rounds = hand_element.findall('round')
        if rounds and len(rounds) > 0:
            blind_actions = rounds[0].findall('action')
            for action in blind_actions:
                action_type = action.get('type')
                player_name = action.get('player')
                
                # Type 1 = small blind, Type 2 = big blind
                if action_type == '1' and player_name:
                    table_info['sb_player'] = player_name
                    print(f"SB player: {player_name}")
                elif action_type == '2' and player_name:
                    table_info['bb_player'] = player_name
                    print(f"BB player: {player_name}")
        
        return table_info

    def get_player_position(self, hand_lines, player_name):
        try:
            player_seat = None
            active_seats = []
            
            # Use the appropriate table info parser based on the site
            table_info = self.parse_table_info(hand_lines)
            actual_button_seat = table_info['actual_button']

            # Get active seats and player seat
            for player in table_info['active_players']:
                active_seats.append(player['seat'])
                if player['name'] == player_name:
                    player_seat = player['seat']

            if not player_seat:
                return None

            active_seats.sort()
            total_players = len(active_seats)
            btn_idx = active_seats.index(actual_button_seat)
            
            print("\n=== POSITION MAPPING ===")
            print(f"Total players: {total_players}")
            print(f"Button index: {btn_idx}")
            
            # Calculate SB and BB positions
            sb_idx = (btn_idx + 1) % total_players
            bb_idx = (btn_idx + 2) % total_players
            
            # Initialize positions array
            positions = [''] * total_players
            
            # Assign BTN, SB, BB first
            positions[btn_idx] = 'BTN'
            positions[sb_idx] = 'SB'
            positions[bb_idx] = 'BB'
            
            # Assign remaining positions working backwards from BTN
            if total_players >= 9:
                pos_sequence = ['CO', 'HJ', 'MP+1', 'MP', 'UTG+2', 'UTG+1', 'UTG']
            elif total_players >= 7:
                pos_sequence = ['CO', 'HJ', 'MP', 'UTG+1', 'UTG']
            elif total_players >= 6:
                pos_sequence = ['CO', 'HJ', 'UTG']
            else:
                pos_sequence = ['CO', 'UTG']
                
            current_pos_idx = 0
            for i in range(total_players - 3):  # -3 for BTN, SB, BB
                pos_idx = (btn_idx - 1 - i) % total_players
                if current_pos_idx < len(pos_sequence):
                    positions[pos_idx] = pos_sequence[current_pos_idx]
                    current_pos_idx += 1
                else:
                    positions[pos_idx] = 'Unknown'

            # Print detailed position mapping
            print("\n=== POSITION SUMMARY ===")
            for i, seat in enumerate(active_seats):
                player = next(p['name'] for p in table_info['active_players'] if p['seat'] == seat)
                print(f"Seat {seat} ({positions[i]}): {player}")

            # Find player's position
            player_idx = active_seats.index(player_seat)
            position = positions[player_idx]
            print(f"\nPlayer {player_name} is in position: {position}")

            return position

        except Exception as e:
            print(f"Error determining position: {str(e)}")
            return None
    

    
    def process_hand(self, hand_lines):
        try:
            # Handle different formats based on poker site
            if self.current_poker_site == "Red Star Poker":
                self.process_redstar_hand(hand_lines)
            else:
                self.process_text_hand(hand_lines)
        
        except Exception as e:
            print(f"Error processing hand: {str(e)}")
    
    def process_text_hand(self, hand_lines):
        # Get table info first
        table_info = self.parse_table_info(hand_lines)
        current_hand_players = set(player['name'] for player in table_info['active_players'])
        
        # Update current_players instead of replacing it
        self.current_players = current_hand_players
        
        # Load or initialize stats
        for player in current_hand_players:
            existing_stats = self.load_player_stats(player)
            if existing_stats:
                self.player_stats[player] = existing_stats
            else:
                self.player_stats[player] = {
                    'total_hands': 0,
                    'vpip_hands': 0,
                    'pfr_hands': 0,
                    'total_actions': 0,
                    'bets': 0,
                    'raises': 0,
                    'calls': 0,
                    'checks': 0,
                    'threebets': 0,
                    'threebet_opportunities': 0,
                    'faced_3bet': 0,
                    'folded_to_3bet': 0,
                    'cbets': 0,
                    'cbet_opportunities': 0,
                    'player_type': PlayerType.UNKNOWN,
                    'position': None
                }

        players_in_hand = set()
        current_street = 'preflop'
        pot_players = set()
        initial_raiser = None
        had_opportunity = set()
        facing_3bet = set()
        last_preflop_aggressor = None
        cbet_opportunity_tracked = False
        first_flop_action = True
        
        # First pass - get positions
        for player in table_info['active_players']:
            player_name = player['name']
            if self.is_player_active(hand_lines, player_name):
                players_in_hand.add(player_name)
                pot_players.add(player_name)
                position = self.get_player_position(hand_lines, player_name)
                self.player_stats[player_name]['position'] = position
                self.session_stats[player_name]['position'] = position

        # Process actions
        for line in hand_lines:
            # Track street changes based on site format
            if self.current_poker_site == "PokerStars":
                if "*** FLOP ***" in line:
                    current_street = 'flop'
                    first_flop_action = True
                elif "*** TURN ***" in line:
                    current_street = 'turn'
                elif "*** RIVER ***" in line:
                    current_street = 'river'
            else:  # 888poker
                if "** Dealing flop **" in line:
                    current_street = 'flop'
                    first_flop_action = True
                elif "** Dealing turn **" in line:
                    current_street = 'turn'
                elif "** Dealing river **" in line:
                    current_street = 'river'
        
            if current_street == 'preflop':
                for player in players_in_hand:
                    # Process action detection based on site format
                    player_action = False
                    
                    if self.current_poker_site == "PokerStars" and f"{player}: " in line:
                        player_action = True
                    elif self.current_poker_site == "888poker" and player in line and (
                        line.startswith(player + " ") or 
                        ": " + player + " " in line or 
                        "Seat " + player in line):
                        player_action = True
                        
                    if player_action:
                        if "raises" in line:
                            last_preflop_aggressor = player
                            if initial_raiser is None:
                                initial_raiser = player
                                had_opportunity.update(pot_players - {player})
                            elif player in had_opportunity:
                                self.player_stats[player]['threebets'] += 1
                                self.session_stats[player]['threebets'] += 1
                                facing_3bet.update(pot_players - {player})
                            
                        if any(action in line for action in ["calls", "raises", "folds", "bets", "checks"]):
                            self.player_stats[player]['total_actions'] += 1
                            self.session_stats[player]['total_actions'] += 1
                            
                            if "raises" in line:
                                self.player_stats[player]['vpip_hands'] += 1
                                self.player_stats[player]['pfr_hands'] += 1
                                self.player_stats[player]['raises'] += 1
                                self.session_stats[player]['vpip_hands'] += 1
                                self.session_stats[player]['pfr_hands'] += 1
                                self.session_stats[player]['raises'] += 1
                            elif "calls" in line and player not in [table_info['sb_player'], table_info['bb_player']]:
                                self.player_stats[player]['vpip_hands'] += 1
                                self.player_stats[player]['calls'] += 1
                                self.session_stats[player]['vpip_hands'] += 1
                                self.session_stats[player]['calls'] += 1
                            elif "checks" in line:
                                self.player_stats[player]['checks'] += 1
                                self.session_stats[player]['checks'] += 1
                            elif "folds" in line:
                                pot_players.remove(player)
                                if player in facing_3bet:
                                    self.player_stats[player]['folded_to_3bet'] += 1
                                    self.session_stats[player]['folded_to_3bet'] += 1
            
            else:  # postflop
                # Track cbet opportunity on the flop
                if current_street == 'flop' and not cbet_opportunity_tracked and last_preflop_aggressor and last_preflop_aggressor in pot_players:
                    self.player_stats[last_preflop_aggressor]['cbet_opportunities'] += 1
                    self.session_stats[last_preflop_aggressor]['cbet_opportunities'] += 1
                    cbet_opportunity_tracked = True

                for player in players_in_hand:
                    # Process action detection based on site format
                    player_action = False
                    
                    if self.current_poker_site == "PokerStars" and f"{player}: " in line:
                        player_action = True
                    elif self.current_poker_site == "888poker" and player in line and (
                        line.startswith(player + " ") or 
                        ": " + player + " " in line or 
                        "Seat " + player in line):
                        player_action = True
                        
                    if player_action:
                        if any(action in line for action in ["calls", "raises", "folds", "bets", "checks"]):
                            self.player_stats[player]['total_actions'] += 1
                            self.session_stats[player]['total_actions'] += 1
                            
                            # Track cbet when the last preflop aggressor makes first bet on flop
                            if current_street == 'flop' and first_flop_action and player == last_preflop_aggressor and "bets" in line:
                                self.player_stats[player]['cbets'] += 1
                                self.session_stats[player]['cbets'] += 1
                            
                            if "bets" in line:
                                self.player_stats[player]['bets'] += 1
                                self.session_stats[player]['bets'] += 1
                            elif "raises" in line:
                                self.player_stats[player]['raises'] += 1
                                self.session_stats[player]['raises'] += 1
                            elif "calls" in line:
                                self.player_stats[player]['calls'] += 1
                                self.session_stats[player]['calls'] += 1
                            elif "checks" in line:
                                self.player_stats[player]['checks'] += 1
                                self.session_stats[player]['checks'] += 1
                            elif "folds" in line:
                                pot_players.remove(player)
                            
                            if current_street == 'flop':
                                first_flop_action = False
        
        # Update final stats
        for player in players_in_hand:
            self.player_stats[player]['total_hands'] += 1
            self.session_stats[player]['total_hands'] += 1
            if player in had_opportunity:
                self.player_stats[player]['threebet_opportunities'] += 1
                self.session_stats[player]['threebet_opportunities'] += 1
            if player in facing_3bet:
                self.player_stats[player]['faced_3bet'] += 1
                self.session_stats[player]['faced_3bet'] += 1
        
        # Save to database
        for player in players_in_hand:
            self.player_stats[player]['player_type'] = self.determine_player_type(self.player_stats[player])
            self.session_stats[player]['player_type'] = self.determine_player_type(self.session_stats[player])
            self.save_player_stats(player, self.player_stats[player])
    
    def process_redstar_hand(self, hand_element):
        # Get table info first
        table_info = self.parse_table_info(hand_element)
        current_hand_players = set(player['name'] for player in table_info['active_players'])
        
        # Update current players
        self.current_players = current_hand_players
        
        # Load or initialize stats
        for player in current_hand_players:
            existing_stats = self.load_player_stats(player)
            if existing_stats:
                self.player_stats[player] = existing_stats
            else:
                self.player_stats[player] = {
                    'total_hands': 0,
                    'vpip_hands': 0,
                    'pfr_hands': 0,
                    'total_actions': 0,
                    'bets': 0,
                    'raises': 0,
                    'calls': 0,
                    'checks': 0,
                    'threebets': 0,
                    'threebet_opportunities': 0,
                    'faced_3bet': 0,
                    'folded_to_3bet': 0,
                    'cbets': 0,
                    'cbet_opportunities': 0,
                    'player_type': PlayerType.UNKNOWN,
                    'position': None
                }
                
        players_in_hand = set()
        pot_players = set()
        initial_raiser = None
        had_opportunity = set()
        facing_3bet = set()
        last_preflop_aggressor = None
        cbet_opportunity_tracked = False
        first_flop_action = True
        
        # Get active players from 'player' elements
        players_element = hand_element.find('./general/players')
        if players_element is None:
            return  # No players found
            
        # First pass - get positions
        for player_element in players_element.findall('player'):
            player_name = player_element.get('name')
            if player_name and self.is_player_active(players_element.findall('player'), player_name):
                players_in_hand.add(player_name)
                pot_players.add(player_name)
                position = self.get_player_position(hand_element, player_name)
                self.player_stats[player_name]['position'] = position
                self.session_stats[player_name]['position'] = position
                
        # Process rounds and actions
        rounds = hand_element.findall('round')
        current_street = 'preflop'
        
        for round_idx, round_element in enumerate(rounds):
            # Map round numbers to streets
            # In Red Star format, round 0 = blinds/antes, round 1 = preflop, round 2 = flop, etc.
            if round_idx == 1:  # Preflop
                current_street = 'preflop'
            elif round_idx == 2:  # Flop
                current_street = 'flop'
                first_flop_action = True
                # Track cbet opportunity
                if last_preflop_aggressor and last_preflop_aggressor in pot_players:
                    self.player_stats[last_preflop_aggressor]['cbet_opportunities'] += 1
                    self.session_stats[last_preflop_aggressor]['cbet_opportunities'] += 1
                    cbet_opportunity_tracked = True
            elif round_idx == 3:  # Turn
                current_street = 'turn'
            elif round_idx == 4:  # River
                current_street = 'river'
                
            # Process actions within the round
            actions = round_element.findall('action')
            
            for action in actions:
                player = action.get('player')
                action_type = action.get('type')
                
                if player not in players_in_hand:
                    continue
                    
                # Track actions based on Red Star's action types
                # Type 0 = fold, Type 3 = call, Type 4 = check, Type 5 = bet, Type 23 = raise
                if current_street == 'preflop':
                    if action_type == '23':  # Raise
                        last_preflop_aggressor = player
                        if initial_raiser is None:
                            initial_raiser = player
                            had_opportunity.update(pot_players - {player})
                        elif player in had_opportunity:
                            self.player_stats[player]['threebets'] += 1
                            self.session_stats[player]['threebets'] += 1
                            facing_3bet.update(pot_players - {player})
                            
                    # Count all actions
                    if action_type in ['0', '3', '4', '5', '23']:
                        self.player_stats[player]['total_actions'] += 1
                        self.session_stats[player]['total_actions'] += 1
                        
                        if action_type == '23':  # Raise
                            self.player_stats[player]['vpip_hands'] += 1
                            self.player_stats[player]['pfr_hands'] += 1
                            self.player_stats[player]['raises'] += 1
                            self.session_stats[player]['vpip_hands'] += 1
                            self.session_stats[player]['pfr_hands'] += 1
                            self.session_stats[player]['raises'] += 1
                        elif action_type == '3':  # Call
                            self.player_stats[player]['vpip_hands'] += 1
                            self.player_stats[player]['calls'] += 1
                            self.session_stats[player]['vpip_hands'] += 1
                            self.session_stats[player]['calls'] += 1
                        elif action_type == '4':  # Check
                            self.player_stats[player]['checks'] += 1
                            self.session_stats[player]['checks'] += 1
                        elif action_type == '0':  # Fold
                            pot_players.remove(player)
                            if player in facing_3bet:
                                self.player_stats[player]['folded_to_3bet'] += 1
                                self.session_stats[player]['folded_to_3bet'] += 1
                
                else:  # postflop streets
                    if action_type in ['0', '3', '4', '5', '23']:
                        self.player_stats[player]['total_actions'] += 1
                        self.session_stats[player]['total_actions'] += 1
                        
                        # Track cbet on flop
                        if current_street == 'flop' and first_flop_action and player == last_preflop_aggressor and action_type == '5':
                            self.player_stats[player]['cbets'] += 1
                            self.session_stats[player]['cbets'] += 1
                            
                        if action_type == '5':  # Bet
                            self.player_stats[player]['bets'] += 1
                            self.session_stats[player]['bets'] += 1
                        elif action_type == '23':  # Raise
                            self.player_stats[player]['raises'] += 1
                            self.session_stats[player]['raises'] += 1
                        elif action_type == '3':  # Call
                            self.player_stats[player]['calls'] += 1
                            self.session_stats[player]['calls'] += 1
                        elif action_type == '4':  # Check
                            self.player_stats[player]['checks'] += 1
                            self.session_stats[player]['checks'] += 1
                        elif action_type == '0':  # Fold
                            pot_players.remove(player)
                            
                        if current_street == 'flop':
                            first_flop_action = False
                            
        # Update final stats
        for player in players_in_hand:
            self.player_stats[player]['total_hands'] += 1
            self.session_stats[player]['total_hands'] += 1
            if player in had_opportunity:
                self.player_stats[player]['threebet_opportunities'] += 1
                self.session_stats[player]['threebet_opportunities'] += 1
            if player in facing_3bet:
                self.player_stats[player]['faced_3bet'] += 1
                self.session_stats[player]['faced_3bet'] += 1
                
        # Save to database
        for player in players_in_hand:
            self.player_stats[player]['player_type'] = self.determine_player_type(self.player_stats[player])
            self.session_stats[player]['player_type'] = self.determine_player_type(self.session_stats[player])
            self.save_player_stats(player, self.player_stats[player])
    

    def refresh_stats(self):
        print(f"Current players: {self.current_players}")  # Debug line
        
        stats_dict = {}
        # First get stats from database
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            if self.current_players:  # Only query if we have players
                query = 'SELECT * FROM player_stats WHERE player_name IN ({})'.format(
                    ','.join('?' * len(self.current_players))
                )
                cursor.execute(query, list(self.current_players))
                all_stats = cursor.fetchall()
                
                for row in all_stats:
                    player = row[0]
                    stats_dict[player] = {
                        'total_hands': row[1] or 0,
                        'vpip_hands': row[2] or 0,
                        'pfr_hands': row[3] or 0,
                        'total_actions': row[4] or 0,
                        'bets': row[5] or 0,
                        'raises': row[6] or 0,
                        'calls': row[7] or 0,
                        'checks': row[8] or 0,
                        'threebets': row[9] or 0,              
                        'threebet_opportunities': row[10] or 0, 
                        'faced_3bet': row[11] or 0,
                        'folded_to_3bet': row[12] or 0,
                        'cbets': row[13] or 0,
                        'cbet_opportunities': row[14] or 0,
                        'player_type': row[15] or PlayerType.UNKNOWN,
                        'position': row[16]
                    }
        
        # Now add any players from current_players that aren't in the database yet
        for player in self.current_players:
            if player not in stats_dict:
                print(f"Adding player not in DB: {player}")  # Debug line
                stats_dict[player] = {
                    'total_hands': 0,
                    'vpip_hands': 0,
                    'pfr_hands': 0,
                    'total_actions': 0,
                    'bets': 0,
                    'raises': 0,
                    'calls': 0,
                    'checks': 0,
                    'threebets': 0,
                    'threebet_opportunities': 0,
                    'faced_3bet': 0,
                    'folded_to_3bet': 0,
                    'cbets': 0,
                    'cbet_opportunities': 0,
                    'player_type': PlayerType.INITIAL,
                    'position': None
                }
                
                # Initialize session stats for new players
                if player not in self.session_stats:
                    self.session_stats[player] = {
                        'total_hands': 0,
                        'vpip_hands': 0,
                        'pfr_hands': 0,
                        'total_actions': 0,
                        'bets': 0,
                        'raises': 0,
                        'calls': 0,
                        'checks': 0,
                        'threebets': 0,
                        'threebet_opportunities': 0,
                        'faced_3bet': 0,
                        'folded_to_3bet': 0,
                        'cbets': 0,
                        'cbet_opportunities': 0,
                        'player_type': PlayerType.INITIAL,
                        'position': None
                    }
                
        sorted_players = sorted(stats_dict.items(),
                    key=lambda x: (self.get_type_priority(x[1]['player_type']),
                                -(x[1]['total_hands'] or 0)))
        
        self.stats_table.setRowCount(len(stats_dict))
        
        current_scale = get_scale_level(self.width())
        
        for row, (player, stats) in enumerate(sorted_players):
            try:
                total_hands = max(1, stats['total_hands'])
                session_total_hands = max(1, self.session_stats[player]['total_hands'])
                
                # Calculate percentages for historical data
                vpip = min(100, (stats['vpip_hands'] / total_hands) * 100)
                pfr = min(100, (stats['pfr_hands'] / total_hands) * 100)
                af = (stats['bets'] + stats['raises']) / max(1, stats['calls'])
                threeb = (stats['threebets'] / max(1, stats['threebet_opportunities'])) * 100
                f3b = (stats['folded_to_3bet'] / max(1, stats['faced_3bet'])) * 100
                cbet = (stats['cbets'] / max(1, stats['cbet_opportunities'])) * 100
                
                # Calculate percentages for session data
                session_vpip = min(100, (self.session_stats[player]['vpip_hands'] / session_total_hands) * 100)
                session_pfr = min(100, (self.session_stats[player]['pfr_hands'] / session_total_hands) * 100)
                session_af = (self.session_stats[player]['bets'] + self.session_stats[player]['raises']) / max(1, self.session_stats[player]['calls'])
                session_threeb = (self.session_stats[player]['threebets'] / max(1, self.session_stats[player]['threebet_opportunities'])) * 100
                session_f3b = (self.session_stats[player]['folded_to_3bet'] / max(1, self.session_stats[player]['faced_3bet'])) * 100
                session_cbet = (self.session_stats[player]['cbets'] / max(1, self.session_stats[player]['cbet_opportunities'])) * 100

                if current_scale['abbreviate']:
                    columns = [
                        (player, ""),
                        (stats['player_type'], self.session_stats[player]['player_type']),
                        (f"{total_hands}", f"{session_total_hands}"),
                        (f"{abbreviate_text(f'{vpip:.1f}%')}", f"{abbreviate_text(f'{session_vpip:.1f}%')}"),
                        (f"{abbreviate_text(f'{pfr:.1f}%')}", f"{abbreviate_text(f'{session_pfr:.1f}%')}"),
                        (f"{af:.2f}", f"{session_af:.2f}"),
                        (f"{abbreviate_text(f'{threeb:.1f}%')}", f"{abbreviate_text(f'{session_threeb:.1f}%')}"),
                        (f"{abbreviate_text(f'{f3b:.1f}%')}", f"{abbreviate_text(f'{session_f3b:.1f}%')}"),
                        (f"{abbreviate_text(f'{cbet:.1f}%')}", f"{abbreviate_text(f'{session_cbet:.1f}%')}")
                    ]
                else:
                    columns = [
                        (player, ""),
                        (stats['player_type'], self.session_stats[player]['player_type']),
                        (f"{total_hands}", f"{session_total_hands}"),
                        (f"{vpip:.1f}%", f"{session_vpip:.1f}%"),
                        (f"{pfr:.1f}%", f"{session_pfr:.1f}%"),
                        (f"{af:.2f}", f"{session_af:.2f}"),
                        (f"{threeb:.1f}%", f"{session_threeb:.1f}%"),
                        (f"{f3b:.1f}%", f"{session_f3b:.1f}%"),
                        (f"{cbet:.1f}%", f"{session_cbet:.1f}%")
                    ]
                
                row_color = self.get_color_for_type(stats['player_type'])
                
                for col, (hist_value, session_value) in enumerate(columns):
                    item = QTableWidgetItem()
                    
                    if col == 1:
                        item.setBackground(row_color)
                    else:
                        item.setBackground(QColor(200, 200, 200))
                    
                    if hist_value and session_value:
                        hist_widget = QLabel(str(hist_value))
                        hist_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
                        hist_widget.setStyleSheet("color: #333333")
                        
                        session_widget = QLabel(str(session_value))
                        session_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        session_widget.setStyleSheet("color: #333333") 
                        
                        container = QWidget()
                        layout = QGridLayout(container)
                        layout.setContentsMargins(0, 0, 0, 0)
                        layout.addWidget(hist_widget, 0, 1)
                        layout.addWidget(session_widget, 1, 0)
                        
                        if col == 1:
                            container.setStyleSheet(f"background-color: {row_color.name()}")
                        else:
                            container.setStyleSheet("background-color: #C8C8C8")
                            
                        self.stats_table.setCellWidget(row, col, container)
                    else:
                        item.setText(hist_value or session_value)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.stats_table.setItem(row, col, item)
                    
            except Exception as e:
                print(f"Error calculating stats for player {player}: {str(e)}")
                continue
        
        # Apply scaling to the entire table
        apply_scaling(self.stats_table, current_scale)
            
    def get_type_priority(self, player_type):
        type_order = {
            PlayerType.TAG: 1,
            PlayerType.LAG: 2,
            PlayerType.NIT: 3,
            PlayerType.FISH: 4,
            PlayerType.MANIAC: 5,
            PlayerType.INITIAL: 6,
            PlayerType.UNKNOWN: 7
        }
        return type_order.get(player_type, 8)

    def closeEvent(self, event):
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    analyzer = LiveHandHistoryAnalyzer()
    analyzer.show()
    sys.exit(app.exec())