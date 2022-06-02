import socket


s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((socket.gethostname(), 2235))

def print_logo():
    print("""      _____ _   ___ _  __  ___ _ _       __  __                             
     |_   _/_\\ / __| |/ / | __(_) |___  |  \\/  |__ _ _ _  __ _ __ _ ___ _ _ 
       | |/ _ \\\\__ \\ ' <  | _|| | / -_) | |\\/| / _` | ' \\/ _` / _` / -_) '_|
       |_/_/ \\_\\___/_|\\_\\ |_| |_|_\\___| |_|  |_\\__,_|_||_\\__,_\\__, \\___|_|  
                                                              |___/      """)

print_logo()
print()
print("Enter Your username:")
username = input()
s.sendall(username.encode())


while True:
  terminal_message = s.recv(1024).decode('utf-8')
  if terminal_message:
    if '*input*' in terminal_message:
      terminal_message = terminal_message[0:terminal_message.index('*input*')]
     
      print(terminal_message, end='')
      
      terminal_message = ''
  
      command = input()
      s.sendall(command.encode())
      if command == 'exit':
        s.close()
        break
      
    else:
      print(terminal_message, end='')
      terminal_message = ''
    
  
  