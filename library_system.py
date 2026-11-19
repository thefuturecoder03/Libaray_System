from collections import defaultdict, deque 
import os
import pprint
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional, Set, Tuple


EMBEDDED_BOOKS = [   {   'author': 'George Orwell', 
        'borrow_count': 7,
        'genre': 'Dystopian Fiction',
        'is_available': True,
        'isbn': '978-0451524935',
        'title': '1984',
        'waitlist': []},
    {   'author': 'Harper Lee',
        'borrow_count': 5,
        'genre': 'Classic Literature',
        'is_available': True,
        'isbn': '978-0061120084',
        'title': 'To Kill a Mockingbird',
        'waitlist': []},
    {   'author': 'Frank Herbert',
        'borrow_count': 14,
        'genre': 'Science Fiction',
        'is_available': False,
        'isbn': '978-0441172719',
        'title': 'Dune',
        'waitlist': []},
    {   'author': 'hello',
        'borrow_count': 1,
        'genre': 'Classic Literature',
        'is_available': True,
        'isbn': '43444',
        'title': 'hello',
        'waitlist': []}]

EMBEDDED_MEMBERS = [   {   'borrowed_books': ['978-0441172719'],
        'fines': 16.5,
        'member_id': 'M001',
        'name': 'Alice Johnson'},
    {   'borrowed_books': [],
        'fines': 0.0,
        'member_id': 'M002',
        'name': 'Bob Smith'}]



class Book:
    """Encapsulates a Book record, FIFO waitlist, and borrow counter."""

    def __init__(self, title: str, author: str, isbn: str, genre: str,
                 is_available: bool = True, waitlist: Optional[List[str]] = None,
                 borrow_count: int = 0):
        self.__title = title.strip()
        self.__author = author.strip()
        self.__isbn = isbn.strip()
        self.__genre = genre.strip()
        self.__is_available = bool(is_available)
        self.__waitlist = deque(waitlist or [])
        self.__borrow_count = max(0, int(borrow_count))

    @property
    def title(self) -> str: return self.__title
    @property
    def author(self) -> str: return self.__author
    @property
    def isbn(self) -> str: return self.__isbn
    @property
    def genre(self) -> str: return self.__genre
    @property
    def is_available(self) -> bool: return self.__is_available
    @property
    def status(self) -> str: return "Available" if self.__is_available else "Checked Out"
    @property
    def borrow_count(self) -> int: return self.__borrow_count
    @property
    def waitlist(self) -> List[str]: return list(self.__waitlist)
    @property
    def waitlist_text(self) -> str:
        return f"{len(self.__waitlist)} ({' -> '.join(self.__waitlist)})" if self.__waitlist else "Empty"

    def update(self, title: str, author: str, genre: str) -> None:
        if not (title.strip() and author.strip() and genre.strip()):
            raise ValueError("Title, Author, and Genre cannot be blank.")
        self.__title, self.__author, self.__genre = title.strip(), author.strip(), genre.strip()

    def set_borrowed(self) -> None:
        self.__is_available = False
        self.__borrow_count += 1

    def set_returned(self) -> None:
        self.__is_available = True

    def join_waitlist(self, member_id: str) -> int:
        if self.__is_available:
            raise ValueError("Book is available; borrow it directly.")
        if member_id in self.__waitlist:
            raise ValueError(f"Member {member_id} is already in the waitlist.")
        self.__waitlist.append(member_id)
        return len(self.__waitlist)

    def leave_waitlist(self, member_id: str) -> None:
        if member_id not in self.__waitlist:
            raise ValueError(f"Member {member_id} is not in this waitlist.")
        self.__waitlist.remove(member_id)

    def pop_waitlist(self) -> Optional[str]:
        return self.__waitlist.popleft() if self.__waitlist else None

    def to_dict(self) -> Dict:
        return {
            "title": self.__title, "author": self.__author, "isbn": self.__isbn,
            "genre": self.__genre, "is_available": self.__is_available,
            "waitlist": list(self.__waitlist), "borrow_count": self.__borrow_count,
        }


class Member:
    """Encapsulates a Member record, borrowed ISBN list, and fines."""

    def __init__(self, member_id: str, name: str,
                 borrowed_books: Optional[List[str]] = None, fines: float = 0.0):
        if fines < 0:
            raise ValueError("Fines cannot be negative.")
        self.__id = member_id.strip()
        self.__name = name.strip()
        self.__borrowed = list(borrowed_books or [])
        self.__fines = round(float(fines), 2)

    @property
    def member_id(self) -> str: return self.__id
    @property
    def name(self) -> str: return self.__name
    @property
    def borrowed(self) -> List[str]: return list(self.__borrowed)
    @property
    def borrowed_text(self) -> str:
        return f"{len(self.__borrowed)} ({', '.join(self.__borrowed)})" if self.__borrowed else "None"
    @property
    def fines(self) -> float: return self.__fines

    def update_name(self, name: str) -> None:
        if not name.strip():
            raise ValueError("Member name cannot be blank.")
        self.__name = name.strip()

    def borrow(self, isbn: str) -> None:
        if isbn in self.__borrowed:
            raise ValueError(f"Member already has ISBN {isbn}.")
        self.__borrowed.append(isbn)

    def return_book(self, isbn: str) -> None:
        if isbn not in self.__borrowed:
            raise ValueError(f"Member does not hold ISBN {isbn}.")
        self.__borrowed.remove(isbn)

    def adjust_fine(self, amount: float, is_payment: bool = False) -> None:
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        if is_payment and amount > self.__fines:
            raise ValueError("Payment exceeds current fine balance.")
        self.__fines = round(self.__fines + (-amount if is_payment else amount), 2)

    def to_dict(self) -> Dict:
        return {
            "member_id": self.__id, "name": self.__name,
            "borrowed_books": list(self.__borrowed), "fines": self.__fines,
        }


class LibraryManager:
    """Handles library CRUD, O(1) indexed search, circulation, waitlists, analytics, and persistence."""

    START_MARK = "# --- BEGIN EMBEDDED DATA ---"
    END_MARK = "# --- END EMBEDDED DATA ---"

    def __init__(self, script_path: str):
        self.__path = os.path.abspath(script_path)
        self.__books: Dict[str, Book] = {}
        self.__members: Dict[str, Member] = {}
        self.__indexes: Dict[str, Dict[str, Set[str]]] = {
            "Title": defaultdict(set), "Author": defaultdict(set),
            "Genre": defaultdict(set), "Availability": defaultdict(set),
        }
        self.__load()

    def __rebuild_indexes(self) -> None:
        for idx in self.__indexes.values():
            idx.clear()
        for b in self.__books.values():
            self.__indexes["Title"][b.title.lower()].add(b.isbn)
            self.__indexes["Author"][b.author.lower()].add(b.isbn)
            self.__indexes["Genre"][b.genre.lower()].add(b.isbn)
            self.__indexes["Availability"][b.status.lower()].add(b.isbn)

    def __load(self) -> None:
        self.__books = {b["isbn"]: Book(**b) for b in EMBEDDED_BOOKS}
        self.__members = {m["member_id"]: Member(**m) for m in EMBEDDED_MEMBERS}
        self.__rebuild_indexes()

    def __save(self) -> None:
        try:
            with open(self.__path, "r", encoding="utf-8") as f:
                src = f.read()
            s, e = src.find(self.START_MARK), src.find(self.END_MARK)
            if s == -1 or e == -1 or s >= e:
                raise RuntimeError("Data markers corrupted in source file.")
            books_str = pprint.pformat([b.to_dict() for b in self.__books.values()], indent=4)
            members_str = pprint.pformat([m.to_dict() for m in self.__members.values()], indent=4)
            block = f"{self.START_MARK}\nEMBEDDED_BOOKS = {books_str}\n\nEMBEDDED_MEMBERS = {members_str}\n"
            with open(self.__path, "w", encoding="utf-8") as f:
                f.write(src[:s] + block + src[e:])
        except OSError as err:
            raise IOError(f"Failed to persist data: {err}")

    # --- Book CRUD & O(1) Indexed Search ---
    def add_book(self, title: str, author: str, isbn: str, genre: str) -> None:
        if not (title.strip() and author.strip() and isbn.strip() and genre.strip()):
            raise ValueError("All book fields are required.")
        clean_isbn = isbn.strip()
        if clean_isbn in self.__books:
            raise ValueError(f"ISBN '{clean_isbn}' already exists.")
        self.__books[clean_isbn] = Book(title, author, clean_isbn, genre)
        self.__rebuild_indexes()
        self.__save()

    def update_book(self, isbn: str, title: str, author: str, genre: str) -> None:
        self.get_book(isbn).update(title, author, genre)
        self.__rebuild_indexes()
        self.__save()

    def delete_book(self, isbn: str) -> None:
        book = self.get_book(isbn)
        if not book.is_available:
            raise ValueError("Cannot delete a checked-out book.")
        del self.__books[isbn]
        self.__rebuild_indexes()
        self.__save()

    def get_book(self, isbn: str) -> Book:
        if isbn not in self.__books:
            raise KeyError(f"Book ISBN '{isbn}' not found.")
        return self.__books[isbn]

    def search_books(self, query: str = "", field: str = "All Fields") -> List[Book]:
        q = query.strip().lower()
        if not q or (field == "Availability" and q == "all"):
            return list(self.__books.values())
        if field == "ISBN":
            if query.strip() in self.__books:
                return [self.__books[query.strip()]]
            return [b for b in self.__books.values() if q in b.isbn.lower()]
        if field in self.__indexes:
            if q in self.__indexes[field]:
                return [self.__books[i] for i in self.__indexes[field][q]]
            attr_map = {"Title": "title", "Author": "author", "Genre": "genre", "Availability": "status"}
            return [b for b in self.__books.values() if q in getattr(b, attr_map[field]).lower()]
        return [
            b for b in self.__books.values()
            if any(q in v.lower() for v in (b.title, b.author, b.isbn, b.genre, b.status))
        ]

    # --- Member CRUD ---
    def add_member(self, member_id: str, name: str, fines_str: str = "0") -> None:
        cid, cname = member_id.strip(), name.strip()
        if not (cid and cname):
            raise ValueError("Member ID and Name are required.")
        if cid in self.__members:
            raise ValueError(f"Member ID '{cid}' already exists.")
        try:
            fines = float(fines_str) if fines_str.strip() else 0.0
        except ValueError:
            raise ValueError("Fines must be a valid number.")
        self.__members[cid] = Member(cid, cname, [], fines)
        self.__save()

    def update_member(self, member_id: str, name: str) -> None:
        self.get_member(member_id).update_name(name)
        self.__save()

    def delete_member(self, member_id: str) -> None:
        m = self.get_member(member_id)
        if m.borrowed or m.fines > 0:
            raise ValueError("Member still has borrowed books or unpaid fines.")
        for b in self.__books.values():
            if member_id in b.waitlist:
                b.leave_waitlist(member_id)
        del self.__members[member_id]
        self.__save()

    def get_member(self, member_id: str) -> Member:
        if member_id not in self.__members:
            raise KeyError(f"Member '{member_id}' not found.")
        return self.__members[member_id]

    def adjust_fine(self, member_id: str, amount: float, is_payment: bool) -> None:
        self.get_member(member_id).adjust_fine(amount, is_payment)
        self.__save()

    def search_members(self, query: str = "") -> List[Member]:
        q = query.strip().lower()
        if not q:
            return list(self.__members.values())
        return [
            m for m in self.__members.values()
            if q in m.member_id.lower() or q in m.name.lower() or any(q in i.lower() for i in m.borrowed)
        ]

    
    def borrow_book(self, member_id: str, isbn: str) -> None:
        member, book = self.get_member(member_id), self.get_book(isbn)
        if not book.is_available:
            raise ValueError("Book is checked out. Join the waitlist instead.")
        book.set_borrowed()
        member.borrow(isbn)
        self.__rebuild_indexes()
        self.__save()

    def return_book(self, member_id: str, isbn: str) -> Optional[Member]:
        member, book = self.get_member(member_id), self.get_book(isbn)
        member.return_book(isbn)
        assigned: Optional[Member] = None
        while book.waitlist:
            next_id = book.pop_waitlist()
            if next_id and next_id in self.__members:
                assigned = self.__members[next_id]
                assigned.borrow(isbn)
                book.set_borrowed()
                break
        if not assigned:
            book.set_returned()
        self.__rebuild_indexes()
        self.__save()
        return assigned

    def join_waitlist(self, member_id: str, isbn: str) -> int:
        member, book = self.get_member(member_id), self.get_book(isbn)
        if isbn in member.borrowed:
            raise ValueError("Member currently has this book checked out.")
        pos = book.join_waitlist(member_id)
        self.__save()
        return pos

    def leave_waitlist(self, member_id: str, isbn: str) -> None:
        self.get_book(isbn).leave_waitlist(member_id)
        self.__save()

    def get_loans(self) -> List[Tuple[str, str, str, str]]:
        return [
            (m.member_id, m.name, i, self.__books[i].title if i in self.__books else "Unknown")
            for m in self.__members.values() for i in m.borrowed
        ]

    def get_waitlists(self) -> List[Tuple[str, str, int, str, str]]:
        return [
            (b.isbn, b.title, pos, mid, self.__members[mid].name if mid in self.__members else "Unknown")
            for b in self.__books.values() for pos, mid in enumerate(b.waitlist, 1)
        ]

    
    def get_most_borrowed(self) -> List[Tuple[int, Book, float]]:
        ranked = sorted(self.__books.values(), key=lambda b: (-b.borrow_count, b.title.lower()))
        total = sum(b.borrow_count for b in ranked)
        return [(i, b, round((b.borrow_count / total * 100) if total else 0.0, 1)) for i, b in enumerate(ranked, 1)]


class LibraryGUI:
    """Nested menu system with centered button columns for main and sub-menus."""

    GENRES = ["Classic Literature", "Dystopian Fiction", "Fantasy", "History", "Mystery", "Non-Fiction", "Science Fiction", "Technology"]

    def __init__(self, root: tk.Tk, mgr: LibraryManager):
        self.__root, self.__mgr = root, mgr
        self.__root.title("Library Management System")
        self.__root.geometry("440x440")

        menu_frame = tk.Frame(root)
        menu_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(menu_frame, text="Library Management System", font=("TkDefaultFont", 13, "bold")).pack(pady=(0, 16))

        main_buttons = [
            ("Manage Books", self.__open_books_menu, "#1565C0"),
            ("Manage Members", self.__open_members_menu, "#2E7D32"),
            ("(Borrow / Return)", self.__open_circulation_menu, "#00695C"),
            ("Waitlist Management", self.__open_waitlist_menu, "#6A1B9A"),
            ("Data Analytics (Most Borrowed)", self.__open_analytics_window, "#EF6C00"),
        ]

        for text, command, color in main_buttons:
            tk.Button(
                menu_frame, text=text, command=command,
                bg=color, fg="white", font=("TkDefaultFont", 10, "bold"),
                width=32, pady=7, cursor="hand2"
            ).pack(pady=5)

    def __new_window(self, title: str, size: str) -> tk.Toplevel:
        win = tk.Toplevel(self.__root)
        win.title(title)
        win.geometry(size)
        win.configure(padx=12, pady=12)
        win.grab_set()
        return win

    def __make_menu_window(self, title: str, buttons: List[Tuple[str, callable, str]]) -> None:
        """Helper to create a sub-menu window with a centered column of action buttons."""
        win = self.__new_window(title, "380x320")
        frame = tk.Frame(win)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        for text, cmd, color in buttons:
            tk.Button(
                frame, text=text, command=cmd,
                bg=color, fg="white", font=("TkDefaultFont", 10, "bold"),
                width=28, pady=6, cursor="hand2"
            ).pack(pady=5)

    def __make_table(self, parent: tk.Widget, cols: Tuple[str, ...], widths: Tuple[int, ...]) -> ttk.Treeview:
        frame = tk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center" if w <= 130 else "w")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tree

    
    def __open_books_menu(self) -> None:
        self.__make_menu_window("Manage Books", [
            ("Add New Book", self.__dialog_add_book, "#2E7D32"),
            ("Search / View Catalog", self.__open_search_window, "#1565C0"),
            ("Update Book Details", self.__dialog_update_book, "#0277BD"),
            ("Delete Book Record", self.__dialog_delete_book, "#C62828"),
        ])

    def __dialog_add_book(self) -> None:
        dlg = self.__new_window("Add Book", "340x240")
        fields = {}
        for r, lbl in enumerate(("Title", "Author", "ISBN")):
            tk.Label(dlg, text=f"{lbl}:").grid(row=r, column=0, sticky="w", padx=8, pady=6)
            e = tk.Entry(dlg, width=24); e.grid(row=r, column=1, padx=8, pady=6)
            fields[lbl] = e
        tk.Label(dlg, text="Genre:").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        genre_cb = ttk.Combobox(dlg, values=self.GENRES, width=21); genre_cb.grid(row=3, column=1, padx=8, pady=6)

        def save():
            try:
                self.__mgr.add_book(fields["Title"].get(), fields["Author"].get(), fields["ISBN"].get(), genre_cb.get())
                messagebox.showinfo("Success", "Book added successfully!", parent=dlg)
                dlg.destroy()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=dlg)
        tk.Button(dlg, text="Save Book", bg="#2E7D32", fg="white", command=save).grid(row=4, column=1, sticky="e", padx=8, pady=8)

    def __open_search_window(self) -> None:
        win = self.__new_window("Search Book Catalog", "820x420")
        bar = tk.Frame(win); bar.pack(fill="x", pady=(0, 10))
        tk.Label(bar, text="Filter By:").pack(side="left")
        field_cb = ttk.Combobox(bar, values=["All Fields", "Title", "Author", "ISBN", "Genre", "Availability"], state="readonly", width=14)
        field_cb.set("All Fields"); field_cb.pack(side="left", padx=6)
        q_entry = tk.Entry(bar, width=30); q_entry.pack(side="left", padx=6)

        tree = self.__make_table(win, ("ISBN", "Title", "Author", "Genre", "Availability"), (130, 230, 170, 140, 110))

        def run_search(*_):
            tree.delete(*tree.get_children())
            for b in self.__mgr.search_books(q_entry.get(), field_cb.get()):
                tree.insert("", "end", values=(b.isbn, b.title, b.author, b.genre, b.status))

        field_cb.bind("<<ComboboxSelected>>", run_search)
        q_entry.bind("<KeyRelease>", run_search)
        run_search()

    def __dialog_update_book(self) -> None:
        isbn = simpledialog.askstring("Update Book", "Enter ISBN of book to update:", parent=self.__root)
        if not isbn: return
        try:
            book = self.__mgr.get_book(isbn)
            dlg = self.__new_window(f"Update Book: {isbn}", "340x200")
            f = {}
            for r, (lbl, val) in enumerate([("Title", book.title), ("Author", book.author), ("Genre", book.genre)]):
                tk.Label(dlg, text=lbl).grid(row=r, column=0, padx=8, pady=6)
                w = ttk.Combobox(dlg, values=self.GENRES, width=23) if lbl == "Genre" else tk.Entry(dlg, width=26)
                w.insert(0, val); w.grid(row=r, column=1, padx=8, pady=6)
                f[lbl] = w
            def save():
                try:
                    self.__mgr.update_book(isbn, f["Title"].get(), f["Author"].get(), f["Genre"].get())
                    messagebox.showinfo("Success", "Book updated!", parent=dlg)
                    dlg.destroy()
                except Exception as err:
                    messagebox.showerror("Error", str(err), parent=dlg)
            tk.Button(dlg, text="Save Changes", bg="#1565C0", fg="white", command=save).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        except Exception as err:
            messagebox.showerror("Error", str(err))

    def __dialog_delete_book(self) -> None:
        isbn = simpledialog.askstring("Delete Book", "Enter ISBN to delete:", parent=self.__root)
        if not isbn: return
        try:
            if messagebox.askyesno("Confirm", f"Delete book ISBN {isbn}?", parent=self.__root):
                self.__mgr.delete_book(isbn)
                messagebox.showinfo("Deleted", "Book deleted successfully.")
        except Exception as err:
            messagebox.showerror("Error", str(err))

    
    def __open_members_menu(self) -> None:
        self.__make_menu_window("Manage Members", [
            ("Register New Member", self.__dialog_add_member, "#2E7D32"),
            ("View Members Directory", self.__open_members_directory, "#1565C0"),
            ("Update Member", self.__dialog_update_member, "#0277BD"),
            ("Add / Pay Fines", self.__dialog_fines, "#EF6C00"),
            ("Delete Member Record", self.__dialog_delete_member, "#C62828"),
        ])

    def __dialog_add_member(self) -> None:
        dlg = self.__new_window("Register Member", "340x200")
        tk.Label(dlg, text="Member ID:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        m_id = tk.Entry(dlg, width=22); m_id.grid(row=0, column=1, padx=8, pady=6)
        tk.Label(dlg, text="Full Name:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        m_name = tk.Entry(dlg, width=22); m_name.grid(row=1, column=1, padx=8, pady=6)

        def save():
            try:
                self.__mgr.add_member(m_id.get(), m_name.get())
                messagebox.showinfo("Success", "Member registered!", parent=dlg)
                dlg.destroy()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=dlg)
        tk.Button(dlg, text="Register", bg="#2E7D32", fg="white", command=save).grid(row=2, column=1, sticky="e", padx=8, pady=8)

    def __open_members_directory(self) -> None:
        win = self.__new_window("Members Directory", "800x400")
        bar = tk.Frame(win); bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="Search:").pack(side="left")
        q_entry = tk.Entry(bar, width=25); q_entry.pack(side="left", padx=6)

        tree = self.__make_table(win, ("ID", "Name", "Books Borrowed", "Fines (£)"), (110, 200, 370, 100))

        def refresh(*_):
            tree.delete(*tree.get_children())
            for m in self.__mgr.search_members(q_entry.get()):
                tree.insert("", "end", values=(m.member_id, m.name, m.borrowed_text, f"£{m.fines:.2f}"))
        q_entry.bind("<KeyRelease>", refresh)
        refresh()

    def __dialog_update_member(self) -> None:
        mid = simpledialog.askstring("Update Member", "Enter Member ID:", parent=self.__root)
        if not mid: return
        try:
            m = self.__mgr.get_member(mid)
            new_n = simpledialog.askstring("Update Member", "New Name:", initialvalue=m.name, parent=self.__root)
            if new_n is not None:
                self.__mgr.update_member(mid, new_n)
                messagebox.showinfo("Success", "Member name updated.")
        except Exception as err:
            messagebox.showerror("Error", str(err))

    def __dialog_fines(self) -> None:
        mid = simpledialog.askstring("Manage Fines", "Enter Member ID:", parent=self.__root)
        if not mid: return
        try:
            m = self.__mgr.get_member(mid)
            dlg = self.__new_window(f"Fines: {mid} ({m.name})", "320x160")
            tk.Label(dlg, text=f"Current Balance: £{m.fines:.2f}", font=("TkDefaultFont", 10, "bold")).pack(pady=6)
            amt = simpledialog.askfloat("Amount", "Enter amount (£):", minvalue=0.01, parent=dlg)
            if amt is not None:
                def pay(is_p):
                    try:
                        self.__mgr.adjust_fine(mid, amt, is_p)
                        messagebox.showinfo("Success", "Fine adjusted.", parent=dlg)
                        dlg.destroy()
                    except Exception as err:
                        messagebox.showerror("Error", str(err), parent=dlg)
                tk.Button(dlg, text="Add Fine", bg="#EF6C00", fg="white", width=14, command=lambda: pay(False)).pack(side="left", padx=15, pady=10)
                tk.Button(dlg, text="Pay Fine", bg="#00695C", fg="white", width=14, command=lambda: pay(True)).pack(side="right", padx=15, pady=10)
        except Exception as err:
            messagebox.showerror("Error", str(err))

    def __dialog_delete_member(self) -> None:
        mid = simpledialog.askstring("Delete Member", "Enter Member ID to delete:", parent=self.__root)
        if not mid: return
        try:
            if messagebox.askyesno("Confirm", f"Delete member {mid}?", parent=self.__root):
                self.__mgr.delete_member(mid)
                messagebox.showinfo("Deleted", "Member deleted successfully.")
        except Exception as err:
            messagebox.showerror("Error", str(err))

    
    def __open_circulation_menu(self) -> None:
        self.__make_menu_window("Circulation", [
            ("Borrow a Book", self.__open_borrow_window, "#1565C0"),
            ("Return a Book", self.__open_return_window, "#2E7D32"),
            ("View Active Loans", self.__open_loans_window, "#37474F"),
        ])

    def __open_borrow_window(self) -> None:
        win = self.__new_window("Borrow a Book", "420x220")
        tk.Label(win, text="Select Member:").pack(anchor="w", pady=(4, 2))
        m_cb = ttk.Combobox(win, state="readonly", width=45, values=[f"{m.member_id} - {m.name}" for m in self.__mgr.search_members()])
        m_cb.pack(pady=(0, 10))

        tk.Label(win, text="Select Available Book:").pack(anchor="w", pady=(4, 2))
        b_cb = ttk.Combobox(win, state="readonly", width=45, values=[f"{b.isbn} - {b.title}" for b in self.__mgr.search_books("Available", "Availability")])
        b_cb.pack(pady=(0, 15))

        def confirm():
            try:
                if not (m_cb.get() and b_cb.get()): raise ValueError("Select both member and book.")
                self.__mgr.borrow_book(m_cb.get().split(" - ")[0], b_cb.get().split(" - ")[0])
                messagebox.showinfo("Success", "Book borrowed successfully!", parent=win)
                win.destroy()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=win)
        tk.Button(win, text="Confirm Borrow", bg="#00695C", fg="white", font=("TkDefaultFont", 10, "bold"), command=confirm).pack(pady=5)

    def __open_return_window(self) -> None:
        win = self.__new_window("Return a Book", "680x380")
        tk.Label(win, text="Select an active loan below to return:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 6))
        tree = self.__make_table(win, ("Member ID", "Member Name", "ISBN", "Book Title"), (100, 180, 130, 230))

        def refresh():
            tree.delete(*tree.get_children())
            for row in self.__mgr.get_loans(): tree.insert("", "end", values=row)

        def confirm():
            sel = tree.selection()
            if not sel: return messagebox.showwarning("Select", "Select a loan row first.", parent=win)
            vals = tree.item(sel[0])["values"]
            try:
                nxt = self.__mgr.return_book(str(vals[0]), str(vals[2]))
                if nxt:
                    messagebox.showinfo("Auto-Assigned", f"Returned & auto-assigned to waitlisted member:\n{nxt.name} ({nxt.member_id})!", parent=win)
                else:
                    messagebox.showinfo("Returned", "Book returned and is now Available.", parent=win)
                refresh()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=win)

        tk.Button(win, text="Return Selected Book", bg="#2E7D32", fg="white", font=("TkDefaultFont", 10, "bold"), command=confirm).pack(pady=(10, 0))
        refresh()

    def __open_loans_window(self) -> None:
        win = self.__new_window("Active Loans Directory", "680x380")
        tree = self.__make_table(win, ("Member ID", "Member Name", "ISBN", "Book Title"), (100, 180, 130, 230))
        for row in self.__mgr.get_loans(): tree.insert("", "end", values=row)

    
    def __open_waitlist_menu(self) -> None:
        self.__make_menu_window("Waitlist Management", [
            ("Join Book Waitlist", self.__dialog_join_waitlist, "#6A1B9A"),
            ("View Active Waitlists", self.__open_waitlists_directory, "#7B1FA2"),
        ])

    def __dialog_join_waitlist(self) -> None:
        win = self.__new_window("Join Waitlist", "420x220")
        tk.Label(win, text="Select Member:").pack(anchor="w", pady=(4, 2))
        m_cb = ttk.Combobox(win, state="readonly", width=45, values=[f"{m.member_id} - {m.name}" for m in self.__mgr.search_members()])
        m_cb.pack(pady=(0, 10))

        tk.Label(win, text="Select Checked-Out Book:").pack(anchor="w", pady=(4, 2))
        b_cb = ttk.Combobox(win, state="readonly", width=45, values=[f"{b.isbn} - {b.title}" for b in self.__mgr.search_books("Checked Out", "Availability")])
        b_cb.pack(pady=(0, 15))

        def confirm():
            try:
                if not (m_cb.get() and b_cb.get()): raise ValueError("Select both member and book.")
                pos = self.__mgr.join_waitlist(m_cb.get().split(" - ")[0], b_cb.get().split(" - ")[0])
                messagebox.showinfo("Waitlist", f"Added to waitlist at Position #{pos}.", parent=win)
                win.destroy()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=win)
        tk.Button(win, text="Confirm Join", bg="#6A1B9A", fg="white", font=("TkDefaultFont", 10, "bold"), command=confirm).pack(pady=5)

    def __open_waitlists_directory(self) -> None:
        win = self.__new_window("Active Waitlists", "740x380")
        tree = self.__make_table(win, ("ISBN", "Book Title", "Queue #", "Member ID", "Member Name"), (125, 240, 75, 100, 180))

        def refresh():
            tree.delete(*tree.get_children())
            for row in self.__mgr.get_waitlists(): tree.insert("", "end", values=row)

        def remove():
            sel = tree.selection()
            if not sel: return messagebox.showwarning("Select", "Select a queue entry first.", parent=win)
            vals = tree.item(sel[0])["values"]
            try:
                self.__mgr.leave_waitlist(str(vals[3]), str(vals[0]))
                refresh()
            except Exception as err:
                messagebox.showerror("Error", str(err), parent=win)

        tk.Button(win, text="Remove Selected from Queue", bg="#C62828", fg="white", command=remove).pack(anchor="e", pady=(6, 0))
        refresh()

    
    def __open_analytics_window(self) -> None:
        win = self.__new_window("Most Borrowed Books (Analytics)", "860x420")
        left = tk.Frame(win); left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(left, text="Most Borrowed Leaderboard", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 6))
        tree = self.__make_table(left, ("Rank", "Title", "Author", "Genre", "Borrows", "Share %"), (45, 160, 115, 105, 65, 65))

        ranked = self.__mgr.get_most_borrowed()
        for rank, b, pct in ranked:
            tree.insert("", "end", values=(rank, b.title, b.author, b.genre, b.borrow_count, f"{pct}%"))

        right = tk.LabelFrame(win, text="Top Borrowed Chart", padx=8, pady=8)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        canvas = tk.Canvas(right, bg="white", width=310)
        canvas.pack(fill="both", expand=True)

        def draw(_=None):
            canvas.delete("all")
            top = ranked[:6]
            max_b = max((b.borrow_count for _, b, _ in top), default=0)
            w = max(canvas.winfo_width() - 160, 60)
            for idx, (rank, b, _) in enumerate(top):
                y = 20 + idx * 42
                canvas.create_text(10, y + 10, anchor="w", text=f"#{rank} {b.title[:16]}", font=("TkDefaultFont", 8))
                bar_w = int((b.borrow_count / max_b) * w) if max_b else 0
                if bar_w > 0:
                    canvas.create_rectangle(125, y, 125 + bar_w, y + 20, fill="#EF6C00", outline="")
                canvas.create_text(130 + bar_w, y + 10, anchor="w", text=str(b.borrow_count), font=("TkDefaultFont", 8, "bold"))
        canvas.bind("<Configure>", draw)


if __name__ == "__main__":
    root = tk.Tk()
    LibraryGUI(root, LibraryManager(__file__))
    root.mainloop()