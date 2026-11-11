"""Small Portuguese Windows panel. Closing it gracefully stops its own bot."""
import logging
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from app.core.contracts import EngineError
from app.main import instance_lock
from app.desktop.control import BotControl

ROOT = Path(__file__).resolve().parents[2]
STATES = {
    'inactive':('INATIVO','#b91c1c','Alfredo está desligado. Clique em Ligar Alfredo.'),
    'starting':('LIGANDO','#b45309','Conectando ao Telegram. Aguarde a confirmação.'),
    'active':('ATIVO','#047857','Alfredo está conectado ao Telegram e aguardando mensagens.'),
    'stopping':('DESLIGANDO','#b45309','Aguardando a operação em andamento terminar com segurança.'),
    'unavailable':('SEM CONEXÃO','#b45309','A conexão falhou. Alfredo está tentando reconectar.'),
    'failed':('FALHA','#b91c1c','Não foi possível manter Alfredo ligado. Confira o código abaixo.'),
    'external':('OUTRA EXECUÇÃO','#b45309','O bot está aberto fora deste painel. Encerre essa execução para controlá-lo aqui.'),
    'unknown':('ESTADO INDISPONÍVEL','#b45309','Não foi possível verificar o estado. Nenhuma nova instância será iniciada.')}


def restore_panel():
    if os.name != 'nt':
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR,wintypes.LPCWSTR)
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = (wintypes.HWND,ctypes.c_int)
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    for title,_,_ in STATES.values():
        hwnd = user32.FindWindowW(None,'Alfredo - '+title)
        if hwnd:
            user32.ShowWindow(hwnd,9)
            user32.SetForegroundWindow(hwnd)
            return True
    return False


class Panel:
    def __init__(self, window, control):
        self.window, self.control, self.closing = window, control, False
        window.title('Alfredo - INATIVO')
        window.geometry('500x460')
        window.minsize(480,460)
        window.configure(bg='#f3f4f6')
        window.protocol('WM_DELETE_WINDOW',self.close)
        window.bind('<Control-l>',lambda _:control.start())
        window.bind('<Control-d>',lambda _:control.stop())
        card = tk.Frame(window,bg='white',padx=28,pady=24,highlightbackground='#e5e7eb',highlightthickness=1)
        card.pack(fill='both',expand=True,padx=20,pady=20)
        tk.Label(card,text='Alfredo',font=('Segoe UI',23,'bold'),fg='#111827',bg='white').pack(anchor='w')
        tk.Label(card,text='Vert2Go · Controle do agente',font=('Segoe UI',10),fg='#6b7280',bg='white').pack(anchor='w')
        self.status = tk.Label(card,font=('Segoe UI',23,'bold'),bg='white')
        self.status.pack(anchor='w',pady=(22,4))
        self.detail = tk.Label(card,font=('Segoe UI',10),justify='left',anchor='w',wraplength=390,bg='white',fg='#374151')
        self.detail.pack(anchor='w',fill='x')
        self.error = tk.Label(card,font=('Segoe UI',9),bg='white',fg='#6b7280',anchor='w')
        self.error.pack(anchor='w',pady=(5,14))
        buttons = tk.Frame(card,bg='white')
        buttons.pack(fill='x')
        self.start_button = tk.Button(buttons,text='Ligar Alfredo',command=control.start,bg='#047857',fg='white',
                                      activebackground='#065f46',activeforeground='white',font=('Segoe UI',11,'bold'),
                                      relief='flat',padx=14,pady=9)
        self.start_button.pack(side='left',expand=True,fill='x',padx=(0,6))
        self.stop_button = tk.Button(buttons,text='Desligar Alfredo',command=control.stop,bg='#b91c1c',fg='white',
                                     activebackground='#991b1b',activeforeground='white',font=('Segoe UI',11,'bold'),
                                     relief='flat',padx=14,pady=9)
        self.stop_button.pack(side='left',expand=True,fill='x',padx=(6,0))
        tk.Label(card,text='Ctrl+L: ligar · Ctrl+D: desligar.\nPode minimizar. Fechar esta janela desliga o Alfredo.',
                 font=('Segoe UI',9),bg='white',fg='#6b7280',wraplength=390,justify='left').pack(anchor='w',pady=(17,0))
        self.refresh()

    def close(self):
        self.closing = True
        if self.control.thread is not None:
            self.control.stop()

    def refresh(self):
        state = self.control.poll()
        title,color,detail = STATES[state]
        self.window.title('Alfredo - '+title)
        self.status.configure(text='● '+title,fg=color)
        self.detail.configure(text=detail)
        self.error.configure(text='Código: '+self.control.code if self.control.code and state in ('failed','unknown') else '')
        self.start_button.configure(state='normal' if not self.closing and self.control.thread is None and state in ('inactive','failed') else 'disabled')
        self.stop_button.configure(state='normal' if self.control.thread is not None and state != 'stopping' else 'disabled')
        if self.closing and self.control.thread is None:
            self.window.destroy()
            return
        self.window.after(200,self.refresh)


def main():
    # No console is needed, and no private payload is sent to the UI or a log file.
    logging.basicConfig(handlers=[logging.NullHandler()],level=logging.INFO)
    window = None
    try:
        with instance_lock(ROOT/'data/alfredo-control'):
            window = tk.Tk()
            Panel(window,BotControl(ROOT))
            window.mainloop()
        return 0
    except (EngineError,OSError) as error:
        code = error.code if isinstance(error,EngineError) else 'control_initialization_error'
        if code == 'instance_already_running' and restore_panel():
            return 0
        if window is None:
            window = tk.Tk()
            window.withdraw()
        if code == 'instance_already_running':
            messagebox.showinfo('Alfredo','O controle já está aberto. Procure Alfredo na barra de tarefas.',parent=window)
        else:
            messagebox.showerror('Alfredo','Não foi possível abrir o controle.\nCódigo: '+code,parent=window)
        window.destroy()
        return 1
