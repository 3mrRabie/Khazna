// qml/LoginScreen.qml
// ────────────────────
// Unlock / first-time vault setup screen.
//
// Security notes
// ──────────────
// • The password string is passed to vault.unlock() / vault.setupVault()
//   via a Slot call and then immediately cleared.
// • No plaintext password is stored in any persistent QML property.
// • The unlock is performed on a background thread (UnlockWorker in bridge.py);
//   the UI shows a loading indicator during the scrypt derivation.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"

Item {
    id: root

    // ── State ──────────────────────────────────
    readonly property bool isSetup: !vault.isInitialized
    property bool  _busy:      false
    property int   _countdown: 0
    property var   _recoveryDlg: null

    // ── Bridge connections ────────────────────
    Connections {
        target: vault

        function onUnlockStarted() {
            root._busy = true
        }

        function onUnlockFinished(success, message) {
            root._busy = false
            if (!success && message !== "") {
                errorLabel.text = message
                errorLabel.visible = true
                pwField.text = ""
            }
        }

        function onLockoutOccurred(message, seconds) {
            root._countdown = seconds
            countdownTimer.start()
            errorLabel.text    = message
            errorLabel.visible = true
        }
    }

    Timer {
        id: countdownTimer
        interval: 1000
        repeat:   true
        onTriggered: {
            root._countdown--
            if (root._countdown <= 0) {
                stop()
                actionBtn.enabled = true
                errorLabel.visible = false
            }
        }
    }

    // ── Background ────────────────────────────
    Rectangle {
        anchors.fill: parent
        color:        Theme.bgBase

        // Ambient purple glow — top center
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: -120
            width:  600; height: 600; radius: 300
            color:  "transparent"
            Rectangle {
                anchors.fill: parent; radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(124/255, 91/255, 245/255, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // Secondary cyan glow — bottom right
        Rectangle {
            anchors.right: parent.right; anchors.rightMargin: -80
            anchors.bottom: parent.bottom; anchors.bottomMargin: -80
            width: 400; height: 400; radius: 200
            color: "transparent"
            Rectangle {
                anchors.fill: parent; radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(34/255, 211/255, 238/255, 0.04) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }
    }

    // ── Card ──────────────────────────────────
    Rectangle {
        id: card
        anchors.centerIn: parent
        width:   440
        implicitHeight: cardLayout.implicitHeight + 72
        radius:  Theme.radiusXL
        color:   Theme.bgSurface
        border.color: Theme.bgBorder
        border.width: 1

        // Subtle glow behind card
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: parent.radius + 1
            color: "transparent"
            border.color: Theme.accentGlow
            border.width: 1
            z: -1
        }

        // Entrance animation
        opacity: 0
        scale:   0.96
        Component.onCompleted: entryAnim.start()

        ParallelAnimation {
            id: entryAnim
            NumberAnimation { target: card; property: "opacity"; from: 0; to: 1; duration: Theme.animSlow; easing.type: Easing.OutCubic }
            NumberAnimation { target: card; property: "scale";   from: 0.96; to: 1; duration: Theme.animSlow; easing.type: Easing.OutCubic }
        }

        ColumnLayout {
            id: cardLayout
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: Theme.spacingXL + 4
            spacing: Theme.spacingMD

            Item { height: 8 }

            // Shield icon
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 72; height: 72; radius: 20
                color: Theme.cyanBg

                Text {
                    anchors.centerIn: parent
                    text:  "🛡"
                    font.pointSize: 32
                }

                // Subtle rotating glow ring
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -2
                    radius: parent.radius + 2
                    color: "transparent"
                    border.color: Theme.cyanGlow
                    border.width: 1
                }
            }

            // Title
            Text {
                Layout.alignment: Qt.AlignHCenter
                text:  "khazna"
                color: Theme.textPrimary
                font.family:    Theme.fontFamily
                font.pointSize: Theme.fontSizeH1
                font.weight:    Font.Bold
                font.letterSpacing: -0.5
            }

            // Sub-title
            Text {
                Layout.alignment:  Qt.AlignHCenter
                Layout.fillWidth:  true
                horizontalAlignment: Text.AlignHCenter
                text:  root.isSetup
                    ? "Create a master password to protect your vault"
                    : "Enter your master password to unlock"
                color: Theme.textSecondary
                font.family:    Theme.fontFamily
                font.pointSize: Theme.fontSizeMD
                wrapMode: Text.Wrap
            }

            Item { height: 8 }

            // Password field
            SvField {
                id: pwField
                Layout.fillWidth: true
                placeholder: root.isSetup ? "Choose a strong master password" : "Master password"
                echoMode:    TextInput.Password
                showToggle:  true
                accessibleName: "Master password"
                onTextEdited: (t) => {
                    errorLabel.visible = false
                    if (root.isSetup) vault.checkStrength(t)
                }
                onAccepted: _submit()
            }

            // Strength bar (setup only)
            StrengthBar {
                id: setupStrength
                Layout.fillWidth: true
                visible: root.isSetup
            }

            // Confirm password (setup only)
            SvField {
                id: confirmField
                Layout.fillWidth: true
                visible:     root.isSetup
                placeholder: "Confirm master password"
                echoMode:    TextInput.Password
                showToggle:  true
                accessibleName: "Confirm master password"
                onAccepted: _submit()
            }

            // Setup warning
            Rectangle {
                Layout.fillWidth: true
                visible:    root.isSetup
                height:     warnRow.implicitHeight + 20
                radius:     Theme.radiusMD
                color:      Theme.warningBg
                border.color: Theme.warningBorder

                RowLayout {
                    id: warnRow
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    spacing: 10
                    Text { text: "⚠"; font.pointSize: Theme.fontSizeMD; color: Theme.warning }
                    Text {
                        Layout.fillWidth: true
                        text:  "Your master password cannot be recovered if lost.\nStore it somewhere safe."
                        color: Theme.warning
                        font.family:    Theme.fontFamily
                        font.pointSize: Theme.fontSizeSM
                        wrapMode: Text.Wrap
                        lineHeight: 1.3
                    }
                }
            }

            // Error label
            Rectangle {
                id: errorLabel
                Layout.fillWidth: true
                height:  errRow.implicitHeight + 18
                radius:  Theme.radiusMD
                color:   Theme.dangerBg
                border.color: Theme.dangerBorder
                visible: false
                property alias text: errText.text

                RowLayout {
                    id: errRow
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
                    spacing: 10
                    Text { text: "✗"; font.pointSize: Theme.fontSizeMD; color: Theme.danger; font.weight: Font.Bold }
                    Text {
                        id: errText
                        Layout.fillWidth: true
                        color: Theme.danger
                        font.family:    Theme.fontFamily
                        font.pointSize: Theme.fontSizeSM
                        wrapMode: Text.Wrap
                    }
                }
            }

            // Action button
            SvButton {
                id: actionBtn
                Layout.fillWidth: true
                implicitHeight:   48
                variant:          "primary"
                enabled:          !root._busy && root._countdown === 0
                text: {
                    if (root._busy)           return "Deriving key…"
                    if (root._countdown > 0)  return "Locked – " + root._countdown + " s"
                    return root.isSetup ? "Create Vault" : "Unlock Vault"
                }
                onClicked: _submit()
                Accessible.name: text
            }

            // Loading indicator
            Rectangle {
                Layout.fillWidth: true
                height: 3
                radius: 2
                color:  Theme.bgBorder
                visible: root._busy

                Rectangle {
                    id: progressBar
                    height: parent.height
                    width: 100
                    radius: 2
                    color: Theme.accent

                    SequentialAnimation on x {
                        loops: Animation.Infinite
                        running: root._busy
                        NumberAnimation { from: -100; to: progressBar.parent.width; duration: 1000; easing.type: Easing.InOutQuad }
                    }
                }
            }

            // Recovery link (Feature 6)
            Text {
                Layout.fillWidth: true
                visible: !root.isSetup
                text: "Forgot password? Use a recovery key"
                color: recoveryMa.containsMouse ? Theme.accent : Theme.textMuted
                font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM
                font.underline: recoveryMa.containsMouse
                horizontalAlignment: Text.AlignHCenter
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                MouseArea {
                    id: recoveryMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                    onClicked: {
                        if (!root._recoveryDlg) {
                            var comp = Qt.createComponent("RecoveryDialog.qml")
                            if (comp.status === Component.Ready)
                                root._recoveryDlg = comp.createObject(root)
                        }
                        if (root._recoveryDlg) {
                            root._recoveryDlg.showRecoveryFlow = true
                            root._recoveryDlg.open()
                        }
                    }
                }
            }

            Item { height: 4 }
        }
    }

    // ── Strength bar bridge connection ────────
    Connections {
        target: vault
        function onStrengthResult(score, level, colour, tips) {
            setupStrength.setStrength(score, level, colour, tips)
        }
    }

    // ── Submit handler ────────────────────────
    function _submit() {
        if (root._busy || root._countdown > 0) return
        errorLabel.visible = false

        var pw = pwField.text
        if (pw === "") { errorLabel.text = "Please enter a password."; errorLabel.visible = true; return }

        if (root.isSetup) {
            if (pw.length < 8)             { errorLabel.text = "Password must be at least 8 characters."; errorLabel.visible = true; return }
            if (pw !== confirmField.text)  { errorLabel.text = "Passwords do not match."; errorLabel.visible = true; return }
            vault.setupVault(pw)
        } else {
            vault.unlock(pw)
        }
        // Clear immediately — VaultBridge keeps only a local copy in the worker
        pwField.text      = ""
        confirmField.text = ""
    }
}
