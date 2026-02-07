#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/types.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <pthread.h>

// Struktura przechowująca informacje o kliencie
typedef struct {
    int socket_fd;
    struct sockaddr_in address;
    int block;
} Client;

// Struktura argumentów dla wątku obsługi połączenia
typedef struct {
    int cfd1;
    int cfd2;
    pthread_mutex_t *mutex;
} Thread_args;

// Mutex do synchronizacji listy klientów
pthread_mutex_t clients_mutex = PTHREAD_MUTEX_INITIALIZER;

#define MAX_CLIENTS 8
#define BUF_SIZE 2000000

// Tablica przechowująca klientów
Client clients[MAX_CLIENTS];
int client_count = 0;

// Funkcja obsługująca przesyłanie danych między od jednego klienta do drugiego
void* handle_connection(void* arg) {
	Thread_args *args = (Thread_args *)arg;
    int cfd1 = args->cfd1;
    int cfd2 = args->cfd2;
    pthread_mutex_t *mutex = args->mutex;
	char buf1[2000000];
	int rc1, bufsize;
	int bug;

	while (1) {
	    bufsize = sizeof(buf1);
	    bug = 0;

		rc1=read(cfd1, buf1, bufsize);
	    if (bug!=0 || rc1<=0) {
	        printf("ERROR: Pthread\n");
	        break;
	    }
	    write(cfd2, buf1, rc1);
	    
	    // Sprawdzenie czy wiadomość to "stop"
		if(strstr(buf1, "stop\n") != NULL){
	    	pthread_mutex_unlock(mutex);
	    	break;
	    }
	    // Sprawdzenie czy drugi z wątków tej rozmowy nie zakończył już pracy
	    if(pthread_mutex_trylock(mutex) == 0){
	    	write(cfd1, "stop\n", 5);
	    	pthread_mutex_unlock(mutex);
	    }
	}
	return NULL;
}

// Funkcja obsługi klienta
void handle_client(int cfd) {
    char buf[BUF_SIZE];
    int rc, id, if_break=0;

    // Znalezienie id klienta w tablicy
    for (int i = 0; i < client_count; i++) {
        if (clients[i].socket_fd == cfd) {
			id=i;
			break;
       	}
    }

    while ((rc = read(cfd, buf, BUF_SIZE - 1)) > 0) {
        buf[rc] = '\0';
        if(clients[id].block!=1){
        	// Obsługa żądania listy podłączonych klientów
	        if (strncmp(buf, "refresh", 7) == 0) {
	            char client_list[BUF_SIZE] = "Connected clients:\n";
	        
	            for (int i = 0; i < client_count; i++) {
	                char client_info[128];
	                sprintf(client_info, "%s\n", inet_ntoa(clients[i].address.sin_addr));
	                strcat(client_list, client_info);
	            }
	            write(cfd, client_list, strlen(client_list));
	        } 
	        // Obsługa żądania połączenia między klientami
	        else if (strncmp(buf, "connect", 7) == 0) {
	        	char target_ip[INET_ADDRSTRLEN];
	        	struct sockaddr_in caddr;
	        	socklen_t sl=sizeof(caddr);
	            sscanf(buf + 8, "%s", target_ip);
				getpeername(cfd, (struct sockaddr *)&caddr, &sl);
	            int target_found = 0;
	            
	            for (int i = 0; i < client_count; i++) {
	                if (strcmp(target_ip, inet_ntoa(clients[i].address.sin_addr)) == 0 && strcmp(target_ip, inet_ntoa((struct in_addr)caddr.sin_addr)) != 0){
	                	char ask[BUF_SIZE] = "ask\n";
	                	char asking_ip[128];
	                	sprintf(asking_ip, "%s\n", inet_ntoa((struct in_addr)caddr.sin_addr));
	   	                strcat(ask, asking_ip);
	                    write(clients[i].socket_fd, ask, strlen(ask));
	                    rc=read(clients[i].socket_fd, ask, strlen(ask));
	                    if(strncmp(ask, "ask yes\n", rc) == 0){
	                    	pthread_t thread1, thread2;	
	                    	pthread_mutex_t connection_mutex = PTHREAD_MUTEX_INITIALIZER;
	                    	pthread_mutex_lock(&connection_mutex);
	                    	Thread_args *args1 = malloc(sizeof(Thread_args));
                    	    args1->cfd1 = clients[i].socket_fd;
                    	    args1->cfd2 = cfd;
                    	    args1->mutex = &connection_mutex;
                    	    Thread_args *args2 = malloc(sizeof(Thread_args));
                       	    args2->cfd1 = cfd;
                       	    args2->cfd2 = clients[i].socket_fd;
                       	    args2->mutex = &connection_mutex;
	              	        pthread_create(&thread1, NULL, handle_connection, args1);
	              	        pthread_create(&thread2, NULL, handle_connection, args2);
	              	        sleep(1);
   	              			write(cfd, "start", 5);
	              	   		write(clients[i].socket_fd, "start", 5);
	              			clients[id].block=1;
	              			clients[i].block=1;
	        				pthread_join(thread1, NULL);
							pthread_join(thread2, NULL);
							sleep(1);
							close(clients[i].socket_fd);
							close(cfd);
	              			clients[id].block=0;
	              			clients[i].block=0;
	                    }
	                    else{
	                    	write(cfd, "ask rejected", 8);
	                    }
	                    target_found = 1;
	                    break;
	                }
	            }
	            if (!target_found) {
	                write(cfd, "ERROR\n",6);
	            }
        	}
        	// Sygnał z wątku który nie tworzy połączenia aby ponownie przesłać odpowiedź od pytanego klienta
        	else if(strncmp(buf, "ask", 3) == 0){
        		char retry[BUF_SIZE]="retry\n";
        		strcat(retry, buf);
        		write(cfd,retry,strlen(retry));
        	} 
        	else {
            	write(cfd, "Unknown command\n",16);
        	}
        }
		else{
			if_break=1;
          	break;
        }
    }
    // Oczekiwanie wątku klienta pytanego o połączenie na zakończenie połączenia
    while(if_break==1 && clients[id].block==1){
    	sleep(1);
    }
    // Usunięcie rozłączonych klientów z listy
    pthread_mutex_lock(&clients_mutex);
    for (int i = 0; i < client_count; i++) {
        if (clients[i].socket_fd == cfd) {
            for (int j = i; j < client_count - 1; j++) {
                clients[j] = clients[j + 1];
            }
            client_count--;
            break;
        }
    }
    pthread_mutex_unlock(&clients_mutex);
}
// Funkcja główna uruchamiająca serwer
int main(){
	int n_cfd;
	socklen_t sl;
	struct sockaddr_in saddr, caddr;

	memset(&saddr, 0, sizeof(saddr));
	saddr.sin_family = AF_INET;
	saddr.sin_addr.s_addr = INADDR_ANY;
	saddr.sin_port = htons(12345);
	int sfd, on = 1;
	sfd = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP);
	setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, (char*)&on, sizeof(on));
	bind(sfd, (struct sockaddr*) &saddr, sizeof(saddr));
	listen(sfd, 10);

	while (1) {
		sl = sizeof(caddr);
        n_cfd = accept(sfd, (struct sockaddr*)&caddr, &sl);
        if(n_cfd < 0){
            perror("Accept failed");
            continue;
        }
		pthread_mutex_lock(&clients_mutex);
        if (client_count < MAX_CLIENTS) {
            clients[client_count].socket_fd = n_cfd;
            clients[client_count].address = caddr;
            clients[client_count].block = 0;
            client_count++;

			printf("Aktualna lista klientów:\n");
		    for (int i = 0; i < client_count; i++) {
		        printf("Klient %d: %s:%d\n", i + 1,
		               inet_ntoa((struct in_addr)clients[i].address.sin_addr),
		               ntohs(clients[i].address.sin_port));
		    }
		    printf("\n");
			
            pthread_t client_thread;
            pthread_create(&client_thread, NULL, (void *(*)(void *))handle_client, (void *)(intptr_t)n_cfd);
            pthread_detach(client_thread);
        } 
        else {
            write(n_cfd, "Server is full\n", 15);
            close(n_cfd);
        }
        pthread_mutex_unlock(&clients_mutex);
    }
    close(sfd);
}
