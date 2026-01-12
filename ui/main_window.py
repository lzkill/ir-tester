"""
Main Window da aplicação IR Tester
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QSlider, QGroupBox,
    QFileDialog, QSplitter, QFrame, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

from audio.audio_engine import AudioEngine
from audio.convolution import ConvolutionProcessor
from audio.convolution_worker import ConvolutionWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IR Tester - Impulse Response Tester")
        self.setMinimumSize(1000, 700)
        
        # Inicializa os componentes de áudio
        self.audio_engine = AudioEngine()
        self.convolution_processor = ConvolutionProcessor()
        
        # Listas de arquivos
        self.ir_files = {}  # {display_name: full_path}
        self.di_files = {}  # {display_name: full_path}
        
        # Estado atual
        self.current_ir = None
        self.current_di = None
        self.is_playing = False
        self.is_looping = True  # Loop ativo por padrão
        self.convolution_worker = None
        self._preserve_position = False
        self._saved_position = 0
        self._was_playing = True
        
        # Timer para debounce do mix slider
        self.mix_debounce_timer = QTimer()
        self.mix_debounce_timer.setSingleShot(True)
        self.mix_debounce_timer.timeout.connect(self._on_mix_debounced)
        
        # Timer para atualizar a posição
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
        
        # Título
        title_label = QLabel("🎸 IR Tester")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Área principal com splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Painel de IRs
        ir_panel = self.create_ir_panel()
        splitter.addWidget(ir_panel)
        
        # Painel de DIs
        di_panel = self.create_di_panel()
        splitter.addWidget(di_panel)
        
        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter, 1)
        
        # Barra de progresso para convolução (oculta por padrão)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Processando... %p%")
        main_layout.addWidget(self.progress_bar)
        
        # Controles de reprodução
        controls_frame = self.create_controls_panel()
        main_layout.addWidget(controls_frame)
        
        # Controle de volume
        volume_frame = self.create_volume_panel()
        main_layout.addWidget(volume_frame)
        
    def create_ir_panel(self):
        group = QGroupBox("  Impulse Responses (IR)")
        layout = QVBoxLayout(group)
        
        # Botões de controle
        btn_layout = QHBoxLayout()
        
        self.btn_add_ir = QPushButton(" ＋  Arquivo")
        self.btn_add_ir_folder = QPushButton(" 📁  Pasta")
        self.btn_remove_ir = QPushButton(" ✕  Remover")
        self.btn_clear_ir = QPushButton(" ⟲  Limpar")
        
        btn_layout.addWidget(self.btn_add_ir)
        btn_layout.addWidget(self.btn_add_ir_folder)
        btn_layout.addWidget(self.btn_remove_ir)
        btn_layout.addWidget(self.btn_clear_ir)
        
        layout.addLayout(btn_layout)
        
        # Árvore de IRs
        self.ir_tree = QTreeWidget()
        self.ir_tree.setHeaderHidden(True)
        self.ir_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.ir_tree)
        
        # Info do IR selecionado
        self.ir_info_label = QLabel("Nenhum IR selecionado")
        self.ir_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.ir_info_label)
        
        return group
        
    def create_di_panel(self):
        group = QGroupBox("  Direct Input (DI)")
        layout = QVBoxLayout(group)
        
        # Botões de controle
        btn_layout = QHBoxLayout()
        
        self.btn_add_di = QPushButton(" ＋  Arquivo")
        self.btn_add_di_folder = QPushButton(" 📁  Pasta")
        self.btn_remove_di = QPushButton(" ✕  Remover")
        self.btn_clear_di = QPushButton(" ⟲  Limpar")
        
        btn_layout.addWidget(self.btn_add_di)
        btn_layout.addWidget(self.btn_add_di_folder)
        btn_layout.addWidget(self.btn_remove_di)
        btn_layout.addWidget(self.btn_clear_di)
        
        layout.addLayout(btn_layout)
        
        # Árvore de DIs
        self.di_tree = QTreeWidget()
        self.di_tree.setHeaderHidden(True)
        self.di_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.di_tree)
        
        # Info do DI selecionado
        self.di_info_label = QLabel("Nenhum DI selecionado")
        self.di_info_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.di_info_label)
        
        return group
        
    def create_controls_panel(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        # Slider de posição
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
        
        # Botões de controle
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_rewind = QPushButton("⏪")
        self.btn_rewind.setToolTip("Retroceder 5 segundos")
        self.btn_rewind.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_rewind)
        
        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setToolTip("Parar")
        self.btn_stop.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setToolTip("Play/Pause")
        self.btn_play_pause.setMinimumSize(70, 50)
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
        """)
        btn_layout.addWidget(self.btn_play_pause)
        
        self.btn_forward = QPushButton("⏩")
        self.btn_forward.setToolTip("Avançar 5 segundos")
        self.btn_forward.setMinimumSize(50, 50)
        btn_layout.addWidget(self.btn_forward)
        
        # Botão de loop (ativo por padrão)
        self.btn_loop = QPushButton("🔄")
        self.btn_loop.setToolTip("Loop (repetir)")
        self.btn_loop.setMinimumSize(50, 50)
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                font-size: 18px;
            }
            QPushButton:checked {
                background-color: #107c10;
            }
            QPushButton:!checked {
                background-color: #4d4d4d;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
        """)
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
        
        layout.addStretch()
        
        # Mix Dry/Wet
        mix_label = QLabel("� Mix (Dry/Wet):")
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
        
        return frame
        
    def connect_signals(self):
        # Botões de IR
        self.btn_add_ir.clicked.connect(self.add_ir_files)
        self.btn_add_ir_folder.clicked.connect(self.add_ir_folder)
        self.btn_remove_ir.clicked.connect(self.remove_selected_ir)
        self.btn_clear_ir.clicked.connect(self.clear_ir_list)
        
        # Botões de DI
        self.btn_add_di.clicked.connect(self.add_di_files)
        self.btn_add_di_folder.clicked.connect(self.add_di_folder)
        self.btn_remove_di.clicked.connect(self.remove_selected_di)
        self.btn_clear_di.clicked.connect(self.clear_di_list)
        
        # Seleção de arquivos (árvore)
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
        
    def add_ir_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar arquivos IR",
            "",
            "Arquivos de áudio (*.wav *.WAV *.aiff *.AIFF *.flac *.FLAC);;Todos os arquivos (*)"
        )
        self.add_files_to_tree(files, self.ir_files, self.ir_tree)
        
    def add_ir_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta com IRs")
        if folder:
            self.add_folder_to_tree(folder, self.ir_files, self.ir_tree)
            
    def add_di_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar arquivos DI",
            "",
            "Arquivos de áudio (*.wav *.WAV *.aiff *.AIFF *.flac *.FLAC *.mp3 *.MP3);;Todos os arquivos (*)"
        )
        self.add_files_to_tree(files, self.di_files, self.di_tree)
        
    def add_di_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta com DIs")
        if folder:
            self.add_folder_to_tree(folder, self.di_files, self.di_tree)
            
    def add_files_to_tree(self, files, file_dict, tree_widget):
        """Adiciona arquivos individuais à árvore (sem pasta pai)"""
        import os
        tree_widget.setUpdatesEnabled(False)
        try:
            for filepath in files:
                filename = os.path.basename(filepath)
                # Cria uma chave única para o arquivo
                key = f"_files_/{filename}"
                if key not in file_dict:
                    file_dict[key] = filepath
                    
                    # Procura ou cria o item "Arquivos Soltos"
                    loose_files_item = None
                    for i in range(tree_widget.topLevelItemCount()):
                        item = tree_widget.topLevelItem(i)
                        if item.data(0, Qt.ItemDataRole.UserRole) == "_loose_files_":
                            loose_files_item = item
                            break
                    
                    if loose_files_item is None:
                        loose_files_item = QTreeWidgetItem(tree_widget)
                        loose_files_item.setText(0, "📄 Arquivos Soltos")
                        loose_files_item.setData(0, Qt.ItemDataRole.UserRole, "_loose_files_")
                        loose_files_item.setExpanded(True)
                    
                    # Adiciona o arquivo como filho
                    file_item = QTreeWidgetItem(loose_files_item)
                    file_item.setText(0, filename)
                    file_item.setData(0, Qt.ItemDataRole.UserRole, key)
        finally:
            tree_widget.setUpdatesEnabled(True)
                
    def add_folder_to_tree(self, folder, file_dict, tree_widget):
        """Adiciona uma pasta inteira à árvore mantendo a estrutura"""
        import os
        extensions = ('.wav', '.WAV', '.aiff', '.AIFF', '.flac', '.FLAC', '.mp3', '.MP3')
        
        folder_name = os.path.basename(folder)
        
        # Cria o item raiz da pasta
        folder_item = QTreeWidgetItem(tree_widget)
        folder_item.setText(0, f"📂 {folder_name}")
        folder_item.setData(0, Qt.ItemDataRole.UserRole, f"_folder_:{folder}")
        folder_item.setExpanded(True)
        
        tree_widget.setUpdatesEnabled(False)
        try:
            # Dicionário para mapear caminhos relativos para itens da árvore
            path_to_item = {"": folder_item}
            
            for root, dirs, files in os.walk(folder):
                # Ordena diretórios e arquivos
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
                    path_to_item[dir_path] = dir_item
                
                # Adiciona arquivos
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
        finally:
            tree_widget.setUpdatesEnabled(True)
                        
    def remove_selected_ir(self):
        current = self.ir_tree.currentItem()
        if current:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                # É um arquivo, remove
                if key in self.ir_files:
                    del self.ir_files[key]
                parent = current.parent()
                if parent:
                    parent.removeChild(current)
                else:
                    index = self.ir_tree.indexOfTopLevelItem(current)
                    self.ir_tree.takeTopLevelItem(index)
            elif key and (key.startswith("_folder_:") or key.startswith("_subfolder_:") or key == "_loose_files_"):
                # É uma pasta, remove todos os arquivos dela
                self._remove_folder_item(current, self.ir_files)
                parent = current.parent()
                if parent:
                    parent.removeChild(current)
                else:
                    index = self.ir_tree.indexOfTopLevelItem(current)
                    self.ir_tree.takeTopLevelItem(index)
            
    def remove_selected_di(self):
        current = self.di_tree.currentItem()
        if current:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                # É um arquivo, remove
                if key in self.di_files:
                    del self.di_files[key]
                parent = current.parent()
                if parent:
                    parent.removeChild(current)
                else:
                    index = self.di_tree.indexOfTopLevelItem(current)
                    self.di_tree.takeTopLevelItem(index)
            elif key and (key.startswith("_folder_:") or key.startswith("_subfolder_:") or key == "_loose_files_"):
                # É uma pasta, remove todos os arquivos dela
                self._remove_folder_item(current, self.di_files)
                parent = current.parent()
                if parent:
                    parent.removeChild(current)
                else:
                    index = self.di_tree.indexOfTopLevelItem(current)
                    self.di_tree.takeTopLevelItem(index)
                    
    def _remove_folder_item(self, folder_item, file_dict):
        """Remove recursivamente todos os arquivos de uma pasta"""
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            key = child.data(0, Qt.ItemDataRole.UserRole)
            if key and not key.startswith("_folder_:") and not key.startswith("_subfolder_:") and key != "_loose_files_":
                if key in file_dict:
                    del file_dict[key]
            else:
                # É uma subpasta, remove recursivamente
                self._remove_folder_item(child, file_dict)
            
    def clear_ir_list(self):
        self.ir_files.clear()
        self.ir_tree.clear()
        self.current_ir = None
        self.ir_info_label.setText("Nenhum IR selecionado")
        
    def clear_di_list(self):
        self.di_files.clear()
        self.di_tree.clear()
        self.current_di = None
        self.di_info_label.setText("Nenhum DI selecionado")
        
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
                    # Preserva a posição ao trocar IR
                    self.process_and_play(preserve_position=True)
            else:
                # É uma pasta, não faz nada
                pass
        else:
            self.ir_info_label.setText("Nenhum IR selecionado")
            
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
                # É uma pasta, não faz nada
                pass
        else:
            self.di_info_label.setText("Nenhum DI selecionado")
            
    def process_and_play(self, preserve_position=False):
        if self.current_ir and self.current_di:
            # Salva posição atual se necessário
            self._preserve_position = preserve_position
            if preserve_position and self.audio_engine.has_audio():
                self._saved_position = self.audio_engine.get_position()
                self._was_playing = self.is_playing
            else:
                self._saved_position = 0
                self._was_playing = True  # Inicia reprodução por padrão
            
            # Cancela worker anterior se existir
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
            pass  # Nenhuma ação necessária quando IR ou DI não estão selecionados
                
    def on_convolution_progress(self, value):
        self.progress_bar.setValue(value)
        
    def on_convolution_finished(self, audio_data, sample_rate):
        self.progress_bar.setVisible(False)
        
        try:
            # Para reprodução atual
            self.audio_engine.stop()
            
            # Carrega o novo áudio
            self.audio_engine.load_audio(audio_data, sample_rate)
            
            # Atualiza a duração
            duration = len(audio_data) / sample_rate
            self.duration_label.setText(self.format_time(duration))
            
            # Restaura posição se preservando
            if self._preserve_position and self._saved_position > 0:
                # Garante que a posição não excede a duração do novo áudio
                seek_pos = min(self._saved_position, duration - 0.1)
                if seek_pos > 0:
                    self.audio_engine.seek(seek_pos)
            
            # Inicia reprodução apenas se estava tocando antes ou é nova seleção
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
            QMessageBox.warning(self, "Erro", f"Erro ao reproduzir: {str(e)}")
            
    def on_convolution_error(self, error_msg):
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Erro", f"Erro ao processar: {error_msg}")
                
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
            
            # Verifica se terminou
            if not self.audio_engine.is_playing() and self.is_playing:
                if self.is_looping:
                    # Reinicia do início
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
        # Usa debounce para evitar reprocessar a cada movimento do slider
        # Só processa após 300ms sem movimento
        self.mix_debounce_timer.stop()
        self.mix_debounce_timer.start(300)
        
    def _on_mix_debounced(self):
        """Chamado após o slider de mix parar de ser movido"""
        if self.current_ir and self.current_di:
            self.process_and_play(preserve_position=True)
                    
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
