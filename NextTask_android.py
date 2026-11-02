from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QDialog,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTreeView, QFileDialog,
    QMessageBox, QSplitter, QFrame, QSizePolicy, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QStandardItemModel, QStandardItem, QIcon, QBrush, QDesktopServices
from PySide6.QtCore import Qt, QItemSelectionModel, QSortFilterProxyModel, QObject, Signal, QSettings, QStandardPaths, QUrl
import sys
import sqlite3
import random
import re
from string import ascii_lowercase
from datetime import datetime
import shutil
from fractions import Fraction
from math import lcm
import resources_rc

data_dir = Path(
    QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
) / "NextTask"

data_dir.mkdir(parents=True, exist_ok=True)

notes_url = data_dir / 'Notes'
notes_url.mkdir(exist_ok=True)

tasks_db = data_dir / "tasks.db"
completed_db = data_dir / "completed.db"

icon_folder_dir = ":/resources/icons/folder.svg"

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

# \s includes \n
patterns = [r"^\s*(?P<target>[^,\s](?:[^,\n]*[^,\s])?)\s*$",
            r"^\s*(?P<target>\d+)\s*$",
            r"^\s*(?P<target>0|1)\s*$",
            re.compile(
            r"""
            (?P<match>
                (?P<name>
                    [^,\[\s]
                    (?:[^,\n\[]*[^,\[\s])?
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
                        [^,\]\s]
                        (?:[^,\n\]]*[^,\]\s])?
                        (?:
                            \s*,\s*
                            [^,\]\s]
                            (?:[^,\n\]]*[^,\]\s])?
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
                            [^,\s]
                            (?:[^,\n]*[^,\s])?
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
                            [^,\s]
                            (?:[^,\n]*[^,\s])?
                        )
                        (?:
                            \s*,\s*
                            (?P<task>[^,\s]
                                (?:[^,\n]*[^,\s])?
                            )
                        )?
                        (?:
                            \s*,\s*\[\s*
                            (?P<keywords>
                                [^\]\s]
                                (?:[^\n\]]*[^\]\s])?
                                (?:
                                    \s*,\s*[^\]\s]
                                    (?:[^\n\]]*[^\]\s])?
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
pattern_sample = r"\s*(?P<name>[^,\/\s](?:[^,\n\/]*[^,\/\s])?)\s*(?:\/\s*(?P<weight>\d+))*"
pattern_current_task = r"(?P<full_task>(?P<name>[^,\s](?:[^,\n]*[^,\s])?)(?:\s*,\s*(?P<task>[^\n]+)*)?)"

expl = ["Name: Characters other than '.' and ','.",
        "Weights: Any integer.\n\tEqual weights = equal propability to be picked.",
        "On/Off: 0 or 1.\n\t0 to exclude and 1 to include in the randomizer.",
        f"Randomizer pattern examples:\n\tWIP"]
helptext = f"""
Patterns:   {expl[0]}
            {expl[1]}
            {expl[2]}
            {expl[3]}
"""

bt_style_tabs = """
    QPushButton {
        background-color: #9C6F6F;
        color: %s;
    }
    QPushButton:hover {
        background-color: #8b5f5f;
    }
"""

settings = QSettings("NextTask", "NextTask")

def update_row_pos():
    if w.movedRows:
        conn = sqlite3.connect(tasks_db)
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

        w.movedRows = False


def numerate(model):
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
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w.click_press(self.indexAt(event.position().toPoint()))

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w.click_release()

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            w.escape()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_A:
            w.select_all()

        if event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_Down:
            w.active_task = w.tree.currentIndex().row() - 1
            w.select_task()
            
        super().keyPressEvent(event)


class TreeViewCompleted(QTreeView):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            w.escape()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_A:
            w.select_all()
            
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
        self.last_completed_task = None
        self.score = 0
        self.total_score = 0
        self.focused = []
        self.held = []
        self.movedRows = False
        self.doubleClicked = False
        self.ewm_rows = []
        self.ewm_chances = []
        self.ewm_all_rows = []

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')

        import_tasks_action = file_menu.addAction('Import tasks')
        import_tasks_action.triggered.connect(lambda: self.import_tasks(tasks_db))

        export_tasks_action = file_menu.addAction('Export tasks')
        export_tasks_action.triggered.connect(lambda: self.export_tasks(self.tree))

        file_menu.addSeparator()

        import_completed_action = file_menu.addAction('Import completed tasks')
        import_completed_action.triggered.connect(lambda: self.import_tasks(completed_db))

        export_completed_action = file_menu.addAction('Export completed tasks')
        export_completed_action.triggered.connect(lambda: self.export_tasks(self.tree_completed))

        file_menu.addSeparator()

        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.network)

        edit_menu = menubar.addMenu('Edit')
        find_weights_action = edit_menu.addAction('Find weights based on chance')
        find_weights_action.triggered.connect(self.show_hide_ewm)

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
                bt_tasks.setStyleSheet(bt_style_tabs % default_fg)
                right_frame.show()
                self.tree.show()
            elif f"color: {default_fg}" in bt_tasks.styleSheet():
                bt_tasks.setStyleSheet(bt_style_tabs % inactive_fg)
                right_frame.hide()
                self.tree.hide()
            else:
                bt_completed_tasks.setStyleSheet(bt_style_tabs % inactive_fg)
                self.tree_completed.hide()
                bt_tasks.setStyleSheet(bt_style_tabs % default_fg)
                self.tree.show()

        def bt_call2():
            if f"color: {default_fg}" not in bt_tasks.styleSheet() and f"color: {default_fg}" not in bt_completed_tasks.styleSheet():
                bt_completed_tasks.setStyleSheet(bt_style_tabs % default_fg)
                right_frame.show()
                self.tree_completed.show()
            elif f"color: {default_fg}" in bt_completed_tasks.styleSheet():
                bt_completed_tasks.setStyleSheet(bt_style_tabs % inactive_fg)
                right_frame.hide()
                self.tree_completed.hide()
            else:
                bt_tasks.setStyleSheet(bt_style_tabs % inactive_fg)
                self.tree.hide()
                bt_completed_tasks.setStyleSheet(bt_style_tabs % default_fg)
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
        bt_tasks.setStyleSheet(bt_style_tabs % default_fg)

        bt_completed_tasks = QPushButton("Completed Tasks")
        bt_completed_tasks.setStyleSheet(bt_style_tabs % inactive_fg)

        top_bar.addWidget(bt_tasks)
        top_bar.addWidget(bt_completed_tasks)

        # Splitter area: left text, right tree + completed
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_frame = QFrame(splitter)
        left_layout = QVBoxLayout(left_frame)

        # Edit_weights_menu
        self.frame_ewm = QFrame()
        self.frame_ewm.setWindowTitle("Edit weights menu")
        left_layout.addWidget(self.frame_ewm)

        layout_ewm = QGridLayout(self.frame_ewm)
        self.txt_ewm = QTextEdit()
        layout_ewm.addWidget(self.txt_ewm, 0, 0, 1, 2)
        self.txt_ewm.setReadOnly(True)
        self.txt_ewm.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_ewm.setFont(QFont('TkFixedFont', 9))

        lbl_selection = QLabel("Select rows")
        lbl_chance = QLabel("Chance to pick (decimal)")
        layout_ewm.addWidget(lbl_selection, 1, 0) 
        layout_ewm.addWidget(lbl_chance, 1, 1) 

        self.qle_selection = QLineEdit()
        self.qle_chance = QLineEdit()
        layout_ewm.addWidget(self.qle_selection, 2, 0) 
        layout_ewm.addWidget(self.qle_chance, 2, 1)

        bt_ewm_add =  QPushButton("Add next selection")
        bt_ewm_clear =  QPushButton("Clear selections")
        layout_ewm.addWidget(bt_ewm_add, 3, 0)
        layout_ewm.addWidget(bt_ewm_clear, 3, 1)

        bt_ewm_calculate = QPushButton("Calculate")
        bt_ewm_close = QPushButton("Close")
        layout_ewm.addWidget(bt_ewm_calculate, 4, 0)
        layout_ewm.addWidget(bt_ewm_close, 4, 1)
        self.frame_ewm.hide()

        # self.txt_main
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
        self.tree_completed = TreeViewCompleted()
        self.tree_completed.setModel(self.tree_model_completed)
        self.tree_completed.setColumnWidth(0, 40)
        self.tree_completed.setColumnWidth(1, 200)
        right_layout.addWidget(self.tree_completed)
        self.proxy_completed = TaskSortModel()
        self.proxy_completed.setSourceModel(self.tree_model_completed)
        self.tree_completed.setModel(self.proxy_completed)
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
            settings.setValue("NextTask", output)

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
            temp = random.choices(temp, weights=[int(n[1]) for n in temp])[0]
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

                conn = sqlite3.connect(completed_db)
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
                bt_files = QPushButton("Upload")
                layout_up.addWidget(lbl_files, 1, 0)
                layout_up.addWidget(bt_files, 1, 1)

                bt_cancel = QPushButton("Cancel")
                bt_ok = QPushButton("OK")
                layout_down.addWidget(bt_cancel)
                layout_down.addWidget(bt_ok)

                fnames = []

                def store_files():
                    nonlocal fnames

                    selected, _ = QFileDialog.getOpenFileNames(self, 'Select Files', str(data_dir))

                    if selected:
                        fnames = selected
                        if len(selected) > 1:
                            bt_files.setText('Files selected')
                        else:
                            bt_files.setText('File selected')

                bt_files.clicked.connect(store_files)
                bt_cancel.clicked.connect(dialog.reject)
                bt_ok.clicked.connect(dialog.accept)

                dialog.adjustSize()

                if dialog.exec() == QDialog.DialogCode.Rejected:
                    return

                name = reg.group('name')
                task_stripped = reg.group('task')
                if task_stripped is None:
                    task_stripped = ""
                conn = sqlite3.connect(completed_db)
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
                folder_url = notes_url / f'{rowid}'  # .../Notes/1

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
                        shutil.copy2(fname, folder_url)

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
                    row_items[4].setIcon(QIcon(icon_folder_dir))
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


 