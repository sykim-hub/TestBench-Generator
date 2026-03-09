from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtCore import Qt, QRect, QPointF

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMinimumWidth(400)
        self.config = {}
        
        self.signals_list = []
        self.gap_ranges = []
        self.t_mapping = []
        self.events = {}
        self.initial_vals = {}
        self.total_width = 400
        self.t_unique = []

    def get_delay_ns(self, r):
        val = float(r.get('delay_ns', 100.0))
        if r.get('delay_unit', 'ns') == 'cycles':
            clock_name = r.get('delay_clock', 'clk')
            clk = next((x for x in self.config.get('clocks', []) if x['name'] == clock_name), None)
            if clk:
                period = 1000.0 / max(clk.get('frequency_mhz', 100.0), 1.0)
                val = val * period
            else:
                val = val * 10.0
        return val

    def time_to_x(self, t_ns):
        if not self.t_mapping:
            return 0
        if t_ns <= self.t_mapping[0][0]:
            return self.t_mapping[0][1]
            
        for i in range(1, len(self.t_mapping)):
            t0, x0 = self.t_mapping[i-1]
            t1, x1 = self.t_mapping[i]
            if t_ns <= t1:
                if t1 == t0: return x0
                ratio = (t_ns - t0) / (t1 - t0)
                return x0 + ratio * (x1 - x0)
                
        return self.t_mapping[-1][1]

    def update_from_config(self, config, input_signals=None):
        self.config = config
        
        clocks = config.get('clocks', [])
        resets = config.get('resets', [])
        auto_sigs = [r for r in resets if r.get('auto', True)]
        
        self.signals_list = []
        for c in clocks:
            self.signals_list.append({'name': c['name'], 'type': 'clock', 'freq': c.get('frequency_mhz', 100.0), 'color': QColor(0, 255, 150)})
            
        color_pool = [QColor(255, 100, 100), QColor(100, 200, 255), QColor(255, 200, 100), QColor(200, 100, 255)]
        
        current_time = 0.0
        self.events = {} 
        self.initial_vals = {}
        
        for r in auto_sigs:
            self.events[r['name']] = []
            self.initial_vals[r['name']] = r['init_val']
            self.signals_list.append({'name': r['name'], 'type': 'control', 'color': color_pool[len(self.signals_list) % len(color_pool)]})

        i = 0
        while i < len(auto_sigs):
            r = auto_sigs[i]
            if r.get('timing', 'sequential') == 'parallel':
                batch = [r]
                i += 1
                while i < len(auto_sigs) and auto_sigs[i].get('timing', 'sequential') == 'parallel':
                    batch.append(auto_sigs[i])
                    i += 1
                max_delay = 0.0
                for br in batch:
                    d = self.get_delay_ns(br)
                    self.events[br['name']].append((current_time + d, br['final_val']))
                    max_delay = max(max_delay, d)
                current_time += max_delay
            else:
                d = self.get_delay_ns(r)
                self.events[r['name']].append((current_time + d, r['final_val']))
                current_time += d
                i += 1

        self.end_time = current_time + 40.0 

        t_unique = {0.0, self.end_time}
        for sig_events in self.events.values():
            for t, val in sig_events:
                t_unique.add(t)
        self.t_unique = sorted(list(t_unique))

        margin_left = 120
        pixels_per_ns = 3.0
        gap_pixel_width = 30
        gap_threshold_ns = 30.0
        
        self.t_mapping = [(0.0, margin_left)]
        self.gap_ranges = []
        
        current_x = margin_left
        for i in range(1, len(self.t_unique)):
            t_prev = self.t_unique[i-1]
            t_curr = self.t_unique[i]
            dt = t_curr - t_prev
            
            if dt > gap_threshold_ns:
                draw_ns = 5.0
                current_x += draw_ns * pixels_per_ns
                gs = current_x
                self.t_mapping.append((t_prev + draw_ns, current_x))
                
                current_x += gap_pixel_width
                ge = current_x
                self.t_mapping.append((t_curr - draw_ns, current_x))
                
                current_x += draw_ns * pixels_per_ns
                self.gap_ranges.append((gs, ge, t_prev + draw_ns, t_curr - draw_ns))
            else:
                current_x += dt * pixels_per_ns
                
            self.t_mapping.append((t_curr, current_x))
            
        self.total_width = current_x + margin_left

        self.setMinimumWidth(max(400, int(self.total_width + 40)))
        num_sigs = len(self.signals_list)
        min_height = max(200, num_sigs * 50 + 60)
        self.setMinimumHeight(min_height)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        bg_color = QColor(20, 25, 35)
        painter.fillRect(self.rect(), bg_color)
        
        if not self.signals_list:
            return

        margin_top = 40
        height = self.height()
        signal_height = (height - margin_top * 2) / max(len(self.signals_list), 1)

        font = QFont("Courier New", 9)
        painter.setFont(font)
        
        # Draw time axis
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(120, margin_top - 10, int(self.total_width), margin_top - 10)
        
        last_text_end = -100
        for t in self.t_unique:
            x = int(self.time_to_x(t))
            
            # draw vertical guide
            painter.setPen(QPen(QColor(255, 255, 255, 10), 1, Qt.DashLine))
            painter.drawLine(x, margin_top - 10, x, height)
            
            # draw tick
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            painter.drawLine(x, margin_top - 10, x, margin_top - 5)
            
            text = f"{t:g}"
            text_rect = painter.fontMetrics().boundingRect(text)
            
            draw_x = int(x - text_rect.width()/2)
            if draw_x > last_text_end + 5:
                painter.drawText(draw_x, margin_top - 15, text)
                last_text_end = draw_x + text_rect.width()

        for idx, sig in enumerate(self.signals_list):
            base_y = int(margin_top + (idx + 1) * signal_height - signal_height * 0.2)
            top_y = int(base_y - signal_height * 0.6)
            
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(10, base_y - int(signal_height * 0.2), sig['name'])
            
            pen = QPen(sig['color'], 2)
            painter.setPen(pen)
            
            if sig['type'] == 'clock':
                period_ns = 1000.0 / max(sig['freq'], 0.001)
                t = 0.0
                state = 1
                
                while t < self.end_time:
                    in_gap = False
                    for gs, ge, ts, te in self.gap_ranges:
                        if ts <= t < te:
                            x_start = self.time_to_x(t)
                            x_end = self.time_to_x(te)
                            y = top_y if state == 1 else base_y
                            painter.drawLine(int(x_start), int(y), int(x_end), int(y))
                            t = te
                            eval_t = t + 0.001
                            state = 1 if ((eval_t % period_ns) < period_ns/2) else 0
                            in_gap = True
                            break
                            
                    if in_gap: continue
                    
                    time_to_edge = period_ns/2 - (t % (period_ns/2))
                    if time_to_edge <= 0.001: time_to_edge = period_ns/2
                    t_next = min(t + time_to_edge, self.end_time)
                    
                    for gs, ge, ts, te in self.gap_ranges:
                        if t < ts < t_next:
                            t_next = ts
                            break
                            
                    x_start = self.time_to_x(t)
                    x_end = self.time_to_x(t_next)
                    
                    y = top_y if state == 1 else base_y
                    painter.drawLine(int(x_start), int(y), int(x_end), int(y))
                    
                    is_gap_boundary = any(abs(t_next - ts) < 0.001 for _, _, ts, _ in self.gap_ranges)
                    if t_next < self.end_time and not is_gap_boundary:
                        next_state = 1 if (((t_next + 0.001) % period_ns) < period_ns/2) else 0
                        next_y = top_y if next_state == 1 else base_y
                        if y != next_y:
                            painter.drawLine(int(x_end), int(y), int(x_end), int(next_y))
                            
                    t = t_next
                    eval_t = t + 0.001
                    state = 1 if ((eval_t % period_ns) < period_ns/2) else 0
                        
            elif sig['type'] == 'control':
                sig_events = self.events.get(sig['name'], [])
                curr_val = self.initial_vals.get(sig['name'], '0')
                
                curr_x = self.time_to_x(0.0)
                for ev_t, ev_val in sig_events:
                    ev_x = self.time_to_x(ev_t)
                    y = top_y if curr_val == '1' else base_y
                    
                    painter.drawLine(int(curr_x), int(y), int(ev_x), int(y))
                    
                    next_y = top_y if ev_val == '1' else base_y
                    if y != next_y:
                        painter.drawLine(int(ev_x), int(y), int(ev_x), int(next_y))
                        
                    curr_x = ev_x
                    curr_val = ev_val
                    
                y = top_y if curr_val == '1' else base_y
                end_x = self.time_to_x(self.end_time)
                painter.drawLine(int(curr_x), int(y), int(end_x), int(y))

        # Draw Gap Overlays last so they seamlessly cut the signals
        for gs, ge, _, _ in self.gap_ranges:
            slope_offset = 6
            
            # Wipe signal lines between the tear
            poly = QPolygonF()
            poly.append(QPointF(gs - slope_offset, height))
            poly.append(QPointF(gs + slope_offset, 0))
            poly.append(QPointF(ge + slope_offset, 0))
            poly.append(QPointF(ge - slope_offset, height))
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_color)
            painter.drawPolygon(poly)
            
            # Draw the tear lines
            painter.setPen(QPen(QColor(100, 130, 200), 2))
            painter.drawLine(int(gs - slope_offset), height, int(gs + slope_offset), 0)
            painter.drawLine(int(ge - slope_offset), height, int(ge + slope_offset), 0)
