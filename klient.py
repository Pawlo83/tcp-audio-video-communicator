import cv2
import threading
import numpy as np
import socket
import time
import pyaudio
from queue import Queue

# Konfiguracja hosta, portu i kamery
HOST = "127.0.0.1"
PORT = 12347
CAMERA = 3
config = open("klient.conf", "r")
HOST=config.readline().strip()
PORT=int(config.readline().strip())
CAMERA=int(config.readline().strip())

# Inicjalizacja pustych klatek obrazu
frame = np.full((512, 910, 3), (128, 128, 128), dtype=np.uint8)
cap_frame = np.full((512, 910, 3), (128, 128, 128), dtype=np.uint8)

# Eventy i kolejka do obsługi wątków
stop_event = threading.Event()
exit_event = threading.Event()
command_writing_mutex = threading.Lock()

# Parametry okna i przycisków
button_width = 200
button_height = 50
button_spacing = 20
window_width = 500
window_height = (button_height + button_spacing) * 10 + button_spacing

# Kolory
bg_color = (50, 50, 50)
button_color = (70, 130, 180)
highlight_color = (100, 170, 220)
text_color = (255, 255, 255)

# Tworzenie canvasu
canvas = np.zeros((window_height, window_width, 3), dtype=np.uint8)
canvas[:] = bg_color

# Tworzenie zmiennych do przycisków
buttons = []
highlighted_button = None
buttons_call = []
highlighted_button_call = None
buttons_popup = []
highlighted_button_popup = None
selected_popup = None

# Funkcja odbierania danych audio i wideo
def receive(sock, output_stream, stop_event):
    global frame

    while not stop_event.is_set():
        data = sock.recv(2000000)
        #print(data)
        if not data:
            continue
        if b'stop\n' in data or stop_event.is_set():
            break
        if data[:5] == b'audio':
            data = data[5:2048]
            output_stream.write(data, exception_on_underflow=False)
        else:
            while True:
                data += sock.recv(2000000)
                if data[-1:]==b"\n":
                   break
            data=data[:-1]
            np_frame = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
    sock.send("stop\n".encode('utf-8'))
    stop_event.set()
    print("end rec")

# Funkcja wysyłania wideo
def send_video(sock, stop_event):
    global cap_frame

    # Obsługa kameru i wybór jakości
    cap = cv2.VideoCapture(CAMERA)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 360)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 202)
    #cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    #cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    while not stop_event.is_set():
        # Wstawienie najnowszej klatki lub pustego zamiennika do globalnej zmiennej
        if cap.isOpened():
            ret, cap_frame = cap.read()
        else:
            cap_frame = np.full((512, 910, 3), (128, 128, 128), dtype=np.uint8)
        success, byteImage = cv2.imencode('.jpg', cap_frame)
        if success:
            byteImage.tobytes()
            bytes_sent = 0
            while (bytes_sent < len(byteImage)):
                new_message = byteImage[bytes_sent:]
                if stop_event.is_set():
                    break
                bytes_sent += sock.send(new_message)
            sock.send("\n".encode('utf-8'))
        # Odstęp między wysyłanymi klatkami (odwrotność fps)
        time.sleep(1/24)
    cap.release()
    print('end send video')

# Funkcja wysyłania audio
def send_audio(sock,input_stream,stop_event):
    while not stop_event.is_set():
        data = input_stream.read(1024, exception_on_overflow=False)
        data=b'audio'+data[:2048]
        bytes_sent = 0
        while (bytes_sent < len(data)):
            new_message = data[bytes_sent:]
            bytes_sent += sock.send(new_message)
        sock.send("\n".encode('utf-8'))
    print('end send audio')

# Rozpoczęcie wideorozmowy
def start_videocall(sock, stop_event):
    stop_event.clear()

    # Utworzenie wątków aby zapewnić jak największą płynność przesyłu obrazu oraz dźwięku
    audio = pyaudio.PyAudio()
    output_stream = audio.open(format=pyaudio.paInt16, channels=1, rate=20000, output=True, frames_per_buffer=1024)
    threading.Thread(target=receive, args=(sock, output_stream, stop_event,)).start()
    threading.Thread(target=send_video, args=(sock, stop_event,)).start()

    input_stream = audio.open(format=pyaudio.paInt16, channels=1, rate=20000, input=True, frames_per_buffer=1024)
    threading.Thread(target=send_audio, args=(sock, input_stream, stop_event,)).start()

# Funkcje do obsługi myszy poszczególnych okienek
def mouse_callback(event, x, y, flags, param):
    global highlighted_button
    global buttons

    if event == cv2.EVENT_MOUSEMOVE or event == cv2.EVENT_LBUTTONDOWN:
        for idx, button in enumerate(buttons):
            bx, by, bw, bh, label = button
            # Sprawdzenie czy mysz znajduje się na przycisku
            if bx <= x <= bx + bw and by <= y <= by + bh:
                highlighted_button = idx
                if event == cv2.EVENT_LBUTTONDOWN:
                    print(f"Kliknięto {idx}")
                    if idx in range(0, 7) and label != "?":
                        print(label)
                        with command_writing_mutex:
                            param.send(f"connect {label}".encode('utf-8'))
                    if idx == 8:
                        with command_writing_mutex:
                            param.send("refresh".encode('utf-8'))
                    elif idx == 9:
                        exit_event.set()
                break
            else:
                highlighted_button = None

def mouse_callback_call(event, x, y, flags, param):
    global stop_event
    global highlighted_button_call

    if event == cv2.EVENT_MOUSEMOVE or event == cv2.EVENT_LBUTTONDOWN:
        for idx, button in enumerate(buttons_call):
            bx, by, bw, bh, label = button
            # Sprawdzenie czy mysz znajduje się na przycisku
            if bx <= x <= bx + bw and by <= y <= by + bh:
                highlighted_button_call = idx
                if event == cv2.EVENT_LBUTTONDOWN:
                    if idx == 0:
                        stop_event.set()
                        cv2.destroyAllWindows()
                        time.sleep(1)
                        print("reset")
                        break
                break
            else:
                highlighted_button_call = None

def mouse_callback_popup(event, x, y, flags, param):
    global highlighted_button_popup
    global buttons_popup
    global selected_popup

    if event == cv2.EVENT_MOUSEMOVE or event == cv2.EVENT_LBUTTONDOWN:
        for idx, button in enumerate(buttons_popup):
            bx, by, bw, bh, label = button
            # Sprawdzenie czy mysz znajduje się na przycisku
            if bx <= x <= bx + bw and by <= y <= by + bh:
                highlighted_button_popup = idx
                if event == cv2.EVENT_LBUTTONDOWN:
                    # Wysłanie odpowiedzi na połączenie
                    if idx == 0:
                        with command_writing_mutex:
                            param.send("ask yes".encode('utf-8'))
                        selected_popup="yes"
                    if idx == 1:
                        with command_writing_mutex:
                            param.send("ask no".encode('utf-8'))
                        selected_popup = "no"
                break
            else:
                highlighted_button_popup = None

# Funkcja do rysowania przycisków w zależności od połączonych do serwera klientów
def draw_menu_buttons(labels_string):
    global highlighted_button, buttons, canvas
    labels = labels_string.split('\n')
    while len(labels)<8:
        labels.append("?")
    labels.append("Refresh")
    labels.append("Exit")
    buttons = []

    for idx, label in enumerate(labels):
        buttons.append(((window_width-button_width)//2, button_spacing+idx*(button_height+button_spacing), button_width, button_height, label))
    for idx, button in enumerate(buttons):
        bx, by, bw, bh, label = button
        color = highlight_color if highlighted_button == idx else button_color
        cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), color, -1)
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        label_x = bx + (bw - label_size[0]) // 2
        label_y = by + (bh + label_size[1]) // 2
        cv2.putText(canvas, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)

# Funkcje do rysowania poszczególnych okienek
def show_menu(sock,stop_event,exit_event,my_queue):
    global frame, cap_frame

    cv2.namedWindow("Menu")
    cv2.setMouseCallback("Menu", mouse_callback, sock)

    with command_writing_mutex:
        sock.send("refresh".encode('utf-8'))
    labels_string = ""

    while stop_event.is_set() and not exit_event.is_set():
        if not my_queue.empty():
            command = my_queue.get()
            if command[:19] == 'Connected clients:\n':
                labels_string = command[19:-1]
            elif command == "exit":
                break
        canvas[:] = bg_color
        draw_menu_buttons(labels_string)
        cv2.imshow("Menu", canvas)
        cv2.waitKey(25)

def show_call(stop_event,exit_event):
    global frame, cap_frame, buttons, buttons_call

    time.sleep(1)
    cv2.namedWindow("Call")
    cv2.setMouseCallback("Call", mouse_callback_call)

    while not stop_event.is_set() and not exit_event.is_set():
        if frame is not None and cap_frame is not None:
            # Łączenie klatki z twojej kamery i osoby z którą rozmawiasz
            temp_frame = frame.copy()
            temp_cap = cap_frame.copy()
            gap_width = 20
            height = 512
            frame_resized = cv2.resize(temp_frame, (int(temp_frame.shape[1] * height / temp_frame.shape[0]), height))
            cap_resized = cv2.resize(temp_cap, (int(temp_cap.shape[1] * height / temp_cap.shape[0]), height))
            gap_h = np.zeros((height, gap_width, 3), dtype=np.uint8)
            gap_h[:]=bg_color
            combined_image = np.hstack((gap_h,cap_resized, gap_h, frame_resized,gap_h))
            gap_v = np.zeros((gap_width, combined_image.shape[1], 3), dtype=np.uint8)
            gap_v[:] = bg_color
            combined_image = np.vstack((gap_v, combined_image, gap_v,gap_v,gap_v,gap_v,gap_v,gap_v))
            # Dodanie przycisku rozłączania z ewentualnym miejscem na inne funkcje
            if buttons_call==[]:
                buttons_call.append((((combined_image.shape[1]-button_width)//2, combined_image.shape[0]-4*gap_width, button_width, gap_width*2, "End Call")))
            for idx, button in enumerate(buttons_call):
                bx, by, bw, bh, label = button
                color = highlight_color if highlighted_button_call == idx else button_color
                cv2.rectangle(combined_image, (bx, by), (bx + bw, by + bh), color, -1)
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                label_x = bx + (bw - label_size[0]) // 2
                label_y = by + (bh + label_size[1]) // 2
                cv2.putText(combined_image, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
            cv2.imshow("Call", combined_image)
            cv2.waitKey(25)

def show_popup(message, sock, timeout=3):
    global highlighted_button_popup, buttons_popup, selected_popup
    buttons_popup = []
    canvas = np.zeros((200, 500, 3), dtype=np.uint8)
    canvas[:] = bg_color

    buttons_popup.append((40, 120, button_width, button_height, "Tak"))
    buttons_popup.append((400 - 140, 120, button_width, button_height, "Nie"))

    cv2.namedWindow("Popup")
    cv2.setMouseCallback("Popup", mouse_callback_popup, sock)

    start_time = time.time()
    while (time.time() - start_time < timeout) and selected_popup==None:
        canvas_height, canvas_width = canvas.shape[:2]
        popup_x = (canvas_width - 400) // 2
        popup_y = (canvas_height - 200) // 2
        text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        text_x = popup_x + (400 - text_size[0]) // 2
        text_y = popup_y + text_size[1] + 20
        cv2.putText(canvas, message, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)
        for idx, button in enumerate(buttons_popup):
            bx, by, bw, bh, label = button
            color = highlight_color if highlighted_button_popup == idx else button_color
            cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), color, -1)
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            label_x = bx + (bw - label_size[0]) // 2
            label_y = by + (bh + label_size[1]) // 2
            cv2.putText(canvas, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
        cv2.imshow("Popup", canvas)
        cv2.waitKey(25)
    # Odmowa w razie timeoutu
    if selected_popup == None:
        with command_writing_mutex:
            sock.send("ask no".encode('utf-8'))
    selected_popup = None
    cv2.destroyWindow("Popup")

# Funkcja do interfejsu
def gui(sock,stop_event,exit_event,my_queue):
    show_menu(sock,stop_event,exit_event,my_queue)
    cv2.destroyAllWindows()

    show_call(stop_event,exit_event)
    cv2.destroyAllWindows()

# Funkcja do odbierania komunikatów od serwera poza rozmową
def receive_text(sock,stop_event,exit_event,my_queue):
    while stop_event.is_set() and not exit_event.is_set():
        try:
            data = sock.recv(2000)
            if data:
                data = data.decode('utf-8')
                print(f"{data}")
                if data[:6] == 'retry\n':
                    with command_writing_mutex:
                        if 'ask no' in data:
                            sock.send('ask no'.encode('utf-8'))
                        elif 'ask yes' in data:
                            sock.send('ask yes'.encode('utf-8'))
                        else:
                            sock.send(data[6:].encode('utf-8'))
                if data[:4] == 'ask\n':
                    show_popup(data[4:],sock)
                if data == 'start':
                    start_videocall(sock,stop_event)
                if data[:19] == 'Connected clients:\n':
                    my_queue.put(data)
        except socket.timeout:
            print("Didn't receive data! [Timeout 5s]")
            continue
        except UnicodeDecodeError:
            print('unicodeError')
            if data[:5] == b'audio':
                print('unicodeError-startcall')
                start_videocall(sock, stop_event)

# Funkcja główna
def main():
    while not exit_event.is_set():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((HOST, PORT))
            print(f"Połączono z serwerem {HOST}:{PORT}")
        except ConnectionRefusedError:
            print(f"Błąd: Połączenie z serwerem {HOST}:{PORT} zostało odrzucone. Upewnij się, że serwer działa.")
        except socket.timeout:
            print(f"Błąd: Połączenie z serwerem {HOST}:{PORT} przekroczyło limit czasu.")
        except socket.error as e:
            print(f"Błąd: Wystąpił problem z połączeniem: {e}")
        sock.settimeout(5.0)

        stop_event.set()
        my_queue = Queue()

        gui_thread = threading.Thread(target=gui, args=(sock,stop_event,exit_event,my_queue), daemon=True)
        receive_thread = threading.Thread(target=receive_text, args=(sock,stop_event,exit_event,my_queue), daemon=True)
        gui_thread.start()
        receive_thread.start()

        receive_thread.join()
        gui_thread.join()
        time.sleep(3)
        print("end main")

    print("Closing connection...")
    sock.close()

if __name__ == "__main__":
    main()
