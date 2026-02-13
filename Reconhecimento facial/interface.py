import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import cv2
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime
import os
import pickle
import numpy as np
from urllib.request import urlretrieve
import winsound  # Para Windows
import platform
import shutil
from pathlib import Path


class SistemaAlarme:
    """Classe para gerenciar alarmes sonoros"""

    def __init__(self):
        self.alarme_ativo = False
        self.thread_alarme = None
        self.sistema_operacional = platform.system()

    def tocar_sirene_windows(self, duracao=3):
        """Toca sirene policial no Windows"""
        try:
            # Sirene alternando frequências
            for _ in range(duracao):
                winsound.Beep(800, 200)  # Frequência alta
                winsound.Beep(400, 200)  # Frequência baixa
        except:
            # Fallback para beep simples
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    def tocar_sirene_linux(self, duracao=3):
        """Toca sirene no Linux"""
        try:
            import subprocess
            # Usa o comando beep do Linux
            for _ in range(duracao * 2):
                subprocess.call(['beep', '-f', '800', '-l', '200'])
                subprocess.call(['beep', '-f', '400', '-l', '200'])
        except:
            # Fallback: print no terminal
            print('\a' * 5)  # Bell character

    def tocar_arquivo_audio(self, arquivo):
        """Toca arquivo de áudio WAV"""
        try:
            if self.sistema_operacional == "Windows":
                winsound.PlaySound(arquivo, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                # Para Linux/Mac
                import subprocess
                subprocess.Popen(['aplay' if self.sistema_operacional == 'Linux' else 'afplay', arquivo])
        except Exception as e:
            print(f"Erro ao tocar áudio: {e}")

    def criar_arquivo_alarme_wav(self):
        """Cria um arquivo WAV de alarme se não existir"""
        try:
            # Verifica se o arquivo já existe
            if os.path.exists("alarme.wav"):
                return "alarme.wav"

            # Tenta usar pydub para criar som
            try:
                from pydub import AudioSegment
                from pydub.generators import Sine

                # Gera tons de sirene
                tone1 = Sine(800).to_audio_segment(duration=200)
                tone2 = Sine(400).to_audio_segment(duration=200)

                # Combina os tons alternadamente
                alarm = AudioSegment.empty()
                for _ in range(6):
                    alarm += tone1 + tone2

                # Salva o arquivo
                alarm.export("alarme.wav", format="wav")
                return "alarme.wav"
            except:
                return None
        except:
            return None

    def iniciar_alarme(self, duracao=5):
        """Inicia o alarme em thread separada"""
        if not self.alarme_ativo:
            self.alarme_ativo = True
            self.thread_alarme = threading.Thread(
                target=self._tocar_alarme_loop,
                args=(duracao,),
                daemon=True
            )
            self.thread_alarme.start()

    def _tocar_alarme_loop(self, duracao):
        """Loop de alarme"""
        tempo_inicio = time.time()

        # Tenta tocar arquivo de áudio primeiro
        arquivo_alarme = self.criar_arquivo_alarme_wav()
        if arquivo_alarme:
            self.tocar_arquivo_audio(arquivo_alarme)
            time.sleep(duracao)
        else:
            # Fallback para beeps
            while time.time() - tempo_inicio < duracao and self.alarme_ativo:
                if self.sistema_operacional == "Windows":
                    self.tocar_sirene_windows(duracao=1)
                else:
                    self.tocar_sirene_linux(duracao=1)
                time.sleep(0.1)

        self.alarme_ativo = False

    def parar_alarme(self):
        """Para o alarme"""
        self.alarme_ativo = False



class SistemaReconhecimento:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Reconhecimento Facial")
        self.root.state('zoomed')

        # Configurações visuais
        self.COR_FUNDO = '#2C3E50'
        self.COR_PRIMARIA = '#3498DB'
        self.COR_SECUNDARIA = '#1A252F'
        self.COR_SUCESSO = '#2ECC71'
        self.COR_ERRO = '#E74C3C'
        self.COR_ALERTA = '#F39C12'
        self.COR_INFO = '#3498DB'
        self.COR_CADASTRO = '#9B59B6'
        self.COR_TREINAR = '#1ABC9C'
        self.COR_IMPORTAR = '#E67E22'


        self.sistema_alarme = SistemaAlarme()
        self.alarme_habilitado = True
        self.ultimo_alarme = {}  # Cooldown de alarmes por pessoa

        self.configurar_variaveis()

        self.verificar_detector()

        self.criar_interface()

        self.detectar_cameras_disponiveis()

        self.carregar_modelo()

    def configurar_variaveis(self):
        """Configura todas as variáveis do sistema"""
        self.sistema_ativo = False
        self.modo_cadastro = False
        self.thread_camera = None
        self.recognizer = None
        self.face_cascade = None
        self.nomes = {}
        self.cam = None

        # Configuração da câmera
        self.camera_index = 0
        self.cameras_disponiveis = []
        self.camera_atual = None

        # Cadastro
        self.dados_cadastro = {
            'id': None,
            'nome': None,
            'tipo': None,
            'contador': 0,
            'salvas': 0
        }

        # Configurações de reconhecimento
        self.confidence_threshold = 70

        # Estatísticas
        self.estatisticas = {
            'reconhecimentos': 0,
            'desconhecidos': 0,
            'alertas': 0
        }

    def detectar_cameras_disponiveis(self):
        """Detecta todas as câmeras disponíveis no sistema"""
        self.cameras_disponiveis = []

        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                try:
                    ret, frame = cap.read()
                    if ret:
                        camera_name = f"Câmera {i}"
                        self.cameras_disponiveis.append({
                            'index': i,
                            'name': camera_name
                        })
                        self.log(f"✓ Detectada: {camera_name}", self.COR_INFO)
                except:
                    pass
                finally:
                    cap.release()

        if not self.cameras_disponiveis:
            self.log(" Nenhuma câmera detectada!", self.COR_ERRO)
        else:
            self.log(f"✓ {len(self.cameras_disponiveis)} câmera(s) disponível(is)", self.COR_SUCESSO)
            camera_names = [cam['name'] for cam in self.cameras_disponiveis]
            self.camera_combo['values'] = camera_names
            if camera_names:
                self.camera_combo.current(0)
                self.camera_atual = self.cameras_disponiveis[0]

    def verificar_detector(self):
        """Baixa o detector facial se necessário"""
        if not os.path.exists("haarcascade_frontalface_default.xml"):
            try:
                url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
                urlretrieve(url, "haarcascade_frontalface_default.xml")
                self.log("✓ Detector facial baixado!", self.COR_SUCESSO)
            except Exception as e:
                self.log(f" Erro ao baixar detector: {e}", self.COR_ERRO)

    def carregar_modelo(self):
        """Carrega o modelo de reconhecimento se existir"""
        try:
            if os.path.exists('haarcascade_frontalface_default.xml'):
                self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
                self.log("✓ Detector facial carregado", self.COR_SUCESSO)

            if os.path.exists('trainer/names.pkl'):
                with open('trainer/names.pkl', 'rb') as f:
                    self.nomes = pickle.load(f)
                self.log(f" {len(self.nomes)} pessoa(s) carregada(s)", self.COR_SUCESSO)
                self.atualizar_lista()

            if os.path.exists('trainer/trainer.yml'):
                self.recognizer = self.criar_recognizer_simples()
                self.carregar_dados_modelo()
                self.log(" Modelo carregado!", self.COR_SUCESSO)
            else:
                self.log(" Nenhum modelo treinado encontrado", self.COR_INFO)

        except Exception as e:
            self.log(f" Erro ao carregar sistema: {e}", self.COR_ERRO)

    def criar_recognizer_simples(self):
        """Cria um reconhecedor facial simples"""

        class SimpleRecognizer:
            def __init__(self):
                self.faces_data = []
                self.labels_data = []

            def train(self, faces, labels):
                self.faces_data = faces
                self.labels_data = labels
                return True

            def predict(self, face):
                if len(self.faces_data) == 0:
                    return -1, 100

                face_resized = cv2.resize(face, (100, 100))
                face_resized = cv2.equalizeHist(face_resized)

                min_distance = 1000
                best_label = -1

                for i, trained_face in enumerate(self.faces_data):
                    trained_resized = cv2.resize(trained_face, (100, 100))
                    trained_resized = cv2.equalizeHist(trained_resized)
                    diff = cv2.absdiff(face_resized, trained_resized)
                    distance = np.mean(diff)

                    if distance < min_distance:
                        min_distance = distance
                        best_label = self.labels_data[i]

                confidence = min(min_distance / 5, 100)
                return best_label, confidence

        return SimpleRecognizer()

    def carregar_dados_modelo(self):
        """Carrega dados do modelo treinado"""
        try:
            if os.path.exists('trainer/model_data.pkl'):
                with open('trainer/model_data.pkl', 'rb') as f:
                    model_data = pickle.load(f)
                self.recognizer.faces_data = model_data.get('faces', [])
                self.recognizer.labels_data = model_data.get('labels', [])
        except:
            pass

    def criar_interface(self):
        """Cria a interface gráfica"""
        self.criar_header()

        corpo = tk.Frame(self.root, bg=self.COR_FUNDO)
        corpo.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.criar_coluna_video(corpo)
        self.criar_coluna_controles(corpo)
        self.criar_area_log()

    def criar_header(self):
        """Cria o cabeçalho"""
        header = tk.Frame(self.root, bg=self.COR_SECUNDARIA, height=100)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=" SISTEMA DE RECONHECIMENTO FACIAL",
            font=("Arial", 18, "bold"),
            bg=self.COR_SECUNDARIA,
            fg="white"
        ).pack(side=tk.LEFT, padx=30, pady=20)

        self.criar_badge_status(header)

    def criar_badge_status(self, parent):
        """Cria badge de status"""
        status_frame = tk.Frame(parent, bg=self.COR_FUNDO)
        status_frame.pack(side=tk.RIGHT, padx=30, pady=20)

        # Frame para câmera
        camera_frame = tk.Frame(status_frame, bg=self.COR_FUNDO)
        camera_frame.pack(pady=(0, 10))

        tk.Label(camera_frame, text="Câmera:", bg=self.COR_FUNDO,
                 fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))

        self.camera_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var,
                                         state="readonly", width=25)
        self.camera_combo.pack(side=tk.LEFT)
        self.camera_combo.bind('<<ComboboxSelected>>', self.selecionar_camera)

        tk.Button(camera_frame, text="", command=self.detectar_cameras_disponiveis,
                  bg=self.COR_INFO, fg="white", font=("Arial", 9),
                  relief=tk.FLAT, cursor="hand2", width=3).pack(side=tk.LEFT, padx=5)

        # Status
        self.label_status = tk.Label(
            status_frame,
            text="OFFLINE",
            font=("Arial", 12, "bold"),
            bg=self.COR_FUNDO,
            fg=self.COR_ERRO,
            padx=10,
            pady=5
        )
        self.label_status.pack()

    def selecionar_camera(self, event=None):
        """Seleciona câmera"""
        selected_name = self.camera_combo.get()
        for cam in self.cameras_disponiveis:
            if cam['name'] == selected_name:
                self.camera_atual = cam
                self.camera_index = cam['index']
                self.log(f" Câmera selecionada: {cam['name']}", self.COR_INFO)
                break

    def criar_coluna_video(self, parent):
        """Cria coluna de vídeo"""
        coluna = tk.Frame(parent, bg=self.COR_SECUNDARIA)
        coluna.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        video_container = tk.Frame(coluna, bg=self.COR_FUNDO)
        video_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.video_frame = tk.Frame(video_container, bg="#000000",
                                    highlightthickness=2, highlightbackground=self.COR_PRIMARIA)
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        self.label_video = tk.Label(self.video_frame, bg="#000000",
                                    text=" SELECIONE UMA CÂMERA\nE TESTE A CONEXÃO",
                                    font=("Arial", 12), fg="#888888", justify=tk.CENTER)
        self.label_video.pack(fill=tk.BOTH, expand=True)

        self.criar_controles_video(coluna)

    def criar_controles_video(self, parent):
        """Cria controles de vídeo"""
        controles = tk.Frame(parent, bg=self.COR_SECUNDARIA, height=100)
        controles.pack(fill=tk.X, padx=10, pady=(10, 0))
        controles.pack_propagate(False)

        botoes = [
            (" Testar Câmera", self.COR_INFO, self.testar_camera),
            (" Iniciar", self.COR_SUCESSO, self.iniciar_sistema),
            (" Parar", self.COR_ERRO, self.parar_sistema),
            (" Cadastrar", self.COR_CADASTRO, self.iniciar_cadastro),
            (" Importar Fotos", self.COR_IMPORTAR, self.importar_fotos)  # NOVO BOTÃO
        ]

        btn_frame = tk.Frame(controles, bg=self.COR_SECUNDARIA)
        btn_frame.pack(expand=True, pady=15)

        for texto, cor, comando in botoes:
            btn = tk.Button(
                btn_frame,
                text=texto,
                command=comando,
                font=("Arial", 10, "bold"),
                bg=cor,
                fg="white",
                relief=tk.FLAT,
                cursor="hand2",
                padx=15,
                pady=6
            )
            btn.pack(side=tk.LEFT, padx=4)

            if "Parar" in texto:
                self.btn_parar = btn
                btn.config(state=tk.DISABLED)
            elif "Iniciar" in texto:
                self.btn_iniciar = btn
            elif "Testar" in texto:
                self.btn_conectar = btn
            elif "Cadastrar" in texto:
                self.btn_cadastrar = btn
            elif "Importar" in texto:
                self.btn_importar = btn

    def testar_camera(self):
        """Testa câmera"""
        if not self.cameras_disponiveis:
            messagebox.showwarning("Aviso", "Nenhuma câmera disponível!")
            return

        if self.camera_atual is None:
            messagebox.showwarning("Aviso", "Selecione uma câmera!")
            return

        self.log(f"🔍 Testando {self.camera_atual['name']}...", self.COR_INFO)

        cap = cv2.VideoCapture(self.camera_atual['index'])
        if not cap.isOpened():
            messagebox.showerror("Erro", "Não foi possível abrir a câmera!")
            return

        ret, frame = cap.read()
        if ret:
            frame_resized = cv2.resize(frame, (640, 480))
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)

            self.label_video.imgtk = imgtk
            self.label_video.configure(image=imgtk, text="")
            self.log(f"✓ Câmera funcionando!", self.COR_SUCESSO)
        else:
            self.log(" Falha na captura", self.COR_ERRO)
            messagebox.showerror("Erro", "Não foi possível capturar imagem!")

        cap.release()

    def criar_coluna_controles(self, parent):
        """Cria coluna de controles"""
        coluna = tk.Frame(parent, bg=self.COR_SECUNDARIA, width=400)
        coluna.pack(side=tk.RIGHT, fill=tk.BOTH)
        coluna.pack_propagate(False)


        self.criar_painel_alarme(coluna)

        self.criar_painel_treinamento(coluna)
        self.criar_lista_pessoas(coluna)
        self.criar_painel_configuracoes(coluna)

    def criar_painel_alarme(self, parent):
        """Cria painel de controle do alarme"""
        painel = tk.Frame(parent, bg=self.COR_ERRO,
                          highlightthickness=2, highlightbackground='#FF0000')
        painel.pack(fill=tk.X, padx=15, pady=(15, 10))

        tk.Label(
            painel,
            text=" SISTEMA DE ALARME ",
            font=("Arial", 12, "bold"),
            bg=self.COR_ERRO,
            fg="white"
        ).pack(pady=8)

        # Checkbox para habilitar/desabilitar alarme
        self.var_alarme = tk.BooleanVar(value=True)
        check_alarme = tk.Checkbutton(
            painel,
            text=" Alarme Ativado (toca ao detectar criminoso)",
            variable=self.var_alarme,
            command=self.toggle_alarme,
            bg=self.COR_ERRO,
            fg="white",
            selectcolor=self.COR_SECUNDARIA,
            font=("Arial", 9, "bold")
        )
        check_alarme.pack(pady=3)


        tk.Button(
            painel,
            text=" TESTAR ALARME",
            command=self.testar_alarme,
            bg="#8B0000",
            fg="white",
            font=("Arial", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=4
        ).pack(pady=(0, 8))

    def toggle_alarme(self):
        """Ativa/desativa alarme"""
        self.alarme_habilitado = self.var_alarme.get()
        status = " ATIVADO" if self.alarme_habilitado else " DESATIVADO"
        cor = self.COR_SUCESSO if self.alarme_habilitado else self.COR_ERRO
        self.log(f" Alarme: {status}", cor)

    def testar_alarme(self):

        self.log(" Testando alarme...", self.COR_ALERTA)
        self.sistema_alarme.iniciar_alarme(duracao=3)
        self.log(" Teste de alarme concluído!", self.COR_SUCESSO)

    def criar_painel_treinamento(self, parent):

        painel = tk.Frame(parent, bg=self.COR_FUNDO,
                          highlightthickness=1, highlightbackground=self.COR_PRIMARIA)
        painel.pack(fill=tk.X, padx=15, pady=(10, 10))

        tk.Label(
            painel,
            text=" TREINAMENTO",
            font=("Arial", 12, "bold"),
            bg=self.COR_FUNDO,
            fg="white"
        ).pack(pady=8)

        botoes_frame = tk.Frame(painel, bg=self.COR_FUNDO)
        botoes_frame.pack(pady=(0, 10))


        self.btn_treinar = tk.Button(
            botoes_frame,
            text=" TREINAR SISTEMA",
            command=self.treinar_modelo,
            bg=self.COR_TREINAR,
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        self.btn_treinar.pack(side=tk.LEFT, padx=5)


        self.btn_limpar = tk.Button(
            botoes_frame,
            text="🗑 LIMPAR",
            command=self.limpar_dados,
            bg=self.COR_ERRO,
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=8
        )
        self.btn_limpar.pack(side=tk.LEFT, padx=5)

        self.label_status_treinamento = tk.Label(
            painel,
            text="Pronto para treinar",
            font=("Arial", 8),
            bg=self.COR_FUNDO,
            fg=self.COR_INFO
        )
        self.label_status_treinamento.pack(pady=(0, 8))

    def criar_lista_pessoas(self, parent):

        frame = tk.Frame(parent, bg=self.COR_FUNDO,
                         highlightthickness=1, highlightbackground=self.COR_PRIMARIA)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(
            frame,
            text=" PESSOAS CADASTRADAS",
            font=("Arial", 12, "bold"),
            bg=self.COR_FUNDO,
            fg="white"
        ).pack(pady=8)

        # Frame para controles da lista
        controles_frame = tk.Frame(frame, bg=self.COR_FUNDO)
        controles_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Botão remover selecionado
        self.btn_remover = tk.Button(
            controles_frame,
            text=" REMOVER",
            command=self.remover_pessoa,
            bg=self.COR_ERRO,
            fg="white",
            font=("Arial", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=4
        )
        self.btn_remover.pack(side=tk.LEFT)


        tk.Button(
            controles_frame,
            text=" VISUALIZAR FOTOS",
            command=self.visualizar_fotos,
            bg=self.COR_INFO,
            fg="white",
            font=("Arial", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=4
        ).pack(side=tk.LEFT, padx=5)


        tk.Button(
            controles_frame,
            text=" ATUALIZAR",
            command=self.atualizar_lista,
            bg=self.COR_INFO,
            fg="white",
            font=("Arial", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=4
        ).pack(side=tk.RIGHT)

        lista_container = tk.Frame(frame, bg=self.COR_FUNDO)
        lista_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        scrollbar = tk.Scrollbar(lista_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.lista_pessoas = tk.Listbox(
            lista_container,
            yscrollcommand=scrollbar.set,
            font=("Arial", 9),
            bg="#1A252F",
            fg="white",
            selectbackground=self.COR_PRIMARIA,
            selectmode=tk.SINGLE,
            height=7
        )
        self.lista_pessoas.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.lista_pessoas.yview)

    def criar_painel_configuracoes(self, parent):

        painel = tk.Frame(parent, bg=self.COR_FUNDO,
                          highlightthickness=1, highlightbackground=self.COR_PRIMARIA)
        painel.pack(fill=tk.X, padx=15, pady=(10, 15))

        tk.Label(
            painel,
            text="⚙ CONFIGURAÇÕES",
            font=("Arial", 12, "bold"),
            bg=self.COR_FUNDO,
            fg="white"
        ).pack(pady=8)

        config_frame = tk.Frame(painel, bg=self.COR_FUNDO)
        config_frame.pack(pady=(0, 8))

        tk.Label(config_frame, text="Limite de Confiança:", bg=self.COR_FUNDO,
                 fg="white", font=("Arial", 8)).grid(row=0, column=0, padx=5, sticky="w")

        self.sensibilidade_var = tk.IntVar(value=self.confidence_threshold)
        self.slider_sensibilidade = tk.Scale(config_frame, from_=30, to=100,
                                             variable=self.sensibilidade_var,
                                             orient=tk.HORIZONTAL, length=180,
                                             bg=self.COR_FUNDO, fg="white",
                                             font=("Arial", 8))
        self.slider_sensibilidade.grid(row=0, column=1, padx=5)
        self.slider_sensibilidade.bind("<ButtonRelease>", self.atualizar_sensibilidade)

    def atualizar_sensibilidade(self, event=None):
        """Atualiza sensibilidade"""
        self.confidence_threshold = self.sensibilidade_var.get()
        self.log(f"⚙ Limite ajustado: {self.confidence_threshold}", self.COR_INFO)

    def criar_area_log(self):

        container = tk.Frame(self.root, bg=self.COR_FUNDO)
        container.pack(fill=tk.X, padx=20, pady=(0, 20))

        tk.Label(
            container,
            text=" LOG DO SISTEMA",
            font=("Arial", 11, "bold"),
            bg=self.COR_FUNDO,
            fg="white"
        ).pack(anchor="w", pady=(0, 5))

        log_frame = tk.Frame(container, bg=self.COR_FUNDO,
                             highlightthickness=1, highlightbackground="#34495E")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.texto_log = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg="#1A252F",
            fg="white",
            height=6,
            relief=tk.FLAT
        )
        self.texto_log.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)


    def importar_fotos(self):
        """Importa fotos para uma pessoa existente"""
        if not self.nomes:
            messagebox.showwarning("Aviso", "Nenhuma pessoa cadastrada ainda!")
            return

        # Janela de seleção de pessoa
        janela_selecao = tk.Toplevel(self.root)
        janela_selecao.title("Importar Fotos")
        janela_selecao.geometry("500x400")
        janela_selecao.configure(bg=self.COR_SECUNDARIA)
        janela_selecao.resizable(False, False)
        janela_selecao.transient(self.root)
        janela_selecao.grab_set()

        tk.Label(
            janela_selecao,
            text=" IMPORTAR FOTOS PARA PESSOA",
            font=("Arial", 14, "bold"),
            bg=self.COR_SECUNDARIA,
            fg="white"
        ).pack(pady=15)


        lista_frame = tk.Frame(janela_selecao, bg=self.COR_FUNDO,
                               highlightthickness=1, highlightbackground=self.COR_PRIMARIA)
        lista_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        tk.Label(lista_frame, text="Selecione uma pessoa:", bg=self.COR_FUNDO,
                 fg="white", font=("Arial", 10)).pack(pady=5)


        pessoas_listbox = tk.Listbox(lista_frame, font=("Arial", 10),
                                     bg="#1A252F", fg="white",
                                     selectbackground=self.COR_PRIMARIA,
                                     height=8)
        pessoas_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for user_id, info in sorted(self.nomes.items()):
            pessoas_listbox.insert(tk.END, f"ID:{user_id} - {info['nome']} ({info['tipo']})")


        botoes_frame = tk.Frame(janela_selecao, bg=self.COR_SECUNDARIA)
        botoes_frame.pack(pady=10)

        pessoa_selecionada = None

        def selecionar_pessoa():

            nonlocal pessoa_selecionada
            selection = pessoas_listbox.curselection()
            if not selection:
                messagebox.showwarning("Aviso", "Selecione uma pessoa!")
                return

            selected_text = pessoas_listbox.get(selection[0])
            import re
            match = re.search(r'ID:(\d+)', selected_text)
            if match:
                user_id = int(match.group(1))
                pessoa_selecionada = user_id
                janela_selecao.destroy()
                self.abrir_selecao_arquivos(user_id)
            else:
                messagebox.showerror("Erro", "Não foi possível identificar a pessoa!")

        # Botões
        tk.Button(botoes_frame, text=" SELECIONAR",
                  command=selecionar_pessoa,
                  bg=self.COR_SUCESSO, fg="white",
                  font=("Arial", 10, "bold"),
                  padx=20, pady=8).pack(side=tk.LEFT, padx=10)

        tk.Button(botoes_frame, text=" CANCELAR",
                  command=janela_selecao.destroy,
                  bg=self.COR_ERRO, fg="white",
                  font=("Arial", 10, "bold"),
                  padx=20, pady=8).pack(side=tk.LEFT, padx=10)

    def abrir_selecao_arquivos(self, user_id):
        """Abre janela para selecionar arquivos"""
        if user_id not in self.nomes:
            messagebox.showerror("Erro", "Pessoa não encontrada!")
            return

        pessoa = self.nomes[user_id]
        nome_pessoa = pessoa['nome']

        # Abrir diálogo para selecionar múltiplos arquivos
        filetypes = [
            ("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff"),
            ("Todos os arquivos", "*.*")
        ]

        files = filedialog.askopenfilenames(
            title=f"Selecionar fotos para {nome_pessoa}",
            filetypes=filetypes
        )

        if not files:
            return

        dataset_dir = "dataset"
        if not os.path.exists(dataset_dir):
            os.makedirs(dataset_dir)

        user_dir = f"{dataset_dir}/User_{user_id}"
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        # Processar cada arquivo
        fotos_processadas = 0
        total_fotos = len(files)

        # Janela de progresso
        janela_progresso = tk.Toplevel(self.root)
        janela_progresso.title("Processando Fotos")
        janela_progresso.geometry("400x200")
        janela_progresso.configure(bg=self.COR_SECUNDARIA)
        janela_progresso.resizable(False, False)
        janela_progresso.transient(self.root)

        tk.Label(janela_progresso, text=" PROCESSANDO FOTOS",
                 font=("Arial", 12, "bold"),
                 bg=self.COR_SECUNDARIA, fg="white").pack(pady=20)

        progresso_var = tk.StringVar(value=f"0/{total_fotos}")
        tk.Label(janela_progresso, textvariable=progresso_var,
                 font=("Arial", 10), bg=self.COR_SECUNDARIA, fg="white").pack()

        barra_progresso = ttk.Progressbar(janela_progresso, length=300,
                                          mode='determinate')
        barra_progresso.pack(pady=20)

        # Texto de status
        status_var = tk.StringVar(value="Iniciando processamento...")
        tk.Label(janela_progresso, textvariable=status_var,
                 font=("Arial", 8), bg=self.COR_SECUNDARIA, fg="white").pack()

        janela_progresso.update()

        def processar_fotos():

            nonlocal fotos_processadas

            try:
                # Contar fotos existentes
                fotos_existentes = 0
                if os.path.exists(user_dir):
                    fotos_existentes = len([f for f in os.listdir(user_dir)
                                            if f.endswith(('.jpg', '.png', '.jpeg'))])

                for i, file_path in enumerate(files):
                    # Atualizar progresso
                    progresso = (i + 1) / total_fotos * 100
                    barra_progresso['value'] = progresso
                    progresso_var.set(f"{i + 1}/{total_fotos}")
                    status_var.set(f"Processando: {os.path.basename(file_path)}")
                    janela_progresso.update()

                    try:
                        # Ler imagem
                        img = cv2.imread(file_path)
                        if img is None:
                            continue

                        # Converter para escala de cinza
                        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                        # Detectar faces
                        if self.face_cascade is None:
                            self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

                        faces = self.face_cascade.detectMultiScale(
                            gray,
                            scaleFactor=1.1,
                            minNeighbors=5,
                            minSize=(100, 100)
                        )

                        if len(faces) == 1:  # Apenas se houver UMA face
                            (x, y, w, h) = faces[0]
                            face_img = gray[y:y + h, x:x + w]

                            if w > 80 and h > 80:
                                # Redimensionar
                                face_img = cv2.resize(face_img, (200, 200))

                                # Salvar foto
                                nova_numero = fotos_existentes + fotos_processadas + 1
                                foto_filename = f"{user_dir}/{user_id}_{nova_numero:03d}.jpg"
                                cv2.imwrite(foto_filename, face_img)
                                fotos_processadas += 1

                                self.log(f"   Foto {i + 1}: face detectada e salva", self.COR_INFO)
                            else:
                                self.log(f"   Foto {i + 1}: face muito pequena", self.COR_ALERTA)
                        else:
                            if len(faces) == 0:
                                self.log(f"  ️ Foto {i + 1}: nenhuma face detectada", self.COR_ALERTA)
                            else:
                                self.log(f"  ️ Foto {i + 1}: {len(faces)} faces detectadas (esperado: 1)",
                                         self.COR_ALERTA)

                    except Exception as e:
                        self.log(f"   Erro na foto {i + 1}: {str(e)}", self.COR_ERRO)

                    time.sleep(0.05)  # Pequeno delay para não sobrecarregar

                # Atualizar dados da pessoa
                if fotos_processadas > 0:
                    self.nomes[user_id]['fotos'] = self.nomes[user_id].get('fotos', 0) + fotos_processadas
                    self.salvar_nomes()
                    self.atualizar_lista()

                # Fechar janela de progresso
                janela_progresso.after(0, janela_progresso.destroy)

                resumo = (
                    f" IMPORTAÇÃO CONCLUÍDA!\n\n"
                    f" Resumo para {nome_pessoa}:\n"
                    f"• Fotos selecionadas: {total_fotos}\n"
                    f"• Fotos processadas: {fotos_processadas}\n"
                    f"• Total de fotos agora: {self.nomes[user_id]['fotos']}\n\n"
                )

                if fotos_processadas < total_fotos:
                    resumo += " Algumas fotos não foram processadas porque:\n"
                    resumo += "• Nenhuma face foi detectada\n"
                    resumo += "• Múltiplas faces foram detectadas\n"
                    resumo += "• Face muito pequena ou qualidade baixa\n\n"

                resumo += " Lembre-se de treinar o modelo para atualizar!"

                messagebox.showinfo("Importação Concluída", resumo)

                if fotos_processadas > 0:
                    self.log(f" {fotos_processadas} fotos importadas para {nome_pessoa}", self.COR_SUCESSO)
                else:
                    self.log(f"️ Nenhuma foto válida importada para {nome_pessoa}", self.COR_ALERTA)

            except Exception as e:
                self.log(f" Erro na importação: {str(e)}", self.COR_ERRO)
                messagebox.showerror("Erro", f"Erro na importação: {str(e)}")
                janela_progresso.after(0, janela_progresso.destroy)

        # Iniciar processamento em thread separada
        threading.Thread(target=processar_fotos, daemon=True).start()

    def visualizar_fotos(self):
        """Visualiza fotos de uma pessoa"""
        selection = self.lista_pessoas.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione uma pessoa primeiro!")
            return

        selected_text = self.lista_pessoas.get(selection[0])
        import re
        match = re.search(r'ID:(\d+)', selected_text)
        if not match:
            messagebox.showwarning("Aviso", "Não foi possível identificar a pessoa!")
            return

        user_id = int(match.group(1))
        if user_id not in self.nomes:
            messagebox.showerror("Erro", "Pessoa não encontrada!")
            return

        pessoa = self.nomes[user_id]
        user_dir = f"dataset/User_{user_id}"

        if not os.path.exists(user_dir):
            messagebox.showinfo("Info", f"Nenhuma foto encontrada para {pessoa['nome']}")
            return

        # Obter todas as imagens
        imagens = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        if not imagens:
            messagebox.showinfo("Info", f"Nenhuma foto encontrada para {pessoa['nome']}")
            return

        # Janela de visualização
        janela_visualizacao = tk.Toplevel(self.root)
        janela_visualizacao.title(f"Fotos de {pessoa['nome']}")
        janela_visualizacao.geometry("800x600")
        janela_visualizacao.configure(bg=self.COR_SECUNDARIA)

        tk.Label(janela_visualizacao,
                 text=f"📸 FOTOS DE {pessoa['nome'].upper()} (ID: {user_id})",
                 font=("Arial", 14, "bold"),
                 bg=self.COR_SECUNDARIA, fg="white").pack(pady=10)

        tk.Label(janela_visualizacao,
                 text=f"Tipo: {pessoa['tipo']} | Total: {len(imagens)} fotos",
                 font=("Arial", 10),
                 bg=self.COR_SECUNDARIA, fg="white").pack()

        # Frame para fotos com scroll
        canvas_frame = tk.Frame(janela_visualizacao, bg=self.COR_SECUNDARIA)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, bg=self.COR_SECUNDARIA)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.COR_SECUNDARIA)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Carregar e mostrar fotos
        row = 0
        col = 0
        max_cols = 3

        for idx, img_name in enumerate(sorted(imagens)):
            img_path = os.path.join(user_dir, img_name)
            try:
                # Carregar imagem
                img = cv2.imread(img_path)
                if img is not None:
                    # Converter para RGB e redimensionar
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img_rgb)
                    pil_img.thumbnail((200, 200), Image.Resampling.LANCZOS)

                    # Converter para PhotoImage
                    photo = ImageTk.PhotoImage(pil_img)

                    # Frame para cada imagem
                    img_frame = tk.Frame(scrollable_frame, bg=self.COR_FUNDO,
                                         relief=tk.RAISED, borderwidth=1)
                    img_frame.grid(row=row, column=col, padx=5, pady=5)

                    # Label com imagem
                    label_img = tk.Label(img_frame, image=photo, bg=self.COR_FUNDO)
                    label_img.image = photo  # Manter referência
                    label_img.pack(padx=2, pady=2)

                    # Label com nome do arquivo
                    tk.Label(img_frame, text=f"{img_name}", font=("Arial", 7),
                             bg=self.COR_FUNDO, fg="white", wraplength=190).pack()

                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1

            except Exception as e:
                print(f"Erro ao carregar {img_name}: {e}")

        # Configurar scroll
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Button(janela_visualizacao, text="FECHAR",
                  command=janela_visualizacao.destroy,
                  bg=self.COR_ERRO, fg="white",
                  font=("Arial", 10, "bold"),
                  padx=20, pady=5).pack(pady=10)

    def iniciar_cadastro(self):

        if self.sistema_ativo:
            messagebox.showwarning("Aviso", "Pare o sistema antes de cadastrar!")
            return

        if not self.camera_atual:
            messagebox.showwarning("Aviso", "Selecione uma câmera primeiro!")
            return

        janela_cadastro = tk.Toplevel(self.root)
        janela_cadastro.title("Cadastro de Pessoa")
        janela_cadastro.geometry("600x700")
        janela_cadastro.configure(bg=self.COR_SECUNDARIA)
        janela_cadastro.resizable(False, False)
        janela_cadastro.transient(self.root)
        janela_cadastro.grab_set()

        tk.Label(
            janela_cadastro,
            text=" CADASTRAR NOVA PESSOA",
            font=("Arial", 14, "bold"),
            bg=self.COR_SECUNDARIA,
            fg="white"
        ).pack(pady=10)

        dados_frame = tk.Frame(janela_cadastro, bg=self.COR_SECUNDARIA)
        dados_frame.pack(pady=10, padx=30, fill=tk.X)


        tk.Label(dados_frame, text="Nome Completo:", bg=self.COR_SECUNDARIA,
                 fg="white", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=3)
        nome_var = tk.StringVar()
        nome_entry = tk.Entry(dados_frame, textvariable=nome_var, font=("Arial", 9),
                              width=30)
        nome_entry.grid(row=0, column=1, pady=3, padx=10)
        nome_entry.focus_set()

        tk.Label(dados_frame, text="Tipo:", bg=self.COR_SECUNDARIA,
                 fg="white", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=3)
        tipo_var = tk.StringVar(value="CIVIL")
        tipo_combo = ttk.Combobox(dados_frame, textvariable=tipo_var,
                                  values=["CIVIL", "CRIMINOSO"], state="readonly",
                                  width=27, font=("Arial", 9))
        tipo_combo.grid(row=1, column=1, pady=3, padx=10)


        tk.Label(dados_frame, text="ID (automático):", bg=self.COR_SECUNDARIA,
                 fg="white", font=("Arial", 9)).grid(row=2, column=0, sticky="w", pady=3)


        next_id = 1
        if self.nomes:
            next_id = max(self.nomes.keys()) + 1

        id_var = tk.StringVar(value=str(next_id))
        tk.Label(dados_frame, textvariable=id_var, bg=self.COR_SECUNDARIA,
                 fg="white", font=("Arial", 9, "bold")).grid(row=2, column=1, sticky="w", pady=3)


        camera_frame = tk.Frame(janela_cadastro, bg="#000000", height=320)
        camera_frame.pack(pady=10, padx=30, fill=tk.X)
        camera_frame.pack_propagate(False)


        label_camera = tk.Label(camera_frame, bg="#000000",
                                text="Abrindo câmera...",
                                fg="white", font=("Arial", 10))
        label_camera.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)


        controles_frame = tk.Frame(janela_cadastro, bg=self.COR_SECUNDARIA)
        controles_frame.pack(pady=10, padx=30, fill=tk.X)


        instrucoes_frame = tk.Frame(controles_frame, bg=self.COR_SECUNDARIA)
        instrucoes_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            instrucoes_frame,
            text=" INSTRUÇÕES:",
            font=("Arial", 10, "bold"),
            bg=self.COR_SECUNDARIA,
            fg=self.COR_INFO
        ).pack(pady=(0, 5))

        instrucoes_texto = (
            "1. Posicione-se em frente à câmera\n"
            "2. Clique em 'INICIAR CAPTURA'\n"
            "3. O sistema capturará 50 fotos automaticamente\n"
            "4. Mantenha seu rosto no quadro durante a captura\n"
            "5. Aguarde a conclusão do processo"
        )

        tk.Label(
            instrucoes_frame,
            text=instrucoes_texto,
            font=("Arial", 8),
            bg=self.COR_SECUNDARIA,
            fg="white",
            justify=tk.LEFT
        ).pack()


        contador_var = tk.StringVar(value="Fotos capturadas: 0/50")
        label_contador = tk.Label(controles_frame, textvariable=contador_var,
                                  font=("Arial", 10, "bold"),
                                  bg=self.COR_SECUNDARIA, fg=self.COR_INFO)
        label_contador.pack(pady=5)

        # Frame para botões
        botoes_frame = tk.Frame(controles_frame, bg=self.COR_SECUNDARIA)
        botoes_frame.pack(pady=10)


        self.cadastro_ativo = False
        self.fotos_capturadas = []
        self.contador_fotos = 0
        self.total_fotos = 50
        self.cap_cadastro = None
        self.visualizacao_ativa = True

        def atualizar_visualizacao():

            if not self.visualizacao_ativa or not self.cap_cadastro:
                return

            try:
                ret, frame = self.cap_cadastro.read()
                if ret:

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))


                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)


                    frame_resized = cv2.resize(frame, (640, 480))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img_resized = img.resize((640, 320))
                    imgtk = ImageTk.PhotoImage(image=img_resized)
                    label_camera.imgtk = imgtk
                    label_camera.configure(image=imgtk, text="")


                if self.visualizacao_ativa and janela_cadastro.winfo_exists():
                    janela_cadastro.after(30, atualizar_visualizacao)
            except Exception as e:
                if janela_cadastro.winfo_exists():
                    label_camera.config(text="Erro na câmera")

        def iniciar_captura():

            if not nome_var.get().strip():
                messagebox.showerror("Erro", "Digite o nome da pessoa!")
                return

            pessoa_nome = nome_var.get().strip()
            pessoa_tipo = tipo_var.get()
            pessoa_id = int(id_var.get())


            if pessoa_id in self.nomes:
                messagebox.showwarning("Aviso", f"ID {pessoa_id} já está em uso!")
                return


            btn_iniciar.config(state=tk.DISABLED)
            btn_cancelar.config(state=tk.DISABLED)
            self.cadastro_ativo = True


            thread_captura = threading.Thread(
                target=self.realizar_captura_fotos,
                args=(pessoa_id, pessoa_nome, pessoa_tipo, contador_var, janela_cadastro),
                daemon=True
            )
            thread_captura.start()

        def finalizar_cadastro():

            self.cadastro_ativo = False
            self.visualizacao_ativa = False
            if self.cap_cadastro:
                self.cap_cadastro.release()
                self.cap_cadastro = None
            janela_cadastro.destroy()

        def iniciar_visualizacao():

            try:
                if self.camera_atual:
                    self.cap_cadastro = cv2.VideoCapture(self.camera_atual['index'])
                    if self.cap_cadastro.isOpened():
                        self.visualizacao_ativa = True
                        self.cap_cadastro.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        self.cap_cadastro.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        atualizar_visualizacao()
                    else:
                        label_camera.config(text=" Não foi possível abrir a câmera")
                else:
                    label_camera.config(text=" Nenhuma câmera selecionada")
            except Exception as e:
                label_camera.config(text=f" Erro: {str(e)}")


        btn_iniciar = tk.Button(botoes_frame, text="🎬 INICIAR CAPTURA", command=iniciar_captura,
                                bg=self.COR_SUCESSO, fg="white", font=("Arial", 10, "bold"),
                                padx=15, pady=8, relief=tk.FLAT, cursor="hand2", width=15)
        btn_iniciar.pack(side=tk.LEFT, padx=10)

        btn_cancelar = tk.Button(botoes_frame, text=" CANCELAR", command=finalizar_cadastro,
                                 bg=self.COR_ERRO, fg="white", font=("Arial", 10, "bold"),
                                 padx=15, pady=8, relief=tk.FLAT, cursor="hand2", width=15)
        btn_cancelar.pack(side=tk.LEFT, padx=10)


        janela_cadastro.after(100, iniciar_visualizacao)

        # Configurar fechamento da janela
        janela_cadastro.protocol("WM_DELETE_WINDOW", finalizar_cadastro)

    def realizar_captura_fotos(self, pessoa_id, pessoa_nome, pessoa_tipo, contador_var, janela_cadastro):

        try:
            self.log(f" Iniciando captura para: {pessoa_nome} (ID: {pessoa_id})", self.COR_CADASTRO)


            dataset_dir = "dataset"
            if not os.path.exists(dataset_dir):
                os.makedirs(dataset_dir)

            user_dir = f"{dataset_dir}/User_{pessoa_id}"
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)


            if self.cap_cadastro is None or not self.cap_cadastro.isOpened():
                if self.camera_atual is None:
                    if janela_cadastro.winfo_exists():
                        janela_cadastro.after(0, lambda: messagebox.showerror("Erro", "Câmera não disponível!"))
                    return

                self.cap_cadastro = cv2.VideoCapture(self.camera_atual['index'])
                if not self.cap_cadastro.isOpened():
                    if janela_cadastro.winfo_exists():
                        janela_cadastro.after(0,
                                              lambda: messagebox.showerror("Erro", "Não foi possível abrir a câmera!"))
                    return

            self.contador_fotos = 0
            self.fotos_capturadas = []


            self.cap_cadastro.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap_cadastro.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            tempo_inicio = time.time()
            tempo_limite = 60  # 1 minuto para capturar 50 fotos

            while (self.cadastro_ativo and
                   self.contador_fotos < self.total_fotos and
                   time.time() - tempo_inicio < tempo_limite):

                ret, frame = self.cap_cadastro.read()
                if not ret:
                    break


                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))

                # Capturar foto quando face for detectada
                if len(faces) == 1:  # Apenas se houver UMA face
                    (x, y, w, h) = faces[0]
                    face_img = gray[y:y + h, x:x + w]

                    # Verificar se a face tem tamanho mínimo
                    if w > 80 and h > 80:
                        face_img = cv2.resize(face_img, (200, 200))


                        foto_filename = f"{user_dir}/{pessoa_id}_{self.contador_fotos:03d}.jpg"
                        cv2.imwrite(foto_filename, face_img)
                        self.fotos_capturadas.append(face_img)
                        self.contador_fotos += 1


                        if janela_cadastro.winfo_exists():
                            janela_cadastro.after(0, lambda: contador_var.set(
                                f"Fotos capturadas: {self.contador_fotos}/{self.total_fotos}"))

                        # Pequeno delay entre fotos
                        time.sleep(0.2)

                # Pequeno delay para não sobrecarregar
                time.sleep(0.03)


            if self.contador_fotos >= self.total_fotos:
                self.log(f" Captura concluída: {self.contador_fotos} fotos para {pessoa_nome}", self.COR_SUCESSO)

                # Salvar dados da pessoa
                self.nomes[pessoa_id] = {
                    'nome': pessoa_nome,
                    'tipo': pessoa_tipo,
                    'data_cadastro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'fotos': self.contador_fotos
                }


                self.salvar_nomes()
                self.atualizar_lista()


                if janela_cadastro.winfo_exists():
                    janela_cadastro.after(0, lambda: self.mostrar_mensagem_sucesso(
                        janela_cadastro, pessoa_nome, pessoa_id, pessoa_tipo
                    ))
            else:
                if janela_cadastro.winfo_exists():
                    fotos_capturadas = self.contador_fotos
                    if fotos_capturadas > 0:

                        resposta = messagebox.askyesno(
                            "Captura Incompleta",
                            f"Capturou apenas {fotos_capturadas}/{self.total_fotos} fotos.\n"
                            f"Deseja salvar mesmo assim?"
                        )
                        if resposta:
                            self.salvar_pessoa_incompleta(pessoa_id, pessoa_nome, pessoa_tipo, fotos_capturadas)
                            janela_cadastro.destroy()
                        else:

                            if os.path.exists(user_dir):
                                import shutil
                                shutil.rmtree(user_dir)
                    else:
                        messagebox.showwarning(
                            "Atenção",
                            f"Nenhuma foto foi capturada.\n"
                            "Verifique:\n"
                            "1. Iluminação adequada\n"
                            "2. Posição em frente à câmera\n"
                            "3. Rosto visível no quadro"
                        )

        except Exception as e:
            self.log(f" Erro durante captura: {e}", self.COR_ERRO)
            if janela_cadastro.winfo_exists():
                janela_cadastro.after(0, lambda: messagebox.showerror("Erro", f"Erro durante captura: {str(e)}"))

    def salvar_pessoa_incompleta(self, pessoa_id, pessoa_nome, pessoa_tipo, fotos_capturadas):

        try:
            self.nomes[pessoa_id] = {
                'nome': pessoa_nome,
                'tipo': pessoa_tipo,
                'data_cadastro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'fotos': fotos_capturadas,
                'incompleto': True
            }

            self.salvar_nomes()
            self.atualizar_lista()

            self.log(f"️ Pessoa {pessoa_nome} salva com {fotos_capturadas} fotos (incompleto)", self.COR_ALERTA)
            messagebox.showinfo(
                "Cadastro Parcial",
                f" Pessoa cadastrada com {fotos_capturadas} fotos.\n\n"
                f" Para melhor reconhecimento, recomenda-se:\n"
                f"1. Cadastrar novamente para mais fotos\n"
                f"2. Treinar o modelo após adicionar mais fotos"
            )

        except Exception as e:
            self.log(f" Erro ao salvar pessoa incompleta: {e}", self.COR_ERRO)

    def mostrar_mensagem_sucesso(self, janela_cadastro, nome, id_pessoa, tipo):
        """Mostra mensagem de sucesso após cadastro"""
        mensagem = (
            f" PESSOA CADASTRADA COM SUCESSO!\n\n"
            f" Nome: {nome}\n"
            f" ID: {id_pessoa}\n"
            f" Tipo: {tipo}\n"
            f" Fotos: {self.contador_fotos}/50\n\n"
            f"️ Lembre-se de treinar o modelo para reconhecer a nova pessoa!"
        )

        messagebox.showinfo("Cadastro Concluído", mensagem)
        janela_cadastro.destroy()

    def salvar_nomes(self):

        try:

            trainer_dir = "trainer"
            if not os.path.exists(trainer_dir):
                os.makedirs(trainer_dir)


            with open(f'{trainer_dir}/names.pkl', 'wb') as f:
                pickle.dump(self.nomes, f)

            self.log(f"✓ Dados salvos: {len(self.nomes)} pessoa(s)", self.COR_SUCESSO)
        except Exception as e:
            self.log(f" Erro ao salvar nomes: {e}", self.COR_ERRO)

    def treinar_modelo(self):
        """Treina o modelo de reconhecimento facial"""
        try:
            self.label_status_treinamento.config(text=" Buscando dados...", fg=self.COR_INFO)
            self.btn_treinar.config(state=tk.DISABLED, text=" TREINANDO...")
            self.root.update()

            dataset_dir = "dataset"
            if not os.path.exists(dataset_dir):
                self.log(" Diretório 'dataset' não encontrado!", self.COR_ERRO)
                self.label_status_treinamento.config(text="❌ Nenhum dado encontrado", fg=self.COR_ERRO)
                self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")
                messagebox.showwarning("Aviso", "Nenhuma pessoa cadastrada ainda!")
                return


            user_dirs = [d for d in os.listdir(dataset_dir) if d.startswith("User_")]
            if not user_dirs:
                self.log(" Nenhuma pessoa para treinar!", self.COR_ERRO)
                self.label_status_treinamento.config(text="❌ Nenhuma pessoa", fg=self.COR_ERRO)
                self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")
                messagebox.showwarning("Aviso", "Nenhuma pessoa cadastrada ainda!")
                return

            faces = []
            labels = []

            self.log(f" Encontradas {len(user_dirs)} pessoa(s) para treinar", self.COR_INFO)


            for user_dir in user_dirs:
                try:
                    user_id = int(user_dir.replace("User_", ""))
                    user_path = os.path.join(dataset_dir, user_dir)

                    if not os.path.isdir(user_path):
                        continue


                    images = [f for f in os.listdir(user_path) if f.endswith(('.jpg', '.png'))]

                    if len(images) < 10:
                        self.log(f"  ️ User_{user_id}: Apenas {len(images)} imagens (mínimo recomendado: 10)",
                                 self.COR_ALERTA)
                    else:
                        self.log(f"  User_{user_id}: {len(images)} imagens", self.COR_INFO)

                    for image_name in images:
                        image_path = os.path.join(user_path, image_name)
                        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

                        if img is not None:

                            img_resized = cv2.resize(img, (200, 200))
                            img_equalized = cv2.equalizeHist(img_resized)
                            faces.append(img_equalized)
                            labels.append(user_id)

                except Exception as e:
                    self.log(f"   Erro em {user_dir}: {e}", self.COR_ERRO)

            if len(faces) == 0:
                self.log(" Nenhuma imagem válida encontrada!", self.COR_ERRO)
                self.label_status_treinamento.config(text=" Nenhuma imagem", fg=self.COR_ERRO)
                self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")
                messagebox.showwarning("Aviso", "Nenhuma imagem válida para treinamento!")
                return

            self.log(f" Total: {len(faces)} imagens para treinar", self.COR_INFO)


            if self.recognizer is None:
                self.recognizer = self.criar_recognizer_simples()

            # Treinar modelo
            self.label_status_treinamento.config(text=" Treinando modelo...", fg=self.COR_ALERTA)
            self.root.update()

            success = self.recognizer.train(faces, labels)

            if success:

                trainer_dir = "trainer"
                if not os.path.exists(trainer_dir):
                    os.makedirs(trainer_dir)


                model_data = {
                    'faces': faces,
                    'labels': labels
                }

                with open(f'{trainer_dir}/model_data.pkl', 'wb') as f:
                    pickle.dump(model_data, f)

                # Criar arquivo YML para compatibilidade
                with open(f'{trainer_dir}/trainer.yml', 'w') as f:
                    f.write("# Modelo treinado\n")

                self.label_status_treinamento.config(text=" Modelo treinado!", fg=self.COR_SUCESSO)
                self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")

                self.log(f" Modelo treinado com {len(faces)} imagens de {len(set(labels))} pessoa(s)!",
                         self.COR_SUCESSO)

                # Mostrar mensagem de sucesso
                messagebox.showinfo(
                    " Treinamento Concluído",
                    f" MODELO TREINADO COM SUCESSO!\n\n"
                    f" Estatísticas:\n"
                    f"• Pessoas: {len(set(labels))}\n"
                    f"• Imagens: {len(faces)}\n"
                    f"• Média por pessoa: {len(faces) // len(set(labels)) if set(labels) else 0}\n\n"
                    f" O sistema está pronto para reconhecimento!"
                )

            else:
                self.label_status_treinamento.config(text=" Falha no treinamento", fg=self.COR_ERRO)
                self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")
                self.log(" Falha ao treinar modelo!", self.COR_ERRO)
                messagebox.showerror("Erro", "Falha ao treinar modelo!")

        except Exception as e:
            self.log(f" Erro no treinamento: {e}", self.COR_ERRO)
            self.label_status_treinamento.config(text=" Erro no treinamento", fg=self.COR_ERRO)
            self.btn_treinar.config(state=tk.NORMAL, text=" TREINAR SISTEMA")
            messagebox.showerror("Erro", f"Erro no treinamento: {str(e)}")

    def limpar_dados(self):

        if not messagebox.askyesno("Confirmação",
                                   " ATENÇÃO!\n\n"
                                   "Isso irá remover TODOS os dados:\n"
                                   "• Todas as pessoas cadastradas\n"
                                   "• Todas as fotos do dataset\n"
                                   "• Modelo treinado\n\n"
                                   "Tem certeza que deseja continuar?"):
            return

        try:

            if self.sistema_ativo:
                self.parar_sistema()


            dataset_dir = "dataset"
            if os.path.exists(dataset_dir):
                import shutil
                shutil.rmtree(dataset_dir)
                self.log(" Dataset removido", self.COR_INFO)


            trainer_dir = "trainer"
            if os.path.exists(trainer_dir):
                import shutil
                shutil.rmtree(trainer_dir)
                self.log(" Modelos removidos", self.COR_INFO)

            # Limpar variáveis
            self.nomes = {}
            self.recognizer = None
            self.estatisticas = {'reconhecimentos': 0, 'desconhecidos': 0, 'alertas': 0}
            self.ultimo_alarme = {}

            # Atualizar interface
            self.atualizar_lista()
            self.label_status_treinamento.config(text=" Sistema limpo", fg=self.COR_SUCESSO)

            self.log("Todos os dados foram removidos!", self.COR_SUCESSO)
            messagebox.showinfo("Sucesso", " Todos os dados foram removidos com sucesso!")

        except Exception as e:
            self.log(f" Erro ao limpar dados: {e}", self.COR_ERRO)
            messagebox.showerror("Erro", f"Erro ao limpar dados: {str(e)}")

    def remover_pessoa(self):
        """Remove a pessoa selecionada da lista"""
        try:

            selection = self.lista_pessoas.curselection()
            if not selection:
                messagebox.showwarning("Aviso", "Selecione uma pessoa para remover!")
                return

            selected_text = self.lista_pessoas.get(selection[0])


            import re
            match = re.search(r'ID:(\d+)', selected_text)
            if not match:
                messagebox.showwarning("Aviso", "Não foi possível identificar a pessoa!")
                return

            user_id = int(match.group(1))


            if user_id in self.nomes:
                pessoa = self.nomes[user_id]
                if not messagebox.askyesno("Confirmação",
                                           f"Remover pessoa?\n\n"
                                           f"ID: {user_id}\n"
                                           f"Nome: {pessoa['nome']}\n"
                                           f"Tipo: {pessoa['tipo']}"):
                    return


                del self.nomes[user_id]


                dataset_dir = "dataset"
                user_dir = f"{dataset_dir}/User_{user_id}"
                if os.path.exists(user_dir):
                    import shutil
                    shutil.rmtree(user_dir)
                    self.log(f" Fotos de ID {user_id} removidas", self.COR_INFO)

                # Salvar alterações
                self.salvar_nomes()
                self.atualizar_lista()

                # Resetar modelo
                self.recognizer = None
                self.log(f" Pessoa ID {user_id} removida!", self.COR_SUCESSO)
                messagebox.showinfo("Sucesso", f"Pessoa ID {user_id} removida com sucesso!")

                # Sugerir retreinar
                self.log("️ Modelo precisa ser retreinado!", self.COR_ALERTA)

        except Exception as e:
            self.log(f" Erro ao remover pessoa: {e}", self.COR_ERRO)
            messagebox.showerror("Erro", f"Erro ao remover pessoa: {str(e)}")

    def atualizar_lista(self):

        self.lista_pessoas.delete(0, tk.END)
        if self.nomes:
            for user_id, info in sorted(self.nomes.items()):
                icone = "" if info['tipo'] == "CRIMINOSO" else "✓"
                texto = f"{icone} ID:{user_id} - {info['nome']} ({info['tipo']})"
                if 'fotos' in info:
                    texto += f" | 📸{info['fotos']} fotos"
                if 'incompleto' in info and info['incompleto']:
                    texto += " ️"
                self.lista_pessoas.insert(tk.END, texto)
        else:
            self.lista_pessoas.insert(tk.END, "Nenhuma pessoa cadastrada")

    def iniciar_sistema(self):

        if not self.camera_atual:
            messagebox.showwarning("Aviso", "Selecione uma câmera!")
            return

        if self.recognizer is None or len(self.nomes) == 0:
            messagebox.showwarning("Aviso", "Treine o modelo primeiro!")
            return

        self.sistema_ativo = True
        self.label_status.config(text=" ONLINE", fg=self.COR_SUCESSO)
        self.log(f" Sistema iniciado", self.COR_SUCESSO)

        self.btn_iniciar.config(state=tk.DISABLED)
        self.btn_parar.config(state=tk.NORMAL)
        self.btn_cadastrar.config(state=tk.DISABLED)

        self.thread_camera = threading.Thread(target=self.processar_camera, daemon=True)
        self.thread_camera.start()

    def processar_camera(self):

        self.cam = cv2.VideoCapture(self.camera_atual['index'])
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not self.cam.isOpened():
            messagebox.showerror("Erro", "Não foi possível abrir a câmera!")
            self.parar_sistema()
            return

        self.log(" Processando câmera...", self.COR_INFO)

        while self.sistema_ativo:
            ret, frame = self.cam.read()
            if not ret:
                break

            frame = self.detectar_faces(frame)
            self.atualizar_video(frame)
            time.sleep(0.03)

        if self.cam:
            self.cam.release()

    def detectar_faces(self, frame):

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if self.face_cascade is None:
                self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(80, 80)
            )

            for (x, y, w, h) in faces:
                face_roi = gray[y:y + h, x:x + w]
                face_resized = cv2.resize(face_roi, (200, 200))
                face_resized = cv2.equalizeHist(face_resized)

                try:
                    user_id, confidence = self.recognizer.predict(face_resized)

                    if user_id != -1 and user_id in self.nomes and confidence <= self.confidence_threshold:

                        pessoa = self.nomes[user_id]
                        self.estatisticas['reconhecimentos'] += 1

                        if pessoa['tipo'] == "CRIMINOSO":

                            cor = (0, 0, 255)  # Vermelho
                            texto = f"CRIMINOSO: {pessoa['nome']}"

                            # Verificar cooldown (alarme a cada 10 segundos por pessoa)
                            current_time = time.time()
                            cooldown = 10  # segundos

                            if user_id not in self.ultimo_alarme or \
                                    current_time - self.ultimo_alarme[user_id] > cooldown:


                                self.ultimo_alarme[user_id] = current_time
                                self.estatisticas['alertas'] += 1

                                # LOG DE ALERTA
                                self.log("=" * 50, self.COR_ERRO)
                                self.log(" ALERTA MÁXIMO! ", self.COR_ERRO)
                                self.log(f"CRIMINOSO DETECTADO: {pessoa['nome']}", self.COR_ERRO)
                                self.log(f"Confiança: {confidence:.1f}% | ID: {user_id}", self.COR_ERRO)
                                self.log(f"Horário: {datetime.now().strftime('%H:%M:%S')}", self.COR_ERRO)
                                self.log("=" * 50, self.COR_ERRO)

                                if self.alarme_habilitado:
                                    self.log(" ATIVANDO SIRENE POLICIAL...", self.COR_ALERTA)
                                    self.sistema_alarme.iniciar_alarme(duracao=5)


                                with open("alertas_criminosos.log", "a") as f:
                                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                                            f"ID:{user_id} | {pessoa['nome']} | "
                                            f"Conf:{confidence:.1f}%\n")


                            if int(current_time * 2) % 2 == 0:
                                cv2.rectangle(frame, (0, 0),
                                              (frame.shape[1], frame.shape[0]),
                                              (0, 0, 255), 15)
                        else:

                            cor = (0, 255, 0)  # Verde
                            texto = f"CIVIL: {pessoa['nome']}"
                    else:

                        self.estatisticas['desconhecidos'] += 1
                        cor = (128, 128, 128)  # Cinza
                        texto = "DESCONHECIDO"


                    cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)


                    cv2.rectangle(frame, (x, y - 30), (x + w, y), cor, -1)

                    # Texto
                    cv2.putText(frame, texto, (x + 5, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


                    cv2.putText(frame, f"Conf: {confidence:.1f}",
                                (x + 5, y + h + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1)

                except Exception as e:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        except Exception as e:
            self.log(f" Erro na detecção: {e}", self.COR_ERRO)

        return frame

    def atualizar_video(self, frame):

        try:
            frame_resized = cv2.resize(frame, (640, 480))
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)

            self.label_video.imgtk = imgtk
            self.label_video.configure(image=imgtk)
        except:
            pass

    def parar_sistema(self):

        self.sistema_ativo = False
        self.label_status.config(text=" OFFLINE", fg=self.COR_ERRO)
        self.log(" Sistema parado", self.COR_ERRO)


        self.sistema_alarme.parar_alarme()

        if hasattr(self, 'estatisticas'):
            total = self.estatisticas['reconhecimentos'] + self.estatisticas['desconhecidos']
            if total > 0:
                self.log(f" Estatísticas: {self.estatisticas['reconhecimentos']} reconhecidos, "
                         f"{self.estatisticas['desconhecidos']} desconhecidos, "
                         f"{self.estatisticas['alertas']} alertas",
                         self.COR_INFO)

        self.btn_iniciar.config(state=tk.NORMAL)
        self.btn_parar.config(state=tk.DISABLED)
        self.btn_cadastrar.config(state=tk.NORMAL)

        if self.cam:
            self.cam.release()
            self.cam = None

        self.label_video.config(text=" CÂMERA DESCONECTADA", image="")

    def log(self, mensagem, cor=None):

        timestamp = datetime.now().strftime("%H:%M:%S")

        if cor:
            self.texto_log.tag_config(cor, foreground=cor)
            self.texto_log.insert(tk.END, f"[{timestamp}] ", "white")
            self.texto_log.insert(tk.END, f"{mensagem}\n", cor)
        else:
            self.texto_log.insert(tk.END, f"[{timestamp}] {mensagem}\n")

        self.texto_log.see(tk.END)

    def fechar(self):

        self.parar_sistema()
        self.sistema_alarme.parar_alarme()
        time.sleep(0.5)
        self.root.destroy()


#
if __name__ == "__main__":
    print("=" * 70)
    print(" SISTEMA DE RECONHECIMENTO FACIAL")
    print("=" * 70)
    print("Recursos:")
    print("✓ Reconhecimento facial em tempo real")
    print("✓ Alarme sonoro ao detectar criminosos")
    print("✓ Cadastro completo de pessoas (fotos + dados)")
    print("✓ IMPORTAR FOTOS do computador para pessoas existentes")
    print("✓ VISUALIZAR FOTOS cadastradas de cada pessoa")
    print("✓ Remoção de pessoas da lista")
    print("✓ Treinamento do modelo")
    print("✓ Interface gráfica moderna")
    print("✓ Captura de 50 fotos por pessoa")
    print("=" * 70)

    root = tk.Tk()
    app = SistemaReconhecimento(root)
    root.protocol("WM_DELETE_WINDOW", app.fechar)
    root.mainloop()