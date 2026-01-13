"""
Main Window for the IR Tester application
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSlider, QGroupBox,
    QDialog, QTreeView, QAbstractItemView, QHeaderView, QListView,
    QSplitter, QFrame, QMessageBox, QProgressBar, QTreeWidgetItemIterator, QApplication, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QDir
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtWidgets import QMenu, QStyle

# Matplotlib Imports
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
        
        # Dark style for matplotlib to match the UI
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor='#1e1e1e')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        
        # Initial empty plot styling
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
            # Ler áudio
            data, samplerate = sf.read(file_path)
            
            # If stereo, mix down to mono for visualization
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            # FFT
            n = len(data)
            yf = scipy.fft.fft(data)
            xf = scipy.fft.fftfreq(n, 1 / samplerate)
            
            # Pega apenas a metade positiva do espectro
            half_n = n // 2
            xf = xf[:half_n]
            magnitude = np.abs(yf[:half_n])
            
            # Evita log de zero
            magnitude = np.where(magnitude == 0, 1e-10, magnitude)
            
            # Converte para dB e normaliza (pico em 0dB)
            response_db = 20 * np.log10(magnitude)
            max_db = np.max(response_db)
            response_db = response_db - max_db
            
            # Plot
            self.ax.clear()
            self._style_axes()
            
            # Filter for 20Hz - 20kHz
            mask = (xf >= 20) & (xf <= 20000)
            
            self.ax.semilogx(xf[mask], response_db[mask], color='#0078d4', linewidth=1.5)
            self.ax.set_xlabel('Frequency (Hz)', fontsize=8)
            self.ax.set_ylabel('Amplitude (dB)', fontsize=8)
            self.ax.set_title('Frequency Response', color='#cccccc', fontsize=9)
            self.ax.set_ylim([-60, 5]) # Limit Y axis to focus on useful range
            self.ax.set_xlim([20, 20000])
            
            # Convert X axis ticks to readable Hz
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
        
        # Initialize audio components
        self.audio_engine = AudioEngine()
        self.convolution_processor = ConvolutionProcessor()
        self.convolution_worker = None
        
        # State for Equalizer
        self.header_raw_audio = None # Stores audio without EQ for processing
        self.current_sample_rate = 44100
        self.equalizer_dialog = EqualizerDialog(self)
        self.equalizer_dialog.gains_changed.connect(self.update_equalization)
        self.equalizer_dialog.eq_toggled.connect(self.on_eq_toggled)
        
        # File lists
        self.ir_files = {}  # {display_name: full_path}
        self.di_files = {}  # {display_name: full_path}
        
        # Current state
        self.current_ir = None
        self.current_di = None
        self.is_playing = False
        self.is_looping = True  # Loop active by default
        self.convolution_worker = None
        self._preserve_position = False
        self._saved_position = 0
        self._was_playing = True
        self._last_mix_value = 100  # Valor padrao para o toggle
        
        # Timer for mix slider debounce
        self.mix_debounce_timer = QTimer()
        self.mix_debounce_timer.setSingleShot(True)
        self.mix_debounce_timer.timeout.connect(self._on_mix_debounced)
        
        # Timer to update position
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
        
        # Title
        title_label = QLabel("🎸 IR Tester")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Main area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # IR Panel
        ir_panel = self.create_ir_panel()
        splitter.addWidget(ir_panel)
        
        # DI Panel
        di_panel = self.create_di_panel()
        splitter.addWidget(di_panel)
        
        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter, 1)
        
        # Progress bar for convolution (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Processing... %p%")
        main_layout.addWidget(self.progress_bar)
        
        # Playback controls
        controls_frame = self.create_controls_panel()
        main_layout.addWidget(controls_frame)
        
        # Volume control
        volume_frame = self.create_volume_panel()
        main_layout.addWidget(volume_frame)
        
    def create_ir_panel(self):
        group = QGroupBox("  Impulse Responses (IR)")
        layout = QVBoxLayout(group)
        
        # Control buttons
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
        
        # IR Tree
        self.ir_tree = QTreeWidget()
        self.ir_tree.setHeaderHidden(True)
        self.ir_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.ir_tree)
        
        # Selected IR info
        self.ir_info_label = QLabel("No IR selected")
        self.ir_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.ir_info_label)
        
        # Frequency Graph
        self.ir_plot_widget = IRPlotWidget()
        self.ir_plot_widget.setFixedHeight(180) # Fixed height to not take too much space
        layout.addWidget(self.ir_plot_widget)
        
        return group
        
    def create_di_panel(self):
        group = QGroupBox("  Direct Input (DI)")
        layout = QVBoxLayout(group)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add_di = QPushButton(" ＋  Add")
        self.btn_add_di.clicked.connect(lambda: self.open_unified_add_dialog(is_ir=False))
        self.btn_remove_di = QPushButton(" ✕  Remove")
        self.btn_clear_di = QPushButton(" ⟲  Clear")
        
        btn_layout.addWidget(self.btn_add_di)
        btn_layout.addWidget(self.btn_remove_di)
        btn_layout.addWidget(self.btn_clear_di)
        
        layout.addLayout(btn_layout)
        
        # DI Tree
        self.di_tree = QTreeWidget()
        self.di_tree.setHeaderHidden(True)
        self.di_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.di_tree)
        
        # Selected DI info
        self.di_info_label = QLabel("No DI selected")
        self.di_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.di_info_label)
        
        return group
        
    def create_controls_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        # Position slider
        position_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
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
        
        # Control buttons
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
        
        # Loop button (active by default)
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
        
        # Equalizer Button
        self.btn_eq = QPushButton("Equalizer 🎚️")
        self.btn_eq.setToolTip("Open Graphic Equalizer")
        self.btn_eq.clicked.connect(self.equalizer_dialog.show)
        layout.addWidget(self.btn_eq)
        
        layout.addStretch()
        
        # Mix Dry/Wet
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

        # Dry/Wet Toggle Button
        self.btn_dry_wet = QPushButton("D/W")
        self.btn_dry_wet.setToolTip("Toggle between Dry (0%) and last Wet value")
        self.btn_dry_wet.setCheckable(True)
        self.btn_dry_wet.setChecked(True)
        self.btn_dry_wet.setMinimumWidth(60)
        self.btn_dry_wet.clicked.connect(self.toggle_dry_wet)
        layout.addWidget(self.btn_dry_wet)
        
        return frame
        
    def connect_signals(self):
        # IR Buttons
        # self.btn_add_ir and self.btn_add_ir_menu are connected via menu/actions
        self.btn_export_marked.clicked.connect(self.export_marked_irs)
        self.btn_remove_ir.clicked.connect(self.remove_selected_ir)
        self.btn_clear_ir.clicked.connect(self.clear_ir_list)
        
        # DI Buttons
        # Connections via menu
        self.btn_remove_di.clicked.connect(self.remove_selected_di)
        self.btn_clear_di.clicked.connect(self.clear_di_list)
        
        # File selection (tree)
        self.ir_tree.currentItemChanged.connect(self.on_ir_selected)
        self.di_tree.currentItemChanged.connect(self.on_di_selected)
        
        # Controles de reprodução
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_rewind.clicked.connect(self.rewind)
        self.btn_forward.clicked.connect(self.forward)
        
        # Sliders
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.mix_slider.valueChanged.connect(self.on_mix_changed)
        self.position_slider.sliderPressed.connect(self.on_position_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_position_slider_released)
        
        # Loop
        self.btn_loop.toggled.connect(self.on_loop_toggled)
        
    def on_loop_toggled(self, checked):
        self.is_looping = checked
        
    def open_unified_add_dialog(self, is_ir=True):
        """Opens the universal dialog to add files and folders using modified QFileDialog"""
        dialog = QFileDialog(self, "Add IRs" if is_ir else "Add DIs")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        # Set filters
        dialog.setNameFilters(["Audio files (*.wav *.mp3 *.flac *.aiff *.ogg)", "All files (*)"])
        
        # HACK: Find internal views (ListView and TreeView) and allow multi-selection
        # This allows selecting files AND folders at the same time in Qt's interface
        views = dialog.findChildren((QListView, QTreeView))
        for view in views:
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            paths = dialog.selectedFiles()
            self.process_added_paths(paths, is_ir)
            
    def process_added_paths(self, paths, is_ir=True):
        """Processes the list of added paths (files or folders)"""
        import os
        
        # Define which data set to use
        # Define which data set to use
        if is_ir:
            tree_widget = self.ir_tree
            file_dict = self.ir_files
        else:
            tree_widget = self.di_tree
            file_dict = self.di_files
            
        # Processa cada caminho
        for path in paths:
            if os.path.isfile(path):
                # Se for arquivo, verifica extensão
                ext = os.path.splitext(path)[1].lower()
                if ext in ['.wav', '.mp3', '.flac', '.aiff', '.ogg']:
                    if is_ir:
                        self.add_files_to_tree([path], self.ir_files, self.ir_tree)
                    else:
                        self.add_files_to_tree([path], self.di_files, self.di_tree)
            elif os.path.isdir(path):
                # Se for pasta, adiciona recursivamente
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
                # Cria uma chave única para o arquivo
                key = f"_files_/{filename}"
                if key not in file_dict:
                    file_dict[key] = filepath
                    
                    # Search for or create "Loose Files" item
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
                    
                    # Adiciona o arquivo como filho
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
        
        # Cria o item raiz da pasta
        folder_item = QTreeWidgetItem(tree_widget)
        folder_item.setText(0, f"📂 {folder_name}")
        folder_item.setData(0, Qt.ItemDataRole.UserRole, f"_folder_:{folder}")
        folder_item.setExpanded(True)
        folder_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        tree_widget.setUpdatesEnabled(False)
        try:
            # Dicionário para mapear caminhos relativos para itens da árvore
            path_to_item = {"": folder_item}
            
            for root, dirs, files in os.walk(folder):
                # Sort directories and files
                dirs.sort()
                files.sort()
                
                rel_root = os.path.relpath(root, folder)
                if rel_root == ".":
                    rel_root = ""
                
                # Obtém o item pai para este diretório
                parent_item = path_to_item.get(rel_root, folder_item)
                
                # Cria itens para subpastas
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
                
                # Add files
                for filename in files:
                    if filename.endswith(extensions):
                        filepath = os.path.join(root, filename)
                        
                        # Cria chave única: pasta_raiz/caminho_relativo
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
        """Exports checked IRs to a folder"""
        import os
        import shutil
        
        # Collect checked files
        marked_files = []
        
        # Iterate through all tree items
        iterator = QTreeWidgetItemIterator(self.ir_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                key = item.data(0, Qt.ItemDataRole.UserRole)
                # Verifica se é um arquivo (e não pasta)
                if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                    filepath = self.ir_files.get(key)
                    if filepath and os.path.exists(filepath):
                        marked_files.append(filepath)
            iterator += 1
            
        if not marked_files:
            QMessageBox.information(self, "Export", "No files selected for export.")
            return
            
        # Select destination folder
        dest_folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not dest_folder:
            return
            
        # Copy files
        success_count = 0
        error_count = 0
        
        # Progress bar for copying
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
                
                # If file already exists, add numeric suffix
                if os.path.exists(dst_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dst_path):
                        dst_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                        counter += 1
                
                shutil.copy2(src_path, dst_path)
                success_count += 1
            except Exception as e:
                print(f"Error copying {src_path}: {e}")
                error_count += 1
            
            progress.setValue(i + 1)
            QApplication.processEvents()
            
        progress.close()
        
        msg = f"Export complete!\n\n{success_count} files copied successfully."
        if error_count > 0:
            msg += f"\n{error_count} errors."
            
        QMessageBox.information(self, "Export", msg)

    def remove_selected_ir(self):
        self.remove_checked_items(self.ir_tree, self.ir_files)
        
    def remove_selected_di(self):
        self.remove_checked_items(self.di_tree, self.di_files)
        
    def remove_checked_items(self, tree_widget, file_dict):
        """Removes checked items (checkbox) or selected item if nothing is checked"""
        items_to_remove = []
        has_checked_items = False
        
        # First, check if there are checked items
        iterator = QTreeWidgetItemIterator(tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                has_checked_items = True
                # Adiciona apenas itens de nível superior na seleção para evitar problemas ao remover pais e filhos
                # Mas aqui precisamos ser cuidadosos. Vamos coletar todos e processar depois.
                items_to_remove.append(item)
            iterator += 1
            
        # If no items are checked, use current selection (legacy behavior)
        if not has_checked_items:
            current = tree_widget.currentItem()
            if current:
                items_to_remove.append(current)
        
        if not items_to_remove:
            return
            
        # Process removal
        # To remove correctly, we need to clear the file dictionary first
        for item in items_to_remove:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key:
                if key.startswith("_folder_:") or key.startswith("_subfolder_:") or key == "_loose_files_":
                    # It's a folder, remove recursively from dictionary
                    self._remove_folder_content_from_dict(item, file_dict)
                else:
                    # It's a file
                    if key in file_dict:
                        del file_dict[key]
        
        # Agora remove os itens da árvore
        # É seguro remover itens se fizermos isso com cuidado (ex: reiniciando a iteração ou algo assim)
        # Mas itens_to_remove pode conter filhos de itens que também estão na lista.
        # O ideal é remover apenas os itens "mais altos" da hierarquia de remoção.
        
        # Simples: removemos item por item. Se o pai já foi removido, o filho já foi junto (Qt cuida disso).
        # Mas precisamos garantir que não tentamos remover um item que já foi deletado (pq o pai foi deletado).
        
        # Vamos fazer seguro: coletar chaves removidas e recarregar a árvore? Não, muito pesado.
        # Vamos apenas deletar da árvore. Se der erro, ignoramos.
        
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
                # Item já deletado
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
            # Ignora se for uma pasta
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                filepath = self.ir_files.get(key)
                if filepath:
                    self.current_ir = filepath
                    info = self.convolution_processor.load_ir(filepath)
                    self.ir_info_label.setText(f"✓ {info}")
                    # Atualiza gráfico
                    self.ir_plot_widget.plot_ir(filepath)
                    # Preserve position when changing IR
                    self.process_and_play(preserve_position=True)
            else:
                # It's a folder, clear the graph
                self.ir_plot_widget.clear_plot()
        else:
            self.ir_info_label.setText("No IR selected")
            self.ir_plot_widget.clear_plot()
            
    def on_di_selected(self, current, previous):
        if current:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            # Ignora se for uma pasta
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                filepath = self.di_files.get(key)
                if filepath:
                    self.current_di = filepath
                    info = self.convolution_processor.load_di(filepath)
                    self.di_info_label.setText(f"✓ {info}")
                    self.process_and_play()
            else:
                # It's a folder, do nothing
                pass
        else:
            self.di_info_label.setText("No DI selected")
            
    def process_and_play(self, preserve_position=False):
        if self.current_ir and self.current_di:
            # Save current position if needed
            self._preserve_position = preserve_position
            if preserve_position and self.audio_engine.has_audio():
                self._saved_position = self.audio_engine.get_position()
                self._was_playing = self.is_playing
            else:
                self._saved_position = 0
                self._was_playing = True  # Start playback by default
            
            # Cancel previous worker if exists
            if self.convolution_worker is not None and self.convolution_worker.isRunning():
                self.convolution_worker.terminate()
                self.convolution_worker.wait()
            
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            
            # Cria e inicia o worker
            wet_mix = self.mix_slider.value() / 100.0
            self.convolution_worker = ConvolutionWorker(self.convolution_processor, wet_mix)
            self.convolution_worker.finished.connect(self.on_convolution_finished)
            self.convolution_worker.error.connect(self.on_convolution_error)
            self.convolution_worker.progress.connect(self.on_convolution_progress)
            self.convolution_worker.start()
        else:
            pass  # No action needed when IR or DI are not selected
                
    def on_convolution_progress(self, value):
        self.progress_bar.setValue(value)
        
    def on_convolution_finished(self, audio_data, sample_rate):
        self.progress_bar.setVisible(False)
        
        try:
            # Stop current playback
            self.audio_engine.stop()
            
            # Load new audio (to set sample_rate and initialize)
            self.audio_engine.load_audio(audio_data, sample_rate)
            
            # Store raw audio for reprocessing (EQ)
            self.header_raw_audio = audio_data
            self.current_sample_rate = sample_rate
            
            # Apply initial EQ (or flat if all zero)
            # This will overwrite the engine buffer via update_audio
            self.update_equalization(self.equalizer_dialog.current_gains)
            
            # Update duration
            duration = len(audio_data) / sample_rate
            self.duration_label.setText(self.format_time(duration))
            
            # Restore position if preserving
            if self._preserve_position and self._saved_position > 0:
                # Ensure position doesn't exceed new audio duration
                seek_pos = min(self._saved_position, duration - 0.1)
                if seek_pos > 0:
                    self.audio_engine.seek(seek_pos)
            
            # Start playback only if it was playing before or it's a new selection
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
        self.progress_bar.setVisible(False)
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
            
            # Check if finished
            if not self.audio_engine.is_playing() and self.is_playing:
                if self.is_looping:
                    # Restart from beginning
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
        # Use debounce to avoid reprocessing on every slider movement
        # Only process after 300ms without movement
        self.mix_debounce_timer.stop()
        self.mix_debounce_timer.start(300)
        
    def _on_mix_debounced(self):
        """Called after the mix slider stops being moved"""
        if self.current_ir and self.current_di:
            self.process_and_play(preserve_position=True)
                    
    def toggle_dry_wet(self):
        current_val = self.mix_slider.value()
        
        if current_val > 0:
            # Going to Dry
            self._last_mix_value = current_val
            self.mix_slider.setValue(0)
            self.btn_dry_wet.setChecked(False)
        else:
            # Going back to Wet
            target = self._last_mix_value if self._last_mix_value > 0 else 100
            self.mix_slider.setValue(target)
            self.btn_dry_wet.setChecked(True)

    def update_equalization(self, gains):
        """Applies equalization to current raw audio and updates the engine"""
        # If EQ is disabled or no audio, ignore
        if not self.equalizer_dialog.btn_enable.isChecked() or self.header_raw_audio is None:
            return
            
        try:
            # Processa o áudio raw com os ganhos atuais
            processed_audio = Equalizer.process_frame(
                self.header_raw_audio, 
                self.current_sample_rate, 
                gains
            )
            
            # Update audio engine (hot-swap)
            self.audio_engine.update_audio(processed_audio)
            
        except Exception as e:
            print(f"Error in equalization: {e}")
            
    def on_eq_toggled(self, enabled: bool):
        """Called when the enable/disable EQ checkbox is changed"""
        if self.header_raw_audio is None:
            return
            
        if enabled:
            # Re-apply current equalization
            self.update_equalization(self.equalizer_dialog.current_gains)
        else:
            # Bypass: load original (raw) audio
            print("EQ Bypass: Loading original audio")
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
