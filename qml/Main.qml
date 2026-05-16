// qml/Main.qml
// ─────────────
// Application shell.  Owns the ApplicationWindow, routes between screens,
// and listens to the VaultBridge for global state changes.
//
// Screen stack
// ────────────
//   "login"     LoginScreen.qml   – unlock / first-time setup
//   "dashboard" DashboardScreen.qml – main entries view (unlocked)
//
// No credentials flow through this file.

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root

    // ── Window geometry ─────────────────────
    width:  1280
    height: 800
    minimumWidth:  960
    minimumHeight: 640
    visible: true
    title:   "khazna"
    color:   Theme.bgBase

    // Remove OS chrome so TitleBar.qml owns the window frame
    flags: Qt.Window | Qt.FramelessWindowHint

    // ── Theme / palette ─────────────────────
    // Theme singleton is defined in qml/Theme.qml (registered as singleton)
    palette.accent: Theme.cyan

    // ── Screen router ────────────────────────
    property string currentScreen: vault.isLocked ? "login" : "dashboard"

    // ── Global connections ───────────────────
    Connections {
        target: vault

        function onAutoLocked() {
            root.currentScreen = "login"
            autoLockBanner.show()
        }

        function onUnlockFinished(success, message) {
            if (success) root.currentScreen = "dashboard"
        }

        function onLockStateChanged() {
            if (vault.isLocked)
                root.currentScreen = "login"
        }

        function onStatusMessage(text, colour) {
            statusToast.show(text, colour)
        }

        function onErrorOccurred(message) {
            statusToast.show(message, Theme.danger)
        }
    }

    // ── Root layout ──────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Custom frameless title bar
        TitleBar {
            id: titleBar
            Layout.fillWidth: true
            showMaximize: true
            window: root
        }

        // Screen content
        StackLayout {
            Layout.fillWidth:  true
            Layout.fillHeight: true
            currentIndex: root.currentScreen === "login" ? 0 : 1

            LoginScreen {
                id: loginScreen
            }

            DashboardScreen {
                id: dashboardScreen
            }
        }
    }

    // ── Auto-lock notification banner ────────
    AutoLockBanner {
        id: autoLockBanner
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 52
        z: 100
    }

    // ── Global status toast ──────────────────
    StatusToast {
        id: statusToast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        z: 100
    }

    // ── Window resize/drag edge (frameless) ──
    WindowResizeHandle { window: root }
}
