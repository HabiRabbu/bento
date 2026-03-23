// Registers a global shortcut via KF6 KGlobalAccel.
// Prints "PRESSED\n" to stdout when the shortcut is triggered.
// Prints "ERROR <reason>\n" on failure.
// Usage: bento-hotkey-helper [shortcut]
//   Default shortcut: Meta+Shift+Space

#include <QApplication>
#include <QAction>
#include <QKeySequence>
#include <QSocketNotifier>
#include <KGlobalAccel>
#include <cstdio>
#include <csignal>
#include <unistd.h>

// Self-pipe for async-signal-safe shutdown.
static int sigPipe[2] = {-1, -1};

static void signalHandler(int) {
    // write() is async-signal-safe; app->quit() is not.
    char c = 1;
    (void)write(sigPipe[1], &c, 1);
}

int main(int argc, char *argv[]) {
    auto *app = new QApplication(argc, argv);
    app->setApplicationName("bento");
    app->setDesktopFileName("bento");

    QString shortcut = argc > 1 ? QString(argv[1]) : "Meta+Shift+Space";

    // Validate the shortcut string.
    QKeySequence seq(shortcut);
    if (seq.isEmpty()) {
        std::fprintf(stderr, "Invalid shortcut: %s\n", qPrintable(shortcut));
        std::fputs("ERROR invalid shortcut\n", stdout);
        std::fflush(stdout);
        return 1;
    }

    auto *action = new QAction(app);
    action->setObjectName("toggle");
    action->setText("Toggle Bento Window");
    action->setProperty("componentName", "bento");
    action->setProperty("componentDisplayName", "Bento");

    KGlobalAccel::self()->setDefaultShortcut(action, {seq});
    bool ok = KGlobalAccel::self()->setShortcut(action, {seq});

    if (!ok) {
        std::fputs("ERROR shortcut registration failed\n", stdout);
        std::fflush(stdout);
        return 1;
    }

    QObject::connect(action, &QAction::triggered, [&]() {
        std::fputs("PRESSED\n", stdout);
        std::fflush(stdout);
    });

    // Set up self-pipe for signal handling.
    if (pipe(sigPipe) == 0) {
        auto *notifier = new QSocketNotifier(sigPipe[0], QSocketNotifier::Read, app);
        QObject::connect(notifier, &QSocketNotifier::activated, app, &QApplication::quit);
        std::signal(SIGTERM, signalHandler);
        std::signal(SIGINT, signalHandler);
    }

    std::fputs("READY\n", stdout);
    std::fflush(stdout);

    return app->exec();
}
