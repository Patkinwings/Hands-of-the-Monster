from typing import List, Tuple, Dict, Set, Any
from dataclasses import dataclass
from enum import Enum
import random
import tkinter as tk
from tkinter import ttk
from itertools import combinations
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from collections import Counter
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QSpinBox, QPushButton,
                            QFrame, QGridLayout, QTextEdit, QSizePolicy, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
# monsterhand.py
from simulation import HandRank, Card, Deck, HandEvaluator, simulate_single_round
from analyser import LiveHandHistoryAnalyzer

import numpy as np
import math
from dataclasses import dataclass
from itertools import zip_longest
import multiprocessing

import sys
if sys.platform.startswith('win'):
    import multiprocessing
    multiprocessing.freeze_support()
    # Set start method to 'spawn' to prevent multiple instances
    multiprocessing.set_start_method('spawn', force=True)







class SimulationWorker(QThread):
    simulation_finished = pyqtSignal(dict)
    def __init__(self, hole_cards, community_cards, available_cards, num_players, unknown_cards, sample_size_multiplier=1.0):
        super().__init__()
        self.hole_cards = hole_cards
        self.community_cards = community_cards
        self.available_cards = available_cards
        self.num_players = num_players
        self.unknown_cards = unknown_cards
        self.sample_size_multiplier = sample_size_multiplier
    def run(self):
        results = self.simulate_hand()
        self.simulation_finished.emit(results)
    def determine_sample_size(self):
        hand = HandEvaluator.evaluate_hand(self.hole_cards + self.community_cards)
        player_multiplier = min(1 + (self.num_players - 2) * 0.2, 2.0)
        if hand.rank in {HandRank.STRAIGHT_FLUSH, HandRank.ROYAL_FLUSH}:
            base_samples = 800
        elif hand.rank == HandRank.FOUR_OF_KIND:
            base_samples = 1000
        elif not self.community_cards:
            card1, card2 = sorted(self.hole_cards, key=lambda x: x.get_value(), reverse=True)
            suited = card1.suit == card2.suit
            paired = card1.rank == card2.rank
            if (card1.get_value() >= 13 and card2.get_value() >= 13) or paired:
                base_samples = 4000
            elif suited and abs(card1.get_value() - card2.get_value()) <= 2:
                base_samples = 4500
            elif card1.get_value() < 7 and card2.get_value() < 7:
                base_samples = 1000
            else:
                base_samples = 3500
        elif len(self.community_cards) >= 3:
            suits = defaultdict(int)
            values = []
            pairs = defaultdict(int)
            for card in self.community_cards:
                suits[card.suit] += 1
                values.append(card.get_value())
                pairs[card.get_value()] += 1
            values.sort(reverse=True)
            paired_board = max(pairs.values()) >= 2
            three_of_kind = max(pairs.values()) >= 3
            has_flush_draw = max(suits.values()) >= 3
            has_straight_draw = False
            has_two_pair = len([v for v in pairs.values() if v >= 2]) >= 2
            gaps = []
            for i in range(len(values)-1):
                gaps.append(values[i] - values[i+1] - 1)
            if len(values) >= 3:
                has_straight_draw = any(sum(gaps[i:i+2]) <= 2 for i in range(len(gaps)-1))
                if 14 in values:  # Ace present
                    wheel_values = {2, 3, 4, 5}
                    wheel_potential = len(wheel_values.intersection(set(values)))
                    has_straight_draw = has_straight_draw or wheel_potential >= 2
            if three_of_kind:
                base_samples = 2000  # Set over set scenarios
            elif paired_board and has_flush_draw:
                base_samples = 4500  # Complex draw and pair scenarios
            elif has_two_pair:
                base_samples = 3500  # Boat draws
            elif has_flush_draw and has_straight_draw:
                base_samples = 5000  # Multiple draw scenarios
            elif has_flush_draw or has_straight_draw:
                base_samples = 4000  # Single draw scenarios
            elif paired_board:
                base_samples = 3000  # Pair scenarios
            else:
                base_samples = 2000  # Dry boards
            if len(self.community_cards) == 4:  # Turn
                base_samples = int(base_samples * 0.8)  # Fewer samples needed
            elif len(self.community_cards) == 5:  # River
                base_samples = int(base_samples * 0.6)  # Even fewer samples needed
        else:
            base_samples = 3000
        if hand.rank in {HandRank.FULL_HOUSE, HandRank.FLUSH}:
            base_samples = int(base_samples * 0.8)  # Strong made hands need fewer samples
        elif hand.rank == HandRank.THREE_OF_KIND:
            base_samples = int(base_samples * 0.9)
        final_samples = int(base_samples * player_multiplier * self.sample_size_multiplier)
        return max(1000, min(final_samples, 10000))
    def simulate_hand(self):
        if len(self.hole_cards) < 2:
            return {"win": 0, "tie": 0, "lose": 0}
        if self.num_players < 2:
            return {"win": 100, "tie": 0, "lose": 0}
        num_samples = self.determine_sample_size()
        known_cards = set(self.hole_cards + self.community_cards)
        available_cards = []
        for rank in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']:
            for suit in ['♠', '♣', '♥', '♦']:
                card = Card(rank, suit)
                if card not in known_cards:
                    available_cards.append(card)
        args = ((self.hole_cards, self.community_cards, available_cards,
                self.num_players, self.unknown_cards) for _ in range(num_samples))
        num_processes = cpu_count()
        try:
            with Pool(processes=num_processes) as pool:
                results = pool.map(simulate_single_round, args)
        except Exception as e:
            return {"win": 0, "tie": 0, "lose": 0}
        result_counts = {
            "win": results.count("win"),
            "tie": results.count("tie"),
            "lose": results.count("lose")
        }
        total = sum(result_counts.values())
        if total == 0:
            return {"win": 0, "tie": 0, "lose": 0}
        return {
            "win": round((result_counts["win"] / total) * 100, 2),
            "tie": round((result_counts["tie"] / total) * 100, 2),
            "lose": round((result_counts["lose"] / total) * 100, 2)
        }
    def select_card(self, rank: str, suit: str):
        card = Card(rank, suit)
        suit_colors = {
            '♠': '#000000',
            '♣': '#2ecc71',
            '♥': '#e74c3c',
            '♦': '#3498db'
        }
        all_cards = self.hole_cards + self.community_cards
        if any(str(c) == str(card) for c in all_cards):
            return
        width = self.width()
        base_font_size = max(8, min(16, width // 60))
        base_style = f"""
            color: {suit_colors[suit]};
            font-size: {base_font_size}px;
            padding: {max(2, min(5, width // 200))}px;
            background-color: #2d572c;
            border: 1px solid #4a8348;
            border-radius: 2px;
            min-width: {max(20, min(30, width // 40))}px;
            text-align: center;
        """
        should_update = False
        if len(self.hole_cards) < 2:
            self.hole_cards.append(card)
            label = self.hole_labels[len(self.hole_cards)-1]
            label.setText(str(card))
            label.setStyleSheet(base_style)
            label.setMinimumWidth(max(20, min(30, width // 40)))
            should_update = len(self.hole_cards) == 2
        elif len(self.community_cards) < 5:
            self.community_cards.append(card)
            label = self.community_labels[len(self.community_cards)-1]
            label.setText(str(card))
            label.setStyleSheet(base_style)
            label.setMinimumWidth(max(20, min(30, width // 40)))
            should_update = len(self.community_cards) in [3, 4, 5]
        if should_update:
            self.update_calculations()
class PokerCalculator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MonsterHand")
        self.setWindowIcon(QIcon('C:/Users/35387/OneDrive/Desktop/POKERFINALGOOD/monsterhand.ico'))
        self.setGeometry(100, 100, 800, 600)
        self.child_windows = []
        self.last_simulation_cards = []
        self.last_simulation_results = None
        self.board_state = 'preflop'
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.deck = Deck()
        self.hole_cards = []
        self.community_cards = []
        self.simulation_worker = None
        self.card_buttons = []  # Store all card buttons
        self.players_label = QLabel("Players:")
        self.hole_label = QLabel("Hole:")
        self.community_label = QLabel("Community:")
        self.minimum_window_width = 150
        self.minimum_window_height = 150
        self.knockout_button = None
        self.clear_button = None
        self.resizeEvent = self.handle_resize
        self.hole_label.setText("H:")
        self.community_label.setText("C:")
        self.setup_gui()
        self.default_player_count = 9
    def open_new_calculator(self):
        new_calc = PokerCalculator()
        new_calc.setGeometry(self.geometry())
        new_calc.show()
        self.child_windows.append(new_calc)
    def setup_gui(self):
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(360, 300)
        self.setStyleSheet("background-color: black;")
        self.main_layout.setSpacing(1)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #333333;
                border-radius: 5px;
                padding: 2px;
                margin: 1px;
            }
        """)
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setSpacing(2)
        controls_layout.setContentsMargins(2, 2, 2, 2)
        players_layout = QHBoxLayout()
        players_layout.setSpacing(5)
        self.players_label.setStyleSheet("color: white; font-size: 12px;")
        players_layout.addWidget(self.players_label)
        self.player_buttons = []
        for i in range(2, 10):
            button = QPushButton(str(i))
            button.setFixedSize(35, 35)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #404040;
                    border-radius: 3px;
                    padding: 2px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:checked {
                    background-color: #ff8db4;
                    border: 1px solid #ff69b4;
                }
                QPushButton:hover {
                    background-color: #FF5050;
                    border: 1px solid #505050;
                }
            """)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, num=i: self.set_player_count(num))
            self.player_buttons.append(button)
            players_layout.addWidget(button)

        self.current_player_count = 9
        self.player_buttons[-1].setChecked(True)
        players_layout.addSpacing(10)

        self.knockout_button = QPushButton("Knockout Player")
        self.knockout_button.clicked.connect(self.knockout_player)
        self.knockout_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #353535;
                border: 1px solid #505050;
            }
        """)

        self.clear_button = QPushButton("Clear Cards")
        self.clear_button.clicked.connect(self.clear_cards)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #353535;
                border: 1px solid #505050;
            }
        """)

        self.new_table_button = QPushButton("New Table")
        self.new_table_button.clicked.connect(self.open_new_calculator)
        self.new_table_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #353535;
                border: 1px solid #505050;
            }
        """)

        players_layout.addWidget(self.knockout_button)
        players_layout.addSpacing(10)
        players_layout.addWidget(self.clear_button)
        players_layout.addWidget(self.new_table_button)
        players_layout.addStretch()

        controls_layout.addLayout(players_layout)
        self.main_layout.addWidget(controls_frame)

        cards_frame = QFrame()
        cards_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        cards_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #333333;
                border-radius: 5px;
                padding: 1px;
                margin: 1px;
            }
        """)
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setSpacing(10)
        cards_layout.setContentsMargins(5, 5, 5, 5)

        hole_layout = QHBoxLayout()
        hole_layout.setSpacing(5)
        self.hole_label.setStyleSheet("color: white; font-size: 12px;")
        hole_layout.addWidget(self.hole_label)

        self.hole_labels = []
        for _ in range(2):
            label = QLabel("  ")
            label.setStyleSheet("""
                color: white;
                font-size: 11px;
                padding: 1px;
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 2px;
                min-width: 20px;
                text-align: center;
            """)
            self.hole_labels.append(label)
            hole_layout.addWidget(label)

        cards_layout.addLayout(hole_layout)

        community_layout = QHBoxLayout()
        community_layout.setSpacing(5)
        self.community_label.setStyleSheet("color: white; font-size: 12px;")
        community_layout.addWidget(self.community_label)

        self.community_labels = []
        for _ in range(5):
            label = QLabel("  ")
            label.setStyleSheet("""
                color: white;
                font-size: 11px;
                padding: 1px;
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 2px;
                min-width: 20px;
                text-align: center;
            """)
            self.community_labels.append(label)
            community_layout.addWidget(label)

        cards_layout.addLayout(community_layout)
        self.main_layout.addWidget(cards_frame)

        selection_frame = QFrame()
        selection_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        selection_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 2px;
                padding: 0px;
                margin: 0px;
            }
        """)
        selection_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        selection_frame.setMaximumHeight(200)

        grid_layout = QGridLayout(selection_frame)
        grid_layout.setSpacing(0)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        ranks = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['♠', '♣', '♥', '♦']
        suit_colors = {'♠': 'black', '♣': 'black', '♥': 'red', '♦': 'red'}

        self.grid_layout = grid_layout
        self.card_buttons = []

        for i, suit in enumerate(suits):
            for j, rank in enumerate(ranks):
                button = QPushButton(f"{rank}{suit}")
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: white;
                        color: {suit_colors[suit]};
                        border: 1px solid #404040;
                        border-radius: 3px;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 5px;
                    }}
                    QPushButton:hover {{
                        background-color: #f0f0f0;
                        border: 1px solid #606060;
                    }}
                    QPushButton:pressed {{
                        background-color: #e0e0e0;
                    }}
                """)
    
    
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.clicked.connect(lambda checked, r=rank, s=suit: self.select_card(r, s))
                self.card_buttons.append(button)
                grid_layout.addWidget(button, i, j)

        self.main_layout.addWidget(selection_frame)

        results_container = QFrame()
        results_container.setStyleSheet("""
            QFrame {
                background-color: black;
                border: 2px solid #333333;
                border-radius: 5px;
            }
        """)
        results_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        results_layout = QHBoxLayout(results_container)
        results_layout.setSpacing(0)
        results_layout.setContentsMargins(0, 0, 0, 0)

        self.left_text = QTextEdit()
        self.left_text.setReadOnly(True)
        self.left_text.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: none;
                font-family: 'Courier New';
                selection-background-color: #404040;
                selection-color: white;
            }
        """)
        self.left_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.right_text = QTextEdit()
        self.right_text.setReadOnly(True)
        self.right_text.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: none;
                font-family: 'Courier New';
                selection-background-color: #404040;
                selection-color: white;
            }
        """)
        self.right_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        results_layout.addWidget(self.left_text)
        results_layout.addWidget(self.right_text)

        self.main_layout.addWidget(results_container)
        
        self.info_button = QPushButton("ℹ️")  # Info emoji as button text
        self.info_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
                min-width: 30px;
            }
            QPushButton:hover {
                background-color: #353535;
                border: 1px solid #505050;
            }
        """)
        self.info_button.clicked.connect(self.show_info_menu)

        # Add it to your players_layout next to your other buttons
        players_layout.addWidget(self.info_button)
        
        
    def show_info_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
            }
            QMenu::item {
                padding: 5px 30px 5px 20px;
            }
            QMenu::item:selected {
                background: #3d3d3d;
            }
        """)
        
        # Add menu items
        help_action = menu.addAction("Help")
        help_action.triggered.connect(self.show_help_window)
        
        # Add hand history analyzer option
        history_action = menu.addAction("Hand History Analyzer")
        history_action.triggered.connect(self.open_history_analyzer)
        
        # Add player count submenu
        player_menu = QMenu("Set Default Players", menu)
        player_menu.setStyleSheet(menu.styleSheet())
        
        # Add options for 2-9 players
        for i in range(2, 10):
            action = player_menu.addAction(f"{i} Players")
            action.triggered.connect(lambda checked, x=i: self.set_default_player_count(x))
        
        menu.addMenu(player_menu)
        
        # Show menu below the button
        menu.exec(self.info_button.mapToGlobal(self.info_button.rect().bottomLeft()))

    def open_history_analyzer(self):
        self.history_analyzer = LiveHandHistoryAnalyzer()
        self.history_analyzer.show()

    def show_help_window(self):
        help_window = QWidget()
        help_window.setWindowTitle("MonsterHand Info")
        help_window.setStyleSheet("background-color: #1a1a1a; color: white;")
        help_window.setGeometry(200, 200, 400, 300)  # Set size and position
        
        layout = QVBoxLayout()
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #404040;
                padding: 10px;
            }
        """)
        
        # Add your info text here
        text.setText("""Understanding the Poker Calculator
Hand Analysis


The calculator shows your current hand strength and potential winning odds based on your hole cards and the community cards on the board. These calculations adjust dynamically based on the number of players in the hand.


Win/Tie/Lose Percentages
These numbers show your probability of winning, tying, or losing the hand against the current number of players. As the number of players increases, winning probabilities typically decrease since you're competing against more hands.


Best Possible Hand


This shows the strongest hand that could currently be made using any combination of the community cards and hole cards. This applies to both you and your opponents, helping you understand what you're potentially up against.
Potential Hands
This section displays the probability of you making specific hands (like flushes, straights, etc.) by the river. Only possibilities with 0.1% or greater chance are shown.


Opponent Hand Possibilities


This section specifically shows hands that can beat your current hand, broken down by:
The type of hand (pair, two pair, etc.)
The percentage chance of opponents having these hands
The number of possible card combinations (combos) that make each hand
Only possibilities with 0.1% or greater chance are shown.

        

        """)
        
        layout.addWidget(text)
        help_window.setLayout(layout)
        help_window.show()
        
        # Keep a reference to prevent garbage collection
        self.help_window = help_window

    
                
                
    def setup_card_grid(self):
        width = self.width()
        scale = width / 800.0

        min_size = max(25, int(30 * scale))

        for i in range(self.grid_layout.rowCount()):
            self.grid_layout.setRowMinimumHeight(i, min_size)

        for j in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnMinimumWidth(j, min_size)

        # Adjust font size based on width
        if width < 500:
            font_size = max(6, int(8 * scale))  # Smaller font for narrow windows
        else:
            font_size = max(8, int(11 * scale))  # Original font scaling

        for button in self.card_buttons:
            button.setMinimumSize(min_size, min_size)
            button.setFont(QFont('Arial', font_size))
        
        
    def handle_resize(self, event):
        width = self.width()

        # Ultra small window
        if width < 370:
            button_size = 20
            spacing = 1
            control_button_width = 40
            font_size = 7
            player_button_size = 15
            self.knockout_button.setText("K")
            self.clear_button.setText("C")
            self.new_table_button.setText("N")
            self.players_label.setText("P:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Very small window
        elif width < 385:
            button_size = 18
            spacing = 1
            control_button_width = 30
            font_size = 8
            player_button_size = 17
            self.knockout_button.setText("KO")
            self.clear_button.setText("CC")
            self.new_table_button.setText("NT")
            self.players_label.setText("Pl:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Small window
        elif width < 400:
            button_size = 20
            spacing = 2
            control_button_width = 40
            font_size = 9
            player_button_size = 20
            self.knockout_button.setText("KO")
            self.clear_button.setText("CC")
            self.new_table_button.setText("NT")
            self.players_label.setText("Pl:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Small-medium window
        elif width < 450:
            button_size = 22
            spacing = 2
            control_button_width = 40
            font_size = 9
            player_button_size = 22
            self.knockout_button.setText("KO")
            self.clear_button.setText("CC")
            self.new_table_button.setText("NT")
            self.players_label.setText("Pl:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Medium window
        elif width < 500:
            button_size = 25
            spacing = 3
            control_button_width = 45
            font_size = 9
            player_button_size = 25
            self.knockout_button.setText("KO")
            self.clear_button.setText("CC")
            self.new_table_button.setText("NT")
            self.players_label.setText("Pl:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Medium-large window
        elif width < 550:
            button_size = 28
            spacing = 3
            control_button_width = 50
            font_size = 10
            player_button_size = 28
            self.knockout_button.setText("KO")
            self.clear_button.setText("CC")
            self.new_table_button.setText("NT")
            self.players_label.setText("Pl:")
            self.hole_label.setText("H:")
            self.community_label.setText("C:")

        # Large window
        elif width < 600:
            button_size = 30
            spacing = 4
            control_button_width = 60
            font_size = 10
            player_button_size = 30
            self.knockout_button.setText("Knock")
            self.clear_button.setText("Clear")
            self.new_table_button.setText("New")
            self.players_label.setText("Play:")
            self.hole_label.setText("Hole:")
            self.community_label.setText("Com:")

        # Very large window
        elif width < 700:
            button_size = 32
            spacing = 5
            control_button_width = 70
            font_size = 11
            player_button_size = 35
            self.knockout_button.setText("Knockout")
            self.clear_button.setText("Clear")
            self.new_table_button.setText("New")
            self.players_label.setText("Players:")
            self.hole_label.setText("Hole:")
            self.community_label.setText("Community:")
            
        elif width < 800:
            button_size = 35
            spacing = 4
            control_button_width = 90
            font_size = 11
            player_button_size = 35
            self.knockout_button.setText("Knockout")
            self.clear_button.setText("Clear")
            self.new_table_button.setText("New")
            self.players_label.setText("Players:")
            self.hole_label.setText("Hole:")
            self.community_label.setText("Community:")

        # Maximum window
        else:
            button_size = 40
            spacing = 5
            control_button_width = 120
            font_size = 12
            player_button_size = 40
            self.knockout_button.setText("Knockout Player")
            self.clear_button.setText("Clear Cards")
            self.new_table_button.setText("New Table")
            self.players_label.setText("Players:")
            self.hole_label.setText("Hole:")
            self.community_label.setText("Community:")

        # Update player number buttons
        for button in self.player_buttons:
            button.setFixedSize(player_button_size, player_button_size)
            button.setFont(QFont('Arial', font_size))
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #404040;
                    border-radius: {max(1, int(player_button_size * 0.1))}px;
                    padding: 2px;
                    font-size: {font_size}px;
                    font-weight: bold;
                    margin: {spacing}px;
                }}
                QPushButton:checked {{
                    background-color: #dc143c;
                    border: 1px solid #dc143c;
                }}
                QPushButton:hover {{
                    background-color: #353535;
                    border: 1px solid #505050;
                }}
            """)

        # Update control buttons
        for button in [self.knockout_button, self.clear_button, self.new_table_button]:
            button.setFixedWidth(control_button_width)
            button.setFont(QFont('Arial', font_size))
            button.setContentsMargins(spacing, spacing, spacing, spacing)
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #404040;
                    border-radius: {max(1, int(button_size * 0.1))}px;
                    padding: {spacing}px;
                    font-size: {font_size}px;
                    margin: {spacing}px;
                }}
                QPushButton:hover {{
                    background-color: #353535;
                    border: 1px solid #505050;
                }}
            """)

        # Update info button
        if hasattr(self, 'info_button'):
            self.info_button.setFixedSize(player_button_size, player_button_size)
            self.info_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #404040;
                    border-radius: {max(1, int(player_button_size * 0.1))}px;
                    padding: 2px;
                    font-size: {font_size}px;
                    margin: {spacing}px;
                }}
                QPushButton:hover {{
                    background-color: #353535;
                    border: 1px solid #505050;
                }}
            """)

        # Update labels
        for label in [self.players_label, self.hole_label, self.community_label]:
            label.setFont(QFont('Arial', font_size))
            label.setStyleSheet(f"color: white; font-size: {font_size}px;")

        super().resizeEvent(event)

    

    def set_player_count(self, count):
        self.current_player_count = count

        for button in self.player_buttons:
            button.setChecked(int(button.text()) == count)

        if not any(button.isChecked() for button in self.player_buttons):
            self.player_buttons[count-1].setChecked(True)

        if count == 1:
            for button in self.player_buttons:
                if int(button.text()) < count:
                    button.setEnabled(False)
        else:
            for button in self.player_buttons:
                button.setEnabled(True)

        self.update_calculations()

    @staticmethod
    def compare_hands(hand1: 'HandEvaluator.HandEvaluation', hand2: 'HandEvaluator.HandEvaluation') -> int:
        """
        Compares two hands and returns:
        1 if hand1 wins
        -1 if hand2 wins
        0 if tie

        Implements enhanced hand comparison with improved:
        - Wheel straight detection
        - Kicker handling
        - Tie breaking
        - Comparison optimization
        """
        if hand1.rank.value != hand2.rank.value:
            return 1 if hand1.rank.value > hand2.rank.value else -1

        if hand1.rank in {HandRank.STRAIGHT, HandRank.STRAIGHT_FLUSH}:
            def get_straight_value(values):
                if 14 in values and {2, 3, 4, 5}.issubset(set(values)):
                    return 5  # Wheel straight is ranked as 5-high
                straight_values = sorted(values, reverse=True)
                return straight_values[0]  # Highest card in non-wheel straight

            hand1_value = get_straight_value(hand1.values)
            hand2_value = get_straight_value(hand2.values)

            if hand1_value != hand2_value:
                return 1 if hand1_value > hand2_value else -1
            return 0  # Identical straights always tie

        if hand1.rank in {HandRank.PAIR, HandRank.TWO_PAIR, HandRank.THREE_OF_KIND, HandRank.FULL_HOUSE, HandRank.FOUR_OF_KIND}:
            pairs1 = [v for v in hand1.values if hand1.values.count(v) > 1]
            pairs2 = [v for v in hand2.values if hand2.values.count(v) > 1]

            pairs1.sort(key=lambda x: (-hand1.values.count(x), -x))
            pairs2.sort(key=lambda x: (-hand2.values.count(x), -x))

            for v1, v2 in zip(pairs1, pairs2):
                if v1 != v2:
                    return 1 if v1 > v2 else -1

            kickers1 = sorted([v for v in hand1.values if v not in pairs1], reverse=True)
            kickers2 = sorted([v for v in hand2.values if v not in pairs2], reverse=True)

            for k1, k2 in zip_longest(kickers1, kickers2, fillvalue=0):
                if k1 != k2:
                    return 1 if k1 > k2 else -1

        elif hand1.rank in {HandRank.FLUSH, HandRank.HIGH_CARD}:
            values1 = sorted(hand1.values, reverse=True)
            values2 = sorted(hand2.values, reverse=True)

            for v1, v2 in zip_longest(values1, values2, fillvalue=0):
                if v1 != v2:
                    return 1 if v1 > v2 else -1

        return 0

    def select_card(self, rank: str, suit: str):
        card = Card(rank, suit)
        suit_colors = {
            '♠': 'black',
            '♣': 'black',
            '♥': 'red',
            '♦': 'red'
        }
        all_cards = self.hole_cards + self.community_cards
        if any(str(c) == str(card) for c in all_cards):
            return
        width = self.width()
        base_font_size = max(10, min(16, width // 60))
        base_style = f"""
            color: {suit_colors[suit]};
            font-size: {base_font_size}px;
            padding: {max(2, min(5, width // 200))}px;
            background-color: white;
            border: 1px solid black;
            border-radius: 2px;
            min-width: {max(20, min(30, width // 40))}px;
            text-align: center;
        """
        if len(self.hole_cards) < 2:
            self.hole_cards.append(card)
            label = self.hole_labels[len(self.hole_cards)-1]
            label.setText(str(card))
            label.setStyleSheet(base_style)
            label.setMinimumWidth(max(20, min(30, width // 40)))
            if len(self.hole_cards) == 2:
                self.update_calculations()
        elif len(self.community_cards) < 5:
            prev_len = len(self.community_cards)
            self.community_cards.append(card)
            label = self.community_labels[len(self.community_cards)-1]
            label.setText(str(card))
            label.setStyleSheet(base_style)
            label.setMinimumWidth(max(20, min(30, width // 40)))
            if len(self.community_cards) in [3, 4, 5] and len(self.community_cards) > prev_len:
                self.update_calculations()

    def calculate_hand_dominance(self):
        from collections import defaultdict
        from itertools import combinations

        if not self.hole_cards or len(self.hole_cards) < 2:
            return ""

        current_hand = HandEvaluator.evaluate_hand(self.hole_cards + self.community_cards)
        visible_cards = set(self.hole_cards + self.community_cards)

        available_cards = [
            Card(rank, suit)
            for rank in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            for suit in ['♠', '♣', '♥', '♦']
            if Card(rank, suit) not in visible_cards
        ]

        total_combos = math.comb(len(available_cards), 2)
        if total_combos == 0:
            return ""

        result = []
        # Only show the header if there are community cards
        if self.community_cards:
            result.append("🎯 Opponent Hand Possibilities")

        if not self.community_cards:
            hand_strength = self._analyze_preflop_strength()
            result.append(f"💫 Preflop Hand Strength: {hand_strength}")

            better_hands = 0
            equal_hands = 0
            worse_hands = 0

            hero_hand = HandEvaluator.evaluate_hand(self.hole_cards)

            for opp_cards in combinations(available_cards, 2):
                opp_hand = HandEvaluator.evaluate_hand(list(opp_cards))
                comparison = self.compare_hands(hero_hand, opp_hand)

                if comparison > 0:
                    worse_hands += 1
                elif comparison < 0:
                    better_hands += 1
                else:
                    equal_hands += 1

            absolute_dominated = (worse_hands / total_combos) * 100
            absolute_equal = (equal_hands / total_combos) * 100
            absolute_weaker = (better_hands / total_combos) * 100

            result.append(f"\n💪 Absolute: {absolute_dominated:.1f}% dominate, {absolute_equal:.1f}% equal, {absolute_weaker:.1f}% weaker")
            result.append("Shows what percentage of all possible hands yours is better than. A pure ranking of your hand's strength compared to all other hands.")
            return "\n".join(result)

        # Post-flop analysis
        better_hands = Counter()
        equal_hands = Counter()
        dominated_hands = Counter()

        current_rank_value = current_hand.rank.value
        current_values = current_hand.values

        value_freqs = defaultdict(int)
        for card in self.community_cards:
            value_freqs[card.get_value()] += 1

        for opponent_cards in combinations(available_cards, 2):
            opponent_hand = HandEvaluator.evaluate_hand(list(opponent_cards) + self.community_cards)

            if opponent_hand.rank.value > current_rank_value:
                better_hands[opponent_hand.rank] += 1
            elif opponent_hand.rank.value < current_rank_value:
                dominated_hands[opponent_hand.rank] += 1
            else:
                comparison = self._compare_equal_rank_hands(
                    current_hand, opponent_hand, value_freqs
                )
                if comparison > 0:
                    dominated_hands[opponent_hand.rank] += 1
                elif comparison < 0:
                    better_hands[opponent_hand.rank] += 1
                else:
                    equal_hands[opponent_hand.rank] += 1

        num_players = self.current_player_count - 1  # Exclude hero
        if num_players > 1:
            result.append("\n🎲 Multi-way Pot Analysis:")

        for rank in sorted(better_hands.keys(), key=lambda x: better_hands[x], reverse=True):
            better_count = better_hands[rank]
            equal_count = equal_hands[rank]

            prob_better = 1 - (1 - better_count / total_combos) ** num_players
            prob_equal = 1 - (1 - equal_count / total_combos) ** num_players

            total_prob = prob_better + prob_equal
            if total_prob >= 0.001:  # 0.1% threshold
                result.append(f"\n⚠️ {rank.name}:")
                if better_count > 0:
                    result.append(f"   Better: {prob_better*100:.1f}% ({better_count} combos)")
                if equal_count > 0:
                    result.append(f"   Equal: {prob_equal*100:.1f}% ({equal_count} combos)")

        return "\n".join(result)
    def _compare_equal_rank_hands(self, hand1, hand2, value_freqs):
        """Helper method for detailed hand comparison."""
        if hand1.rank in {HandRank.STRAIGHT, HandRank.STRAIGHT_FLUSH}:

            h1_high = 5 if hand1.values[0] == 14 and max(hand1.values[1:]) <= 5 else hand1.values[0]
            h2_high = 5 if hand2.values[0] == 14 and max(hand2.values[1:]) <= 5 else hand2.values[0]
            return h1_high - h2_high

        for v1, v2 in zip(hand1.values, hand2.values):
            if v1 != v2:

                if value_freqs[v1] >= 2 or value_freqs[v2] >= 2:
                    continue
                return v1 - v2
        return 0

    def _analyze_preflop_strength(self) -> str:
        """Analyze preflop hand strength."""
        card1, card2 = sorted(self.hole_cards, key=lambda x: x.get_value(), reverse=True)
        suited = card1.suit == card2.suit
        paired = card1.rank == card2.rank

        if paired:
            if card1.get_value() >= 10:
                return "Premium Pair"
            elif card1.get_value() >= 7:
                return "Medium Pair"
            return "Small Pair"

        gap = card1.get_value() - card2.get_value()
        if card1.get_value() >= 12 and card2.get_value() >= 11:
            return "Premium Unpaired" + (" Suited" if suited else "")
        elif gap <= 2 and suited and card1.get_value() >= 10:
            return "Strong Suited Connector"
        elif gap <= 2 and card1.get_value() >= 10:
            return "Connector"
        elif suited and card1.get_value() >= 10:
            return "Suited High Card"
        elif gap <= 2:
            return "Small Connector" + (" Suited" if suited else "")
        return "Unconnected" + (" Suited" if suited else "")

    def get_key_cards_needed(self, target_hand: HandRank) -> str:
        visible_cards = set(self.hole_cards + self.community_cards)
        suits_count = {suit: sum(1 for c in self.community_cards if c.suit == suit)
                    for suit in ['♠', '♣', '♥', '♦']}

        if target_hand == HandRank.FLUSH:
            max_suit = max(suits_count.items(), key=lambda x: x[1])
            if max_suit[1] >= 3:
                remaining_flush_cards = [card for card in self.deck.cards
                                        if card.suit == max_suit[0] and card not in visible_cards]
                return f"{len(remaining_flush_cards)} more {max_suit[0]} cards needed for a flush"

        elif target_hand == HandRank.STRAIGHT:
            values = sorted(c.get_value() for c in self.community_cards)

            for i in range(len(values) - 4):
                if values[i+4] - values[i] == 4:
                    lower_card = Card.value_to_rank(values[i] - 1)
                    higher_card = Card.value_to_rank(values[i+4] + 1)
                    return f"{lower_card} or {higher_card} to complete the open-ended straight draw"

            for i in range(len(values) - 3):
                if values[i+3] - values[i] == 4:
                    missing_card = Card.value_to_rank(values[i+1] + 1)
                    return f"{missing_card} to complete the gutshot straight draw"

            for i in range(len(values) - 2):
                if values[i+2] - values[i] == 4:
                    lower_card = Card.value_to_rank(values[i] + 1)
                    higher_card = Card.value_to_rank(values[i+2] - 1)
                    return f"{lower_card} and {higher_card} for a double gutshot straight draw"

        elif target_hand == HandRank.STRAIGHT_FLUSH:
            for suit in suits_count:
                suited_values = sorted(c.get_value() for c in self.community_cards if c.suit == suit)

                if len(suited_values) >= 3:
                    for i in range(len(suited_values) - 2):
                        if suited_values[i+2] - suited_values[i] <= 4:
                            lower_card = Card.value_to_rank(suited_values[i] - 1)
                            higher_card = Card.value_to_rank(suited_values[i+2] + 1)
                            return f"{lower_card} and {higher_card} of {suit} for a straight flush draw"

        return "Multiple cards needed"

    def update_results(self, results):
        if not self.hole_cards:
            self.left_text.clear()
            self.right_text.clear()
            return

        current_hand = HandEvaluator.evaluate_hand(self.hole_cards + self.community_cards)

        possible_hands = HandEvaluator.get_possible_hands(
            self.hole_cards,
            self.community_cards,
            set(self.hole_cards + self.community_cards)
        )

        best_rank = current_hand.rank
        for rank in reversed(HandRank):
            if rank.value > best_rank.value and (
                possible_hands['hands'][rank]['suited'] or
                possible_hands['hands'][rank]['offsuit'] or
                possible_hands['hands'][rank]['pairs']
            ):
                best_rank = rank
                break

        stats = {
            'current_hand': current_hand.rank.name,
            'players': self.current_player_count,
            'win_pct': results['win'],
            'tie_pct': results['tie'],
            'lose_pct': results['lose'],
            'best_possible': best_rank.name,
            'dominance_info': self.calculate_hand_dominance()
        }

        width = self.width()
        base_font_size = max(8, min(14, width // 60))

        font = self.left_text.font()
        font.setPointSize(base_font_size)
        self.left_text.setFont(font)
        self.right_text.setFont(font)

        self.left_text.clear()
        self.right_text.clear()

        hole_cards = ' '.join(str(card) for card in self.hole_cards) if self.hole_cards else "None"
        community = ' '.join(str(card) for card in self.community_cards) if self.community_cards else "None"

        is_nuts = (results['win'] == 100 and results['tie'] == 0)

        potential_hands_text = "\nPotential Hands:"
        num_players = self.current_player_count - 1  # Exclude hero
        
        if not self.community_cards:  # Preflop
            # Preflop potential hand probabilities 
            potential_probs = {
                HandRank.ROYAL_FLUSH: 0.00002,
                HandRank.STRAIGHT_FLUSH: 0.0001,
                HandRank.FOUR_OF_KIND: 0.0003,
                HandRank.FULL_HOUSE: 0.004,
                HandRank.FLUSH: 0.005,
                HandRank.STRAIGHT: 0.008,
                HandRank.THREE_OF_KIND: 0.004,
                HandRank.TWO_PAIR: 0.05,
                HandRank.PAIR: 0.26
            }
            
            # Adjust probabilities based on hole cards
            if self.hole_cards[0].rank == self.hole_cards[1].rank:  # Pocket pair
                potential_probs.pop(HandRank.PAIR)  # Remove pair since we already have it
                potential_probs[HandRank.FOUR_OF_KIND] = 0.001
                potential_probs[HandRank.FULL_HOUSE] = 0.012
                potential_probs[HandRank.THREE_OF_KIND] = 0.018
                potential_probs[HandRank.TWO_PAIR] = 0.08
            
            if self.hole_cards[0].suit == self.hole_cards[1].suit:  # Suited
                potential_probs[HandRank.ROYAL_FLUSH] *= 1.2 if all(c.get_value() >= 10 for c in self.hole_cards) else 1
                potential_probs[HandRank.STRAIGHT_FLUSH] *= 1.1
                potential_probs[HandRank.FLUSH] = 0.011
            
            # Straight potential for connected cards
            card_gap = abs(self.hole_cards[0].get_value() - self.hole_cards[1].get_value())
            if card_gap <= 4:
                straight_multiplier = {0: 1, 1: 1.2, 2: 1.1, 3: 1.05, 4: 1.02}[card_gap]
                potential_probs[HandRank.STRAIGHT] *= straight_multiplier
                if self.hole_cards[0].suit == self.hole_cards[1].suit:
                    potential_probs[HandRank.STRAIGHT_FLUSH] *= straight_multiplier

            for rank, prob in potential_probs.items():
                if rank.value > current_hand.rank.value:  # Only show better hands
                    # Adjusted logarithmic scaling
                    adjusted_prob = (prob * (math.log(num_players + 1) * 0.8)) * 100
                    if adjusted_prob >= 0.1:  # Only show if probability is at least 0.1%
                        potential_hands_text += f"\n{rank.name}: {min(adjusted_prob, 70.0):.1f}%"
                        
        elif len(self.community_cards) < 5:  # Post-flop but not river
            all_cards = self.hole_cards + self.community_cards
            suits_count = Counter(card.suit for card in all_cards)
            values = sorted([card.get_value() for card in all_cards])
            
            remaining_cards = 52 - len(all_cards)
            
            # Flush draws
            flush_suit = max(suits_count.items(), key=lambda x: x[1])[0]
            flush_count = suits_count[flush_suit]
            if flush_count >= 4:
                remaining_suited = 13 - sum(1 for card in all_cards if card.suit == flush_suit)
                if remaining_suited > 0:
                    royal_potential = sum(1 for card in all_cards if card.suit == flush_suit and card.get_value() >= 10)
                    if royal_potential >= 3:
                        possible_hands['hands'][HandRank.ROYAL_FLUSH]['probability'] = (remaining_suited / remaining_cards) * 0.15
                    possible_hands['hands'][HandRank.STRAIGHT_FLUSH]['probability'] = (remaining_suited / remaining_cards) * 0.15
            elif flush_count == 3:
                remaining_suited = 13 - sum(1 for card in all_cards if card.suit == flush_suit)
                if remaining_suited >= 2:
                    flush_prob = ((remaining_suited/remaining_cards) * ((remaining_suited-1)/(remaining_cards-1))) * 0.15
                    possible_hands['hands'][HandRank.FLUSH]['probability'] = flush_prob
            
            # Straight draws
            straight_draws = set()
            for i in range(len(values) - 2):
                window = values[i:i+3]
                if max(window) - min(window) <= 4:
                    for v in range(min(window)-1, max(window)+2):
                        if v not in window and 1 <= v <= 14:
                            straight_draws.add(v)
            
            if straight_draws:
                available_outs = len(straight_draws)
                straight_prob = min(0.4, (available_outs/remaining_cards) * ((available_outs-1)/(remaining_cards-1)) * 0.15)
                possible_hands['hands'][HandRank.STRAIGHT]['probability'] = straight_prob
            
            # Add all potentially better hands to display
            for rank in reversed(HandRank):
                if rank.value > current_hand.rank.value:  # Only show better hands
                    prob = possible_hands['hands'][rank]['probability']
                    if prob > 0:
                        # Adjusted logarithmic scaling with dampening
                        adjusted_prob = (prob * (math.log(num_players + 1) * 0.8)) * 100
                        if adjusted_prob >= 0.1:  # Only show if probability is at least 0.1%
                            potential_hands_text += f"\n{rank.name}: {min(adjusted_prob, 70.0):.1f}%"

        if width < 600:
            left_text = f"""{'🔥 YOU HAVE THE NUTS!\n\n' if is_nuts else ''}Hand: {current_hand.description}
            Players: {stats['players']}
            Win: {stats['win_pct']:>5.1f}%
            Tie: {stats['tie_pct']:>5.1f}%
            Loss: {stats['lose_pct']:>5.1f}%
            Hand: {hole_cards}
            Community: {community}"""
        else:
            left_text = f"""{'🔥 YOU HAVE THE NUTS!\n\n' if is_nuts else ''}Current Hand: {current_hand.description}
            Players: {stats['players']}

            Win:  {stats['win_pct']:>5.1f}%
            Tie:  {stats['tie_pct']:>5.1f}%
            Lose: {stats['lose_pct']:>5.1f}%

            Hole Cards:    {hole_cards}
            Community:     {community}"""

        if best_rank != current_hand.rank or not self.community_cards:  # Show on preflop too
            left_text += f"\nBest Possible: {best_rank.name}"
            if len(self.community_cards) < 5:  # Only show potential hands if not on river
                left_text += potential_hands_text

        # Add the warning message in a custom color
        left_text += "\n\nREMEMBER TO SET NUMBER OF PLAYERS!\nIT CAN DRASTICALLY EFFECT CALCULATIONS!"

        right_text = stats['dominance_info']

        self.left_text.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: none;
                font-family: 'IBM Plex Mono';
                font-weight: bold;
                selection-background-color: #2d572c;
                selection-color: white;
                padding: 2px;
            }
        """)

        self.right_text.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: none;
                font-family: 'IBM Plex Mono';
                font-weight: bold;
                selection-background-color: #2d572c;
                selection-color: white;
                padding: 2px;
            }
        """)

        self.left_text.setText(left_text)
        self.right_text.setText(right_text)
     
     
    def format_analysis(self, stats: dict) -> str:
        try:
            win_pct = round(float(stats['win_pct']), 1)
            tie_pct = round(float(stats['tie_pct']), 1)
            lose_pct = round(float(stats['lose_pct']), 1)

            if win_pct >= 80:
                strength = '💪'
            elif win_pct >= 60:
                strength = '🔥'
            elif win_pct >= 40:
                strength = '📊'
            else:
                strength = '⚠️'

            hole_cards = ' '.join(str(card) for card in self.hole_cards) if self.hole_cards else "None"
            community = ' '.join(str(card) for card in self.community_cards) if self.community_cards else "None"

            hand = HandEvaluator.evaluate_hand(self.hole_cards + self.community_cards)
            known_cards = set(self.hole_cards + self.community_cards)
            possible = HandEvaluator.get_possible_hands(self.community_cards, known_cards)
            best_possible = possible['statistics']['best_possible'].name if possible else hand.rank.name

            left_side = f"""{strength} Current Hand: {hand.description}
    👥 Players: {stats['players']}

    Win:  {win_pct:>5.1f}%
    Tie:  {tie_pct:>5.1f}%
    Lose: {lose_pct:>5.1f}%

    🎴 Your Cards:    {hole_cards}
    🃏 Community:     {community}"""

            if best_possible != hand.rank.name:
                left_side += f"\n✨ Best Possible: {best_possible}"

            if len(self.community_cards) < 5 and hand.draws:
                left_side += "\n\n🎲 Draw Potential:"
                for draw_type, equity in hand.draws.items():
                    left_side += f"\n   {draw_type}: {equity:.1f}% equity"

            right_side = stats.get('dominance_info', '').strip()

            left_lines = left_side.split('\n')
            right_lines = right_side.split('\n')

            max_lines = max(len(left_lines), len(right_lines))
            left_lines += [''] * (max_lines - len(left_lines))
            right_lines += [''] * (max_lines - len(right_lines))

            result = []
            for left, right in zip(left_lines, right_lines):
                result.append(f"{left:<50}{right}")

            return '\n'.join(result)

        except Exception as e:
            return f"Error in analysis formatting: {str(e)}"

    def knockout_player(self):
        if self.current_player_count > 1:
            self.set_player_count(self.current_player_count - 1)

    def clear_cards(self):
        self.hole_cards = []
        self.community_cards = []

        for label in self.hole_labels + self.community_labels:
            label.setText(" ")
            label.setStyleSheet("color: white; font-size: 16px; padding: 5px;")
        self.left_text.clear()
        self.right_text.clear()
        
        # Reset to default player count
        self.set_player_count(self.default_player_count)
        
    def set_default_player_count(self, count):
        self.default_player_count = count
        # Also update current count if no cards are present
        if not self.hole_cards and not self.community_cards:
            self.set_player_count(count)

    def update_calculations(self):
        # Check if there are enough hole cards
        if len(self.hole_cards) < 2:
            self.left_text.clear()
            self.right_text.clear()
            return

        # Validate community cards count
        if len(self.community_cards) not in [0, 3, 4, 5]:
            return

        # Safely check if the simulation worker is running
        if hasattr(self, 'simulation_worker') and self.simulation_worker:
            if self.simulation_worker.isRunning():
                return

        # Determine known and available cards
        known_cards = set(self.hole_cards + self.community_cards)
        available_cards = [card for card in self.deck.cards if card not in known_cards]

        # Ensure there are enough available cards to proceed
        if len(available_cards) < (5 - len(self.community_cards)):
            return

        # Create a new simulation worker
        self.simulation_worker = SimulationWorker(
            self.hole_cards,
            self.community_cards,
            available_cards,
            self.current_player_count,
            5 - len(self.community_cards)
        )

        # Disconnect any existing signal connections (if applicable)
        if hasattr(self, 'simulation_worker') and self.simulation_worker:
            try:
                self.simulation_worker.simulation_finished.disconnect()
            except (TypeError, RuntimeError):
                pass  # Ignore disconnection errors

        # Connect the new worker's signal and start it
        self.simulation_worker.simulation_finished.connect(self.update_results)
        self.simulation_worker.start()


    

if __name__ == "__main__":
    import sys
    
    
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    calculator = PokerCalculator()
    calculator.show()
    sys.exit(app.exec())