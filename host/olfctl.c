/* SPDX-License-Identifier: Apache-2.0 */
/* Small native console client for the OLFs Signal Generator CDC shell. */
#ifdef __APPLE__
#define _DARWIN_C_SOURCE
#endif
#ifndef _WIN32
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <signal.h>
#include <errno.h>

#ifdef _WIN32
#include <windows.h>
static HANDLE port = INVALID_HANDLE_VALUE;
static uint64_t milliseconds(void) { return GetTickCount64(); }
static void pause_ms(void) { Sleep(10); }
static int open_port(const char *name)
{
    char path[256];
    if (strncmp(name, "\\\\.\\", 4) == 0) snprintf(path, sizeof(path), "%s", name);
    else snprintf(path, sizeof(path), "\\\\.\\%s", name);
    port = CreateFileA(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (port == INVALID_HANDLE_VALUE) return -1;
    DCB dcb = {0};
    dcb.DCBlength = sizeof(dcb);
    if (!GetCommState(port, &dcb)) return -1;
    dcb.BaudRate = CBR_115200;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    dcb.fBinary = TRUE;
    dcb.fParity = FALSE;
    dcb.fOutxCtsFlow = FALSE;
    dcb.fOutxDsrFlow = FALSE;
    dcb.fDtrControl = DTR_CONTROL_ENABLE;
    dcb.fRtsControl = RTS_CONTROL_DISABLE;
    dcb.fOutX = dcb.fInX = FALSE;
    if (!SetCommState(port, &dcb)) return -1;
    COMMTIMEOUTS timeout = {0};
    timeout.ReadIntervalTimeout = MAXDWORD;
    timeout.WriteTotalTimeoutConstant = 1000;
    if (!SetCommTimeouts(port, &timeout)) return -1;
    EscapeCommFunction(port, SETDTR);
    DWORD mode;
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    if (GetConsoleMode(output, &mode)) SetConsoleMode(output, mode | 4 /* VT processing */);
    return 0;
}
static int read_port(char *data, size_t size)
{
    DWORD count;
    return ReadFile(port, data, (DWORD)size, &count, NULL) ? (int)count : -1;
}
static int write_port(const char *data, size_t size)
{
    while (size) {
        DWORD written;
        if (!WriteFile(port, data, (DWORD)size, &written, NULL) || !written) return -1;
        data += written; size -= written;
    }
    return 0;
}
static void close_port(void)
{
    if (port != INVALID_HANDLE_VALUE) CloseHandle(port);
    port = INVALID_HANDLE_VALUE;
}
static void list_ports(void)
{
    char name[32], target[512];
    for (unsigned int i = 1; i <= 256; ++i) {
        snprintf(name, sizeof(name), "COM%u", i);
        if (QueryDosDeviceA(name, target, sizeof(target))) puts(name);
    }
}
#else
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <time.h>
#include <glob.h>
static int port = -1;
static struct termios saved;
static int have_saved;
static uint64_t milliseconds(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint64_t)now.tv_sec * 1000 + (unsigned long)now.tv_nsec / 1000000;
}
static void pause_ms(void) { struct timespec delay = {0, 10000000}; nanosleep(&delay, NULL); }
static int open_port(const char *name)
{
    port = open(name, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (port < 0 || tcgetattr(port, &saved) < 0) return -1;
    have_saved = 1;
    struct termios config = saved;
    cfmakeraw(&config);
    cfsetispeed(&config, B115200);
    cfsetospeed(&config, B115200);
    config.c_cflag |= CLOCAL | CREAD;
#ifdef CRTSCTS
    config.c_cflag &= ~CRTSCTS;
#endif
    config.c_cc[VMIN] = 0;
    config.c_cc[VTIME] = 0;
    if (tcsetattr(port, TCSANOW, &config) < 0) return -1;
    int dtr = TIOCM_DTR;
    /* PTYs used in tests do not implement modem control. */
    if (ioctl(port, TIOCMBIS, &dtr) < 0 && errno != ENOTTY && errno != EINVAL) return -1;
    return 0;
}
static int read_port(char *data, size_t size)
{
    ssize_t count = read(port, data, size);
    if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) return 0;
    return (int)count;
}
static int write_port(const char *data, size_t size)
{
    uint64_t deadline = milliseconds() + 2000;
    while (size) {
        ssize_t written = write(port, data, size);
        if (written > 0) { data += written; size -= (size_t)written; }
        else if (written < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) return -1;
        else if (milliseconds() > deadline) return -1;
        else pause_ms();
    }
    return 0;
}
static void close_port(void)
{
    if (port >= 0) {
        if (have_saved) tcsetattr(port, TCSANOW, &saved);
        close(port);
    }
    port = -1;
}
static void list_ports(void)
{
#ifdef __APPLE__
    const char *patterns[] = {"/dev/cu.usbmodem*", "/dev/cu.usbserial*"};
#else
    const char *patterns[] = {"/dev/ttyACM*", "/dev/ttyUSB*"};
#endif
    for (size_t i = 0; i < sizeof(patterns) / sizeof(patterns[0]); ++i) {
        glob_t paths = {0};
        if (glob(patterns[i], 0, NULL, &paths) == 0) {
            for (size_t j = 0; j < paths.gl_pathc; ++j) puts(paths.gl_pathv[j]);
        }
        globfree(&paths);
    }
}
#endif

static volatile sig_atomic_t interrupted;
static void stop(int sig) { (void)sig; interrupted = 1; }

static void help(void)
{
    puts("OLFs Signal Generator - console control\n"
         "Usage: olfctl --list\n"
         "       olfctl --port PORT [COMMAND ...]\n"
         "Without COMMAND: interactive line console; quit exits.\n"
         "Select the SHELL port, not the second (log) port. Close other terminals first.\n"
         "Commands (optional 'gen' prefix):\n"
         "  status | start [left|right|both] | stop [left|right|both]\n"
         "  wave sine|triangle|square [left|right|both]\n"
         "  freq 1..20000 [left|right|both] | amp 0..100 [left|right|both]\n"
         "  link on|off\n"
         "Other shell commands (help, gpio_app, log, history) pass through unchanged.\n"
         "Sample rate and 16/24-bit format are selected in the computer's audio settings.\n"
         "Examples:\n"
         "  olfctl --port COM7 freq 1000 left\n"
         "  ./olfctl --port /dev/ttyACM0 status\n"
         "  ./olfctl --port /dev/cu.usbmodemXXXX\n");
}

static int receive_reply(unsigned int max_wait)
{
    uint64_t started = milliseconds(), last = started;
    int received = 0;
    char buffer[512];
    while (!interrupted && milliseconds() - started < max_wait) {
        int count = read_port(buffer, sizeof(buffer));
        if (count < 0) { fputs("Serial read failed or device disconnected.\n", stderr); return -1; }
        if (count) {
            fwrite(buffer, 1, (size_t)count, stdout);
            fflush(stdout);
            last = milliseconds();
            received = 1;
        } else if (received && milliseconds() - last >= 200) break;
        else pause_ms();
    }
    return received;
}

static int send_command(const char *input)
{
    char line[512];
    size_t length = strcspn(input, "\r\n");
    if (!length) return 0;
    if (length >= sizeof(line) - 8) {
        fputs("Command too long.\n", stderr); return -1;
    }
    memcpy(line, input, length); line[length] = 0;
    const char *commands[] = {"status", "start", "stop", "wave", "freq", "amp", "link"};
    int prefix = 0;
    for (size_t i = 0; i < sizeof(commands) / sizeof(commands[0]); ++i) {
        size_t n = strlen(commands[i]);
        if (!strncmp(line, commands[i], n) && (line[n] == 0 || line[n] == ' ')) prefix = 1;
    }
    if ((prefix && write_port("gen ", 4)) || write_port(line, length) || write_port("\r", 1)) {
        fputs("Serial write failed.\n", stderr); return -1;
    }
    int reply = receive_reply(3000);
    if (!reply) fputs("No reply: verify the shell port and DTR, not the log port.\n", stderr);
    return reply > 0 ? 0 : -1;
}

int main(int argc, char **argv)
{
    if (argc == 1 || !strcmp(argv[1], "--help") || !strcmp(argv[1], "-h")) { help(); return 0; }
    if (argc == 2 && !strcmp(argv[1], "--list")) { list_ports(); return 0; }
    if (argc < 3 || strcmp(argv[1], "--port")) { help(); return 2; }
#ifdef _WIN32
    signal(SIGINT, stop);
    signal(SIGTERM, stop);
#else
    struct sigaction action = {0};
    action.sa_handler = stop;
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, NULL);
    sigaction(SIGTERM, &action, NULL);
#endif
    atexit(close_port);
    if (open_port(argv[2])) {
#ifdef _WIN32
        fprintf(stderr, "Cannot open %s (Windows error %lu).\n", argv[2], (unsigned long)GetLastError());
#else
        fprintf(stderr, "Cannot open %s: %s\n", argv[2], strerror(errno));
#endif
        return 1;
    }
    receive_reply(500);
    if (argc > 3) {
        char command[512] = {0};
        size_t used = 0;
        for (int i = 3; i < argc; ++i) {
            size_t n = strlen(argv[i]);
            if (used + n + 2 >= sizeof(command)) { fputs("Command too long.\n", stderr); return 2; }
            if (used) command[used++] = ' ';
            memcpy(command + used, argv[i], n + 1); used += n;
        }
        return send_command(command) ? 1 : 0;
    }
    puts("\nOLFs console. Type 'status', 'help' or 'quit'. Ctrl+C exits.");
    char line[512];
    while (!interrupted) {
        fputs("olfctl> ", stdout); fflush(stdout);
        if (!fgets(line, sizeof(line), stdin)) break;
        if (!strchr(line, '\n') && !feof(stdin)) {
            int ch; while ((ch = getchar()) != '\n' && ch != EOF) {}
            fputs("Command too long.\n", stderr); continue;
        }
        line[strcspn(line, "\r\n")] = 0;
        if (!strcmp(line, "quit") || !strcmp(line, "exit")) break;
        if (send_command(line)) return 1;
        puts("");
    }
    return 0;
}
