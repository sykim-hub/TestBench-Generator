from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, QRect

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMinimumWidth(400)
        
        # Default properties
        self.clock_freq = 100.0  # MHz
        self.reset_delay = 100.0 # ns
        self.reset_active_low = True
        self.signals = [
            {'name': 'clk', 'type': 'clock', 'color': QColor(0, 255, 150)},
            {'name': 'rst_n', 'type': 'reset', 'color': QColor(255, 50, 50)},
            {'name': 'data', 'type': 'data', 'color': QColor(50, 200, 255)},
            {'name': 'valid', 'type': 'pulse', 'color': QColor(200, 100, 255)}
        ]

    def update_params(self, clock_freq, reset_delay, reset_name, active_low, input_signals=None, clock_name="clk", duty_cycle=50.0):
        self.clock_freq = clock_freq
        self.duty_cycle = duty_cycle
        self.reset_delay = reset_delay
        self.reset_active_low = active_low
        
        # Build signals dynamically
        self.signals = []
        self.signals.append({'name': clock_name, 'type': 'clock', 'color': QColor(0, 255, 150)})
        self.signals.append({'name': reset_name, 'type': 'reset', 'color': QColor(255, 50, 50)})
        
        if input_signals:
            colors = [QColor(50, 200, 255), QColor(200, 100, 255), QColor(255, 200, 50), QColor(100, 255, 100)]
            idx = 0
            for sig in input_signals:
                if sig['name'] in [clock_name, reset_name]: continue
                sig_type = 'data' if sig.get('width', '') else 'pulse'
                self.signals.append({'name': sig['name'], 'type': sig_type, 'color': colors[idx % len(colors)]})
                idx += 1
        else:
            self.signals.append({'name': 'data', 'type': 'data', 'color': QColor(50, 200, 255)})
            self.signals.append({'name': 'valid', 'type': 'pulse', 'color': QColor(200, 100, 255)})
            
        self.update() # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        bg_color = QColor(20, 25, 35) # Very dark blue
        painter.fillRect(self.rect(), bg_color)
        
        # Grid
        grid_pen = QPen(QColor(40, 45, 60), 1, Qt.DashLine)
        painter.setPen(grid_pen)
        width = self.width()
        height = self.height()
        
        # Draw vertical grid lines to represent time
        num_grid_lines = 10
        grid_step = width / num_grid_lines
        for i in range(1, num_grid_lines):
            x = int(i * grid_step)
            painter.drawLine(x, 0, x, height)

        # Draw signals
        if not self.signals:
            return

        margin_left = 60
        margin_top = 20
        signal_height = (height - margin_top * 2) / len(self.signals)
        
        font = QFont("Courier New", 10)
        painter.setFont(font)

        # Time scale assumptions for visualization
        # Let's say the total width represents 500ns
        total_time_ns = 500.0 
        pixels_per_ns = (width - margin_left) / total_time_ns

        for idx, sig in enumerate(self.signals):
            base_y = int(margin_top + (idx + 1) * signal_height - signal_height * 0.2)
            top_y = int(base_y - signal_height * 0.6)
            
            # Draw label
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(10, base_y - int(signal_height * 0.2), sig['name'])
            
            # Draw waveform
            pen = QPen(sig['color'], 2)
            painter.setPen(pen)
            
            x_start = margin_left
            x_end = width
            
            if sig['type'] == 'clock':
                # Calculate clock period in pixels
                period_ns = 1000.0 / max(self.clock_freq, 1.0) # avoid div by zero
                period_px = period_ns * pixels_per_ns
                high_time_px = period_px * (getattr(self, 'duty_cycle', 50.0) / 100.0)
                low_time_px = period_px - high_time_px
                
                curr_x = x_start
                state = 0 # start low (depending on phase, but let's just draw 50/50 normally)
                
                # Minimum pixel width to avoid drawing solid blocks if frequency is too high
                if high_time_px < 1: high_time_px = 1
                if low_time_px < 1: low_time_px = 1
                    
                while curr_x < x_end:
                    step_px = high_time_px if state == 1 else low_time_px
                    next_x = min(curr_x + step_px, x_end)
                    y = top_y if state == 1 else base_y
                    
                    # Draw horizontal
                    painter.drawLine(int(curr_x), int(y), int(next_x), int(y))
                    
                    # Draw vertical transition
                    if next_x < x_end:
                        next_y = base_y if state == 1 else top_y
                        painter.drawLine(int(next_x), int(y), int(next_x), int(next_y))
                        
                    curr_x = next_x
                    state = 1 - state
                    
            elif sig['type'] == 'reset':
                # Reset starts active, goes inactive after delay
                delay_px = self.reset_delay * pixels_per_ns
                transition_x = x_start + delay_px
                
                assert_y = base_y if self.reset_active_low else top_y
                deassert_y = top_y if self.reset_active_low else base_y
                
                if transition_x >= x_end:
                    # Stays asserted
                    painter.drawLine(int(x_start), int(assert_y), int(x_end), int(assert_y))
                else:
                    painter.drawLine(int(x_start), int(assert_y), int(transition_x), int(assert_y))
                    painter.drawLine(int(transition_x), int(assert_y), int(transition_x), int(deassert_y))
                    painter.drawLine(int(transition_x), int(deassert_y), int(x_end), int(deassert_y))
                    
            elif sig['type'] == 'data':
                period_ns = 1000.0 / max(self.clock_freq, 1.0)
                period_px = max(period_ns * pixels_per_ns, 1.0)  # Prevent infinite loop
                
                import random
                random.seed(hash(sig['name']))
                
                curr_x = x_start
                # Draw continuous top and bottom bus lines
                painter.drawLine(int(x_start), int(base_y), int(x_end), int(base_y))
                painter.drawLine(int(x_start), int(top_y), int(x_end), int(top_y))
                
                while curr_x < x_end:
                    curr_x += period_px
                    if curr_x < x_end and random.random() > 0.6:
                        # Draw transition crosses exactly at clock edges
                        painter.drawLine(int(curr_x), int(base_y), int(curr_x+4), int(top_y))
                        painter.drawLine(int(curr_x), int(top_y), int(curr_x+4), int(base_y))
                        
            elif sig['type'] == 'pulse':
                period_ns = 1000.0 / max(self.clock_freq, 1.0)
                period_px = max(period_ns * pixels_per_ns, 1.0) # Prevent infinite loop
                
                import random
                random.seed(hash(sig['name'] + "_pulse"))
                
                curr_x = x_start
                state = 0
                
                while curr_x < x_end:
                    next_x = min(curr_x + period_px, x_end)
                    next_state = 1 if random.random() > 0.7 else 0
                    
                    y = top_y if state == 1 else base_y
                    painter.drawLine(int(curr_x), int(y), int(next_x), int(y))
                    
                    if next_x < x_end:
                        next_y = top_y if next_state == 1 else base_y
                        if y != next_y:
                            painter.drawLine(int(next_x), int(y), int(next_x), int(next_y))
                            
                    state = next_state
                    curr_x = next_x
