import tkinter.simpledialog as tksd
from string import ascii_lowercase
import tkinter.filedialog as tkfd
from tkinter import ttk
import tkinter as tk
import numpy as np
import sqlite3
import random
import ctypes
import sys
import re

patterns = [r"^([^.,\n]+)$", r"^\s*(\d+)\s*$", r"^\s*(0|1)\s*$",
            r"(([^\s,[]+[^\s[]*(\s+[^\s[]+)*)\s*(\[\s*(-?\d+)\s*-\s*(-?\d+)\s*\]|"
            r"\[\s*([a-zA-Z]+)\s*-\s*([a-zA-Z]+)\s*\]|\[([^.,\n-\/][^\n-]*)\]))"]
pattern_import = r"([^.,\n]+),\s*(\d+)\s*,\s*(0|1)(\s*,\s*[^\n]+)*"
pattern_duplic_name = r"^.+(\((\d+)\))$"
pattern_sample = r"\s*([^.,\n\/]+)\s*(\/\s*(\d+))*"

expl = ["Name: Characters other than '.' and ','.",
        "Weights: Any integer.\n\t\tEqual weights = equal propability to be picked.",
        "On/Off: 0 or 1.\n\t\t0 to exclude and 1 to include in the randomizer.",
        f"Randomizer: Explanation WIP. Pattern:\n\t\t{patterns[3]}"]
helptext = """If you want to edit the completed tasks you can:\n1) Export .txt file\n2) Delete completed.db\n3) Open \
the exported .txt file with a notepad\n4) Make your edits\n5) Import the new txt file\nThe pattern needs to be the \
same as before, for them to appear."""


def minrev(anchor, tupos, *target, reverse=False, fg="SystemButtonText", fgactive="Maroon"):
    if any(target):
        if reverse:
            fg, fgactive = fgactive, fg

        def forch(i):
            for child in target:
                mrd = {'grid': ['grid_remove', 'grid'], 'pack': ['pack_forget', 'pack'],
                       'place': ['place_forget', 'place'], 'toplvl': ['withdraw', 'deiconify']}
                if child != anchor:
                    getattr(child, mrd[tupos][i])()

        if anchor['foreground'] == fg:
            anchor.config(foreground=fgactive)
            forch(1)
        elif anchor['foreground'] == fgactive:
            anchor.config(foreground=fg)
            forch(0)


def arithmise(tree):
    rows = tree.get_children()
    for row in range(1, len(rows) + 1):
        tree.set(rows[row - 1], column="No.", value=row)


def addup(w):
    s = 0
    t = 1
    for ch in w.lower()[::-1]:
        s += (ord(ch) - 96) * t
        t *= 26
    return s


def strup(ns):
    if ns <= 0:
        return ''
    s = 'a'
    e = 0
    while ns // 26 ** (e + 1) > 0:
        e += 1
        s += 'a'
    for i in range(e + 1):
        s = s[:i] + ascii_lowercase[ns // 26 ** (e - i) - 1] + s[i + 1:]
        ns = ns % 26 ** (e - i)
    return s


def export_tasks(db):
    text_file = tkfd.asksaveasfilename(title="Save File", defaultextension=".txt",
                                       filetypes=(("Text Files", "*.txt"),))
    if text_file:
        with open(text_file, 'w', encoding='utf-8') as f:
            conn = sqlite3.connect(db)
            c = conn.cursor()
            if db == "tasks.db":
                c.execute("SELECT * FROM tasks")
                tasks = c.fetchall()
                for task in tasks:
                    f.write(f"{task[0]},{task[1]},{task[2]},{task[3]}\n")
            elif db == "completed.db":
                c.execute("SELECT * FROM tasks")
                tasks = c.fetchall()
                for task in tasks:
                    f.write(f"{task[0]}\n")
            conn.commit()
            conn.close()


class NextTask(tk.Frame):
    def __init__(self, master):
        tk.Frame.__init__(self, master, bg="rosybrown")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        w = int(master.winfo_screenwidth())
        h = int(master.winfo_screenheight())
        master.update_idletasks()
        f_width = master.winfo_rootx() - master.winfo_x()
        self.rm = self.master  # rootmaster
        self.memory = None
        self.mem_output = []
        self.mem_index = 0
        self.active_task = None
        self.first_task = None
        self.score = 0
        self.focused = []
        self.held = []

        while self.rm.winfo_class() != 'Tk':
            self.rm = self.rm.master

        if __name__ == "__main__":
            # 20:menu height, 31:upborder height(fullscreen is 8 less)
            self.rm.geometry(f"{w - 900}x{h - ctypes.windll.user32.GetSystemMetrics(4) - 20 - 200}+{-f_width}+0")
            self.rm.update_idletasks()

        self.__initmenu__()

        self.tl_help = tk.Toplevel(bg='grey75')
        self.tl_help.geometry(f'{w // 4}x{h // 3}+{w // 4}+{h // 6}')
        self.tl_help.title("Helpful information")
        self.tl_help.withdraw()
        self.tl_help.protocol('WM_DELETE_WINDOW', lambda: self.tl_help.withdraw())

        lbl_1 = tk.Label(self.tl_help, text="Patterns:", font="Helvetica 12 bold", bg=self.tl_help["bg"],
                         justify="left", anchor='w')
        lbl_1.pack(fill='both')

        lbl_2 = tk.Label(self.tl_help, text=f"\t{expl[0]}\n\t{expl[1]}\n\t{expl[2]}\n\t"
                                            f"{expl[3]}\n\t",
                         bg=self.tl_help["bg"], justify="left", anchor='w')
        lbl_2.pack(fill='both')

        lbl_3 = tk.Label(self.tl_help, text=helptext, bg=self.tl_help["bg"], justify="left", anchor='w')
        lbl_3.pack(fill='both')

        f_up = tk.Frame(self, bg="rosybrown")
        f_up.grid(row=0, column=0, sticky='new')

        def bt_call1():
            if not bt_1["fg"] == "SystemButtonText" and not bt_2["fg"] == "SystemButtonText":
                pw.add(f_right)
                minrev(bt_1, "grid", *[self.tree_cl, vsb1, hsb1], fgactive="SystemButtonText", fg="#505050")
            elif bt_1["fg"] == "SystemButtonText":
                minrev(bt_1, "grid", *[self.tree_cl, vsb1, hsb1], fgactive="SystemButtonText", fg="#505050")
                pw.remove(f_right)
            else:
                minrev(bt_2, "grid", *[self.txt_right, vsb2, hsb2], fgactive="SystemButtonText", fg="#505050")
                minrev(bt_1, "grid", *[self.tree_cl, vsb1, hsb1], fgactive="SystemButtonText", fg="#505050")

        def bt_call2():
            if not bt_1["fg"] == "SystemButtonText" and not bt_2["fg"] == "SystemButtonText":
                pw.add(f_right)
                minrev(bt_2, "grid", *[self.txt_right, vsb2, hsb2], fgactive="SystemButtonText", fg="#505050")
            elif bt_2["fg"] == "SystemButtonText":
                minrev(bt_2, "grid", *[self.txt_right, vsb2, hsb2], fgactive="SystemButtonText", fg="#505050")
                pw.remove(f_right)
            else:
                minrev(bt_1, "grid", *[self.tree_cl, vsb1, hsb1], fgactive="SystemButtonText", fg="#505050")
                minrev(bt_2, "grid", *[self.txt_right, vsb2, hsb2], fgactive="SystemButtonText", fg="#505050")

        lbl_score = tk.Label(f_up, text=f"Completed this session: {self.score}", bg="rosybrown", relief="raised")
        lbl_score.pack(fill='both', side='left', expand=True)
        self.lbl_score_all = tk.Label(f_up, text=f"Completed: ", bg="rosybrown", relief="raised")
        self.lbl_score_all.pack(fill='both', side='left', expand=True)

        bt_1 = tk.Button(f_up, text="Tasks Table", bg="#9C6F6F", activebackground="#9C6F6F", command=bt_call1)
        bt_1.pack(fill='both', side='left')

        bt_2 = tk.Button(f_up, text="Completed Tasks", bg="#9C6F6F", activebackground="#9C6F6F", fg="#505050",
                         command=bt_call2)
        bt_2.pack(fill='both', side='left')

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#D3D3D3", foreground="black", rowheight=25, fieldbackground="#D3D3D3")
        style.configure("TLabelframe", background="#D3D3D3", foreground="black")
        style.map("Treeview", background=[("selected", "#347083")])

        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.grid(row=1, column=0, sticky='nsew')

        f_left = tk.Frame(pw, bg="#D3D3D3")
        f_right = tk.Frame(pw, bg="#D3D3D3")
        f_right.columnconfigure(0, weight=1)

        pw.add(f_left, weight=1)
        pw.add(f_right)

        vsb1 = tk.Scrollbar(f_right, orient="vertical")
        hsb1 = tk.Scrollbar(f_right, orient="horizontal")

        self.tree_cl = ttk.Treeview(f_right, xscrollcommand=hsb1.set, yscrollcommand=vsb1.set, selectmode="extended")
        self.tree_cl.grid(row=0, column=0, sticky='nsew')

        vsb1.grid(row=0, column=1, sticky='nse')
        hsb1.grid(row=1, column=0, sticky='nsew')

        vsb1.config(command=self.tree_cl.yview)
        hsb1.config(command=self.tree_cl.xview)

        self.tree_cl["columns"] = ("No.", "Name", "Weight", "On/Off", "Randomizer")
        self.tree_cl["displaycolumns"] = ("No.", "Name", "Weight", "On/Off")

        self.tree_cl.heading("#0", text='', anchor='w')
        self.tree_cl.heading("No.", text="No.", anchor="center")
        self.tree_cl.heading("Name", text="Name", anchor='w')
        self.tree_cl.heading("Weight", text="Weight", anchor="center")
        self.tree_cl.heading("On/Off", text="On/Off", anchor="center")

        self.tree_cl.column("#0", width=0, stretch=False)
        self.tree_cl.column("No.", anchor="center", width=30, minwidth=15)
        self.tree_cl.column("Name", anchor='w', width=140, minwidth=30)
        self.tree_cl.column("Weight", anchor="center", width=50, minwidth=15)
        self.tree_cl.column("On/Off", anchor="center", width=40, minwidth=15)

        vsb2 = tk.Scrollbar(f_right, orient="vertical")
        hsb2 = tk.Scrollbar(f_right, orient="horizontal")

        self.txt_right = tk.Text(f_right, xscrollcommand=hsb2.set, yscrollcommand=vsb2.set, relief=tk.GROOVE,
                                 wrap="none", bg="#D3D3D3", borderwidth=5, font=('TkFixedFont', 9), state=tk.DISABLED,
                                 width=36)
        self.txt_right.grid(row=0, column=0, sticky='nsew')
        self.txt_right.grid_remove()

        vsb2.grid(row=0, column=1, sticky="nse")
        vsb2.grid_remove()
        hsb2.grid(row=1, column=0, sticky='nsew')
        hsb2.grid_remove()

        vsb2.config(command=self.txt_right.yview)
        hsb2.config(command=self.txt_right.xview)

        vsb0 = tk.Scrollbar(f_left, orient="vertical")
        hsb0 = tk.Scrollbar(f_left, orient="horizontal")

        self.txt_main = tk.Text(f_left, relief=tk.GROOVE, wrap="none", bg='black', fg='MediumSeaGreen', borderwidth=5,
                                insertbackground='white', font=('TkFixedFont', 9), xscrollcommand=hsb0.set,
                                yscrollcommand=vsb0.set)
        self.txt_main.grid(row=0, column=0, sticky='nsew')

        vsb0.grid(row=0, column=1, sticky='nse')
        hsb0.grid(row=1, column=0, sticky='nsew')

        vsb0.config(command=self.txt_main.yview)
        hsb0.config(command=self.txt_main.xview)

        def r():
            if not self.memory:
                return rt()
            output = self.memory[1]
            if self.bt_r["text"] == "roll lower":
                for k, group in enumerate(self.memory[4]):
                    if group[4]:
                        if self.mem_output[k] == int(group[4]):
                            self.mem_output[k] = int(group[5]) + 1
                        self.mem_output[k] = random.randint(int(group[4]), self.mem_output[k] - 1)
                    elif group[6]:
                        if self.mem_output[k] == group[6]:
                            self.mem_output[k] = strup(addup(group[7]) + 1)
                        self.mem_output[k] = strup(random.randint(addup(group[6]), addup(self.mem_output[k]) - 1))
                    else:
                        reg = re.findall(pattern_sample, group[8])
                        temp = [x for x in [repet[0] for repet in reg] if x != self.mem_output[k]]
                        if temp:
                            we = random.choices(temp, weights=[int(repet[2]) if repet[2] else 1 for repet in reg])[0]
                            self.mem_output[k] = we
                    output += f", {group[1]}: {self.mem_output[k]}"
            else:
                for k, group in enumerate(self.memory[4]):
                    if group[4]:
                        s = random.randint(int(group[4]), int(group[5]))
                        if int(group[4]) != int(group[5]):
                            while s == self.mem_output[k]:
                                s = random.randint(int(group[4]), int(group[5]))
                        self.mem_output[k] = s
                    elif group[6]:
                        qw = strup(random.randint(addup(group[6]), addup(group[7])))
                        if group[6] != group[7]:
                            while qw == self.mem_output[k]:
                                qw = strup(random.randint(addup(group[6]), addup(group[7])))
                        self.mem_output[k] = qw
                    else:
                        reg = re.findall(pattern_sample, group[8])
                        reg = [x for x in reg if x[0] != self.mem_output[k]]
                        if reg:
                            we = random.choices([repet[0] for repet in reg],
                                                weights=[int(repet[2]) if repet[2] else 1 for repet in reg])[0]
                            self.mem_output[k] = we
                    output += f", {group[1]}: {self.mem_output[k]}"
            self.memory[6] = output
            for ctask in [': '.join(gramh.split(': ')[1:]) for gramh in self.txt_right.get('1.0', tk.END).split('\n')]:
                if ctask == output:
                    output += " is already completed"
            self.txt_main.see(tk.END)
            self.txt_main.insert(tk.END, output + '\n')

        def rr():
            if not self.memory:
                return rt()
            output = self.memory[1]
            if not self.mem_output:
                self.mem_output.extend([0] * len(self.memory[4]))
            for k, group in enumerate(self.memory[4]):
                if k not in self.held:
                    if group[4]:
                        self.mem_output[k] = random.randint(int(group[4]), int(group[5]))
                    elif group[6]:
                        self.mem_output[k] = strup(random.randint(addup(group[6]), addup(group[7])))
                    else:
                        reg = re.findall(pattern_sample, group[8])
                        self.mem_output[k] = random.choices([repet[0] for repet in reg],
                                                            weights=[int(repet[2]) if repet[2] else 1 for repet in
                                                                     reg])[0]
                output += f", {group[1]}: {self.mem_output[k]}"
            self.memory[6] = output
            for ctask in [': '.join(gramh.split(': ')[1:]) for gramh in self.txt_right.get('1.0', tk.END).split('\n')]:
                if ctask == output:
                    output += " is already completed"
            self.txt_main.see(tk.END)
            self.txt_main.insert(tk.END, output + '\n')

        def rt():
            if len(self.tree_cl.get_children()) == 0:
                return "No tasks found. Add a new task."
            temp = []
            for iid in self.tree_cl.get_children():
                if self.tree_cl.item(iid)['values'][3]:
                    temp.append([iid] + self.tree_cl.item(iid)['values'][1:3] + [self.tree_cl.item(iid)['values'][4]])
            if not temp:
                return "All tasks are set to OFF"
            txt_routput.config(state=tk.NORMAL)
            txt_routput.delete('0.0', tk.END)
            self.memory = random.choices(temp, weights=[int(n) for n in np.array(temp)[:, 2].tolist()])[0]
            txt_routput.insert(tk.END, self.memory[3])
            txt_routput.config(state=tk.DISABLED)
            self.memory.append(re.findall(patterns[3], self.memory[3]))
            self.memory.append(list(map(lambda x: (self.memory[3].index(x), self.memory[3].index(x) + len(x)),
                                        np.array(self.memory[4])[:, 0].tolist())))
            self.memory.append('')
            self.mem_output = []
            self.mem_index = 0
            self.held = []
            temp = ((self.memory[5][0][1] + self.memory[5][0][0]) // 2 - 1) * ' '
            lbl_index.config(text='%s^' % temp)
            return rr()

        def complete():
            if not self.memory:
                return
            for ctask in [': '.join(gramh.split(': ')[1:]) for gramh in self.txt_right.get('1.0', tk.END).split('\n')]:
                if ctask == self.memory[6]:
                    self.txt_main.insert(tk.END, "Task is already completed" + '\n')
                    self.txt_main.see(tk.END)
                    return
            self.score += 1
            lbl_score.config(text=f"Completed this session: {self.score}")
            self.txt_right.config(state=tk.NORMAL)
            self.txt_right.insert(tk.END, f"{self.txt_right.index(tk.INSERT).split('.')[0]}: {self.memory[6]}\n")
            self.lbl_score_all.config(text="Completed: " + str(len(self.txt_right.get('1.0', tk.END).split('\n')) - 2))
            self.txt_right.config(state=tk.DISABLED)
            conn = sqlite3.connect("completed.db")
            c = conn.cursor()
            c.execute("INSERT INTO tasks VALUES (:task)", {"task": self.memory[6]})
            conn.commit()
            conn.close()
            self.txt_main.see(tk.END)
            self.txt_main.insert(tk.END, "Completed!\n")
            self.txt_main.see(tk.END)

        def move(n):
            if not self.memory:
                return
            if (n == - 1 and self.mem_index == 0) or (n == 1 and self.mem_index == len(self.memory[5]) - 1):
                return
            else:
                self.mem_index += n
            temp = ((self.memory[5][self.mem_index][1] + self.memory[5][self.mem_index][0]) // 2 - 1) * ' '
            lbl_index.config(text='%s^' % temp)

        def hold():
            if not self.memory:
                return
            if self.mem_index in self.held:
                txt_routput.tag_remove("hold", "1." + str(self.memory[5][self.mem_index][0]),
                                       "1." + str(self.memory[5][self.mem_index][1]))
                self.held.remove(self.mem_index)
            else:
                txt_routput.tag_add("hold", "1." + str(self.memory[5][self.mem_index][0]),
                                    "1." + str(self.memory[5][self.mem_index][1]))
                self.held.append(self.mem_index)

        f_routput = tk.Frame(self, bg="#D3D3D3")
        f_routput.grid(row=2, column=0, sticky='sew', ipady=10)

        lblu_routput_lbl = tk.Label(f_routput, text=f"Randomizer output:   ", bg="#D3D3D3", font=("Helvetica", 12))
        txt_routput = tk.Text(f_routput, height=1, spacing1=10, bg="#D3D3D3", font=("Lucida Console", 12), wrap="none")
        txt_routput.config(state=tk.DISABLED)
        txt_routput.tag_configure("hold", foreground="blue")
        lbl_index = tk.Label(f_routput, text='', bg="#D3D3D3", anchor='w', font=("Lucida Console", 12))
        bt_left = tk.Button(f_routput, text="  <  ", command=lambda: move(-1))
        bt_right = tk.Button(f_routput, text="  >  ", command=lambda: move(1))
        bt_hold = tk.Button(f_routput, text="Hold", command=hold)

        lblu_routput_lbl.grid(row=0, column=0, sticky='nsew')
        txt_routput.grid(row=0, column=1, sticky='nsew')
        lbl_index.grid(row=1, column=1, sticky='nsew')
        bt_left.grid(row=0, column=2, sticky='nsew')
        bt_right.grid(row=0, column=3, sticky='nsew')
        bt_hold.grid(row=1, column=2, columnspan=2, sticky='nsew')

        f_bot = tk.Frame(self)
        f_bot.grid(row=3, column=0, sticky='nsew')

        self.bt_r = tk.Button(f_bot, text="roll different", command=lambda: [r(), self.txt_main.see(tk.END)])
        bt_ddm = tk.Button(f_bot, text='^', command=lambda: minrev(bt_ddm, 'grid', f_li))
        bt_rr = tk.Button(f_bot, text="roll randomizer", command=lambda: [rr(), self.txt_main.see(tk.END)])
        bt_rt = tk.Button(f_bot, text="roll task", command=lambda: [rt(), self.txt_main.see(tk.END)])
        bt_clear = tk.Button(f_bot, text="clear text", command=lambda: self.txt_main.delete('1.0', tk.END))
        bt_complete = tk.Button(f_bot, text='complete', command=complete)
        bt_edit = tk.Button(f_bot, text="Edit", command=lambda: minrev(bt_edit, "grid", *[lf_c, lf_c2, lf_c_btns]))

        bt_ddm.pack(fill='both', side='left')
        self.bt_r.pack(fill='both', side='left', expand=True)
        bt_rr.pack(fill='both', side='left', expand=True)
        bt_rt.pack(fill='both', side='left', expand=True)
        bt_clear.pack(fill='both', side='left', expand=True)
        bt_complete.pack(fill='both', side='left', expand=True)
        bt_edit.pack(fill='both', side='left', expand=True)

        f_li = tk.Frame(f_routput)
        f_li.grid(row=1, column=0, sticky='sw', padx=(bt_ddm.winfo_reqwidth(), 0))
        f_li.grid_remove()

        bt_ch_rl = tk.Button(f_li, text="roll lower", command=lambda: self.bt_r.config(text="roll lower"))
        bt_ch_rd = tk.Button(f_li, text="roll different", command=lambda: self.bt_r.config(text="roll different"))

        bt_ch_rl.pack(fill='both', side='top', expand=True)
        bt_ch_rd.pack(fill='both', side='top', expand=True)

        def focus_lbl(_, lbl):
            widgets = lbl.master.winfo_children()
            entry = widgets[widgets.index(lbl) + 1]
            if entry not in self.focused:
                lbl.config(background="gray50")
                self.focused.append(entry)
            else:
                lbl.config(background="#D3D3D3")
                self.focused.remove(entry)

        lf_c = ttk.LabelFrame(self, text="Task")
        lf_c.grid(row=4, column=0, sticky='sew')
        lf_c.grid_remove()

        lbl_name = tk.Label(lf_c, text="Name:", bg="#D3D3D3")
        lbl_name.grid(row=0, column=0, ipady=7, sticky="nsew")
        lbl_name.bind('<Button-1>', lambda event: focus_lbl(event, lbl_name))
        ent_name = tk.Entry(lf_c)
        ent_name.grid(row=0, column=1, columnspan=2, pady=7, sticky="nsew")

        lbl_wgt = tk.Label(lf_c, text="Weight:", bg="#D3D3D3")
        lbl_wgt.grid(row=0, column=3, ipady=7, sticky="nsew")
        lbl_wgt.bind('<Button-1>', lambda event: focus_lbl(event, lbl_wgt))
        ent_wgt = tk.Entry(lf_c)
        ent_wgt.grid(row=0, column=4, pady=7, sticky="nsew")

        lbl_onoff = tk.Label(lf_c, text="On/Off:", bg="#D3D3D3")
        lbl_onoff.grid(row=0, column=5, ipady=7, sticky="nsew")
        lbl_onoff.bind('<Button-1>', lambda event: focus_lbl(event, lbl_onoff))
        ent_onoff = tk.Entry(lf_c)
        ent_onoff.grid(row=0, column=6, pady=7, sticky="nsew")
        lbl_onoffinfo = tk.Label(lf_c, text="=0/1", bg="#D3D3D3")
        lbl_onoffinfo.grid(row=0, column=7, padx=(0, 25), ipady=7, sticky="w")

        lf_c2 = ttk.LabelFrame(self, text="Randomizer")
        lf_c2.grid(row=5, column=0, sticky='sew')
        lf_c2.grid_remove()

        lbld_routput_lbl = tk.Label(lf_c2, text=f"Randomizer output:   ", bg="#D3D3D3", font=("Helvetica", 12))
        lbld_routput_lbl.pack(side='left', fill='both')
        lbld_routput_lbl.bind('<Button-1>', lambda event: focus_lbl(event, lbld_routput_lbl))
        self.ent_routput = tk.Entry(lf_c2, font=("Helvetica", 12))
        self.ent_routput.pack(side='left', fill='both', expand=True, padx=(0, 85))

        def update_task(_=None):
            if not self.tree_cl.selection():
                self.txt_main.insert(tk.END, f"There is no task selected. Select a task in the task table.\n")
                return
            timh = ["name = :name", "weight = :weight", "onoff = :onoff", "sqlrandomizer = :sqlrandomizer"]
            change = []
            for n, entry in enumerate([ent_name, ent_wgt, ent_onoff]):
                if not self.focused or entry in self.focused:
                    reg = re.match(patterns[n], entry.get())
                    if not reg:
                        tksd.messagebox.showerror("Error", "Unable to read input. At:\n" + expl[n])
                        entry.focus()
                        entry.selection_range(0, tk.END)
                        return
                    change.append(timh[n])
            if not self.focused or self.ent_routput in self.focused:
                rizer = self.pattern_check(self.ent_routput.get(), 2)
                if not rizer:
                    return
                change.append(timh[3])
            else:
                rizer = self.ent_routput.get()
            conn = sqlite3.connect("tasks.db")
            c = conn.cursor()
            command = "UPDATE tasks SET %s WHERE rowid = :rowid" % ','.join(change)
            for task in self.tree_cl.selection():
                c.execute(command,
                          {
                              "name": ent_name.get(),
                              "weight": ent_wgt.get(),
                              "onoff": ent_onoff.get(),
                              "sqlrandomizer": rizer,
                              "rowid": task
                          })
            command = "SELECT rowid, * FROM tasks WHERE rowid in ({0})".format(
                ', '.join('?' for _ in self.tree_cl.selection()))
            c.execute(command, self.tree_cl.selection())
            tasks = c.fetchall()
            conn.commit()
            conn.close()
            for task in tasks:
                self.tree_cl.item(task[0], text='', values=(self.tree_cl.item(task[0])['values'][0], *task[1:]))
            self.focus()

        def add_task():
            name = ent_name.get()
            for n, entry in enumerate([kid for kid in lf_c.winfo_children() if kid.winfo_class() == 'Entry']):
                reg = re.match(patterns[n], entry.get())
                if not reg:
                    tksd.messagebox.showerror("Error", "Unable to read input. Should be:\n" + expl[n])
                    entry.focus()
                    entry.selection_range(0, tk.END)
                    return
                if n == 0:
                    name = reg.group(1)
                    names = [self.tree_cl.item(iid)['values'][1] for iid in self.tree_cl.get_children()]
                    if name in names:
                        m = 0
                        reg2 = re.match(pattern_duplic_name, reg.group(1))
                        if reg2:
                            while name in names:
                                m += 1
                                name = str(int(reg2.group(2)) + m).join(name.rsplit(str(int(reg2.group(2)) + m - 1), 1))
                            continue
                        name += ' (1)'
                        while name in names:
                            m += 1
                            name = str(1 + m).join(name.rsplit(str(m), 1))
                        continue
            rizer = self.pattern_check(self.ent_routput.get(), 1)
            conn = sqlite3.connect("tasks.db")
            c = conn.cursor()
            c.execute("INSERT INTO tasks VALUES (:name, :weight, :onoff, :sqlrandomizer)",
                      {
                          "name": name,
                          "weight": ent_wgt.get(),
                          "onoff": ent_onoff.get(),
                          "sqlrandomizer": rizer
                      })
            c.execute("SELECT rowid, * FROM tasks")
            self.tree_cl.insert(parent='', index="end", iid=c.lastrowid, text='', values=(
                len(c.fetchall()), name, ent_wgt.get(), ent_onoff.get(), rizer))
            conn.commit()
            conn.close()

        def remove_selected():
            if self.tree_cl.selection() and tksd.messagebox.askyesno("Warning!", "Delete the selected tasks?"):
                conn = sqlite3.connect("tasks.db")
                c = conn.cursor()
                c.executemany("DELETE from tasks WHERE rowid=?", [(task,) for task in self.tree_cl.selection()])
                for task in self.tree_cl.selection():
                    self.tree_cl.delete(task)
                conn.commit()
                conn.close()
                arithmise(self.tree_cl)

        def up():
            rows = self.tree_cl.selection()
            for row in rows:
                self.tree_cl.move(row, self.tree_cl.parent(row), self.tree_cl.index(row) - 1)
            arithmise(self.tree_cl)

        def down():
            rows = self.tree_cl.selection()
            for row in reversed(rows):
                self.tree_cl.move(row, self.tree_cl.parent(row), self.tree_cl.index(row) + 1)
            arithmise(self.tree_cl)

        def clear_entries():
            ent_name.delete('0', tk.END)
            ent_wgt.delete('0', tk.END)
            ent_onoff.delete('0', tk.END)
            self.ent_routput.delete('0', tk.END)

        def select_task(_):
            clear_entries()
            values = self.tree_cl.item(self.active_task, 'values')
            try:
                ent_name.insert('0', values[1])
                ent_wgt.insert('0', values[2])
                ent_onoff.insert('0', values[3])
                self.ent_routput.insert('0', values[4])
            except IndexError:
                return

        lf_c_btns = tk.Frame(self, bg="#D3D3D3")
        lf_c_btns.grid(row=6, column=0, sticky='sew')
        lf_c_btns.grid_remove()

        bt_update = tk.Button(lf_c_btns, text="Update selected", command=update_task)
        bt_update.grid(row=0, column=0, pady=5, sticky='sew')

        bt_add = tk.Button(lf_c_btns, text="Add task", command=add_task)
        bt_add.grid(row=0, column=1, pady=5, sticky='sew')

        bt_remove = tk.Button(lf_c_btns, text="Remove selected", command=remove_selected)
        bt_remove.grid(row=0, column=2, pady=5, sticky='sew')

        bt_up = tk.Button(lf_c_btns, text="Move up", command=up)
        bt_up.grid(row=0, column=3, pady=5, sticky='sew')

        bt_down = tk.Button(lf_c_btns, text="Move down", command=down)
        bt_down.grid(row=0, column=4, pady=5, sticky='sew')

        bt_clear = tk.Button(lf_c_btns, text="Clear entries", command=clear_entries)
        bt_clear.grid(row=0, column=5, pady=5, sticky='sew')

        def motion(_):
            task = self.tree_cl.identify_row(self.tree_cl.winfo_pointery() - self.tree_cl.winfo_rooty())
            if not task or task == self.active_task:
                return
            if not self.first_task:
                self.first_task = self.active_task = task
                self.tree_cl.selection_toggle(task)
                return
            a = self.tree_cl.index(self.first_task)
            ac = self.tree_cl.index(self.active_task)
            c = self.tree_cl.index(task)
            kids = self.tree_cl.get_children()
            if c > ac:
                if c > a > ac:  # down from in to away
                    toggled = kids[ac:a] + kids[a + 1:c + 1]
                elif c > a:  # down and away
                    toggled = kids[ac + 1:c + 1]
                else:  # down and in
                    toggled = kids[ac:c]
            else:
                if ac > a > c:  # up from in to away
                    toggled = kids[a + 1:ac + 1] + kids[c:a]
                elif a > c:  # up and away
                    toggled = kids[c:ac]
                else:  # up and in
                    toggled = kids[c + 1:ac + 1]
            for n in toggled:
                self.tree_cl.selection_toggle(n)
            self.active_task = task

        def escape(_):
            self.tree_cl.selection_remove(self.tree_cl.selection())

        def click_press(_):
            self.first_task = self.active_task = self.tree_cl.identify_row(
                self.tree_cl.winfo_pointery() - self.tree_cl.winfo_rooty())
            self.tree_cl.bind('<Motion>', motion)

        def click_release(_):
            self.tree_cl.unbind('<Motion>')
            self.first_task = None
            if self.active_task:
                select_task(_)
            else:
                escape(_)

        def double_click(_):  # focuses the entry when clicking a value in the treeview
            x, y = self.tree_cl.winfo_pointerxy()
            self.active_task = self.tree_cl.identify_row(y - self.tree_cl.winfo_rooty())
            if self.active_task:
                column = self.tree_cl.identify_column(x - self.tree_cl.winfo_rootx())
                entry_i = [child for child in lf_c.winfo_children() if child.winfo_class() == 'Entry'][
                    int(column.strip('#')) - 2]
                entry_i.focus()
                entry_i.selection_range(0, tk.END)

        ent_name.bind('<Return>', update_task)
        ent_wgt.bind('<Return>', update_task)
        ent_onoff.bind('<Return>', update_task)
        self.ent_routput.bind('<Return>', update_task)
        self.tree_cl.bind('<Escape>', escape)
        self.tree_cl.bind('<Button-1>', click_press)
        self.tree_cl.bind('<Double-Button-1>', double_click)
        self.tree_cl.bind('<ButtonRelease-1>', click_release)

        def create_databases():
            conn = sqlite3.connect("tasks.db")  # creates databases or connects to existing
            c = conn.cursor()  # creates cursor instance
            c.execute("""CREATE TABLE if not exists tasks (
                      name text,
                      weight integer, 
                      onoff integer,
                      sqlrandomizer text)
                      """)
            conn.commit()  # without this the table is empty
            conn.close()

            conn = sqlite3.connect("completed.db")
            c = conn.cursor()
            c.execute("""CREATE TABLE if not exists tasks (
                      task text)
                      """)
            conn.commit()
            conn.close()

        def query_database():  # putting databases to view
            conn = sqlite3.connect("tasks.db")
            c = conn.cursor()
            c.execute("SELECT rowid, * FROM tasks")  # rowid is the same as oid (object id)
            tasks = c.fetchall()
            conn.commit()
            conn.close()
            for n, task in enumerate(tasks):  # note: you cant change treeview iid
                if task[4] == '':
                    self.tree_cl.insert(parent='', index="end", iid=task[0], text='', values=(
                        n + 1, task[1], task[2], task[3], "Random [1-1000]"))
                    self.txt_main.insert(tk.END, f"Task {task[1]} has no saved randomizer. Default selected\n")
                    self.txt_main.see(tk.END)
                    continue
                self.tree_cl.insert(parent='', index="end", iid=task[0], text='',
                                    values=(n + 1, task[1], task[2], task[3], task[4]))
            conn = sqlite3.connect("completed.db")
            c = conn.cursor()
            c.execute("SELECT rowid, * FROM tasks")
            tasks = c.fetchall()
            conn.commit()
            conn.close()
            self.txt_right.config(state=tk.NORMAL)
            for task in tasks:
                self.txt_right.insert(tk.END, f'{task[0]}: {task[1]}')
            self.txt_right.config(state=tk.DISABLED)

        f_left.columnconfigure(0, weight=1)
        f_left.rowconfigure(0, weight=1)
        f_right.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        lf_c.columnconfigure(0, weight=1)
        f_routput.rowconfigure(0, weight=1)
        f_routput.rowconfigure(1, weight=1)
        f_routput.columnconfigure(1, weight=1)
        for j in [lf_c, lf_c_btns]:
            for i in range(j.grid_size()[0]):
                j.columnconfigure(i, weight=1)

        create_databases()
        query_database()

        self.txt_right.config(state=tk.NORMAL)
        self.lbl_score_all.config(text="Completed: " + str(len(self.txt_right.get('1.0', tk.END).split('\n')) - 2))
        self.txt_right.config(state=tk.DISABLED)

    def pattern_check(self, target, *mode):
        if target:
            reg = re.findall(patterns[3], target)
            if reg:
                rizer = []
                for repet in reg:
                    if repet[4]:
                        if repet[4] > repet[5]:
                            self.txt_main.insert(tk.END, f"Skipped: {repet[0]}. Try: {repet[1]} ([{repet[5]}"
                                                         f"-{repet[4]}])\n")
                            continue
                        rizer.append(f"{repet[1]} [{repet[4]}-{repet[5]}]")
                    elif repet[6]:
                        if addup(repet[6]) > addup(repet[7]):
                            self.txt_main.insert(tk.END, f"Skipped: {repet[0]}. Try: {repet[1]} ([{repet[7]}"
                                                         f"-{repet[6]}])\n")
                            continue
                        rizer.append(f"{repet[1]} [{repet[6]}-{repet[7]}]")
                    else:
                        reg2 = re.findall(pattern_sample, repet[8])
                        rizer.append(
                            f"{repet[1]} [{', '.join([f'{repet2[0]}/{repet2[2]}' if repet2[2] else repet2[0] for repet2 in reg2])}]")
                rizer = ', '.join(rizer)
                if mode == 1 or mode == 2:
                    self.ent_routput.delete('0', tk.END)
                    self.ent_routput.insert('0', rizer)
                return rizer
            else:
                if mode == 1 or mode == 2:
                    self.ent_routput.focus()
                    self.ent_routput.selection_range(0, tk.END)
                if mode == 1:
                    tksd.messagebox.showerror("Error", f"Unable to read input. At:\n{expl[3]}\nUsing default instead")
                if mode == 2:
                    tksd.messagebox.showerror("Error", f"Unable to read input. At:\n{expl[3]}")
                    return
        return "Random [1-1000]"

    def import_tasks(self, db, viewer):
        text_file = tkfd.askopenfilename(title="Open File", filetypes=(("Text Files", "*.txt"),))
        if text_file:
            try:
                with open(text_file, "r", encoding='utf-8') as f:
                    conn = sqlite3.connect(db)
                    c = conn.cursor()
                    c.execute("SELECT * FROM tasks")
                    lines = f.readlines()
                    if db == "tasks.db":
                        cnames = [row[0] for row in c.fetchall()]
                        for line in lines:
                            reg = re.match(pattern_import, line)
                            if reg and reg[1] not in cnames:
                                rizer = self.pattern_check(reg[4], 3)
                                c.execute("INSERT INTO tasks VALUES (:name, :weight, :onoff, :sqlrandomizer)",
                                          {
                                              "name": reg[1],
                                              "weight": reg[2],
                                              "onoff": reg[3],
                                              "sqlrandomizer": rizer
                                          })
                                c.execute("SELECT * FROM tasks")
                                viewer.insert(parent='', index="end", iid=c.lastrowid, text='',
                                              values=(len(c.fetchall()), reg[1], reg[2], reg[3], rizer))
                    elif db == "completed.db":
                        ctasks = [row[0] for row in c.fetchall()]
                        viewer.config(state=tk.NORMAL)
                        for line in lines:
                            if line not in ctasks and re.match(r"\S", line):
                                c.execute("INSERT INTO tasks VALUES (:task)", {"task": line})
                                c.execute("SELECT * FROM tasks")
                                viewer.insert(tk.END, f"{c.lastrowid}: {line}")
                                ctasks.append(line)
                        viewer.config(state=tk.DISABLED)
                    conn.commit()
                    conn.close()
                    self.lbl_score_all.config(
                        text="Completed: " + str(len(self.txt_right.get('1.0', tk.END).split('\n')) - 2))
            except FileNotFoundError:
                tksd.messagebox.showerror("Error", f"{text_file} file not found")

    def __initmenu__(self):
        # Managing multiple menubars
        mm = self.master  # menumaster
        while True:
            mmchildren = list(map(lambda x: x.winfo_class(), mm.winfo_children()))
            if 'Menu' in mmchildren:
                menubar = mm.winfo_children()[mmchildren.index('Menu')]
                menubar.add_separator()
                break
            elif mm.winfo_class() == 'Tk':
                menubar = tk.Menu(self)
                mm.config(menu=menubar)
                break
            mm = mm.master

        filemenu = tk.Menu(menubar, tearoff=0)

        filemenu.add_command(label="Import tasks", command=lambda: self.import_tasks("tasks.db", self.tree_cl))
        filemenu.add_command(label="Export tasks", command=lambda: export_tasks("tasks.db"))
        filemenu.add_separator()
        filemenu.add_command(label="Import completed tasks", command=lambda: self.import_tasks("completed.db",
                                                                                               self.txt_right))
        filemenu.add_command(label="Export completed tasks", command=lambda: export_tasks("completed.db"))

        if __name__ == '__main__':
            titles = ["File", "Help"]
            filemenu.add_separator()
            filemenu.add_command(label="Exit", command=self.network)
        else:
            titles = ["File-Nt", "Help-Nt"]

        menubar.add_cascade(label=titles[0], menu=filemenu)
        menubar.add_command(label=titles[1], command=lambda: self.tl_help.deiconify())

    def network(self):
        if __name__ == '__main__':
            self.rm.destroy()
            sys.exit()
        else:
            self.destroy()


if __name__ == '__main__':
    try:  # >= win 8.1
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:  # win 8.0 or less
        ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    NextTask(root).grid(sticky='nsew')
    root.title('Next Task')
    root.mainloop()
