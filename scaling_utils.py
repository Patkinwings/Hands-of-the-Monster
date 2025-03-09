from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtGui import QFont

def apply_scaling(stats_table, scale):
    # Update table dimensions
    stats_table.verticalHeader().setDefaultSectionSize(scale['row_height'])
    for column in range(stats_table.columnCount()):
        stats_table.setColumnWidth(column, scale['col_width'])
    
    # Update all cells with new scaling
    for row in range(stats_table.rowCount()):
        for col in range(stats_table.columnCount()):
            cell_widget = stats_table.cellWidget(row, col)
            if isinstance(cell_widget, QWidget):
                layout = cell_widget.layout()
                if not layout:
                    continue
                
                # Set all margins to 0
                layout.setContentsMargins(0, 0, 0, 0)
                
                hist_widget = layout.itemAtPosition(0, 1).widget()
                if isinstance(hist_widget, QLabel):
                    font = hist_widget.font()
                    font.setPointSize(scale['hist_font'])
                    hist_widget.setFont(font)
                    
                    # Apply symbol removal and abbreviation to historical values
                    text = hist_widget.text()
                    if scale['remove_symbols']:
                        text = text.replace('%', '')
                    if scale['abbreviate']:
                        text = abbreviate_text(text)
                    hist_widget.setText(text)
                    
                session_widget = layout.itemAtPosition(1, 0).widget()
                if isinstance(session_widget, QLabel):
                    font = session_widget.font()
                    font.setPointSize(scale['main_font'])
                    session_widget.setFont(font)
                    
                    text = session_widget.text()
                    if scale['remove_symbols']:
                        text = text.replace('%', '')
                    if scale['abbreviate']:
                        text = abbreviate_text(text)
                    session_widget.setText(text)

def get_scale_level(window_width):
    scale_levels = {
        
        600: {  # Extra small window
            'main_font': 10,
            'hist_font': 8,
            'row_height': 38,
            'col_width': 70,
            'remove_symbols': True,
            'abbreviate': True
        },
        
        800: {  # Extra small window
            'main_font': 12,
            'hist_font': 10,
            'row_height': 42,
            'col_width': 75,
            'remove_symbols': True,
            'abbreviate': True
        },
        1000: {  # Small window
            'main_font': 14,
            'hist_font': 12,
            'row_height': 50,
            'col_width': 85,
            'remove_symbols': True,
            'abbreviate': True
        },
        1200: {  # Medium window
            'main_font': 14,
            'hist_font': 12,
            'row_height': 55,
            'col_width': 82,
            'remove_symbols': False,
            'abbreviate': False
        },
        1400: {  # Large window
            'main_font': 14,
            'hist_font': 12,
            'row_height': 80,
            'col_width': 95,
            'remove_symbols': False,
            'abbreviate': False
        },
        1600: {  # Extra large window
            'main_font': 15,
            'hist_font': 12,
            'row_height': 125,
            'col_width': 170,
            'remove_symbols': False,
            'abbreviate': False
        },
        
        1900: {  # Extra large window
            'main_font': 16,
            'hist_font': 12,
            'row_height': 130,
            'col_width': 175,
            'remove_symbols': False,
            'abbreviate': False
        }
    }
    
    for width, scale in sorted(scale_levels.items()):
        if window_width <= width:
            return scale
    return scale_levels[1600]

def abbreviate_text(text):
    abbreviations = {
        'VPIP': 'VP',
        'PFR': 'PF',
        'F3B': 'F3',
        '3Bet': '3B',
        'Unknown': 'Un',
        'Initial': 'none',
        'Maniac': 'Man',
        'Tight Aggressive': 'TAG',
        'Loose Aggressive': 'LAG'
    }
    
    for full, abbr in abbreviations.items():
        text = text.replace(full, abbr)
    return text