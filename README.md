# DeadBasic.BA

[![Made With Python](https://img.shields.io/badge/Made%20with-Python-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

DeadBasic is a **toy programming language** built for fun, demos, and learning.  
It’s lightweight, indentation-based, and runs either interactively or from `.ba` script files.

---

## ✨ Features

- **Typed variables**: `int`, `long`, `double`, `str`
- **Built-in commands**:  
  - `printtext` — print variables or text  
  - `showvars` — list current variables  
  - `openfile` — run another `.ba` file  
  - `add` — add two numbers  
- **Flow control**:  
  - `if / else / endif` — conditional blocks  
  - `while / endwhile` — looping blocks  
- **Indentation-based**: block lines must start with **one TAB** or **four spaces**  
- **Cross-platform**: runs on Windows, Linux, macOS (with Python 3 or as a compiled binary)

---

## 📦 Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/deadbasic.ba.git
cd deadbasic.ba ```

Run with Python 3:

```PY
python deadbasic.py program.ba```


Or launch the interactive console:

```py
python deadbasic.py```

Global install (Linux/macOS)
chmod +x deadbasic.py
sudo mv deadbasic.py /usr/local/bin/deadbasic


Now you can run:

deadbasic program.ba

Build standalone binary
pip install pyinstaller
pyinstaller --onefile deadbasic.py


Executable will be in dist/deadbasic.

📄 Example Program
# variables
int x 0
str name "Ryan"

# loop
while x < 3
    printtext "Loop iteration:" x
    x = x + 1
endwhile

# condition
if x = 3
    printtext name "finished the loop!"
else
    printtext "Unexpected value for x"
endif


Output:

Loop iteration: 0
Loop iteration: 1
Loop iteration: 2
Ryan finished the loop!

▶️ Usage

Interactive Console

python deadbasic.py


Type commands one at a time. Exit with quit, exit, or Ctrl+C.

Run a Script

python deadbasic.py myscript.ba


Commands Quick Reference

int name 10
str title "Hello"
printtext "Message" varname
showvars
openfile "other.ba"
add 2 3

🚧 Limitations

Blocks must end with endif or endwhile

Only one level of if or while is supported (no nesting yet)

Variables are strongly typed; reassignments must match the original type

Indentation must be exactly one TAB or four spaces

🛠 Roadmap

 = assignment (x = x + 1)

 Nested if and while support

 inputtext command for user input

 More math commands (sub, mul, div)

 Functions / proc blocks

 Save/load variables between runs

🤝 Contributing

Pull requests are welcome!
Feel free to add new commands, improve error handling, or extend flow control.
Fork the repo, create a branch, make changes, and submit a PR.

