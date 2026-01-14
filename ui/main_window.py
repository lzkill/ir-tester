"""
Main Window for the IR Tester application
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSlider, QGroupBox,
    QDialog, QTreeView, QAbstractItemView, QHeaderView, QListView,
    QSplitter, QFrame, QMessageBox, QProgressBar, QTreeWidgetItemIterator, QApplication, QFileDialog,
    QCheckBox, QComboBox, QDialogButtonBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QDir
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtWidgets import QMenu, QStyle

import matplotlib
matplotlib.use('qtagg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np
import soundfile as sf
import scipy.fft

from audio.audio_engine import AudioEngine
from audio.convolution import ConvolutionProcessor
from audio.convolution_worker import ConvolutionWorker
from audio.equalizer import Equalizer
from ui.equalizer_dialog import EqualizerDialog


class IRPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor='#1e1e1e')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        
        self._style_axes()
        
        layout.addWidget(self.canvas)
        
    def _style_axes(self):
        """Applies dark styles to the axes"""
        self.ax.tick_params(colors='#888888', labelsize=8)
        self.ax.spines['bottom'].set_color('#444444')
        self.ax.spines['top'].set_color('#444444') 
        self.ax.spines['left'].set_color('#444444')
        self.ax.spines['right'].set_color('#444444')
        self.ax.xaxis.label.set_color('#888888')
        self.ax.yaxis.label.set_color('#888888')
        self.ax.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        self.figure.tight_layout()

    def plot_ir(self, file_path):
        """Calculates and plots the IR frequency response"""
        try:
            data, samplerate = sf.read(file_path)
            
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            n = len(data)
            yf = scipy.fft.fft(data)
            xf = scipy.fft.fftfreq(n, 1 / samplerate)
            
            # Use only positive frequencies
            half_n = n // 2
            xf = xf[:half_n]
            magnitude = np.abs(yf[:half_n])
            
            magnitude = np.where(magnitude == 0, 1e-10, magnitude)  # Avoid log(0)
            
            response_db = 20 * np.log10(magnitude)
            max_db = np.max(response_db)
            response_db = response_db - max_db  # Normalize peak to 0dB
            
            self.ax.clear()
            self._style_axes()
            
            mask = (xf >= 20) & (xf <= 20000)
            
            self.ax.semilogx(xf[mask], response_db[mask], color='#0078d4', linewidth=1.5)
            self.ax.set_xlabel('Frequency (Hz)', fontsize=8)
            self.ax.set_ylabel('Amplitude (dB)', fontsize=8)
            self.ax.set_title('Frequency Response', color='#cccccc', fontsize=9)
            self.ax.set_ylim([-60, 5])
            self.ax.set_xlim([20, 20000])
            
            self.ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error plotting IR: {e}")
            self.clear_plot()

    def clear_plot(self):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, "Select an IR", ha='center', va='center', color='#555555')
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IR Tester - Impulse Response Tester")
        self.setMinimumSize(1000, 700)
        
        self.audio_engine = AudioEngine()
        self.convolution_processor = ConvolutionProcessor()
        self.convolution_worker = None
        
        self.header_raw_audio = None
        self.current_sample_rate = 44100
        self.equalizer_dialog = EqualizerDialog(self)
        self.equalizer_dialog.gains_changed.connect(self.update_equalization)
        self.equalizer_dialog.eq_toggled.connect(self.on_eq_toggled)
        
        self.ir_files = {}
        self.di_files = {}
        
        self.current_ir = None
        self.current_di = None
        self.is_playing = False
        self.is_looping = True
        self.convolution_worker = None
        self._preserve_position = False
        self._saved_position = 0
        self._was_playing = True
        self._last_mix_value = 100
        
        self.mix_debounce_timer = QTimer()
        self.mix_debounce_timer.setSingleShot(True)
        self.mix_debounce_timer.timeout.connect(self._on_mix_debounced)
        
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.setInterval(100)
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("🎸 IR Tester")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        ir_panel = self.create_ir_panel()
        splitter.addWidget(ir_panel)
        
        di_panel = self.create_di_panel()
        splitter.addWidget(di_panel)
        
        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter, 1)
        
        controls_frame = self.create_controls_panel()
        main_layout.addWidget(controls_frame)
        
        volume_frame = self.create_volume_panel()
        main_layout.addWidget(volume_frame)
        
    def create_ir_panel(self):
        group = QGroupBox("  Impulse Responses (IR)")
        layout = QVBoxLayout(group)
        
        btn_layout = QHBoxLayout()
        
        self.btn_add_ir = QPushButton(" ＋  Add")
        self.btn_add_ir.clicked.connect(lambda: self.open_unified_add_dialog(is_ir=True))
        self.btn_export_marked = QPushButton(" ➱  Export")
        self.btn_remove_ir = QPushButton(" ✕  Remove")
        self.btn_clear_ir = QPushButton(" ⟲  Clear")
        
        btn_layout.addWidget(self.btn_add_ir)
        btn_layout.addWidget(self.btn_export_marked)
        btn_layout.addWidget(self.btn_remove_ir)
        btn_layout.addWidget(self.btn_clear_ir)
        
        layout.addLayout(btn_layout)
        
        self.ir_tree = QTreeWidget()
        self.ir_tree.setHeaderHidden(True)
        self.ir_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.ir_tree)
        
        self.ir_info_label = QLabel("No IR selected")
        self.ir_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.ir_info_label)
        
        self.ir_plot_widget = IRPlotWidget()
        self.ir_plot_widget.setFixedHeight(180)
        layout.addWidget(self.ir_plot_widget)
        
        return group
        
    def create_di_panel(self):
        group = QGroupBox("  Direct Input (DI)")
        layout = QVBoxLayout(group)
        
        btn_layout = QHBoxLayout()
        
        self.btn_add_di = QPushButton(" ＋  Add")
        self.btn_add_di.clicked.connect(lambda: self.open_unified_add_dialog(is_ir=False))
        self.btn_remove_di = QPushButton(" ✕  Remove")
        self.btn_clear_di = QPushButton(" ⟲  Clear")
        
        btn_layout.addWidget(self.btn_add_di)
        btn_layout.addWidget(self.btn_remove_di)
        btn_layout.addWidget(self.btn_clear_di)
        
        layout.addLayout(btn_layout)
        
        self.di_tree = QTreeWidget()
        self.di_tree.setHeaderHidden(True)
        self.di_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.di_tree)
        
        self.di_info_label = QLabel("No DI selected")
        self.di_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.di_info_label)
        
        return group
        
    def create_controls_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        position_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00"))
        self.time_label.setMinimumWidth(50)
        position_layout.addWidget(self.time_label)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(1000)
        self.position_slider.setValue(0)
        position_layout.addWidget(self.position_slider)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setMinimumWidth(50)
        position_layout.addWidget(self.duration_label)
        
        layout.addLayout(position_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_rewind = QPushButton("⏪")
        self.btn_rewind.setToolTip("Rewind 5 seconds")
        self.btn_rewind.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_rewind)
        
        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setToolTip("Play/Pause")
        self.btn_play_pause.setMinimumSize(70, 50)
        self.btn_play_pause.setObjectName("primary_action")
        btn_layout.addWidget(self.btn_play_pause)
        
        self.btn_forward = QPushButton("⏩")
        self.btn_forward.setToolTip("Forward 5 seconds")
        self.btn_forward.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_forward)
        
        self.btn_loop = QPushButton("🔄")
        self.btn_loop.setToolTip("Loop (repeat)")
        self.btn_loop.setMinimumSize(50, 50)
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setObjectName("primary_action")
        btn_layout.addWidget(self.btn_loop)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return frame
        
    def create_volume_panel(self):
        frame = QFrame()
        layout = QHBoxLayout(frame)
        
        volume_label = QLabel("🔊 Volume:")
        layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(200)
        layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("80%")
        self.volume_label.setMinimumWidth(40)
        layout.addWidget(self.volume_label)
        
        self.btn_eq = QPushButton("Equalizer 🎚️")
        self.btn_eq.setToolTip("Open Graphic Equalizer")
        self.btn_eq.clicked.connect(self.equalizer_dialog.show)
        layout.addWidget(self.btn_eq)
        
        layout.addStretch()
        
        mix_label = QLabel("🎛️ Mix (Dry/Wet):")
        layout.addWidget(mix_label)
        
        self.mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.mix_slider.setMinimum(0)
        self.mix_slider.setMaximum(100)
        self.mix_slider.setValue(100)
        self.mix_slider.setMaximumWidth(200)
        layout.addWidget(self.mix_slider)
        
        self.mix_label = QLabel("100%")
        self.mix_label.setMinimumWidth(40)
        layout.addWidget(self.mix_label)

        self.btn_dry_wet = QPushButton("D/W")
        self.btn_dry_wet.setToolTip("Toggle between Dry (0%) and last Wet value")
        self.btn_dry_wet.setCheckable(True)
        self.btn_dry_wet.setChecked(True)
        self.btn_dry_wet.setMinimumWidth(60)
        self.btn_dry_wet.clicked.connect(self.toggle_dry_wet)
        layout.addWidget(self.btn_dry_wet)
        
        return frame
        
    def connect_signals(self):
        self.btn_export_marked.clicked.connect(self.export_marked_irs)
        self.btn_remove_ir.clicked.connect(self.remove_selected_ir)
        self.btn_clear_ir.clicked.connect(self.clear_ir_list)
        
        self.btn_remove_di.clicked.connect(self.remove_selected_di)
        self.btn_clear_di.clicked.connect(self.clear_di_list)
        
        self.ir_tree.currentItemChanged.connect(self.on_ir_selected)
        self.di_tree.currentItemChanged.connect(self.on_di_selected)
        
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_rewind.clicked.connect(self.rewind)
        self.btn_forward.clicked.connect(self.forward)
        
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.mix_slider.valueChanged.connect(self.on_mix_changed)
        self.position_slider.sliderPressed.connect(self.on_position_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_position_slider_released)
        
        self.btn_loop.toggled.connect(self.on_loop_toggled)
        
    def on_loop_toggled(self, checked):
        self.is_looping = checked
        
    def open_unified_add_dialog(self, is_ir=True):
        """Opens the universal dialog to add files and folders using modified QFileDialog"""
        dialog = QFileDialog(self, "Add IRs" if is_ir else "Add DIs")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        dialog.setNameFilters(["Audio files (*.wav *.mp3 *.flac *.aiff *.ogg)", "All files (*)"])
        
        # HACK: Allow selecting files AND folders simultaneously in Qt's dialog
        views = dialog.findChildren((QListView, QTreeView))
        for view in views:
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            paths = dialog.selectedFiles()
            self.process_added_paths(paths, is_ir)
            
    def process_added_paths(self, paths, is_ir=True):
        """Processes the list of added paths (files or folders)"""
        import os
        
        if is_ir:
            tree_widget = self.ir_tree
            file_dict = self.ir_files
        else:
            tree_widget = self.di_tree
            file_dict = self.di_files
            
        for path in paths:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in ['.wav', '.mp3', '.flac', '.aiff', '.ogg']:
                    if is_ir:
                        self.add_files_to_tree([path], self.ir_files, self.ir_tree)
                    else:
                        self.add_files_to_tree([path], self.di_files, self.di_tree)
            elif os.path.isdir(path):
                if is_ir:
                    self.add_folder_to_tree(path, self.ir_files, self.ir_tree)
                else:
                    self.add_folder_to_tree(path, self.di_files, self.di_tree)


            
    def add_files_to_tree(self, files, file_dict, tree_widget):
        """Adds individual files to the tree (without parent folder)"""
        import os
        tree_widget.setUpdatesEnabled(False)
        try:
            for filepath in files:
                filename = os.path.basename(filepath)
                key = f"_files_/{filename}"
                if key not in file_dict:
                    file_dict[key] = filepath
                    
                    loose_files_item = None
                    for i in range(tree_widget.topLevelItemCount()):
                        item = tree_widget.topLevelItem(i)
                        if item.data(0, Qt.ItemDataRole.UserRole) == "_loose_files_":
                            loose_files_item = item
                            break
                    
                    if loose_files_item is None:
                        loose_files_item = QTreeWidgetItem(tree_widget)
                        loose_files_item.setText(0, "📄 Loose Files")
                        loose_files_item.setData(0, Qt.ItemDataRole.UserRole, "_loose_files_")
                        loose_files_item.setExpanded(True)
                        loose_files_item.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    file_item = QTreeWidgetItem(loose_files_item)
                    file_item.setText(0, filename)
                    file_item.setData(0, Qt.ItemDataRole.UserRole, key)
                    file_item.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            tree_widget.setUpdatesEnabled(True)
                
    def add_folder_to_tree(self, folder, file_dict, tree_widget):
        """Adds an entire folder to the tree maintaining structure"""
        import os
        extensions = ('.wav', '.WAV', '.aiff', '.AIFF', '.flac', '.FLAC', '.mp3', '.MP3')
        
        folder_name = os.path.basename(folder)
        
        folder_item = QTreeWidgetItem(tree_widget)
        folder_item.setText(0, f"📂 {folder_name}")
        folder_item.setData(0, Qt.ItemDataRole.UserRole, f"_folder_:{folder}")
        folder_item.setExpanded(True)
        folder_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        tree_widget.setUpdatesEnabled(False)
        try:
            path_to_item = {"": folder_item}
            
            for root, dirs, files in os.walk(folder):
                dirs.sort()
                files.sort()
                
                rel_root = os.path.relpath(root, folder)
                if rel_root == ".":
                    rel_root = ""
                
                parent_item = path_to_item.get(rel_root, folder_item)
                
                for dirname in dirs:
                    if rel_root:
                        dir_path = os.path.join(rel_root, dirname)
                    else:
                        dir_path = dirname
                    
                    dir_item = QTreeWidgetItem(parent_item)
                    dir_item.setText(0, f"📁 {dirname}")
                    dir_item.setData(0, Qt.ItemDataRole.UserRole, f"_subfolder_:{dir_path}")
                    dir_item.setCheckState(0, Qt.CheckState.Unchecked)
                    path_to_item[dir_path] = dir_item
                
                for filename in files:
                    if filename.endswith(extensions):
                        filepath = os.path.join(root, filename)
                        
                        if rel_root:
                            key = f"{folder_name}/{rel_root}/{filename}"
                        else:
                            key = f"{folder_name}/{filename}"
                        
                        if key not in file_dict:
                            file_dict[key] = filepath
                            
                            file_item = QTreeWidgetItem(parent_item)
                            file_item.setText(0, filename)
                            file_item.setData(0, Qt.ItemDataRole.UserRole, key)
                            file_item.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            tree_widget.setUpdatesEnabled(True)
                        
    def export_marked_irs(self):
        """Exports checked IRs to a folder with optional normalization"""
        import os
        import shutil
        
        marked_files = []
        
        iterator = QTreeWidgetItemIterator(self.ir_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                key = item.data(0, Qt.ItemDataRole.UserRole)
                if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                    filepath = self.ir_files.get(key)
                    if filepath and os.path.exists(filepath):
                        marked_files.append(filepath)
            iterator += 1
            
        if not marked_files:
            QMessageBox.information(self, "Export", "No files selected for export.")
            return
        
        # Show export options dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Options")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)
        
        normalize_check = QCheckBox("Normalize IRs (equalize volume levels)"))
        normalize_check.setChecked(False)
        layout.addWidget(normalize_check)
        
        norm_type_layout = QHBoxLayout()
        norm_type_label = QLabel("Normalization type:")
        norm_type_combo = QComboBox()
        norm_type_combo.addItem("Peak (0 dB)", "peak")
        norm_type_combo.addItem("RMS (perceived loudness)", "rms")
        norm_type_combo.setEnabled(False)
        norm_type_layout.addWidget(norm_type_label)
        norm_type_layout.addWidget(norm_type_combo)
        layout.addLayout(norm_type_layout)
        
        target_layout = QHBoxLayout()
        target_label = QLabel("Target RMS (dB):")
        target_spin = QSpinBox()
        target_spin.setRange(-30, -6)
        target_spin.setValue(-18)
        target_spin.setEnabled(False)
        target_layout.addWidget(target_label)
        target_layout.addWidget(target_spin)
        layout.addLayout(target_layout)
        
        info_label = QLabel(f"{len(marked_files)} file(s) selected for export")
        info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info_label)
        
        def on_normalize_changed(state):
            enabled = state == Qt.CheckState.Checked.value
            norm_type_combo.setEnabled(enabled)
            target_spin.setEnabled(enabled and norm_type_combo.currentData() == "rms")
        
        def on_norm_type_changed(index):
            target_spin.setEnabled(norm_type_combo.currentData() == "rms")
        
        normalize_check.stateChanged.connect(on_normalize_changed)
        norm_type_combo.currentIndexChanged.connect(on_norm_type_changed)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        dest_folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not dest_folder:
            return
        
        do_normalize = normalize_check.isChecked()
        norm_type = norm_type_combo.currentData()
        target_rms_db = target_spin.value()
            
        success_count = 0
        error_count = 0
        
        progress = QProgressBar(self)
        progress.setWindowTitle("Exporting...")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimum(0)
        progress.setMaximum(len(marked_files))
        progress.show()
        
        for i, src_path in enumerate(marked_files):
            try:
                filename = os.path.basename(src_path)
                dst_path = os.path.join(dest_folder, filename)
                
                if os.path.exists(dst_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dst_path):
                        dst_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                        counter += 1
                
                if do_normalize:
                    self._export_normalized_ir(src_path, dst_path, norm_type, target_rms_db)
                else:
                    shutil.copy2(src_path, dst_path)
                    
                success_count += 1
            except Exception as e:
                print(f"Error processing {src_path}: {e}")
                error_count += 1
            
            progress.setValue(i + 1)
            QApplication.processEvents()
            
        progress.close()
        
        msg = f"Export complete!\n\n{success_count} files exported successfully."
        if do_normalize:
            msg += f"\n\nNormalization: {norm_type.upper()}"
            if norm_type == "rms":
                msg += f" (target: {target_rms_db} dB)"
        if error_count > 0:
            msg += f"\n{error_count} errors."
            
        QMessageBox.information(self, "Export", msg)
    
    def _export_normalized_ir(self, src_path, dst_path, norm_type, target_rms_db):
        """Normalizes and exports a single IR file"""
        data, sample_rate = sf.read(src_path, dtype='float32')
        
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        
        if norm_type == "peak":
            peak = np.max(np.abs(data))
            if peak > 0:
                data = data / peak
        else:
            rms = np.sqrt(np.mean(data ** 2))
            if rms > 0:
                target_rms = 10 ** (target_rms_db / 20)
                scale = target_rms / rms
                data = data * scale
                
                peak = np.max(np.abs(data))
                if peak > 0.99:
                    data = data * (0.99 / peak)  # Prevent clipping
        
        info = sf.info(src_path)
        subtype = info.subtype
        
        sf.write(dst_path, data, sample_rate, subtype=subtype)

    def remove_selected_ir(self):
        self.remove_checked_items(self.ir_tree, self.ir_files)
        
    def remove_selected_di(self):
        self.remove_checked_items(self.di_tree, self.di_files)
        
    def remove_checked_items(self, tree_widget, file_dict):
        """Removes checked items (checkbox) or selected item if nothing is checked"""
        items_to_remove = []
        has_checked_items = False
        
        iterator = QTreeWidgetItemIterator(tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                has_checked_items = True
                items_to_remove.append(item)
            iterator += 1
            
        if not has_checked_items:
            current = tree_widget.currentItem()
            if current:
                items_to_remove.append(current)
        
        if not items_to_remove:
            return
            
        for item in items_to_remove:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key:
                if key.startswith("_folder_:") or key.startswith("_subfolder_:") or key == "_loose_files_":
                    self._remove_folder_content_from_dict(item, file_dict)
                else:
                    if key in file_dict:
                        del file_dict[key]
        
        for item in items_to_remove:
            try:
                parent = item.parent()
                if parent:
                    parent.removeChild(item)
                else:
                    index = tree_widget.indexOfTopLevelItem(item)
                    if index != -1:
                        tree_widget.takeTopLevelItem(index)
            except RuntimeError:
                pass

    def _remove_folder_content_from_dict(self, folder_item, file_dict):
        """Recursively removes all files from a folder from the dictionary"""""
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            key = child.data(0, Qt.ItemDataRole.UserRole)
            if key:
                if not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                    if key in file_dict:
                        del file_dict[key]
                else:
                    self._remove_folder_content_from_dict(child, file_dict)


            
    def clear_ir_list(self):
        self.ir_files.clear()
        self.ir_tree.clear()
        self.current_ir = None
        self.ir_info_label.setText("No IR selected")
        
    def clear_di_list(self):
        self.di_files.clear()
        self.di_tree.clear()
        self.current_di = None
        self.di_info_label.setText("No DI selected")
        
    def on_ir_selected(self, current, previous):
        if current:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                filepath = self.ir_files.get(key)
                if filepath:
                    self.current_ir = filepath
                    info = self.convolution_processor.load_ir(filepath)
                    self.ir_info_label.setText(f"✓ {info}")
                    self.ir_plot_widget.plot_ir(filepath)
                    self.process_and_play(preserve_position=True)
            else:
                self.ir_plot_widget.clear_plot()
        else:
            self.ir_info_label.setText("No IR selected")
            self.ir_plot_widget.clear_plot()
            
    def on_di_selected(self, current, previous):
        if current:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                filepath = self.di_files.get(key)
                if filepath:
                    self.current_di = filepath
                    info = self.convolution_processor.load_di(filepath)
                    self.di_info_label.setText(f"✓ {info}")
                    self.process_and_play()
        else:
            self.di_info_label.setText("No DI selected")
            
    def process_and_play(self, preserve_position=False):
        if self.current_ir and self.current_di:
            self._preserve_position = preserve_position
            if preserve_position and self.audio_engine.has_audio():
                self._saved_position = self.audio_engine.get_position()
                self._was_playing = self.is_playing
            else:
                self._saved_position = 0
                self._was_playing = True
            
            if self.convolution_worker is not None and self.convolution_worker.isRunning():
                self.convolution_worker.terminate()
                self.convolution_worker.wait()
            
            wet_mix = self.mix_slider.value() / 100.0
            self.convolution_worker = ConvolutionWorker(self.convolution_processor, wet_mix)
            self.convolution_worker.finished.connect(self.on_convolution_finished)
            self.convolution_worker.error.connect(self.on_convolution_error)
            self.convolution_worker.start()
        
    def on_convolution_finished(self, audio_data, sample_rate):
        try:
            self.audio_engine.stop()
            self.audio_engine.load_audio(audio_data, sample_rate)
            
            self.header_raw_audio = audio_data
            self.current_sample_rate = sample_rate
            
            self.update_equalization(self.equalizer_dialog.current_gains)
            
            duration = len(audio_data) / sample_rate
            self.duration_label.setText(self.format_time(duration))
            
            if self._preserve_position and self._saved_position > 0:
                seek_pos = min(self._saved_position, duration - 0.1)
                if seek_pos > 0:
                    self.audio_engine.seek(seek_pos)
            
            volume = self.volume_slider.value() / 100.0
            self.audio_engine.set_volume(volume)
            
            if self._was_playing:
                self.audio_engine.play()
                self.is_playing = True
                self.btn_play_pause.setText("⏸")
                self.position_timer.start()
            else:
                self.is_playing = False
                self.btn_play_pause.setText("▶")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error playing: {str(e)}")
            
    def on_convolution_error(self, error_msg):
        QMessageBox.warning(self, "Error", f"Error processing: {error_msg}")
                
    def toggle_play_pause(self):
        if self.audio_engine.has_audio():
            if self.is_playing:
                self.audio_engine.pause()
                self.is_playing = False
                self.btn_play_pause.setText("▶")
                self.position_timer.stop()
            else:
                self.audio_engine.resume()
                self.is_playing = True
                self.btn_play_pause.setText("⏸")
                self.position_timer.start()
                
    def stop_playback(self):
        self.audio_engine.stop()
        self.is_playing = False
        self.btn_play_pause.setText("▶")
        self.position_slider.setValue(0)
        self.time_label.setText("00:00")
        self.position_timer.stop()
        
    def rewind(self):
        if self.audio_engine.has_audio():
            self.audio_engine.seek_relative(-5.0)
            self.update_position()
            
    def forward(self):
        if self.audio_engine.has_audio():
            self.audio_engine.seek_relative(5.0)
            self.update_position()
            
    def update_position(self):
        if self.audio_engine.has_audio():
            position = self.audio_engine.get_position()
            duration = self.audio_engine.get_duration()
            
            if duration > 0:
                slider_pos = int((position / duration) * 1000)
                self.position_slider.blockSignals(True)
                self.position_slider.setValue(slider_pos)
                self.position_slider.blockSignals(False)
                
            self.time_label.setText(self.format_time(position))
            
            if not self.audio_engine.is_playing() and self.is_playing:
                if self.is_looping:
                    self.audio_engine.seek(0)
                    self.audio_engine.play()
                else:
                    self.is_playing = False
                    self.btn_play_pause.setText("▶")
                    self.position_timer.stop()
                
    def on_position_slider_pressed(self):
        self.position_timer.stop()
        
    def on_position_slider_released(self):
        if self.audio_engine.has_audio():
            duration = self.audio_engine.get_duration()
            position = (self.position_slider.value() / 1000.0) * duration
            self.audio_engine.seek(position)
            if self.is_playing:
                self.position_timer.start()
                
    def on_volume_changed(self, value):
        self.volume_label.setText(f"{value}%")
        self.audio_engine.set_volume(value / 100.0)
        
    def on_mix_changed(self, value):
        self.mix_label.setText(f"{value}%")
        self.mix_debounce_timer.stop()
        self.mix_debounce_timer.start(300)
        
    def _on_mix_debounced(self):
        """Called after the mix slider stops being moved"""
        if self.current_ir and self.current_di:
            self.process_and_play(preserve_position=True)
                    
    def toggle_dry_wet(self):
        current_val = self.mix_slider.value()
        
        if current_val > 0:
            self._last_mix_value = current_val
            self.mix_slider.setValue(0)
            self.btn_dry_wet.setChecked(False)
        else:
            target = self._last_mix_value if self._last_mix_value > 0 else 100
            self.mix_slider.setValue(target)
            self.btn_dry_wet.setChecked(True)

    def update_equalization(self, gains):
        """Applies equalization to current raw audio and updates the engine"""
        if not self.equalizer_dialog.btn_enable.isChecked() or self.header_raw_audio is None:
            return
            
        try:
            processed_audio = Equalizer.process_frame(
                self.header_raw_audio, 
                self.current_sample_rate, 
                gains
            )
            
            self.audio_engine.update_audio(processed_audio)
            
        except Exception as e:
            print(f"Error in equalization: {e}")
            
    def on_eq_toggled(self, enabled: bool):
        """Called when the enable/disable EQ checkbox is changed"""
        if self.header_raw_audio is None:
            return
            
        if enabled:
            self.update_equalization(self.equalizer_dialog.current_gains)
        else:
            self.audio_engine.update_audio(self.header_raw_audio)

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
        
    def closeEvent(self, event):
        self.audio_engine.stop()
        self.position_timer.stop()
        if self.convolution_worker is not None and self.convolution_worker.isRunning():
            self.convolution_worker.terminate()
            self.convolution_worker.wait()
        event.accept()
