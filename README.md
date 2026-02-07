# TCP Audio-Video Communicator

![Project Status](https://img.shields.io/badge/status-completed-blue)
![Language](https://img.shields.io/badge/language-C%20%7C%20Python-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

Projekt implementuje serwer obsługujący komunikację między klientami poprzez własny protokół komunikacyjny oparty na gniazdach TCP, wykorzystując wydajność języka C po stronie serwera oraz elastyczność Pythona do obsługi multimediów i GUI po stronie klienta. Serwer umożliwia klientom łączenie się, wyświetlanie listy dostępnych użytkowników oraz wywołanie połączeń do bezpośredniej komunikacji.

![screenshot](screenshot.png)

## Kluczowe funkcjonalności

* **Transmisja w czasie rzeczywistym:** Przesyłanie obrazu i dźwięku między klientami.
* **Architektura:**
    * **Serwer (C):** Wydajna obsługa wielu połączeń przy użyciu wątków POSIX (pthreads) i mutexów.
    * **Klient (Python):** Przetwarzanie obrazu (OpenCV), obsługa dźwięku (PyAudio) i interfejs graficzny.
* **Protokół:** Własny protokół tekstowy do negocjacji połączeń (handshake).
* **Wielowątkowość:** Równoległa obsługa GUI, przechwytywania wideo, audio oraz komunikacji sieciowej.
* **System zaproszeń:** Mechanizm "Zadzwoń" -> "Odbierz/Odrzuć" z dynamicznym odświeżaniem listy dostępnych użytkowników.

## Technologie

### Serwer
* **Język:** C
* **Biblioteki:** `sys/socket`, `pthread`, `netinet`

### Klient
* **Język:** Python 3
* **Biblioteki:**
    * `OpenCV` (przetwarzanie i wyświetlanie wideo)
    * `PyAudio` (strumieniowanie dźwięku)
    * `NumPy` (operacje na macierzach klatek wideo)
    * `Threading` & `Socket`

### Opis protokołu komunikacyjnego:
Protokół komunikacyjny opiera się na przesyłaniu prostych wiadomości tekstowych między klientami a serwerem. Komendy obsługiwane przez serwer to:
- `refresh` – wysyła listę dostępnych klientów,
- `connect <IP>` – próba połączenia z podanym klientem,
- `ask <IP>` – wiadomość wysyłana do użytkownika z zapytaniem o zgodę na połączenie,
- `ask yes` – akceptacja połączenia przez drugiego klienta,
- `ask no` – odmowa połączenia, 
- `stop` – zakończenie rozmowy wideo,
- `start` – rozpoczęcie rozmowy wideo.

Ewentualne części komunikatów i ich zakończenie są oddzielone znakiem nowej linii. Serwer zarządza połączeniami i kontroluje dostępność klientów, zapewniając mechanizm blokowania użytkowników podczas aktywnej komunikacji.

## Sposób kompilacji i uruchomienia:
1. **Kompilacja i uruchomienie serwera:**
   ```sh
   gcc -Wall -lpthread serwer.c -o serwer
   ./serwer
   ```
   Serwer domyślnie nasłuchuje na porcie `12345`.
2. **Konfiguracja klienta (edycja pliku klient.conf, w którym zawiera się IP serwera, port oraz indeks kamery) np.:**
   ```
   192.168.0.1
   12345
   0
   ```
3. **Pobranie bibliotek i uruchomienie klienta:**
   ```
   pip install opencv-python pyaudio numpy
   python klient.py
   ```
