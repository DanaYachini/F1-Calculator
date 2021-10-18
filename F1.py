# F1 calculator by Dana Yachini

###########################
##       Imports         ##
###########################
import pyparsing as pp
import unicodecsv as csv
import pandas as pd
import os
import tkinter as tk
from tkinter import simpledialog
from tkinter import filedialog
from tkinter import messagebox

###########################
##        Classes        ##
###########################
node_count = 0
line_count = 0


# classes for all F1 lexical groups:
# Node: base case for all tree nodes
class Node:
    def __init__(self, f1_type, text):
        global node_count
        self.f1_type = f1_type
        node_count += 1
        self.name = f1_type + str(node_count)
        self.text = text
        self.value_as_text = text
        self.value_as_item = text
        self.line_num = 0
        self.line_num_v = 0

    def __repr__(self):
        return "[" + self.name + " " + self.text + "]"

    def write_line_node(self, r, writer, using_text=True, v_name="v"):
        global line_count
        line_count += 1
        ln = str(line_count)

        if using_text:
            val = self.value_as_text
        else:
            val = "%s" % self.value_as_item
            if type(self.value_as_item) == list:
                val = val.replace("(", "<").replace(")", ">").replace("[", "{").replace("]", "}")

        e = u"[[%s]]%s = %s" % (self.name, v_name, val)

        if v_name == "v":
            self.line_num = line_count
        else:
            self.line_num_v = line_count
            e = e.replace("'", "").replace("True", "1").replace("False", "0")

        writer.writerow([ln, e, r])

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        return self.value_as_item

# N: noun
class N(Node):
    def __init__(self, text):
        Node.__init__(self, "N", text)

    def write_line(self, writer):
        Node.write_line_node(self, "VL,R1", writer)

# Vi: verb (inntransitive)
class Vi(Node):
    def __init__(self, text):
        Node.__init__(self, "Vi", text)
        self.value_as_item = []
        self.value_as_text = "{x: x %s in v}" % text

    def write_line(self, writer):
        Node.write_line_node(self, "VL,R1", writer)

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        if self.name in v.keys():
            self.value_as_item = v[self.name]
        else:
            self.value_as_item = verb_dict_v[self.name]
            v[self.name] = self.value_as_item
            self.write_line_node(v_name, writer, using_text=False, v_name=v_name)
        return self.value_as_item

# Vt: verb (transitive)
class Vt(Node):
    def __init__(self, text):
        Node.__init__(self, "Vt", text)
        self.value_as_item = []
        self.value_as_text = "{<x,y>: x %s y in v}" % text

    def write_line(self, writer):
        Node.write_line_node(self, "VL,R1", writer)

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        if self.name in v.keys():
            self.value_as_item = v[self.name]
        else:
            self.value_as_item = verb_dict_v[self.name]
            v[self.name] = self.value_as_item
            self.write_line_node(v_name, writer, using_text=False, v_name=v_name)
        return self.value_as_item

# Neg: negation
class Neg(Node):
    def __init__(self, text):
        Node.__init__(self, "Neg", text)
        self.value_as_item = lambda x: not x
        self.value_as_text = "[0 -> 1; 1 -> 0]"

    def write_line(self, writer):
        Node.write_line_node(self, "VL,R1", writer)

# Conj: conjuction ('or'\'and')
class Conj(Node):
    def __init__(self, text):
        Node.__init__(self, "Conj", text)
        if text.lower() == "or":
            self.value_as_item = lambda x, y: x or y
            self.value_as_text = "[<0,0> -> 0; <0,1> -> 1; <1,0> -> 1; <1,1> -> 1]"
        elif text.lower() == "and":
            self.value_as_item = lambda x, y: x and y
            self.value_as_text = "[<0,0> -> 0; <0,1> -> 0; <1,0> -> 0; <1,1> -> 1]"
        else:
            raise ValueError("invalid Conj value: can only accept 'and' or 'or")

    def write_line(self, writer):
        Node.write_line_node(self, "VL,R1", writer)

# Phrase: base case for complex phrase with children (VP and S)
class Phrase(Node):
    def __init__(self, f1_type, children):
        Node.__init__(self, f1_type, " ".join([x.text for x in children]))
        self.children = children

    def __repr__(self):
        return "[" + self.name + "".join([str(x) for x in self.children]) + "]"

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        return [x.evaluate_in_v(v_name, writer, v, verb_dict_v) for x in self.children]

    def get_all_verbs(self):
        verb_list = [x for x in self.children if x.f1_type in ["Vi", "Vt"]]
        # verb_list += [x.get_all_verbs() for x in self.children if x.f1_type in ["VP", "S"]]
        for child in self.children:
            if child.f1_type in ["VP", "S"]:
                verb_list += child.get_all_verbs()
        return verb_list

# VP: verb phrase
class VP(Phrase):
    def __init__(self, children):
        Phrase.__init__(self, "VP", children)
        self.value_as_item = []

    def write_line(self, writer):
        vp_type = [x.f1_type for x in self.children]
        if vp_type == ["Vi"]:
            self.value_as_text = self.children[0].value_as_text
            Node.write_line_node(self, "R1,L%d" % self.children[0].line_num, writer)
        elif vp_type == ["Vt", "N"]:
            self.value_as_text = u"{x: <x,[[%s]]> ∈ [[%s]]}" % (self.children[1].name, self.children[0].name)
            Node.write_line_node(self, "R3", writer)
            self.value_as_text = u"{x: <x,%s> ∈ %s}" % (self.children[1].text, self.children[0].value_as_text)
            Node.write_line_node(self, "L%d,L%d,L%d" %
                                 (self.line_num, self.children[0].line_num, self.children[1].line_num), writer)
            self.value_as_text = "{x: x %s %s in v}" % (self.children[0].text, self.children[1].text)
            Node.write_line_node(self, "S,L%d" % self.line_num, writer)

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        if self.name in v.keys():
            self.value_as_item = v[self.name]
        else:
            Phrase.evaluate_in_v(self, v_name, writer, v, verb_dict_v)
            vp_type = [x.f1_type for x in self.children]
            if vp_type == ["Vi"]:
                self.value_as_item = self.children[0].value_as_item
                self.write_line_node("R1", writer, using_text=False, v_name=v_name)
            elif vp_type == ["Vt", "N"]:
                old = self.value_as_text
                self.value_as_text = "{x: <x,%s> ∈ %s}" % (self.children[1].text, self.children[0].value_as_item)
                self.value_as_text = self.value_as_text.replace("(", "<").replace(")", ">")
                self.value_as_text = self.value_as_text.replace("[", "{").replace("]", "}")
                Node.write_line_node(self, "L%d,L%d,L%d" %
                                     (self.line_num - 1, self.children[0].line_num, self.children[1].line_num_v),
                                     writer, v_name=v_name)
                self.value_as_text = old
                self.value_as_item = [x[0] for x in self.children[0].value_as_item if x[1] ==
                                      self.children[1].value_as_item]
                self.write_line_node("C%d" % self.line_num_v, writer, using_text=False, v_name=v_name)
            v[self.name] = self.value_as_item
        return self.value_as_item

# S: sentence
class S(Phrase):
    def __init__(self, children):
        Phrase.__init__(self, "S", children)
        self.value_as_item = None
        self.s_type = [x.f1_type for x in self.children]

    def write_line(self, writer):
        if self.s_type == ["N", "VP"]:
            self.value_as_text = u"1 iff [[%s]] ∈ [[%s]]; 0 o.w" % (self.children[0].name, self.children[1].name)
            Node.write_line_node(self, "R2", writer)
            self.value_as_text = u"1 iff %s ∈ %s; 0 o.w" % (self.children[0].text, self.children[1].value_as_text)
            Node.write_line_node(self, "L%d,L%d,L%d" %
                                 (self.line_num, self.children[0].line_num, self.children[1].line_num), writer)
        elif self.s_type == ["Neg", "S"]:
            self.value_as_text = "[[%s]]([[%s]])" % (self.children[0].name, self.children[1].name)
            Node.write_line_node(self, "R4,L%d,L%d" % (self.children[0].line_num, self.children[1].line_num), writer)
            self.value_as_text = negate_text(self.children[1])
            Node.write_line_node(self, "C,L%d" % self.line_num, writer)
        elif self.s_type == ["S", "Conj", "S"]:
            self.value_as_text = "[[%s]](<[[%s]],[[%s]]>)" % (self.children[1].name, self.children[0].name,
                                                              self.children[2].name)
            Node.write_line_node(self, "R5,L%d,L%d,L%d" % (self.children[0].line_num, self.children[1].line_num,
                                                           self.children[2].line_num), writer)
            self.value_as_text = "1 " + build_conj_tree(self) + "\n; 0 o.w"
            Node.write_line_node(self, "C,L%d" % self.line_num, writer)

    def evaluate_in_v(self, v_name, writer, v={}, verb_dict_v={}):
        if self.name in v.keys():
            self.value_as_item = v[self.name]
        else:
            Phrase.evaluate_in_v(self, v_name, writer, v, verb_dict_v)
            old = self.value_as_text
            if self.s_type == ["N", "VP"]:
                self.value_as_text = self.value_as_text.replace(self.children[1].value_as_text,
                                                                "%s" % self.children[1].value_as_item)
                self.value_as_text = self.value_as_text.replace("(", "<").replace(")", ">")
                self.value_as_text = self.value_as_text.replace("[", "{").replace("]", "}")
                Node.write_line_node(self, "L%d,L%d" %
                                     (self.line_num, self.children[1].line_num_v),
                                     writer, v_name=v_name)
                self.value_as_item = (self.children[0].value_as_item.lower() in self.children[1].value_as_item)
                self.write_line_node("C%d" % self.line_num_v, writer, using_text=False, v_name=v_name)
            elif self.s_type == ["Neg", "S"]:
                self.value_as_text = "%s(%s)" % (self.children[0].value_as_text, self.children[1].value_as_item)
                Node.write_line_node(self, "L%d,L%d" %
                                     (self.line_num - 1, self.children[1].line_num_v),
                                     writer, v_name=v_name)
                self.value_as_item = self.children[0].value_as_item(self.children[1].value_as_item)
                self.write_line_node("C%d" % self.line_num_v, writer, using_text=False, v_name=v_name)
            elif self.s_type == ["S", "Conj", "S"]:
                self.value_as_text = "%s(<%s,%s>)" % (self.children[1].value_as_text, self.children[0].value_as_item,
                                                      self.children[2].value_as_item)
                self.write_line_node("L%d,L%d,L%d" %
                                     (self.line_num - 1, self.children[0].line_num_v, self.children[2].line_num_v),
                                     writer, v_name=v_name)
                self.value_as_item = self.children[1].value_as_item(self.children[0].value_as_item,
                                                                    self.children[2].value_as_item)
                self.write_line_node("C%d" % self.line_num_v, writer, using_text=False, v_name=v_name)
            v[self.name] = self.value_as_item
            self.value_as_text = old
        return self.value_as_item


###########################
##      Functions        ##
###########################

# get a sentence object, returns list of list for all rows for a csv of tree hirarchy
def get_tree_hirarchy_lines(tree):
    row = [tree.name + ":"]

    if tree.f1_type in ["S", "VP"]:
        child0rows = get_tree_hirarchy_lines(tree.children[0])
        row += child0rows[0]
        rows = [row] + [[""] + x for x in child0rows[1:]]

        for i in tree.children[1:]:
            new_rows = get_tree_hirarchy_lines(i)
            rows += [[""] + x for x in new_rows]

        return rows
    else:
        row.append(tree.text)
        return [row]

# get parsed nested lists for tree and file writer, make sentence object and write to main csv
def make_tree(parse_tree, writer, tree_dict={}):
    first = parse_tree.pop(0)
    if first in ["S", "VP"]:
        childes = [make_tree(x, writer, tree_dict) for x in parse_tree]
        new_node = class_dict[first](childes)
    else:
        new_node = class_dict[first](" ".join(parse_tree[0]))

    if (new_node.f1_type, new_node.text) in list(tree_dict.keys()):
        global node_count
        node_count -= 1
        return tree_dict[(new_node.f1_type, new_node.text)]
    tree_dict[(new_node.f1_type, new_node.text)] = new_node
    new_node.write_line(writer)
    return new_node

# get a negation sentence object, return text describing its truth contitions
def negate_text(sentence):
    s_type = [x.f1_type for x in sentence.children]
    if s_type == ["N", "VP"]:
        neg_sen = sentence.value_as_text.replace("∈", "∉")
    elif s_type == ["Neg", "S"]:
        neg_sen = sentence.children[1].value_as_text
    else:
        neg_sen = "1 iff "
        conj_list = list(conj_tree_dict)
        neg_sen += conj_tree_dict[conj_list[conj_list.index(sentence.children[1].text) - 1]]
        neg_sen += "\n"
        for child_sen in [sentence.children[0], sentence.children[2]]:
            neg_child = negate_text(child_sen)
            neg_child = neg_child.replace("1 iff ", "").replace("; 0 o.w", "").strip()
            for line in neg_child.split("\n"):
                neg_sen += "...." + line + "\n"
        neg_sen += ";0 o.w"
    return neg_sen

# get a conj sentence object, return text describing its truth contitions
def build_conj_tree(sentence, depth=0):
    conj_str = ("...." * depth) + conj_tree_dict[sentence.children[1].text]
    for child_sen in [sentence.children[0], sentence.children[2]]:
        s_type = [x.f1_type for x in child_sen.children]
        if s_type == ["N", "VP"] or ["Neg", "S"]:
            lines = child_sen.value_as_text.replace("1 iff ", "").replace(";0 o.w", "").strip().split("\n")
            for line in lines:
                conj_str += "\n...." + line
        else:
            lines = build_conj_tree(child_sen, depth + 1).replace("; 0 o.w", "")
            conj_str += "\n" + lines
    return conj_str.replace("; 0 o.w", "")

# create main csv and call write tree, return sentece object
def make_main_csv(dir_path, sentence):
    file = None
    sen = None
    filepath = r"%s\F1_temp.csv" % dir_path
    try:
        # file setup
        file = open(filepath, "wb")
        writer = csv.writer(file, encoding='utf-8')
        writer.writerow(["line", "expression", "rule"])

        # bulding tree and file
        sen = make_tree(s.parseString(sentence), writer)
    except IOError:
        print("file cant be opend")
    except pp.ParseException:
        print("bad sentence")
    finally:
        if file:
            file.close()
        return sen

# get path and sentence object, make tree hirarchy csv (calls get_tree_hirarchy_lines)
def make_hirarchy_csv(dir_path, sentence):
    tree_file = None
    filename = dir_path + "\\%s (tree).csv" % sentence.text
    try:
        tree_file = open(filename, "wb")
        tree_writer = csv.writer(tree_file, encoding='utf-8')
        lines = get_tree_hirarchy_lines(sentence)
        tree_writer.writerows(lines)
    except IOError:
        print("IO error opening %s" % filename)
    finally:
        if tree_file:
            tree_file.close()

# get dir path and name of v, calculates truth value in main csv (calls Node methode evaluate_in_v)
def add_v_to_main_csv(dir_path, sentence, v, verb_dict_v):
    file = None
    try:
        file = open(r"%s\F1_temp.csv" % dir_path, "ab")
        v_writer = csv.writer(file, encoding='utf-8')
        sentence.evaluate_in_v(v, v_writer, verb_dict_v=verb_dict_v, v={})
    except IOError:
        print("IO error in appending v")
    finally:
        if file:
            file.close()

# get csv path and new filename, creates xlsx and deletes original csv
def save_xlsx_delete(filepath, newname):
    read_file = pd.read_csv(filepath)
    read_file.to_excel((r"%s" % (filepath.replace("F1_temp", newname).replace(".csv", ".xlsx"))),
                       index=None, header=True)
    os.remove(filepath)
    # except FileCreateError:
    #    global sen_obj
    #    messagebox.showerror("Failed save", "Error: could not save.\n"
    #                                        "make sure no file with name:\n"
    #                                        "%s.xlsx\n"
    #                                        "is open, and that you can\n"
    #                                        "save files to your selected\n"
    #                                        "output folder." % sen_obj.text)

# get string, returns a list of verb group members according to type
def convert_str_to_group_list(string, f1_type):
    out_list = []
    if string:
        if f1_type == "Vt":
            lst = pairs_group.parseString(string.lower())
            out_list = [(" ".join(x[0]), " ".join(x[1])) for x in lst]
        elif f1_type == "Vi":
            out_list = string.lower().split(",")
    return out_list

# function for main frame evaluation button, create second page for inputing group members in v
def get_group_members_btn():
    global sen_obj
    if sen_obj:
        global verb_dict
        frame_main.pack_forget()
        frame_v = tk.Frame(win)
        frame_v.configure(bg="#2b2b2b")
        verb_dict = {}
        v_header = tk.Label(frame_v, text="Evaluate in V", **header_style)
        v_label = tk.Label(frame_v, text="Name: v", **label_style)
        v_entry = tk.Entry(frame_v, **entry_style)
        v_header.grid(column=0, row=0, columnspan=2)
        v_label.grid(column=0, row=1, sticky="e", padx=10)
        v_entry.grid(column=1, row=1, padx=10)
        i = 2
        for ver in list(set(sen_obj.get_all_verbs())):
            new_label = tk.Label(frame_v, text=ver.value_as_text, **label_style)
            new_entry = tk.Entry(frame_v, **entry_style)
            verb_dict[(ver.name, ver.f1_type)] = new_entry
            new_label.grid(column=0, row=i, padx=10, sticky="e")
            new_entry.grid(column=1, row=i, padx=10)
            i += 1

        # creting the button that will be in the second frame
        # reading fron all entrys for verbs group members, evaluate v in file (calls add_v_to_main_csv)
        def eval_btn():
            global verb_dict
            global vs_list
            if v_entry.get() in vs_list:
                messagebox.showwarning("V name", "State of reality:\nv%s\n already exists in your file" % v_entry.get())
            else:
                try:
                    verb_dict = dict([(v[0],
                                       convert_str_to_group_list(verb_dict[v].get(),
                                                                 v[1])) for v in verb_dict.keys()])
                    global sen_obj
                    add_v_to_main_csv(entry_path.get(), sen_obj, "v" + v_entry.get(), verb_dict)
                    frame_v.pack_forget()
                    frame_main.pack()
                    vs_list += v_entry.get()
                except pp.ParseException:
                    simpledialog.messagebox.showwarning("bad input", "The group does not match format\n"
                                                                     "<x,y>,<z,w>....\nTry again")

        btn_eval = tk.Button(frame_v, text="Evaluate", **button_style, command=eval_btn)
        btn_eval.grid(column=1, row=i)
        frame_v.pack()

# function for browse button, opens folder browser
def browse_btn():
    entry_path.delete(0, tk.END)
    dirname = filedialog.askdirectory(initialdir="/")
    entry_path.insert(0, dirname)

# show warning in case of exit when temp was not saved to exel, option to save before exit
def close_btn():
    global sen_obj

    if sen_obj:
        opt = messagebox.askyesnocancel("Unsaved",
                                        "You have not saved your file.\nDo you wish to save as exel before exiting?")
        filepath = entry_path.get() + "/F1_temp.csv"
        if opt:
            try:
                save_xlsx_delete(filepath, sen_obj.text)
                win.destroy()
            except:
                messagebox.showerror("Failed save", "Error: could not save.\n"
                                                    "make sure no file with name:\n"
                                                    "%s.xlsx\n"
                                                    "is open, and that you can\n"
                                                    "save files to your selected\n"
                                                    "output folder." % sen_obj.text)
        elif str(opt) == "False":
            os.remove(filepath)
            os.remove(filepath.replace("/F1_temp", "/%s (tree)" % sen_obj.text))
            win.destroy()
    else:
        win.destroy()

# function for create button, makes the temp csv and creates sentence object
def create_btn():
    if not entry_path.get():
        messagebox.showwarning("no folder path", "The output folder path is empty")
    else:
        try:
            s.parseString(entry_sen.get())
            try:
                global sen_obj
                global line_count
                global node_count
                line_count = 0
                node_count = 0
                sen_obj = make_main_csv(entry_path.get(), entry_sen.get())
                make_hirarchy_csv(entry_path.get(), sen_obj)
                btn_create["state"] = tk.DISABLED
                btn_browse["state"] = tk.DISABLED
                btn_save["state"] = tk.NORMAL
                btn_getgroups["state"] = tk.NORMAL
                entry_path["state"] = tk.DISABLED
                entry_sen["state"] = tk.DISABLED
                tk.messagebox.showinfo("sucess", "temp file created sucessfully")
            except:
                messagebox.showwarning("bad sentence", "The sentece does not follow F1 rules")
        except pp.ParseException:
            messagebox.showwarning("bad sentence", "The sentece does not follow F1 rules")

# saves temp csv as exel, enable creation of new sentence+file
def save_btn():
    global sen_obj
    try:
        save_xlsx_delete(entry_path.get() + "/F1_temp.csv", sen_obj.text)
        global verb_dict
        global vs_list
        verb_dict = {}

        sen_obj = None
        vs_list = [""]
        btn_create["state"] = tk.NORMAL
        btn_browse["state"] = tk.NORMAL
        btn_save["state"] = tk.DISABLED
        btn_getgroups["state"] = tk.DISABLED
        entry_path["state"] = tk.NORMAL
        entry_sen["state"] = tk.NORMAL
        entry_sen.delete(0, "end")
    except:
        messagebox.showerror("Failed save", "Error: could not save.\n"
                                            "make sure no file with name:\n"
                                            "%s.xlsx\n"
                                            "is open, and that you can\n"
                                            "save files to your selected\n"
                                            "output folder." % sen_obj.text)


# shows messegbox with usage info
def info_btn():
    opt = messagebox.askquestion("Info", "Using the browse button,\n"
                                         "select a folder for the output files.\n"
                                         "In the second field, enter a sentece\n"
                                         "that follows F1 rules.\n"
                                         "Do you wish to view the rules?")
    if opt == "yes":
        messagebox.showinfo("F1 rules", "N: [N words go here]\n"
                                        "Vt: [Vt words go here]\n"
                                        "Vi: [Vi words go here]\n"
                                        "Conj: [Conj and]\\[Conj or] \n"
                                        "Neg: [Neg words go here]\n"
                                        "VP: [VP Vi]\\[VP Vt N]\n"
                                        "S: [S N VP]\\[S Neg S]\\[S S Conj S]\n"
                                        "\nExaples:\n"
                                        "[S[N F1][VP[Vi is cool]]]\n"
                                        "[S[Neg it is not the case that][S[N F1][VP[Vi is hard]]]]"
                            )


###########################
##         Code          ##
###########################

class_dict = {
    "N": N,
    "Vi": Vi,
    "Vt": Vt,
    "Neg": Neg,
    "Conj": Conj,
    "VP": VP,
    "S": S
}

conj_tree_dict = {
    "or": "iff either holds:",
    "and": "iff both hold:"
}

sen_obj = None
verb_dict = {}
vs_list = [""]

# Literals to ingnore in parsing
lpar = pp.Literal("[").suppress()
rpar = pp.Literal("]").suppress()
rtup = pp.Literal(">").suppress()
ltup = pp.Literal("<").suppress()
com = pp.Literal(",").suppress()

# Define format of lexical groups
noun = lpar + pp.Keyword("N") + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + rpar
verb_i = lpar + pp.Keyword("Vi") + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + rpar
verb_t = lpar + pp.Keyword("Vt") + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + rpar
conj = lpar + pp.Keyword("Conj") + pp.Group(pp.CaselessKeyword("and") | pp.CaselessKeyword("or")) + rpar
neg = lpar + pp.Keyword("Neg") + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + rpar
vp = lpar + pp.Keyword("VP") + (pp.Group(verb_i) | pp.Group(verb_t) + pp.Group(noun)) + rpar
s = pp.Forward()
S_NV = lpar + pp.Keyword("S") + pp.Group(noun) + pp.Group(vp) + rpar
S_neg = lpar + pp.Keyword("S") + pp.Group(neg) + pp.Group(s) + rpar
S_conj = lpar + pp.Keyword("S") + pp.Group(s) + pp.Group(conj) + pp.Group(s) + rpar
s << (S_neg | S_NV | S_conj)

# define format for group of pairs: <x,y>,<z,w>....
pair = ltup + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + com + pp.Group(pp.OneOrMore(pp.Word(pp.alphas))) + rtup
pairs_group = pp.delimitedList(pp.Group(pair), com)

# tkinter windows
win = tk.Tk()
frame_main = tk.Frame(win)

# styles of widgets
header_style = {'background': "#2b2b2b", 'foreground': '#19ff98', 'font': 'Arial 30', "padx": 15, "pady": 15}
label_style = {'background': "#2b2b2b", 'foreground': '#42ff5f', 'font': 'Arial 15', "pady": 10}
button_style = {'background': '#23e865', 'foreground': 'black', 'font': 'Arial 13', "padx": 10, "pady": 5, "width": 10,
                "activebackground": "#19ff98"}
entry_style = {'background': '#63ffc6', 'foreground': 'black', 'font': 'Arial 13', "width": 80,
               "disabledbackground": '#63ffc6'}
frame_main.configure(bg="#2b2b2b")

# creating all widgets
lbl_header = tk.Label(frame_main, text="F1 calculator", **header_style)
lbl_browse = tk.Label(frame_main, text="Insert folder for output files:", **label_style)
entry_path = tk.Entry(frame_main, **entry_style)
btn_browse = tk.Button(frame_main, text="Browse\nfolder", **button_style, command=browse_btn)
lbl_sen = tk.Label(frame_main, text="Insert sentence for analysis:", **label_style)
entry_sen = tk.Entry(frame_main, **entry_style)
btn_create = tk.Button(frame_main, text="Create&\ncalculate", **button_style, command=create_btn)
btn_getgroups = tk.Button(frame_main, text="Evaluate for V", **button_style, command=get_group_members_btn)
btn_save = tk.Button(frame_main, text="Save to exel", **button_style, command=save_btn)
btn_info = tk.Button(frame_main, text="Help?", **button_style, command=info_btn)

btn_save["state"] = tk.DISABLED
btn_getgroups["state"] = tk.DISABLED
win.protocol("WM_DELETE_WINDOW", close_btn)
entry_sen.insert(0, "[S[N This][VP[Vi is an example]]]")

# aligning in grid
lbl_header.grid(column=0, row=0, pady=15)
btn_info.grid(column=1, row=0, padx=15, pady=10, sticky="e")
lbl_browse.grid(column=0, row=1, pady=5, padx=15, sticky="w")
entry_path.grid(column=0, row=2, pady=5, padx=15)
btn_browse.grid(column=1, row=2, pady=5, padx=15)
lbl_sen.grid(column=0, row=3, pady=5, padx=15, sticky="w")
entry_sen.grid(column=0, row=4, pady=5, padx=15)
btn_create.grid(column=1, row=4, pady=5, padx=15)
btn_getgroups.grid(column=0, row=5, padx=15, pady=15, sticky="w")
btn_save.grid(column=1, row=5, padx=15, pady=15)

# open window
frame_main.pack()
win.iconbitmap("f1_icon.ico")
win.resizable(0, 0)
win.title("F1 Calculator")
win.eval('tk::PlaceWindow . center')
win.mainloop()