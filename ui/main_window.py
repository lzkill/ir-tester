"""
Main Window da aplicação IR Tester
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
        """Aplica estilos escuros aos eixos"""
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
        """Calcula e plota a resposta em frequência do IR"""
        try:
            # Ler áudio
            data, samplerate = sf.read(file_path)
            
            # Se estéreo, mixa para mono para visualização
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
            
            # Filtra para 20Hz - 20kHz
            mask = (xf >= 20) & (xf <= 20000)
            
            self.ax.semilogx(xf[mask], response_db[mask], color='#0078d4', linewidth=1.5)
            self.ax.set_xlabel('Frequência (Hz)', fontsize=8)
            self.ax.set_ylabel('Amplitude (dB)', fontsize=8)
            self.ax.set_title('Resposta em Frequência', color='#cccccc', fontsize=9)
            self.ax.set_ylim([-60, 5]) # Limita eixo Y para focar no útil
            self.ax.set_xlim([20, 20000])
            
            # Converte ticks do eixo X para Hz legíveis
            self.ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Erro ao plotar IR: {e}")
            self.clear_plot()

    def clear_plot(self):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, "Selecione um IR", ha='center', va='center', color='#555555')
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IR Tester - Impulse Response Tester")
        self.setMinimumSize(1000, 700)
        
        # Inicializa os componentes de áudio
        self.audio_engine = AudioEngine()
        self.convolution_processor = ConvolutionProcessor()
        self.convolution_worker = None
        
        # Estado para Equalizador
        self.header_raw_audio = None # Armazena áudio sem EQ para processamento
        self.current_sample_rate = 44100
        self.equalizer_dialog = EqualizerDialog(self)
        self.equalizer_dialog.gains_changed.connect(self.update_equalization)
        self.equalizer_dialog.eq_toggled.connect(self.on_eq_toggled)
        
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
        self._last_mix_value = 100  # Valor padrao para o toggle
        
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
        
        self.btn_add_ir = QPushButton(" ＋  Adicionar")
        self.btn_add_ir.clicked.connect(lambda: self.open_unified_add_dialog(is_ir=True))
        self.btn_export_marked = QPushButton(" ➱  Exportar")
        self.btn_remove_ir = QPushButton(" ✕  Remover")
        self.btn_clear_ir = QPushButton(" ⟲  Limpar")
        
        btn_layout.addWidget(self.btn_add_ir)
        btn_layout.addWidget(self.btn_export_marked)
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
        
        # Gráfico de Frequência
        self.ir_plot_widget = IRPlotWidget()
        self.ir_plot_widget.setFixedHeight(180) # Altura fixa para não ocupar muito espaço
        layout.addWidget(self.ir_plot_widget)
        
        return group
        
    def create_di_panel(self):
        group = QGroupBox("  Direct Input (DI)")
        layout = QVBoxLayout(group)
        
        # Botões de controle
        btn_layout = QHBoxLayout()
        
        self.btn_add_di = QPushButton(" ＋  Adicionar")
        self.btn_add_di.clicked.connect(lambda: self.open_unified_add_dialog(is_ir=False))
        self.btn_remove_di = QPushButton(" ✕  Remover")
        self.btn_clear_di = QPushButton(" ⟲  Limpar")
        
        btn_layout.addWidget(self.btn_add_di)
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
        self.btn_play_pause.setObjectName("primary_action")
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
        
        # Botão Equalizer
        self.btn_eq = QPushButton("Equalizer 🎚️")
        self.btn_eq.setToolTip("Abrir Equalizador Gráfico")
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

        # Botão Dry/Wet Toggle
        self.btn_dry_wet = QPushButton("D/W")
        self.btn_dry_wet.setToolTip("Alternar entre Dry (0%) e o último valor Wet")
        self.btn_dry_wet.setCheckable(True)
        self.btn_dry_wet.setChecked(True)
        self.btn_dry_wet.setMinimumWidth(60)
        self.btn_dry_wet.clicked.connect(self.toggle_dry_wet)
        layout.addWidget(self.btn_dry_wet)
        
        return frame
        
    def connect_signals(self):
        # Botões de IR
        # self.btn_add_ir e self.btn_add_ir_menu são conectados via menu/actions
        self.btn_export_marked.clicked.connect(self.export_marked_irs)
        self.btn_remove_ir.clicked.connect(self.remove_selected_ir)
        self.btn_clear_ir.clicked.connect(self.clear_ir_list)
        
        # Botões de DI
        # Conexões via menu
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
        
    def open_unified_add_dialog(self, is_ir=True):
        """Abre o diálogo universal para adicionar arquivos e pastas usando QFileDialog modificado"""
        dialog = QFileDialog(self, "Adicionar IRs" if is_ir else "Adicionar DIs")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        # Define filtros
        dialog.setNameFilters(["Arquivos de áudio (*.wav *.mp3 *.flac *.aiff *.ogg)", "Todos os arquivos (*)"])
        
        # HACK: Encontra as views internas (ListView e TreeView) e permite seleção múltipla
        # Isso permite selecionar arquivos E pastas ao mesmo tempo na interface do Qt
        views = dialog.findChildren((QListView, QTreeView))
        for view in views:
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            paths = dialog.selectedFiles()
            self.process_added_paths(paths, is_ir)
            
    def process_added_paths(self, paths, is_ir=True):
        """Processa a lista de caminhos adicionados (arquivos ou pastas)"""
        import os
        
        # Define qual conjunto de funções usar
        # Define qual conjunto de dados usar
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
                        loose_files_item.setCheckState(0, Qt.CheckState.Unchecked)
                    
                    # Adiciona o arquivo como filho
                    file_item = QTreeWidgetItem(loose_files_item)
                    file_item.setText(0, filename)
                    file_item.setData(0, Qt.ItemDataRole.UserRole, key)
                    file_item.setCheckState(0, Qt.CheckState.Unchecked)
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
        folder_item.setCheckState(0, Qt.CheckState.Unchecked)
        
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
                    dir_item.setCheckState(0, Qt.CheckState.Unchecked)
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
                            file_item.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            tree_widget.setUpdatesEnabled(True)
                        
    def export_marked_irs(self):
        """Exporta os IRs marcados com checkbox para uma pasta"""
        import os
        import shutil
        
        # Coleta arquivos marcados
        marked_files = []
        
        # Percorre todos os itens da árvore
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
            QMessageBox.information(self, "Exportar", "Nenhum arquivo selecionado para exportação.")
            return
            
        # Seleciona pasta de destino
        dest_folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino")
        if not dest_folder:
            return
            
        # Copia arquivos
        success_count = 0
        error_count = 0
        
        # Barra de progresso para cópia
        progress = QProgressBar(self)
        progress.setWindowTitle("Exportando...")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimum(0)
        progress.setMaximum(len(marked_files))
        progress.show()
        
        for i, src_path in enumerate(marked_files):
            try:
                filename = os.path.basename(src_path)
                dst_path = os.path.join(dest_folder, filename)
                
                # Se arquivo já existe, adiciona sufixo numérico
                if os.path.exists(dst_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dst_path):
                        dst_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                        counter += 1
                
                shutil.copy2(src_path, dst_path)
                success_count += 1
            except Exception as e:
                print(f"Erro ao copiar {src_path}: {e}")
                error_count += 1
            
            progress.setValue(i + 1)
            QApplication.processEvents()
            
        progress.close()
        
        msg = f"Exportação concluída!\n\n{success_count} arquivos copiados com sucesso."
        if error_count > 0:
            msg += f"\n{error_count} erros."
            
        QMessageBox.information(self, "Exportar", msg)

    def remove_selected_ir(self):
        self.remove_checked_items(self.ir_tree, self.ir_files)
        
    def remove_selected_di(self):
        self.remove_checked_items(self.di_tree, self.di_files)
        
    def remove_checked_items(self, tree_widget, file_dict):
        """Remove itens marcados (checkbox) ou o item selecionado se nada estiver marcado"""
        items_to_remove = []
        has_checked_items = False
        
        # Primeiro, verifica se há itens marcados
        iterator = QTreeWidgetItemIterator(tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                has_checked_items = True
                # Adiciona apenas itens de nível superior na seleção para evitar problemas ao remover pais e filhos
                # Mas aqui precisamos ser cuidadosos. Vamos coletar todos e processar depois.
                items_to_remove.append(item)
            iterator += 1
            
        # Se não houver itens marcados, usa a seleção atual (comportamento legado)
        if not has_checked_items:
            current = tree_widget.currentItem()
            if current:
                items_to_remove.append(current)
        
        if not items_to_remove:
            return
            
        # Processa a remoção
        # Para remover corretamente, precisamos limpar o dicionário de arquivos primeiro
        for item in items_to_remove:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key:
                if key.startswith("_folder_:") or key.startswith("_subfolder_:") or key == "_loose_files_":
                    # É uma pasta, remove recursivamente do dicionário
                    self._remove_folder_content_from_dict(item, file_dict)
                else:
                    # É um arquivo
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
        """Remove recursivamente todos os arquivos de uma pasta do dicionário"""
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
                    # Atualiza gráfico
                    self.ir_plot_widget.plot_ir(filepath)
                    # Preserva a posição ao trocar IR
                    self.process_and_play(preserve_position=True)
            else:
                # É uma pasta, limpa o gráfico
                self.ir_plot_widget.clear_plot()
        else:
            self.ir_info_label.setText("Nenhum IR selecionado")
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
            
            # Carrega o novo áudio (para definir sample_rate e inicializar)
            self.audio_engine.load_audio(audio_data, sample_rate)
            
            # Armazena o áudio raw para reprocessamento (EQ)
            self.header_raw_audio = audio_data
            self.current_sample_rate = sample_rate
            
            # Aplica EQ inicial (ou flat se tudo zero)
            # Isso vai sobrescrever o buffer do engine via update_audio
            self.update_equalization(self.equalizer_dialog.current_gains)
            
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
                    
    def toggle_dry_wet(self):
        current_val = self.mix_slider.value()
        
        if current_val > 0:
            # Indo para Dry
            self._last_mix_value = current_val
            self.mix_slider.setValue(0)
            self.btn_dry_wet.setChecked(False)
        else:
            # Voltando para Wet
            target = self._last_mix_value if self._last_mix_value > 0 else 100
            self.mix_slider.setValue(target)
            self.btn_dry_wet.setChecked(True)

    def update_equalization(self, gains):
        """Aplica equalização ao áudio raw atual e atualiza o engine"""
        # Se EQ estiver desativado ou sem áudio, ignora
        if not self.equalizer_dialog.btn_enable.isChecked() or self.header_raw_audio is None:
            return
            
        try:
            # Processa o áudio raw com os ganhos atuais
            processed_audio = Equalizer.process_frame(
                self.header_raw_audio, 
                self.current_sample_rate, 
                gains
            )
            
            # Atualiza o motor de áudio (hot-swap)
            self.audio_engine.update_audio(processed_audio)
            
        except Exception as e:
            print(f"Erro na equalização: {e}")
            
    def on_eq_toggled(self, enabled: bool):
        """Chamado quando o checkbox de ativar/desativar EQ é alterado"""
        if self.header_raw_audio is None:
            return
            
        if enabled:
            # Re-aplica a equalização atual
            self.update_equalization(self.equalizer_dialog.current_gains)
        else:
            # Bypass: carrega o áudio original (raw)
            print("EQ Bypass: Carregando áudio original")
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
