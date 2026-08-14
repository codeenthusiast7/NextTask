from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QDialog,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTreeView, QFileDialog,
    QMessageBox, QSplitter, QFrame, QSizePolicy, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QStandardItemModel, QStandardItem, QCursor, QIcon
from PySide6.QtCore import Qt, QItemSelectionModel, QSortFilterProxyModel, QObject, Signal
import sys
import sqlite3
import random
import re
from string import ascii_lowercase
import numpy as np
from datetime import datetime
import shutil
import subprocess

if getattr(sys, 'frozen', False):
    # Path(sys.executable).resolve().parent points to App/
    app_dir = Path(sys._MEIPASS)  # points to App/_internal/
else:
    app_dir = Path(__file__).resolve().parent

if sys.platform == "win32":
    default_fg = "SystemButtonText"
else:
    default_fg = "#000000"
inactive_fg = "#505050"

default_rizer = "Random [1-1000]"

fmt = QTextCharFormat()
fmt.setForeground(QColor("blue"))
default_fmt = QTextCharFormat()
default_fmt.setForeground(QColor("black"))

patterns = [r"^\s*(?P<target>[^,\n\s](?:[^,\n]*[^,\n\s])?)$",
            r"^\s*(?P<target>\d+)\s*$",
            r"^\s*(?P<target>0|1)\s*$",
            re.compile(
            r"""
            (?P<match>
                (?P<name>
                    [^,\n\[\s]
                    (?:[^,\n\[]*[^,\n\[\s])?
                )
                (?:
                    \s*\[\s*
                    (?P<num_lo>\d+)
                    \s*-\s*
                    (?P<num_hi>\d+)
                    \s*\]
                    |
                    \s*\[\s*
                    (?P<str_lo>[a-zA-Z]+)
                    \s*-\s*
                    (?P<str_hi>[a-zA-Z]+)
                    \s*\]
                    |
                    \s*\[\s*
                    (?P<choices>
                        [^,\n\]\s]
                        (?:[^,\n\]]*[^,\n\]\s])?
                        (?:
                            \s*,\s*
                            [^,\n\]\s]
                            (?:[^,\n\]]*[^,\n\]\s])?
                        )*
                    )
                    \s*\]
                )
            )
            """,
            re.VERBOSE,
            )
            ]

pattern_import_tasks = re.compile(
                        r"""
                        (?:
                            (?P<row_pos>\d+)
                            \s*,\s*
                        )?
                        (?P<name>
                            [^,\n\s]
                            (?:[^,\n]*[^,\n\s])?
                        )
                        (?P<options>
                            \s*,\s*
                            (?P<weight>\d+)
                            \s*,\s*
                            (?P<onoff>[01])
                            (?:
                                \s*,\s*
                                (?P<rizer>[^\n]+)
                            )?
                        )?
                        """,
                        re.VERBOSE,
                       )
pattern_import_ctasks = re.compile(
                        r"""
                        (?:
                            (?P<sql_ID>\d+)
                            \s*,\s*
                        )?
                        (?P<name>
                            [^,\n\s]
                            (?:[^,\n]*[^,\n\s])?
                        )
                        (?:
                            \s*,\s*
                            (?P<task>[^,\n\s]
                                (?:[^,\n]*[^,\n\s])?
                            )
                        )?
                        (?:
                            \s*,\s*\[\s*
                            (?P<keywords>
                                [^\n\]\s]
                                (?:[^\n\]]*[^\n\]\s])?
                                (?:
                                    \s*,\s*[^\n\]\s]
                                    (?:[^\n\]]*[^\n\]\s])?
                                )*
                            )?
                            \s*\]
                        )?
                        (?:
                            \s*,\s*
                            (?P<datetime>
                                \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}
                            )
                        )?
                        (?:
                            \s*,\s*
                            (?P<completitions>\d+)
                        )?
                        """,
                        re.VERBOSE,
                        )
pattern_duplic_name = r"^.+\((?P<num_dupe>\d+)\)$"
pattern_sample = r"\s*(?P<name>[^,\n\/\s](?:[^,\n\/]*[^,\n\/\s])?)\s*(?:\/\s*(?P<weight>\d+))*"
pattern_current_task = r"(?P<full_task>(?P<name>[^,\n\s](?:[^,\n]*[^,\n\s])?)(?:\s*,\s*(?P<task>[^\n]+)*)?)"

expl = ["Name: Characters other than '.' and ','.",
        "Weights: Any integer.\n\tEqual weights = equal propability to be picked.",
        "On/Off: 0 or 1.\n\t0 to exclude and 1 to include in the randomizer.",
        f"Randomizer pattern examples:\n\tWIP"]
helptext = f"""
Patterns:   {expl[0]}
            {expl[1]}
            {expl[2]}
            {expl[3]}

If you want to edit the completed tasks you can:\n1) Export .txt file\n2) Delete completed.db\n3) Open \
the exported .txt file with a notepad\n4) Make your edits\n5) Import the new txt file\nThe pattern needs to be the \
same as before, for them to appear.
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
        conn = sqlite3.connect(app_dir / 'tasks.db')
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


def addup(chars):
    s = 0
    t = 1
    for ch in chars.lower()[::-1]:
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


class ErrorRedirector(QObject):
    text_written = Signal(str)

    def __init__(self, original_stderr):
        super().__init__()
        self.original_stderr = original_stderr

    def write(self, text):
        self.original_stderr.write(text)
        self.original_stderr.flush()
        self.text_written.emit(text)

    def flush(self):
        self.original_stderr.flush()


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
        # self.memory[1] = matches, match object
        # self.memory[2] = randomizer indices

        self.mem_output = [] # only the results of output, not the names
        self.mem_index = 0
        self.active_task = None
        self.first_task = None
        self.last_completed_task = None
        self.score = 0
        self.total_score = 0
        self.focused = []
        self.held = []
        self.movedRows = False
        self.doubleClicked = False

        self.notes_url = app_dir / 'Notes'
        self.notes_url.mkdir(exist_ok=True)

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
        export_tasks_action.triggered.connect(lambda: self.export_tasks(self.tree))

        file_menu.addSeparator()

        import_completed_action = file_menu.addAction('Import completed tasks')
        import_completed_action.triggered.connect(lambda: self.import_tasks('completed.db'))

        export_completed_action = file_menu.addAction('Export completed tasks')
        export_completed_action.triggered.connect(lambda: self.export_tasks(self.tree_completed))

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

        left_frame = QFrame(splitter)
        left_layout = QVBoxLayout(left_frame)

        self.txt_main = QTextEdit()
        error_redirector = ErrorRedirector(sys.stderr)
        error_redirector.text_written.connect(self.txt_main.insertPlainText)
        sys.stderr = error_redirector
        left_layout.addWidget(self.txt_main)
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

        lbl_current_task = QLabel("Current task")
        lbl_current_task.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lbl_current_task.setFont(QFont("Helvetica", 12))
        qle_current_task = QLineEdit()

        left_layout.addWidget(lbl_current_task)
        left_layout.addWidget(qle_current_task)

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
        self.tree_model_completed.setHorizontalHeaderLabels(["No.", "Name", "Task", "Keywords", "Files", "Date", "Completitions"])
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
        self.tree_completed.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_completed.setIndentation(0)
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


        def handle_output(output):
            qle_current_task.setText(output)
            row_found = find_in_tree_completed(output)
            if row_found is not None:
                times_done = self.tree_model_completed.item(row_found, 6).text()
                output += f'\nTask (No. {self.tree_model_completed.item(row_found, 0).text()}) has already been completed {times_done} time'
                if times_done != '1':
                    output += 's'
            self.txt_main.append(output)

        def rl():
            if not self.memory:
                return rt()
            if not self.mem_output:
                return rd()
            output = self.memory[0]
            for k, match in enumerate(self.memory[1]):
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
            handle_output(output)

        def rd():
            if not self.memory:
                return rt()
            output = self.memory[0]
            same_task = True
            if not self.mem_output:
                self.mem_output = [0] * sum(1 for _ in self.memory[1])
                same_task = False
            for k, match in enumerate(self.memory[1]):
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
            handle_output(output)

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
            self.memory = [temp[0]]
            txt_routput.setReadOnly(False)
            txt_routput.setPlainText(temp[1])
            txt_routput.setReadOnly(True)
            self.memory.append(list(re.finditer(patterns[3], temp[1])))  # self.memory[1]: matches, match object
            self.memory.append([m.span() for m in self.memory[1]])  # self.memory[2]: randomizer indices
            self.mem_output = []
            self.mem_index = 0
            self.held = []
            lbl_index.setText(f'{((self.memory[2][0][1] + self.memory[2][0][0]) // 2 - 1) * " "}^')
            rd()

        def complete():
            reg = re.match(pattern_current_task, qle_current_task.text())
            if not reg:
                self.txt_main.append("No task found")
                return
            full_task = reg.group('full_task')
            row_found = find_in_tree_completed(full_task)
            
            if row_found is not None:
                if self.tree_model_completed.item(row_found, 0).text() == self.last_completed_task:
                    if QMessageBox.question(self, 'Confirm', 'Complete the same task again?') != QMessageBox.Yes:
                        return

                completitions = int(self.tree_model_completed.item(row_found, 6).text()) + 1

                conn = sqlite3.connect(app_dir / 'completed.db')
                c = conn.cursor()
                c.execute('''
                    UPDATE tasks
                    SET completitions = :completitions
                    WHERE rowid = :rowid
                ''', {
                    'completitions': completitions,
                    'rowid': self.tree_model_completed.item(row_found, 0).data(Qt.ItemDataRole.UserRole)
                })
                conn.commit()
                conn.close()
                
                self.tree_model_completed.item(row_found, 6).setText(str(completitions))
                self.last_completed_task = self.tree_model_completed.item(row_found, 0).text()
            else:
                dialog = QDialog(self)
                dialog.setWindowTitle("Complete menu")
                layout = QVBoxLayout(dialog)

                frame_up = QFrame(dialog)
                frame_down = QFrame(dialog)
                layout.addWidget(frame_up)
                layout.addWidget(frame_down)

                layout_up = QGridLayout(frame_up)
                layout_down = QHBoxLayout(frame_down)

                lbl_keywords = QLabel("Keywords ")
                qle_keywords = QLineEdit()
                qle_keywords.setMaxLength(100)
                layout_up.addWidget(lbl_keywords, 0, 0)
                layout_up.addWidget(qle_keywords, 0, 1)

                lbl_files = QLabel("Store files ")
                button_files = QPushButton("Upload")
                layout_up.addWidget(lbl_files, 1, 0)
                layout_up.addWidget(button_files, 1, 1)

                button_cancel = QPushButton("Cancel")
                button_ok = QPushButton("OK")
                layout_down.addWidget(button_cancel)
                layout_down.addWidget(button_ok)

                fnames = []

                def store_files():
                    nonlocal fnames

                    selected, _ = QFileDialog.getOpenFileNames(self, 'Select Files', str(app_dir))

                    if selected:
                        fnames = selected
                        if len(selected) > 1:
                            button_files.setText('Files selected')
                        else:
                            button_files.setText('File selected')

                button_files.clicked.connect(store_files)
                button_cancel.clicked.connect(dialog.reject)
                button_ok.clicked.connect(dialog.accept)

                dialog.adjustSize()

                if dialog.exec() == QDialog.DialogCode.Rejected:
                    return

                name = reg.group('name')
                task_stripped = reg.group('task')
                if task_stripped is None:
                    task_stripped = ""
                conn = sqlite3.connect(app_dir / 'completed.db')
                c = conn.cursor()
                datetime_obj = datetime.now()
                c.execute('''INSERT INTO tasks VALUES (
                                                        :name,
                                                        :task,
                                                        :keywords,
                                                        :folder_url,
                                                        :datetime,
                                                        :completitions
                                                    )
                        ''', {
                            'name': name,
                            'task': task_stripped,
                            'keywords': qle_keywords.text(),
                            'folder_url': None,
                            'datetime': datetime_obj.isoformat(),
                            'completitions': 1
                })

                rowid = c.lastrowid
                folder_url = self.notes_url / f'{rowid}'  # .../Notes/1

                c.execute('''
                    UPDATE tasks
                    SET folder_url = :folder_url
                    WHERE rowid = :rowid
                ''', {
                    'folder_url': str(folder_url),
                    'rowid': rowid
                })

                if fnames:
                    folder_url.mkdir(exist_ok=True)
                    for fname in fnames:
                        shutil.move(fname, folder_url)

                row_items = [
                    QStandardItem(str(self.tree_model_completed.rowCount() + 1)),
                    QStandardItem(name),
                    QStandardItem(task_stripped),
                    QStandardItem(qle_keywords.text()),
                    QStandardItem(''),
                    QStandardItem(datetime_obj.strftime("%Y-%m-%d")),
                    QStandardItem('1')
                ]
                row_items[0].setData(rowid, Qt.ItemDataRole.UserRole)
                row_items[0].setData(self.tree_model_completed.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
                row_items[2].setData(full_task, Qt.ItemDataRole.UserRole)
                if fnames:
                    row_items[4].setIcon(QIcon(str(app_dir / "icons" / "folder.svg")))
                row_items[4].setData(folder_url, Qt.ItemDataRole.UserRole)
                row_items[5].setData(datetime_obj, Qt.ItemDataRole.UserRole)
                row_items[6].setTextAlignment(Qt.AlignCenter)
                conn.commit()
                conn.close()
                self.tree_model_completed.appendRow(row_items)
                self.last_completed_task = row_items[0].text()

            self.score += 1
            lbl_score.setText(f"Completed this session: {self.score}")
            self.total_score += 1
            self.lbl_score_all.setText(f'Completed: {self.total_score}')
            self.txt_main.append('Completed')

        def move(n):
            if not self.memory:
                return
            if (n == - 1 and self.mem_index == 0) or (n == 1 and self.mem_index == len(self.memory[2]) - 1):
                return
            else:
                self.mem_index += n
            lbl_index.setText(f'{((self.memory[2][self.mem_index][1] + self.memory[2][self.mem_index][0]) // 2 - 1) * " "}^')

        def hold():
            if not self.memory:
                return
            if self.mem_index in self.held:
                txt_routput_cursor.setPosition(self.memory[2][self.mem_index][0])
                txt_routput_cursor.setPosition(self.memory[2][self.mem_index][1], QTextCursor.MoveMode.KeepAnchor)
                txt_routput_cursor.mergeCharFormat(default_fmt)
                self.held.remove(self.mem_index)
            else:
                txt_routput_cursor.setPosition(self.memory[2][self.mem_index][0])
                txt_routput_cursor.setPosition(self.memory[2][self.mem_index][1], QTextCursor.MoveMode.KeepAnchor)
                txt_routput_cursor.mergeCharFormat(fmt)
                self.held.append(self.mem_index)
        
        def find_in_tree_completed(task):
            for row in range(self.tree_model_completed.rowCount()):
                if self.tree_model_completed.item(row, 2).data(Qt.ItemDataRole.UserRole) == task:
                    return row
            return None


        # Editor frames for add/edit
        edit_frame_1 = QFrame()
        edit_frame_1.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(edit_frame_1)
        edit_layout_1 = QGridLayout(edit_frame_1)

        lbl_name = ClickableLabel('Name:')
        self.qle_name = QLineEdit()
        lbl_wgt = ClickableLabel('Weight:')
        self.qle_wgt = QLineEdit()
        lbl_onoff = ClickableLabel('On/Off:')
        self.qle_onoff = QLineEdit()
        lbld_routput = ClickableLabel('Randomizer:')
        self.qle_routput = QLineEdit()

        lbl_name.setStyleSheet("background-color: #D3D3D3;")
        lbl_wgt.setStyleSheet("background-color: #D3D3D3;")
        lbl_onoff.setStyleSheet("background-color: #D3D3D3;")
        lbld_routput.setStyleSheet("background-color: #D3D3D3;")

        edit_layout_1.addWidget(lbl_name, 0, 0)
        edit_layout_1.addWidget(self.qle_name, 0, 1)
        edit_layout_1.addWidget(lbl_wgt, 0, 2)
        edit_layout_1.addWidget(self.qle_wgt, 0, 3)
        edit_layout_1.addWidget(lbl_onoff, 0, 4)
        edit_layout_1.addWidget(self.qle_onoff, 0, 5)
        edit_layout_1.addWidget(lbld_routput, 1, 0)
        edit_layout_1.addWidget(self.qle_routput, 1, 1, 1, 5)

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
            if len(selection_ids) > 1 and (not self.focused or self.qle_name in self.focused):
                if QMessageBox.warning(self, 'Warning', 'Do you really want to give multiple tasks the same name?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.Yes:
                    return
            columns = ["name",
                       "weight",
                       "onoff",
                       "randomizer"]
            changes = []
            for n, entry in enumerate([self.qle_name, self.qle_wgt, self.qle_onoff]):
                if not self.focused or entry in self.focused:
                    reg = re.match(patterns[n], entry.text())
                    if not reg:
                        QMessageBox.warning(self, 'Warning', 'Unable to read input. At:\n' + expl[n])
                        entry.setFocus()
                        return
                    changes.append(columns[n])
            if not self.focused or self.qle_routput in self.focused:
                if not self.randomizer_check(self.qle_routput.text(), 2):
                    return
                changes.append("randomizer")
            conn = sqlite3.connect(app_dir / 'tasks.db')
            c = conn.cursor()
            command = f"UPDATE tasks SET {','.join([f"{change} = :{change}" for change in changes])} WHERE rowid = :rowid"
            for row in selection_ids:
                c.execute(command, 
                          {
                              'name': self.qle_name.text(),
                              'weight': self.qle_wgt.text(),
                              'onoff': self.qle_onoff.text(),
                              'randomizer': self.qle_routput.text(),
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
            for n, entry in enumerate([self.qle_name, self.qle_wgt, self.qle_onoff]):
                reg = re.match(patterns[n], entry.text())
                if not reg:
                    QMessageBox.warning(self, 'Error', 'Unable to read input.\n' + expl[n])
                    entry.setFocus()
                    return
                entry.setText(reg.group("target"))
                if n == 0:
                    name = entry.text()
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

            self.qle_routput.setText(self.randomizer_check(self.qle_routput.text(), 1))
            conn = sqlite3.connect(app_dir / 'tasks.db')
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
                        'weight': self.qle_wgt.text(),
                        'onoff': self.qle_onoff.text(),
                        'randomizer': self.qle_routput.text(),
                    }
            )
            row_items = [
                QStandardItem(str(self.tree_model.rowCount() + 1)),
                QStandardItem(name),
                QStandardItem(self.qle_wgt.text()),
                QStandardItem(self.qle_onoff.text()),
                QStandardItem(self.qle_routput.text()),
            ]
            row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
            row_items[0].setData(self.tree_model.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
            row_items[2].setTextAlignment(Qt.AlignCenter)
            row_items[3].setTextAlignment(Qt.AlignCenter)
            self.tree_model.appendRow(row_items)
            conn.commit()
            conn.close()

        def remove_selected():
            if self.tree.isVisible():
                db = 'tasks.db'
                model = self.tree_model
                selection_model = self.tree.selectionModel()

                proxy_indexes = selection_model.selectedRows()
                selection = [self.proxy.mapToSource(pindex) for pindex in proxy_indexes]
            elif self.tree_completed.isVisible():
                db = 'completed.db'
                model = self.tree_model_completed
                selection_model = self.tree_completed.selectionModel()

                selection = selection_model.selectedRows()
            else:
                return
        
            if not selection:
                return
            if QMessageBox.question(self, 'Warning!', 'Delete the selected tasks?') != QMessageBox.Yes:
                return
            conn = sqlite3.connect(app_dir / db)
            c = conn.cursor()
            rows = sorted({index.row() for index in selection}, reverse=True)
            for row in rows:
                row_item = model.item(row, 0)
                rowid = int(row_item.data(Qt.ItemDataRole.UserRole))
                c.execute('DELETE from tasks WHERE rowid=?', (rowid,))
                model.removeRow(row)
            conn.commit()
            conn.close()
            arithmise(model)

        def up():
            selection_model = self.tree.selectionModel()
            selection = selection_model.selectedRows()

            if selection:
                header = self.tree.header()

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

                    if sort_order == Qt.SortOrder.AscendingOrder:
                        if row == 0:
                            continue
                        items = self.tree_model.takeRow(row)
                        items[0].setText(str(row))
                        items[0].setData(row, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row - 1, items)
                    else:
                        if row == self.tree_model.rowCount() - 1:
                            continue
                        items = self.tree_model.takeRow(row)
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

                for index in reversed(selection):
                    row = index.row()

                    if sort_order == Qt.SortOrder.AscendingOrder:
                        if row == self.tree_model.rowCount() - 1:
                            continue
                        items = self.tree_model.takeRow(row)
                        items[0].setText(str(row + 2))
                        items[0].setData(row + 2, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row + 1, items)
                    else:
                        if row == 0:
                            continue
                        items = self.tree_model.takeRow(row)
                        items[0].setText(str(row))
                        items[0].setData(row, Qt.ItemDataRole.UserRole + 1)
                        self.tree_model.insertRow(row - 1, items)

                if sort_order == Qt.SortOrder.AscendingOrder:
                    selection = [self.proxy.mapFromSource(self.tree_model.index(index.row() + 1, index.column(), index.parent())) for index in selection]
                else:
                    selection = [self.proxy.mapFromSource(self.tree_model.index(index.row() - 1, index.column(), index.parent())) for index in selection]
                
                for index in selection:
                    selection_model.select(
                        index,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
                arithmise(self.tree_model)

        def double_click(index):  # focuses the entry when clicking a value in the treeview
            if not index.isValid():
                return

            self.doubleClicked = True
            entries = edit_frame_1.findChildren(QLineEdit)
            column = index.column()
            if column == 0:
                entry = entries[0]
            else:
                entry = entries[column - 1]
            entry.setFocus()
            entry.selectAll()

        def open_folder(index):
            if not index.isValid() or index.column() != 4:
                return

            index = proxy_completed.mapToSource(index)

            path = self.tree_model_completed.item(index.row(), 4).data(Qt.ItemDataRole.UserRole)
            if Path(path).is_dir():
                subprocess.Popen(["xdg-open", path])
            else:
                dialog = QDialog(self)
                dialog.setWindowTitle("Upload files menu")
                layout = QVBoxLayout(dialog)

                frame_up = QFrame(dialog)
                frame_down = QFrame(dialog)
                layout.addWidget(frame_up)
                layout.addWidget(frame_down)

                layout_up = QGridLayout(frame_up)
                layout_down = QHBoxLayout(frame_down)

                lbl_files = QLabel("Upload files ")
                button_files = QPushButton("Upload")
                layout_up.addWidget(lbl_files, 0, 0)
                layout_up.addWidget(button_files, 0, 1)

                button_cancel = QPushButton("Cancel")
                button_ok = QPushButton("OK")
                layout_down.addWidget(button_cancel)
                layout_down.addWidget(button_ok)

                fnames = []

                def store_files():
                    nonlocal fnames

                    selected, _ = QFileDialog.getOpenFileNames(self, 'Select Files', str(app_dir))

                    if selected:
                        fnames = selected
                        if len(selected) > 1:
                            button_files.setText('Files selected')
                        else:
                            button_files.setText('File selected')

                button_files.clicked.connect(store_files)
                button_cancel.clicked.connect(dialog.reject)
                button_ok.clicked.connect(dialog.accept)

                dialog.adjustSize()

                if dialog.exec() == QDialog.DialogCode.Rejected:
                    return

                rowid = self.tree_model_completed.item(index.row(), 4).data(Qt.ItemDataRole.UserRole)
                folder_url = self.notes_url / f'{rowid}'

                if fnames:
                    if not Path(folder_url).is_dir():
                        self.tree_model_completed.item(index.row(), 4).setIcon(QIcon(str(app_dir / "icons" / "folder.svg")))

                    folder_url.mkdir(exist_ok=True)
                    for fname in fnames:
                        shutil.move(fname, folder_url)


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
        self.qle_name.returnPressed.connect(update_task)
        self.qle_wgt.returnPressed.connect(update_task)
        self.qle_onoff.returnPressed.connect(update_task)
        self.qle_routput.returnPressed.connect(update_task)
        self.tree.doubleClicked.connect(double_click)
        self.tree_completed.doubleClicked.connect(open_folder)


        def create_databases():
            conn = sqlite3.connect(app_dir / 'tasks.db')
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
            conn = sqlite3.connect(app_dir / 'completed.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE if not exists tasks (
                    name text,
                    task text,
                    keywords text,
                    folder_url text,
                    datetime text,
                    completitions integer)
                    ''')
            conn.commit()
            conn.close()

        def query_database():
            conn = sqlite3.connect(app_dir / 'tasks.db')
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
                    QStandardItem(task[5] if task[5] else default_rizer),
                ]
                row_items[0].setData(task[0], Qt.ItemDataRole.UserRole)
                row_items[0].setData(task[1], Qt.ItemDataRole.UserRole + 1)
                row_items[2].setTextAlignment(Qt.AlignCenter)
                row_items[3].setTextAlignment(Qt.AlignCenter)
                self.tree_model.appendRow(row_items)

            conn = sqlite3.connect(app_dir / 'completed.db')
            c = conn.cursor()
            c.execute('SELECT rowid, * FROM tasks')
            ctasks = c.fetchall()
            conn.close()
            for n, ctask in enumerate(ctasks):
                if ctask[5]:
                    datetime_obj = datetime.fromisoformat(ctask[5])
                    datetime_strf = datetime_obj.strftime("%Y-%m-%d")
                else:
                    datetime_obj = None
                    datetime_strf = None
                self.total_score += ctask[6]
                row_items = [
                    QStandardItem(str(n + 1)),
                    QStandardItem(ctask[1]),
                    QStandardItem(ctask[2]),
                    QStandardItem(ctask[3]),
                    QStandardItem(''),
                    QStandardItem(datetime_strf),
                    QStandardItem(str(ctask[6])),
                ]
                row_items[0].setData(ctask[0], Qt.ItemDataRole.UserRole)
                row_items[0].setData(n + 1, Qt.ItemDataRole.UserRole + 1)
                row_items[2].setData(f"{ctask[1]}, {ctask[2]}", Qt.ItemDataRole.UserRole)
                if Path(ctask[4]).is_dir():
                    row_items[4].setIcon(QIcon(str(app_dir / "icons" / "folder.svg")))
                row_items[4].setData(ctask[4], Qt.ItemDataRole.UserRole)
                row_items[5].setData(datetime_obj, Qt.ItemDataRole.UserRole)
                row_items[6].setTextAlignment(Qt.AlignCenter)
                self.tree_model_completed.appendRow(row_items)

        create_databases()
        query_database()

        self.lbl_score_all.setText(f'Completed: {self.total_score}')


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
        if self.tree.isVisible():
            selection_model = self.tree.selectionModel()
        elif self.tree_completed.isVisible():
            selection_model = self.tree_completed.selectionModel()
        else:
            return

        for row in range(self.tree_model.rowCount()):
            index = self.tree_model.index(row, 0)

            if not selection_model.isSelected(index):
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select |
                    QItemSelectionModel.SelectionFlag.Rows
                )

    def clear_entries(self):
        self.qle_name.setText('')
        self.qle_wgt.setText('')
        self.qle_onoff.setText('')
        self.qle_routput.setText('')

    def select_task(self):
        values = [
            self.tree_model.item(
                self.active_task,
                column
            ).text()
            for column in range(self.tree_model.columnCount())
        ]

        qles = [self.qle_name, self.qle_wgt, self.qle_onoff, self.qle_routput]
        for n, entry in enumerate(qles):
            if self.focused and entry in self.focused and qles[n].text() != self.tree_model.item(self.active_task, n + 1).text():
                continue
            else:
                qles[n].setText(values[n + 1])
                if n in (0, 3):
                    qles[n].setCursorPosition(0)

    def motion(self, _):
        pos = self.tree.viewport().mapFromGlobal(QCursor.pos())
        pindex = self.tree.indexAt(pos)
        index = self.proxy.mapToSource(pindex)

        if not index.isValid():
            return

        task = index.row()
        if task == self.active_task:
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

    def randomizer_check(self, target, mode):
        if not target:
            return default_rizer
        
        reg = list(re.finditer(patterns[3], target))
        if not reg:
            if mode in (1, 2):
                self.qle_routput.setFocus()
                QMessageBox.warning(self, 'Error', f"Unable to read randomizer input.\n{expl[3]}"
                    + ("\nUsing default instead" if mode == 1 else "")
                )
            return default_rizer if mode in (1, 3) else None

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
            self.qle_routput.setText(rizer)
        return rizer

    def export_tasks(self, tree):
        fname, _ = QFileDialog.getSaveFileName(w, 'Save File', str(app_dir), filter='Text Files (*.txt)')
        if fname:
            if not fname.lower().endswith('.txt'):
                fname += '.txt'

            with open(fname, 'w', encoding='utf-8') as f:
                model = tree.model().sourceModel()
                row_items_list = [
                    [
                        model.item(row, column)
                        for column in range(model.columnCount())
                    ]
                    for row in range(model.rowCount())
                ]

                row_items_list.sort(key=lambda row_items: int(row_items[0].text()))

                if tree == self.tree:
                    for row_items in row_items_list:
                        f.write(", ".join([item.text() for item in row_items]))
                        f.write('\n')
                elif tree == self.tree_completed:
                    for row_items in row_items_list:
                        f.write(f"{row_items[0].data(Qt.ItemDataRole.UserRole)}, ")
                        f.write(", ".join([item.text() for item in row_items[1:3]]))
                        f.write(f", [{row_items[3].text()}]")
                        if row_items[5]:
                            f.write(f", {row_items[5].data(Qt.ItemDataRole.UserRole).isoformat()}")
                        f.write(f", {row_items[6].text()}")
                        f.write('\n')
                    

    def import_tasks(self, db):
        if db == 'completed.db':
            dialog = QDialog(self)
            dialog.setWindowTitle("Import menu")
            layout = QVBoxLayout(dialog)

            frame_up = QFrame(dialog)
            frame_down = QFrame(dialog)
            layout.addWidget(frame_up)
            layout.addWidget(frame_down)

            layout_up = QGridLayout(frame_up)
            layout_down = QHBoxLayout(frame_down)

            lbl_file = QLabel("Select file ")
            button_file = QPushButton("Select")
            layout_up.addWidget(lbl_file, 0, 0)
            layout_up.addWidget(button_file, 0, 1)

            lbl_notes = QLabel("Select 'Notes' folder (optional) ")
            button_notes = QPushButton("Select")
            layout_up.addWidget(lbl_notes, 1, 0)
            layout_up.addWidget(button_notes, 1, 1)

            button_cancel = QPushButton("Cancel")
            button_ok = QPushButton("OK")
            layout_down.addWidget(button_cancel)
            layout_down.addWidget(button_ok)

            fname = ""
            notes_import = None

            def select_file():
                nonlocal fname

                selected, _ = QFileDialog.getOpenFileName(self, 'Select file', str(app_dir))

                if selected:
                    fname = selected
                    button_file.setText('File selected')

            def select_notes():
                nonlocal notes_import

                folder = QFileDialog.getExistingDirectory(self, "Select 'Notes' Folder", str(app_dir))

                if folder:
                    notes_import = Path(folder)
                    button_notes.setText('Folder selected')

            button_file.clicked.connect(select_file)
            button_notes.clicked.connect(select_notes)

            button_cancel.clicked.connect(dialog.reject)
            button_ok.clicked.connect(dialog.accept)

            dialog.adjustSize()

            if dialog.exec() == QDialog.DialogCode.Rejected:
                return
        else:
            fname, _ = QFileDialog.getOpenFileName(self, 'Open File', str(app_dir), filter='Text Files (*.txt)')

        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    conn = sqlite3.connect(app_dir / db)
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
                                row_pos = reg.group('row_pos')
                                if row_pos is None or int(row_pos) <= self.tree_model.rowCount():
                                    row_pos = self.tree_model.rowCount() + 1
                                name = reg.group('name')
                                if reg.group('options'):
                                    weight = reg.group('weight')
                                    onoff = reg.group('onoff')
                                else:
                                    weight = '1'
                                    onoff = '1'
                                rizer = self.randomizer_check(reg.group('rizer'), 3)
                                c.execute('INSERT INTO tasks VALUES (:row_pos, :name, :weight, :onoff, :randomizer)',
                                          {
                                              'row_pos': row_pos,
                                              'name': name,
                                              'weight': weight,
                                              'onoff': onoff,
                                              'randomizer': rizer
                                          })
                                row_items = [
                                    QStandardItem(row_pos),
                                    QStandardItem(name),
                                    QStandardItem(weight),
                                    QStandardItem(onoff),
                                    QStandardItem(rizer),
                                ]
                                row_items[0].setData(c.lastrowid, Qt.ItemDataRole.UserRole)
                                row_items[0].setData(int(row_pos), Qt.ItemDataRole.UserRole + 1)
                                row_items[2].setTextAlignment(Qt.AlignCenter)
                                row_items[3].setTextAlignment(Qt.AlignCenter)
                                row_items_list.append(row_items)
                                cnames.append(name)
                        if row_items_list:
                            row_items_list.sort(key=lambda row_items: int(row_items[0].text()))
                            for row_items in row_items_list:
                                self.tree_model.appendRow(row_items)
                    elif db == 'completed.db':
                        ctasks = [row[1] for row in rows]
                        for line in lines:
                            reg = re.match(pattern_import_ctasks, line)
                            if reg and reg.group('task') not in ctasks:
                                sql_ID = reg.group('sql_ID')  # for matching the Notes folder
                                name = reg.group('name')
                                task = reg.group('task')
                                keywords = reg.group('keywords')
                                datetime_iso = reg.group('datetime')
                                if datetime_iso:
                                    datetime_obj = datetime.fromisoformat(datetime_iso)
                                    datetime_strf = datetime_obj.strftime("%Y-%m-%d")
                                else:
                                    datetime_obj = None
                                    datetime_strf = None
                                completitions = reg.group('completitions')
                                self.total_score += completitions
                                c.execute('''INSERT INTO tasks VALUES (:name,
                                                                       :task,
                                                                       :keywords,
                                                                       :folder_url,
                                                                       :datetime,
                                                                       :completitions)
                                          ''',
                                          {
                                              'name': name,
                                              'task': task,
                                              'keywords': keywords,
                                              'folder_url': None,
                                              'datetime': datetime_iso,
                                              'completitions': completitions
                                          })

                                rowid = c.lastrowid
                                folder_url = self.notes_url / f'{rowid}'

                                c.execute('''
                                    UPDATE tasks
                                    SET folder_url = :folder_url
                                    WHERE rowid = :rowid
                                ''', {
                                    'folder_url': str(folder_url),
                                    'rowid': rowid
                                })

                                if notes_import:
                                    folder_url.mkdir(exist_ok=True)
                                    for file in (notes_import / sql_ID).iterdir():
                                        shutil.move(file, folder_url)

                                row_items = [
                                    QStandardItem(str(self.tree_model_completed.rowCount() + 1)),
                                    QStandardItem(name),
                                    QStandardItem(task),
                                    QStandardItem(keywords),
                                    QStandardItem(''),
                                    QStandardItem(datetime_strf),
                                    QStandardItem(completitions),
                                ]
                                row_items[0].setData(rowid, Qt.ItemDataRole.UserRole)
                                row_items[0].setData(self.tree_model_completed.rowCount() + 1, Qt.ItemDataRole.UserRole + 1)
                                row_items[2].setData(f"{name}, {task}", Qt.ItemDataRole.UserRole)
                                row_items[4].setData(str(folder_url), Qt.ItemDataRole.UserRole)
                                row_items[5].setData(datetime_obj, Qt.ItemDataRole.UserRole)
                                row_items[6].setTextAlignment(Qt.AlignCenter)
                                self.tree_model_completed.appendRow(row_items)
                                ctasks.append(task)
                        self.lbl_score_all.setText('Completed: ' + str(self.total_score))
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
