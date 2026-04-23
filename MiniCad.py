import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import ezdxf
import csv
import svgwrite


# -----------------------------
# Geometrijski objekti
# -----------------------------

class Line:
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2

class Circle:
    def __init__(self, cx, cy, r):
        self.cx, self.cy, self.r = cx, cy, r

class Rectangle:
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2

class Text:
    def __init__(self, x, y, text, height=5.0, rotation=0.0):
        self.x, self.y = x, y
        self.text = text
        self.height = height
        self.rotation = rotation


# -----------------------------
# Glavna aplikacija
# -----------------------------

class CADApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini CAD – tkinter")

        self.lines = []
        self.circles = []
        self.rectangles = []
        self.texts = []

        # Povijest za Undo – lista tuplova ("line"/"circle"/"rectangle"/"text", objekt)
        self.history = []

        # Defaultni raspon koordinatnog sustava
        self.axis_range = 100

        self.create_menu()
        self.create_canvas()

    # -----------------------------
    # GUI elementi
    # -----------------------------

    def create_menu(self):
        menubar = tk.Menu(self.root)

        # FILE
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New",     command=self.new_drawing)
        file_menu.add_separator()
        file_menu.add_command(label="Open CSV", command=self.load_csv)
        file_menu.add_command(label="Open DXF", command=self.load_dxf)
        file_menu.add_separator()
        file_menu.add_command(label="Save CSV", command=self.save_csv)
        file_menu.add_command(label="Save DXF", command=self.save_dxf)
        file_menu.add_command(label="Save SVG", command=self.save_svg)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # EDIT
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Line",      command=self.add_line_dialog)
        edit_menu.add_command(label="Add Circle",    command=self.add_circle_dialog)
        edit_menu.add_command(label="Add Rectangle", command=self.add_rectangle_dialog)
        edit_menu.add_command(label="Add Text",      command=self.add_text_dialog)
        edit_menu.add_separator()
        edit_menu.add_command(label="Undo (zadnji element)  Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Obriši element...",             command=self.delete_dialog)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # VIEW
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh View", command=self.refresh_canvas)
        view_menu.add_separator()
        view_menu.add_command(label="Raspon: 10",  command=lambda: self.set_range(10))
        view_menu.add_command(label="Raspon: 100", command=lambda: self.set_range(100))
        view_menu.add_command(label="Raspon: 1000", command=lambda: self.set_range(1000))
        view_menu.add_command(label="Auto raspon", command=self.auto_range)
        menubar.add_cascade(label="View", menu=view_menu)

        # LISP
        lisp_menu = tk.Menu(menubar, tearoff=0)
        lisp_menu.add_command(label="Generiraj LISP iz trenutnog crteža", command=self.export_lisp)
        lisp_menu.add_command(label="Generiraj LISP iz CSV datoteke...",  command=self.export_lisp_from_csv)
        menubar.add_cascade(label="AutoCAD LISP", menu=lisp_menu)

        # HELP
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "About", "Mini CAD – tkinter\n\nPopravci:\n- Unos koordinata ispravljen\n- Koordinatni sustav 0–100"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def create_canvas(self):
        self.fig, self.ax = plt.subplots(figsize=(6, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.refresh_canvas()
        # tipkovnički prečaci
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-Z>", lambda e: self.undo())

    # -----------------------------
    # New / Undo / Delete
    # -----------------------------

    def new_drawing(self):
        """Briše sve elemente i počinje novi crtež."""
        if self.lines or self.circles or self.rectangles:
            if not messagebox.askyesno("New", "Obrisati sve elemente i početi novi crtež?"):
                return
        self.lines.clear()
        self.circles.clear()
        self.rectangles.clear()
        self.texts.clear()
        self.history.clear()
        self.refresh_canvas()

    def undo(self):
        """Briše zadnji dodani element (bez obzira na tip)."""
        if not self.history:
            messagebox.showinfo("Undo", "Nema više elemenata za poništiti.")
            return
        kind, obj = self.history.pop()
        if kind == "line":
            self.lines.remove(obj)
        elif kind == "circle":
            self.circles.remove(obj)
        elif kind == "rectangle":
            self.rectangles.remove(obj)
        elif kind == "text":
            self.texts.remove(obj)
        self.refresh_canvas()

    def delete_dialog(self):
        """Prikazuje popis svih elemenata; korisnik odabire koji želi obrisati."""
        # Sastavi listu svih elemenata s opisom
        items = []
        for i, ln in enumerate(self.lines):
            items.append(("line", i, f"Linija {i+1}:  ({ln.x1}, {ln.y1}) → ({ln.x2}, {ln.y2})"))
        for i, c in enumerate(self.circles):
            items.append(("circle", i, f"Kružnica {i+1}:  središte ({c.cx}, {c.cy}),  r={c.r}"))
        for i, r in enumerate(self.rectangles):
            items.append(("rectangle", i, f"Pravokutnik {i+1}:  ({r.x1}, {r.y1}) – ({r.x2}, {r.y2})"))
        for i, t in enumerate(self.texts):
            items.append(("text", i, f"Tekst {i+1}:  ({t.x}, {t.y})  \"{t.text}\"  h={t.height}"))

        if not items:
            messagebox.showinfo("Brisanje", "Nema elemenata za brisanje.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Obriši element")
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Odaberi element koji želiš obrisati:",
                 font=("", 10, "bold")).pack(padx=12, pady=(10, 4))

        # Listbox s klizačem
        frame = tk.Frame(dialog)
        frame.pack(padx=12, pady=4, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set,
                             width=55, height=min(len(items), 12),
                             selectmode=tk.SINGLE, font=("Courier", 9))
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for _, _, opis in items:
            listbox.insert(tk.END, opis)

        def potvrdi():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Upozorenje", "Nije odabran nijedan element.", parent=dialog)
                return
            kind, idx, _ = items[sel[0]]
            if kind == "line":
                obj = self.lines.pop(idx)
                # makni i iz historije ako postoji
                if ("line", obj) in self.history:
                    self.history.remove(("line", obj))
            elif kind == "circle":
                obj = self.circles.pop(idx)
                if ("circle", obj) in self.history:
                    self.history.remove(("circle", obj))
            elif kind == "rectangle":
                obj = self.rectangles.pop(idx)
                if ("rectangle", obj) in self.history:
                    self.history.remove(("rectangle", obj))
            elif kind == "text":
                obj = self.texts.pop(idx)
                if ("text", obj) in self.history:
                    self.history.remove(("text", obj))
            dialog.destroy()
            self.refresh_canvas()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Obriši", width=12, bg="#e05050", fg="white",
                  command=potvrdi).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Odustani", width=12,
                  command=dialog.destroy).pack(side=tk.LEFT, padx=6)

        # dvoklик = odmah obriši
        listbox.bind("<Double-Button-1>", lambda e: potvrdi())

    def set_range(self, r):
        self.axis_range = r
        self.refresh_canvas()

    def auto_range(self):
        """Automatski postavi raspon prema nacrtanim objektima."""
        self.axis_range = None
        self.refresh_canvas()

    # -----------------------------
    # Dijalozi za unos
    # -----------------------------

    def ask_values(self, fields):
        """
        Ispravljena verzija: rezultat se sprema u self._dialog_result
        jer callback funkcija submit() ne može vratiti vrijednost pozivatelju.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Input")
        dialog.grab_set()  # modalni dijalog – blokira glavni prozor
        self._dialog_result = None

        entries = {}
        for i, f in enumerate(fields):
            tk.Label(dialog, text=f).grid(row=i, column=0, padx=8, pady=4)
            e = tk.Entry(dialog)
            e.grid(row=i, column=1, padx=8, pady=4)
            entries[f] = e

        # fokus na prvo polje
        list(entries.values())[0].focus_set()

        def submit(event=None):
            try:
                self._dialog_result = [float(entries[f].get()) for f in fields]
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Greška", "Unesite ispravne brojeve!", parent=dialog)

        btn = tk.Button(dialog, text="OK", command=submit)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=8)

        # Enter tipka potvrđuje unos
        dialog.bind("<Return>", submit)

        dialog.wait_window()
        return self._dialog_result

    def add_line_dialog(self):
        vals = self.ask_values(["x1", "y1", "x2", "y2"])
        if vals:
            obj = Line(*vals)
            self.lines.append(obj)
            self.history.append(("line", obj))
            self.refresh_canvas()

    def add_circle_dialog(self):
        vals = self.ask_values(["cx", "cy", "r"])
        if vals:
            obj = Circle(*vals)
            self.circles.append(obj)
            self.history.append(("circle", obj))
            self.refresh_canvas()

    def add_rectangle_dialog(self):
        vals = self.ask_values(["x1", "y1", "x2", "y2"])
        if vals:
            obj = Rectangle(*vals)
            self.rectangles.append(obj)
            self.history.append(("rectangle", obj))
            self.refresh_canvas()

    def add_text_dialog(self):
        """Dijalog za unos teksta: koordinate, visina, kut i sam tekst."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Dodaj tekst")
        dialog.grab_set()
        dialog.resizable(False, False)

        fields = [("X koordinata", "0"), ("Y koordinata", "0"),
                  ("Visina teksta", "5"), ("Kut (°)", "0"), ("Tekst", "")]
        entries = {}

        for i, (label, default) in enumerate(fields):
            tk.Label(dialog, text=label + ":").grid(row=i, column=0, sticky="e", padx=8, pady=4)
            e = tk.Entry(dialog, width=28)
            e.insert(0, default)
            e.grid(row=i, column=1, padx=8, pady=4)
            entries[label] = e

        result = {}

        def potvrdi():
            try:
                x       = float(entries["X koordinata"].get())
                y       = float(entries["Y koordinata"].get())
                height  = float(entries["Visina teksta"].get())
                rot     = float(entries["Kut (°)"].get())
                text    = entries["Tekst"].get().strip()
                if not text:
                    messagebox.showwarning("Upozorenje", "Tekst ne može biti prazan!", parent=dialog)
                    return
                result["obj"] = Text(x, y, text, height, rot)
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Greška", "Koordinate, visina i kut moraju biti brojevi!", parent=dialog)

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Dodaj", width=12, command=potvrdi).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Odustani", width=12, command=dialog.destroy).pack(side=tk.LEFT, padx=6)
        dialog.bind("<Return>", lambda e: potvrdi())

        # Fokus na polje Tekst
        entries["Tekst"].focus_set()
        dialog.wait_window()

        if "obj" in result:
            obj = result["obj"]
            self.texts.append(obj)
            self.history.append(("text", obj))
            self.refresh_canvas()

    # -----------------------------
    # Crtanje
    # -----------------------------

    def refresh_canvas(self):
        self.ax.clear()

        # koordinatne osi
        self.ax.axhline(0, color='black', linewidth=0.8)
        self.ax.axvline(0, color='black', linewidth=0.8)
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_aspect('equal')

        # postavljanje raspona osi
        if self.axis_range is not None:
            self.ax.set_xlim(-self.axis_range * 0.05, self.axis_range)
            self.ax.set_ylim(-self.axis_range * 0.05, self.axis_range)
        # kad je axis_range=None matplotlib sam odabire raspon prema podacima

        # linije
        for ln in self.lines:
            self.ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color='blue')

        # kružnice
        for c in self.circles:
            circle = plt.Circle((c.cx, c.cy), c.r, fill=False, color='red')
            self.ax.add_patch(circle)

        # pravokutnici
        for r in self.rectangles:
            x = min(r.x1, r.x2)
            y = min(r.y1, r.y2)
            w = abs(r.x2 - r.x1)
            h = abs(r.y2 - r.y1)
            rect = plt.Rectangle((x, y), w, h, fill=False, color='green')
            self.ax.add_patch(rect)

        # tekstovi
        for t in self.texts:
            self.ax.text(t.x, t.y, t.text,
                         fontsize=max(4, t.height * 0.8),
                         rotation=t.rotation,
                         color='black',
                         verticalalignment='bottom')

        self.canvas.draw()

    # -----------------------------
    # CSV
    # -----------------------------

    def save_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV datoteke", "*.csv")])
        if not filename:
            return

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["type", "x1", "y1", "x2", "y2", "r", "height", "rotation", "text"])

            for ln in self.lines:
                writer.writerow(["line", ln.x1, ln.y1, ln.x2, ln.y2, "", "", "", ""])

            for c in self.circles:
                writer.writerow(["circle", c.cx, c.cy, "", "", c.r, "", "", ""])

            for r in self.rectangles:
                writer.writerow(["rectangle", r.x1, r.y1, r.x2, r.y2, "", "", "", ""])

            for t in self.texts:
                writer.writerow(["text", t.x, t.y, "", "", "", t.height, t.rotation, t.text])

        messagebox.showinfo("Spremljeno", f"CSV snimljen:\n{filename}")

    def load_csv(self):
        filename = filedialog.askopenfilename(filetypes=[("CSV datoteke", "*.csv")])
        if not filename:
            return

        self.lines.clear()
        self.circles.clear()
        self.rectangles.clear()
        self.texts.clear()

        with open(filename, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = row["type"]
                if t == "line":
                    self.lines.append(Line(float(row["x1"]), float(row["y1"]),
                                           float(row["x2"]), float(row["y2"])))
                elif t == "circle":
                    self.circles.append(Circle(float(row["x1"]), float(row["y1"]),
                                               float(row["r"])))
                elif t == "rectangle":
                    self.rectangles.append(Rectangle(float(row["x1"]), float(row["y1"]),
                                                     float(row["x2"]), float(row["y2"])))
                elif t == "text":
                    self.texts.append(Text(
                        float(row["x1"]), float(row["y1"]),
                        row.get("text", ""),
                        float(row["height"]) if row.get("height") else 5.0,
                        float(row["rotation"]) if row.get("rotation") else 0.0
                    ))

        self.refresh_canvas()

    # -----------------------------
    # DXF
    # -----------------------------

    def save_dxf(self):
        filename = filedialog.asksaveasfilename(defaultextension=".dxf",
                                                filetypes=[("DXF datoteke", "*.dxf")])
        if not filename:
            return

        doc = ezdxf.new()
        msp = doc.modelspace()

        for ln in self.lines:
            msp.add_line((ln.x1, ln.y1), (ln.x2, ln.y2))

        for c in self.circles:
            msp.add_circle((c.cx, c.cy), c.r)

        for r in self.rectangles:
            msp.add_lwpolyline([(r.x1, r.y1), (r.x2, r.y1),
                                (r.x2, r.y2), (r.x1, r.y2), (r.x1, r.y1)],
                               close=True)

        for t in self.texts:
            msp.add_text(t.text, dxfattribs={
                "insert": (t.x, t.y),
                "height": t.height,
                "rotation": t.rotation,
            })

        doc.saveas(filename)
        messagebox.showinfo("Spremljeno", f"DXF snimljen:\n{filename}")

    def load_dxf(self):
        filename = filedialog.askopenfilename(filetypes=[("DXF datoteke", "*.dxf")])
        if not filename:
            return

        self.lines.clear()
        self.circles.clear()
        self.rectangles.clear()
        self.texts.clear()

        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()

        for e in msp:
            if e.dxftype() == "LINE":
                self.lines.append(Line(e.dxf.start.x, e.dxf.start.y,
                                       e.dxf.end.x, e.dxf.end.y))

            elif e.dxftype() == "CIRCLE":
                self.circles.append(Circle(e.dxf.center.x, e.dxf.center.y,
                                           e.dxf.radius))

            elif e.dxftype() == "LWPOLYLINE":
                pts = list(e.get_points())
                pts_open = pts[:-1] if len(pts) == 5 else pts
                if len(pts_open) == 4:
                    xs = [p[0] for p in pts_open]
                    ys = [p[1] for p in pts_open]
                    self.rectangles.append(Rectangle(min(xs), min(ys),
                                                     max(xs), max(ys)))

            elif e.dxftype() == "TEXT":
                self.texts.append(Text(
                    e.dxf.insert.x, e.dxf.insert.y,
                    e.dxf.text,
                    e.dxf.get("height", 5.0),
                    e.dxf.get("rotation", 0.0)
                ))

        self.refresh_canvas()

    # -----------------------------
    # SVG
    # -----------------------------

    def save_svg(self):
        filename = filedialog.asksaveasfilename(defaultextension=".svg",
                                                filetypes=[("SVG datoteke", "*.svg")])
        if not filename:
            return

        # Odredimo viewBox prema sadržaju ili defaultnom rasponu
        r = self.axis_range if self.axis_range else 100
        dwg = svgwrite.Drawing(filename, size=(f"{r}px", f"{r}px"),
                               viewBox=f"0 0 {r} {r}")

        for ln in self.lines:
            dwg.add(dwg.line((ln.x1, ln.y1), (ln.x2, ln.y2),
                             stroke="blue", stroke_width=0.5))

        for c in self.circles:
            dwg.add(dwg.circle(center=(c.cx, c.cy), r=c.r,
                               stroke="red", fill="none", stroke_width=0.5))

        for rect in self.rectangles:
            x = min(rect.x1, rect.x2)
            y = min(rect.y1, rect.y2)
            w = abs(rect.x2 - rect.x1)
            h = abs(rect.y2 - rect.y1)
            dwg.add(dwg.rect(insert=(x, y), size=(w, h),
                             stroke="green", fill="none", stroke_width=0.5))

        for t in self.texts:
            dwg.add(dwg.text(t.text,
                             insert=(t.x, t.y),
                             font_size=t.height,
                             fill="black",
                             transform=f"rotate({-t.rotation},{t.x},{t.y})"))

        dwg.save()
        messagebox.showinfo("Spremljeno", f"SVG snimljen:\n{filename}")

    # -----------------------------
    # AutoCAD LISP export
    # -----------------------------

    def _generate_lisp_lines(self, lines, circles, rectangles, texts):
        """Generira AutoCAD LISP kod iz liste objekata."""
        lisp = []
        lisp.append(";; AutoCAD LISP skripta – generirana iz MiniCAD")
        lisp.append(";; Učitajte u AutoCAD-u: Tools → Load Application ili tipkajte APPLOAD")
        lisp.append(";; Zatim pokrenite: (c:minicad-draw)")
        lisp.append("")
        lisp.append("(defun c:minicad-draw ()")
        lisp.append('  (princ "\\nCrtam MiniCAD elemente...")')
        lisp.append("")

        if lines:
            lisp.append("  ;; --- LINIJE ---")
        for ln in lines:
            lisp.append(f'  (command "LINE" '
                        f'"{ln.x1},{ln.y1}" '
                        f'"{ln.x2},{ln.y2}" "")')

        if circles:
            lisp.append("")
            lisp.append("  ;; --- KRUŽNICE ---")
        for c in circles:
            lisp.append(f'  (command "CIRCLE" '
                        f'"{c.cx},{c.cy}" '
                        f'"{c.r}")')

        if rectangles:
            lisp.append("")
            lisp.append("  ;; --- PRAVOKUTNICI ---")
        for r in rectangles:
            lisp.append(f'  (command "RECTANG" '
                        f'"{r.x1},{r.y1}" '
                        f'"{r.x2},{r.y2}")')

        if texts:
            lisp.append("")
            lisp.append("  ;; --- TEKSTOVI ---")
        for t in texts:
            lisp.append(f'  (command "TEXT" '
                        f'"{t.x},{t.y}" '
                        f'"{t.height}" '
                        f'"{t.rotation}" '
                        f'"{t.text}")')

        lisp.append("")
        lisp.append('  (princ "\\nGotovo!")')
        lisp.append('  (princ)')
        lisp.append(")")
        lisp.append("")
        lisp.append(";; Automatsko pokretanje pri učitavanju skripte:")
        lisp.append("(c:minicad-draw)")
        return "\n".join(lisp)

    def export_lisp(self):
        """Generira LISP iz trenutno nacrtanih elemenata."""
        if not (self.lines or self.circles or self.rectangles or self.texts):
            messagebox.showinfo("LISP export", "Nema elemenata za export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".lsp",
            filetypes=[("AutoCAD LISP", "*.lsp"), ("Sve datoteke", "*.*")],
            title="Spremi LISP skriptu")
        if not filename:
            return

        kod = self._generate_lisp_lines(self.lines, self.circles,
                                        self.rectangles, self.texts)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(kod)
        self._lisp_preview(kod, filename)

    def export_lisp_from_csv(self):
        """Učitava CSV i generira LISP – bez mijenjanja trenutnog crteža."""
        csv_file = filedialog.askopenfilename(
            filetypes=[("CSV datoteke", "*.csv")],
            title="Odaberi CSV datoteku")
        if not csv_file:
            return

        lines, circles, rectangles, texts = [], [], [], []

        try:
            with open(csv_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t = row.get("type", "").strip()
                    if t == "line":
                        lines.append(Line(float(row["x1"]), float(row["y1"]),
                                          float(row["x2"]), float(row["y2"])))
                    elif t == "circle":
                        circles.append(Circle(float(row["x1"]), float(row["y1"]),
                                              float(row["r"])))
                    elif t == "rectangle":
                        rectangles.append(Rectangle(float(row["x1"]), float(row["y1"]),
                                                    float(row["x2"]), float(row["y2"])))
                    elif t == "text":
                        texts.append(Text(
                            float(row["x1"]), float(row["y1"]),
                            row.get("text", ""),
                            float(row["height"]) if row.get("height") else 5.0,
                            float(row["rotation"]) if row.get("rotation") else 0.0
                        ))
        except Exception as ex:
            messagebox.showerror("Greška pri čitanju CSV", str(ex))
            return

        if not (lines or circles or rectangles or texts):
            messagebox.showinfo("LISP export", "CSV ne sadrži prepoznatljive elemente.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".lsp",
            filetypes=[("AutoCAD LISP", "*.lsp"), ("Sve datoteke", "*.*")],
            title="Spremi LISP skriptu")
        if not filename:
            return

        kod = self._generate_lisp_lines(lines, circles, rectangles, texts)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(kod)
        self._lisp_preview(kod, filename)

    def _lisp_preview(self, kod, filename):
        """Prikazuje preview generirane LISP skripte."""
        win = tk.Toplevel(self.root)
        win.title(f"LISP skripta – {filename}")
        win.geometry("620x480")

        tk.Label(win, text="Generirana AutoCAD LISP skripta:",
                 font=("", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(frame, font=("Courier", 9), yscrollcommand=sb.set,
                      bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        txt.pack(fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)

        txt.insert(tk.END, kod)
        txt.config(state=tk.DISABLED)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Zatvori", width=14,
                  command=win.destroy).pack(side=tk.LEFT, padx=6)

        messagebox.showinfo("Spremljeno",
                            f"LISP skripta snimljena:\n{filename}\n\n"
                            "Upute za AutoCAD:\n"
                            "1. Tools → Load Application (ili APPLOAD)\n"
                            "2. Odaberite .lsp datoteku\n"
                            "3. Skripta se automatski pokreće pri učitavanju",
                            parent=win)


# -----------------------------
# Pokretanje aplikacije
# -----------------------------

root = tk.Tk()
app = CADApp(root)
root.mainloop()
