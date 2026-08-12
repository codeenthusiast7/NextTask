from pathlib import Path
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QDialog,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTreeView, QFileDialog,
    QMessageBox, QSplitter, QFrame, QSizePolicy, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QStandardItemModel, QStandardItem, QCursor
from PySide6.QtCore import Qt, QItemSelectionModel, QSortFilterProxyModel
import sys
import sqlite3
import random
import re
from string import ascii_lowercase
import numpy as np
from datetime import datetime


os.chdir(Path(__file__).resolve().parent)

if sys.platform == "win32":
    default_fg = "SystemButtonText"
else:
    default_fg = "#000000"
inactive_fg = "#505050"

fmt = QTextCharFormat()
fmt.setForeground(QColor("blue"))
default_fmt = QTextCharFormat()
default_fmt.setForeground(QColor("black"))

patterns = [r"^(?P<name>[^,\n]+)$", r"^\s*(?P<weight>\d+)\s*$", r"^\s*(?P<onoff>0|1)\s*$",
            r"(?P<match>(?P<name>[^\s,[]+[^\s[]*(?:\s+[^\s[]+)*)\s*(?:\[\s*(?P<num_lo>-?\d+)\s*-\s*(?P<num_hi>-?\d+)\s*\]|"
            r"\[\s*(?P<str_lo>[a-zA-Z]+)\s*-\s*(?P<str_hi>[a-zA-Z]+)\s*\]|\[(?P<choices>\s*[^,\n\]]+(?:\s*,\s*[^,\n\]]+)*\s*)\]))"]
pattern_import_tasks = r"(?P<row_pos>\d+)\s*,\s*(?P<name>[^,\n]+)\s*,\s*(?P<options>(?P<weight>\d+)\s*,\s*(?P<onoff>0|1)\s*,\s*(?P<rizer>[^\n]+)*)?"
pattern_import_ctasks = r"(?P<name>[^,\n]+)\s*,\s*(?P<task>[^,\n]+)\s*,\s*(?P<datetime>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})?"
pattern_duplic_name = r"^.+\((?P<num_dupe>\d+)\)$"
pattern_sample = r"\s*(?P<name>[^,\n\/]+)\s*(?:\/\s*(?P<weight>\d+))*"

expl = ["Name: Characters other than '.' and ','.",
        "Weights: Any integer.\n\tEqual weights = equal propability to be picked.",
        "On/Off: 0 or 1.\n\t0 to exclude and 1 to include in the randomizer.",
        f"Randomizer: Explanation WIP. Pattern:\n\t{patterns[3]}"]
helptext = f"""
Patterns:   {expl[0]}
            {expl[1]}
            {expl[2]}
            {expl[3]}

If you want to edit the completed tasks you can:\n1) Export .txt file\n2) Delete completed.db\n3) Open \
the exported .txt file with a notepad\n4) Make your edits\n5) Import the new txt file\nThe pattern needs to be the \
same as before, for them to appear.

version 2.0
"""

button_style_tabs = """
    QPushButton {
        background-color: #9C6F6F;
        color: %s;
    }
    QPushButton:hover {
        background-color: #8b5f5f;
    }
"""


def cleanup():
    if w.movedRows:
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('SELECT rowid, * FROM tasks')
        tasks = c.fetchall()
        for task in tasks:
            for row in range(w.tree_model.rowCount()):
                iid = w.tree_model.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if task[0] != iid:
                    continue
                row_pos = int(w.tree_model.item(row, 0).text())
                if task[1] == row_pos:
                    break
                command = "UPDATE tasks SET row_pos = :row_pos WHERE rowid = :rowid"
                c.execute(command, 
                          {
                            'row_pos': row_pos,
                            'rowid': task[0]
                          })
                break
        conn.commit()
        conn.close()


def arithmise(model):
    for row in range(model.rowCount()):
        item = model.item(row, 0)

        if item.text() != str(row + 1):
            item.setText(str(row + 1))
            item.setData(row + 1, Qt.ItemDataRole.UserRole + 1)

    if not w.movedRows:
        w.movedRows = True


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
    fname, _ = QFileDialog.getSaveFileName(w, 'Save File', filter='Text Files (*.txt)')
    if fname:
        with open(fname, 'w', encoding='utf-8') as f:
            conn = sqlite3.connect(db)
            c = conn.cursor()
            if db == 'tasks.db':
                c.execute('SELECT * FROM tasks')
                tasks = c.fetchall()
                tasks.sort(key=lambda task: int(task[0]))
                for task in tasks:
                    f.write(f"{task[0]}, {task[1]}, {task[2]}, {task[3]}, {task[4]}\n")
            elif db == 'completed.db':
                c.execute('SELECT * FROM tasks')
                for ctask in c.fetchall():
                    f.write(f"{ctask[0]}, {ctask[1]}, {ctask[2]}\n")
            conn.close()


def focus_lbl(_, lbl):
    widgets = lbl.parentWidget().findChildren(
        QWidget,
        options=Qt.FindChildOption.FindDirectChildrenOnly
    )
    entry = widgets[widgets.index(lbl) + 1]
    if entry not in w.focused:
        lbl.setStyleSheet("background-color: gray;")
        w.focused.append(entry)
    else:
        lbl.setStyleSheet("background-color: #D3D3D3;")
        w.focused.remove(entry)


class TaskSortModel(QSortFilterProxyModel):
    def lessThan(self, left, right):
        if left.column() == 0:
            return left.data(Qt.ItemDataRole.UserRole + 1) < right.data(
                Qt.ItemDataRole.UserRole + 1
            )

        return super().lessThan(left, right)


class TreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.motion_enabled = False

    def mouseMoveEvent(self, event):
        if self.motion_enabled:
            w.motion(event)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w.click_press(event)

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w.click_release(event)

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            w.escape()
        elif (
            event.key() == Qt.Key.Key_A
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            w.select_all()

        if event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_Down:
            w.active_task = w.tree.currentIndex().row() - 1
            w.select_task()
            
        super().keyPressEvent(event)


class ClickableLabel(QLabel):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            focus_lbl(event, self)

        super().mousePressEvent(event)


class NextTask(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Next Task')
        self.memory = None
        # self.memory[0] = task name
        # self.memory[1] = randomizer
        # self.memory[2] = matches, match object
        # self.memory[3] = randomizer indices
        # self.memory[4] = output

        self.mem_output = [] # only the results of output, not the names
        self.mem_index = 0
        self.active_task = None
        self.first_task = None
        self.score = 0
        self.focused = []
        self.held = []
        self.movedRows = False
        self.doubleClicked = False

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')

        import_tasks_action = file_menu.addAction('Import tasks')
        import_tasks_action.triggered.connect(lambda: self.import_tasks('tasks.db'))

        export_tasks_action = file_menu.addAction('Export tasks')
        export_tasks_action.triggered.connect(lambda: export_tasks('tasks.db'))

        file_menu.addSeparator()

        import_completed_action = file_menu.addAction('Import completed tasks')
        import_completed_action.triggered.connect(lambda: self.import_tasks('completed.db'))

        export_completed_action = file_menu.addAction('Export completed tasks')
        export_completed_action.triggered.connect(lambda: export_tasks('completed.db'))

        file_menu.addSeparator()

        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.network)

        edit_menu = menubar.addMenu('Edit')
        find_weights_action = edit_menu.addAction('Find weights based on chance')
        find_weights_action.triggered.connect(self.find_weights)

        help_menu = menubar.addAction('Help')
        help_menu.triggered.connect(lambda: QMessageBox.information(self, 'Help', helptext))

        # Top bar
        top_bar_widget = QWidget()
        main_layout.addWidget(top_bar_widget)
        top_bar_widget.setStyleSheet("background-color: rosybrown;")
        top_bar_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        top_bar = QHBoxLayout(top_bar_widget)
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        lbl_score = QLabel(f"Completed this session: {self.score}")
        top_bar.addWidget(lbl_score)
        self.lbl_score_all = QLabel("")
        top_bar.addWidget(self.lbl_score_all)


        def bt_call1():
            if f"color: {default_fg}" not in bt_tasks.styleSheet() and f"color: {default_fg}" not in bt_completed_tasks.styleSheet():
                bt_tasks.setStyleSheet(button_style_tabs % default_fg)
                right_frame.show()
                self.tree.show()
            elif f"color: {default_fg}" in bt_tasks.styleSheet():
                bt_tasks.setStyleSheet(button_style_tabs % inactive_fg)
                right_frame.hide()
                self.tree.hide()
            else:
                bt_completed_tasks.setStyleSheet(button_style_tabs % inactive_fg)
                self.tree_completed.hide()
                bt_tasks.setStyleSheet(button_style_tabs % default_fg)
                self.tree.show()

        def bt_call2():
            if f"color: {default_fg}" not in bt_tasks.styleSheet() and f"color: {default_fg}" not in bt_completed_tasks.styleSheet():
                bt_completed_tasks.setStyleSheet(button_style_tabs % default_fg)
                right_frame.show()
                self.tree_completed.show()
            elif f"color: {default_fg}" in bt_completed_tasks.styleSheet():
                bt_completed_tasks.setStyleSheet(button_style_tabs % inactive_fg)
                right_frame.hide()
                self.tree_completed.hide()
            else:
                bt_tasks.setStyleSheet(button_style_tabs % inactive_fg)
                self.tree.hide()
                bt_completed_tasks.setStyleSheet(button_style_tabs % default_fg)
                self.tree_completed.show()

        def toggle_edit_frames():
            visible = edit_frame_1.isVisible()

            edit_frame_1.setVisible(not visible)
            edit_frame_2.setVisible(not visible)

            if not visible:
                bt_edit.setStyleSheet("""
                    QPushButton {
                        color: "maroon";
                    }
                """)
            else:
                bt_edit.setStyleSheet("""
                    QPushButton {
                        color: "black";
                    }
                """)


        bt_tasks = QPushButton("Tasks Table")
        bt_tasks.setStyleSheet(button_style_tabs % default_fg)

        bt_completed_tasks = QPushButton("Completed Tasks")
        bt_completed_tasks.setStyleSheet(button_style_tabs % inactive_fg)

        top_bar.addWidget(bt_tasks)
        top_bar.addWidget(bt_completed_tasks)

        # Splitter area: left text, right tree + completed
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self.txt_main = QTextEdit(splitter)
        self.txt_main.setReadOnly(False)
        self.txt_main.setAcceptRichText(False)
        self.txt_main.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_main.setFont(QFont('TkFixedFont', 9))
        self.txt_main.setStyleSheet(
            "QTextEdit {"
            "background-color: black;"
            "color: MediumSeaGreen;"
            "border: 5px groove gray;"
            "selection-background-color: gray;"
            "selection-color: black;"
            "}"
            "QTextEdit QScrollBar:vertical {"
            "background: gray;"
            "width: 16px;"
            "margin: 0px;"
            "}"
            "QTextEdit QScrollBar::handle:vertical {"
            "background: dimgray;"
            "min-height: 24px;"            "}"
            "QTextEdit QScrollBar::handle:vertical:hover {"
            "background: lightgray;"
            "}"
            "QTextEdit QScrollBar:horizontal {"
            "background: gray;"
            "height: 16px;"
            "margin: 0px;"
            "}"
            "QTextEdit QScrollBar::handle:horizontal {"
            "background: dimgray;"
            "min-width: 24px;"            "}"
            "QTextEdit QScrollBar::handle:horizontal:hover {"
            "background: lightgray;"
            "}"
        )

        right_frame = QFrame(splitter)
        right_layout = QVBoxLayout(right_frame)

        self.tree_model = QStandardItemModel(0, 5)
        self.tree_model.setHorizontalHeaderLabels(["No.", "Name", "Weight", "On/Off", "Randomizer"])
        self.tree = TreeView()
        self.tree.setModel(self.tree_model)
        self.tree.setColumnWidth(0, 40)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 50)
        self.tree.setColumnWidth(3, 50)
        right_layout.addWidget(self.tree)
        self.proxy = TaskSortModel()
        self.proxy.setSourceModel(self.tree_model)
        self.tree.setModel(self.proxy)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setIndentation(0)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)

        self.tree_model_completed = QStandardItemModel(0, 4)
        self.tree_model_completed.setHorizontalHeaderLabels(["No.", "Name", "Task", "Date"])
        self.tree_completed = TreeView()
        self.tree_completed.setModel(self.tree_model_completed)
        self.tree_completed.setColumnWidth(0, 40)
        self.tree_completed.setColumnWidth(1, 200)
        right_layout.addWidget(self.tree_completed)
        proxy_completed = TaskSortModel()
        proxy_completed.setSourceModel(self.tree_model_completed)
        self.tree_completed.setModel(proxy_completed)
        self.tree_completed.setSortingEnabled(True)
        self.tree_completed.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree_completed.setAlternatingRowColors(True)
        self.tree_completed.setUniformRowHeights(True)
        self.tree_completed.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_completed.hide()

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # R output
        routput_frame = QFrame()
        routput_frame.setStyleSheet("background-color: #D3D3D3;")
        routput_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        routput_layout = QGridLayout(routput_frame)
        routput_layout.setSpacing(0)
        routput_layout.setContentsMargins(0, 0, 0, 0)
        lblu_routput = QLabel("Randomizer output:   ")
        lblu_routput.setStyleSheet("background-color: #D3D3D3;")
        lblu_routput.setFont(QFont("Helvetica", 12))
        txt_routput = QTextEdit()
        txt_routput.setFixedHeight(30)
        txt_routput.setReadOnly(True)
        txt_routput.setFont(QFont("DejaVu Sans Mono", 12))
        txt_routput_cursor = txt_routput.textCursor()

        main_layout.addWidget(routput_frame)
        routput_layout.addWidget(lblu_routput, 0, 0)
        routput_layout.addWidget(txt_routput, 0, 1)

        lbl_index = QLabel('')
        lbl_index.setStyleSheet("background-color: #D3D3D3;")
        lbl_index.setFont(QFont("DejaVu Sans Mono", 12))
        bt_left = QPushButton("  <  ")
        bt_right = QPushButton("  >  ")
        bt_hold = QPushButton("Hold")

        routput_layout.addWidget(lbl_index, 1, 1)
        routput_layout.addWidget(bt_left, 0, 2)
        routput_layout.addWidget(bt_right, 0, 3)
        routput_layout.addWidget(bt_hold, 1, 2, 1, 2)

        # Mid section buttons
        mid_frame = QFrame()
        mid_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(mid_frame)
        mid_layout = QHBoxLayout(mid_frame)
        mid_layout.setSpacing(0)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        bt_rl = QPushButton('roll lower')
        bt_rd = QPushButton('roll different')
        bt_rt = QPushButton('roll task')
        bt_clear = QPushButton('clear text')
        bt_complete = QPushButton('complete')
        bt_edit = QPushButton('Edit')

        mid_layout.addWidget(bt_rl)
        mid_layout.addWidget(bt_rd)
        mid_layout.addWidget(bt_rt)
        mid_layout.addWidget(bt_clear)
        mid_layout.addWidget(bt_complete)
        mid_layout.addWidget(bt_edit)


        def rl():
            if not self.memory:
                return rt()
            if not self.mem_output:
                return rd()
            output = self.memory[0]
            for k, match in enumerate(self.memory[2]):
                name = match.group("name")
                num_lo = match.group("num_lo")
                num_hi = match.group("num_hi")
                str_lo = match.group("str_lo")
                str_hi = match.group("str_hi")
                choices = match.group("choices")
                if k not in self.held:
                    if num_lo and num_hi:
                        low, high = int(num_lo), int(num_hi)
                        if self.mem_output[k] == low:
                            self.mem_output[k] = high + 1
                        self.mem_output[k] = random.randint(low, self.mem_output[k] - 1)
                    elif str_lo and str_hi:
                        if self.mem_output[k] == str_lo:
                            self.mem_output[k] = strup(addup(str_hi) + 1)
                        self.mem_output[k] = strup(random.randint(addup(str_lo), addup(self.mem_output[k]) - 1))
                    elif choices:
                        pass
                output += f", {name}: {self.mem_output[k]}"
            self.memory[4] = output
            if find_in_tree_completed(output):
                output += ' is already completed'
            self.txt_main.append(output)

        def rd():
            if not self.memory:
                return rt()
            output = self.memory[0]
            same_task = True
            if not self.mem_output:
                self.mem_output = [0] * sum(1 for _ in self.memory[2])
                same_task = False
            for k, match in enumerate(self.memory[2]):
                name = match.group("name")
                num_lo = match.group("num_lo")
                num_hi = match.group("num_hi")
                str_lo = match.group("str_lo")
                str_hi = match.group("str_hi")
                choices = match.group("choices")
                if k not in self.held:
                    if num_lo and num_hi:
                        low, high = int(num_lo), int(num_hi)
                        s = random.randint(low, high)
                        if low != high and same_task:
                            while s == self.mem_output[k]:
                                s = random.randint(low, high)
                        self.mem_output[k] = s
                    elif str_lo and str_hi:
                        low, high = addup(str_lo), addup(str_hi)
                        qw = strup(random.randint(low, high))
                        if str_lo != str_hi and same_task:
                            while qw == self.mem_output[k]:
                                qw = strup(random.randint(low, high))
                        self.mem_output[k] = qw
                    elif choices:
                        choices = list(re.finditer(pattern_sample, choices))
                        if choices:
                            if len(choices) > 1 and same_task:
                                choices = [x for x in choices if x.group('name') != self.mem_output[k]]
                            self.mem_output[k] = random.choices([choice.group('name') for choice in choices],
                                                                weights=[int(choice.group('weight')) if choice.group('weight') else 1 for choice in
                                                                        choices])[0]
                output += f", {name}: {self.mem_output[k]}"
            self.memory[4] = output
            if find_in_tree_completed(output):
                output += ' is already completed'
            self.txt_main.append(output)

        def rt():
            if self.tree_model.rowCount() == 0:
                return "No tasks found. Add a new task."
            temp = []
            for row in range(self.tree_model.rowCount()):
                item_name = self.tree_model.item(row, 1).text()
                item_weight = int(self.tree_model.item(row, 2).text())
                item_onoff = self.tree_model.item(row, 3).text()
                item_randomizer = self.tree_model.item(row, 4).text()
                if item_onoff == '1' or item_onoff == 'True':
                    temp.append([item_name, item_weight, item_randomizer])
            if not temp:
                return "All tasks are set to OFF"
            temp = random.choices(temp, weights=[int(n) for n in np.array(temp)[:, 1].tolist()])[0]
            del temp[1]  # deletes item_weight
            self.memory = temp
            txt_routput.setReadOnly(False)
            txt_routput.setPlainText(self.memory[1])
            txt_routput.setReadOnly(True)
            # finditer returns an iterator so materialize it into a list to be able to use it multiple times
            self.memory.append(list(re.finditer(patterns[3], self.memory[1])))  # self.memory[2]: matches, match object
            self.memory.append([m.span() for m in self.memory[2]])  # self.memory[3]: randomizer indices
            self.memory.append('')
            self.mem_output = []
            self.mem_index = 0
            self.held = []
            lbl_index.setText(f'{((self.memory[3][self.mem_index][1] + self.memory[3][self.mem_index][0]) // 2 - 1) * " "}^')
            rd()

        def complete():
            if not self.memory:
                return
            if find_in_tree_completed(self.memory[4]):
                self.txt_main.append('Task is already completed')
                return
            self.score += 1
            conn = sqlite3.connect('completed.db')
            c = conn.cursor()
            task_stripped = self.memory[4][(len(self.memory[0]) + 2):].lstrip()
            c.execute('INSERT INTO tasks VALUES (:name, :task, :datetime)',
                      {
                          'name': self.memory[0],
                          'task': task_stripped,
                          'datetime': datetime.now().isoformat()
                      })
            row_items = [
                QStandardItem(str(self.tree_model_completed.rowCount() + 1)),
                QStandardItem(self.memory[0]),
                QStandardItem(task_stripped),
                QStandardItem(datetime.now().strftime("%Y-%m-%d")),
            ]
            row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
            row_items[0].setData(self.tree_model_completed.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
            row_items[2].setData(self.memory[4], Qt.ItemDataRole.UserRole)
            row_items[3].setData(datetime.now(), Qt.ItemDataRole.UserRole)
            conn.commit()
            conn.close()
            self.tree_model_completed.appendRow(row_items)
            lbl_score.setText(f"Completed this session: {self.score}")
            self.lbl_score_all.setText(f'Completed: {self.tree_model_completed.rowCount()}')
            self.txt_main.append('Completed!')

        def move(n):
            if not self.memory:
                return
            if (n == - 1 and self.mem_index == 0) or (n == 1 and self.mem_index == len(self.memory[3]) - 1):
                return
            else:
                self.mem_index += n
            lbl_index.setText(f'{((self.memory[3][self.mem_index][1] + self.memory[3][self.mem_index][0]) // 2 - 1) * " "}^')

        def hold():
            if not self.memory:
                return
            if self.mem_index in self.held:
                txt_routput_cursor.setPosition(self.memory[3][self.mem_index][0])
                txt_routput_cursor.setPosition(self.memory[3][self.mem_index][1], QTextCursor.MoveMode.KeepAnchor)
                txt_routput_cursor.mergeCharFormat(default_fmt)
                self.held.remove(self.mem_index)
            else:
                txt_routput_cursor.setPosition(self.memory[3][self.mem_index][0])
                txt_routput_cursor.setPosition(self.memory[3][self.mem_index][1], QTextCursor.MoveMode.KeepAnchor)
                txt_routput_cursor.mergeCharFormat(fmt)
                self.held.append(self.mem_index)
        
        def find_in_tree_completed(word):
            for row in range(self.tree_model_completed.rowCount()):
                if self.tree_model_completed.item(row, 2).data(Qt.ItemDataRole.UserRole) == word:
                    return True
            return False


        # Editor frames for add/edit
        edit_frame_1 = QFrame()
        edit_frame_1.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(edit_frame_1)
        edit_layout_1 = QGridLayout(edit_frame_1)

        lbl_name = ClickableLabel('Name:')
        self.ent_name = QLineEdit()
        lbl_wgt = ClickableLabel('Weight:')
        self.ent_wgt = QLineEdit()
        lbl_onoff = ClickableLabel('On/Off:')
        self.ent_onoff = QLineEdit()
        lbld_routput = ClickableLabel('Randomizer:')
        self.ent_routput = QLineEdit()

        lbl_name.setStyleSheet("background-color: #D3D3D3;")
        lbl_wgt.setStyleSheet("background-color: #D3D3D3;")
        lbl_onoff.setStyleSheet("background-color: #D3D3D3;")
        lbld_routput.setStyleSheet("background-color: #D3D3D3;")

        edit_layout_1.addWidget(lbl_name, 0, 0)
        edit_layout_1.addWidget(self.ent_name, 0, 1)
        edit_layout_1.addWidget(lbl_wgt, 0, 2)
        edit_layout_1.addWidget(self.ent_wgt, 0, 3)
        edit_layout_1.addWidget(lbl_onoff, 0, 4)
        edit_layout_1.addWidget(self.ent_onoff, 0, 5)
        edit_layout_1.addWidget(lbld_routput, 1, 0)
        edit_layout_1.addWidget(self.ent_routput, 1, 1, 1, 5)

        # Bottom action buttons
        edit_frame_2 = QFrame()
        edit_frame_2.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(edit_frame_2)
        edit_layout_2 = QGridLayout(edit_frame_2)
        edit_layout_2.setSpacing(0)
        edit_layout_2.setContentsMargins(0, 0, 0, 0)
        bt_update = QPushButton('Update selected')
        bt_add = QPushButton('Add task')
        bt_remove = QPushButton('Remove selected')
        bt_up = QPushButton('Move up')
        bt_down = QPushButton('Move down')
        bt_clear = QPushButton('Clear entries')
        bt_selectall = QPushButton('Select all')

        edit_layout_2.addWidget(bt_update, 0, 0)
        edit_layout_2.addWidget(bt_add, 0, 1)
        edit_layout_2.addWidget(bt_remove, 0, 2)
        edit_layout_2.addWidget(bt_up, 0, 3)
        edit_layout_2.addWidget(bt_down, 0, 4)
        edit_layout_2.addWidget(bt_clear, 0, 5)
        edit_layout_2.addWidget(bt_selectall, 1, 0, 1, 6)

        edit_frame_1.setVisible(False)
        edit_frame_2.setVisible(False)


        def update_task():
            proxy_indexes = self.tree.selectionModel().selectedRows()
            source_indexes = [self.proxy.mapToSource(pindex) for pindex in proxy_indexes]
            selection_ids = [int(self.tree_model.itemFromIndex(sindex).text()) - 1 for sindex in source_indexes]
            if not selection_ids:
                self.txt_main.append('There is no task selected. Select a task in the task table.')
                return
            if len(selection_ids) > 1 and (not self.focused or self.ent_name in self.focused):
                if QMessageBox.warning(self, 'Warning', 'Do you really want to give multiple tasks the same name?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.Yes:
                    return
            columns = ["name",
                       "weight",
                       "onoff",
                       "randomizer"]
            changes = []
            for n, entry in enumerate([self.ent_name, self.ent_wgt, self.ent_onoff]):
                if not self.focused or entry in self.focused:
                    reg = re.match(patterns[n], entry.text())
                    if not reg:
                        QMessageBox.critical(self, 'Error', 'Unable to read input. At:\n' + expl[n])
                        entry.setFocus()
                        return
                    changes.append(columns[n])
            if not self.focused or self.ent_routput in self.focused:
                if not self.randomizer_check(self.ent_routput.text(), 2):
                    return
                changes.append("randomizer")
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            command = f"UPDATE tasks SET {','.join([f"{change} = :{change}" for change in changes])} WHERE rowid = :rowid"
            for row in selection_ids:
                c.execute(command, 
                          {
                              'name': self.ent_name.text(),
                              'weight': self.ent_wgt.text(),
                              'onoff': self.ent_onoff.text(),
                              'randomizer': self.ent_routput.text(),
                              'rowid': row + 1
                          })
            command = f"SELECT * FROM tasks WHERE rowid in ({', '.join('?' for _ in selection_ids)})"
            c.execute(command, [rowid + 1 for rowid in selection_ids])
            for task in c.fetchall():
                for column, value in enumerate(task[1:]):
                    if columns[column] in changes:
                        self.tree_model.item(task[0] - 1, column + 1).setText(str(value))
            conn.commit()
            conn.close()

        def add_task():
            name = self.ent_name.text()
            for n, entry in enumerate(edit_frame_1.findChildren(QLineEdit)):
                reg = re.match(patterns[n], entry.text())
                if not reg:
                    QMessageBox.critical(self, 'Error', 'Unable to read input. Should be:\n' + expl[n])
                    entry.setFocus()
                    return
                if n == 0:
                    name = reg.group("name")
                    names = [self.tree_model.item(row, 1).text() for row in range(self.tree_model.rowCount())]
                    if name in names:
                        m = 0
                        reg2 = re.match(pattern_duplic_name, name)
                        if reg2:
                            while name in names:
                                m += 1
                                name = str(int(reg2.group("num_dupe")) + m).join(name.rsplit(str(int(reg2.group("num_dupe")) + m - 1), 1))
                            continue
                        name += ' (1)'
                        while name in names:
                            m += 1
                            name = str(1 + m).join(name.rsplit(str(m), 1))
                        continue
            if not self.randomizer_check(self.ent_routput.text(), 2):
                return
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute('''INSERT INTO tasks VALUES
                    (
                    :row_pos,
                    :name,
                    :weight,
                    :onoff,
                    :randomizer
                    )
                ''', {
                        'row_pos': str(self.tree_model.rowCount() + 1),
                        'name': name,
                        'weight': self.ent_wgt.text(),
                        'onoff': self.ent_onoff.text(),
                        'randomizer': self.ent_routput.text(),
                    }
            )
            row_items = [
                QStandardItem(str(self.tree_model.rowCount() + 1)),
                QStandardItem(name),
                QStandardItem(self.ent_wgt.text()),
                QStandardItem(self.ent_onoff.text()),
                QStandardItem(self.ent_routput.text()),
            ]
            row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
            row_items[0].setData(self.tree_model.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
            self.tree_model.appendRow(row_items)
            conn.commit()
            conn.close()

        def remove_selected():
            proxy_indexes = self.tree.selectionModel().selectedRows()
            selection = [self.proxy.mapToSource(pindex) for pindex in proxy_indexes]
            if not selection:
                return
            if QMessageBox.question(self, 'Warning!', 'Delete the selected tasks?') != QMessageBox.Yes:
                return
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            rows = sorted({index.row() for index in selection}, reverse=True)
            for row in rows:
                row_item = self.tree_model.item(row, 0)
                rowid = int(row_item.data(Qt.ItemDataRole.UserRole))
                c.execute('DELETE from tasks WHERE rowid=?', (rowid,))
                self.tree_model.removeRow(row)
            conn.commit()
            conn.close()
            arithmise(self.tree_model)

        def up():
            selection_model = self.tree.selectionModel()
            selection = selection_model.selectedRows()

            if selection:
                header = self.tree.header()
                sort_column = None
                sort_order = None

                if header.isSortIndicatorShown():
                    sort_column = header.sortIndicatorSection()
                    sort_order = header.sortIndicatorOrder()
                    if sort_order == Qt.SortOrder.DescendingOrder:
                        selection = [self.proxy.mapToSource(pindex) for pindex in selection]
                else:
                    return

                if sort_column != 0:
                    self.txt_main.append("Moving rows only works when 'No.' column is sorted.")
                    return
                
                for index in selection:
                    row = index.row()
                    items = self.tree_model.takeRow(row)

                    if sort_order == Qt.SortOrder.AscendingOrder:
                        items[0].setText(str(row))
                        items[0].setData(row, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row - 1, items)
                    else:
                        items[0].setText(str(row + 2))
                        items[0].setData(row + 2, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row + 1, items)
                        index = self.proxy.mapFromSource(self.tree_model.index(row + 1, index.column(), index.parent()))
                    selection_model.select(
                        index,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
                    arithmise(self.tree_model)

        def down():
            selection_model = self.tree.selectionModel()
            selection = selection_model.selectedRows()

            if selection:
                header = self.tree.header()
                sort_column = None
                sort_order = None

                if header.isSortIndicatorShown():
                    sort_column = header.sortIndicatorSection()
                    sort_order = header.sortIndicatorOrder()
                    if sort_order == Qt.SortOrder.DescendingOrder:
                        selection = [self.proxy.mapToSource(pindex) for pindex in selection]
                else:
                    return

                if sort_column != 0:
                    self.txt_main.append("Moving rows only works when 'No.' column is sorted.")
                    return
                
                for index in selection:
                    row = index.row()
                    items = self.tree_model.takeRow(row)

                    if sort_order == Qt.SortOrder.AscendingOrder:
                        items[0].setText(str(row + 2))
                        items[0].setData(row + 2, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row + 1, items)
                        index = self.tree_model.index(row + 1, index.column(), index.parent())
                    else:
                        items[0].setText(str(row))
                        items[0].setData(row, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row - 1, items)
                        index = self.proxy.mapFromSource(self.tree_model.index(row - 1, index.column(), index.parent()))
                    selection_model.select(
                        index,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
                    arithmise(self.tree_model)

        def double_click(index):  # focuses the entry when clicking a value in the treeview
            if index.isValid():
                self.doubleClicked = True
                entries = edit_frame_1.findChildren(QLineEdit)
                entry = entries[index.column() - 1]
                entry.setFocus()
                entry.selectAll()


        # Connections
        bt_rl.clicked.connect(rl)
        bt_rd.clicked.connect(rd)
        bt_rt.clicked.connect(rt)
        bt_clear.clicked.connect(lambda: self.txt_main.clear())
        bt_complete.clicked.connect(complete)
        bt_edit.clicked.connect(toggle_edit_frames)
        bt_update.clicked.connect(update_task)
        bt_add.clicked.connect(add_task)
        bt_remove.clicked.connect(remove_selected)
        bt_up.clicked.connect(up)
        bt_down.clicked.connect(down)
        bt_clear.clicked.connect(self.clear_entries)
        bt_selectall.clicked.connect(self.select_all)
        bt_left.clicked.connect(lambda: move(-1))
        bt_right.clicked.connect(lambda: move(1))
        bt_hold.clicked.connect(hold)
        bt_tasks.clicked.connect(bt_call1)
        bt_completed_tasks.clicked.connect(bt_call2)
        self.ent_name.returnPressed.connect(update_task)
        self.ent_wgt.returnPressed.connect(update_task)
        self.ent_onoff.returnPressed.connect(update_task)
        self.ent_routput.returnPressed.connect(update_task)
        self.tree.doubleClicked.connect(double_click)


        def create_databases():
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE if not exists tasks (
                    row_pos integer,
                    name text,
                    weight integer,
                    onoff integer,
                    randomizer text)
                    ''')
            conn.commit()
            conn.close()
            conn = sqlite3.connect('completed.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE if not exists tasks (
                    name text,
                    task text,
                    datetime text)
                    ''')
            conn.commit()
            conn.close()

        def query_database():
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute('SELECT rowid, * FROM tasks') # rowid is first so it is task[0]
            tasks = c.fetchall()
            conn.close()
            tasks.sort(key=lambda task: int(task[1]))
            for task in tasks:
                row_items = [
                    QStandardItem(str(task[1])),
                    QStandardItem(task[2]),
                    QStandardItem(str(task[3])),
                    QStandardItem(str(task[4])),
                    QStandardItem(task[5] if task[5] else 'Random [1-1000]'),
                ]
                row_items[0].setData(task[0], Qt.ItemDataRole.UserRole)
                row_items[0].setData(task[1], Qt.ItemDataRole.UserRole + 1)
                row_items[2].setTextAlignment(Qt.AlignCenter)
                row_items[3].setTextAlignment(Qt.AlignCenter)
                self.tree_model.appendRow(row_items)

            conn = sqlite3.connect('completed.db')
            c = conn.cursor()
            c.execute('SELECT rowid, * FROM tasks')
            ctasks = c.fetchall()
            conn.close()
            for n, ctask in enumerate(ctasks):
                row_items = [
                    QStandardItem(str(n + 1)),
                    QStandardItem(ctask[1]),
                    QStandardItem(ctask[2]),
                    QStandardItem(datetime.fromisoformat(ctask[3]).strftime("%Y-%m-%d")),
                ]
                row_items[0].setData(ctask[0], Qt.ItemDataRole.UserRole)
                row_items[0].setData(n + 1, Qt.ItemDataRole.UserRole + 1)
                row_items[2].setData(f"{ctask[1]}, {ctask[2]}", Qt.ItemDataRole.UserRole)
                row_items[3].setData(datetime.fromisoformat(ctask[3]))
                self.tree_model_completed.appendRow(row_items)

        create_databases()
        query_database()

        self.lbl_score_all.setText(f'Completed: {self.tree_model_completed.rowCount()}')


    def find_weights(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Enter chance")

        layout = QVBoxLayout(dialog)

        entry = QLineEdit()
        layout.addWidget(entry)

        button = QPushButton("OK")
        layout.addWidget(button)

        button.clicked.connect(dialog.accept)

        if dialog.exec() and entry.text():
            proxy_indexes = self.tree.selectionModel().selectedRows()
            source_indexes = [self.proxy.mapToSource(pindex) for pindex in proxy_indexes]
            selection_ids = [int(self.tree_model.itemFromIndex(sindex).text()) - 1 for sindex in source_indexes]
            if not selection_ids:
                QMessageBox.critical(self, 'Error', 'No rows were selected')
                return

            chance = float(entry.text())
            if not 0.0 < chance < 1.0:
                QMessageBox.critical(self, 'Error', 'Entry chance must be between 0 and 1')
                return

            n = len(selection_ids)
            rw = 0
            for row in range(self.tree_model.rowCount()):
                if row not in selection_ids:
                    rw += int(self.tree_model.item(row, 2).text())

            weight = rw/n*chance/(1-chance)
            self.txt_main.append(f"You must edit the weights to be {weight}.")

    def select_all(self):
        selection_model = self.tree.selectionModel()

        for row in range(self.tree_model.rowCount()):
            index = self.tree_model.index(row, 0)

            if not selection_model.isSelected(index):
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select |
                    QItemSelectionModel.SelectionFlag.Rows
                )

    def clear_entries(self):
        self.ent_name.setText('')
        self.ent_wgt.setText('')
        self.ent_onoff.setText('')
        self.ent_routput.setText('')

    def select_task(self):
        values = [
            self.tree_model.item(
                self.active_task,
                column
            ).text()
            for column in range(self.tree_model.columnCount())
        ]
        try:
            self.ent_name.setText(values[1])
            self.ent_name.setCursorPosition(0)
            self.ent_wgt.setText(values[2])
            self.ent_onoff.setText(values[3])
            self.ent_routput.setText(values[4])
        except IndexError:
            return

    def motion(self, _):
        pos = self.tree.viewport().mapFromGlobal(QCursor.pos())
        pindex = self.tree.indexAt(pos)
        index = self.proxy.mapToSource(pindex)

        if not index.isValid():
            return

        task = index.row()
        if task == self.active_task:
            return
    
        if self.first_task is None:
            self.first_task = self.active_task = task
            self.tree.selectionModel().select(
                self.tree_model.index(task, 0),
                QItemSelectionModel.SelectionFlag.Toggle
                | QItemSelectionModel.SelectionFlag.Rows
            )
            return
        
        a = self.first_task
        ac = self.active_task
        c = task

        if c > ac:
            if c > a > ac:  # down from in to away
                toggled = list(range(ac, a)) + list(range(a + 1, c + 1))
            elif c > a:  # down and away
                toggled = list(range(ac + 1, c + 1))
            else:  # down and in
                toggled = list(range(ac, c))
        else:
            if ac > a > c:  # up from in to away
                toggled = list(range(a + 1, ac + 1)) + list(range(c, a))
            elif a > c:  # up and away
                toggled = list(range(c, ac))
            else:  # up and in
                toggled = list(range(c + 1, ac + 1))

        for row in toggled:
            index = self.tree_model.index(row, 0)
            self.tree.selectionModel().select(
                index,
                QItemSelectionModel.SelectionFlag.Toggle
                | QItemSelectionModel.SelectionFlag.Rows
            )
        self.active_task = task

    def escape(self):
        proxy_indexes = self.tree.selectionModel().selectedRows()
        selection = [self.proxy.mapToSource(pindex) for pindex in proxy_indexes]
        for index in selection:
            self.tree.selectionModel().select(
                index,
                QItemSelectionModel.SelectionFlag.Deselect |
                QItemSelectionModel.SelectionFlag.Rows
            )

    def click_press(self, _):
        pos = self.tree.viewport().mapFromGlobal(QCursor.pos())
        pindex = self.tree.indexAt(pos)
        index = self.proxy.mapToSource(pindex)

        self.first_task = self.active_task = index.row()
        self.tree.motion_enabled = True

    def click_release(self, _):
        self.tree.motion_enabled = False
        self.first_task = None
        if self.doubleClicked:
            self.doubleClicked = False
            return
        if self.active_task is not None:
            self.select_task()
        else:
            self.escape()

    def randomizer_check(self, target, *mode):
        if target:
            reg = list(re.finditer(patterns[3], target))
            if reg:
                rizer = []
                for repet in reg:
                    if repet.group("num_lo"):
                        if int(repet.group("num_lo")) > int(repet.group("num_hi")):
                            self.txt_main.append(f"Skipped: {repet.group('match')}. Try: {repet.group('name')} ([{repet.group('num_hi')}-{repet.group('num_lo')}])")
                            continue
                        rizer.append(f"{repet.group("name")} [{repet.group("num_lo")}-{repet.group("num_hi")}]")
                    elif repet.group("str_lo"):
                        if addup(repet.group("str_lo")) > addup(repet.group("str_hi")):
                            self.txt_main.append(f"Skipped: {repet.group('match')}. Try: {repet.group('name')} ([{repet.group('str_hi')}-{repet.group('str_lo')}])")
                            continue
                        rizer.append(f"{repet.group("name")} [{repet.group("str_lo")}-{repet.group("str_hi")}]")
                    else:
                        reg2 = list(re.finditer(pattern_sample, repet.group("choices")))
                        rizer.append(
                            f"{repet.group("name")} [{', '.join([f'{repet2.group("name")}/{repet2.group("weight")}' if repet2.group("weight") else repet2.group("name") for repet2 in reg2])}]")
                rizer = ', '.join(rizer)
                if mode == (1,) or mode == (2,):
                    self.ent_routput.setText(rizer)
                return rizer
            else:
                if mode == (1,) or mode == (2,):
                    self.ent_routput.setFocus()
                if mode == (1,):
                    QMessageBox.critical(self, 'Error', f"Unable to read input. At:\n{expl[3]}\nUsing default instead")
                if mode == (2,):
                    QMessageBox.critical(self, 'Error', f"Unable to read input. At:\n{expl[3]}")
                    return
        return 'Random [1-1000]'

    def import_tasks(self, db):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open File', filter='Text Files (*.txt)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    conn = sqlite3.connect(db)
                    c = conn.cursor()
                    c.execute('SELECT * FROM tasks')
                    rows = c.fetchall()
                    lines = f.readlines()
                    if db == 'tasks.db':
                        row_items_list = []
                        cnames = [row[1] for row in rows]
                        for line in lines:
                            reg = re.match(pattern_import_tasks, line)
                            if reg and reg.group('name') not in cnames:
                                rizer_in = self.randomizer_check(reg.group('rizer'), 3)
                                row_pos_in = reg.group('row_pos')
                                if int(row_pos_in) <= self.tree_model.rowCount():
                                    row_pos_in = self.tree_model.rowCount() + 1
                                name_in = reg.group('name')
                                if not reg.group('options'):
                                    weight_in = '1'
                                    onoff_in = '1'
                                else:
                                    weight_in = reg.group('weight')
                                    onoff_in = reg.group('onoff')
                                c.execute('INSERT INTO tasks VALUES (:row_pos, :name, :weight, :onoff, :randomizer)',
                                          {
                                              'row_pos': row_pos_in,
                                              'name': name_in,
                                              'weight': weight_in,
                                              'onoff': onoff_in,
                                              'randomizer': rizer_in
                                          })
                                row_items = [
                                    QStandardItem(row_pos_in),
                                    QStandardItem(name_in),
                                    QStandardItem(weight_in),
                                    QStandardItem(onoff_in),
                                    QStandardItem(rizer_in),
                                ]
                                row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
                                row_items[0].setData(int(row_pos_in), Qt.ItemDataRole.UserRole + 1)
                                row_items[2].setTextAlignment(Qt.AlignCenter)
                                row_items[3].setTextAlignment(Qt.AlignCenter)
                                row_items_list.append(row_items)
                                cnames.append(name_in)
                        if row_items_list:
                            row_items_list.sort(key=lambda row_items: int(row_items[0].text()))
                            for row_items in row_items_list:
                                self.tree_model.appendRow(row_items)
                    elif db == 'completed.db':
                        ctasks = [row[1] for row in rows]
                        for line in lines:
                            reg = re.match(pattern_import_ctasks, line)
                            if reg and reg.group('task') not in ctasks:
                                name_in = reg.group('name')
                                task_in = reg.group('task')
                                date_in = datetime.fromisoformat(reg.group('datetime'))
                                c.execute('INSERT INTO tasks VALUES (:name, :task, :datetime)',
                                          {
                                              'name': name_in,
                                              'task': task_in,
                                              'datetime': reg.group('datetime')
                                          })
                                row_items = [
                                    QStandardItem(str(self.tree_model_completed.rowCount() + 1)),
                                    QStandardItem(name_in),
                                    QStandardItem(task_in),
                                    QStandardItem(date_in.strftime("%Y-%m-%d")),
                                ]
                                row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
                                row_items[0].setData(self.tree_model_completed.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
                                row_items[2].setData(f"{name_in}, {task_in}", Qt.ItemDataRole.UserRole)
                                row_items[3].setData(date_in, Qt.ItemDataRole.UserRole)
                                self.tree_model_completed.appendRow(row_items)
                                ctasks.append(task_in)
                        self.lbl_score_all.setText('Completed: ' + str(self.tree_model_completed.rowCount()))
                    conn.commit()
                    conn.close()
            except FileNotFoundError:
                QMessageBox.critical(self, 'Error', f"{fname} file not found")

    def network(self):
        if __name__ == '__main__':
            self.close()
            QApplication.quit()
        else:
            self.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(cleanup)
    w = NextTask()
    w.showMaximized()
    sys.exit(app.exec())
