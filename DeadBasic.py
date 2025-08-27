#!/usr/bin/env python3
# DeadBasic.BA — minimal interpreter with 1-indent IF/ELSE and WHILE
# v0.4.0: adds while/endwhile, clearer error messages, TAB or 4 spaces accepted

import sys, shlex, pathlib

VERSION = "0.4.0"

# ---------- Error types ----------
class DeadBasicError(Exception):
    """Base interpreter error."""
    pass

class SyntaxDeadBasicError(DeadBasicError):
    """Syntax error (e.g., missing indent, bad keywords)."""
    pass

class RuntimeDeadBasicError(DeadBasicError):
    """Runtime error (e.g., type mismatch, unknown var)."""
    pass


class DeadBasic:
    def __init__(self):
        # Vars: name -> {"type": "int|long|double|str", "value": pyvalue}
        self.vars = {}

        # Commands
        self.commands = {
            "printtext": self.cmd_printtext,
            "showvars":  self.cmd_showvars,
            "openfile":  self.cmd_openfile,
            "add":       self.cmd_add,
        }

        # Declarations
        self.type_keywords = {"int", "long", "double", "str"}

        # Flow-control contexts (no nesting by design)
        self.if_ctx = None             # {"cond_true": bool, "in_else": bool}
        self.while_ctx = None          # {"start_pc": int, "cond_tokens": list[str]}

        # For better error messages
        self.current_file = "<repl>"

    # ---------- helpers ----------
    def _resolve(self, token, line_no):
        """Resolve token to a Python value (may be str, int, float)."""
        if token in self.vars:
            return self.vars[token]["value"]
        try:
            if "." in token:
                return float(token)
            return int(token)
        except ValueError:
            pass
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            return token[1:-1]
        return token

    def _to_number(self, value, line_no, label="value"):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return float(int(value))
            except ValueError:
                pass
        raise RuntimeDeadBasicError(self._fmt(line_no,
            f"{label} is not numeric"))

    def _truthy(self, value):
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value != ""
        return True

    def _fmt(self, line_no, msg):
        return f"[{self.current_file}:line {line_no}] {msg}"

    def _detect_indent(self, line: str):
        """Return (indent, content). indent==1 if line starts with TAB or 4 spaces."""
        if line.startswith("\t"):
            return 1, line[1:]
        if line.startswith("    "):
            return 1, line[4:]
        return 0, line

    # ---------- condition evaluation (shared by IF/WHILE) ----------
    def _eval_condition_tokens(self, tokens, line_no):
        if not tokens:
            raise SyntaxDeadBasicError(self._fmt(line_no, "condition required"))
        if tokens[0].lower() == "not":
            if len(tokens) != 2:
                raise SyntaxDeadBasicError(self._fmt(line_no, "'not' expects exactly one value"))
            val = self._resolve(tokens[1], line_no)
            return not self._truthy(val)

        if len(tokens) != 3:
            raise SyntaxDeadBasicError(self._fmt(line_no,
                "condition must be: <lhs> <op> <rhs> or 'not <value>'"))

        lhs_tok, op, rhs_tok = tokens
        lhs_val = self._resolve(lhs_tok, line_no)
        rhs_val = self._resolve(rhs_tok, line_no)

        if op == "=":
            return lhs_val == rhs_val
        if op == "!=":
            return lhs_val != rhs_val

        lnum = self._to_number(lhs_val, line_no, "left side")
        rnum = self._to_number(rhs_val, line_no, "right side")
        if op == "<":
            return lnum < rnum
        if op == ">":
            return lnum > rnum
        if op == "<=":
            return lnum <= rnum
        if op == ">=":
            return lnum >= rnum

        raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown operator '{op}'"))

    def _should_execute_if_body_line(self):
        if self.if_ctx is None:
            return False
        if not self.if_ctx["in_else"] and self.if_ctx["cond_true"]:
            return True
        if self.if_ctx["in_else"] and not self.if_ctx["cond_true"]:
            return True
        return False

    # ---------- commands ----------
    def cmd_printtext(self, args, line_no):
        if not args:
            raise SyntaxDeadBasicError(self._fmt(line_no, "printtext needs text or var names"))
        out = []
        for tok in args:
            if tok in self.vars:
                out.append(str(self.vars[tok]["value"]))
            else:
                out.append(tok)
        print(" ".join(out))

    def cmd_showvars(self, args, line_no):
        if not self.vars:
            print("(no vars)")
            return
        for k, meta in self.vars.items():
            print(f"{meta['type']} {k} = {meta['value']}")

    def cmd_openfile(self, args, line_no):
        if not args:
            raise SyntaxDeadBasicError(self._fmt(line_no, "openfile needs a filename"))
        path = pathlib.Path(args[0])
        # Clear dangling control states before jumping into another file
        self.if_ctx = None
        self.while_ctx = None
        self.run_file(path)

    def cmd_add(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "add needs exactly 2 numbers"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        b = self._to_number(self._resolve(args[1], line_no), line_no, "second argument")
        result = a + b
        print(int(result) if result.is_integer() else result)

    def cmd_declare(self, vtype, args, line_no):
        if len(args) < 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"{vtype} needs: <name> <value>"))
        name, *raw_value = args
        value_str = " ".join(raw_value)
        if vtype in {"int", "long"}:
            try:
                val = int(value_str)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{value_str}' is not an integer"))
        elif vtype == "double":
            try:
                val = float(value_str)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{value_str}' is not a double"))
        elif vtype == "str":
            val = value_str.strip('"')
        else:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown type: {vtype}"))
        if name in self.vars and self.vars[name]["type"] != vtype:
            raise RuntimeDeadBasicError(self._fmt(line_no,
                f"type mismatch: {name} is {self.vars[name]['type']}, not {vtype}"))
        self.vars[name] = {"type": vtype, "value": val}

    # ---------- single-line execution (used by REPL) ----------
    def execute_line(self, line, line_no):
        """Executes a *single* textual line. Suitable for REPL.
        Loops are not supported here (they need multi-line scan)."""
        indent, content = self._detect_indent(line)
        raw = content.strip()
        if not raw:
            return
        if raw.startswith("#") or raw.startswith("//"):
            return

        try:
            tokens = shlex.split(raw, posix=True)
        except ValueError as e:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"parse error: {e}"))
        if not tokens:
            return

        head, *args = tokens
        head_l = head.lower()

        # REPL: disallow while/endwhile (needs multi-line control)
        if head_l in {"while", "endwhile"}:
            raise SyntaxDeadBasicError(self._fmt(line_no,
                "while/endwhile are only supported in .ba files, not in REPL"))

        # IF/ELSE/ENDIF handling at top level in REPL
        if indent == 0:
            if head_l == "if":
                if self.if_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no,
                        "Nested IF not supported (previous IF missing 'endif'?)"))
                cond = self._eval_condition_tokens(args, line_no)
                self.if_ctx = {"cond_true": cond, "in_else": False}
                return
            if head_l == "else":
                if self.if_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'else' without matching 'if'"))
                if self.if_ctx["in_else"]:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'else' not allowed"))
                self.if_ctx["in_else"] = True
                return
            if head_l == "endif":
                if self.if_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'endif' without matching 'if'"))
                self.if_ctx = None
                return

            # If an IF is open, only else/endif are legal at top level
            if self.if_ctx is not None:
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "Inside IF: expected an indented line (TAB/4 spaces), 'else', or 'endif'"))

            # decls / commands
            if head_l in self.type_keywords:
                self.cmd_declare(head_l, args, line_no); return
            if head_l not in self.commands:
                raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
            self.commands[head_l](args, line_no); return

        # Indented line
        if indent == 1:
            if self.if_ctx is None:
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "You are missing the required TAB/4 spaces before this IF body line"))
            if head_l in {"if", "else", "endif"}:
                raise SyntaxDeadBasicError(self._fmt(line_no, f"'{head_l}' must be at top level (no indent)"))
            if not self._should_execute_if_body_line():
                return
            if head_l in self.type_keywords:
                self.cmd_declare(head_l, args, line_no); return
            if head_l not in self.commands:
                raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
            self.commands[head_l](args, line_no); return

    # ---------- file execution with program counter (supports WHILE) ----------
    def run_file(self, path: pathlib.Path):
        if not path.exists():
            raise RuntimeDeadBasicError(self._fmt(0, f"file not found: {path}"))
        self.current_file = str(path)
        self.if_ctx = None
        self.while_ctx = None

        with path.open("r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]

        pc = 0
        n = len(lines)

        def parse_tokens(line, lno):
            indent, content = self._detect_indent(line)
            raw = content.strip()
            return indent, raw, (shlex.split(raw, posix=True) if raw and not raw.startswith(("#", "//")) else [])

        while pc < n:
            line_no = pc + 1
            line = lines[pc]
            indent, raw, tokens = parse_tokens(line, line_no)

            if not raw or raw.startswith("#") or raw.startswith("//"):
                pc += 1
                continue

            head, *args = tokens
            head_l = head.lower()

            # ---- Top-level control: IF/ELSE/ENDIF/WHILE/ENDWHILE
            if indent == 0:

                # WHILE
                if head_l == "while":
                    if self.while_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no,
                            "Nested WHILE not supported"))
                    if self.if_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no,
                            "WHILE cannot start inside an open IF; close IF first"))
                    cond = self._eval_condition_tokens(args, line_no)
                    # find matching endwhile to allow skipping when false
                    # (no nesting => first top-level 'endwhile' we meet)
                    if not cond:
                        j = pc + 1
                        found = False
                        while j < n:
                            i2, raw2, tok2 = parse_tokens(lines[j], j + 1)
                            if i2 == 0 and tok2 and tok2[0].lower() == "endwhile":
                                found = True
                                break
                            j += 1
                        if not found:
                            raise SyntaxDeadBasicError(self._fmt(line_no,
                                "missing 'endwhile' for this 'while'"))
                        # skip to line after 'endwhile'
                        pc = j + 1
                        continue
                    # condition true -> enter loop
                    self.while_ctx = {"start_pc": pc, "cond_tokens": args}
                    pc += 1
                    continue

                if head_l == "endwhile":
                    if self.while_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'endwhile' without matching 'while'"))
                    # re-evaluate condition
                    cond = self._eval_condition_tokens(self.while_ctx["cond_tokens"], line_no)
                    if cond:
                        # jump back to line after 'while' header
                        pc = self.while_ctx["start_pc"] + 1
                        continue
                    else:
                        # exit loop
                        self.while_ctx = None
                        pc += 1
                        continue

                # IF
                if head_l == "if":
                    if self.if_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no,
                            "Nested IF not supported (previous IF missing 'endif'?)"))
                    if self.while_ctx is not None:
                        # allowed to be inside a loop, but IF header must be top-level already (it is)
                        pass
                    cond = self._eval_condition_tokens(args, line_no)
                    self.if_ctx = {"cond_true": cond, "in_else": False}
                    pc += 1
                    continue

                if head_l == "else":
                    if self.if_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'else' without matching 'if'"))
                    if self.if_ctx["in_else"]:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'else' not allowed"))
                    self.if_ctx["in_else"] = True
                    pc += 1
                    continue

                if head_l == "endif":
                    if self.if_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'endif' without matching 'if'"))
                    self.if_ctx = None
                    pc += 1
                    continue

                # If an IF is open, only else/endif are allowed at top level
                if self.if_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no,
                        "Inside IF: expected an indented body line (TAB/4 spaces), 'else', or 'endif'"))

                # Declarations / Commands
                if head_l in self.type_keywords:
                    self.cmd_declare(head_l, args, line_no)
                    pc += 1
                    continue
                if head_l not in self.commands:
                    raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                self.commands[head_l](args, line_no)
                pc += 1
                continue

            # ---- Indented body line (IF or WHILE body)
            if indent == 1:
                if head_l in {"if", "else", "endif", "while", "endwhile"}:
                    raise SyntaxDeadBasicError(self._fmt(line_no, f"'{head_l}' must be at top level (no indent)"))

                # IF body?
                if self.if_ctx is not None:
                    if not self._should_execute_if_body_line():
                        pc += 1
                        continue
                    # execute IF body line
                    if head_l in self.type_keywords:
                        self.cmd_declare(head_l, args, line_no)
                    else:
                        if head_l not in self.commands:
                            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                        self.commands[head_l](args, line_no)
                    pc += 1
                    continue

                # WHILE body?
                if self.while_ctx is not None:
                    # execute WHILE body line
                    if head_l in self.type_keywords:
                        self.cmd_declare(head_l, args, line_no)
                    else:
                        if head_l not in self.commands:
                            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                        self.commands[head_l](args, line_no)
                    pc += 1
                    continue

                # Indent but no block => syntax error
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "You are missing the required 'while/if' before this indented line"))

        # End of file: check for dangling blocks
        if self.if_ctx is not None:
            raise SyntaxDeadBasicError(self._fmt(n, "file ended but 'endif' is missing"))
        if self.while_ctx is not None:
            raise SyntaxDeadBasicError(self._fmt(n, "file ended but 'endwhile' is missing"))


# ---------- CLI / REPL ----------
def usage():
    print(
        f"DeadBasic.BA v{VERSION}\n"
        "Usage:\n"
        "  python deadbasic.py <program.ba>\n"
        "  python deadbasic.py        # REPL (no multi-line while)\n"
        "\n"
        "Notes:\n"
        "  - Decls: int x 5 | long big 999999 | double pi 3.14 | str name \"Ryan\"\n"
        "  - Cmds : printtext ... | showvars | openfile \"file.ba\" | add a b\n"
        "  - IF   : if <lhs> <op> <rhs> | if not <val> ; ops: = != < > <= >=\n"
        "  - WHILE: while <cond> ... endwhile   (no nesting; body uses ONE TAB or FOUR SPACES)\n"
        "  - Comments start with # or //\n"
    )

def repl():
    print(f"DeadBasic.BA Console v{VERSION} — Ctrl+C to exit")
    db = DeadBasic()
    line_no = 0
    try:
        while True:
            line_no += 1
            line = input("DB> ")
            if line.strip().lower() in {"exit", "quit"}:
                break
            try:
                db.execute_line(line, line_no)
            except DeadBasicError as e:
                print(e)
    except (EOFError, KeyboardInterrupt):
        print("\nbye")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        repl()
    elif len(sys.argv) == 2:
        prog = pathlib.Path(sys.argv[1])
        db = DeadBasic()
        try:
            db.run_file(prog)
        except DeadBasicError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
    else:
        usage()
        sys.exit(2)
