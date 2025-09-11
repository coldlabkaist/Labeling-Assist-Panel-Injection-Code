        # === [Injected] Labeling-Assist Panel ===
        # Inject this code to Cutie/gui/main_controller.py line 128~
        try:
            # PyQt6 (or PyQt5 based)
            from PyQt6 import QtWidgets, QtCore, QtGui
            _QT_IS_6 = True
        except Exception:
            from PyQt5 import QtWidgets, QtCore, QtGui
            _QT_IS_6 = False

        # selectional play timer
        self._sel_timer = QtCore.QTimer()
        self._sel_timer.setInterval(0) # as fast as possible (0 ms interval)
        self._sel_timer.timeout.connect(self._on_selective_play_tick)

        # internal states for labeling-assist
        self._sel_playing: bool = False
        self._sel_seek_idx: int = max(0, self.curr_ti) 
        self._last_risk_idx: int = -10**9              
        self._scan_chunk: int = 100                      
        self._reprop_running: bool = False                
        self._range_start = None                        
        self._range_end = None            
        # selective play direction / speed
        self._sel_direction: int = 1    # +1: forward, -1: backward
        self._sel_speed_mul: int = 1    # 표시 stride (1x, 2x, 4x ...)
        self._sel_display_accum: int = 0              

        # install the panel
        self._install_labeling_assist_panel(QtWidgets, QtCore, QtGui)

    def _install_labeling_assist_panel(self, QtWidgets, QtCore, QtGui):
        import math
        WT = getattr(QtCore.Qt, "WindowType", QtCore.Qt)
        self._assist = QtWidgets.QWidget()
        try:
            self._assist.setWindowFlag(QtCore.Qt.WindowType.Tool, True)
            # self._assist.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, False)
        except Exception:
            self._assist.setWindowFlags(
                (self._assist.windowFlags() | QtCore.Qt.Tool) & ~QtCore.Qt.WindowStaysOnTopHint
            )
        self._assist.setWindowTitle("Labeling Assist")
        try:
            self._assist.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        self._assist.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        try:
            self._assist.setFixedWidth(350)
        except Exception:
            pass

        root = QtWidgets.QVBoxLayout(self._assist)
        warn = QtWidgets.QLabel(
            "※ This UI is a feature added for convenient labeling,\n"
            "and may not be compatible if used simultaneously with the existing UI's video playback/control."
        )
        warn.setWordWrap(True)
        root.addWidget(warn)

        # ---------- G1: selection paly/seek ----------
        g1 = QtWidgets.QGroupBox("Selective Play / Seek")
        l1 = QtWidgets.QVBoxLayout(g1)
        form1 = QtWidgets.QFormLayout()
        self._margin_spin = QtWidgets.QSpinBox(); self._margin_spin.setRange(0, 512); self._margin_spin.setValue(4)
        self._post_spin   = QtWidgets.QSpinBox(); self._post_spin.setRange(0, 5000); self._post_spin.setValue(10)
        form1.addRow("margin(px)", self._margin_spin)
        form1.addRow("post_window(fr)", self._post_spin)
        # speed (배속): 위험구간 재생 시 표시 stride
        self._speed_spin  = QtWidgets.QSpinBox(); self._speed_spin.setRange(1, 16); self._speed_spin.setValue(1)
        form1.addRow("sampling (×)", self._speed_spin)
        l1.addLayout(form1)
        self._btn_next_risk      = QtWidgets.QPushButton("Move to next occlusion frame")
        self._btn_sel_start      = QtWidgets.QPushButton("Start selective play")
        self._btn_sel_start_back = QtWidgets.QPushButton("Start selective play (backward)")
        self._btn_sel_stop       = QtWidgets.QPushButton("Stop selective play")
        l1.addWidget(self._btn_next_risk)
        l1.addWidget(self._btn_sel_start)
        l1.addWidget(self._btn_sel_start_back)
        l1.addWidget(self._btn_sel_stop)
        root.addWidget(g1)
        for _sb in (self._margin_spin, self._post_spin, self._speed_spin):
            _sb.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
            try:
                _sb.editingFinished.connect(self._refocus_main)
            except Exception:
                pass

        # ---------- G2: Re-Propagate the section between danger and safety ----------
        g2 = QtWidgets.QGroupBox("Re-Propagate")
        l2 = QtWidgets.QVBoxLayout(g2)
        # 순방향
        self._btn_reprop_start = QtWidgets.QPushButton("Start sectional re-propagation (forward)")
        # 역방향
        self._btn_reprop_start_back = QtWidgets.QPushButton("Start sectional re-propagation (backward)")
        # 정지
        self._btn_reprop_stop  = QtWidgets.QPushButton("Stop re-propagation")
        l2.addWidget(self._btn_reprop_start)
        l2.addWidget(self._btn_reprop_start_back)
        l2.addWidget(self._btn_reprop_stop)
        root.addWidget(g2)

        # ---------- G3: Single frame transmission ----------
        g3 = QtWidgets.QGroupBox("Propagate One Frame")
        l3 = QtWidgets.QVBoxLayout(g3)
        self._btn_one_step = QtWidgets.QPushButton("propagate one frame forward")
        self._btn_one_step_back = QtWidgets.QPushButton("propagate one frame backward")
        l3.addWidget(self._btn_one_step)
        l3.addWidget(self._btn_one_step_back)
        root.addWidget(g3)

        # ---------- G4: Reassigning range IDs (colors) ----------
        g4 = QtWidgets.QGroupBox("Mask ID Remap (Color Swap)")
        l4 = QtWidgets.QVBoxLayout(g4)
        self._lbl_range = QtWidgets.QLabel("range: (not assigned)")
        l4.addWidget(self._lbl_range)
        self._btn_mark_start = QtWidgets.QPushButton("Set start as current frame")
        self._btn_mark_end   = QtWidgets.QPushButton("Set end as current frame")
        l4.addWidget(self._btn_mark_start)
        l4.addWidget(self._btn_mark_end)
        self._btn_recolor = QtWidgets.QPushButton("Reassign IDs over the range")
        l4.addWidget(self._btn_recolor)
        root.addWidget(g4)

        _no_focus = getattr(QtCore.Qt.FocusPolicy, "NoFocus", None)
        if _no_focus is not None:
            for _btn in (
                self._btn_next_risk, self._btn_sel_start, self._btn_sel_start_back, self._btn_sel_stop,
                self._btn_reprop_start, self._btn_reprop_stop,
                self._btn_one_step,
                self._btn_mark_start, self._btn_mark_end, self._btn_recolor
            ):
                _btn.setFocusPolicy(_no_focus)

        # signal-slot connections
        self._btn_next_risk.clicked.connect(self._jump_to_next_risk)
        self._btn_sel_start.clicked.connect(self._start_selective_play)
        self._btn_sel_start_back.clicked.connect(self._start_selective_play_backward)
        self._btn_sel_stop.clicked.connect(self._stop_selective_play)

        self._btn_reprop_start.clicked.connect(self._start_reprop_segment)
        self._btn_reprop_start_back.clicked.connect(self._start_reprop_segment_backward)
        self._btn_reprop_stop.clicked.connect(self._stop_reprop_segment)

        self._btn_one_step.clicked.connect(self._propagate_one_forward)
        self._btn_one_step_back.clicked.connect(self._propagate_one_backward)

        self._btn_mark_start.clicked.connect(self._mark_range_start)
        self._btn_mark_end.clicked.connect(self._mark_range_end)
        self._btn_recolor.clicked.connect(self._open_recolor_dialog)

        # speed control for selective play
        try:
            self._speed_spin.valueChanged.connect(lambda v: setattr(self, "_sel_speed_mul", int(v)))
        except Exception:
            pass

        # additional panel
        try:
            geo = self.gui.frameGeometry()
            self._assist.move(
                geo.topRight() - QtCore.QPoint(self._assist.width(), 0) + QtCore.QPoint(-16, 0)
            )
        except Exception:
            pass
        self._assist.hide()

        self._float_btn_win = QtWidgets.QWidget()
        self._float_btn_win.setObjectName("assistFloatButtonWindow")
        self._float_btn_win.setWindowFlag(WT.FramelessWindowHint, True)
        self._float_btn_win.setWindowFlag(WT.Tool, True)
        self._float_btn_win.setWindowFlag(WT.Window, True)
        try:
            self._float_btn_win.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        self._float_btn_win.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        lay = QtWidgets.QHBoxLayout(self._float_btn_win)
        lay.setContentsMargins(8, 8, 8, 8)
        self._assist_btn = QtWidgets.QPushButton("Open Assist Panel")
        self._assist_btn.setFixedHeight(28)
        self._assist_btn.clicked.connect(self._show_assist_panel)
        lay.addWidget(self._assist_btn)
        try:
            self._assist_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        except Exception:
            pass
        try:
            self._float_btn_win.adjustSize()
        except Exception:
            pass
        self._anchor_float_button(QtCore)
        self._float_anchor_timer = QtCore.QTimer()
        self._float_anchor_timer.setInterval(250) 
        self._float_anchor_timer.timeout.connect(lambda: self._anchor_float_button(QtCore))
        self._float_anchor_timer.start()

        class _AssistKeyFilter(QtCore.QObject):
            def __init__(self, controller, parent=None):
                super().__init__(parent)
                self.c = controller
            def eventFilter(self, obj, ev):
                try:
                    if ev.type() == QtCore.QEvent.Type.KeyPress:
                        key = ev.key()
                        if key in (getattr(QtCore.Qt.Key, "Key_Left"), getattr(QtCore.Qt.Key, "Key_Right")):
                            if key == getattr(QtCore.Qt.Key, "Key_Left"):
                                self.c.on_prev_frame(1)
                            else:
                                self.c.on_next_frame(1)
                            return True 
                except Exception:
                    pass
                return False
        try:
            self._assist_key_filter = _AssistKeyFilter(self, self._assist)
            self._assist.installEventFilter(self._assist_key_filter)
            for _w in self._assist.findChildren(QtWidgets.QWidget):
                _w.installEventFilter(self._assist_key_filter)
        except Exception:
            pass

        def _resolve_parent_qwidget() -> "QtWidgets.QWidget|None":
            app = QtWidgets.QApplication.instance()
            cands = []
            if isinstance(getattr(self, "gui", None), QtWidgets.QWidget):
                cands.append(self.gui)
            if getattr(self, "gui", None) is not None:
                for name in ("window", "win", "main_window", "mainwindow"):
                    attr = getattr(self.gui, name, None)
                    if callable(attr):
                        try:
                            attr = attr()
                        except Exception:
                            attr = None
                    if isinstance(attr, QtWidgets.QWidget):
                        cands.append(attr)
                        break
            if app is not None:
                aw = app.activeWindow()
                if isinstance(aw, QtWidgets.QWidget):
                    cands.append(aw)
                for w in app.topLevelWidgets():
                    if isinstance(w, QtWidgets.QMainWindow):
                        cands.append(w)
                        break
                cands += [w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QWidget)]
            for w in cands:
                if w is not None and w is not self._float_btn_win:
                    return w
            return None
        parent_win = _resolve_parent_qwidget()
        if parent_win is not None:
            self._assist.setParent(parent_win, WT.Tool | WT.Window)
            try:
                self._assist.hide()
            except Exception:
                pass

            self._float_btn_win.setParent(
                parent_win,
                WT.FramelessWindowHint | WT.Tool | WT.Window
            )
            try:
                self._float_btn_win.show()
            except Exception:
                pass
            try:
                self._shortcut_R = QtGui.QShortcut(QtGui.QKeySequence("R"), parent_win)
                self._shortcut_R.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
                self._shortcut_R.activated.connect(self._shortcut_reset_all_memory)
            except Exception:
                pass
            try:
                self._shortcut_space = QtGui.QShortcut(QtGui.QKeySequence("Space"), parent_win)
                self._shortcut_space.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
                self._shortcut_space.activated.connect(self._shortcut_stop_all_play)
                self._shortcut_space.setEnabled(False)
            except Exception:
                pass

            class _AssistVisFilter(QtCore.QObject):
                def __init__(self, shortcut, parent=None):
                    super().__init__(parent)
                    self._sc = shortcut
                def eventFilter(self, obj, ev):
                    try:
                        et = int(ev.type())
                        if et == int(QtCore.QEvent.Type.Show):
                            if self._sc is not None:
                                self._sc.setEnabled(True)
                        elif et in (int(QtCore.QEvent.Type.Hide), int(QtCore.QEvent.Type.Close)):
                            if self._sc is not None:
                                self._sc.setEnabled(False)
                    except Exception:
                        pass
                    return False
            try:
                self._assist_vis_filter = _AssistVisFilter(getattr(self, "_shortcut_space", None), self._assist)
                self._assist.installEventFilter(self._assist_vis_filter)
            except Exception:
                pass
            try:
                self._assist_vis_filter = _AssistVisFilter(getattr(self, "_shortcut_space", None), self._assist)
                self._assist.installEventFilter(self._assist_vis_filter)
            except Exception:
                pass

            class _ParentRaiseFilter(QtCore.QObject):
                def __init__(self, panel, float_win, parent=None):
                    super().__init__(parent)
                    self._panel = panel
                    self._float = float_win
                def eventFilter(self, obj, ev):
                    try:
                        et = int(ev.type())
                        if et in (
                            int(QtCore.QEvent.Type.WindowActivate),
                            int(QtCore.QEvent.Type.Show),
                            int(QtCore.QEvent.Type.ZOrderChange),
                            int(QtCore.QEvent.Type.Move),
                            int(QtCore.QEvent.Type.Resize),
                        ):
                            if self._float is not None and self._float.isVisible():
                                self._float.raise_()
                            if self._panel is not None and self._panel.isVisible():
                                self._panel.raise_()
                    except Exception:
                        pass
                    return False
            try:
                self._parent_raise_filter = _ParentRaiseFilter(self._assist, self._float_btn_win, parent_win)
                parent_win.installEventFilter(self._parent_raise_filter)
            except Exception:
                pass

    def _show_assist_panel(self):
        try:
            try:
                self._assist.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            except Exception:
                pass
            self._assist.show()
            self._assist.raise_()
        except Exception:
            pass

    def _anchor_float_button(self, QtCore):
        """CUTIE 메인 윈도우(frameGeometry) 기준으로 floating 버튼을 우하단에 고정."""
        try:
            if not hasattr(self, "_float_btn_win"):
                return
            geo = self.gui.frameGeometry()  # 전역 좌표의 QRect
            w = self._float_btn_win.width()
            h = self._float_btn_win.height()
            margin = 0
            # frameGeometry는 글로벌 좌표, topLeft/right/bottom 반환도 글로벌 기준
            x = geo.right() - w - margin
            y = geo.bottom() - h - margin
            # move는 스크린 좌표 기준
            self._float_btn_win.move(x, y)
        except Exception:
            pass

    def _shortcut_stop_all_play(self):
        try:
            if hasattr(self, "_assist") and self._assist.isVisible():
                if getattr(self, "_sel_playing", False):
                    self._stop_selective_play()
                if getattr(self, "_reprop_running", False):
                    self._stop_reprop_segment()
                if getattr(self, "propagating", False):
                    self.on_pause()
        except Exception:
            pass

    def _shortcut_reset_all_memory(self):
        try:
            self.on_clear_memory()
            self.gui.text("All memory cleared (via 'R').")
        except Exception:
            pass

    def _refocus_main(self):
        """보조 패널 위젯에서 포커스를 해제하고 메인 윈도우로 돌려줍니다."""
        try:
            # 현재 활성 창이 메인이 아니면, top-level 중 첫 번째 QWidget에 포커스 시도
            try:
                from PyQt6 import QtWidgets as _QW
            except Exception:
                from PyQt5 import QtWidgets as _QW
            app = _QW.QApplication.instance()
            win = app.activeWindow() if app else None
            if win is None and app is not None:
                tls = app.topLevelWidgets()
                win = tls[0] if tls else None
            if win is not None:
                win.setFocus()
        except Exception:
            pass

    def _is_occlusion_risk(self, mask_np, margin_px: int) -> bool:
        import numpy as np, cv2
        if margin_px <= 0:
            # simple occlusion check
            seen = np.zeros(mask_np.shape, dtype=np.uint8)
            for oid in range(1, self.num_objects + 1):
                binm = (mask_np == oid).astype(np.uint8)
                if (seen & binm).any():
                    return True
                seen |= binm
            return False
        # margin dilation check
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin_px * 2 + 1, margin_px * 2 + 1))
        seen = np.zeros(mask_np.shape, dtype=np.uint8)
        for oid in range(1, self.num_objects + 1):
            binm = (mask_np == oid).astype(np.uint8)
            if not binm.any():
                continue
            dil = cv2.dilate(binm, k, iterations=1)
            if (seen & dil).any():
                return True
            seen |= dil
        return False

    def _display_or_save_if_needed(self, ti: int, img_np, mask_np):
        if self.save_visualization_mode == 'Always':
            vis = get_visualization(self.vis_mode, img_np, mask_np, self.overlay_layer, self.vis_target_objects)
            self.res_man.save_visualization(ti, self.vis_mode, vis)

    def _scan_next_risk(self, start_idx: int, margin: int, post_window: int) -> int:
        import numpy as np
        last_risk = -10**9
        for i in range(start_idx, self.T):
            m = self.res_man.get_mask(i)
            if m is None:
                m = np.zeros((self.h, self.w), dtype=np.uint8)
            risky = self._is_occlusion_risk(m, margin)
            if risky:
                last_risk = i
                return i
            if i - last_risk <= post_window:
                return i
        return -1

    def _start_selective_play(self):
        self._sel_playing = True
        self._sel_direction = 1
        self._sel_display_accum = 0
        self._sel_seek_idx = self.curr_ti 
        self._last_risk_idx = -10**9
        self._sel_timer.start()

    def _start_selective_play_backward(self):
        self._sel_playing = True
        self._sel_direction = -1
        self._sel_display_accum = 0
        self._sel_seek_idx = self.curr_ti
        self._last_risk_idx = 10**9
        self._sel_timer.start()

    def _stop_selective_play(self):
        self._sel_playing = False
        self._sel_timer.stop()

    def _on_selective_play_tick(self):
        import numpy as np
        if not self._sel_playing:
            return
        margin = int(self._margin_spin.value())
        postw  = int(self._post_spin.value())
        steps = 0
        while self._sel_playing and steps < self._scan_chunk:
            step = -1 if getattr(self, "_sel_direction", 1) < 0 else 1
            i = self._sel_seek_idx + step
            if i >= self.T or i < 0:
                self._stop_selective_play()
                return
            self._sel_seek_idx = i

            img = self.res_man.get_image(i)
            m = self.res_man.get_mask(i)
            if m is None:
                m = np.zeros((self.h, self.w), dtype=np.uint8)

            risky = self._is_occlusion_risk(m, margin)
            if risky:
                self._last_risk_idx = i

            if risky or (abs(i - self._last_risk_idx) <= postw):
                self._display_or_save_if_needed(i, img, m)
                self.curr_ti = i
                self._sel_display_accum = (self._sel_display_accum + 1) % max(1, getattr(self, "_sel_speed_mul", 1))
                if self._sel_display_accum == 0:
                    self.load_current_image_mask()
                    self.show_current_frame()
                    self.gui.process_events()
                    return
            else:
                self._display_or_save_if_needed(i, img, m)

            steps += 1
        self.gui.process_events()

    def _jump_to_next_risk(self):
        margin = int(self._margin_spin.value())
        postw  = int(self._post_spin.value())
        idx = self._scan_next_risk(self.curr_ti + 1, margin, postw)
        if idx >= 0:
            self.curr_ti = idx
            self.load_current_image_mask()
            self.show_current_frame()

    def _find_safe_segment_ahead(self, start_idx: int, margin: int, postw: int):
        import numpy as np
        T = self.T
        def is_risky(i):
            m = self.res_man.get_mask(i)
            if m is None:
                m = np.zeros((self.h, self.w), dtype=np.uint8)
            return self._is_occlusion_risk(m, margin)
        i = start_idx
        if i >= T:
            return None

        if not is_risky(i):
            found = False
            for k in range(i, T):
                if is_risky(k):
                    i = k
                    found = True
                    break
            if not found:
                return None
        last_risk = i

        s = None
        for k in range(i + 1, T):
            m = self.res_man.get_mask(k)
            if m is None:
                import numpy as np
                m = np.zeros((self.h, self.w), dtype=np.uint8)
            if self._is_occlusion_risk(m, margin):
                last_risk = k
                continue
            if k - last_risk > postw:
                s = k
                break
        if s is None:
            return None

        e = T - 1
        for k in range(s + 1, T):
            if is_risky(k):
                e = k - 1
                break
        if e < s:
            return None
        return (s, e)

    def _start_reprop_segment(self):
        from torch import autocast
        import numpy as np

        if self._reprop_running:
            return
        margin = int(self._margin_spin.value())
        postw  = int(self._post_spin.value())

        seg = self._find_safe_segment_ahead(self.curr_ti, margin, postw)
        if seg is None:
            self.gui.text("No frames to re-propagate.")
            return
        s, e = seg
        self._reprop_running = True
        self.gui.text(f"Re-propagate: [{s}..{e}]")

        with autocast(self.device, enabled=(self.amp and self.device == 'cuda')):
            self.convert_current_image_mask_torch()
            self.processor.clear_sensory_memory()
            self.curr_prob = self.processor.step(self.curr_image_torch,
                                                self.curr_prob[1:], idx_mask=False)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
            self.interacted_prob = None
            self.reset_this_interaction()
            self.show_current_frame(fast=True, invalid_soft_mask=True)

            start_ti = min(max(self.curr_ti + 1, 0), self.T - 1)
            end_ti = max(e, start_ti)
            for ti in range(start_ti, end_ti + 1):
                if not self._reprop_running:
                    break
                self.curr_image_np = self.res_man.get_image(ti)
                self.curr_image_torch = to_tensor(self.curr_image_np).to(self.device, non_blocking=True)
                self.curr_prob = self.processor.step(self.curr_image_torch)
                self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
                self.curr_ti = ti
                self.save_current_mask()
                self.show_current_frame(fast=True)
                self.update_memory_gauges()
                self.gui.process_events()

        self._reprop_running = False
        self.gui.text("Re-propagate ended.")

    def _stop_reprop_segment(self):
        self._reprop_running = False

    def _propagate_one_forward(self):
        from torch import autocast
        if self.curr_ti >= self.T - 1:
            return
        with autocast(self.device, enabled=(self.amp and self.device == 'cuda')):
            self.convert_current_image_mask_torch()
            self.processor.clear_sensory_memory()
            self.curr_prob = self.processor.step(self.curr_image_torch,
                                                self.curr_prob[1:], idx_mask=False)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
            self.interacted_prob = None
            self.reset_this_interaction()
            self.show_current_frame(fast=True, invalid_soft_mask=True)

            ti = self.curr_ti + 1
            self.curr_image_np = self.res_man.get_image(ti)
            self.curr_image_torch = to_tensor(self.curr_image_np).to(self.device, non_blocking=True)
            self.curr_prob = self.processor.step(self.curr_image_torch)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)

            self.curr_ti = ti
            self.save_current_mask()
            self.show_current_frame(fast=True)

            self.update_memory_gauges()
            self.gui.process_events()

    def _find_safe_segment_backward(self, start_idx: int, margin: int, postw: int):
        import numpy as np
        def is_risky(i):
            m = self.res_man.get_mask(i)
            if m is None:
                m = np.zeros((self.h, self.w), dtype=np.uint8)
            return self._is_occlusion_risk(m, margin)

        i = start_idx
        if i < 0:
            return None
        if not is_risky(i):
            found = False
            for k in range(i, -1, -1):
                if is_risky(k):
                    i = k
                    found = True
                    break
            if not found:
                return None
        last_risk = i  

        e = None
        for k in range(i - 1, -1, -1):
            m = self.res_man.get_mask(k)
            if m is None:
                m = np.zeros((self.h, self.w), dtype=np.uint8)
            if self._is_occlusion_risk(m, margin):
                last_risk = k
                continue
            if (last_risk - k) > postw:
                e = k
                break
        if e is None:
            return None

        s = 0
        for k in range(e - 1, -1, -1):
            if is_risky(k):
                s = k + 1
                break
        if s > e:
            return None
        return (s, e)

    def _start_reprop_segment_backward(self):
        from torch import autocast
        if self._reprop_running:
            return
        margin = int(self._margin_spin.value())
        postw  = int(self._post_spin.value())
        seg = self._find_safe_segment_backward(self.curr_ti, margin, postw)
        if seg is None:
            self.gui.text("No frames to re-propagate (backward).")
            return
        s, e = seg
        self._reprop_running = True
        self.gui.text(f"Re-propagate (backward): [{s}..{e}]")

        with autocast(self.device, enabled=(self.amp and self.device == 'cuda')):
            self.convert_current_image_mask_torch()
            self.processor.clear_sensory_memory()
            self.curr_prob = self.processor.step(self.curr_image_torch,
                                                self.curr_prob[1:], idx_mask=False)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
            self.interacted_prob = None
            self.reset_this_interaction()
            self.show_current_frame(fast=True, invalid_soft_mask=True)

            begin_ti = max(self.curr_ti - 1, 0)
            end_ti = max(min(s, begin_ti), 0)
            for ti in range(begin_ti, end_ti - 1, -1):
                if not self._reprop_running:
                    break
                self.curr_image_np = self.res_man.get_image(ti)
                self.curr_image_torch = to_tensor(self.curr_image_np).to(self.device, non_blocking=True)
                self.curr_prob = self.processor.step(self.curr_image_torch)
                self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
                self.curr_ti = ti
                self.save_current_mask()
                self.show_current_frame(fast=True)
                self.update_memory_gauges()
                self.gui.process_events()

        self._reprop_running = False
        self.gui.text("Re-propagate (backward) ended.")

    def _propagate_one_backward(self):
        from torch import autocast
        if self.curr_ti <= 0:
            return
        with autocast(self.device, enabled=(self.amp and self.device == 'cuda')):
            self.convert_current_image_mask_torch()
            self.processor.clear_sensory_memory()
            self.curr_prob = self.processor.step(self.curr_image_torch,
                                                self.curr_prob[1:], idx_mask=False)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)
            self.interacted_prob = None
            self.reset_this_interaction()
            self.show_current_frame(fast=True, invalid_soft_mask=True)

            ti = self.curr_ti - 1
            self.curr_image_np = self.res_man.get_image(ti)
            self.curr_image_torch = to_tensor(self.curr_image_np).to(self.device, non_blocking=True)
            self.curr_prob = self.processor.step(self.curr_image_torch)
            self.curr_mask = torch_prob_to_numpy_mask(self.curr_prob)

            self.curr_ti = ti
            self.save_current_mask()
            self.show_current_frame(fast=True)

            self.update_memory_gauges()
            self.gui.process_events()

    def _mark_range_start(self):
        self._range_start = int(self.curr_ti)
        self._update_range_label()

    def _mark_range_end(self):
        self._range_end = int(self.curr_ti)
        self._update_range_label()

    def _update_range_label(self):
        if self._range_start is None or self._range_end is None:
            self._lbl_range.setText("duration: (not assinged)")
        else:
            s = min(self._range_start, self._range_end)
            e = max(self._range_start, self._range_end)
            self._lbl_range.setText(f"duration: {s} ~ {e} (included)")

    def _open_recolor_dialog(self):
        import numpy as np
        from typing import Dict

        if self._range_start is None or self._range_end is None:
            self.gui.text("First, specify the start/end frames.")
            return
        s = min(self._range_start, self._range_end)
        e = max(self._range_start, self._range_end)

        ids = set()
        for ti in range(s, e + 1):
            m = self.res_man.get_mask(ti)
            if m is None:
                continue
            ids.update(np.unique(m).tolist())
        ids.discard(0) 
        if not ids:
            self.gui.text("The specified range does not contain an object ID.")
            return
        ids = sorted(ids)

        try:
            from PyQt6 import QtWidgets as _QW, QtCore as _QC
        except Exception:
            from PyQt5 import QtWidgets as _QW, QtCore as _QC

        dlg = _QW.QDialog(self._assist)
        dlg.setWindowTitle("ID reassignment (color swap)")
        v = _QW.QVBoxLayout(dlg)
        form = _QW.QFormLayout()
        v.addLayout(form)

        combos = {}
        for oid in ids:
            cb = _QW.QComboBox()
            for tgt in range(1, self.num_objects + 1):
                cb.addItem(str(tgt), userData=tgt)
            cb.setCurrentText(str(oid))
            roww = _QW.QWidget()
            h = _QW.QHBoxLayout(roww); h.setContentsMargins(0,0,0,0)
            sw = _QW.QLabel()
            sw.setFixedSize(18, 18)
            try:
                r,g,b = self._id_to_color(oid)
                sw.setStyleSheet(f"background-color: rgb({r},{g},{b}); border:1px solid #444;")
            except Exception:
                pass
            h.addWidget(sw)
            h.addWidget(cb, 1)
            form.addRow(_QW.QLabel(f"ID {oid} →"), roww)
            combos[oid] = cb

        warn = _QW.QLabel("Caution: Merging multiple IDs into one may result in data loss. Do you want to continue?")
        v.addWidget(warn)

        try:
            okb = _QW.QDialogButtonBox.StandardButton.Ok
            ccb = _QW.QDialogButtonBox.StandardButton.Cancel
            btns = _QW.QDialogButtonBox(okb | ccb)
        except AttributeError:
            btns = _QW.QDialogButtonBox(_QW.QDialogButtonBox.Ok | _QW.QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        accepted = False
        try:
            # PyQt6
            accepted = (dlg.exec() == _QW.QDialog.DialogCode.Accepted)
        except Exception:
            # PyQt5
            accepted = (dlg.exec_() == _QW.QDialog.Accepted)
        if not accepted:
            return

        mapping: Dict[int, int] = {}
        for oid, cb in combos.items():
            val = cb.currentData()
            if val is None:
                try:
                    val = int(cb.currentText())
                except Exception:
                    val = oid
            mapping[oid] = int(val)

        if len(set(mapping.values())) < len(mapping):
            try:
                yes = _QW.QMessageBox.StandardButton.Yes
                no  = _QW.QMessageBox.StandardButton.No
                yn = _QW.QMessageBox.warning(
                    self._assist, "Warning",
                    "Multiple existing IDs will be merged into a single ID. Do you want to continue?",
                    yes | no, no
                )
                proceed = (yn == yes)
            except AttributeError:
                yn = _QW.QMessageBox.warning(
                    self._assist, "Warning",
                    "Multiple existing IDs will be merged into a single ID. Do you want to continue?",
                    _QW.QMessageBox.Yes | _QW.QMessageBox.No, _QW.QMessageBox.No
                )
                proceed = (yn == _QW.QMessageBox.Yes)
            if not proceed:
                return

        self._apply_recolor_over_range(mapping, s, e)

    def _apply_recolor_over_range(self, mapping, s: int, e: int):
        import numpy as np
        lut = np.arange(self.num_objects + 1, dtype=np.uint8)
        for k, v in mapping.items():
            if 1 <= k <= self.num_objects and 1 <= v <= self.num_objects:
                lut[k] = v

        for ti in range(s, e + 1):
            img = self.res_man.get_image(ti)
            m = self.res_man.get_mask(ti)
            if m is None:
                continue
            new_m = lut[m]
            self.res_man.save_mask(ti, new_m)

            if self.save_visualization_mode == 'Always':
                vis = get_visualization(self.vis_mode, img, new_m, self.overlay_layer, self.vis_target_objects)
                self.res_man.save_visualization(ti, self.vis_mode, vis)

            if ti == self.curr_ti:
                self.curr_mask = new_m.copy()
                self.curr_prob = None
                self.show_current_frame()

        self.gui.text(f"ID Re-assigned: [{s}..{e}]")

    def _id_to_color(self, oid: int):
        CUTIE_COLOR_BASE = [
            "#ab1f24", "#36ae37", "#b9b917", "#063391", "#983a91",
            "#20b6b5", "#c1c0bf", "#5c0d11", "#e71f19", "#60b630",
            "#f4ba19", "#503390", "#ca4392", "#5eb7b7", "#f6bcbc"
        ]
        try:
            color_hex = CUTIE_COLOR_BASE[(oid - 1) % len(CUTIE_COLOR_BASE)]
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            return r, g, b
        except Exception:
            return 128, 128, 128
    # === [Injected End] ===
