import os
import socket
import threading
from threading import Lock

class Folder:

    def __init__(self, name):
        self.name = name
        self.children = {}
        self.open_count = 0

    def add_folder(self, folder_name):
        self.children[folder_name] = Folder(folder_name)

    def add_file(self, file_name):
        self.children[file_name] = File(file_name)

    def remove_child(self, child_name, file_manager):

        # if the folder has subfolders, it asks for confirmation
        if type(self.children[child_name]) is Folder and self.children[child_name].children:
            file_manager.client.c_print("{} is not empty, do you still want to delete it? [y/n]\n".format(self.name))
            file_manager.client.c_print('*input*')
            selection = file_manager.client.c_input()
            if selection == 'n':
                return
        # pop a child

        temp = self.children.pop(child_name)

        #free the frames if it is a file
        if type(temp) is File:
            if  temp.is_open:
                file_manager.client.c_print('Another client is working on the file, can not delete')
                self.children[child_name] = temp
            else:
                temp.free_pages(file_manager,temp.pages)
        elif type(temp) is Folder:
            if  temp.open_count > 0:
                file_manager.client.c_print('Another client is working in the directory, can not delete')
                self.children[child_name] = temp

    def list_children(self, file_manager):
        for child in self.children:
             file_manager.client.c_print(child+'\n')

    def print_tree(self, file_manager, indent=''):
        # print the name and indent
        file_manager.client.c_print(indent + self.name+'\n')
        if self.children:
            for child in self.children.values():
                # if it is folder, recursive call
                if type(child) is Folder:
                    child.print_tree(file_manager,indent + '  |')
                # if it is a file, print it's name
                else:
                    file_manager.client.c_print(indent + child.name+ '\n')

    def access_child(self, name):
        return self.children.get(name)

    def generate_tree(self):
        tree_string = "/" + self.name + "'" # '/' indicates that the following name is that of a folder, "'" indicates the end of the name
        if self.children:
            tree_string += "[" # '[' indicates that the following are children of the current folder
            for child in self.children.values():
                tree_string += child.generate_tree()
            tree_string += "]" #']' indicates that the list of children has ended
        return tree_string




class File:

    def __init__(self, name):
        self.name = name
        self.pages = []
        self.size = 0
        self.read_lock = Lock()
        self.write_lock = Lock()


    def write(self, text, file_manager):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base

        # if there is space in last page
        if self.pages:
            page_no = self.pages[-1]
            file.seek(base + page_no*page_size)
            text = file.read(page_size) + text
            self.free_pages(file_manager, [page_no])

        # request and write pages
        for i in range(int(len(text)/page_size)+1):
                page_no = file_manager.request_page()
                self.pages.append(page_no)
                file.seek(base + page_no*page_size)
                self.size += file.write(text[i*page_size:i*page_size+page_size])

    def write_at(self, text, file_manager, index):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base

        start_page = index // page_size
        start_offset = index % page_size

        #write in the start page
        file.seek(base + start_offset + self.pages[start_page]*page_size)
        file.write(text[0:page_size-start_offset])
        text = text[page_size-start_offset:]

        # write over the rest of pages
        for i in range(start_page+1,len(self.pages)):
            file.seek(base + self.pages[i] * page_size)
            file_manager.client.c_print(text+'\n')
            if len(text) > page_size:
                file.write(text[:page_size])
                text = text[page_size:]
            else:
                file.write(text)
                return
        # if there if more text, append it
        self.write(text, file_manager)


    def read(self, file_manager):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base
        # read every page
        for page in self.pages:
            file.seek(base + page * page_size)
            text = file.read(page_size)
            file_manager.client.c_print(text)
        file_manager.client.c_print('\n')


    def read_from(self, file_manager,fr,no_of_chars):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base

        start_page = fr//page_size
        start_offset = fr%page_size

        text = ''
        # read the start_page
        file.seek(base + self.pages[start_page] * page_size + start_offset)
        text += file.read(page_size - start_offset)

        # read the rest of pages
        for page in self.pages[start_page:]:
            file.seek(base + page * page_size)
            text += file.read(page_size)
            if len(text) > no_of_chars:
                break
        file_manager.client.c_print(text[:no_of_chars])



    def read_page(self, file_manager, page_no):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base
        #move to page index and read the page
        file.seek(base + page_no * page_size)
        text = file.read(page_size)
        return text

    def info(self, path, file_manager):
        file_manager.client.c_print()
        file_manager.client.c_print("File Name: {}\n".format(self.name))
        file_manager.client.c_print("size: {} bytes\n".format(self.size))
        file_manager.client.c_print("path: {}\n".format(path))
        file_manager.client.c_print("divided into {} pages.\n".format(len(self.pages)))
        file_manager.client.c_print("___________Page Mapping___________\n")
        file_manager.client.c_print("PAGE_NO\tDATA_SAVED\n")
        if self.pages:
            for page in self.pages:
                file_manager.client.c_print(str(page)+'\t'+self.read_page(file_manager,int(page))+'\n')

    def free_pages(self, file_manager, to_remove):
        temp=None
        # iterate over pages to remove
        for rp in to_remove:
            for pocket in file_manager.page_pool:
                #merging consecitive free pages
                if rp+1 == pocket[0]:
                    pocket[0] = rp
                    if temp is None:
                        temp = pocket
                    else:
                        file_manager.merge_page_pockets(temp,pocket)

                elif rp-1 == pocket[1]:
                    pocket[1] = rp
                    if temp is None:
                        temp = pocket
                    else:
                        file_manager.merge_page_pockets(temp,pocket)
            # removing the page from page list
            self.pages.remove(rp)

    def truncate(self, index, file_manager):
        # get pagesize, the file and base addr from the file_manager
        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base

        #read last page and split it
        last_page = index//page_size + 1
        offset = index % page_size
        self.free_pages(file_manager,self.pages[last_page:])
        file.seek(base + self.pages.pop()*page_size)
        temp = file.read(page_size)
        self.write(temp[:offset], file_manager)




    def generate_tree(self):
        tree_string = "." + self.name + "'" # '.' indicates that the following name is that of a file, "'" indicates the end of the name
        if self.pages:
            tree_string += "(" #'(' indicates that the following list is a list of page numbers
            for page in self.pages:
                tree_string += str(page) + ","#page numbers are separated by ','
            tree_string += ")"#')' indicates the end of the list
        return tree_string




class Tree_File(File):


    def write(self, text, file_manager):
        # freeing the existing pages
        self.free_pages(file_manager, self.pages)

        page_size = file_manager.page_size
        file = file_manager.partition
        base = file_manager.base

        no_of_pages = int(len(text)/page_size) + 1



        for i in range(no_of_pages):
            page_no = file_manager.request_page()
            self.pages.append(page_no)
        file.seek(0)
        # writing the metadata
        file.write(str(page_size)+','+str(base)+','+str(file_manager.partition_size)+',\n')
        # writing the pagepool
        p_pool = ''
        for i in file_manager.page_pool:
            for j in i:
                p_pool += str(j) + ','
        file.write(p_pool + '\n')

        #writing the tree pages
        for page in self.pages:
            file.write(str(page)+',')

        file.write('\n')

        for i in range(no_of_pages):
            page_no = self.pages[i]
            file.seek(base + page_no*page_size)
            self.size += file.write(text[i*page_size:i*page_size+page_size])



    def read(self, file_manager):

        file = file_manager.partition

        file.seek(0)
        # reading the meta data
        meta_data = file.readline().split(',')
        page_size = int(meta_data[0])
        base = int(meta_data[1])
        partition_size = int(meta_data[2])

        # reading the page pool
        sp = file.readline().split(',')[:-1]
        #self.fm.client.c_print(sp+'\n')
        sp = [int(i) for i in sp]
        page_pool = []
        for i in range(1,len(sp),2):
            page_pool.append([sp[i-1],sp[i]])
        #self.fm.client.c_print(page_pool+'\n')

        # reading the pages
        self.pages = file.readline().split(',')[:-1]
        self.pages = [int(i) for i in self.pages]

        table_string = ''
        for page in self.pages:
            file.seek(base + page * page_size)
            table_string += file.read(page_size)
        #self.fm.client.c_print(table_string+'\n')
        return table_string, int(partition_size), int(page_size), int(base), page_pool



class File_Manager:

    def __init__(self, partition_name, create ,client , file, root):

        # create is a boolean that tells that if we have to create a partition or open it
        if create:
            print("Creating New Partition: ", partition_name)
            self.partition_name = partition_name
            self.partition_size = 500000
            self.page_size = 16
            self.root = root
            self.root.open_count += 1
            self.working_directory = self.root
            self.path = [self.root]
            self.base = 10000
            self.active_file = None
            self.no_of_pages = int((self.partition_size - self.base)/ self.page_size)
            self.page_pool = [[0,self.no_of_pages]]
            self.partition = file #open(f"{partition_name}.tsk", 'w+')
            self.write_tree()
            self.partition.close()
            self.open_mode = 'none'

        else:
            self.client = client
            self.partition_name = partition_name
            self.partition = file #open(f"{partition_name}.tsk", 'r+')
            self.root = root
            self.read_tree()
            self.CLI()
            self.open_mode = 'none'


    def CLI(self):
        # Contains an infinte loop that takes, parse and handles user commands
        self.client.c_print("Connected to server! \n")
        self.client.c_print("You can enter commands now, enter 'help' for a list of commands \n")
        running = True
        file_commands ={'close','read','write', 'writeat', 'truncate'}

        while running:
            path = ""
            if self.active_file is None:
                path = ""#the one printed in the cli
                for folder in self.path:
                    path = path+folder.name+'/'
            else:
                path=self.active_file.name

            #printing the path
            self.client.c_print(path + '>')

            # TAKING THE COMMAND INPUT
            self.client.c_print('*input*')
            command = self.client.c_input()
            # spliting it into command and argument
            argv = command.split(' ',1)

            if argv[0] in file_commands:
                #file opeartions
                if self.active_file == None:
                    self.client.c_print("No file open, Please open a file first by using 'open file_name\n'")
                else:
                    #write
                    if argv[0] == 'write':
                        if self.open_mode == 'write':
                            if len(argv) == 2:
                                self.active_file.write(argv[1], self)
                            else:
                                self.client.c_print("invalid syntax! Usage: write [text]\n")
                        else:
                            self.client.c_print("File is not open in write mode\n")

                    #writeat
                    elif argv[0] == 'writeat':
                        if self.open_mode == 'write':
                            if len(argv) == 2:
                                args = argv[1].split(' ',1)
                                self.active_file.write_at(args[1], self, int(args[0]))
                            else:
                                self.client.c_print("invalid syntax! Usage: writeat [position] [text]\n")
                        else:
                            self.client.c_print("File is not open in write mode\n")

                    #truncate
                    if argv[0] == 'truncate':
                        if self.open_mode == 'write':
                            if len(argv) == 2:
                                self.active_file.truncate(int(argv[1]), self)
                            else:
                                self.client.c_print("invalid syntax! Usage: write [text]\n")
                        else:
                            self.client.c_print("File is not open in write mode\n")

                    #read
                    elif argv[0] == 'read':
                        if self.open_mode == 'read':
                            if len(argv) == 1:
                                self.active_file.read(self)
                            else:
                                args = argv[1].split(' ')
                                if len(args) == 2:
                                    self.active_file.read_from(self,int(args[0]),int(args[1]))
                        else:
                            self.client.c_print("File is not open in write mode\n")


                    #close
                    elif argv[0] == 'close':
                        if file.read_lock.locked():
                            self.active_file.read_lock.release()
                        if file.write_lock.locked():
                            self.active_file.write_lock.release()
                        self.active_file.is_open = False
                        self.active_file = None
                        self.open_mode = 'none'



            elif self.active_file is not None:
                self.client.c_print("Currently working in a file, Please close the file first by using 'close' command\n")
                continue

            # break out of loop if exit
            if argv[0] == 'exit':
                running = False
                self.write_tree()
                self.partition.close()

            # change directory CD
            elif argv[0] == 'cd':
                if len(argv) == 2:

                    # cd ..
                    if argv[1] == '..':
                        if len(self.path) > 1:
                            self.path.pop()
                        self.working_directory.open_count += 1
                        self.working_directory = self.path[-1]

                    # cd ~
                    elif argv[1] == '~':
                        self.working_directory = self.root
                        for i in self.path:
                            i.open_count -= 1
                        self.root.open_count += 1
                        self.path = [self.root]
                    # cd folder
                    elif argv[1] in self.working_directory.children:
                        self.working_directory = self.working_directory.access_child(argv[1])
                        self.path.append(self.working_directory)
                        self.working_directory.open_count += 1
                else:
                    self.client.c_print("invalid syntax! Usage: cd destination \n enter 'help' for a list of commands\n")

            # list directories ls
            elif argv[0] == 'ls':
                for child in list(self.working_directory.children.values()):
                    self.client.c_print(child.name+'\n')

            #display the directory tree of working directory
            elif argv[0] == 'tree':
                self.working_directory.print_tree(self)
            # make a new folder in working directory
            elif argv[0] == 'mkdir':
                if len(argv) == 2:
                    self.working_directory.add_folder(argv[1])
                else:
                    self.client.c_print("invalid syntax! Usage: mkdir folder_name \n enter 'help' for a list of commands\n")


            #open for reading
            elif argv[0] == 'openr':
                if len(argv) == 2:
                    if argv[1] in self.working_directory.children.keys():
                        file = self.working_directory.children[argv[1]]
                        if not file.write_lock.locked():
                            file.read_lock.acquire(False)
                            self.active_file = file
                            self.open_mode = 'read'
                            self.client.c_print(f"Opened {self.active_file.name} in READ Mode, \n")
                        else:
                            self.client.c_print(f"Can not open {argv[1]}. Another user is working on the file \n")
                    else:
                        self.client.c_print("File {} does not exists! use 'create file_name' to make a new file\n".format(argv[1]))
                else:
                    self.client.c_print("invalid syntax! Usage: open file_name \n enter 'help' for a list of commands\n")


            #Open for writing
            elif argv[0] == 'openw':
                if len(argv) == 2:
                    if argv[1] in self.working_directory.children.keys():
                        file = self.working_directory.children[argv[1]]
                        if file.write_lock.acquire(False) and file.read_lock.acquire(False):
                            self.active_file = file
                            self.open_mode = 'write'
                            self.client.c_print(f"Opened {self.active_file.name} in write Mode, \n")
                        else:
                            self.client.c_print(f"Can not open {argv[1]}. Another user is working on the file \n")
                    else:
                            self.client.c_print("File {} does not exists! use 'create file_name' to make a new file\n".format(argv[1]))
                else:
                    self.client.c_print("invalid syntax! Usage: open file_name \n enter 'help' for a list of commands\n")





            # create
            elif argv[0] == 'create':
                if len(argv) == 2:
                    if argv[1] not in self.working_directory.children.keys():
                        self.working_directory.add_file(argv[1])
                        self.client.c_print("created {}, \n use 'openr {}' to open in read mode OR 'openw {}' to open in write mode\n".format(argv[1],argv[1],argv[1]))
                    else:
                        self.client.c_print("File {} already exists!Use 'open file_name' to perform file operations\n".format(argv[1]))
                else:
                     self.client.c_print("invalid syntax! Usage: create file_name \n enter 'help' for a list of commands\n")

            # delete
            elif argv[0] == 'delete':
                if len(argv) == 2:
                    if argv[1] in self.working_directory.children.keys():
                        self.working_directory.remove_child(argv[1],self)
                    else:
                        self.client.c_print("{} does not exist\n".format(argv[1]))
                else:
                    self.client.c_print("invalid syntax! Usage: delete file_name \n enter 'help' for a list of commands\n")

            #Info
            elif argv[0] == 'info':
                if len(argv) == 2:
                    if argv[1] in self.working_directory.children.keys():
                        self.working_directory.children[argv[1]].info(path, self)
                    else:
                        self.client.c_print("{} does not exist\n".format(argv[1]))
                else:
                    self.client.c_print("invalid syntax! Usage: delete file_name \n enter 'help' for a list of commands\n")

            # move
            elif argv[0] == 'move':

                args = argv[1].split(" ")
                src_path = args[0].split('/')
                source = None
                if src_path[0] == "~":
                    source = self.root
                    for directory in src_path[1:-1]:
                        source = source.access_child(directory)
                else:
                    source = self.working_directory
                    for directory in src_path[:-1]:
                        source = source.access_child(directory)


                dest_path = args[1].split('/')
                destination = None
                if dest_path[0] == "~":
                    destination = self.root
                    for directory in dest_path[1:]:
                        destination = destination.access_child(directory)

                else:
                    destination = self.working_directory
                    for directory in dest_path:
                        destination = destination.access_child(directory)
                if source is File and source.is_open:
                    self.client.c_print('Can not move, another client is working on the file')
                elif source is Folder and source.open_count > 0:
                    self.client.c_print('Can not move, another client is working in the folder')
                else:
                    self.move(source, destination, src_path[-1])

            #print the help
            elif argv[0] == 'help':
                self.client.c_print('-------------TASK FILE MANAGER COMMANDS-------------\n')
                self.client.c_print('\n')
                self.client.c_print("exit \t\t\tsave the partition and go back to partition select\n")
                self.client.c_print("cd ~\t\t\tchange working directory to root\n")
                self.client.c_print("cd ..\t\t\tchange working directory to the parent of current working directory\n")
                self.client.c_print("cd folder_name\t\tchange working directory to given folder\n")
                self.client.c_print("mkdir folder_name\tcreate a new folder\n")
                self.client.c_print("ls \t\t\tlist the files/folders in working directory\n")
                self.client.c_print("tree \t\t\tdisplay the folder structure of the working directory\n")
                self.client.c_print("delete file/folder_name\tdelete a file/folder\n")
                self.client.c_print("info file_name\t\tshow the memory map of a file\n")
                self.client.c_print("create file_name\tmake a new file\n")
                self.client.c_print("move file_name path\tmove a file/folder to given path\n")
                self.client.c_print("openr file_name ~\topen a file in read mode\n")
                self.client.c_print("openw file_name ~\topen a file in write mode\n")
                self.client.c_print('\n\tfile operations (only work after opening a file)\n')
                self.client.c_print("read \t\t\t read the content of a file\n")
                self.client.c_print("read from size\t\t read string of given size from given index\n")
                self.client.c_print("write text\t\t append the text to the file\n")
                self.client.c_print("writeat index text\t write the text to the file at given index\n")
                self.client.c_print("truncate size\t\t truncate the file to given size\n")
                self.client.c_print("close\t\t\t close the open file\n")



    def request_page(self):
        # get the first free page
        temp = self.page_pool[-1][0]
        #update the page pool
        self.page_pool[-1][0] += 1
        if self.page_pool[-1][0] > self.page_pool[-1][1]:
            self.page_pool.pop()
        return temp

    def merge_page_pockets(self, pocket1, pocket2):
        # check if consecutive, if so merge second into first, remove the second entry
        if pocket1[1]==pocket2[0]:
            pocket1[1] = pocket2[1]
            self.page_pool.remove(pocket2)
        elif pocket2[1] == pocket1[0]:
            pocket2[1] = pocket1[1]
            self.page_pool.remove(pocket1)


    def write_tree(self):
        tree_string = ""
        tree_string += "/" + self.root.name + "'"#write name of root folder

        #add children of root to file
        for child in self.root.children.values():
            tree_string += child.generate_tree()


        tree_file = Tree_File('tree')
        tree_file.write(tree_string,self)


    def read_tree(self):
        tree_file = Tree_File('tree')
        meta_data = tree_file.read(self)
        table_string, self.partition_size, self.page_size, self.base, self.page_pool = meta_data
        self.parse_tree(table_string)


    def parse_tree(self, tree_string):

        #read the file tree and initialize it
        text = tree_string.split("'", 1)
        #get root folder
        #self.root = Folder(text[0][1:],self)
        self.working_directory = self.root
        self.path = [self.root]
        text = text[1]

        #stores name of last folder and file created. Temporary variables for while loop
        last_folder_created = None
        last_file_created = None

        while text:
            indicator = text[0] #character to indicate what is stored next in the file
            #if a folder is located
            if indicator == '/':
                text = text[1:].split("'", 1)
                last_folder_created = text[0]
                self.working_directory.add_folder(last_folder_created)
                text = text[1]

            #if list of children is starting
            elif indicator == '[':
                self.path.append(self.working_directory.access_child(last_folder_created))
                self.working_directory = self.path[-1]
                text = text[1:]

            #if list of children is ending:
            elif indicator == ']':
                self.path.pop()
                self.working_directory = self.path[-1]
                text = text[1:]

            #if a file is located
            elif indicator == '.':
                text = text[1:].split("'", 1)
                last_file_created = text[0]
                self.working_directory.add_file(last_file_created)
                text = text[1]

            #if list of page numbers is located
            elif indicator == '(':
                text = text[1:].split(')', 1)
                self.working_directory.access_child(last_file_created).pages = [int(i) for i in text[0].split(',')[:-1]]
                self.working_directory.access_child(last_file_created).size = self.page_size * len(self.working_directory.access_child(last_file_created).pages)
                text = text[1]

        #initialize the rest of the variables
        self.active_file = None
        self.no_of_pages = (self.partition_size - self.base)/ self.page_size

    def move(self, source, destination, item_name):
        temp_item = source.children[item_name]
        source.children.pop(item_name)
        destination.children[item_name] = temp_item


    def makefolder(self, folder_name):
        self.working_directory.add_folder(folder_name)

    def makefile(self):
        self.working_directory.add_child()



class Server:
    def __init__(self):
        self.root = Folder('~')
        if not os.path.exists('Partition.tsk'):
            file = open("Partition.tsk", 'w+')
            print('Partition not found, creating a new one.')
            File_Manager("Partition.tsk", True,None ,file, self.root)
            file.close()

        self.file = open("Partition.tsk", 'r+')

        print('Server running')
        print('Waiting for clients to connect')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((socket.gethostname(),2235))
        self.socket.listen(5)
        total_clients = 0
        while True:
            clientsocket, address = self.socket.accept()
            total_clients += 1;
            print(f'User connected. Total users:{total_clients}')
            x = threading.Thread(target=thread_func, args=(clientsocket,self.root,self.file))
            x.start()

def thread_func(client_socket,root,file):
    Client(client_socket,root,file)

class Client:

    def __init__(self,socket,root,file):
        self.socket = socket
        self.username = self.socket.recv(1024).decode('utf-8')
        print(f"User provided Username: {self.username}")
        File_Manager('Partition', False,self,file,root)

    def c_print(self,msg):
        self.socket.sendall(msg.encode())

    def c_input(self):

        msg = self.socket.recv(1024).decode('utf-8')
        print(f'{self.username} sent command: {msg}')
        return msg


if __name__ == "__main__":
    Server()
